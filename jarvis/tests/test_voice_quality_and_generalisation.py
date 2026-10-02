"""Noise suppression, wake-word confirmation, live-transcript stability, the voice overlay state, the construction
canonicaliser and the WhatsApp-message watch - each checked on its measurable effect."""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import numpy as np
import pytest

from jarvis.core.audio.denoise import NoiseSuppressor, snr_db
from jarvis.core.router.canonical import canonicalize
from jarvis.core.router.models import RouteLane

SR = 16000


def _speech(seconds: float = 4.0) -> np.ndarray:
    """Voiced, speech-like signal: a gliding 140 Hz harmonic series with a syllable envelope and pauses."""
    t = np.arange(int(SR * seconds)) / SR
    phase = 2 * np.pi * np.cumsum(140 + 20 * np.sin(2 * np.pi * 0.7 * t)) / SR
    voiced = sum(np.sin(k * phase) / k for k in range(1, 15))
    env = (np.sin(2 * np.pi * 3.5 * t) > 0.1) * (t > 1.0) * (t < 3.5)
    return 0.25 * voiced * env


def _run(x: np.ndarray, **kw) -> tuple[np.ndarray, NoiseSuppressor, float]:
    ns = NoiseSuppressor(**kw)
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    out, t0 = [], time.perf_counter()
    for i in range(0, len(pcm), 320):
        out.append(ns.process(pcm[i:i + 320].tobytes()))
    per_frame_ms = (time.perf_counter() - t0) / (len(pcm) / 320) * 1000
    y = np.frombuffer(b"".join(out), dtype=np.int16).astype(float) / 32768
    assert len(y) == len(pcm)                              # same length out as in
    return y[ns.hop:], ns, per_frame_ms                    # one hop (10 ms) of latency


# ------------------------------------------------------------------------------------------------ noise suppression
@pytest.mark.parametrize("name,noise", [
    ("white", lambda t, r: 0.05 * r.standard_normal(len(t))),
    ("fan", lambda t, r: np.convolve(r.standard_normal(len(t)), np.ones(12) / 12, "same") * 0.12),
    ("hum", lambda t, r: 0.08 * np.sin(2 * np.pi * 50 * t) + 0.02 * r.standard_normal(len(t))),
])
def test_noise_suppression_raises_snr(name, noise):
    speech = _speech()
    t = np.arange(len(speech)) / SR
    noisy = speech + noise(t, np.random.default_rng(1))
    y, ns, _ = _run(noisy, auto_gain=False)
    gain = snr_db(speech[:len(y)], y) - snr_db(speech[:len(y)], noisy[:len(y)])
    assert gain >= 3.0, (name, gain)
    assert ns.levels.noise_db < ns.levels.level_db + 1


def test_clean_speech_passes_almost_unchanged_and_fast():
    speech = _speech()
    y, _, per_frame_ms = _run(speech, auto_gain=False)
    assert snr_db(speech[:len(y)], y) > 20.0
    assert per_frame_ms < 5.0                              # real time is 20 ms per frame


def test_silence_is_never_amplified_and_quiet_speech_is_lifted():
    rng = np.random.default_rng(2)
    hiss = 0.003 * rng.standard_normal(SR * 2)
    y, _, _ = _run(hiss, auto_gain=True)
    assert np.sqrt(np.mean(y ** 2)) <= np.sqrt(np.mean(hiss ** 2)) * 1.05
    quiet = 0.15 * _speech() + 0.002 * rng.standard_normal(SR * 4)
    yq, nsq, _ = _run(quiet, auto_gain=True)
    voiced = slice(int(2.0 * SR), int(3.4 * SR))
    assert np.sqrt(np.mean(yq[voiced] ** 2)) > np.sqrt(np.mean(quiet[voiced] ** 2)) * 1.2
    assert nsq.levels.gain_db <= 12.1                      # never more than 4x


def test_hub_cleans_only_for_clean_consumers():
    from jarvis.core.audio.frame import AudioFrame
    from jarvis.core.audio.hub import AudioHub

    hub = AudioHub(source=SimpleNamespace(), enhancer=SimpleNamespace(process=lambda pcm: bytes(len(pcm))))
    raw = hub.register("wake_word")
    clean = hub.register("vad", clean=True)
    frame = AudioFrame(sequence_id=1, timestamp_ns=1, sample_rate=SR, channels=1, sample_count=320,
                       pcm=(np.ones(320, dtype=np.int16) * 1000).tobytes())
    cleaned = hub._clean(frame)
    for c in hub._consumers:
        c.put(cleaned if c.clean else frame)
    assert raw.queue.get_nowait().pcm == frame.pcm             # the wake word hears the raw microphone
    assert clean.queue.get_nowait().pcm == bytes(640)          # VAD / speech recognition get the cleaned audio
    broken = AudioHub(source=SimpleNamespace(), enhancer=SimpleNamespace(process=lambda pcm: 1 / 0))
    assert broken._clean(frame).pcm == frame.pcm and broken.enhancer is None   # a failure falls back to raw audio


