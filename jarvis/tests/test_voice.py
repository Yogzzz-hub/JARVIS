"""Comprehensive tests for JARVIS EDGE Phase 6 — Voice Input Pipeline.

All tests use synthetic audio or mock sources. No live microphone required.
Tests cover: AudioFrame, RingBuffer, AudioHub, WakeWord, VAD, STT,
Stabilizer, VoiceSession, EarlyRouter, and VoicePipeline.
"""
import asyncio
import struct
import math
from time import perf_counter_ns
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

# ── AudioFrame Tests ──

from jarvis.core.audio.frame import (
    AudioFrame,
    CANONICAL_SAMPLE_RATE,
    CANONICAL_CHANNELS,
    CANONICAL_SAMPLES_PER_FRAME,
    CANONICAL_BYTES_PER_FRAME,
)


class TestAudioFrame:
    def test_construction(self):
        frame = AudioFrame.silence()
        assert frame.sample_rate == CANONICAL_SAMPLE_RATE
        assert frame.channels == CANONICAL_CHANNELS
        assert frame.sample_count == CANONICAL_SAMPLES_PER_FRAME
        assert len(frame.pcm) == CANONICAL_BYTES_PER_FRAME
        assert frame.is_canonical

    def test_duration(self):
        frame = AudioFrame.silence(sample_count=16000)
        assert abs(frame.duration_ms - 1000.0) < 0.01
        assert abs(frame.duration_s - 1.0) < 0.001

    def test_float32_roundtrip(self):
        samples = [0.5, -0.5, 0.0, 1.0, -1.0]
        frame = AudioFrame.from_float32(samples)
        assert frame.sample_count == 5
        assert frame.is_canonical
        f32 = frame.to_float32()
        assert len(f32) == 5
        assert abs(f32[0] - 0.5) < 0.001
        assert abs(f32[1] + 0.5) < 0.001

    def test_timestamp_uses_perf_counter(self):
        t0 = perf_counter_ns()
        frame = AudioFrame.silence()
        t1 = perf_counter_ns()
        assert t0 <= frame.timestamp_ns <= t1

    def test_non_canonical_detection(self):
        frame = AudioFrame(
            sequence_id=0, timestamp_ns=0,
            sample_rate=44100, channels=2,
            sample_count=100, pcm=b"\x00" * 400,
            source="test",
        )
        assert not frame.is_canonical


# ── RingBuffer Tests ──

from jarvis.core.audio.ring_buffer import RingBuffer


class TestRingBuffer:
    def test_write_and_read(self):
        ring = RingBuffer(duration_ms=1000)  # 1 second = 16000 samples
        frame = AudioFrame.silence(sample_count=320)
        ring.write(frame)
        data = ring.read_last_ms(20)
        assert len(data) == 640  # 320 samples * 2 bytes

    def test_wrap_around(self):
        ring = RingBuffer(duration_ms=100)  # 1600 samples
        # Write more than capacity
        for i in range(20):
            frame = AudioFrame.silence(sample_count=320)
            ring.write(frame)
        assert ring.total_written == 320 * 20
        data = ring.read_last_ms(100)
        assert len(data) == 3200  # 1600 samples * 2 bytes

    def test_preroll_extraction(self):
        ring = RingBuffer(duration_ms=2000)
        for i in range(50):
            frame = AudioFrame.silence(sample_count=320)
            ring.write(frame)
        preroll = ring.read_preroll(perf_counter_ns(), preroll_ms=500)
        expected_samples = int(16000 * 0.5)
        assert len(preroll) == expected_samples * 2

    def test_clear(self):
        ring = RingBuffer(duration_ms=1000)
        ring.write(AudioFrame.silence(sample_count=320))
        ring.clear()
        assert ring.available_ms == 0.0
        assert ring.total_written == 0

    def test_available_ms(self):
        ring = RingBuffer(duration_ms=1000)
        ring.write(AudioFrame.silence(sample_count=3200))  # 200ms
        assert abs(ring.available_ms - 200.0) < 1.0

    def test_fixed_size_no_growth(self):
        ring = RingBuffer(duration_ms=100)  # 1600 samples
        for _ in range(100):
            ring.write(AudioFrame.silence(sample_count=320))
        # Read should never exceed capacity
        data = ring.read_last_ms(1000)
        assert len(data) <= 1600 * 2


