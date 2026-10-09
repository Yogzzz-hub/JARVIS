import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import numpy as np
import pytest
from jarvis.core.commands.contracts import CommandRequest, CommandResult
from jarvis.core.commands.envelope import JarvisInputEnvelope
from jarvis.core.commands.service import CommandService
from jarvis.core.response.coordinator import ResponseCoordinator, ResponseLanguagePolicy, RESPONSE_LANGUAGE
from jarvis.core.tts.speech_service import JarvisSpeechResponseService, speech_segments
from jarvis.core.gateway.phone_voice import authorized
from jarvis.core.audio.wake import OpenWakeWordEngine
from jarvis.core.context.semantic_adapter import resolve_semantic_references


@pytest.mark.parametrize('source', ['http', 'voice', 'cli', 'whatsapp', 'websocket'])
def test_all_existing_command_sources_preserve_envelope(source):
    raw = '  GitHub Chrome open பண்ணு  '
    request = CommandRequest(text=raw, source=source, chat_id='thread')
    envelope = JarvisInputEnvelope.from_request(request)
    assert envelope.raw_text == raw and envelope.input_id == request.request_id
    assert envelope.conversation_id == 'thread' and envelope.authenticated_actor == 'owner'


def test_language_priority_and_phone_single_output():
    assert ResponseLanguagePolicy.choose('Chrome open பண்ணு') == 'MIXED_TAMIL_ENGLISH'
    assert ResponseLanguagePolicy.choose('hi', explicit='Tamil', conversation='English', contact='Tanglish') == 'TAMIL'
    assert ResponseLanguagePolicy.choose('hi', conversation='Tamil', contact='Tanglish') == 'TAMIL'
    assert ResponseLanguagePolicy.choose('hi', contact='Tanglish') == 'TANGLISH'
    envelope = JarvisInputEnvelope.from_request(CommandRequest(text='hello', source='websocket', metadata={'input_source':'phone'}))
    plan = ResponseCoordinator.plan(envelope)
    assert not plan.speak and plan.text_destination == 'phone' and plan.voice_destination is None
    coordinator = ResponseCoordinator(capacity=2)
    assert coordinator.claim_final('one') and not coordinator.claim_final('one')
    assert coordinator.claim_final('two') and coordinator.claim_final('three')
    assert len(coordinator.finals) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('text,owner,state', [('இந்த file delete பண்ணாத', True, 'CANCELLED'),
    ('Chrome open pannu', False, 'WAITING_FOR_USER')])
async def test_prohibition_and_external_contact_never_reach_execution(monkeypatch,text,owner,state):
    service = CommandService.__new__(CommandService)
    service._handle = AsyncMock()
    service._last_decisions = {}
    service.response = SimpleNamespace(enabled=False)
    monkeypatch.setattr('jarvis.core.language_shadow.get_language_service', lambda: SimpleNamespace(submit=Mock()))
    result = await service.handle(CommandRequest(text=text, source='whatsapp', is_owner=owner))
    assert result.state == state
    service._handle.assert_not_awaited()


@pytest.mark.asyncio
async def test_authenticated_owner_raw_text_reaches_existing_safety_path(monkeypatch):
    service = CommandService.__new__(CommandService)
    service._last_decisions = {}
    service.response = SimpleNamespace(enabled=False)
    observed = []
    async def old_path(request,clock):
        observed.append((request.metadata['input_envelope'], RESPONSE_LANGUAGE.get()))
        return CommandResult(request_id=request.request_id,state='SUCCESS',message='Verified.',metrics={})
    service._handle = old_path
    shadow = Mock()
    monkeypatch.setattr('jarvis.core.language_shadow.get_language_service', lambda: SimpleNamespace(submit=shadow))
    raw = 'backend status check pannu'
    result = await service.handle(CommandRequest(text=raw, source='whatsapp', is_owner=True))
    assert result.message == 'Verified.' and observed[0][0]['raw_text'] == raw
    assert RESPONSE_LANGUAGE.get() == 'ENGLISH'
    assert shadow.call_args.args[0] == raw


def test_phone_authentication_requires_tls_and_real_token(monkeypatch):
    monkeypatch.setenv('JARVIS_PHONE_TOKEN','a'*40)
    socket = SimpleNamespace(headers={'authorization':'Bearer '+'a'*40},scope={'scheme':'wss'})
    assert authorized(socket)
    socket.scope['scheme'] = 'ws'
    assert not authorized(socket)
    socket.scope['scheme'] = 'wss'
    socket.headers['authorization'] = 'Bearer friend-name'
    assert not authorized(socket)
    socket.headers = {'authorization':'Bearer '+'a'*40,'origin':'https://untrusted.example'}
    assert not authorized(socket)


def test_pronunciation_changes_speech_only_and_preserves_technical_tokens():
    raw = 'FastAPI backend running bro, Postgres connection um okay. pannu'
    parts = speech_segments(raw,'MIXED')
    joined = ' '.join(p for _,p in parts)
    assert 'FastAPI' in joined and 'Postgres' in joined and 'பண்ணு' in joined
    assert raw.endswith('pannu')


