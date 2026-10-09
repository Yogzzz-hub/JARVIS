import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import numpy as np
import pytest
from jarvis.core.audio.owner_benchmark import OwnerVoiceBenchmark, prompts, wake_metrics
from jarvis.core.audio.pipeline import VoicePipeline
from jarvis.core.stt.uncertainty import transcript_evidence
from jarvis.core.stt.faster_whisper_engine import FasterWhisperEngine
from jarvis.core.stt.vocabulary import JarvisSpeechVocabulary
from jarvis.core.tts.speech_service import JarvisSpeechResponseService, speech_segments


@pytest.mark.parametrize('text', ['Deepa ku file anupu', 'Postgres connection check பண்ணு',
    'FastAPI backend status என்ன', '4 mani ku remind pannu'])
def test_original_entities_and_unicode_never_fuzzy_replaced(text):
    engine = FasterWhisperEngine(language=None)
    engine.vocabulary = SimpleNamespace(correct=Mock(side_effect=AssertionError('Must not rewrite')))
    assert engine._fix_names(text) == text


@pytest.mark.parametrize('token', ['Deepa', 'report.pdf', '4', 'Postgres'])
def test_uncertain_entities_require_clarification(token):
    evidence = transcript_evidence('send '+token, [{'kept': True, 'words': [
        {'word': 'send', 'probability': .99}, {'word': token, 'probability': .4}]}])
    assert evidence['clarification_required']
    assert evidence['uncertain_spans'][0]['text'] == token
    assert evidence['raw_text'] == 'send '+token


def test_missing_word_evidence_never_treated_as_certainty():
    assert transcript_evidence('delete report.pdf', [])['clarification_required']
    assert not transcript_evidence('', [])['clarification_required']


def test_vocabulary_is_bounded_and_uses_metadata():
    provider = JarvisSpeechVocabulary.from_metadata(apps=['Chrome'], projects=['JarvisEdge'],
        contacts=['Deepa'], capabilities=['google.gmail'])
    text = provider.generate_prompt()
    assert 'Deepa' in text and 'JarvisEdge' in text and 'FastAPI' in text
    assert len(text) <= 152


def test_no_owner_recordings_no_fabricated_metrics(tmp_path):
    state = OwnerVoiceBenchmark(None, tmp_path).state()
    assert state['real_recordings'] == 0
    assert state['bare']['TP'] is None and state['hey']['TP'] is None
    assert state['bare']['state'] == 'OWNER_MIC_BENCHMARK_PENDING'
    assert state['stt_semantic_pass_rate'] is None
    assert not state['training_admission'] and not state['tools_executed']


def test_bare_and_hey_scored_independently_with_real_negative_duration():
    data = []
    for family, expected, detected in [('bare', True, False), ('hey', True, True), ('negative', False, False)]:
        data.append({'prompt': {'kind': 'wake' if expected else 'background',
            'wake_family': family, 'expected_wake': expected}, 'duration_s': 7,
            'wake': {'detected': detected, 'latency_from_energy_onset_ms': 100 if detected else None}})
    assert wake_metrics(data, 'bare')['FNR'] == 1
    assert wake_metrics(data, 'hey')['TPR'] == 1
    assert wake_metrics(data, 'bare')['negative_seconds'] == 7


def test_prompts_cover_languages_and_conditions_without_mass_recording():
    rows = prompts()
    assert len(rows) == 26 and len({p['id'] for p in rows}) == 26
    assert sum(p['expected_wake'] for p in rows) == 10
    assert {'ENGLISH', 'TANGLISH', 'TAMIL', 'MIXED'} <= {p['language'] for p in rows}


def test_listening_reviews_are_separate_from_accuracy(tmp_path):
    benchmark = OwnerVoiceBenchmark(None, tmp_path)
    benchmark.rate('TAMIL', 'CLEAR')
    assert benchmark.state()['listening_ratings']['TAMIL'] == 'CLEAR'
    assert benchmark.state()['real_recordings'] == 0
    with pytest.raises(ValueError): benchmark.rate('TAMIL', 'AUTO_APPROVE')


@pytest.mark.asyncio
async def test_benchmark_blocks_live_session_and_never_routes():
    voice = VoicePipeline(wake_enabled=False)
    voice.benchmark_active = True
    voice._handle_speech_session_unlocked = AsyncMock()
    await voice._handle_speech_session()
    voice._handle_speech_session_unlocked.assert_not_awaited()


@pytest.mark.asyncio
async def test_recording_requires_available_owner_microphone(tmp_path):
    benchmark = OwnerVoiceBenchmark(SimpleNamespace(voice=None), tmp_path)
    with pytest.raises(ValueError): await benchmark.record('w01')
    assert not list(tmp_path.rglob('*.wav'))


