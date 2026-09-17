import asyncio
import json
import logging
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
import queue
from datetime import datetime, timezone

class DroppingQueueHandler(QueueHandler):
    dropped = 0
    def enqueue(self, record):
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            self.dropped += 1

class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname, "request_id": getattr(record, "request_id", None),
            "component": record.name, "event": getattr(record, "event", record.msg),
            "duration_ms": getattr(record, "duration_ms", None), "message": record.getMessage(),
        })

class LogQueue:
    def __init__(self, path, size=4096):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.queue = queue.Queue(size)
        self.handler = DroppingQueueHandler(self.queue)
        self.file = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        self.file.setFormatter(JSONFormatter())
        self.logger = logging.getLogger("jarvis")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        self.logger.addHandler(self.handler)
        self.listener = QueueListener(self.queue, self.file)
        self.listener.start()

    async def close(self):
        self.logger.removeHandler(self.handler)
        def finish():
            self.queue.join()
            self.listener.stop()
            self.file.close()
        await asyncio.to_thread(finish)
