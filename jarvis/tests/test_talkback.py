"""Talkback: every sentence of an answer is spoken, the owner can talk over JARVIS, and voice commands are understood
by meaning ("stop", "wait", "continue", "say that again", "slower", "louder")."""
from __future__ import annotations

import asyncio
import time

import pytest

from jarvis.core.audio.output.player import AudioOutputManager
from jarvis.core.response.models import DeliveryStatus, ResponsePriority, ResponseType, SpokenResponse

SENTENCES = [f"This is sentence number {i} of a long answer." for i in range(1, 9)]


class FakeTTS:
    blocking = False
    sample_rate = 16000

    def synthesize(self, text):
        return b"\x10\x00" * 160, "fake"  # 10 ms of audio per sentence


def _player():
    out = AudioOutputManager(mock_output=True, sample_rate=16000)
    out.start()
    return out


def _wait(predicate, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        time.sleep(0.01)
    return False


# ------------------------------------------------------------------------------------------------ speak fully
@pytest.mark.asyncio
async def test_a_streamed_answer_is_spoken_to_the_last_sentence():
    from jarvis.core.pulse.engine import PulseEngine
    out = _player()
    played = []
    out.event_callback = lambda name, rid, data: played.append(data["text"]) if name == "tts.stopped" and data["text"] else None
    pulse = PulseEngine(audio_output=out, tts_manager=FakeTTS())
    stream = pulse.open_speech_stream("long-1")
    for sentence in SENTENCES:
        stream.push(sentence)
        await asyncio.sleep(0.005)  # sentences arrive while the first ones are already playing
    pulse.on_verified("long-1", True, " ".join(SENTENCES), is_voice=True)
    await asyncio.wait_for(stream.task, 3)
    assert await asyncio.to_thread(_wait, lambda: len(played) == len(SENTENCES))
    assert played == SENTENCES  # before the fix only the first sentence was heard
    out.stop()


@pytest.mark.asyncio
async def test_a_long_final_reply_is_not_cut_short():
    from jarvis.core.pulse.engine import PulseEngine
    out = _player()
    played = []
    out.event_callback = lambda name, rid, data: played.append(data["text"]) if name == "tts.stopped" and data["text"] else None
    pulse = PulseEngine(audio_output=out, tts_manager=FakeTTS())
    message = " ".join(f"Point {i}: the report lists item {i} with all of its details and the owner's notes." for i in range(1, 30))
    assert len(message) > 2000  # far beyond the old 900-character cut
    pulse.on_verified("long-2", True, message, is_voice=True)
    assert await asyncio.to_thread(_wait, lambda: played and "Point 29" in played[-1])
    assert "Point 1:" in played[0] and sum(p.count("Point") for p in played) == 29
    out.stop()


def test_queue_keeps_later_chunks_after_the_first_one_played():
    out = AudioOutputManager(mock_output=True)
    q = out.queue
    first = SpokenResponse(text="One.", type=ResponseType.FINAL, request_id="r", audio_bytes=b"\0\0", is_chunk=True,
                           is_last_chunk=False)
    assert q.put(first)
    assert q.get() is first
    out._play_response(first)  # the first sentence finished playing
    second = SpokenResponse(text="Two.", type=ResponseType.FINAL, request_id="r", audio_bytes=b"\0\0", is_chunk=True,
                            chunk_index=1, is_last_chunk=False)
    assert q.put(second) and q.get() is second  # still part of the same answer


def test_spoken_text_limits_are_generous():
    from jarvis.core.llm.streaming import StreamSink
    spoken = []
    sink = StreamSink(on_sentence=spoken.append, text_interval_s=0)
    for sentence in SENTENCES * 4:
        sink.feed(sentence + " ")
    sink.close()
    assert len(spoken) == len(SENTENCES) * 4


# ------------------------------------------------------------------------------------------------ hold / resume / skip
def test_pause_holds_playback_and_resume_finishes_it():
    out = _player()
    out.play(SpokenResponse(text="Hold me.", type=ResponseType.FINAL, request_id="p", audio_bytes=b"\x10\x00" * 8000,
                            sample_rate=16000))
    assert _wait(lambda: out._current_response is not None)
    assert out.pause() and out.is_paused and not out.is_playing
    time.sleep(0.3)
    assert out._current_response is not None  # still held, not thrown away
    out.resume()
    assert _wait(lambda: out._current_response is None and out.total_played == 1, timeout=3)
    out.stop()


def test_wait_without_continue_gives_up_and_stays_quiet():
    out = _player()
    out.play(SpokenResponse(text="A.", type=ResponseType.FINAL, request_id="h", audio_bytes=b"\x10\x00" * 8000, sample_rate=16000))
    out.play(SpokenResponse(text="B.", type=ResponseType.FINAL, request_id="h", audio_bytes=b"\x10\x00" * 8000, sample_rate=16000,
                            is_chunk=True, chunk_index=1))
    assert _wait(lambda: out._current_response is not None)
    assert out.hold(seconds=0.2)
    assert _wait(lambda: out._current_response is None, timeout=3)
    time.sleep(0.2)
    assert out.total_played == 0 and len(out.queue) == 0
    out.stop()


def test_skip_moves_to_the_next_sentence():
    out = _player()
    resp = SpokenResponse(text="Long.", type=ResponseType.FINAL, request_id="s", audio_bytes=b"\x10\x00" * 32000,
                          sample_rate=16000, is_chunk=True, is_last_chunk=False)
    nxt = SpokenResponse(text="Next.", type=ResponseType.FINAL, request_id="s", audio_bytes=b"\x10\x00" * 160,
                         sample_rate=16000, is_chunk=True, chunk_index=1)
    out.play(resp)
    out.play(nxt)
    assert _wait(lambda: out._current_response is resp)
    assert out.skip_current()
    assert _wait(lambda: nxt.delivery_status == DeliveryStatus.COMPLETED, timeout=3)
    assert resp.delivery_status == DeliveryStatus.INTERRUPTED
    out.stop()


# ------------------------------------------------------------------------------------------------ talk-over detection
def _run(detector, frames):
    return any(detector.feed(mic, out, speech, 30.0) for mic, out, speech in frames)


def test_jarvis_own_echo_never_counts_as_the_owner():
    from jarvis.core.audio.talk_over import TalkOverDetector
    d = TalkOverDetector()
    # loud speakers next to the mic: the mic hears JARVIS at 40% of its output, and the VAD calls it speech
    frames = [(0.4 * lvl, lvl, True) for lvl in [3000, 5000, 4000, 6000, 2500] * 40]
    assert not _run(d, frames)
    assert d.coupling < 0.6


def test_the_owner_talking_over_jarvis_is_heard():
    from jarvis.core.audio.talk_over import TalkOverDetector
    d = TalkOverDetector()
    _run(d, [(0.3 * 3000, 3000, False)] * 40)              # learns the echo
    assert _run(d, [(4500, 3000, True)] * 12)                # ~360 ms of clearly louder speech


def test_a_click_or_cough_does_not_interrupt():
    from jarvis.core.audio.talk_over import TalkOverDetector
    d = TalkOverDetector()
    _run(d, [(0.3 * 3000, 3000, False)] * 40)
    assert not _run(d, [(6000, 3000, True), (600, 3000, False), (500, 3000, False), (400, 3000, False)] * 5)


def test_headphones_quiet_speech_interrupts():
    from jarvis.core.audio.talk_over import TalkOverDetector
    d = TalkOverDetector(sensitivity="high")
    _run(d, [(30, 4000, False)] * 60)                        # headphones: almost no echo
    assert _run(d, [(900, 4000, True)] * 10)


def test_speech_between_sentences_interrupts():
    from jarvis.core.audio.talk_over import TalkOverDetector
    d = TalkOverDetector()
    _run(d, [(0.3 * 3000, 3000, False)] * 40)
    assert _run(d, [(1500, 0, True)] * 10)                   # JARVIS is silent between two sentences


# ------------------------------------------------------------------------------------------------ what was said
@pytest.mark.parametrize("action,phrases", [
    ("stop", ["stop talking", "ok that's enough", "shh", "be quiet", "you can stop now", "I got it, thanks", "enough already",
              "no need to read all that", "pesadha", "podhum", "stop it jarvis", "no more talking", "zip it"]),
    ("pause", ["wait", "hold on", "one second", "give me a moment", "hang on", "wait a sec", "pause", "konjam iru",
               "just a minute", "one moment please"]),
    ("resume", ["continue", "go on", "carry on", "keep going", "where were we", "continue reading", "keep talking",
                "you can continue", "resume", "finish what you were saying"]),
    ("repeat", ["say that again", "what did you say", "come again", "pardon", "I didn't catch that", "repeat that please",
                "can you say it again", "sorry what", "thirumba sollu", "one more time"]),
    ("skip", ["skip", "skip that", "next", "next part", "move on", "skip this part", "skip ahead", "next point", "next one",
              "skip it"]),
    ("slower", ["speak slower", "slow down", "talk a bit slower", "you're talking too fast", "read more slowly",
                "speak slowly please", "too fast", "go slower", "slow it down", "talk slower jarvis"]),
    ("faster", ["speak faster", "speed up", "talk a little faster", "you're speaking too slowly", "read quicker", "too slow",
                "go faster", "speed it up", "talk quicker", "speak faster please"]),
    ("louder", ["speak up", "louder", "I can't hear you", "talk louder", "a bit more loud", "raise your voice",
                "speak louder please", "louder please", "jarvis speak up", "talk up"]),
    ("softer", ["speak softer", "lower your voice", "you're too loud", "too loud", "talk quieter", "speak more quietly",
                "not so loud", "softer please", "talk lower", "speak down"]),
])
def test_voice_controls_by_meaning_while_speaking(action, phrases):
    from jarvis.core.audio.speech_control import classify
    for phrase in phrases:
        assert classify(phrase, speaking=True) == action, phrase


@pytest.mark.parametrize("text", ["open chrome", "what's the weather", "stop the music", "next song", "play the next video",
                                  "slow down the video", "turn the volume up", "send it to arun", "pause the music",
                                  "skip this ad on youtube", "continue the download"])
def test_ordinary_commands_are_not_voice_controls(text):
    from jarvis.core.audio.speech_control import classify
    assert classify(text, speaking=True) is None
    assert classify(text, speaking=False) is None


@pytest.mark.parametrize("text", ["next", "wait", "repeat that", "once more", "stop", "continue", "skip", "pause"])
def test_bare_words_keep_their_normal_meaning_when_jarvis_is_quiet(text):
    from jarvis.core.audio.speech_control import classify
    assert classify(text, speaking=False) is None


def test_leading_stop_keeps_the_new_instruction():
    from jarvis.core.audio.speech_control import leading_stop
    assert leading_stop("stop, open chrome instead") == "open chrome instead"
    assert leading_stop("Jarvis, wait. What time is it?") == "What time is it?"
    assert leading_stop("no no, I meant the other file") == "I meant the other file"
    assert leading_stop("open chrome") is None


# ------------------------------------------------------------------------------------------------ pipeline decision
class FakeEngine:
    def __init__(self, player):
        self.audio_output = player
        self.actions, self.stopped = [], 0

    def apply_speech_action(self, action):
        self.actions.append(action)
        return action

    def stop_speaking(self):
        self.stopped += 1
        self.audio_output.cancel_all()


def _pipeline(spoken="The capital of France is Paris and it is famous for the Eiffel Tower."):
    from jarvis.core.audio.output.barge_in import BargeInController
    from jarvis.core.audio.pipeline import VoicePipeline
    player = AudioOutputManager(mock_output=True)
    player._current_response = SpokenResponse(text=spoken, type=ResponseType.FINAL, request_id="x", audio_bytes=b"\0\0")
    player._currently_spoken_text = spoken
    player.pause()
    engine = FakeEngine(player)
    pipe = VoicePipeline(response_engine=engine, barge_in_controller=BargeInController(player), voice_enabled=False)
    pipe._talk_over_held = True
    return pipe, engine, player


def test_echo_or_noise_carries_on_speaking():
    pipe, engine, player = _pipeline()
    assert pipe._settle_talk_over("famous for the Eiffel Tower") is None
    assert not player.is_paused and engine.stopped == 0
    pipe, engine, player = _pipeline()
    assert pipe._settle_talk_over("") is None and not player.is_paused


def test_a_real_instruction_stops_speech_and_is_processed():
    pipe, engine, player = _pipeline()
    assert pipe._settle_talk_over("open chrome") == "open chrome"
    assert engine.stopped == 1
    pipe, engine, player = _pipeline()
    assert pipe._settle_talk_over("stop, what time is it") == "what time is it"
    assert engine.stopped == 1


@pytest.mark.parametrize("words,action", [("stop talking", "stop"), ("wait a second", "pause"), ("speak slower", "slower"),
                                          ("louder please", "louder"), ("skip that", "skip"), ("continue", "resume")])
def test_voice_controls_over_speech_are_applied_not_routed(words, action):
    pipe, engine, player = _pipeline()
    assert pipe._settle_talk_over(words) is None
    assert engine.actions == [action]


# ------------------------------------------------------------------------------------------------ routing + service
@pytest.mark.parametrize("text,intent,action", [
    ("speak slower", "speech_control", "slower"), ("talk a bit faster", "speech_control", "faster"),
    ("speak up", "speech_control", "louder"), ("lower your voice", "speech_control", "softer"),
    ("continue reading", "speech_control", "resume"), ("stop talking", "stop_speaking", None),
    ("no need to read all that", "stop_speaking", None), ("pesadha", "stop_speaking", None),
])
def test_router_maps_voice_controls(text, intent, action):
    from jarvis.core.router.control import match_control
    d = match_control(text, "r")
    assert d is not None and d.intent == intent
    if action:
        assert d.slots["action"] == action


def test_repeat_and_voice_settings_through_the_service(tmp_path):
    from jarvis.tests.ai_harness import AIHarness
    h = AIHarness(tmp_path, responder=lambda p: "LLM-WAS-CALLED")

    async def run():
        first = await h.say("what time is it")
        again = await h.say("say that again")
        slower = await h.say("speak slower")
        louder = await h.say("speak up")
        return first, again, slower, louder
    first, again, slower, louder = asyncio.run(run())
    assert first.message.split(".")[0] in again.message and again.state == "SUCCESS"  # the last answer, from the record
    assert "slower" in slower.message and h.service.response.tts.speech_rate < 1.0
    assert "louder" in louder.message and h.service.response.audio_output.volume > 1.0
    assert h.fake.chat_payloads() == []
    asyncio.run(h.close())
