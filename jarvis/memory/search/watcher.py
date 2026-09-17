import asyncio
from collections import defaultdict
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Callable
from jarvis.config import SearchConfig
from jarvis.memory.search.cache import SearchHotCache
from jarvis.memory.search.tokenizer import path_tokens_string

class FileWatcher:
    """Monitors filesystem changes with event debouncing and incremental index synchronization."""
    def __init__(
        self,
        db_path: Path | str,
        roots: list[Path],
        cache: SearchHotCache | None = None,
        config: SearchConfig | None = None,
        debounce_seconds: float = 0.5,
    ):
        self.db_path = str(db_path)
        self.roots = [r for r in roots if r.exists() and r.is_dir()]
        self.cache = cache
        self.config = config or SearchConfig()
        self.debounce_seconds = debounce_seconds
        self.observer = None
        self._pending_events: dict[str, str] = {}  # path -> event_type
        self._event_timestamps: dict[str, float] = {}
        self._lock = threading.Lock()
        self.is_running = False
        self._flush_thread = None

    def _get_connection(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        con.execute("PRAGMA busy_timeout=5000")
        return con

    def start(self):
        """Starts the watchdog observer and the debouncing background flusher."""
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer

            class EventHandler(FileSystemEventHandler):
                def __init__(self, watcher: "FileWatcher"):
                    self.watcher = watcher

                def on_created(self, event):
                    self.watcher.queue_event(event.src_path, "created")

                def on_modified(self, event):
                    self.watcher.queue_event(event.src_path, "modified")

                def on_deleted(self, event):
                    self.watcher.queue_event(event.src_path, "deleted")

                def on_moved(self, event):
                    self.watcher.queue_event(event.src_path, "deleted")
                    self.watcher.queue_event(event.dest_path, "created")

            self.observer = Observer()
            handler = EventHandler(self)
            for root in self.roots:
                self.observer.schedule(handler, str(root), recursive=True)

            self.observer.start()
            self.is_running = True

            self._flush_thread = threading.Thread(target=self._debounce_loop, name="jarvis-watcher-debounce", daemon=True)
            self._flush_thread.start()
        except Exception:
            # Graceful fallback: Watcher disabled if watchdog fails
            self.is_running = False

    def queue_event(self, path_str: str, event_type: str):
        with self._lock:
            self._pending_events[path_str] = event_type
            self._event_timestamps[path_str] = time.time()

    def _debounce_loop(self):
        while self.is_running:
            time.sleep(0.25)
            now = time.time()
            to_process = []
            with self._lock:
                for path_str, ts in list(self._event_timestamps.items()):
                    if now - ts >= self.debounce_seconds:
                        event_type = self._pending_events.pop(path_str, "modified")
                        self._event_timestamps.pop(path_str, None)
                        to_process.append((path_str, event_type))

            if to_process:
                self._apply_events(to_process)
                if self.cache:
                    self.cache.invalidate()

    def _apply_events(self, events: list[tuple[str, str]]):
        now_ns = time.time_ns()
        with self._get_connection() as con:
            cur = con.cursor()
            for path_str, event_type in events:
                p = Path(path_str)
                path_norm = path_str.lower()
                if event_type == "deleted" or not p.exists():
                    cur.execute("SELECT id FROM files WHERE path = ?", (path_str,))
                    row = cur.fetchone()
                    if row:
                        fid = row[0]
                        cur.execute("UPDATE files SET is_available = 0 WHERE id = ?", (fid,))
                        cur.execute("DELETE FROM files_fts WHERE file_id = ?", (fid,))
                elif event_type in ("created", "modified"):
                    try:
                        stat = p.stat()
                        is_dir = p.is_dir()
                        name = p.name
                        name_norm = name.lower()
                        stem = p.stem.lower()
                        ext = p.suffix.lower() if not is_dir else "[directory]"
                        parent_str = str(p.parent)

                        cur.execute(
                            """
                            INSERT INTO files (
                                path, path_norm, parent_path, name, name_norm, stem, extension,
                                size_bytes, created_ns, modified_ns, indexed_ns, last_seen_ns,
                                is_directory, is_hidden, is_available, content_status
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'PENDING')
                            ON CONFLICT(path) DO UPDATE SET
                                name = excluded.name,
                                name_norm = excluded.name_norm,
                                stem = excluded.stem,
                                extension = excluded.extension,
                                size_bytes = excluded.size_bytes,
                                modified_ns = excluded.modified_ns,
                                last_seen_ns = excluded.last_seen_ns,
                                is_available = 1,
                                content_status = 'PENDING'
                            """,
                            (
                                path_str, path_norm, parent_str, name, name_norm, stem, ext,
                                stat.st_size if not is_dir else 0,
                                int(stat.st_ctime * 1e9), int(stat.st_mtime * 1e9),
                                now_ns, now_ns, 1 if is_dir else 0, 1 if name.startswith(".") else 0,
                            ),
                        )

                        cur.execute("SELECT id FROM files WHERE path = ?", (path_str,))
                        row = cur.fetchone()
                        if row:
                            fid = row[0]
                            ptokens = path_tokens_string(path_str)
                            cur.execute("DELETE FROM files_fts WHERE file_id = ?", (fid,))
                            cur.execute(
                                "INSERT INTO files_fts(file_id, name, stem, path_tokens, content) VALUES (?, ?, ?, ?, '')",
                                (fid, name, stem, ptokens),
                            )
                    except (PermissionError, OSError):
                        continue
            con.commit()

    def stop(self):
        self.is_running = False
        if self.observer:
            try:
                self.observer.stop()
                self.observer.join(timeout=2.0)
            except Exception:
                pass
