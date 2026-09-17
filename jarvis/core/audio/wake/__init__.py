"""Wake word engine abstractions and implementations for JARVIS EDGE.

Supports OpenWakeWord (ONNX) and push-to-talk hotkey.
"""
from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from time import perf_counter_ns
from typing import Protocol, runtime_checkable

import numpy as np

from jarvis.core.audio.frame import AudioFrame, OWW_CHUNK_SAMPLES

logger = logging.getLogger("jarvis.audio.wake")


@dataclass(slots=True)
class WakeDetection:
    """Wake word detection event."""
    detected: bool
    score: float
    model: str
    timestamp_ns: int
    cooldown_active: bool = False


@runtime_checkable
class WakeWordEngine(Protocol):
    """Protocol for wake word detection engines."""

    def feed(self, frame: AudioFrame) -> WakeDetection | None: ...
    def reset(self) -> None: ...
    def close(self) -> None: ...


class OpenWakeWordEngine:
    """OpenWakeWord wake word detector using ONNX runtime.

    Runs on CPU only — no GPU waste for wake word detection.
    Requires 16-bit 16kHz PCM, 80ms chunks (1280 samples).
    """

    def __init__(
        self,
        model_path: str | None = None,
        threshold: float = 0.5,
        cooldown_ms: int = 1500,
        inference_framework: str = "onnx",
    ):
        self.threshold = threshold
        self.cooldown_ms = cooldown_ms
        self.inference_framework = inference_framework
        self._model_path = model_path
        self._model = None
        self._last_trigger_ns: int = 0
        self._buffer = np.array([], dtype=np.int16)
        self._model_name = "unknown"
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        try:
            from openwakeword.model import Model
            kwargs = {"inference_framework": self.inference_framework}
            if self._model_path:
                kwargs["wakeword_models"] = [self._model_path]
            self._model = Model(**kwargs)
            if self._model.models:
                self._model_name = list(self._model.models.keys())[0]
            self._loaded = True
            logger.info("OpenWakeWord loaded: model=%s, threshold=%.2f", self._model_name, self.threshold)
        except Exception as exc:
            logger.warning("OpenWakeWord load failed: %s", exc)
            self._loaded = False

    def feed(self, frame: AudioFrame) -> WakeDetection | None:
        """Feed audio frame, return WakeDetection if triggered."""
        self._ensure_loaded()
        if not self._loaded or self._model is None:
            return None

        # Accumulate samples until we have enough for OWW (1280 samples)
        samples = np.frombuffer(frame.pcm, dtype=np.int16)
        self._buffer = np.concatenate([self._buffer, samples])

        if len(self._buffer) < OWW_CHUNK_SAMPLES:
            return None

        # Process in 1280-sample chunks
        while len(self._buffer) >= OWW_CHUNK_SAMPLES:
            chunk = self._buffer[:OWW_CHUNK_SAMPLES]
            self._buffer = self._buffer[OWW_CHUNK_SAMPLES:]

            prediction = self._model.predict(chunk)
            score = max(prediction.values()) if prediction else 0.0

            now = perf_counter_ns()

            # Check cooldown
            if self._last_trigger_ns > 0:
                elapsed_ms = (now - self._last_trigger_ns) / 1e6
                if elapsed_ms < self.cooldown_ms:
                    if score >= self.threshold:
                        return WakeDetection(
                            detected=False, score=score,
                            model=self._model_name,
                            timestamp_ns=now, cooldown_active=True,
                        )
                    continue

            if score >= self.threshold:
                self._last_trigger_ns = now
                logger.info("Wake word detected: score=%.3f, model=%s", score, self._model_name)
                return WakeDetection(
                    detected=True, score=score,
                    model=self._model_name,
                    timestamp_ns=now,
                )

        return None

    def reset(self) -> None:
        """Reset internal state for new session."""
        self._buffer = np.array([], dtype=np.int16)
        if self._model:
            self._model.reset()

    def close(self) -> None:
        """Release resources."""
        self._model = None
        self._loaded = False
        self._buffer = np.array([], dtype=np.int16)


class PushToTalkEngine:
    """Push-to-talk trigger via global hotkey.

    Bypasses wake word detection — useful for noisy environments,
    testing, privacy, or wake-word failure.
    """

    def __init__(self, hotkey: str = "ctrl+shift+j"):
        self.hotkey = hotkey
        self._triggered = False
        self._registered = False
        self._callback = None

    def start(self, callback=None):
        """Register global hotkey."""
        self._callback = callback
        try:
            import keyboard
            keyboard.add_hotkey(self.hotkey, self._on_press)
            self._registered = True
            logger.info("Push-to-talk registered: hotkey=%s", self.hotkey)
        except Exception as exc:
            logger.warning("Push-to-talk hotkey registration failed: %s", exc)

    def _on_press(self):
        self._triggered = True
        if self._callback:
            self._callback()

    def check(self) -> bool:
        """Check if hotkey was pressed (consumes the trigger)."""
        if self._triggered:
            self._triggered = False
            return True
        return False

    def stop(self):
        """Unregister hotkey."""
        if self._registered:
            try:
                import keyboard
                keyboard.remove_hotkey(self.hotkey)
            except Exception:
                pass
            self._registered = False