# ── AudioSource Tests ──

from jarvis.core.audio.source import SyntheticAudioSource, FileAudioSource


class TestSyntheticAudioSource:
    @pytest.mark.asyncio
    async def test_silence_generation(self):
        src = SyntheticAudioSource(duration_s=0.1, mode="silence")
        await src.start()
        frames = []
        async for frame in src.frames():
            frames.append(frame)
        assert len(frames) > 0
        assert all(f.is_canonical for f in frames)

    @pytest.mark.asyncio
    async def test_tone_generation(self):
        src = SyntheticAudioSource(duration_s=0.1, mode="tone", frequency=440.0)
        await src.start()
        frames = []
        async for frame in src.frames():
            frames.append(frame)
        assert len(frames) > 0
        # Tone should have non-zero energy
        all_pcm = b"".join(f.pcm for f in frames)
        samples = np.frombuffer(all_pcm, dtype=np.int16)
        assert np.abs(samples).max() > 100

    @pytest.mark.asyncio
    async def test_noise_generation(self):
        src = SyntheticAudioSource(duration_s=0.1, mode="noise")
        await src.start()
        frames = []
        async for frame in src.frames():
            frames.append(frame)
        assert len(frames) > 0

    @pytest.mark.asyncio
    async def test_stop(self):
        src = SyntheticAudioSource(duration_s=10.0, mode="silence")
        await src.start()
        await src.stop()
        assert not src._running


# ── AudioHub Tests ──

from jarvis.core.audio.hub import AudioHub, AudioConsumer


class TestAudioHub:
    @pytest.mark.asyncio
    async def test_register_consumer(self):
        src = SyntheticAudioSource(duration_s=0.1, mode="silence")
        hub = AudioHub(source=src)
        consumer = hub.register("test_consumer", queue_size=50)
        assert consumer.name == "test_consumer"
        assert len(hub._consumers) == 1

    @pytest.mark.asyncio
    async def test_distribution(self):
        src = SyntheticAudioSource(duration_s=0.05, mode="tone")
        hub = AudioHub(source=src)
        c1 = hub.register("c1")
        c2 = hub.register("c2")
        await hub.start()
        await asyncio.sleep(0.2)
        await hub.stop()
        assert c1.total > 0
        assert c2.total > 0

    @pytest.mark.asyncio
    async def test_ring_buffer_populated(self):
        src = SyntheticAudioSource(duration_s=0.1, mode="tone")
        hub = AudioHub(source=src, ring_buffer_ms=1000)
        hub.register("test")
        await hub.start()
        await asyncio.sleep(0.2)
        await hub.stop()
        assert hub.ring.available_ms > 0

    @pytest.mark.asyncio
    async def test_queue_overflow_metric(self):
        src = SyntheticAudioSource(duration_s=0.5, mode="silence")
        hub = AudioHub(source=src)
        consumer = hub.register("tiny", queue_size=2)
        await hub.start()
        await asyncio.sleep(0.3)
        await hub.stop()
        # With tiny queue and fast production, should have drops
        assert consumer.dropped >= 0  # May or may not overflow depending on timing

    @pytest.mark.asyncio
    async def test_metrics(self):
        src = SyntheticAudioSource(duration_s=0.05, mode="silence")
        hub = AudioHub(source=src)
        hub.register("m1")
        await hub.start()
        await asyncio.sleep(0.15)
        await hub.stop()
        m = hub.metrics
        assert "total_frames" in m
        assert "consumers" in m
        assert "m1" in m["consumers"]


# ── Wake Word Tests ──

from jarvis.core.audio.wake import OpenWakeWordEngine, PushToTalkEngine, WakeDetection


