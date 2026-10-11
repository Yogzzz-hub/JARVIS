"""Optional ElevenLabs voice: opt-in, raw PCM straight to the player, and the local voice takes over on any failure."""
from __future__ import annotations

import asyncio
import json

import httpx

from jarvis.core.tts import elevenlabs_engine
from jarvis.core.tts.elevenlabs_engine import ElevenLabsEngine
from jarvis.core.tts.manager import TTSManager


class Local:
    sample_rate = 22050
    backend_name = "piper"

    def __init__(self):
        self.calls = 0

    def synthesize(self, text):
        self.calls += 1
        return b"\x01\x00" * 100

    async def stream(self, text):
        from jarvis.core.tts.base import TTSChunk
        yield TTSChunk(pcm=b"\x01\x00" * 10)

    def load(self): pass
    def cancel(self): pass
    def unload(self): pass


def engine(handler):
    return ElevenLabsEngine(api_key="k", transport=httpx.MockTransport(handler))


def test_opt_in_only(monkeypatch):
    monkeypatch.delenv("JARVIS_TTS_ENGINE", raising=False)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    assert not elevenlabs_engine.enabled()
    monkeypatch.setenv("JARVIS_TTS_ENGINE", "elevenlabs")
    assert elevenlabs_engine.enabled()
    monkeypatch.delenv("ELEVENLABS_API_KEY")
    assert not elevenlabs_engine.enabled()
    assert TTSManager(piper_engine=Local(), sapi_engine=Local()).cloud is None


def test_requests_raw_pcm_with_the_flash_model():
    seen = {}

    def handler(request):
        seen["url"], seen["key"] = str(request.url), request.headers["xi-api-key"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, content=b"\x02\x00" * 50)
    local = Local()
    tts = TTSManager(piper_engine=local, sapi_engine=Local(), cloud_engine=engine(handler))
    pcm, backend = tts.synthesize("Good evening, sir.")
    assert backend == "elevenlabs" and pcm == b"\x02\x00" * 50 and local.calls == 0
    assert "output_format=pcm_22050" in seen["url"] and seen["key"] == "k"
    assert seen["body"]["model_id"] == "eleven_flash_v2_5" and seen["body"]["text"] == "Good evening, sir."


def test_failure_falls_back_to_the_local_voice_and_trips_a_breaker():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(401, text="invalid api key")
    local = Local()
    tts = TTSManager(piper_engine=local, sapi_engine=Local(), cloud_engine=engine(handler))
    assert tts.synthesize("Hello there.")[1] == "piper"
    assert tts.synthesize("Hello again.")[1] == "piper"
    assert calls["n"] == 1 and "401" in tts.cloud.last_error      # no retry storm while it is down


def test_streaming_uses_the_cloud_voice():
    tts = TTSManager(piper_engine=Local(), sapi_engine=Local(),
                     cloud_engine=engine(lambda r: httpx.Response(200, content=b"\x03\x00" * 40)))

    async def collect():
        return [(c.pcm, b) async for c, b in tts.stream("Right away.")]
    chunks = asyncio.run(collect())
    assert chunks == [(b"\x03\x00" * 40, "elevenlabs")]