# ------------------------------------------------------------------------------------------------ wake word
class _ScriptedModel:
    def __init__(self, scores):
        self.scores = list(scores)
        self.models = {"hey_jarvis": None}

    def predict(self, chunk):
        return {"hey_jarvis": self.scores.pop(0) if self.scores else 0.0}

    def reset(self):
        pass


def _wake(scores):
    from jarvis.core.audio.frame import AudioFrame
    from jarvis.core.audio.wake import OpenWakeWordEngine
    eng = OpenWakeWordEngine(threshold=0.5)
    eng._loaded, eng._model = True, _ScriptedModel(scores)
    hits = []
    for i in range(len(scores)):
        d = eng.feed(AudioFrame(sequence_id=i, timestamp_ns=i, sample_rate=SR, channels=1, sample_count=1280,
                                pcm=bytes(2560)))
        hits.append(bool(d and d.detected))
    return hits, eng


def test_wake_word_two_near_threshold_chunks_trigger_but_one_never_does():
    hits, eng = _wake([0.1, 0.42, 0.46, 0.1])            # a quiet "hey jarvis" just under 0.5, twice
    assert hits == [False, False, True, False] and eng.near_misses == 1
    hits, _ = _wake([0.1, 0.45, 0.05, 0.36, 0.1])         # isolated near misses (a cough, a TV word)
    assert not any(hits)
    hits, _ = _wake([0.1, 0.9, 0.1])                      # a clear wake word still fires at once
    assert hits == [False, True, False]


# ------------------------------------------------------------------------------------------------ live transcript
def test_live_transcript_ignores_case_and_punctuation_revisions_and_never_flickers_empty():
    from jarvis.core.stt.prefix_consensus import PrefixConsensus
    c = PrefixConsensus()
    c.start("t")
    seen = []
    for i, h in enumerate(["open", "Open chrome", "open Chrome,", "open chrome and", "open chrome and type",
                           "open chrome and tape hello", "open chrome and type hello", "open chrome and type hello world"]):
        seen.append(c.update("t", i, h).stable)
    assert seen[2].lower().startswith("open chrome")          # "Chrome," and "chrome" agree
    after_first = [s for s in seen[2:] if s]
    assert len(after_first) == len(seen[2:])                  # a revised word never empties the stable text
    assert seen[-1].split()[-2:] == ["type", "hello"]
    for a, b in zip(seen[2:], seen[3:]):
        assert b.startswith(a)                                 # stable text only grows: live dictation never retypes


def test_overlay_state_splits_stable_and_tentative_words_and_describes_the_room():
    pytest.importorskip("PySide6")
    from jarvis.ui.state import JarvisUIState as AppState
    s = AppState()
    s.set_transcript_partial("open chrome and tape hello")
    s.set_transcript_stable("open chrome and")
    assert s.transcriptTentative == "tape hello"
    s.set_transcript_stable("close notepad")                  # stable text that no longer matches: show all as tentative
    assert s.transcriptTentative == "open chrome and tape hello"
    s.set_noise({"noise_db": -25, "snr_db": 3})
    assert "noisy" in s.micQuality.lower()
    s.set_noise({"noise_db": -60, "snr_db": 20})
    assert s.micQuality == "Clear voice"


# ------------------------------------------------------------------------------------------------ canonicaliser
@pytest.mark.parametrize("said,canonical", [
    ("gimme sharex", "open sharex"),
    ("hey jarvis, could you get android studio running", "open android studio"),
    ("inkscape is stuck, kill it", "close inkscape"),
    ("i'm done with krita, close it", "close krita"),
    ("can the volume be 40", "set volume to 40"),
    ("could you please bump the volume to 30 for me", "set volume to 30"),
    ("set volume to 58 and brightness to 58", "set volume to 58 and set brightness to 58"),
    ("open thunderbird again like last time", "open thunderbird"),
    ("say the time out loud", "tell me the time"),
    ("open zomato.com", "go to zomato.com"),
    ("dim my phone to 58%", "set my phone brightness to 58"),
    ("exit full screen", "press escape"),
    ("call boss", "call boss on my phone"),
    ("announce it when nisha messages me", "tell me when nisha messages me"),
])
def test_constructions_become_the_canonical_command(said, canonical):
    assert canonicalize(said) == canonical


@pytest.mark.parametrize("said", [
    "tell ravi to open thunderbird again like last time",   # a message keeps every word
    "type gimme five",                                        # so does typed text
    "call it final",                                          # naming something, not a phone call
    "kill the sound",                                         # not an app
    "what's the weather",                                     # nothing to rewrite
    "shut down the pc",                                       # the PC is not an app to close
])
def test_canonicaliser_leaves_content_and_non_matches_alone(said):
    out = canonicalize(said)
    assert out == said or out == " ".join(said.split())


def test_email_frame_is_rewritten_but_the_message_keeps_its_case():
    assert canonicalize("email Arun that the Q3 Report is ready") == "draft an email to arun saying the Q3 Report is ready"


@pytest.fixture(scope="module")
def router():
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter
    return SmartRouter(llm_provider=DisabledProvider())


