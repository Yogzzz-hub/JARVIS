"""Faster-Whisper STT engine for JARVIS EDGE.

Implements streaming STT using faster-whisper (CTranslate2).
CUDA primary with CPU fallback. Streaming via sliding window.
"""
from __future__ import annotations

import asyncio
import logging
import time
from time import perf_counter_ns

import numpy as np

from jarvis.core.stt.base import (
    STTEngine,
    TranscriptFinal,
    TranscriptPartial,
)

logger = logging.getLogger("jarvis.stt.whisper")


class FasterWhisperEngine:
    """Faster-Whisper STT engine with CUDA/CPU support.

    Features:
    - CUDA primary, CPU fallback
    - Streaming via sliding window (configurable context + step)
    - beam_size=1 for low-latency streaming
    - int8 quantization for VRAM efficiency
    - Vocabulary bias via initial_prompt
    """

    def __init__(
        self,
        model: str = "base",
        device: str = "cuda",
        compute_type: str = "int8",
        context_window_s: float = 6.0,
        step_size_ms: int = 400,
        initial_prompt: str = "",
        language: str = "en",
    ):
        self.model_name_str = model
        self.device_preference = device
        self.compute_type = compute_type
        self.context_window_s = context_window_s
        self.step_size_ms = step_size_ms
        self.initial_prompt = initial_prompt
        self.language = language

        self._model = None
        self._loaded = False
        self._device_actual = "cpu"
        self._session_id = ""
        self._audio_buffer = np.array([], dtype=np.float32)
        self._last_partial_text = ""
        self._load_time_ms = 0.0

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def model_name(self) -> str:
        return self.model_name_str

    @property
    def backend_name(self) -> str:
        return "faster_whisper"

    @property
    def device_name(self) -> str:
        return self._device_actual

    async def load(self) -> None:
        """Load Whisper model. Tries CUDA first, falls back to CPU."""
        t0 = perf_counter_ns()

        def _load():
            from faster_whisper import WhisperModel

            device = self.device_preference
            compute = self.compute_type

            # Try CUDA first
            if device == "cuda":
                try:
                    model = WhisperModel(
                        self.model_name_str,
                        device="cuda",
                        compute_type=compute,
                    )
                    # Verify CUDA DLLs are present by running a tiny test slice
                    dummy = np.zeros(1600, dtype=np.float32)
                    _ = list(model.transcribe(dummy, beam_size=1, without_timestamps=True)[0])
                    self._device_actual = "cuda"
                    logger.info("Whisper loaded on CUDA: model=%s, compute=%s", self.model_name_str, compute)
                    return model
                except Exception as exc:
                    logger.warning("CUDA load/warmup failed, falling back to CPU: %s", exc)

            # CPU fallback
            import os
            num_threads = min(8, max(4, os.cpu_count() or 4))
            model = WhisperModel(
                self.model_name_str,
                device="cpu",
                compute_type="int8",
                cpu_threads=num_threads,
            )
            self._device_actual = "cpu"
            logger.info("Whisper loaded on CPU (%d threads): model=%s", num_threads, self.model_name_str)
            return model


        self._model = await asyncio.to_thread(_load)
        self._loaded = True
        self._load_time_ms = (perf_counter_ns() - t0) / 1e6
        logger.info("Whisper load time: %.1f ms", self._load_time_ms)

    async def start_session(self, session_id: str) -> None:
        """Start a new transcription session."""
        self._session_id = session_id
        self._audio_buffer = np.array([], dtype=np.float32)
        self._last_partial_text = ""
        self._last_partial_sample_count = 0

    async def feed_audio(self, pcm: bytes, sample_rate: int = 16000) -> None:
        """Feed PCM16 audio into the transcription buffer."""
        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        self._audio_buffer = np.concatenate([self._audio_buffer, samples])

        # Trim to context window (keep latest N seconds)
        max_samples = int(self.context_window_s * sample_rate)
        if len(self._audio_buffer) > max_samples:
            self._audio_buffer = self._audio_buffer[-max_samples:]

    async def get_partial(self) -> TranscriptPartial | None:
        """Run inference on current buffer and return partial transcript."""
        if not self._loaded or self._model is None:
            return None

        if len(self._audio_buffer) < 1600:  # Need at least 0.1s
            return None

        t0 = perf_counter_ns()

        def _transcribe():
            segments, info = self._model.transcribe(
                self._audio_buffer,
                language=self.language,
                beam_size=1,
                best_of=1,
                temperature=0.0,
                condition_on_previous_text=False,
                initial_prompt=self.initial_prompt or None,
                vad_filter=False,  # We handle VAD externally
                without_timestamps=True,
            )
            text = " ".join(seg.text.strip() for seg in segments).strip()
            return text

        text = await asyncio.to_thread(_transcribe)

        if not text or text == self._last_partial_text:
            return None

        self._last_partial_text = text
        self._last_partial_sample_count = len(self._audio_buffer)
        duration_ms = len(self._audio_buffer) / 16.0  # 16 samples/ms at 16kHz

        return TranscriptPartial(
            session_id=self._session_id,
            text=text,
            start_ms=0.0,
            end_ms=duration_ms,
            confidence=0.0,
            generated_ns=perf_counter_ns(),
        )

    async def finalize(self) -> TranscriptFinal:
        """Run final high-quality transcription on complete audio."""
        t0 = perf_counter_ns()

        if not self._loaded or self._model is None:
            return TranscriptFinal(
                session_id=self._session_id,
                text=self._last_partial_text or "",
                stt_model=self.model_name_str,
                backend="faster_whisper",
                device=self._device_actual,
            )

        # Fast path: If recent partial was within 900ms of audio end (covers silence endpoint), reuse directly!
        samples_since_partial = len(self._audio_buffer) - getattr(self, "_last_partial_sample_count", 0)
        if self._last_partial_text and samples_since_partial < 16000 * 0.95:
            duration_ms = len(self._audio_buffer) / 16.0
            return TranscriptFinal(
                session_id=self._session_id,
                text=self._last_partial_text,
                language=self.language or "en",
                duration_ms=duration_ms,
                stt_model=self.model_name_str,
                backend="faster_whisper",
                device=self._device_actual,
                finalization_ms=(perf_counter_ns() - t0) / 1e6,
                segments=[],
            )

        def _transcribe_final():
            segments, info = self._model.transcribe(
                self._audio_buffer,
                language=self.language,
                beam_size=1,  # Fast and accurate for local commands
                best_of=1,
                temperature=0.0,
                condition_on_previous_text=False,
                initial_prompt=self.initial_prompt or None,
                vad_filter=False,
                without_timestamps=True,
            )
            seg_list = []
            texts = []
            for seg in segments:
                t = seg.text.strip()
                texts.append(t)
                seg_list.append({
                    "start": seg.start,
                    "end": seg.end,
                    "text": t,
                })
            return " ".join(texts).strip(), info.language, seg_list

        text, language, segments = await asyncio.to_thread(_transcribe_final)
        finalization_ms = (perf_counter_ns() - t0) / 1e6
        duration_ms = len(self._audio_buffer) / 16.0

        return TranscriptFinal(
            session_id=self._session_id,
            text=text,
            language=language or "en",
            duration_ms=duration_ms,
            stt_model=self.model_name_str,
            backend="faster_whisper",
            device=self._device_actual,
            finalization_ms=finalization_ms,
            segments=segments,
        )

    async def cancel(self) -> None:
        """Cancel current session."""
        self._audio_buffer = np.array([], dtype=np.float32)
        self._last_partial_text = ""
        self._session_id = ""

    async def unload(self) -> None:
        """Unload model to free VRAM/RAM."""
        self._model = None
        self._loaded = False
        self._audio_buffer = np.array([], dtype=np.float32)
        self._device_actual = "cpu"
        logger.info("Whisper model unloaded")
