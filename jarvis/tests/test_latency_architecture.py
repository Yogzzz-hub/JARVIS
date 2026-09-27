"""Low-latency voice path: speculative final STT during the pause, a live preview that never calls a model,
and a "command complete" verdict that is withdrawn when the user keeps talking."""
from __future__ import annotations

import asyncio

from jarvis.core.audio.frame import AudioFrame
from jarvis.core.audio.hub import AudioConsumer
from jarvis.core.audio.pipeline import VoicePipeline
from jarvis.core.audio.vad import EndpointDetector, VADResult, VADState
from jarvis.core.stt.base import TranscriptFinal

SPEECH, SIL = VADState.SPEECH, VADState.TRAILING_SILENCE


class ScriptedVAD:
    """Plays a list of states; silence_duration_ms grows by 100 ms per silent frame."""

    def __init__(self, states):
        self.states = list(states)
        self.silence_duration_ms = 0.0
        self.speech_duration_ms = 0.0

    def feed(self, frame):
        state = self.states.pop(0) if self.states else SIL
        if state == SPEECH:
            self.silence_duration_ms = 0.0
            self.speech_duration_ms += 300.0
        else:
            self.silence_duration_ms += 100.0
        return VADResult(is_speech=state == SPEECH, probability=0.9 if state == SPEECH else 0.1, inference_ms=0.1, state=state)

    def reset(self):
        pass


class SpecSTT:
    is_loaded = True
    model_name = "test"

    def __init__(self):
        self.spec_calls = 0
        self.final_calls = 0

    async def start_session(self, sid):
        pass

    async def feed_audio(self, pcm):
        pass

    async def get_partial(self):
        return None

    async def speculative_finalize(self):
        self.spec_calls += 1
        n = self.spec_calls
        await asyncio.sleep(0.005)
        return TranscriptFinal(session_id="s", text=f"speculative {n}")

    async def finalize(self):
        self.final_calls += 1
        return TranscriptFinal(session_id="s", text="slow final pass")


class EndAfter:
    """Ends the turn after ``ms`` of silence."""

    def __init__(self, ms):
        self.ms = ms

    def should_finalize(self, vad_state, silence_ms, **kw):
        return (silence_ms >= self.ms, "silence")


def run_session(states, end_after_ms=500):
    stt, vad = SpecSTT(), ScriptedVAD(states)
    pipeline = VoicePipeline(stt_engine=stt, vad_engine=vad, endpoint_detector=EndAfter(end_after_ms), preroll_ms=0)
    pipeline._running = True
    consumer = AudioConsumer("test_vad")
    pipeline._vad_consumer = consumer
    events = []
    pipeline._emit = lambda event, **data: events.append((event, data))
    frame = AudioFrame(sequence_id=1, timestamp_ns=1, sample_rate=16000, channels=1, sample_count=160, pcm=b"\x00\x01" * 160)

    async def main():
        async def feed():
            for _ in range(len(states) + 10):
                consumer.put(frame)
                await asyncio.sleep(0.01)  # lets the speculative task run between frames
        feeder = asyncio.create_task(feed())
        await pipeline._handle_speech_session(trigger_source="ptt")
        feeder.cancel()
    asyncio.run(main())
    finals = [d["text"] for e, d in events if e == "voice.final"]
    return stt, finals


def test_final_transcript_comes_from_the_pause_not_after_it():
    stt, finals = run_session([SPEECH, SPEECH, SIL, SIL, SIL, SIL, SIL, SIL])
    assert finals == ["speculative 1"]
    assert stt.spec_calls == 1 and stt.final_calls == 0  # no extra STT pass after the endpoint


def test_speaking_again_discards_the_speculative_pass():
    stt, finals = run_session([SPEECH, SPEECH, SIL, SIL, SIL, SPEECH, SPEECH, SIL, SIL, SIL, SIL, SIL, SIL])
    assert stt.spec_calls == 2 and finals == ["speculative 2"]  # the mid-sentence pause's result was thrown away


def test_short_command_pause_is_short_only_when_the_router_understood_everything():
    ep = EndpointDetector(default_silence_ms=800)
    assert ep.short_command_silence_ms == 320
    assert ep.should_finalize(SIL, 330, 900, stable_text="open chrome", router_complete=True)[0]
    assert not ep.should_finalize(SIL, 330, 900, stable_text="open chrome", router_complete=False)[0]
    assert not ep.should_finalize(SIL, 330, 900, stable_text="open chrome and", router_complete=True)[0]


def test_live_preview_never_calls_a_model():
    from jarvis.core.router.router import SmartRouter

    class Watch:
        calls = 0

        async def classify(self, *a, **k):
            Watch.calls += 1
            raise AssertionError("preview must not call the model")

    router = SmartRouter(llm_provider=Watch())
    d = asyncio.run(router.preview("what is the meaning of"))
    assert Watch.calls == 0 and d.lane.value != "LANE_0"
    assert asyncio.run(router.preview("open chrome")).intent == "open_app"


def test_early_preview_uses_the_model_free_path():
    from jarvis.core.audio.early_router import EarlyRoutePreview
    from jarvis.core.stt.base import TranscriptStablePrefix

    class Router:
        used = []

        async def preview(self, text):
            Router.used.append("preview")
            from jarvis.core.router.ollama import DisabledProvider
            from jarvis.core.router.router import SmartRouter
            return await SmartRouter(llm_provider=DisabledProvider()).preview(text)

        async def route(self, text):
            raise AssertionError("full route (may call a model) used for a live preview")

    pred = asyncio.run(EarlyRoutePreview(router=Router()).preview(TranscriptStablePrefix(session_id="s", text="mute")))
    assert Router.used == ["preview"] and pred.is_deterministic and pred.is_complete
