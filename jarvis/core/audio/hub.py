"""AudioHub — single capture pipeline distributing frames to consumers.

Opens microphone ONCE and fans out AudioFrames to registered consumers
via bounded queues. Avoids device conflicts, duplicate resampling, and
unnecessary copies.
"""
from __future__ import annotations

import asyncio
import logging
from time import perf_counter_ns
from typing import Callable

from jarvis.core.audio.frame import AudioFrame, CANONICAL_SAMPLE_RATE
from jarvis.core.audio.ring_buffer import RingBuffer
from jarvis.core.audio.source import AudioSource, MicSource

logger = logging.getLogger("jarvis.audio.hub")


class AudioConsumer:
    """A registered consumer with its own bounded queue."""

    def __init__(self, name: str, queue_size: int = 100):
        self.name = name
        self.queue: asyncio.Queue[AudioFrame] = asyncio.Queue(maxsize=queue_size)
        self.dropped = 0
        self.total = 0

    def put(self, frame: AudioFrame) -> None:
        try:
            self.queue.put_nowait(frame)
            self.total += 1
        except asyncio.QueueFull:
            self.dropped += 1


class AudioHub:
    """Single audio capture → fan-out to multiple consumers.

    Consumers register before start and receive frames via bounded queues.
    The hub also maintains a ring buffer for pre-roll access.
    """

    def __init__(
        self,
        source: AudioSource | None = None,
        ring_buffer_ms: int = 2000,
        sample_rate: int = CANONICAL_SAMPLE_RATE,
    ):
        self.source = source or MicSource()
        self.ring = RingBuffer(duration_ms=ring_buffer_ms, sample_rate=sample_rate)
        self._consumers: list[AudioConsumer] = []
        self._running = False
        self._task: asyncio.Task | None = None
        self.total_frames = 0
        self.total_dropped = 0

    def register(self, name: str, queue_size: int = 100) -> AudioConsumer:
        """Register a consumer before start. Returns consumer handle."""
        consumer = AudioConsumer(name, queue_size)
        self._consumers.append(consumer)
        logger.debug("Registered audio consumer: %s (queue=%d)", name, queue_size)
        return consumer

    async def start(self) -> None:
        """Start audio capture and distribution."""
        await self.source.start()
        self._running = True
        self._task = asyncio.create_task(self._distribute())
        logger.info("AudioHub started with %d consumers", len(self._consumers))

    async def _distribute(self) -> None:
        """Main distribution loop — reads from source, fans out to consumers."""
        try:
            async for frame in self.source.frames():
                if not self._running:
                    break
                self.total_frames += 1

                # Always write to ring buffer
                self.ring.write(frame)

                # Fan out to all consumers
                for consumer in self._consumers:
                    consumer.put(frame)

        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("AudioHub distribution error")

    async def stop(self) -> None:
        """Stop audio capture and distribution."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.source.stop()

        # Compute total drops
        self.total_dropped = sum(c.dropped for c in self._consumers)
        logger.info(
            "AudioHub stopped: total_frames=%d, total_dropped=%d",
            self.total_frames, self.total_dropped,
        )

    @property
    def dropped_frames(self) -> int:
        """Total dropped frames across all consumers."""
        return sum(c.dropped for c in self._consumers)

    @property
    def metrics(self) -> dict:
        """Current pipeline metrics."""
        return {
            "total_frames": self.total_frames,
            "total_dropped": self.total_dropped,
            "ring_available_ms": self.ring.available_ms,
            "consumers": {
                c.name: {"total": c.total, "dropped": c.dropped, "queue_depth": c.queue.qsize()}
                for c in self._consumers
            },
        }
