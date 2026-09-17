import asyncio
import json
import logging
import queue
import sqlite3
import threading
from pathlib import Path
from jarvis.config import ROOT, Database

TABLES = frozenset({"requests", "task_events", "tool_runs", "metrics"})

class PersistenceWriter:
    def __init__(self, path: Path, size=4096, config: Database | None = None):
        self.path = path
        self.queue = queue.Queue(size)
        self.config = config or Database()
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._run, name="jarvis-sqlite", daemon=True)
        self.error: str | None = None
        self.dropped = 0
        self.written = 0
        self.batches = 0
        self.max_batch = 0
        self.pragmas = {}
        self.closed = False

    async def start(self):
        self.thread.start()
        await asyncio.to_thread(self.ready.wait)
        if self.error:
            raise RuntimeError(self.error)

    def enqueue(self, table: str, request_id: str, payload: dict) -> bool:
        if table not in TABLES:
            raise ValueError("unknown telemetry table")
        if self.closed or self.error:
            self.dropped += 1
            return False
        try:
            self.queue.put_nowait((table, request_id, payload))
            return True
        except queue.Full:
            self.dropped += 1
            return False

    def _run(self):
        connection = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path)
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute(f"PRAGMA busy_timeout={self.config.busy_timeout_ms}")
            connection.execute("PRAGMA foreign_keys=ON")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            migrations = sorted((ROOT / "db/migrations").glob("*.sql"))
            if version > len(migrations):
                raise RuntimeError("database is newer than this service")
            for number, migration in enumerate(migrations, 1):
                if number > version:
                    connection.executescript("BEGIN;\n" + migration.read_text() + f"\nPRAGMA user_version={number};\nCOMMIT;")
            self.pragmas = {key: connection.execute(f"PRAGMA {key}").fetchone()[0]
                            for key in ("journal_mode", "synchronous", "busy_timeout", "foreign_keys", "user_version")}
            self.ready.set()
            stop = False
            while not stop:
                item = self.queue.get()  # blocks with zero idle polling
                batch = []
                if item is None:
                    self.queue.task_done()
                    break
                batch.append(item)
                # A short worker-only coalescing window never delays commands.
                import time
                deadline = time.monotonic() + 0.005
                while len(batch) < 256:
                    try:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            break
                        item = self.queue.get(timeout=remaining)
                    except queue.Empty:
                        break
                    if item is None:
                        self.queue.task_done()
                        stop = True
                        break
                    batch.append(item)
                try:
                    with connection:
                        for table, request_id, payload in batch:
                            connection.execute(f"INSERT INTO {table}(request_id,payload) VALUES (?,?)",
                                               (request_id, json.dumps(payload, separators=(",", ":"))))
                    self.written += len(batch)
                    self.batches += 1
                    self.max_batch = max(self.max_batch, len(batch))
                finally:
                    for _ in batch:
                        self.queue.task_done()
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception as exc:
            self.error = repr(exc)
            logging.getLogger("jarvis.persistence").exception("persistence worker failed")
            self.ready.set()
        finally:
            if connection is not None:
                connection.close()

    async def close(self):
        self.closed = True
        def finish():
            while self.thread.is_alive():
                try:
                    self.queue.put(None, timeout=0.1)
                    break
                except queue.Full:
                    continue
            self.thread.join(timeout=10)
            if self.thread.is_alive():
                raise RuntimeError("persistence shutdown timed out")
            if self.error:
                raise RuntimeError(self.error)
        await asyncio.to_thread(finish)
