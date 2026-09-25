"""Regression tests for wake / voice / talkback reliability fixes."""
from __future__ import annotations

import asyncio
from pathlib import Path

import numpy as np
import pytest

from jarvis.core.audio.frame import AudioFrame
from jarvis.core.audio.source import MicSource, StreamingResampler


def _frame(samples: np.ndarray, seq: int = 1) -> AudioFrame:
    pcm = samples.astype(np.int16).tobytes()
    return AudioFrame(sequence_id=seq, timestamp_ns=seq * 20_000_000, sample_rate=16000, channels=1,
                      sample_count=len(samples), pcm=pcm)


# ---------------------------------------------------------------- resampling
@pytest.mark.parametrize("rate,block", [(48000, 960), (44100, 882), (22050, 441)])
def test_streaming_resampler_matches_whole_signal(rate, block):
    from scipy.signal import resample_poly

    t = np.arange(rate) / rate
    sig = (8000 * np.sin(2 * np.pi * 440 * t)).astype(np.int16)
    r = StreamingResampler(rate, 16000)
    out = b"".join(r.process(sig[i:i + block].tobytes()) for i in range(0, len(sig), block))
    y = np.frombuffer(out, dtype=np.int16).astype(float)
    ref = np.round(resample_poly(sig.astype(float), r.up, r.down))
    lag = r.pad * r.up // r.down
    assert np.max(np.abs(y[lag:] - ref[: len(y) - lag])) <= 1.0
    # The old per-block approach distorts badly at block edges.
    naive = b"".join(MicSource._resample_pcm16(sig[i:i + block].tobytes(), rate, 16000) for i in range(0, len(sig), block))
    yn = np.frombuffer(naive, dtype=np.int16).astype(float)
    assert np.max(np.abs(yn[: len(ref)] - ref[: len(yn)])) > 500


# ---------------------------------------------------------------- VAD fallback
def test_energy_vad_fallback_detects_speech_without_silero():
    from jarvis.core.audio.vad import SileroVADEngine, VADState

    vad = SileroVADEngine(min_speech_ms=40)
    vad._load_failed = True  # simulate silero-vad-lite missing
    rng = np.random.default_rng(0)
    states = []
    for i in range(30):
        noise = rng.normal(0, 30, 320)
        states.append(vad.feed(_frame(noise, i)).state)
    assert VADState.SPEECH not in states, "background noise must not count as speech"
    for i in range(30, 50):
        voice = 6000 * np.sin(2 * np.pi * 220 * np.arange(320) / 16000) + rng.normal(0, 30, 320)
        states.append(vad.feed(_frame(voice, i)).state)
    assert VADState.SPEECH in states[30:]
    assert vad.uses_energy_fallback


# ---------------------------------------------------------------- STT
def test_whisper_directory_without_weights_falls_back_to_model_size(tmp_path):
    from jarvis.core.stt.faster_whisper_engine import resolve_whisper_model

    empty = tmp_path / "base"
    empty.mkdir()
    (empty / "config.json").write_text("{}")
    assert resolve_whisper_model(str(empty)) == "base"
    (empty / "model.bin").write_bytes(b"x")
    assert resolve_whisper_model(str(empty)) == str(empty)
    assert resolve_whisper_model("small.en") == "small.en"


@pytest.mark.asyncio
async def test_final_transcript_keeps_whole_long_utterance_and_rejects_stale_partial():
    from jarvis.core.stt.faster_whisper_engine import FasterWhisperEngine

    seen = []

    class FakeModel:
        def transcribe(self, audio, **kwargs):
            seen.append(len(audio))

            class Seg:
                text = f"{len(audio)} samples"
                start, end = 0.0, 1.0

            class Info:
                language = "en"
            return iter([Seg()]), Info()

    eng = FasterWhisperEngine(model="base", device="cpu")
    eng._model, eng._loaded = FakeModel(), True
    await eng.start_session("s")
    for _ in range(400):  # 8 seconds of audio in 20 ms frames
        await eng.feed_audio(b"\x01\x00" * 320)
    partial = await eng.get_partial()
    assert partial is not None
    assert seen[-1] == int(eng.context_window_s * 16000), "partials use the sliding window"
    for _ in range(40):  # 0.8 s more speech after the partial
        await eng.feed_audio(b"\x01\x00" * 320)
    final = await eng.finalize()
    assert seen[-1] == 8.8 * 16000, "final pass must see the whole utterance, not the last 6 s"
    assert final.text == f"{int(8.8 * 16000)} samples"


