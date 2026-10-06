"""Authenticated WSS thin-client boundary, sharing the PC STT and command service.

Disabled unless JARVIS_PHONE_TOKEN is configured. Never bind a new listener or
infer authentication from a device/contact name. TLS must be configured by the
existing gateway deployment; an unencrypted phone connection is refused.
"""
import asyncio
import hmac
import io
import json
import os
import wave
from uuid import uuid4
from fastapi import WebSocket, WebSocketDisconnect
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.response.coordinator import ResponseLanguagePolicy


def authorized(socket):
    token = os.environ.get('JARVIS_PHONE_TOKEN', '')
    supplied = socket.headers.get('authorization', '')
    return bool(len(token) >= 32 and socket.scope.get('scheme') == 'wss'
        and not socket.headers.get('origin')
        and hmac.compare_digest(supplied, 'Bearer ' + token))


def register(app, runtime):
    @app.websocket('/phone/voice')
    async def phone_voice(socket: WebSocket):
        if not authorized(socket):
            await socket.close(code=1008)
            return
        await socket.accept()
        voice = getattr(runtime, 'voice', None)
        owns_lock = False
        request_id = uuid4().hex
        try:
            start = await asyncio.wait_for(socket.receive_json(), 15)
            if start.get('type') not in {'start', 'command'}:
                raise ValueError('Expected start or command')
            if start['type'] == 'command':
                text = start.get('text', '')
                metadata = {}
            else:
                if start.get('sample_rate', 16000) != 16000 or start.get('channels', 1) != 1:
                    raise ValueError('Audio must be mono PCM16 at 16000 Hz')
                if not voice or not voice.stt or not voice.stt.is_loaded or voice.stt_session_lock.locked():
                    raise ValueError('Speech recognition is unavailable or busy; use typed input')
                await voice.stt_session_lock.acquire()
                owns_lock = True
                voice.remote_audio_active = True
                await voice.stt.start_session(request_id)
                received = 0
                deadline = asyncio.get_running_loop().time() + 30
                while True:
                    remaining = deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        raise ValueError('Audio session exceeded 30 seconds')
                    frame = await asyncio.wait_for(socket.receive(), remaining)
                    if frame['type'] == 'websocket.disconnect':
                        return
                    pcm = frame.get('bytes')
                    if pcm is not None:
                        if len(pcm) > 32768 or len(pcm) % 2:
                            raise ValueError('Invalid PCM frame')
                        received += len(pcm)
                        if received > 960000:
                            raise ValueError('Audio capacity exceeded')
                        await voice.stt.feed_audio(pcm)
                    else:
                        message = frame.get('text') or ''
                        if len(message) > 1024 or json.loads(message).get('type') != 'stop':
                            raise ValueError('Expected audio or stop')
                        break
                if received < 3200:
                    raise ValueError('Not enough speech; try again')
                transcript = await voice.stt.finalize()
                from jarvis.core.stt.uncertainty import requires_clarification
                if requires_clarification(transcript):
                    await socket.send_json({'type': 'clarify', 'message': 'Please repeat or type the request.',
                        'raw_transcript': transcript.raw_text or transcript.text,
                        'confidence': transcript.confidence, 'uncertain_spans': transcript.uncertain_spans})
                    return
                text = transcript.text
                metadata = {'audio_metadata': {'sample_rate': 16000, 'bytes': received,
                    'session_id': request_id, 'stt_language': transcript.language,
                    'stt_final_ms': transcript.finalization_ms,
                    'raw_text': getattr(transcript, 'raw_text', None) or transcript.text,
                    'confidence': getattr(transcript, 'confidence', None),
                    'uncertain_spans': getattr(transcript, 'uncertain_spans', []),
                    'alternatives': getattr(transcript, 'alternatives', [])}}
                voice.remote_audio_active = False
                voice.stt_session_lock.release()
                owns_lock = False
            selected = ResponseLanguagePolicy.choose(text)
            result = await runtime.service.handle(CommandRequest(text=text, request_id=request_id,
                source='websocket', is_owner=True, trust_level='AUTHENTICATED_OWNER',
                metadata={**metadata, 'input_source': 'phone', 'conversation_id': 'phone',
                    'response_language': selected}))
            await socket.send_json({'type': 'result', 'language': selected, **result.model_dump(mode='json')})
            if start.get('reply_voice', True):
                tts = runtime.service.response.tts
                pcm, backend = await asyncio.to_thread(tts.synthesize, result.message, language=selected, device_target='phone')
                if pcm:
                    buffer = io.BytesIO()
                    with wave.open(buffer, 'wb') as out:
                        out.setnchannels(1); out.setsampwidth(2); out.setframerate(tts.sample_rate)
                        out.writeframes(pcm)
                    await socket.send_json({'type': 'audio', 'format': 'wav', 'backend': backend,
                        'request_id': request_id, 'bytes': len(buffer.getvalue())})
                    await socket.send_bytes(buffer.getvalue())
        except (ValueError, asyncio.TimeoutError):
            await socket.send_json({'type': 'error', 'message': 'Phone input could not be completed. Check audio format or try typed input.'})
        except WebSocketDisconnect:
            pass
        except Exception:
            # Optional phone failures do not abort local voice or expose traces.
            try:
                await socket.send_json({'type': 'error', 'message': 'Phone voice is unavailable right now. Try typed input.'})
            except (RuntimeError, WebSocketDisconnect):
                pass
        finally:
            if owns_lock:
                voice.remote_audio_active = False
                voice.stt_session_lock.release()
            try:
                await socket.close()
            except RuntimeError:
                pass
