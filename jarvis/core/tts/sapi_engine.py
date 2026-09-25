"""Windows SAPI Fallback TTS Engine for JARVIS EDGE Phase 7.

Provides reliable local speech fallback via Windows SAPI / pyttsx3
when Piper is unavailable or encounters an unrecoverable failure.
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import uuid
import wave
from pathlib import Path
from time import perf_counter_ns
from typing import AsyncIterable, Optional

from jarvis.core.tts.base import TTSChunk, TTSEngine

logger = logging.getLogger("jarvis.tts.sapi")


class SAPIEngine:
    """Windows SAPI fallback TTS engine via pyttsx3."""

    def __init__(self, rate: int = 190, volume: float = 1.0) -> None:
        self.rate = rate
        self.volume = volume
        self._engine = None
        self._is_loaded = False
        self._cancelled = False
        self.total_syntheses = 0
        self.sample_rate = 22050

    @property
    def backend_name(self) -> str:
        return "sapi"

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    def load(self) -> None:
        """Initialize SAPI engine."""
        if self._is_loaded:
            return

        try:
            import pyttsx3
            self._engine = pyttsx3.init("sapi5")
            self._engine.setProperty("rate", self.rate)
            self._engine.setProperty("volume", self.volume)
            self._is_loaded = True
            logger.info("Windows SAPI TTS engine initialized successfully")
        except Exception as exc:
            logger.warning("Failed to initialize Windows SAPI engine: %s", exc)
            self._is_loaded = False

    def set_gender(self, gender: str) -> None:
        """Switch SAPI voice gender if matching voice is available."""
        self.load()
        if not self._is_loaded or not self._engine:
            return
        try:
            voices = self._engine.getProperty("voices")
            is_fem = "fem" in gender.lower() or "woman" in gender.lower()
            for v in voices:
                v_name = v.name.lower()
                if is_fem and ("zira" in v_name or "female" in v_name or "hazel" in v_name or "susan" in v_name):
                    self._engine.setProperty("voice", v.id)
                    logger.info("SAPI voice set to %s", v.name)
                    break
                elif not is_fem and ("david" in v_name or "male" in v_name or "george" in v_name):
                    self._engine.setProperty("voice", v.id)
                    logger.info("SAPI voice set to %s", v.name)
                    break
        except Exception as exc:
            logger.warning("Could not set SAPI voice gender: %s", exc)

    def synthesize(self, text: str) -> bytes:
        """Synthesize text to PCM16 bytes via temporary WAV."""
        self.load()
        if not self._is_loaded or not self._engine:
            return b""

        temp_path = os.path.join(tempfile.gettempdir(), f"jarvis_sapi_{uuid.uuid4().hex[:8]}.wav")
        try:
            self._engine.save_to_file(text, temp_path)
            self._engine.runAndWait()

            if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                return b""

            with wave.open(temp_path, "rb") as wf:
                self.sample_rate = wf.getframerate()
                if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
                    raise ValueError("SAPI must produce mono PCM16")
                pcm = wf.readframes(wf.getnframes())

            self.total_syntheses += 1
            return pcm
        except Exception as exc:
            logger.error("SAPI synthesis error: %s", exc)
            return b""
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    async def stream(self, text: str) -> AsyncIterable[TTSChunk]:
        """Stream SAPI synthesized audio chunk."""
        loop = asyncio.get_running_loop()
        pcm = await loop.run_in_executor(None, self.synthesize, text)
        if not pcm:
            return

        # SAPI default rate is typically 22050 or 16000 or 44100
        dur_ms = (len(pcm) / (2 * 22050)) * 1000.0
        yield TTSChunk(
            pcm=pcm,
            sample_rate=22050,
            sample_width=2,
            channels=1,
            is_final=True,
            first_chunk=True,
            text=text,
            duration_ms=dur_ms,
        )

    def cancel(self) -> None:
        self._cancelled = True
        if self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass

    def unload(self) -> None:
        self._engine = None
        self._is_loaded = False
