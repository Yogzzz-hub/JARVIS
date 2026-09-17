"""Piper Local TTS Engine for JARVIS EDGE Phase 7.

Wraps piper.PiperVoice to provide ultra-fast streaming sentence-chunked
speech synthesis entirely on local CPU/device with 0 cloud dependencies.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from pathlib import Path
from time import perf_counter_ns
from typing import AsyncIterable, Dict, List, Optional

from jarvis.core.tts.base import TTSChunk, TTSEngine

logger = logging.getLogger("jarvis.tts.piper")

DEFAULT_PIPER_MODEL = "models/piper/en/en_US/lessac/medium/en_US-lessac-medium.onnx"

PRONUNCIATION_OVERRIDES = {
    r"\bFastAPI\b": "Fast A P I",
    r"\bCUDA\b": "Cooda",
    r"\bRIT\b": "R I T",
    r"\bNLP\b": "N L P",
    r"\bAPI\b": "A P I",
    r"\bGPU\b": "G P U",
    r"\bCPU\b": "C P U",
    r"\bRAM\b": "Ram",
    r"\bQwen\b": "Kwen",
    r"\bSupabase\b": "Soopa base",
    r"\bUI\b": "U I",
    r"\bCLI\b": "C L I",
    r"\bDAG\b": "D A G",
    r"\bJSON\b": "Jason",
    r"\bSQL\b": "Sequel",
}


def normalize_tts_text(text: str) -> str:
    """Normalize text prior to synthesis for natural pronunciation."""
    if not text:
        return ""

    norm = text.strip()

    # Apply pronunciation overrides
    for pattern, replacement in PRONUNCIATION_OVERRIDES.items():
        norm = re.sub(pattern, replacement, norm, flags=re.IGNORECASE)

    # Normalize ellipses and duplicate punctuation
    norm = re.sub(r"\.{2,}", ".", norm)
    norm = re.sub(r"\s+([,.?!;:])", r"\1", norm)

    # Clean double spaces
    norm = re.sub(r"\s+", " ", norm).strip()
    return norm


class PiperEngine:
    """High-performance local TTS engine powered by Piper."""

    def __init__(
        self,
        model_path: Optional[str | Path] = None,
        config_path: Optional[str | Path] = None,
        use_cuda: bool = False,
    ) -> None:
        self.model_path = Path(model_path or DEFAULT_PIPER_MODEL)
        self.config_path = Path(config_path) if config_path else None
        self.use_cuda = use_cuda
        self._voice = None
        self._cancelled = False
        self._load_lock = asyncio.Lock()

        # Telemetry
        self.total_syntheses = 0
        self.last_load_ms = 0.0
        self.last_first_chunk_ms = 0.0
        self.last_total_synthesis_ms = 0.0

    @property
    def backend_name(self) -> str:
        return "piper"

    @property
    def is_loaded(self) -> bool:
        return self._voice is not None

    def load(self) -> None:
        """Load the Piper ONNX model synchronously into memory."""
        if self._voice is not None:
            return

        if not self.model_path.exists():
            raise FileNotFoundError(f"Piper model not found at {self.model_path}")

        t0 = perf_counter_ns()
        from piper import PiperVoice

        cfg = str(self.config_path) if self.config_path and self.config_path.exists() else None
        self._voice = PiperVoice.load(str(self.model_path), config_path=cfg, use_cuda=self.use_cuda)
        self.last_load_ms = (perf_counter_ns() - t0) / 1e6
        logger.info("Piper voice model loaded in %.1f ms from %s", self.last_load_ms, self.model_path)

    async def ensure_loaded(self) -> None:
        """Ensure model is loaded asynchronously in executor if needed."""
        if self._voice is None:
            async with self._load_lock:
                if self._voice is None:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, self.load)

    def synthesize(self, text: str) -> bytes:
        """Synthesize entire text to PCM16 bytes synchronously."""
        self.load()
        norm_text = normalize_tts_text(text)
        if not norm_text:
            return b""

        self._cancelled = False
        t0 = perf_counter_ns()
        pcm_chunks = []
        for chunk in self._voice.synthesize(norm_text):
            if self._cancelled:
                break
            pcm_chunks.append(chunk.audio_int16_bytes)

        self.last_total_synthesis_ms = (perf_counter_ns() - t0) / 1e6
        self.total_syntheses += 1
        return b"".join(pcm_chunks)

    async def stream(self, text: str) -> AsyncIterable[TTSChunk]:
        """Stream sentence chunks asynchronously as they are synthesized."""
        await self.ensure_loaded()
        norm_text = normalize_tts_text(text)
        if not norm_text:
            return

        self._cancelled = False
        t0 = perf_counter_ns()
        first_chunk_yielded = False

        # Sentence-level stream from Piper
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Optional[TTSChunk]] = asyncio.Queue()

        def _synthesize_worker():
            try:
                chunk_index = 0
                for chunk in self._voice.synthesize(norm_text):
                    if self._cancelled:
                        break
                    now_ns = perf_counter_ns()
                    dur_ms = (len(chunk.audio_int16_bytes) / (2 * chunk.sample_rate)) * 1000.0
                    tts_chunk = TTSChunk(
                        pcm=chunk.audio_int16_bytes,
                        sample_rate=chunk.sample_rate,
                        sample_width=chunk.sample_width,
                        channels=chunk.sample_channels,
                        first_chunk=(chunk_index == 0),
                        is_final=False,
                        duration_ms=dur_ms,
                    )
                    chunk_index += 1
                    asyncio.run_coroutine_threadsafe(queue.put(tts_chunk), loop)
            except Exception as exc:
                logger.error("Error during Piper streaming synthesis: %s", exc)
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)

        # Run worker thread
        synth_task = loop.run_in_executor(None, _synthesize_worker)

        while True:
            chunk = await queue.get()
            if chunk is None:
                break

            if not first_chunk_yielded:
                self.last_first_chunk_ms = (perf_counter_ns() - t0) / 1e6
                first_chunk_yielded = True

            yield chunk

        self.last_total_synthesis_ms = (perf_counter_ns() - t0) / 1e6
        self.total_syntheses += 1
        await synth_task

    def cancel(self) -> None:
        """Signal ongoing synthesis to abort."""
        self._cancelled = True

    def unload(self) -> None:
        """Release voice model."""
        self._voice = None
        logger.info("Piper voice model unloaded")
