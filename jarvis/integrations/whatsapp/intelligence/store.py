from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any


def content_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode()).hexdigest()


class IntelligenceStore:
    """Versioned additive tables beside the existing inbox. Never opens another message database."""
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        for version, filename in ((9, "009_whatsapp_intelligence.sql"), (10, "010_whatsapp_dispatch.sql")):
            with self.connection() as conn:
                table = conn.execute("SELECT name FROM sqlite_master WHERE name='wa_intelligence_versions'").fetchone()
                applied = table and conn.execute("SELECT 1 FROM wa_intelligence_versions WHERE version=?", (version,)).fetchone()
                if applied:
                    continue
                # sqlite backup includes committed WAL pages. Structural changes follow the snapshot.
                backup = self.db_path.with_name(self.db_path.stem + f".before_intelligence_{version:03}.db")
                if not backup.exists():
                    with sqlite3.connect(backup) as target:
                        conn.backup(target)
                sql = Path(__file__).resolve().parents[3] / "db/migrations/whatsapp_inbox" / filename
                conn.executescript("BEGIN IMMEDIATE;\n" + sql.read_text(encoding="utf-8")
                    + f"\nINSERT INTO wa_intelligence_versions VALUES({version}, strftime('%s','now'));\nCOMMIT;")

    def enqueue_dispatch(self, message):
        with self.connection() as conn:
            conn.execute("INSERT OR IGNORE INTO wa_dispatch_jobs(message_id,thread_id,payload,created_at) VALUES(?,?,?,?)",
                (message.message_id if message.state == "READY" else "pending:" + message.message_id,
                 message.chat_id, message.model_dump_json(), time.time()))

    def claim_dispatch(self):
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT j.* FROM wa_dispatch_jobs j WHERE status='PENDING' AND NOT EXISTS "
                "(SELECT 1 FROM wa_dispatch_jobs active WHERE active.thread_id=j.thread_id AND active.status='STARTED') "
                "ORDER BY created_at,message_id LIMIT 1").fetchone()
            if not row:
                return None
            conn.execute("UPDATE wa_dispatch_jobs SET status='STARTED' WHERE message_id=?", (row["message_id"],))
            return dict(row)

    def finish_dispatch(self, message_id, error=""):
        with self.connection() as conn:
            conn.execute("UPDATE wa_dispatch_jobs SET status=?,error=? WHERE message_id=?",
                ("UNCERTAIN" if error else "DONE", error[:200], message_id))

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def metric(self, name: str, value: float = 1):
        with self.connection() as conn:
            conn.execute("INSERT INTO wa_intelligence_metrics VALUES(?,?) ON CONFLICT(name) DO UPDATE SET value=value+excluded.value", (name, value))

    def put(self, kind: str, resource: Any, message_id: str = ""):
        data = resource.model_dump() if hasattr(resource, "model_dump") else resource
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT thread_id,kind FROM wa_resources WHERE id=?", (data["id"],)).fetchone()
            if existing and (existing[0] != data["thread_id"] or existing[1] != kind):
                raise ValueError("Resource identity cannot change thread or type")
            conn.execute("INSERT INTO wa_resources VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at",
                (data["id"], data["thread_id"], kind, message_id, json.dumps(data, ensure_ascii=False), time.time()))

    def get(self, resource_id: str, thread_id: str | None = None):
        with self.connection() as conn:
            row = conn.execute("SELECT payload FROM wa_resources WHERE id=?" + (" AND thread_id=?" if thread_id else ""),
                (resource_id, thread_id) if thread_id else (resource_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def resources(self, thread_id: str, kind: str, limit: int = 50, status: str | None = None):
        with self.connection() as conn:
            rows = conn.execute("SELECT payload FROM wa_resources WHERE thread_id=? AND kind=?" +
                (" AND json_extract(payload,'$.status')=?" if status else "") + " ORDER BY updated_at DESC LIMIT ?",
                (thread_id, kind, status, limit) if status else (thread_id, kind, limit)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def version(self, thread_id: str) -> int:
        with self.connection() as conn:
            row = conn.execute("SELECT version FROM wa_thread_state WHERE thread_id=?", (thread_id,)).fetchone()
        return row[0] if row else 0

    def generated(self, thread_id: str, text: str, request_id: str, message_id: str = ""):
        with self.connection() as conn:
            conn.execute("INSERT OR REPLACE INTO wa_generated_messages VALUES(?,?,?,?,?)", (
                message_id or "pending:" + request_id, thread_id, content_hash(text), request_id, time.time()))
            if message_id:
                conn.execute("UPDATE wa_events SET authorship='JARVIS' WHERE thread_id=? AND message_id=?", (thread_id, message_id))

    def is_generated(self, thread_id: str, message_id: str, text: str) -> bool:
        with self.connection() as conn:
            return bool(conn.execute("SELECT 1 FROM wa_generated_messages WHERE thread_id=? AND (message_id=? OR (content_hash=? AND created_at>?))",
                (thread_id, message_id, content_hash(text), time.time() - 120)).fetchone())

    def ingest(self, message, authorship: str) -> bool:
        payload = message.model_dump()
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            old = conn.execute("SELECT payload,thread_id FROM wa_events WHERE message_id=?", (message.message_id,)).fetchone()
            if old and old[1] != message.chat_id:
                raise ValueError("Message identity cannot change thread")
            comparable = json.loads(old[0]) if old else None
            if comparable is not None:
                comparable.pop("history", None)
            candidate = dict(payload)
            candidate.pop("history", None)
            if old and comparable == candidate:
                conn.execute("INSERT INTO wa_intelligence_metrics VALUES('dedupe',1) ON CONFLICT(name) DO UPDATE SET value=value+1")
                return False
            conn.execute("INSERT INTO wa_events(message_id,thread_id,timestamp,payload,authorship) VALUES(?,?,?,?,?) ON CONFLICT(message_id) DO UPDATE SET payload=excluded.payload,authorship=excluded.authorship,revision=revision+1",
                (message.message_id, message.chat_id, float(message.timestamp) if str(message.timestamp).replace('.', '', 1).isdigit() else self._timestamp(message.timestamp), raw, authorship))
            conn.execute("DELETE FROM wa_vectors WHERE message_id=?", (message.message_id,))
            conn.execute("DELETE FROM wa_events_fts WHERE message_id=?", (message.message_id,))
            conn.execute("INSERT INTO wa_events_fts VALUES(?,?,?)", (message.message_id, message.chat_id, message.text))
            conn.execute("INSERT INTO wa_thread_state VALUES(?,1,?) ON CONFLICT(thread_id) DO UPDATE SET version=version+1,updated_at=excluded.updated_at", (message.chat_id, time.time()))
            conn.execute("INSERT INTO wa_intelligence_jobs VALUES(?,?,'PENDING',0) ON CONFLICT(message_id) DO UPDATE SET status='PENDING',attempts=0", (message.message_id, message.chat_id))
        return True

    @staticmethod
    def _timestamp(text):
        from datetime import datetime
        return datetime.fromisoformat(str(text).replace("Z", "+00:00")).timestamp()

    def rows(self, thread_id: str, limit: int = 12, before: float | None = None):
        with self.connection() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM wa_events WHERE thread_id=? AND timestamp<=? ORDER BY timestamp DESC,rowid DESC LIMIT ?", (thread_id, before if before is not None else time.time(), limit)).fetchall()][::-1]

    def search(self, thread_id: str, query: str, limit: int = 12):
        import re
        tokens = re.findall(r"\w+", query)[:16]
        if not tokens:
            return []
        match = " OR ".join('"' + token + '"' for token in tokens)
        with self.connection() as conn:
            rows = conn.execute("SELECT e.* FROM wa_events_fts f JOIN wa_events e ON e.message_id=f.message_id WHERE wa_events_fts MATCH ? AND e.thread_id=? ORDER BY bm25(wa_events_fts),e.timestamp DESC LIMIT ?", (match, thread_id, limit)).fetchall()
        return [dict(r) for r in rows]

    def vector_search(self, thread_id, vector, before, limit=8, model="configured"):
        import math
        if not vector or not all(math.isfinite(float(x)) for x in vector):
            return []
        with self.connection() as conn:
            rows = conn.execute("SELECT e.*,v.vector FROM wa_vectors v JOIN wa_events e USING(message_id) "
                "WHERE e.thread_id=? AND v.thread_id=? AND e.timestamp<=? AND v.model=? ORDER BY e.timestamp DESC LIMIT 2000",
                (thread_id, thread_id, before, model)).fetchall()
        ranked = []
        norm = math.sqrt(sum(x*x for x in vector))
        for row in rows:
            other = json.loads(row["vector"])
            if len(other) != len(vector) or not norm or not all(math.isfinite(float(x)) for x in other): continue
            denominator = norm * math.sqrt(sum(x*x for x in other))
            score = sum(a*b for a, b in zip(vector, other)) / denominator if denominator else 0
            if score >= 0.4:
                ranked.append((score, dict(row)))
        return [row for _, row in sorted(ranked, key=lambda pair: pair[0], reverse=True)[:limit]]

    def pending_jobs(self, limit=32):
        with self.connection() as conn:
            return [dict(r) for r in conn.execute("SELECT j.*,e.payload,e.timestamp,e.revision AS event_revision FROM wa_intelligence_jobs j JOIN wa_events e USING(message_id) WHERE j.status='PENDING' AND j.attempts<3 ORDER BY e.timestamp LIMIT ?", (limit,))]

    def finish_job(self, message_id: str, success=True, revision=None):
        with self.connection() as conn:
            conn.execute("UPDATE wa_intelligence_jobs SET status=CASE WHEN ? THEN 'DONE' WHEN attempts>=2 THEN 'FAILED' ELSE 'PENDING' END,attempts=attempts+1 "
                "WHERE message_id=? AND (? IS NULL OR EXISTS(SELECT 1 FROM wa_events WHERE message_id=? AND revision=?))",
                (success, message_id, revision, message_id, revision))

    def lexicon(self):
        with self.connection() as conn:
            return {row[0]: row[1] for row in conn.execute("SELECT surface,meaning FROM wa_lexicon WHERE confirmed=1 OR observations>=3 LIMIT 512")}

    def learn_term(self, surface: str, meaning: str, confirmed=False):
        # Ambiguous one-shot observations are not used. Conflicting meanings reset observation count.
        with self.connection() as conn:
            old = conn.execute("SELECT meaning FROM wa_lexicon WHERE surface=?", (surface,)).fetchone()
            if old and old[0] != meaning and not confirmed:
                return False
            conn.execute("INSERT INTO wa_lexicon VALUES(?,?,1,?) ON CONFLICT(surface) DO UPDATE SET observations=observations+1,confirmed=max(confirmed,excluded.confirmed),meaning=excluded.meaning", (surface, meaning, int(confirmed)))
        return True