# ---------------------------------------------------------------- wake word
class _FakeWake:
    threshold = 0.5

    def __init__(self, score):
        self.score = score
        self.fed = []

    def feed(self, frame):
        from jarvis.core.audio.wake import WakeDetection
        self.fed.append(frame.sample_count)
        return WakeDetection(detected=self.score >= self.threshold, score=self.score, model="m", timestamp_ns=1)

    def reset(self):
        pass

    def close(self):
        pass


class _Output:
    def __init__(self, playing):
        self.is_playing = playing
        self.queue = []
        self.last_playback_stop_ns = 0


class _Response:
    def __init__(self, playing=False):
        self.audio_output = _Output(playing)
        self.active_followup_window = False
        self.stopped = 0

    def stop_speaking(self):
        self.stopped += 1
        self.audio_output.is_playing = False

    def close_followup_window(self):
        self.active_followup_window = False


def _pipeline(wake, response):
    from jarvis.core.audio.hub import AudioConsumer
    from jarvis.core.audio.pipeline import VoicePipeline

    p = VoicePipeline(wake_engine=wake, response_engine=response, ptt_enabled=False)
    p._running = True
    p._wake_consumer = AudioConsumer("wake", queue_size=100)
    p._vad_consumer = AudioConsumer("vad", queue_size=100)
    return p


@pytest.mark.asyncio
async def test_wake_backlog_is_batched_into_one_inference_call():
    wake = _FakeWake(0.9)
    p = _pipeline(wake, _Response())
    for i in range(10):
        p._wake_consumer.put(_frame(np.zeros(320), i))
    trigger = await asyncio.wait_for(p._wait_for_trigger(), 1.0)
    assert trigger == ("wake_word", None)
    assert wake.fed == [3200], "ten queued frames -> a single batched feed"


@pytest.mark.asyncio
async def test_wake_while_speaking_needs_higher_confidence_then_barges_in():
    response = _Response(playing=True)
    weak = _FakeWake(0.6)  # above normal threshold, below barge-in threshold
    p = _pipeline(weak, response)
    p._wake_consumer.put(_frame(np.zeros(1280)))
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(p._wait_for_trigger(), 0.4)
    assert response.stopped == 0

    strong = _FakeWake(0.9)
    p = _pipeline(strong, response)
    p._wake_consumer.put(_frame(np.zeros(1280)))
    assert await asyncio.wait_for(p._wait_for_trigger(), 1.0) == ("wake_word", None)
    assert response.stopped == 1, "a confident wake word interrupts JARVIS's speech"


@pytest.mark.asyncio
async def test_followup_window_ignores_jarvis_own_voice():
    from jarvis.core.audio.vad import VADResult, VADState

    class SpeechVAD:
        def feed(self, frame):
            return VADResult(is_speech=True, probability=0.9, inference_ms=0.1, state=VADState.SPEECH)

        def reset(self):
            pass

    response = _Response(playing=True)
    response.active_followup_window = True
    p = _pipeline(_FakeWake(0.0), response)
    p.vad = SpeechVAD()
    for i in range(5):
        p._vad_consumer.put(_frame(np.zeros(320), i))
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(p._wait_for_trigger(), 0.3)
    response.audio_output.is_playing = False
    trigger = asyncio.create_task(p._wait_for_trigger())
    await asyncio.sleep(0.15)  # echo frames from the playback period are discarded...
    from time import perf_counter_ns
    after = _frame(np.zeros(320), 9)
    after.timestamp_ns = perf_counter_ns()  # ...speech captured after JARVIS stopped counts
    p._vad_consumer.put(after)
    source, _ = await asyncio.wait_for(trigger, 1.0)
    assert source == "followup"


