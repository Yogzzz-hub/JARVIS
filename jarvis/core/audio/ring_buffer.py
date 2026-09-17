"""Fixed-size circular audio ring buffer for JARVIS EDGE voice pipeline.

Maintains a rolling audio window (default: 2 seconds) so wake-word
detectors can retrieve pre-roll audio around the trigger point.
"""
from __future__ import annotations

import threading
from time import perf_counter_ns

import numpy as np

from jarvis.core.audio.frame import AudioFrame, CANONICAL_SAMPLE_RATE, CANONICAL_CHANNELS


class RingBuffer:
    """Thread-safe fixed-size circular audio buffer.

    Stores PCM16 samples in a numpy ring. No unbounded accumulation.
    """

    def __init__(self, duration_ms: int = 2000, sample_rate: int = CANONICAL_SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.capacity = int(sample_rate * duration_ms / 1000)
        self._buffer = np.zeros(self.capacity, dtype=np.int16)
        self._write_pos = 0
        self._total_written = 0
        self._lock = threading.Lock()

    def write(self, frame: AudioFrame) -> None:
        """Write audio frame into ring buffer."""
        samples = np.frombuffer(frame.pcm, dtype=np.int16)
        n = len(samples)

        with self._lock:
            if n >= self.capacity:
                # Frame larger than buffer — keep only tail
                self._buffer[:] = samples[-self.capacity:]
                self._write_pos = 0
                self._total_written += n
                return

            end = self._write_pos + n
            if end <= self.capacity:
                self._buffer[self._write_pos:end] = samples
            else:
                first = self.capacity - self._write_pos
                self._buffer[self._write_pos:] = samples[:first]
                self._buffer[:n - first] = samples[first:]
            self._write_pos = end % self.capacity
            self._total_written += n

    def read_last_ms(self, duration_ms: int) -> bytes:
        """Read the last N milliseconds of audio as PCM16 bytes."""
        n_samples = min(int(self.sample_rate * duration_ms / 1000), self.capacity)

        with self._lock:
            available = min(self._total_written, self.capacity)
            n_samples = min(n_samples, available)

            if n_samples == 0:
                return b""

            start = (self._write_pos - n_samples) % self.capacity
            if start < self._write_pos:
                result = self._buffer[start:self._write_pos].copy()
            else:
                result = np.concatenate([
                    self._buffer[start:],
                    self._buffer[:self._write_pos],
                ])

        return result[:n_samples].tobytes()

    def read_preroll(self, trigger_ns: int, preroll_ms: int = 500, postroll_ms: int = 0) -> bytes:
        """Read audio around a trigger point.

        Returns preroll_ms of audio before the current write position.
        Used to capture command audio that started before wake word fired.
        """
        return self.read_last_ms(preroll_ms + postroll_ms)

    @property
    def available_ms(self) -> float:
        """How many milliseconds of audio are currently stored."""
        with self._lock:
            available = min(self._total_written, self.capacity)
        return (available / self.sample_rate) * 1000.0

    @property
    def total_written(self) -> int:
        """Total samples ever written (for overflow detection)."""
        return self._total_written

    def clear(self) -> None:
        """Reset the ring buffer."""
        with self._lock:
            self._buffer[:] = 0
            self._write_pos = 0
            self._total_written = 0