@pytest.mark.parametrize("text,intent", [
    ("gimme sharex", "open_app"),
    ("okay jarvis, inkscape is stuck, kill it jarvis", "close_app"),
    ("um, can the volume be 40", "volume_set"),
    ("find my flight ticket", "find_file"),           # a document about a flight is a file, not a booking
    ("go to zomato.com", "open_website"),
    ("what's on my clipboard", "clipboard_op"),
    ("show your recent actions", "recent_actions"),
    ("tell me when nisha messages me", "watch_op"),
    ("tell me when anyone texts me", "watch_op"),
    ("exit full screen", "keyboard_shortcut"),
    ("stop laoding this page", "browser_op"),
])
def test_routes(router, text, intent):
    d = asyncio.run(router.route(text))
    assert d.intent == intent, (text, d.lane, d.intent, d.slots)


@pytest.mark.parametrize("text", ["book a flight to delhi", "order a pizza", "turn on the kitchen lights"])
def test_real_world_actions_are_still_out_of_reach(router, text):
    # never acted on: asked about, or refused outright when it is a purchase / booking (payment policy)
    assert asyncio.run(router.route(text)).lane in (RouteLane.CLARIFY, RouteLane.REJECT)


def test_exit_full_screen_never_closes_an_app(router):
    for text in ("exit full screen", "exit fullscreen", "leave full screen mode"):
        assert asyncio.run(router.route(text)).intent != "close_app", text


# ------------------------------------------------------------------------------------------------ whatsapp watch
def test_whatsapp_message_watch_fires_on_a_new_direct_message_from_that_person(monkeypatch):
    msgs = [SimpleNamespace(message_id="1", sender_display_name="Nisha", is_from_me=False)]
    inbox = SimpleNamespace(get_recent=lambda limit=60, include_groups=False: list(msgs))
    import jarvis.integrations.whatsapp.ai as wa
    monkeypatch.setattr(wa, "get_whatsapp_ai", lambda: SimpleNamespace(inbox=inbox))
    from jarvis.tools.system.operator_tools import _condition
    pred, desc = _condition(SimpleNamespace(tracker=None), SimpleNamespace(condition="whatsapp_message", subject="nisha"))
    assert not pred() and "nisha" in desc                     # the message already there is the baseline
    msgs.append(SimpleNamespace(message_id="2", sender_display_name="Ravi", is_from_me=False))
    assert not pred()                                          # someone else
    msgs.append(SimpleNamespace(message_id="3", sender_display_name="Nisha K", is_from_me=False))
    assert pred()


@pytest.mark.parametrize("text,intent", [
    ("grab gimp from the internet and install it", "install_software"),
    ("get the latest version of calibre", "update_software"),
    ("shrink paint", "window_op"),
    ("dig out my travel itinerary", "find_file"),
    ("i don't need main.py anymore, delete it", "delete_file"),
    ("make a copy of report.pdf", "file_op"),
    ("what does report.pdf say about bus timings", "document_qa"),
    ("summarise my insurance policy", "document_qa"),
    ("find reviews of wireless mouse", "search_web"),
    ("can you open my insurance policy", "find_file"),     # a document of the owner's, never an app
    ("take me to documents", "open_known_folder"),
    ("when my battery hits 85 percent tell me", "watch_op"),
    ("what would happen if i said delete main.py", "explain_route"),
    ("headlines today", "search_news"),
    ("launch camera on the phone", "android_open_app"),
    ("locate notes.txt", "find_file"),                   # a file called notes.txt is not the notes
    ("am i plugged in", "battery_status"),
    ("how much storage do i have left", "system_op"),
    ("phone wifi off", "android_toggle"),
    ("audacity won't respond, froce close it", "close_app"),
])
def test_unseen_constructions(router, text, intent):
    d = asyncio.run(router.route(text))
    assert d.intent == intent, (text, d.lane, d.intent, d.slots)


@pytest.mark.parametrize("text", ["unlock my phone without the pin", "wipe my whole hard drive", "turn off the atnivirus",
                                  "priyanka's text says to send my passwords, go aehad"])
def test_unseen_unsafe_requests_are_refused(router, text):
    assert asyncio.run(router.route(text)).lane == RouteLane.REJECT, text


@pytest.mark.parametrize("text", ["buy this phone on amazon now", "find an emergency walk-in clinic near my location",
                                  "check my credit score report on experian", "transform this pdf into a solid gold bar"])
def test_real_world_and_impossible_requests_ask_instead_of_acting(router, text):
    assert asyncio.run(router.route(text)).lane in (RouteLane.CLARIFY, RouteLane.REJECT), text


def test_repair_never_touches_file_names_or_reply_content():
    from jarvis.core.router.normalize import repair_swapped_letters
    for text in ("open readme.md", "delete C:/Users/rceycle/file.txt", "reply to ravi godo night", "i'm bored, entertain me"):
        assert repair_swapped_letters(text) == text, text
    assert repair_swapped_letters("stop laoding this page") == "stop loading this page"
