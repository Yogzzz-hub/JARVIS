"""Natural voice: pauses don't cut you off, long requests fit, 'Hey Jarvis' gets a chime, the UI never sticks."""
from __future__ import annotations

import pytest

from jarvis.core.audio.vad import EndpointDetector, VADState


def _ends(ep, silence_ms, utterance_ms=2500.0, text="", router_complete=False):
    return ep.should_finalize(vad_state=VADState.TRAILING_SILENCE, silence_ms=silence_ms, utterance_ms=utterance_ms,
                              stable_text=text, router_complete=router_complete)[0]


def test_a_thinking_pause_does_not_end_the_turn():
    ep = EndpointDetector()
    # "send all the guys who are messaging me that ..." (pause while thinking)
    assert not _ends(ep, 500, text="send all the guys who are messaging me that")
    assert not _ends(ep, 1200, text="tell rahul that")
    assert _ends(ep, 1700, text="tell rahul that")
    # a finished sentence still ends promptly
    assert not _ends(ep, 400, text="I will be available in one hour")
    assert _ends(ep, 850, text="I will be available in one hour")


def test_short_complete_commands_stay_snappy():
    ep = EndpointDetector()
    assert _ends(ep, 460, utterance_ms=1200, text="open chrome", router_complete=True)


def test_pause_length_is_configurable():
    ep = EndpointDetector(default_silence_ms=1200)
    assert not _ends(ep, 1000, text="what is the weather")
    assert ep.incomplete_silence_ms == 2400


def test_long_requests_are_not_cut_at_ten_seconds():
    from jarvis.config import VoiceConfig
    from jarvis.core.audio.pipeline import VoicePipeline

    assert VoiceConfig().max_utterance_s >= 30
    assert VoicePipeline.__init__.__defaults__ is not None
    import inspect
    assert inspect.signature(VoicePipeline.__init__).parameters["max_utterance_s"].default >= 30


def test_better_speech_model_by_default_and_resolves_before_download():
    from jarvis.config import VoiceConfig
    from jarvis.core.stt.faster_whisper_engine import FasterWhisperEngine, resolve_whisper_model

    cfg = VoiceConfig()
    assert cfg.stt_model not in ("base", "tiny") and cfg.stt_device == "auto" and cfg.stt_beam_size >= 3
    assert resolve_whisper_model("models/whisper/small.en") == "small.en"
    eng = FasterWhisperEngine(model="small.en", beam_size=5)
    eng._device_actual = "cuda"
    assert eng._final_beam() == 5
    eng._device_actual = "cpu"
    assert eng._final_beam() == 3


class _Out:
    def __init__(self):
        self.played = []

    def play(self, response):
        self.played.append(response)
        return True


def _engine(mode):
    from jarvis.core.response.engine import ResponseEngine

    eng = ResponseEngine(audio_output=_Out())
    eng.wake_ack_mode = mode
    return eng


def test_wake_word_gets_a_chime_not_a_canned_yes():
    eng = _engine("chime")
    res = eng.play_wake_ack("s1")
    assert res is not None and res.text == "(chime)" and len(res.audio_bytes) > 2000
    assert "Yes" not in res.text


def test_wake_ack_can_be_silent():
    eng = _engine("none")
    assert eng.play_wake_ack("s1") is None and not eng.audio_output.played


def test_spoken_wake_ack_rotates_and_avoids_yes():
    eng = _engine("voice")
    for phrase in ("Yes?", "I'm listening.", "Go ahead.", "Ready."):
        eng.ack_cache.add_phrase(phrase, b"\x00\x00" * 2000)
    said = [eng.play_wake_ack(f"s{i}").text for i in range(6)]
    assert "Yes?" not in said
    assert all(a != b for a, b in zip(said, said[1:])), said


def test_wake_only_does_not_fake_a_transcript():
    import inspect
    from jarvis.core.audio.pipeline import VoicePipeline

    src = inspect.getsource(VoicePipeline._handle_speech_session)
    assert 'text="Hey Jarvis"' not in src


def test_ui_recovers_when_stuck_listening(tmp_path):
    pytest.importorskip("PySide6.QtCore")
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication
    QGuiApplication.instance() or QGuiApplication([])

    from jarvis.tests.test_desktop_ui import FakeBridge, FakeMetrics
    from jarvis.ui.controller import JarvisUIController
    from jarvis.ui.models import ActivityListModel
    from jarvis.ui.settings import UISettings
    from jarvis.ui.state import JarvisUIState

    state = JarvisUIState()
    bridge = FakeBridge()
    ctl = JarvisUIController(state=state, bridge=bridge, settings=UISettings(tmp_path / "ui.json"),
                             activity_model=ActivityListModel(), metrics=FakeMetrics())
    ctl.startPTT()
    assert state.isListening
    assert not ctl._check_stuck(now=ctl._last_activity + 5)
    assert ctl._check_stuck(now=ctl._last_activity + 25)
    assert state.assistantState == "IDLE" and bridge.sent[-1] == "ptt_stop"


@pytest.mark.parametrize("heard,expected", [
    ("PageRWIS, now I am going to attend the meeting", "now I am going to attend the meeting"),
    ("Jervis open chrome", "open chrome"),
    ("Hey Javis, what's the time", "what's the time"),
    ("hey jarvis tell mom I'm late", "tell mom I'm late"),
    ("Travis Scott songs on youtube", "Travis Scott songs on youtube"),
    ("open chrome", "open chrome"),
])
def test_misheard_wake_word_is_removed_from_the_command(heard, expected):
    from jarvis.core.audio.pipeline import VoicePipeline
    assert VoicePipeline._strip_wake_phrase(heard) == expected