def test_common_tts_privacy_and_script_voice_selection():
    service = JarvisSpeechResponseService(piper_engine=SimpleNamespace(model_path='missing.onnx'),keep_warm=False)
    service.tamil = SimpleNamespace(synthesize=lambda t: np.ones(200,dtype=np.int16).tobytes(),_voice=None)
    pcm,backend = service.synthesize('வணக்கம்','TAMIL')
    assert pcm and backend == 'piper_tamil'
    assert service.synthesize('OTP 123456') == (b'', 'sensitive_text_suppressed')


def test_adaptation_is_bounded_and_does_not_lower_for_misses():
    wake = OpenWakeWordEngine(threshold=.5)
    for _ in range(1000): wake.observe_environment(.9, false_trigger=True)
    assert .5 <= wake.adaptive_threshold <= .95
    for _ in range(1000): wake.observe_environment(0)
    assert wake.adaptive_threshold >= .5


def test_unresolved_typed_reference_never_guesses():
    result = resolve_semantic_references({'raw_text':'previous mail', 'action':'DELETE',
        'references':[{'type':'EmailRef'}]},SimpleNamespace())
    assert result['recommendation'] == 'CLARIFY' and not result['controls_tools']


@pytest.mark.asyncio
async def test_phone_pcm_final_to_common_command_and_phone_only_audio(monkeypatch):
    from fastapi import FastAPI
    from jarvis.core.gateway.phone_voice import register
    monkeypatch.setenv('JARVIS_PHONE_TOKEN','b'*40)
    stt = SimpleNamespace(is_loaded=True, start_session=AsyncMock(), feed_audio=AsyncMock(),
        finalize=AsyncMock(return_value=SimpleNamespace(text='பேக்கெண்ட் நிலை என்ன', language='ta',finalization_ms=12)))
    voice = SimpleNamespace(stt=stt,stt_session_lock=asyncio.Lock(),remote_audio_active=False)
    async def handle(req):
        assert req.metadata['input_source']=='phone' and req.is_owner
        assert not CommandService.__new__(CommandService)._speaks(req)
        return CommandResult(request_id=req.request_id,state='SUCCESS',message='Backend is running.',metrics={})
    tts=SimpleNamespace(synthesize=Mock(return_value=(b'\x01\x00'*200,'mock')),sample_rate=22050)
    runtime=SimpleNamespace(voice=voice,service=SimpleNamespace(handle=handle,response=SimpleNamespace(tts=tts)))
    app=FastAPI(); register(app,runtime)
    socket=SimpleNamespace(headers={'authorization':'Bearer '+'b'*40},scope={'scheme':'wss'},
        accept=AsyncMock(),close=AsyncMock(),send_json=AsyncMock(),send_bytes=AsyncMock(),
        receive_json=AsyncMock(return_value={'type':'start'}),
        receive=AsyncMock(side_effect=[{'type':'websocket.receive','bytes':b'\x02\x00'*3200},
            {'type':'websocket.receive','text':'{"type":"stop"}'}]))
    await app.routes[-1].endpoint(socket)
    stt.finalize.assert_awaited_once()
    assert not voice.stt_session_lock.locked() and not voice.remote_audio_active
    socket.send_bytes.assert_awaited_once()
    assert socket.send_json.call_args_list[0].args[0]['language']=='TAMIL'


def test_preroll_retains_command_onset_instead_of_last_word_only():
    from jarvis.core.audio.ring_buffer import RingBuffer
    from jarvis.core.audio.frame import AudioFrame
    ring=RingBuffer(duration_ms=2000)
    samples=np.arange(12800,dtype=np.int16)
    for offset in range(0,len(samples),320):
        x=samples[offset:offset+320]
        ring.write(AudioFrame(0,0,16000,1,len(x),x.tobytes()))
    assert ring.read_last_ms(800)==samples.tobytes()


def test_optional_component_failure_does_not_hide_other_health(monkeypatch):
    from jarvis.core.response import status
    service=SimpleNamespace(enabled=lambda:True,process=None,pending=SimpleNamespace(qsize=lambda:0))
    monkeypatch.setattr(status,'get_language_service',lambda:service)
    monkeypatch.setattr(status,'ShadowStore',lambda:SimpleNamespace(state=lambda:{}))
    runtime=SimpleNamespace(voice=None,registry=object(),service=SimpleNamespace(response=SimpleNamespace(tts=None,audio_output=None)))
    result=status.integration_status(runtime)
    assert result['microphone']=='UNAVAILABLE' and result['tts']['state']=='UNAVAILABLE'
    assert result['capability_brain']=='READY' and result['language']['shadow_enabled']


def test_auto_stt_preserves_tamil_script_and_uses_multilingual_model():
    from jarvis.core.stt.faster_whisper_engine import FasterWhisperEngine
    engine=FasterWhisperEngine(model='small.en',language=None)
    assert engine.multilingual and not engine.thanglish
    assert engine.model_name_str=='small'
    assert engine._fix_names('வணக்கம்')=='வணக்கம்'


def test_tamil_combining_marks_do_not_inflate_speech_rate():
    from jarvis.core.stt.quality import _words, clean_transcript
    text='வணக்கம் சரிபார்ப்பு முடிந்தது'
    assert len(_words(text))==3
    assert clean_transcript(text,speech_ms=1800)==text
