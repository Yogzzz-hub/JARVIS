import asyncio

class MetricsCollector:
    def __init__(self, writer, bus, size):
        self.queue = asyncio.Queue(size)
        self.writer, self.bus = writer, bus
        self.dropped = 0
        self.count = 0
        self.worker = asyncio.create_task(self._run())

    def record(self, request_id, values):
        try:
            self.queue.put_nowait((request_id, values))
        except asyncio.QueueFull:
            self.dropped += 1

    async def _run(self):
        while True:
            item = await self.queue.get()
            try:
                if item is None:
                    return
                request_id, values = item
                self.writer.enqueue("metrics", request_id, values)
                self.count += 1
                self.bus.emit("metrics.recorded", request_id)
            finally:
                self.queue.task_done()

    async def close(self):
        await self.queue.put(None)
        await self.worker
