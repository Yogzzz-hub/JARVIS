"""Speech recognition quality: noise hallucinations dropped, real commands kept; app matching never guesses
helper executables or bare verbs."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import numpy as np
import pytest

from jarvis.core.stt.quality import clean_transcript, join_segments, prepare_audio, repetition_loop, segment_ok


@pytest.mark.parametrize("text", [
    "Akash Anna, Akash Anna, Akash Anna, Akash Anna, Akash Anna, Akash Anna.", "Also, we...", "Thank you for watching.",
    "you", "[BLANK_AUDIO]", "set it set it set it set it",
])
def test_noise_hallucinations_are_dropped(text):
    assert clean_transcript(text) == ""


@pytest.mark.parametrize("text", ["open chrome", "no no no", "turn it up up", "Open the engine.",
                                  "send a message to akash anna saying I'm on the way", "what's the weather in Chennai"])
def test_real_commands_are_kept(text):
    assert clean_transcript(text) == text.rstrip()


def test_too_many_words_for_the_voiced_audio_is_rejected():
    assert clean_transcript("open chrome and play some music now", speech_ms=300) == ""
    assert clean_transcript("open chrome and play some music now", speech_ms=2500) != ""


def test_low_confidence_segments_are_dropped():
    good = SimpleNamespace(text=" open chrome", no_speech_prob=0.02, avg_logprob=-0.2, compression_ratio=1.2, start=0, end=1)
    noise = SimpleNamespace(text=" Also, we", no_speech_prob=0.8, avg_logprob=-1.0, compression_ratio=1.1, start=1, end=2)
    loop = SimpleNamespace(text=" Akash Anna, Akash Anna", no_speech_prob=0.1, avg_logprob=-0.4, compression_ratio=3.1, start=2, end=3)
    guess = SimpleNamespace(text=" mumble", no_speech_prob=0.2, avg_logprob=-1.4, compression_ratio=1.0, start=3, end=4)
    assert segment_ok(good) and not segment_ok(noise) and not segment_ok(loop) and not segment_ok(guess)
    text, info = join_segments([good, noise, loop, guess])
    assert text == "open chrome" and [i["kept"] for i in info] == [True, False, False, False]
    assert repetition_loop("akash anna akash anna akash anna")


def test_audio_preparation_removes_rumble_and_normalises():
    t = np.arange(16000) / 16000.0
    rumble = 0.5 * np.sin(2 * np.pi * 30 * t)
    voice = 0.05 * np.sin(2 * np.pi * 440 * t)
    out = prepare_audio((rumble + voice).astype(np.float32))
    spec = np.abs(np.fft.rfft(out))
    assert spec[30] < spec[440] / 4  # rumble removed
    assert 0.15 < np.max(np.abs(out)) <= 0.71  # quiet speech boosted (at most 4x, so noise is not blown up)


def test_engine_auto_model_choice_and_final_pass_uses_vad(monkeypatch):
    from jarvis.core.stt import faster_whisper_engine as fw
    calls = {}

    class FakeModel:
        def __init__(self, name, device, compute_type, **kw):
            if device == "cuda":
                raise RuntimeError("no GPU here")
            calls["model"] = name

        def transcribe(self, audio, **kw):
            calls["kw"] = kw
            segs = [SimpleNamespace(text=" Akash Anna, Akash Anna, Akash Anna", no_speech_prob=0.7, avg_logprob=-1.2,
                                    compression_ratio=2.8, start=0, end=2)]
            return iter(segs), SimpleNamespace(language="en", duration_after_vad=0.4)

    import sys
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=FakeModel))
    eng = fw.FasterWhisperEngine(model="auto", device="auto", beam_size=5)

    async def run():
        await eng.load()
        await eng.start_session("s")
        await eng.feed_audio((np.random.randn(16000) * 1000).astype(np.int16).tobytes())
        return await eng.finalize()
    final = asyncio.run(run())
    assert calls["model"] == "small.en" and eng.model_name == "small.en"  # CPU -> small.en (GPU -> large-v3-turbo)
    assert calls["kw"]["vad_filter"] is True and calls["kw"]["no_speech_threshold"] == 0.6
    assert final.text == ""  # the noise loop never reaches the command router


@pytest.mark.parametrize("query,candidate,ok", [
    ("engine", "mlenginestub.exe", False), ("engine", "resetengine", False), ("open", "opencode", False),
    ("chrome", "chrome.exe", True), ("spot", "spotify", True), ("code", "visual studio code", True),
])
def test_app_matching_is_plausible_only(query, candidate, ok):
    from jarvis.core.router.disambiguation import plausible_app_match
    assert plausible_app_match(query, candidate) is ok


def test_bare_verb_asks_what_to_open():
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter
    d = asyncio.run(SmartRouter(llm_provider=DisabledProvider()).route("open"))
    assert d.lane.value == "CLARIFY" and d.clarification == "What should I open?"