def test_wake_engine_falls_back_to_builtin_model_name(monkeypatch, tmp_path):
    import sys
    import types

    from jarvis.core.audio.wake import OpenWakeWordEngine

    created = []

    class FakeModel:
        def __init__(self, **kwargs):
            created.append(kwargs["wakeword_models"])
            if kwargs["wakeword_models"] != ["hey_jarvis"]:
                raise RuntimeError("bad model file")
            self.models = {"hey_jarvis": object()}

    module = types.ModuleType("openwakeword.model")
    module.Model = FakeModel
    utils = types.ModuleType("openwakeword.utils")
    utils.download_models = lambda **kw: None
    monkeypatch.setitem(sys.modules, "openwakeword", types.ModuleType("openwakeword"))
    monkeypatch.setitem(sys.modules, "openwakeword.model", module)
    monkeypatch.setitem(sys.modules, "openwakeword.utils", utils)

    broken = tmp_path / "hey_jarvis_v0.1.onnx"
    broken.write_bytes(b"not onnx")
    eng = OpenWakeWordEngine(model_path=str(broken))
    eng._ensure_loaded()
    assert eng._loaded and eng._model_name == "hey_jarvis"
    assert created == [[str(broken)], ["hey_jarvis"]]


# ---------------------------------------------------------------- talkback
@pytest.mark.asyncio
async def test_stop_speaking_invalidates_in_flight_synthesis():
    from jarvis.core.response.engine import ResponseEngine

    class Out:
        def __init__(self):
            self.cancelled = 0
            self.played = []
            self.is_playing = False
            self.queue = []

        def cancel_all(self):
            self.cancelled += 1

        def play(self, r):
            self.played.append(r)
            return True

    engine = ResponseEngine(audio_output=Out())
    gen = engine._speech_generation
    engine.stop_speaking()
    assert engine._speech_generation == gen + 1
    assert engine.audio_output.cancelled == 1


@pytest.mark.asyncio
async def test_followup_window_counts_silence_after_speech():
    from jarvis.core.response.engine import ResponseEngine

    out = _Output(playing=True)
    engine = ResponseEngine(audio_output=out)
    engine.open_followup_window("r", duration_seconds=0.2)
    await asyncio.sleep(0.4)
    assert engine.active_followup_window, "window must not expire while JARVIS is still talking"
    out.is_playing = False
    await asyncio.sleep(0.45)
    assert not engine.active_followup_window


def test_pulse_splits_long_answers_into_sentence_chunks():
    from jarvis.core.pulse.engine import PulseEngine

    text = "First sentence here. " + "Second one is a bit longer and keeps going, with a clause, and another clause. " * 4 + "Done!"
    chunks = PulseEngine.split_for_speech(text, max_chars=120)
    assert all(len(c) <= 120 for c in chunks)
    assert " ".join(chunks).split() == text.split()
    assert len(chunks) > 3


@pytest.mark.asyncio
async def test_pulse_stays_silent_for_whatsapp_and_offloads_blocking_tts():
    from jarvis.core.pulse.engine import PulseEngine

    played = []

    class Out:
        def play(self, r):
            played.append(r.text)
            return True

    class BlockingTTS:
        blocking = True
        sample_rate = 22050

        def synthesize(self, text):
            return b"\x00" * 4410, "fake"

    pulse = PulseEngine(audio_output=Out(), tts_manager=BlockingTTS())
    pulse.start_interaction("wa1", "open_app", 900.0, source="whatsapp", slots={"name": "chrome"})
    assert not [t for t in played if not t.startswith("earcon")]

    pulse._dispatch_micro_ack("r2", "Opening Chrome.")
    assert "Opening Chrome." not in played, "real TTS must not synthesize on the event loop"
    await asyncio.sleep(0.1)
    assert "Opening Chrome." in played
    played.clear()
    pulse._dispatch_micro_ack("r3", "Opening Chrome.")
    assert "Opening Chrome." in played, "repeat acks come from the in-memory cache instantly"
