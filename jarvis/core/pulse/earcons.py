from __future__ import annotations

import math
import struct
from enum import StrEnum
from typing import Dict


class EarconType(StrEnum):
    COMMAND_ACCEPTED = "COMMAND_ACCEPTED"       # Soft click (1200Hz, 20ms)
    LISTENING = "LISTENING"                     # Rising tone (440Hz -> 880Hz, 60ms)
    PROCESSING = "PROCESSING"                   # Subtle pulse (300Hz, 40ms)
    SUCCESS = "SUCCESS"                         # Chime chord (523Hz + 659Hz, 70ms)
    CONFIRMATION_NEEDED = "CONFIRMATION_NEEDED" # Question inflection (440Hz -> 660Hz, 80ms)
    FAILED_UNCERTAIN = "FAILED_UNCERTAIN"       # Low alert tone (220Hz downward, 90ms)


class EarconManager:
    """In-memory synthesizer and manager for distinct local audio earcons.
    Generates 16-bit PCM waveforms at 22,050 Hz directly into RAM at startup.
    Zero disk I/O, sub-millisecond retrieval.
    """

    def __init__(self, sample_rate: int = 22050) -> None:
        self.sample_rate = sample_rate
        self._cache: Dict[EarconType, bytes] = {}
        self._generate_all()

    def _generate_all(self) -> None:
        self._cache[EarconType.COMMAND_ACCEPTED] = self._make_click()
        self._cache[EarconType.LISTENING] = self._make_rising_tone()
        self._cache[EarconType.PROCESSING] = self._make_pulse()
        self._cache[EarconType.SUCCESS] = self._make_success_chord()
        self._cache[EarconType.CONFIRMATION_NEEDED] = self._make_question_tone()
        self._cache[EarconType.FAILED_UNCERTAIN] = self._make_alert_tone()

    def get_earcon(self, earcon_type: EarconType) -> bytes:
        """O(1) in-memory retrieval of pre-synthesized PCM bytes."""
        return self._cache.get(earcon_type, b"")

    def _make_click(self) -> bytes:
        # 20ms soft click at 1200Hz with fast exponential decay
        duration_s = 0.020
        freq = 1200.0
        n_samples = int(self.sample_rate * duration_s)
        samples = []
        for i in range(n_samples):
            t = i / self.sample_rate
            decay = math.exp(-i / (n_samples * 0.2))
            val = math.sin(2.0 * math.pi * freq * t) * decay * 0.5
            samples.append(int(val * 32767))
        return struct.pack(f"<{len(samples)}h", *samples)

    def _make_rising_tone(self) -> bytes:
        # 60ms chirp from 440Hz to 880Hz
        duration_s = 0.060
        f_start = 440.0
        f_end = 880.0
        n_samples = int(self.sample_rate * duration_s)
        samples = []
        for i in range(n_samples):
            t = i / self.sample_rate
            frac = i / n_samples
            freq = f_start + (f_end - f_start) * frac
            envelope = math.sin(math.pi * frac)
            val = math.sin(2.0 * math.pi * freq * t) * envelope * 0.4
            samples.append(int(val * 32767))
        return struct.pack(f"<{len(samples)}h", *samples)

    def _make_pulse(self) -> bytes:
        # 40ms warm pulse at 300Hz
        duration_s = 0.040
        freq = 300.0
        n_samples = int(self.sample_rate * duration_s)
        samples = []
        for i in range(n_samples):
            t = i / self.sample_rate
            envelope = math.sin(math.pi * (i / n_samples))
            val = math.sin(2.0 * math.pi * freq * t) * envelope * 0.35
            samples.append(int(val * 32767))
        return struct.pack(f"<{len(samples)}h", *samples)

    def _make_success_chord(self) -> bytes:
        # 70ms harmonious dyad: C5 (523.25 Hz) + E5 (659.25 Hz)
        duration_s = 0.070
        f1, f2 = 523.25, 659.25
        n_samples = int(self.sample_rate * duration_s)
        samples = []
        for i in range(n_samples):
            t = i / self.sample_rate
            envelope = math.sin(math.pi * (i / n_samples)) ** 0.8
            val = (0.5 * math.sin(2.0 * math.pi * f1 * t) + 0.5 * math.sin(2.0 * math.pi * f2 * t)) * envelope * 0.45
            samples.append(int(val * 32767))
        return struct.pack(f"<{len(samples)}h", *samples)

    def _make_question_tone(self) -> bytes:
        # 80ms rising question inflection from 440Hz to 660Hz
        duration_s = 0.080
        f_start, f_end = 440.0, 660.0
        n_samples = int(self.sample_rate * duration_s)
        samples = []
        for i in range(n_samples):
            t = i / self.sample_rate
            frac = i / n_samples
            freq = f_start + (f_end - f_start) * (frac ** 1.5)
            envelope = math.sin(math.pi * frac)
            val = math.sin(2.0 * math.pi * freq * t) * envelope * 0.4
            samples.append(int(val * 32767))
        return struct.pack(f"<{len(samples)}h", *samples)

    def _make_alert_tone(self) -> bytes:
        # 90ms downward warning inflection from 280Hz to 200Hz
        duration_s = 0.090
        f_start, f_end = 280.0, 200.0
        n_samples = int(self.sample_rate * duration_s)
        samples = []
        for i in range(n_samples):
            t = i / self.sample_rate
            frac = i / n_samples
            freq = f_start + (f_end - f_start) * frac
            envelope = math.sin(math.pi * frac)
            val = math.sin(2.0 * math.pi * freq * t) * envelope * 0.45
            samples.append(int(val * 32767))
        return struct.pack(f"<{len(samples)}h", *samples)
