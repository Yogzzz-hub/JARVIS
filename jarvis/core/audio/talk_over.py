"""Hear the owner while JARVIS is talking, without mistaking JARVIS's own voice for them.

A microphone near the speakers hears JARVIS too. The detector learns how loud JARVIS's voice comes back into the
microphone (the echo coupling: microphone level / output level while only JARVIS is talking) and only reports
talk-over when the microphone is clearly louder than that echo *and* the voice detector hears speech, for long
enough to be a word rather than a click. In the gaps between sentences (no output) any clear speech counts.

With headphones the echo coupling learns to almost zero, so even quiet speech interrupts at once.
"""
from __future__ import annotations

import math
from array import array

SENSITIVITY = {"low": 4.5, "normal": 3.0, "high": 2.0}


def rms(pcm: bytes) -> float:
    if not pcm:
        return 0.0
    samples = array("h")
    samples.frombytes(pcm[: len(pcm) - (len(pcm) % 2)])
    if not samples:
        return 0.0
    return math.sqrt(sum(s * s for s in samples) / len(samples))


class TalkOverDetector:
    def __init__(self, sensitivity: str = "normal", min_speech_ms: float = 260.0, warmup_ms: float = 450.0,
                 min_level: float = 450.0) -> None:
        self.ratio = SENSITIVITY.get(sensitivity, 3.0)
        self.min_speech_ms = min_speech_ms
        self.warmup_ms = warmup_ms
        self.min_level = min_level
        self.coupling = 0.6       # conservative until learned: assume the room echoes strongly
        self.noise_floor = 150.0  # microphone level with nobody talking
        self._speaking_ms = 0.0   # how long this stretch of JARVIS speech has been heard
        self._voiced_ms = 0.0     # consecutive talk-over evidence
        self._misses = 0
        self.triggers = 0

    def reset(self) -> None:
        """A new stretch of JARVIS speech: learning continues, evidence starts over."""
        self._speaking_ms = 0.0
        self._voiced_ms = 0.0
        self._misses = 0

    def observe_silence(self, mic_level: float) -> None:
        """Microphone level while JARVIS is silent and nobody is talking (keeps the noise floor current)."""
        self.noise_floor = 0.95 * self.noise_floor + 0.05 * max(20.0, mic_level)

    def feed(self, mic_level: float, out_level: float, speech: bool, frame_ms: float) -> bool:
        """One microphone frame while JARVIS is speaking. True = the owner is talking over JARVIS."""
        self._speaking_ms += frame_ms
        predicted_echo = self.coupling * out_level
        threshold = max(self.ratio * predicted_echo, 2.5 * self.noise_floor, self.min_level)
        loud = mic_level > threshold
        if out_level > 300 and not loud:
            # JARVIS alone: learn how much of its voice reaches the microphone
            observed = mic_level / out_level
            self.coupling = min(2.0, max(0.005, 0.9 * self.coupling + 0.1 * observed))
        if self._speaking_ms < self.warmup_ms:
            return False  # the first moments of playback only teach the echo level
        if speech and loud:
            self._voiced_ms += frame_ms
            self._misses = 0
        else:
            self._misses += 1
            if self._misses > 2:
                self._voiced_ms = 0.0
        if self._voiced_ms >= self.min_speech_ms:
            self._voiced_ms = 0.0
            self.triggers += 1
            return True
        return False