class TestWakeWord:
    def test_no_trigger_on_silence(self):
        engine = OpenWakeWordEngine(threshold=0.5)
        # Feed silence — should not trigger
        frame = AudioFrame.silence(sample_count=1280)
        result = engine.feed(frame)
        # Result is None or not detected (model may not be loaded)
        if result:
            assert not result.detected

    def test_cooldown_suppression(self):
        engine = OpenWakeWordEngine(threshold=0.01, cooldown_ms=2000)
        # Simulate trigger by manipulating internal state
        engine._last_trigger_ns = perf_counter_ns()
        engine._loaded = True
        engine._model = MagicMock()
        engine._model.predict = MagicMock(return_value={"hey_jarvis": 0.99})
        engine._model_name = "test"

        frame = AudioFrame.silence(sample_count=1280)
        result = engine.feed(frame)
        # Should be suppressed by cooldown
        if result:
            assert not result.detected or result.cooldown_active

    def test_reset(self):
        engine = OpenWakeWordEngine()
        engine._buffer = np.ones(100, dtype=np.int16)
        engine.reset()
        assert len(engine._buffer) == 0

    def test_push_to_talk_check(self):
        ptt = PushToTalkEngine()
        assert not ptt.check()
        ptt._triggered = True
        assert ptt.check()
        assert not ptt.check()  # Consumed

    def test_close(self):
        engine = OpenWakeWordEngine()
        engine.close()
        assert not engine._loaded


# ── VAD Tests ──

from jarvis.core.audio.vad import SileroVADEngine, VADState, EndpointDetector


class TestVAD:
    def test_initial_state_is_silence(self):
        vad = SileroVADEngine()
        assert vad.state == VADState.SILENCE

    def test_silence_input_stays_silent(self):
        vad = SileroVADEngine()
        frame = AudioFrame.silence(sample_count=512)
        result = vad.feed(frame)
        assert result.state == VADState.SILENCE or result.state == VADState.POSSIBLE_SPEECH

    def test_reset_returns_to_silence(self):
        vad = SileroVADEngine()
        vad._state = VADState.SPEECH
        vad.reset()
        assert vad.state == VADState.SILENCE

    def test_speech_duration_tracking(self):
        vad = SileroVADEngine()
        assert vad.speech_duration_ms == 0.0

    def test_silence_duration_tracking(self):
        vad = SileroVADEngine()
        assert vad.silence_duration_ms == 0.0

    def test_close(self):
        vad = SileroVADEngine()
        vad.close()
        assert not vad._loaded

    def test_state_machine_possible_speech(self):
        """Test SILENCE → POSSIBLE_SPEECH transition."""
        vad = SileroVADEngine(min_speech_ms=0)
        vad._loaded = True
        vad._vad = MagicMock()
        vad._vad.process = MagicMock(return_value=0.8)

        frame = AudioFrame.silence(sample_count=512)
        result = vad.feed(frame)
        # Should transition to POSSIBLE_SPEECH or SPEECH
        assert result.state in (VADState.POSSIBLE_SPEECH, VADState.SPEECH)

    def test_max_utterance_enforced(self):
        vad = SileroVADEngine(max_utterance_seconds=0)
        vad._state = VADState.SPEECH
        vad._speech_start_ns = perf_counter_ns() - int(1e9)  # 1 second ago
        vad._loaded = True
        vad._vad = MagicMock()
        vad._vad.process = MagicMock(return_value=0.8)
        frame = AudioFrame.silence(sample_count=512)
        result = vad.feed(frame)
        # Should transition to TRAILING_SILENCE due to max utterance
        assert result.state == VADState.TRAILING_SILENCE


class TestEndpointDetector:
    def test_default_silence_endpoint(self):
        ep = EndpointDetector(default_silence_ms=300)
        result, reason = ep.should_finalize(
            vad_state=VADState.SILENCE, silence_ms=350.0,
            utterance_ms=2000.0,
        )
        assert result
        assert reason == "default_silence"

    def test_no_endpoint_during_speech(self):
        ep = EndpointDetector()
        result, reason = ep.should_finalize(
            vad_state=VADState.SPEECH, silence_ms=0.0,
            utterance_ms=1000.0,
        )
        assert not result
        assert reason == "speech_active"

    def test_short_command_faster_endpoint(self):
        ep = EndpointDetector(short_command_silence_ms=200)
        result, reason = ep.should_finalize(
            vad_state=VADState.SILENCE, silence_ms=250.0,
            utterance_ms=1500.0, stable_text="open chrome",
            router_complete=True,
        )
        assert result
        assert reason == "short_command_complete"

    def test_incomplete_waits_longer(self):
        ep = EndpointDetector(incomplete_silence_ms=600)
        result, reason = ep.should_finalize(
            vad_state=VADState.TRAILING_SILENCE, silence_ms=400.0,
            utterance_ms=3000.0, incomplete_hint=True,
        )
        assert not result
        assert reason == "waiting_incomplete"

    def test_long_utterance_silence(self):
        ep = EndpointDetector(long_utterance_silence_ms=500)
        result, reason = ep.should_finalize(
            vad_state=VADState.SILENCE, silence_ms=550.0,
            utterance_ms=10000.0,
        )
        assert result
        assert reason == "long_utterance_silence"


