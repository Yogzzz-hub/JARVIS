"""Answers are spoken sentence by sentence while the model is still writing them."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from jarvis.core.llm.streaming import SentenceChunker, StreamSink
from jarvis.tests.ai_harness import AIHarness, route_by_prompt
from jarvis.tests.fake_ollama import FakeOllama


def _chunks(text: str, step: int = 3) -> list[str]:
    chunker = SentenceChunker()
    out: list[str] = []
    for i in range(0, len(text), step):
        out += chunker.feed(text[i:i + step])
    return out + chunker.flush()


def test_sentences_are_released_as_soon_as_they_end():
    chunker = SentenceChunker()
    assert chunker.feed("Paris is the capital of France. It is") == ["Paris is the capital of France."]
    assert chunker.feed(" known for the Eiffel Tower!") == []
    assert chunker.flush() == ["It is known for the Eiffel Tower!"]


def test_abbreviations_and_decimals_do_not_split():
    text = "Dr. Rao said the dose is 2.5 mg e.g. twice daily. Take it with food."
    assert _chunks(text) == ["Dr. Rao said the dose is 2.5 mg e.g. twice daily.", "Take it with food."]


def test_long_first_clause_is_released_early_at_a_comma():
    chunker = SentenceChunker()
    out = chunker.feed("Recursion is when a function calls itself, and each call works on a smaller")
    assert out == ["Recursion is when a function calls itself,"]


def test_sink_stops_speaking_after_budget_but_keeps_text():
    spoken, texts = [], []
    sink = StreamSink(on_sentence=spoken.append, on_text=texts.append, text_interval_s=0, max_spoken_chars=20)
    for part in ["One two three four five. ", "Six seven eight. ", "Nine ten."]:
        sink.feed(part)
    sink.close()
    assert spoken == ["One two three four five."]
    assert sink.text.endswith("Nine ten.") and texts[-1] == sink.text


@pytest.mark.asyncio
async def test_stream_chat_hides_think_blocks_split_across_chunks():
    parts = ["<think>plan", " more</think>Hel", "lo <think>x</think>there"]
    lines = [json.dumps({"message": {"content": p}, "done": False}) for p in parts] + [json.dumps({"done": True})]
    fake = FakeOllama(models=["qwen3:1.7b"], responder=lambda p: httpx.Response(200, content=("\n".join(lines) + "\n").encode()))
    client = fake.client(chat_model="qwen3:1.7b")
    try:
        text = "".join([d async for d in client.stream_chat([{"role": "user", "content": "hi"}])])
    finally:
        await client.aclose()
    assert text == "Hello there"


class FakeSpeech:
    def __init__(self):
        self.sentences: list[str] = []
        self.spoke = False
        self.closed = False
        self.task = None

    def push(self, sentence: str) -> None:
        self.spoke = True
        self.sentences.append(sentence)

    def close(self) -> None:
        self.closed = True


class FakePulse:
    """Records what the PULSE engine would say."""

    def __init__(self):
        self.stream = FakeSpeech()
        self.final_messages: list[str] = []
        self.audio_output = object()

    def open_speech_stream(self, request_id):
        return self.stream

    def close_speech_stream(self, request_id):
        self.stream.close()

    def predict_duration(self, *args, **kwargs):
        return 900.0

    def __getattr__(self, name):
        return lambda *a, **k: None

    def on_verified(self, request_id, is_verified, result_message, **kwargs):
        self.final_messages.append(result_message)


@pytest.mark.asyncio
async def test_voice_answer_is_streamed_to_speech_and_ui(tmp_path):
    answer = "Recursion is a function calling itself. Each call solves a smaller piece. It stops at a base case."
    harness = AIHarness(tmp_path, route_by_prompt([], default=answer))
    pulse = FakePulse()
    harness.service.pulse = pulse
    partials: list[str] = []

    async def capture(event):
        if event.name == "assistant.partial":
            partials.append(event.data["text"])

    harness.bus.subscribe(capture)
    try:
        result = await harness.say("explain recursion like I'm five", source="voice")
        await asyncio.sleep(0)
    finally:
        await harness.close()
    assert result.state == "SUCCESS"
    assert pulse.stream.sentences == [
        "Recursion is a function calling itself.", "Each call solves a smaller piece.", "It stops at a base case."]
    assert partials and partials[-1].strip() == answer
    assert result.metrics.get("first_token_ms") is not None


class RecordingTTS:
    blocking = False
    sample_rate = 22050

    def __init__(self):
        self.texts: list[str] = []

    def synthesize(self, text):
        self.texts.append(text)
        return b"\x00\x00" * 10, "fake"


class RecordingOutput:
    _running = True
    _cancel_ns = 0

    def __init__(self):
        self.played: list[str] = []

    def play(self, response):
        self.played.append(response.text)


@pytest.mark.asyncio
async def test_pulse_speaks_streamed_sentences_once_and_skips_the_final_repeat():
    from jarvis.core.pulse.engine import PulseEngine

    output, tts = RecordingOutput(), RecordingTTS()
    pulse = PulseEngine(audio_output=output, tts_manager=tts)
    stream = pulse.open_speech_stream("r1")
    stream.push("First sentence.")
    stream.push("**Second** sentence.")
    pulse.on_verified("r1", True, "First sentence. Second sentence.", is_voice=True)
    await asyncio.wait_for(stream.task, 2)
    assert output.played == ["First sentence.", "Second sentence."]


@pytest.mark.asyncio
async def test_barge_in_drops_the_rest_of_a_streamed_answer():
    import time
    from jarvis.core.pulse.engine import PulseEngine

    output, tts = RecordingOutput(), RecordingTTS()
    pulse = PulseEngine(audio_output=output, tts_manager=tts)
    stream = pulse.open_speech_stream("r2")
    stream.push("Hello there.")
    await asyncio.sleep(0.01)
    output._cancel_ns = time.perf_counter_ns()
    stream.push("You should not hear this.")
    pulse.on_verified("r2", True, "Hello there. You should not hear this.", is_voice=True)
    await asyncio.wait_for(stream.task, 2)
    assert output.played == ["Hello there."]
