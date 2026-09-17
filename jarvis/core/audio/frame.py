"""Audio frame contract for JARVIS EDGE voice pipeline.

All speech engines consume the canonical format:
  sample_rate = 16000, channels = 1, format = PCM16 signed little-endian.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from time import perf_counter_ns
from typing import Literal

# Canonical audio constants
CANONICAL_SAMPLE_RATE = 16000
CANONICAL_CHANNELS = 1
CANONICAL_FRAME_MS = 20  # 20ms base transport frame
CANONICAL_SAMPLES_PER_FRAME = CANONICAL_SAMPLE_RATE * CANONICAL_FRAME_MS // 1000  # 320
CANONICAL_BYTES_PER_FRAME = CANONICAL_SAMPLES_PER_FRAME * 2  # 640 bytes PCM16

# Silero VAD requires 512-sample chunks (32ms at 16kHz)
SILERO_CHUNK_SAMPLES = 512
SILERO_CHUNK_MS = 32

# OpenWakeWord requires 1280-sample chunks (80ms at 16kHz)
OWW_CHUNK_SAMPLES = 1280
OWW_CHUNK_MS = 80


@dataclass(slots=True)
class AudioFrame:
    """A single audio frame in the voice pipeline.

    Lightweight dataclass — no Pydantic, no disk I/O.
    timestamp_ns uses perf_counter_ns() for accurate latency measurement.
    """
    sequence_id: int
    timestamp_ns: int
    sample_rate: int
    channels: int
    sample_count: int
    pcm: bytes  # PCM16 signed little-endian
    source: str = "mic"

    @property
    def duration_ms(self) -> float:
        """Duration of this frame in milliseconds."""
        return (self.sample_count / self.sample_rate) * 1000.0

    @property
    def duration_s(self) -> float:
        """Duration of this frame in seconds."""
        return self.sample_count / self.sample_rate

    @property
    def is_canonical(self) -> bool:
        """Check if frame matches canonical format."""
        return (
            self.sample_rate == CANONICAL_SAMPLE_RATE
            and self.channels == CANONICAL_CHANNELS
            and len(self.pcm) == self.sample_count * 2  # 2 bytes per PCM16 sample
        )

    def to_float32(self) -> list[float]:
        """Convert PCM16 to float32 normalized [-1, 1] for model inference."""
        samples = struct.unpack(f"<{self.sample_count}h", self.pcm)
        return [s / 32768.0 for s in samples]

    @staticmethod
    def from_float32(
        samples: list[float] | tuple[float, ...],
        sequence_id: int = 0,
        sample_rate: int = CANONICAL_SAMPLE_RATE,
        source: str = "synthetic",
    ) -> AudioFrame:
        """Create an AudioFrame from float32 normalized samples."""
        pcm = struct.pack(
            f"<{len(samples)}h",
            *(max(-32768, min(32767, int(s * 32768))) for s in samples),
        )
        return AudioFrame(
            sequence_id=sequence_id,
            timestamp_ns=perf_counter_ns(),
            sample_rate=sample_rate,
            channels=CANONICAL_CHANNELS,
            sample_count=len(samples),
            pcm=pcm,
            source=source,
        )

    @staticmethod
    def silence(
        sample_count: int = CANONICAL_SAMPLES_PER_FRAME,
        sequence_id: int = 0,
        source: str = "synthetic",
    ) -> AudioFrame:
        """Create a silent AudioFrame."""
        return AudioFrame(
            sequence_id=sequence_id,
            timestamp_ns=perf_counter_ns(),
            sample_rate=CANONICAL_SAMPLE_RATE,
            channels=CANONICAL_CHANNELS,
            sample_count=sample_count,
            pcm=b"\x00" * (sample_count * 2),
            source=source,
        )
