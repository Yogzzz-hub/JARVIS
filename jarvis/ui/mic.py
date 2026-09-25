"""Live continuous microphone monitor and wake detector for JARVIS Desktop UI."""
from __future__ import annotations

import collections
import logging
import time
from typing import Callable

import numpy as np
import PySide6.QtMultimedia as mm
from PySide6.QtCore import QObject, QTimer, Signal, Slot

logger = logging.getLogger("jarvis.ui.mic")


class LiveMicMonitor(QObject):
    """Continuously monitors microphone input using native Qt Multimedia."""

    levelsUpdated = Signal(list)       # list of 24 normalized amplitudes [0.0..1.0]
    voiceActivityDetected = Signal()   # Triggered on voice threshold (speech/wake)

    def __init__(self, energy_threshold: float = 0.015, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.energy_threshold = energy_threshold
        self._source: mm.QAudioSource | None = None
        self._io_dev = None
        self._timer = QTimer(self)
        self._timer.setInterval(33)  # ~30 FPS
        self._timer.timeout.connect(self._process_audio)
        self._history = collections.deque([0.0] * 24, maxlen=24)
        self._last_trigger_time = 0.0
        self._speech_frames = 0

    def start(self) -> bool:
        """Start listening continuously to default microphone."""
        try:
            dev = mm.QMediaDevices.defaultAudioInput()
            if dev.isNull():
                logger.warning("No default audio input device found.")
                return False

            fmt = dev.preferredFormat()
            self._source = mm.QAudioSource(dev, fmt, self)
            self._io_dev = self._source.start()
            self._timer.start()
            logger.info("Continuous live microphone monitor started on: %s", dev.description())
            return True
        except Exception as exc:
            logger.error("Failed to start microphone monitor: %s", exc)
            return False

    def stop(self) -> None:
        """Stop microphone monitor."""
        if self._timer.isActive():
            self._timer.stop()
        if self._source:
            self._source.stop()
            self._source = None
            self._io_dev = None

    @Slot()
    def _process_audio(self) -> None:
        if not self._io_dev:
            return

        data = self._io_dev.readAll()
        raw_bytes = data.data()
        if len(raw_bytes) < 32:
            return

        try:
            samples = np.frombuffer(raw_bytes, dtype=np.float32)
            if len(samples) == 0:
                return

            rms = float(np.sqrt(np.mean(samples**2)))
            # Normalize to 0..1 scale
            normalized = min(1.0, rms * 15.0)

            self._history.append(normalized)
            self.levelsUpdated.emit(list(self._history))

            # Voice activity detection logic
            now = time.time()
            if rms > self.energy_threshold:
                self._speech_frames += 1
                # If voice is sustained for > 3 frames (~100ms) and not on cooldown (2.5s)
                if self._speech_frames >= 3 and (now - self._last_trigger_time > 2.5):
                    self._last_trigger_time = now
                    self._speech_frames = 0
                    logger.info("Live voice activity / wake detection trigger (RMS=%.4f)", rms)
                    self.voiceActivityDetected.emit()
            else:
                self._speech_frames = max(0, self._speech_frames - 1)

        except Exception as exc:
            logger.debug("Error processing audio frame: %s", exc)