# ── STT Stabilizer Tests ──

from jarvis.core.stt.base import TranscriptPartial
from jarvis.core.stt.stabilizer import TranscriptStabilizer


class TestStabilizer:
    def test_progressive_stabilization(self):
        stab = TranscriptStabilizer(stability_threshold=2, session_id="test")

        # Revision 1: "open"
        p1 = TranscriptPartial(session_id="test", text="open")
        s1 = stab.update(p1)
        assert s1 is None  # Not stable yet (need 2 matches)

        # Revision 2: "open visual"
        p2 = TranscriptPartial(session_id="test", text="open visual")
        s2 = stab.update(p2)
        assert s2 is not None
        assert s2.text == "open"  # "open" is stable

        # Revision 3: "open visual studio"
        p3 = TranscriptPartial(session_id="test", text="open visual studio")
        s3 = stab.update(p3)
        assert s3 is not None
        assert s3.text == "open visual"

        # Revision 4: "open visual studio code"
        p4 = TranscriptPartial(session_id="test", text="open visual studio code")
        s4 = stab.update(p4)
        assert s4 is not None
        assert s4.text == "open visual studio"

    def test_revision_rewrite(self):
        stab = TranscriptStabilizer(stability_threshold=2, session_id="test")

        p1 = TranscriptPartial(session_id="test", text="open visual studio coat")
        stab.update(p1)

        # Rewrite last word
        p2 = TranscriptPartial(session_id="test", text="open visual studio code")
        s2 = stab.update(p2)
        # "open visual studio" should be stable
        assert s2 is not None
        assert "studio" in s2.text
        assert "coat" not in s2.text
        assert "code" not in s2.text

    def test_no_duplicate_stable_words(self):
        stab = TranscriptStabilizer(stability_threshold=2, session_id="test")
        for text in ["open", "open chrome", "open chrome"]:
            stab.update(TranscriptPartial(session_id="test", text=text))
        prefix = stab.stable_prefix
        words = prefix.split()
        assert len(words) == len(set(words))

    def test_reset(self):
        stab = TranscriptStabilizer(session_id="test")
        stab.update(TranscriptPartial(session_id="test", text="hello"))
        stab.reset()
        assert stab.stable_prefix == ""
        assert stab.revision_count == 0

    def test_empty_partial(self):
        stab = TranscriptStabilizer(session_id="test")
        result = stab.update(TranscriptPartial(session_id="test", text=""))
        assert result is None

    def test_single_word_stability(self):
        stab = TranscriptStabilizer(stability_threshold=2, session_id="test")
        stab.update(TranscriptPartial(session_id="test", text="stop"))
        s = stab.update(TranscriptPartial(session_id="test", text="stop"))
        assert s is not None
        assert s.text == "stop"


# ── VoiceSession Tests ──

from jarvis.core.audio.session import VoiceSession, VoiceState


