"""Optional cloud voice: ElevenLabs text-to-speech, as the first engine with Piper / SAPI behind it.

Opt-in only, because it sends what JARVIS says to a cloud service: set ELEVENLABS_API_KEY and
JARVIS_TTS_ENGINE=elevenlabs (optionally ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL). It asks for raw 16-bit PCM at
22.05 kHz, the same format Piper produces, so the audio goes straight to the existing player with no decoding, and
uses the low-latency flash model by default. Any failure (no key, offline, quota) trips a short breaker and the
local voice speaks instead - JARVIS never goes silent because a cloud call failed.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import AsyncIterable, Optional

from jarvis.core.tts.base import TTSChunk

logger = logging.getLogger("jarvis.tts.elevenlabs")

API = "https://api.elevenlabs.io/v1/text-to-speech/{voice}"
DEFAULT_VOICE = "JBFqnCBsd6RMkjVDRZzb"      # "George": a warm British male voice from the default library
DEFAULT_MODEL = "eleven_flash_v2_5"
SAMPLE_RATE = 22050
BREAKER_S = 120.0


def enabled() -> bool:
    return os.environ.get("JARVIS_TTS_ENGINE", "").strip().lower() in ("elevenlabs", "eleven", "11labs") \
        and bool(os.environ.get("ELEVENLABS_API_KEY", "").strip())


class ElevenLabsEngine:
    def __init__(self, api_key: Optional[str] = None, voice_id: Optional[str] = None, model: Optional[str] = None,
                 transport=None, timeout_s: float = 12.0) -> None:
        self.api_key = (api_key or os.environ.get("ELEVENLABS_API_KEY", "")).strip()
        self.voice_id = (voice_id or os.environ.get("ELEVENLABS_VOICE_ID", "") or DEFAULT_VOICE).strip()
        self.model = (model or os.environ.get("ELEVENLABS_MODEL", "") or DEFAULT_MODEL).strip()
        self.sample_rate = SAMPLE_RATE
        self.timeout_s = timeout_s
        self._transport = transport
        self._client = None
        self._lock = threading.Lock()
        self._down_until = 0.0
        self.last_error = ""
        self.length_scale = 1.0                   # set by TTSManager.set_rate; mapped to ElevenLabs "speed"

    backend_name = "elevenlabs"

    @property
    def is_loaded(self) -> bool:
        return self._client is not None

    @property
    def available(self) -> bool:
        return bool(self.api_key) and time.monotonic() >= self._down_until

    def load(self) -> None:
        if self._client is None:
            import httpx
            self._client = httpx.Client(timeout=self.timeout_s, transport=self._transport)

    def synthesize(self, text: str) -> bytes:
        if not self.available:
            raise RuntimeError(self.last_error or "ElevenLabs is not configured")
        self.load()
        speed = max(0.7, min(1.2, 1.0 / (self.length_scale or 1.0)))
        try:
            with self._lock:
                resp = self._client.post(
                    API.format(voice=self.voice_id), params={"output_format": f"pcm_{SAMPLE_RATE}"},
                    headers={"xi-api-key": self.api_key, "accept": "audio/pcm", "content-type": "application/json"},
                    json={"text": text, "model_id": self.model, "voice_settings": {"stability": 0.5, "similarity_boost": 0.75,
                                                                                   "speed": round(speed, 2)}})
            if resp.status_code != 200:
                detail = resp.text[:160] if resp.text else ""
                raise RuntimeError(f"ElevenLabs HTTP {resp.status_code} {detail}".strip())
            pcm = resp.content
            if len(pcm) % 2:
                pcm = pcm[:-1]
            if not pcm:
                raise RuntimeError("ElevenLabs returned no audio")
            self.last_error = ""
            return pcm
        except Exception as exc:
            self.last_error = str(exc) or type(exc).__name__
            self._down_until = time.monotonic() + BREAKER_S
            logger.warning("ElevenLabs TTS failed (%s); using the local voice for %.0fs", self.last_error, BREAKER_S)
            raise

    async def stream(self, text: str) -> AsyncIterable[TTSChunk]:
        import asyncio
        pcm = await asyncio.to_thread(self.synthesize, text)
        yield TTSChunk(pcm=pcm, sample_rate=SAMPLE_RATE, is_final=True, first_chunk=True, text=text,
                       duration_ms=len(pcm) / 2 / SAMPLE_RATE * 1000)

    def cancel(self) -> None:
        pass

    def unload(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