def test_preroll_actual_config_preserves_1500ms():
    from jarvis.config import load
    from jarvis.core.audio.ring_buffer import RingBuffer
    from jarvis.core.audio.frame import AudioFrame
    assert load().voice.preroll_ms >= 1500
    ring = RingBuffer(duration_ms=2000)
    samples = np.arange(24000, dtype=np.int16)
    for start in range(0, len(samples), 320):
        pcm = samples[start:start+320].tobytes()
        ring.write(AudioFrame(0, 0, 16000, 1, len(pcm)//2, pcm))
    assert ring.read_last_ms(1500) == samples.tobytes()


@pytest.mark.asyncio
async def test_sentence_stream_preserves_order_and_cancels_remaining_chunks():
    service = JarvisSpeechResponseService(keep_warm=False)
    calls = []
    def synthesize(text):
        calls.append(text); return b'\x01\x00'*100, 'mock'
    service.synthesize = synthesize
    chunks = []
    async for chunk, backend in service.stream('Checking FastAPI. Backend is running.'):
        chunks.append(chunk)
        service.cancel()
    assert calls == ['Checking FastAPI.'] and len(chunks) == 1
    assert chunks[0].first_chunk and not chunks[0].is_final


def test_pronunciation_dictionary_never_changes_technical_terms():
    value = speech_segments('FastAPI Postgres enna epdi illa', 'TANGLISH')
    assert value[0] == ('ENGLISH', 'FastAPI Postgres')
    assert value[1][0] == 'TAMIL'


def test_original_wake_threshold_not_lowered():
    from jarvis.config import load
    assert load().voice.threshold == .5


def test_tamil_activation_and_first_command_word_preserved():
    assert VoicePipeline._strip_wake_phrase('ஜார்விஸ் Chrome open பண்ணு') == 'Chrome open பண்ணு'
    assert VoicePipeline._strip_wake_phrase('Jarvis open Chrome') == 'open Chrome'
    assert VoicePipeline._strip_wake_phrase('JarvisEdge open project') == 'JarvisEdge open project'


def test_compatible_bare_and_hey_share_one_cpu_engine(tmp_path, monkeypatch):
    import hashlib, json, sys
    from jarvis.core.audio.wake import OpenWakeWordEngine
    hey = tmp_path/'hey.onnx'; hey.write_bytes(b'hey')
    bare = tmp_path/'jarvis_bare.onnx'; bare.write_bytes(b'bare')
    bare.with_suffix('.manifest.json').write_text(json.dumps({'phrase': 'Jarvis',
        'sha256': hashlib.sha256(bare.read_bytes()).hexdigest()}))
    calls = []
    class FakeModel:
        def __init__(self, **kwargs):
            calls.append(kwargs); self.models = {'bare': object(), 'hey': object()}
    monkeypatch.setitem(sys.modules, 'openwakeword.model', SimpleNamespace(Model=FakeModel))
    engine = OpenWakeWordEngine(str(hey), bare_model_path=str(bare))
    engine._ensure_loaded()
    assert len(calls) == 1
    assert calls[0]['inference_framework'] == 'onnx'
    assert calls[0]['wakeword_models'] == [str(bare), str(hey)]
    assert engine.bare_model_state == 'LOADED_OWNER_ACCEPTANCE_REQUIRED'


def test_bare_hash_mismatch_keeps_hey_without_lowering_threshold(tmp_path, monkeypatch):
    import json, sys
    from jarvis.core.audio.wake import OpenWakeWordEngine
    hey = tmp_path/'hey.onnx'; hey.write_bytes(b'hey')
    bare = tmp_path/'jarvis_bare.onnx'; bare.write_bytes(b'bare')
    bare.with_suffix('.manifest.json').write_text(json.dumps({'phrase': 'Jarvis', 'sha256': 'wrong'}))
    calls = []
    class FakeModel:
        def __init__(self, **kwargs): calls.append(kwargs); self.models = {'hey': object()}
    monkeypatch.setitem(sys.modules, 'openwakeword.model', SimpleNamespace(Model=FakeModel))
    engine = OpenWakeWordEngine(str(hey), bare_model_path=str(bare))
    engine._ensure_loaded()
    assert calls[0]['wakeword_models'] == [str(hey)]
    assert engine.bare_model_state == 'HASH_OR_PHRASE_MISMATCH' and engine.threshold == .5


def test_benchmark_write_nonce_and_audio_allowlist():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from jarvis.core.gateway.dashboard_api import register
    app = FastAPI(); register(app, None)
    client = TestClient(app)
    assert client.post('/dashboard/voice-benchmark/rating', json={'language': 'TAMIL', 'rating': 'CLEAR'}).status_code == 403
    assert client.get('/dashboard/voice-benchmark/audio/credentials').status_code == 404
    assert 'Record this prompt' in client.get('/dashboard/voice-benchmark/page').text


@pytest.mark.asyncio
async def test_sentence_one_plays_before_sentence_two_and_failure_does_not_repeat():
    from jarvis.core.response.engine import ResponseEngine
    from jarvis.core.tts.base import TTSChunk
    played = []
    async def stream(text):
        yield TTSChunk(pcm=b'\x01\x00'*100, sample_rate=22050, is_final=False, first_chunk=True), 'mock'
        assert len(played) == 1  # no lookahead delay
        raise RuntimeError('Second sentence failed')
    tts = SimpleNamespace(complete_sentence_chunks=True, stream=stream,
        sample_rate=22050, synthesize=Mock(side_effect=AssertionError('Do not replay full result')))
    output = SimpleNamespace(play=lambda response: played.append(response) or True)
    response = ResponseEngine(tts_manager=tts, audio_output=output)
    response.schedule_final('r1', 'Sentence one. Sentence two.')
    response.schedule_final('r1', 'Sentence one. Sentence two.')
    await asyncio.sleep(.1)
    assert len(played) == 1
    tts.synthesize.assert_not_called()


@pytest.mark.asyncio
async def test_phone_uncertainty_never_reaches_command_service(monkeypatch):
    from fastapi import FastAPI
    from jarvis.core.gateway.phone_voice import register
    from jarvis.core.stt.base import TranscriptFinal
    monkeypatch.setenv('JARVIS_PHONE_TOKEN', 'b'*40)
    transcript = TranscriptFinal('test', 'send file to Deepa', raw_text='send file to Deepa',
        confidence=.4, uncertain_spans=[{'text': 'Deepa'}], clarification_required=True)
    stt = SimpleNamespace(is_loaded=True, start_session=AsyncMock(), feed_audio=AsyncMock(),
        finalize=AsyncMock(return_value=transcript))
    voice = SimpleNamespace(stt=stt, stt_session_lock=asyncio.Lock(), remote_audio_active=False)
    handle = AsyncMock()
    app = FastAPI(); register(app, SimpleNamespace(voice=voice, service=SimpleNamespace(handle=handle)))
    socket = SimpleNamespace(headers={'authorization': 'Bearer '+'b'*40}, scope={'scheme': 'wss'},
        accept=AsyncMock(), close=AsyncMock(), send_json=AsyncMock(), send_bytes=AsyncMock(),
        receive_json=AsyncMock(return_value={'type': 'start'}), receive=AsyncMock(side_effect=[
            {'type': 'websocket.receive', 'bytes': b'\x02\x00'*3200},
            {'type': 'websocket.receive', 'text': '{"type":"stop"}'}]))
    await app.routes[-1].endpoint(socket)
    handle.assert_not_awaited(); socket.send_bytes.assert_not_awaited()
    assert socket.send_json.call_args_list[0].args[0]['type'] == 'clarify'
    assert not voice.stt_session_lock.locked()


@pytest.mark.asyncio
async def test_interrupted_acceptance_claim_cannot_be_overwritten(tmp_path):
    import json
    directory = tmp_path/'interrupted'; directory.mkdir()
    claim = json.dumps({'prompt': {'id': 'w01'}})
    (directory/'claim.json').write_text(claim)
    voice = SimpleNamespace(is_running=True, stt=SimpleNamespace(is_loaded=True),
        stt_session_lock=asyncio.Lock(), _session=None, _command_tasks=[])
    benchmark = OwnerVoiceBenchmark(SimpleNamespace(voice=voice), tmp_path)
    with pytest.raises(ValueError, match='already recorded'):
        await benchmark.record('w01')
    assert (directory/'claim.json').read_text() == claim


def test_rejected_segment_cannot_remove_critical_negation_and_execute_rest():
    evidence = transcript_evidence('delete file', [
        {'kept': True, 'words': [{'word': 'delete', 'probability': .99}, {'word': 'file', 'probability': .99}]},
        {'kept': False, 'text': 'not'}])
    assert evidence['clarification_required']


@pytest.mark.asyncio
async def test_disappeared_microphone_fails_without_selecting_other_device():
    from jarvis.core.audio.source import MicSource
    mic = MicSource(device='Owner microphone')
    mic._running = True; mic._stream = SimpleNamespace(active=False)
    with pytest.raises(RuntimeError, match='disconnected'):
        await mic.frames().__anext__()
    assert mic.device == 'Owner microphone' and not mic._running
    assert mic.device_health == 'DISCONNECTED_TYPED_INPUT_REQUIRED'


@pytest.mark.asyncio
async def test_capture_loss_stops_voice_but_does_not_invent_command():
    hub = SimpleNamespace(source=SimpleNamespace(_running=False))
    service = SimpleNamespace(handle=AsyncMock())
    voice = VoicePipeline(hub=hub, command_service=service)
    voice._running = True
    assert await voice._wait_for_trigger() is None
    service.handle.assert_not_awaited()
    assert not voice.is_running and 'typed input' in voice.last_error


@pytest.mark.asyncio
@pytest.mark.parametrize('worker_unavailable', [False, True])
async def test_owner_capture_uses_shared_hub_and_stt_without_executing(tmp_path, monkeypatch, worker_unavailable):
    from time import perf_counter_ns
    from jarvis.core.audio.frame import AudioFrame
    from jarvis.core.audio.hub import AudioConsumer
    from jarvis.core.stt.base import TranscriptFinal
    import jarvis.core.language_shadow as language_shadow
    class FakeHub:
        source = SimpleNamespace(selected_device={'name': 'TEST_FIXTURE_ONLY'})
        def register(self, *args, **kwargs):
            self.consumer = AudioConsumer('test', queue_size=400)
            async def produce():
                while True:
                    self.consumer.put(AudioFrame(0, perf_counter_ns(), 16000, 1, 320,
                        (np.ones(320, dtype=np.int16)*1000).tobytes()))
                    await asyncio.sleep(.02)
            self.task = asyncio.create_task(produce())
            return self.consumer
        def unregister(self, consumer): self.task.cancel()
    hub = FakeHub()
    stt = SimpleNamespace(is_loaded=True, start_session=AsyncMock(), feed_audio=AsyncMock(),
        finalize=AsyncMock(return_value=TranscriptFinal('test', 'Jarvis open Chrome', confidence=.99)))
    wake = SimpleNamespace(reset=Mock(), last_score=.9, last_inference_ms=1,
        threshold=.5, adaptive_threshold=.5, feed=Mock(return_value=SimpleNamespace(detected=True)))
    voice = VoicePipeline(hub=hub, stt_engine=stt, wake_engine=wake)
    voice._running = True
    response = SimpleNamespace(stop_speaking=Mock(), close_followup_window=Mock())
    service = SimpleNamespace(response=response, handle=AsyncMock(),
        router=SimpleNamespace(preview=AsyncMock(return_value=SimpleNamespace(intent='open_app', slots={'app': 'Chrome'}))))
    candidate = AsyncMock(return_value={'candidate': {'action': 'OPEN'}, 'controls_tools': False})
    if worker_unavailable:
        candidate.side_effect = RuntimeError('Optional advisory worker unavailable')
    monkeypatch.setattr(language_shadow, 'get_language_service', lambda: SimpleNamespace(benchmark_preview=candidate))
    benchmark = OwnerVoiceBenchmark(SimpleNamespace(voice=voice, service=service), tmp_path)
    result = await benchmark.record('w04')
    assert result['tools_executed'] is False and result['training_allowed'] is False
    service.handle.assert_not_awaited()
    service.router.preview.assert_awaited_once_with('open Chrome')
    candidate.assert_awaited_once_with('open Chrome')
    assert len(list(tmp_path.rglob('microphone.wav'))) == 1
    assert not voice.benchmark_active and not voice.stt_session_lock.locked()
    assert voice.input_epoch == 2
    assert voice.hub.discard_before_ns > 0
    assert not voice.ptt_engine._triggered
    if worker_unavailable:
        assert result['candidate']['state'] == 'UNAVAILABLE'
    assert benchmark.state()['real_recordings'] == 1  # temporary fixture store only


@pytest.mark.asyncio
async def test_sapi_loaded_on_main_synthesizes_on_workers_without_shared_com_loop():
    import os
    if os.name != 'nt': pytest.skip('Windows fallback only')
    pytest.importorskip('pythoncom'); pytest.importorskip('win32com.client')
    from jarvis.core.tts.sapi_engine import SAPIEngine
    engine = SAPIEngine(); engine.load()
    assert engine.is_loaded
    results = await asyncio.wait_for(asyncio.gather(*[
        asyncio.to_thread(engine.synthesize, 'Fallback check.') for _ in range(3)]), 8)
    assert all(len(pcm) > 0 for pcm in results)


@pytest.mark.asyncio
async def test_queued_voice_session_cannot_cross_owner_capture_epoch():
    voice = VoicePipeline(hub=SimpleNamespace())
    voice._handle_speech_session_unlocked = AsyncMock()
    await voice.stt_session_lock.acquire()
    queued = asyncio.create_task(voice._handle_speech_session())
    await asyncio.sleep(0)
    voice.input_epoch += 2
    voice.stt_session_lock.release()
    await queued
    voice._handle_speech_session_unlocked.assert_not_awaited()