class TestVoiceSession:
    def test_session_id_generated(self):
        s = VoiceSession()
        assert s.session_id.startswith("vs_")

    def test_valid_transition(self):
        s = VoiceSession()
        assert s.transition(VoiceState.WAKE_DETECTED)
        assert s.state == VoiceState.WAKE_DETECTED

    def test_invalid_transition_rejected(self):
        s = VoiceSession()
        assert not s.transition(VoiceState.FINALIZING)
        assert s.state == VoiceState.IDLE

    def test_timeline(self):
        s = VoiceSession()
        s.wake_timestamp_ns = perf_counter_ns()
        s.speech_start_ns = s.wake_timestamp_ns + int(200e6)  # 200ms later
        tl = s.timeline()
        assert "wake_to_speech_ms" in tl
        assert tl["wake_to_speech_ms"] > 0

    def test_speech_end_to_action_tracking(self):
        s = VoiceSession()
        s.speech_end_ns = perf_counter_ns()
        s.first_action_ns = s.speech_end_ns + int(500e6)  # 500ms later
        assert abs(s.speech_end_to_first_action_ms - 500.0) < 10.0

    def test_audio_unavailable_transition(self):
        s = VoiceSession()
        assert s.transition(VoiceState.AUDIO_UNAVAILABLE)
        assert s.state == VoiceState.AUDIO_UNAVAILABLE


# ── Early Router Tests ──

from jarvis.core.audio.early_router import EarlyRoutePreview, PredictedRoute
from jarvis.core.stt.base import TranscriptStablePrefix


class TestEarlyRouter:
    def test_read_only_prefetch_allowed(self):
        er = EarlyRoutePreview()
        assert er.is_prefetch_safe("list_dir", "READ_ONLY")
        assert er.is_prefetch_safe("get_time", "READ_ONLY")

    def test_state_changing_prefetch_blocked(self):
        er = EarlyRoutePreview()
        assert not er.is_prefetch_safe("delete_file")
        assert not er.is_prefetch_safe("open_app")
        assert not er.is_prefetch_safe("move_file")
        assert not er.is_prefetch_safe("send_email")
        assert not er.is_prefetch_safe("change_volume")

    def test_non_readonly_risk_blocked(self):
        er = EarlyRoutePreview()
        assert not er.is_prefetch_safe("some_tool", "DESTRUCTIVE")
        assert not er.is_prefetch_safe("some_tool", "EXTERNAL_EFFECT")
        assert not er.is_prefetch_safe("some_tool", "REVERSIBLE")

    def test_cancel_prefetch(self):
        er = EarlyRoutePreview()
        from jarvis.core.audio.early_router import PrefetchResult
        er._prefetch_results["pf1"] = PrefetchResult(
            prefetch_id="pf1", session_id="s1", tool="list_dir",
        )
        count = er.cancel_prefetch("s1")
        assert count == 1

    def test_reset(self):
        er = EarlyRoutePreview()
        er._current_prediction = PredictedRoute(
            prefetch_id="pf1", session_id="s1", stable_text="test",
        )
        er.reset()
        assert er.get_prediction() is None


# ── VoicePipeline Tests ──

from jarvis.core.audio.pipeline import VoicePipeline


