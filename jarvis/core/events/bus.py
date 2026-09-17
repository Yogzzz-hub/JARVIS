import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

@dataclass(slots=True, frozen=True)
class Event:
    name: str
    request_id: str
    data: dict

class EventBus:
    """Each async subscriber owns a bounded mailbox and independent consumer."""
    def __init__(self, size=1024):
        self.size = size
        self.subscribers = []
        self.dropped = 0
        self.errors = 0
        self.closed = False

    def subscribe(self, callback: Callable[[Event], Awaitable[None]]):
        if self.closed:
            raise RuntimeError("event bus closed")
        queue = asyncio.Queue(self.size)
        worker = asyncio.create_task(self._consume(queue, callback))
        self.subscribers.append((queue, worker))

    async def _consume(self, queue, callback):
        while True:
            event = await queue.get()
            try:
                await callback(event)
            except Exception:
                self.errors += 1
                logging.getLogger("jarvis.events").exception("subscriber failed", extra={"request_id": event.request_id})
            finally:
                queue.task_done()

    def emit(self, name: str, request_id: str, **data):
        if self.closed:
            return
        event = Event(name, request_id, data)
        for queue, _ in self.subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                self.dropped += 1

    async def close(self, timeout=3.0):
        self.closed = True
        try:
            async with asyncio.timeout(timeout):
                await asyncio.gather(*(q.join() for q, _ in self.subscribers))
        except TimeoutError:
            self.dropped += sum(q.qsize() for q, _ in self.subscribers)
            logging.getLogger("jarvis.events").warning("subscriber drain timed out")
        for _, worker in self.subscribers:
            worker.cancel()
        await asyncio.gather(*(w for _, w in self.subscribers), return_exceptions=True)
