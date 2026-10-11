"""Clap to wake JARVIS.

A clap is not loud, it is SHARP: silence, a near-instant rise to the peak, and a collapse inside about a tenth of
a second. Almost nothing else in a room does all three - a door, a cough, speech or music each fails at least one -
so the detector checks the shape, never loudness alone:

  1. quiet before:  the level a moment earlier was a small fraction of the peak (rejects rising speech),
  2. sharp attack:  the peak is far above the running noise floor and above an absolute minimum,
  3. fast decay:    the level falls below DECAY_TO x peak within DECAY_MS (rejects anything with a body to it).

An always-listening assistant cannot wake on a single strike (a dropped book is one), so by default it takes two
claps 0.15-0.9 s apart. Everything runs on the sample clock of the audio itself, so batched backlog and tests
behave exactly like live audio.
"""
from __future__ import annotations

import math
from array import array
from dataclasses import dataclass, field

FULL_SCALE = 32768.0

PEAK_OVER_FLOOR = 7.0     # how far above the running floor counts as a candidate transient
MIN_PEAK = 0.055          # ...and an absolute floor (fraction of full scale), so a silent room can't make a tap a clap
QUIET_BEFORE = 0.16       # the room must have been this quiet (relative to the peak) just before the strike
LOOKBACK_MS = 50          # how far back "just before" means
HISTORY_MS = 330
DECAY_TO = 0.35           # confirmed once the level has fallen this far below the peak...
DECAY_MS = 130            # ...within this long
GIVE_UP_MS = 260          # still loud by now: something sustained
COOLDOWN_MS = 250         # one strike is one event
WINDOW_MS = 10            # analysis hop


@dataclass
class ClapDiagnostics:
    claps: int = 0
    wakes: int = 0
    last_peak: float = 0.0
    rejected: str = ""
    floor: float = 0.0
    recent: list[float] = field(default_factory=list)


class ClapDetector:
    """Feed 16-bit mono PCM; ``feed`` returns True when the wake pattern (one or two claps) completes."""

    def __init__(self, sample_rate: int = 16000, claps_needed: int = 2, min_gap_ms: float = 150.0,
                 max_gap_ms: float = 900.0, wake_cooldown_ms: float = 1200.0) -> None:
        self.sample_rate = sample_rate
        self.window = max(1, sample_rate * WINDOW_MS // 1000)
        self.claps_needed = max(1, claps_needed)
        self.min_gap_ms, self.max_gap_ms = min_gap_ms, max_gap_ms
        self.wake_cooldown_ms = wake_cooldown_ms
        self.diag = ClapDiagnostics()
        self.reset()

    def reset(self) -> None:
        self._now_ms = 0.0
        self._pending = array("h")
        self._history: list[float] = []
        self._floor = 0.01
        self._candidate: tuple[float, float] | None = None     # (started_ms, peak)
        self._last_clap = -1e9
        self._last_wake = -1e9
        self._claps: list[float] = []

    # ------------------------------------------------------------------ public
    def feed(self, pcm: bytes) -> bool:
        samples = array("h")
        samples.frombytes(pcm[: len(pcm) - (len(pcm) % 2)])
        self._pending.extend(samples)
        woke = False
        while len(self._pending) >= self.window:
            chunk = self._pending[: self.window]
            del self._pending[: self.window]
            level = math.sqrt(sum(s * s for s in chunk) / len(chunk)) / FULL_SCALE
            self._now_ms += WINDOW_MS
            if self._step(level):
                woke = True
        return woke

    # ------------------------------------------------------------------ internals
    def _step(self, level: float) -> bool:
        now = self._now_ms
        self._history.append(level)
        if len(self._history) > HISTORY_MS // WINDOW_MS:
            self._history.pop(0)
        # The floor tracks the room - never while a candidate is in flight, or the clap raises its own bar.
        if self._candidate is None and level < self._floor * 3:
            self._floor = max(0.002, self._floor + (level - self._floor) * 0.05)
        self.diag.floor = self._floor

        if self._candidate is not None:
            started, peak = self._candidate
            if level < peak * DECAY_TO and now - started < DECAY_MS:
                self._candidate = None
                self._last_clap = now
                self.diag.claps += 1
                self.diag.rejected = ""
                return self._register_clap(now)
            if now - started > GIVE_UP_MS:
                self.diag.rejected = "too sustained to be a clap"
                self._candidate = None
            else:
                self._candidate = (started, max(peak, level))
            return False

        if now - self._last_clap < COOLDOWN_MS:
            return False
        if level < MIN_PEAK or level < self._floor * PEAK_OVER_FLOOR:
            return False
        back = LOOKBACK_MS // WINDOW_MS
        if len(self._history) <= back or self._history[-1 - back] > level * QUIET_BEFORE:
            self.diag.rejected = "no silence before it"
            return False
        self.diag.last_peak = level
        self._candidate = (now, level)
        return False

    def _register_clap(self, now: float) -> bool:
        if now - self._last_wake < self.wake_cooldown_ms:
            return False
        self._claps = [t for t in self._claps if now - t <= self.max_gap_ms * self.claps_needed] + [now]
        self.diag.recent = list(self._claps)
        if len(self._claps) < self.claps_needed:
            return False
        tail = self._claps[-self.claps_needed:]
        gaps = [b - a for a, b in zip(tail, tail[1:])]
        if all(self.min_gap_ms <= g <= self.max_gap_ms for g in gaps):
            self._claps = []
            self._last_wake = now
            self.diag.wakes += 1
            return True
        self._claps = self._claps[-1:]
        return False
