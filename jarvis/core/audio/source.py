"""Audio source abstractions for JARVIS EDGE voice pipeline.

Protocol and implementations for microphone, file, and synthetic audio sources.
All sources output canonical AudioFrame objects (16kHz, mono, PCM16).
"""
from __future__ import annotations

import asyncio
import logging
import math
import struct
import wave
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from pathlib import Path
from time import perf_counter_ns
from typing import Protocol, runtime_checkable

import numpy as np

from jarvis.core.audio.frame import (
    AudioFrame,
    CANONICAL_CHANNELS,
    CANONICAL_SAMPLE_RATE,
    CANONICAL_SAMPLES_PER_FRAME,
)

logger = logging.getLogger("jarvis.audio.source")


@runtime_checkable
class AudioSource(Protocol):
    """Protocol for audio input sources."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def frames(self) -> AsyncIterator[AudioFrame]: ...


class MicSource:
    """Microphone capture via sounddevice.

    Opens a single input stream and produces canonical AudioFrames.
    The callback does ONLY: copy samples, timestamp, enqueue.
    No database, no logging-to-disk, no STT, no model loading.
    """

    def __init__(
        self,
        device: int | str | None = None,
        sample_rate: int = CANONICAL_SAMPLE_RATE,
        frame_samples: int = CANONICAL_SAMPLES_PER_FRAME,
        queue_size: int = 200,
    ):
        self.device = device
        self.target_rate = sample_rate
        self.frame_samples = frame_samples
        self._queue: asyncio.Queue[AudioFrame] = asyncio.Queue(maxsize=queue_size)
        self._stream = None
        self._seq = 0
        self._running = False
        self.dropped_frames = 0
        self._native_rate: int | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    async def start(self) -> None:
        import sounddevice as sd

        self._loop = asyncio.get_running_loop()
        # Query device to get native sample rate
        dev_info = sd.query_devices(self.device, "input")
        self._native_rate = int(dev_info["default_samplerate"])
        actual_rate = self._native_rate

        # Calculate frame size for native rate
        native_frame_samples = int(self.frame_samples * actual_rate / self.target_rate)

        self._stream = sd.InputStream(
            device=self.device,
            samplerate=actual_rate,
            channels=CANONICAL_CHANNELS,
            dtype="int16",
            blocksize=native_frame_samples,
            callback=self._callback,
        )
        self._running = True
        self._stream.start()
        logger.info(
            "MicSource started: device=%s, native_rate=%d, target_rate=%d",
            self.device or "default", actual_rate, self.target_rate,
        )

    def _callback(self, indata, frames, time_info, status):
        """Audio device callback — minimal work only."""
        if not self._running:
            return
        ts = perf_counter_ns()
        self._seq += 1
        pcm_data = indata[:, 0].tobytes()  # mono channel, already int16

        # Resample if native rate differs from target
        if self._native_rate and self._native_rate != self.target_rate:
            pcm_data = self._resample_pcm16(pcm_data, self._native_rate, self.target_rate)

        sample_count = len(pcm_data) // 2  # PCM16 = 2 bytes per sample
        frame = AudioFrame(
            sequence_id=self._seq,
            timestamp_ns=ts,
            sample_rate=self.target_rate,
            channels=CANONICAL_CHANNELS,
            sample_count=sample_count,
            pcm=pcm_data,
            source="mic",
        )

        # Non-blocking enqueue — never block audio callback
        try:
            if self._loop and not self._loop.is_closed():
                self._loop.call_soon_threadsafe(self._try_put, frame)
            else:
                self.dropped_frames += 1
        except RuntimeError:
            self.dropped_frames += 1

    def _try_put(self, frame: AudioFrame):
        try:
            self._queue.put_nowait(frame)
        except asyncio.QueueFull:
            self.dropped_frames += 1

    @staticmethod
    def _resample_pcm16(pcm: bytes, from_rate: int, to_rate: int) -> bytes:
        """Efficient resampling using scipy."""
        from scipy.signal import resample_poly
        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        # Use GCD for efficient rational resampling
        gcd = math.gcd(from_rate, to_rate)
        up = to_rate // gcd
        down = from_rate // gcd
        resampled = resample_poly(samples, up, down).astype(np.int16)
        return resampled.tobytes()

    async def stop(self) -> None:
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        logger.info("MicSource stopped (dropped=%d)", self.dropped_frames)

    async def frames(self) -> AsyncIterator[AudioFrame]:
        while self._running:
            try:
                frame = await asyncio.wait_for(self._queue.get(), timeout=0.5)
                yield frame
            except asyncio.TimeoutError:
                continue


class FileAudioSource:
    """Read audio from a WAV file, producing canonical AudioFrames.

    Used for testing and benchmarking without a live microphone.
    """

    def __init__(
        self,
        path: Path | str,
        frame_samples: int = CANONICAL_SAMPLES_PER_FRAME,
    ):
        self.path = Path(path)
        self.frame_samples = frame_samples
        self._running = False
        self._seq = 0

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def frames(self) -> AsyncIterator[AudioFrame]:
        with wave.open(str(self.path), "rb") as wf:
            native_rate = wf.getframerate()
            n_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()

            while self._running:
                raw = wf.readframes(self.frame_samples)
                if not raw:
                    break

                # Convert to mono int16 if needed
                arr = np.frombuffer(raw, dtype=np.int16 if sample_width == 2 else np.uint8)
                if n_channels > 1:
                    arr = arr.reshape(-1, n_channels)[:, 0]  # take first channel
                if sample_width != 2:
                    arr = (arr.astype(np.float32) * 256).astype(np.int16)

                # Resample if needed
                if native_rate != CANONICAL_SAMPLE_RATE:
                    pcm_bytes = MicSource._resample_pcm16(
                        arr.tobytes(), native_rate, CANONICAL_SAMPLE_RATE
                    )
                else:
                    pcm_bytes = arr.tobytes()

                sample_count = len(pcm_bytes) // 2
                self._seq += 1
                yield AudioFrame(
                    sequence_id=self._seq,
                    timestamp_ns=perf_counter_ns(),
                    sample_rate=CANONICAL_SAMPLE_RATE,
                    channels=CANONICAL_CHANNELS,
                    sample_count=sample_count,
                    pcm=pcm_bytes,
                    source="file",
                )
                # Simulate real-time pacing
                await asyncio.sleep(sample_count / CANONICAL_SAMPLE_RATE)


class SyntheticAudioSource:
    """Generate synthetic audio frames for testing.

    Supports: silence, sine tone, white noise, impulse clicks.
    """

    def __init__(
        self,
        duration_s: float = 2.0,
        frame_samples: int = CANONICAL_SAMPLES_PER_FRAME,
        mode: str = "silence",  # silence, tone, noise, impulse
        frequency: float = 440.0,
        amplitude: float = 0.5,
    ):
        self.duration_s = duration_s
        self.frame_samples = frame_samples
        self.mode = mode
        self.frequency = frequency
        self.amplitude = amplitude
        self._running = False
        self._seq = 0

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def frames(self) -> AsyncIterator[AudioFrame]:
        total_samples = int(self.duration_s * CANONICAL_SAMPLE_RATE)
        offset = 0

        while self._running and offset < total_samples:
            n = min(self.frame_samples, total_samples - offset)
            t = np.arange(offset, offset + n) / CANONICAL_SAMPLE_RATE

            if self.mode == "silence":
                samples = np.zeros(n, dtype=np.float32)
            elif self.mode == "tone":
                samples = (self.amplitude * np.sin(2 * np.pi * self.frequency * t)).astype(np.float32)
            elif self.mode == "noise":
                samples = (self.amplitude * np.random.randn(n)).astype(np.float32)
            elif self.mode == "impulse":
                samples = np.zeros(n, dtype=np.float32)
                # Add click every 0.1s
                click_interval = int(0.1 * CANONICAL_SAMPLE_RATE)
                for i in range(n):
                    if (offset + i) % click_interval == 0:
                        samples[i] = self.amplitude
            else:
                samples = np.zeros(n, dtype=np.float32)

            pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
            self._seq += 1
            offset += n

            yield AudioFrame(
                sequence_id=self._seq,
                timestamp_ns=perf_counter_ns(),
                sample_rate=CANONICAL_SAMPLE_RATE,
                channels=CANONICAL_CHANNELS,
                sample_count=n,
                pcm=pcm,
                source="synthetic",
            )
            # No real-time pacing for synthetic — tests run fast


class NetworkAudioSource:
    """Placeholder for Phase 8 phone streaming.

    Will accept WebSocket audio streams from mobile clients.
    """

    async def start(self) -> None:
        raise NotImplementedError("NetworkAudioSource is a Phase 8 placeholder")

    async def stop(self) -> None:
        raise NotImplementedError("NetworkAudioSource is a Phase 8 placeholder")

    async def frames(self) -> AsyncIterator[AudioFrame]:
        raise NotImplementedError("NetworkAudioSource is a Phase 8 placeholder")
        yield  # pragma: no cover — makes this a generator
