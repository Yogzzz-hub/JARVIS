"""Voice Activity Detection (VAD) engine for JARVIS EDGE.

Implements streaming VAD using Silero ONNX with state machine
for speech boundary detection and adaptive endpointing.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from time import perf_counter_ns
from typing import Protocol, runtime_checkable

import numpy as np

from jarvis.core.audio.frame import AudioFrame, SILERO_CHUNK_SAMPLES

logger = logging.getLogger("jarvis.audio.vad")


class VADState(StrEnum):
    """Voice activity detection states."""
    SILENCE = "SILENCE"
    POSSIBLE_SPEECH = "POSSIBLE_SPEECH"
    SPEECH = "SPEECH"
    TRAILING_SILENCE = "TRAILING_SILENCE"


@dataclass(slots=True)
class VADResult:
    """Result from a single VAD inference."""
    is_speech: bool
    probability: float
    inference_ms: float
    state: VADState


@runtime_checkable
class VADEngine(Protocol):
    """Protocol for VAD engines."""

    def feed(self, frame: AudioFrame) -> VADResult: ...
    def reset(self) -> None: ...
    def close(self) -> None: ...


class SileroVADEngine:
    """Silero ONNX streaming VAD on CPU.

    Uses silero-vad-lite for lightweight inference (< 1ms per chunk).
    512-sample chunks (32ms at 16kHz). Keeps model on CPU.
    """

    def __init__(
        self,
        speech_start_threshold: float = 0.5,
        speech_end_threshold: float = 0.35,
        min_speech_ms: int = 100,
        min_silence_ms: int = 250,
        speech_pad_ms: int = 150,
        max_utterance_seconds: int = 60,
    ):
        self.speech_start_threshold = speech_start_threshold
        self.speech_end_threshold = speech_end_threshold
        self.min_speech_ms = min_speech_ms
        self.min_silence_ms = min_silence_ms
        self.speech_pad_ms = speech_pad_ms
        self.max_utterance_seconds = max_utterance_seconds

        self._state = VADState.SILENCE
        self._speech_start_ns: int = 0
        self._silence_start_ns: int = 0
        self._buffer = np.array([], dtype=np.float32)
        self._vad = None
        self._loaded = False
        self._last_probability = 0.0
        self._audio_ns = 0

    def _ensure_loaded(self):
        if self._loaded:
            return
        try:
            from silero_vad_lite import SileroVAD
            self._vad = SileroVAD(16000)
            self._loaded = True
            logger.info("SileroVAD loaded (CPU)")
        except Exception as exc:
            logger.warning("SileroVAD load failed: %s", exc)

    def feed(self, frame: AudioFrame) -> VADResult:
        """Feed audio frame through VAD. Returns speech probability and state."""
        self._ensure_loaded()

        t0 = perf_counter_ns()
        now = perf_counter_ns()

        if not self._loaded or self._vad is None:
            return VADResult(
                is_speech=False, probability=0.0,
                inference_ms=0.0, state=self._state,
            )

        now = frame.timestamp_ns if getattr(frame, "timestamp_ns", 0) > 0 else perf_counter_ns()
        self._last_now_ns = now

        # Convert PCM16 to float32 normalized [-1, 1]
        samples = np.frombuffer(frame.pcm, dtype=np.int16).astype(np.float32) / 32768.0
        self._buffer = np.concatenate([self._buffer, samples])

        probability = self._last_probability

        # Process in 512-sample chunks
        while len(self._buffer) >= SILERO_CHUNK_SAMPLES:
            chunk = self._buffer[:SILERO_CHUNK_SAMPLES]
            self._buffer = self._buffer[SILERO_CHUNK_SAMPLES:]
            probability = float(self._vad.process(chunk.tobytes()))
        self._last_probability = probability

        inference_ms = (perf_counter_ns() - t0) / 1e6

        # State machine with hysteresis
        is_speech = False

        if self._state == VADState.SILENCE:
            if probability >= self.speech_start_threshold:
                self._state = VADState.POSSIBLE_SPEECH
                self._speech_start_ns = now
                self._silence_start_ns = 0
                is_speech = False

        elif self._state == VADState.POSSIBLE_SPEECH:
            if probability >= self.speech_start_threshold:
                elapsed_ms = (now - self._speech_start_ns) / 1e6
                if elapsed_ms >= self.min_speech_ms:
                    self._state = VADState.SPEECH
                    is_speech = True
            else:
                self._state = VADState.SILENCE
                self._speech_start_ns = 0

        elif self._state == VADState.SPEECH:
            is_speech = True
            # Check max utterance
            elapsed_s = (now - self._speech_start_ns) / 1e9
            if elapsed_s >= self.max_utterance_seconds:
                self._state = VADState.TRAILING_SILENCE
                self._silence_start_ns = now
            elif probability < self.speech_end_threshold:
                self._state = VADState.TRAILING_SILENCE
                self._silence_start_ns = now

        elif self._state == VADState.TRAILING_SILENCE:
            if probability >= self.speech_start_threshold:
                # Speech resumed — back to SPEECH
                self._state = VADState.SPEECH
                is_speech = True
                self._silence_start_ns = 0
            else:
                silence_ms = (now - self._silence_start_ns) / 1e6
                if silence_ms >= self.min_silence_ms:
                    # Endpoint detected
                    self._state = VADState.SILENCE
                    is_speech = False
                else:
                    is_speech = True  # Still within trailing silence window

        return VADResult(
            is_speech=is_speech,
            probability=probability,
            inference_ms=inference_ms,
            state=self._state,
        )

    @property
    def state(self) -> VADState:
        return self._state

    @property
    def speech_duration_ms(self) -> float:
        """Current speech duration in ms (0 if not speaking)."""
        if self._speech_start_ns == 0:
            return 0.0
        now = getattr(self, "_last_now_ns", 0) or perf_counter_ns()
        return (now - self._speech_start_ns) / 1e6

    @property
    def silence_duration_ms(self) -> float:
        """Current trailing silence duration in ms."""
        if self._silence_start_ns == 0:
            return 0.0
        now = getattr(self, "_last_now_ns", 0) or perf_counter_ns()
        return (now - self._silence_start_ns) / 1e6

    def reset(self) -> None:
        """Reset VAD state for new session."""
        self._state = VADState.SILENCE
        self._last_probability = 0.0
        self._audio_ns = 0
        self._speech_start_ns = 0
        self._silence_start_ns = 0
        self._last_now_ns = 0
        self._buffer = np.array([], dtype=np.float32)
        if self._vad:
            try:
                self._vad.reset()
            except Exception:
                self._vad = None
                try:
                    from silero_vad_lite import SileroVAD
                    self._vad = SileroVAD(16000)
                except Exception:
                    pass

    def close(self) -> None:
        """Release resources."""
        self._vad = None
        self._loaded = False
        self._buffer = np.array([], dtype=np.float32)


CONTINUATION_INDICATORS = frozenset({
    "and", "then", "after that", "with", "for", "to", "or", "but", "also"
})


class EndpointDetector:
    """Adaptive end-of-speech detection.

    Combines VAD silence duration with transcript stability, linguistic continuation hints,
    and router completeness signals for optimal endpointing.
    """

    def __init__(
        self,
        default_silence_ms: int = 320,
        short_command_silence_ms: int = 180,
        long_utterance_silence_ms: int = 420,
        incomplete_silence_ms: int = 500,
    ):
        self.default_silence_ms = default_silence_ms
        self.short_command_silence_ms = short_command_silence_ms
        self.long_utterance_silence_ms = long_utterance_silence_ms
        self.incomplete_silence_ms = incomplete_silence_ms

    def should_finalize(
        self,
        vad_state: VADState,
        silence_ms: float,
        utterance_ms: float,
        stable_text: str = "",
        router_complete: bool = False,
        incomplete_hint: bool = False,
    ) -> tuple[bool, str]:
        """Decide if utterance should be finalized.

        Returns (should_finalize, reason).
        """
        if vad_state != VADState.SILENCE and vad_state != VADState.TRAILING_SILENCE:
            return False, "speech_active"

        # Check linguistic continuation indicators
        words = stable_text.strip().lower().split()
        last_word = words[-1] if words else ""
        last_two = " ".join(words[-2:]) if len(words) >= 2 else ""
        is_continuation = (
            incomplete_hint
            or last_word in CONTINUATION_INDICATORS
            or last_two in CONTINUATION_INDICATORS
        )

        # Incomplete linguistic structure / continuation word — wait longer
        if is_continuation:
            if silence_ms >= self.incomplete_silence_ms:
                return True, "incomplete_timeout" if incomplete_hint else "continuation_timeout"
            return False, "waiting_incomplete" if incomplete_hint else "waiting_continuation"

        # Short deterministic command with router confirmation
        if router_complete and stable_text and utterance_ms < 4000:
            if silence_ms >= self.short_command_silence_ms:
                return True, "short_command_complete"

        # Long utterance — use longer silence
        if utterance_ms > 8000:
            if silence_ms >= self.long_utterance_silence_ms:
                return True, "long_utterance_silence"
            return False, "waiting_long"

        # Default natural sentence silence (300-350ms)
        if silence_ms >= self.default_silence_ms:
            return True, "default_silence"

        return False, "waiting"