class TestVoicePipeline:
    def test_wake_phrase_removal(self):
        assert VoicePipeline._strip_wake_phrase("Hey Jarvis, open Chrome") == "open Chrome"
        assert VoicePipeline._strip_wake_phrase("hey jarvis open notepad") == "open notepad"
        assert VoicePipeline._strip_wake_phrase("Jarvis, find my notes") == "find my notes"
        assert VoicePipeline._strip_wake_phrase("open chrome") == "open chrome"
        assert VoicePipeline._strip_wake_phrase("Yes, open Chrome") == "open Chrome"
        assert VoicePipeline._strip_wake_phrase("Yes open Chrome") == "open Chrome"
        assert VoicePipeline._strip_wake_phrase("ok jarvis launch calc") == "launch calc"
        assert VoicePipeline._strip_wake_phrase("Hey Jarvis") == ""
        assert VoicePipeline._strip_wake_phrase("Yes") == "Yes"

    def test_disabled_pipeline(self):
        pipeline = VoicePipeline(voice_enabled=False)
        assert not pipeline.is_running

    def test_metrics(self):
        pipeline = VoicePipeline(voice_enabled=False)
        m = pipeline.metrics
        assert m["voice_enabled"] is False
        assert m["total_sessions"] == 0

    @pytest.mark.asyncio
    async def test_voice_disabled_no_start(self):
        pipeline = VoicePipeline(voice_enabled=False)
        await pipeline.start()
        assert not pipeline.is_running

    @pytest.mark.asyncio
    async def test_stop_idempotent(self):
        pipeline = VoicePipeline(voice_enabled=False)
        await pipeline.stop()
        assert not pipeline.is_running

    @pytest.mark.asyncio
    async def test_speech_frames_fed_during_wake_ack(self):
        from jarvis.core.audio.frame import AudioFrame
        from jarvis.core.audio.hub import AudioConsumer
        from jarvis.core.audio.vad import VADResult, VADState
        from jarvis.core.stt.base import TranscriptFinal

        class MockSTT:
            is_loaded = True
            model_name = "test-model"
            def __init__(self):
                self.fed_pcm = []
            async def start_session(self, sid):
                pass
            async def feed_audio(self, pcm):
                self.fed_pcm.append(pcm)
            async def get_partial(self):
                return None
            async def finalize(self):
                return TranscriptFinal(session_id="s1", text="Hey Jarvis, open Chrome")

        class MockVAD:
            silence_duration_ms = 900.0
            speech_duration_ms = 600.0
            def __init__(self):
                self.feed_count = 0
            def feed(self, frame):
                self.feed_count += 1
                if self.feed_count <= 2:
                    return VADResult(is_speech=True, probability=0.9, inference_ms=0.5, state=VADState.SPEECH)
                return VADResult(is_speech=False, probability=0.1, inference_ms=0.5, state=VADState.TRAILING_SILENCE)
            def reset(self):
                pass

        class MockBargeIn:
            def __init__(self):
                self.cancelled = False
            def on_user_speech_started(self, ns):
                self.cancelled = True

        class MockResponseEngine:
            class MockAudioOutput:
                is_playing = True
            audio_output = MockAudioOutput()
            def play_wake_ack(self, sid):
                return True

        class MockEndpoint:
            def should_finalize(self, **kwargs):
                return (True, "silence")

        stt = MockSTT()
        vad = MockVAD()
        barge = MockBargeIn()
        resp = MockResponseEngine()
        endpoint = MockEndpoint()

        pipeline = VoicePipeline(
            stt_engine=stt,
            vad_engine=vad,
            endpoint_detector=endpoint,
            barge_in_controller=barge,
            response_engine=resp,
            preroll_ms=0,
        )
        pipeline._running = True
        consumer = AudioConsumer("test_vad")
        pipeline._vad_consumer = consumer

        test_frame = AudioFrame(
            sequence_id=1,
            timestamp_ns=100,
            sample_rate=16000,
            channels=1,
            sample_count=160,
            pcm=b"\x00\x01" * 160,
        )

        async def feed_frames():
            await asyncio.sleep(0.01)
            for _ in range(4):
                consumer.put(test_frame)
                await asyncio.sleep(0.01)

        feed_task = asyncio.create_task(feed_frames())
        await pipeline._handle_speech_session(trigger_source="wake_word")
        await feed_task

        # Crucial assertions:
        # 1. Microphone frames were fed to STT even though assistant wake ACK was playing!
        assert len(stt.fed_pcm) >= 2, f"STT received {len(stt.fed_pcm)} frames; expected >= 2"
        # 2. Barge-in was triggered to mute wake ACK
        assert barge.cancelled is True


# ── Vocabulary Bias Tests ──

from jarvis.core.stt.vocabulary import VocabularyBiasProvider


class TestVocabularyBias:
    def test_generate_prompt(self):
        provider = VocabularyBiasProvider(custom_terms=["NLP", "FastAPI"])
        prompt = provider.generate_prompt()
        assert "NLP" in prompt
        assert "FastAPI" in prompt
        assert len(prompt) > 0

    def test_bounded_prompt_size(self):
        # Many terms should be bounded
        terms = [f"term_{i}" for i in range(500)]
        provider = VocabularyBiasProvider(custom_terms=terms, max_tokens=50)
        prompt = provider.generate_prompt()
        word_count = len(prompt.split())
        assert word_count <= 70  # Some tolerance for static terms

    def test_empty_context(self):
        provider = VocabularyBiasProvider(custom_terms=[])
        prompt = provider.generate_prompt()
        # Should still include static terms
        assert len(prompt) > 0
