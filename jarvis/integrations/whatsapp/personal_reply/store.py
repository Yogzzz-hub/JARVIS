"""SQLite persistence for the personal reply agent (shares JARVIS's database; migration 008).

Every contact-specific query filters by ``contact_id`` (a stable WhatsApp JID), so one person's
examples can never be retrieved for another person's reply. Text is encrypted with ``DataBox``.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np

from jarvis.integrations.whatsapp.personal_reply.crypto import DataBox
from jarvis.integrations.whatsapp.personal_reply.models import (
    AutoReplyGrant, ChatLine, ContactStyleProfile, Direction, ExampleSource, GrantScope, ReplyExample, ReplyMode,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS wa_pr_contacts (
    contact_id TEXT PRIMARY KEY, display_name TEXT NOT NULL DEFAULT '', mode TEXT NOT NULL DEFAULT 'OFF',
    updated_at REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS wa_pr_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT, contact_id TEXT NOT NULL, import_id TEXT NOT NULL, ts REAL NOT NULL,
    direction TEXT NOT NULL, text_enc TEXT NOT NULL, message_id TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wa_pr_sources_contact ON wa_pr_sources(contact_id, ts);
CREATE TABLE IF NOT EXISTS wa_pr_examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT, contact_id TEXT NOT NULL, context_enc TEXT NOT NULL, reply_enc TEXT NOT NULL,
    ts REAL NOT NULL, source TEXT NOT NULL, split TEXT NOT NULL DEFAULT 'TRAIN', vector BLOB, created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wa_pr_examples_contact ON wa_pr_examples(contact_id, split);
CREATE TABLE IF NOT EXISTS wa_pr_profiles (
    contact_id TEXT PRIMARY KEY, display_name TEXT NOT NULL DEFAULT '', profile_enc TEXT NOT NULL,
    profile_version INTEGER NOT NULL, updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS wa_pr_profile_versions (
    contact_id TEXT NOT NULL, profile_version INTEGER NOT NULL, profile_enc TEXT NOT NULL, created_at REAL NOT NULL,
    PRIMARY KEY (contact_id, profile_version)
);
CREATE TABLE IF NOT EXISTS wa_pr_grants (
    grant_id TEXT PRIMARY KEY, scope TEXT NOT NULL, contact_ids TEXT NOT NULL, mode TEXT NOT NULL,
    enabled_at REAL NOT NULL, expires_at REAL NOT NULL, granted_by_user INTEGER NOT NULL DEFAULT 1,
    revoked_at REAL, include_untrained INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS wa_pr_processed (
    message_id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS wa_pr_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT, incoming_message_id TEXT NOT NULL UNIQUE, message_ids TEXT NOT NULL,
    contact_id TEXT NOT NULL, chat_id TEXT NOT NULL, grant_id TEXT, mode TEXT NOT NULL, status TEXT NOT NULL,
    draft_hash TEXT, final_hash TEXT, text_enc TEXT, incoming_enc TEXT, reason TEXT, quality_json TEXT,
    ledger_action_id TEXT, sent_message_id TEXT, send_started REAL, send_verified REAL,
    created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wa_pr_replies_contact ON wa_pr_replies(contact_id, created_at);
CREATE INDEX IF NOT EXISTS idx_wa_pr_replies_status ON wa_pr_replies(status);
CREATE TABLE IF NOT EXISTS wa_pr_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, contact_id TEXT NOT NULL, display_name TEXT NOT NULL,
    stage TEXT NOT NULL, detail TEXT NOT NULL DEFAULT ''
);
"""

VECTOR_DIM = 1024


def text_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:24]


def default_db_path() -> Path:
    from jarvis.tools.system.everyday_tools import default_db_path as _p
    return _p()


class PersonalReplyStore:
    def __init__(self, path: Optional[Path] = None, box: Optional[DataBox] = None) -> None:
        self.path = Path(path) if path else default_db_path()
        self.box = box if box is not None else DataBox()
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as con:
            con.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=10)
        con.execute("PRAGMA busy_timeout=10000")
        con.row_factory = sqlite3.Row
        return con

    # ------------------------------------------------------------------ contacts / modes
    def upsert_contact(self, contact_id: str, display_name: str = "") -> None:
        with self._lock, self._conn() as con:
            con.execute(
                "INSERT INTO wa_pr_contacts(contact_id, display_name, updated_at) VALUES (?,?,?) "
                "ON CONFLICT(contact_id) DO UPDATE SET display_name = CASE WHEN excluded.display_name != '' "
                "THEN excluded.display_name ELSE wa_pr_contacts.display_name END, updated_at = excluded.updated_at",
                (contact_id, display_name or "", time.time()))

    def set_mode(self, contact_id: str, mode: ReplyMode) -> None:
        self.upsert_contact(contact_id)
        with self._lock, self._conn() as con:
            con.execute("UPDATE wa_pr_contacts SET mode = ?, updated_at = ? WHERE contact_id = ?",
                        (ReplyMode(mode).value, time.time(), contact_id))

    def get_mode(self, contact_id: str) -> ReplyMode:
        with self._conn() as con:
            row = con.execute("SELECT mode FROM wa_pr_contacts WHERE contact_id = ?", (contact_id,)).fetchone()
        return ReplyMode(row["mode"]) if row else ReplyMode.OFF

    def contacts(self) -> list[dict[str, Any]]:
        with self._conn() as con:
            rows = con.execute("SELECT * FROM wa_pr_contacts ORDER BY display_name COLLATE NOCASE").fetchall()
        return [dict(r) for r in rows]

    def display_name(self, contact_id: str) -> str:
        with self._conn() as con:
            row = con.execute("SELECT display_name FROM wa_pr_contacts WHERE contact_id = ?", (contact_id,)).fetchone()
        return (row["display_name"] if row else "") or contact_id.split("@")[0]

    # ------------------------------------------------------------------ source history (never destructively overwritten)
    def add_sources(self, contact_id: str, lines: Iterable[ChatLine], import_id: str = "") -> int:
        import_id = import_id or uuid.uuid4().hex[:12]
        now = time.time()
        rows = [(contact_id, import_id, ln.timestamp, ln.direction.value, self.box.encrypt(ln.text), ln.message_id, now)
                for ln in lines if ln.text]
        with self._lock, self._conn() as con:
            existing = {(r[0], r[1]) for r in con.execute(
                "SELECT ts, message_id FROM wa_pr_sources WHERE contact_id = ?", (contact_id,))}
            fresh = [r for r in rows if not (r[5] and (r[2], r[5]) in existing)]
            con.executemany("INSERT INTO wa_pr_sources(contact_id, import_id, ts, direction, text_enc, message_id, created_at) "
                            "VALUES (?,?,?,?,?,?,?)", fresh)
        return len(fresh)

    def sources(self, contact_id: str) -> list[ChatLine]:
        with self._conn() as con:
            rows = con.execute("SELECT * FROM wa_pr_sources WHERE contact_id = ? ORDER BY ts, id", (contact_id,)).fetchall()
        return [ChatLine(timestamp=r["ts"], sender="", direction=Direction(r["direction"]),
                         text=self.box.decrypt(r["text_enc"]), message_id=r["message_id"], origin=r["import_id"]) for r in rows]

    def source_count(self, contact_id: str) -> dict[str, int]:
        with self._conn() as con:
            rows = con.execute("SELECT direction, count(*) FROM wa_pr_sources WHERE contact_id = ? GROUP BY direction",
                               (contact_id,)).fetchall()
        return {r[0]: r[1] for r in rows}

    # ------------------------------------------------------------------ examples (per-contact RAG index)
    def replace_examples(self, contact_id: str, examples: list[ReplyExample], vectors: np.ndarray,
                         sources: tuple[str, ...] = (ExampleSource.IMPORT.value,)) -> None:
        """Rebuild derived examples of the given sources (source messages themselves are kept)."""
        now = time.time()
        marks = ",".join("?" * len(sources))
        with self._lock, self._conn() as con:
            con.execute(f"DELETE FROM wa_pr_examples WHERE contact_id = ? AND source IN ({marks})", (contact_id, *sources))
            con.executemany(
                "INSERT INTO wa_pr_examples(contact_id, context_enc, reply_enc, ts, source, split, vector, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                [(contact_id, self.box.encrypt(e.context), self.box.encrypt(e.reply), e.timestamp, ExampleSource(e.source).value,
                  e.split, vectors[i].astype(np.float16).tobytes(), now) for i, e in enumerate(examples)])

    def add_example(self, example: ReplyExample, vector: np.ndarray) -> int:
        if example.source not in (ExampleSource.IMPORT, ExampleSource.LIVE_USER, ExampleSource.USER_EDITED, ExampleSource.APPROVED):
            raise ValueError("only owner-authored or owner-approved text may become a style example")
        with self._lock, self._conn() as con:
            cur = con.execute(
                "INSERT INTO wa_pr_examples(contact_id, context_enc, reply_enc, ts, source, split, vector, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (example.contact_id, self.box.encrypt(example.context), self.box.encrypt(example.reply), example.timestamp,
                 ExampleSource(example.source).value, example.split, vector.astype(np.float16).tobytes(), time.time()))
            return int(cur.lastrowid)

    def examples(self, contact_id: str, splits: tuple[str, ...] = ("TRAIN",)) -> tuple[list[ReplyExample], np.ndarray]:
        marks = ",".join("?" * len(splits))
        with self._conn() as con:
            rows = con.execute(f"SELECT * FROM wa_pr_examples WHERE contact_id = ? AND split IN ({marks}) ORDER BY ts, id",
                               (contact_id, *splits)).fetchall()
        exs, vecs = [], []
        for r in rows:
            exs.append(ReplyExample(contact_id=r["contact_id"], context=self.box.decrypt(r["context_enc"]),
                                    reply=self.box.decrypt(r["reply_enc"]), timestamp=r["ts"], source=ExampleSource(r["source"]),
                                    split=r["split"], example_id=r["id"]))
            vecs.append(np.frombuffer(r["vector"], dtype=np.float16).astype(np.float32) if r["vector"] else np.zeros(VECTOR_DIM, np.float32))
        return exs, (np.vstack(vecs) if vecs else np.zeros((0, VECTOR_DIM), np.float32))

    def example_count(self, contact_id: str) -> int:
        with self._conn() as con:
            return con.execute("SELECT count(*) FROM wa_pr_examples WHERE contact_id = ?", (contact_id,)).fetchone()[0]

    # ------------------------------------------------------------------ profiles (versioned)
    def save_profile(self, profile: ContactStyleProfile) -> int:
        with self._lock, self._conn() as con:
            row = con.execute("SELECT max(profile_version) FROM wa_pr_profile_versions WHERE contact_id = ?",
                              (profile.contact_id,)).fetchone()
            profile.profile_version = int(row[0] or 0) + 1
            profile.updated_at = time.time()
            blob = self.box.encrypt(json.dumps(profile.to_dict(), ensure_ascii=False))
            con.execute("INSERT INTO wa_pr_profile_versions(contact_id, profile_version, profile_enc, created_at) VALUES (?,?,?,?)",
                        (profile.contact_id, profile.profile_version, blob, profile.updated_at))
            con.execute("INSERT OR REPLACE INTO wa_pr_profiles(contact_id, display_name, profile_enc, profile_version, updated_at) "
                        "VALUES (?,?,?,?,?)", (profile.contact_id, profile.display_name, blob, profile.profile_version, profile.updated_at))
        self.upsert_contact(profile.contact_id, profile.display_name)
        return profile.profile_version

    def load_profile(self, contact_id: str) -> Optional[ContactStyleProfile]:
        with self._conn() as con:
            row = con.execute("SELECT profile_enc FROM wa_pr_profiles WHERE contact_id = ?", (contact_id,)).fetchone()
        if not row:
            return None
        text = self.box.decrypt(row["profile_enc"])
        return ContactStyleProfile.from_dict(json.loads(text)) if text else None

    def profile_versions(self, contact_id: str) -> list[int]:
        with self._conn() as con:
            return [r[0] for r in con.execute("SELECT profile_version FROM wa_pr_profile_versions WHERE contact_id = ? "
                                              "ORDER BY profile_version", (contact_id,))]

    def clear_profile(self, contact_id: str, keep_sources: bool = False) -> None:
        with self._lock, self._conn() as con:
            con.execute("DELETE FROM wa_pr_profiles WHERE contact_id = ?", (contact_id,))
            con.execute("DELETE FROM wa_pr_profile_versions WHERE contact_id = ?", (contact_id,))
            con.execute("DELETE FROM wa_pr_examples WHERE contact_id = ?", (contact_id,))
            if not keep_sources:
                con.execute("DELETE FROM wa_pr_sources WHERE contact_id = ?", (contact_id,))

    # ------------------------------------------------------------------ grants
    def add_grant(self, grant: AutoReplyGrant) -> None:
        with self._lock, self._conn() as con:
            con.execute("INSERT INTO wa_pr_grants(grant_id, scope, contact_ids, mode, enabled_at, expires_at, granted_by_user, "
                        "revoked_at, include_untrained) VALUES (?,?,?,?,?,?,?,?,?)",
                        (grant.grant_id, grant.scope.value, json.dumps(grant.contact_ids), grant.mode.value, grant.enabled_at,
                         grant.expires_at, 1 if grant.granted_by_user else 0, grant.revoked_at, 1 if grant.include_untrained else 0))

    def grants(self, include_inactive: bool = False) -> list[AutoReplyGrant]:
        q = "SELECT * FROM wa_pr_grants" + ("" if include_inactive else " WHERE revoked_at IS NULL") + " ORDER BY enabled_at"
        with self._conn() as con:
            rows = con.execute(q).fetchall()
        return [AutoReplyGrant(grant_id=r["grant_id"], scope=GrantScope(r["scope"]), contact_ids=json.loads(r["contact_ids"]),
                               enabled_at=r["enabled_at"], expires_at=r["expires_at"], mode=ReplyMode(r["mode"]),
                               granted_by_user=bool(r["granted_by_user"]), revoked_at=r["revoked_at"],
                               include_untrained=bool(r["include_untrained"])) for r in rows]

    def revoke_grant(self, grant_id: str, at: Optional[float] = None) -> None:
        with self._lock, self._conn() as con:
            con.execute("UPDATE wa_pr_grants SET revoked_at = ? WHERE grant_id = ? AND revoked_at IS NULL",
                        (time.time() if at is None else at, grant_id))

    def update_grant_contacts(self, grant_id: str, contact_ids: list[str]) -> None:
        with self._lock, self._conn() as con:
            con.execute("UPDATE wa_pr_grants SET contact_ids = ? WHERE grant_id = ?", (json.dumps(contact_ids), grant_id))

    # ------------------------------------------------------------------ processed ids (duplicate + placeholder protection)
    def processed_state(self, message_id: str) -> Optional[str]:
        with self._conn() as con:
            row = con.execute("SELECT state FROM wa_pr_processed WHERE message_id = ?", (message_id,)).fetchone()
        return row["state"] if row else None

    def mark_pending_decryption(self, message_id: str, chat_id: str) -> bool:
        """Record a placeholder. Returns False if the real message was already processed."""
        with self._lock, self._conn() as con:
            row = con.execute("SELECT state FROM wa_pr_processed WHERE message_id = ?", (message_id,)).fetchone()
            if row and row["state"] != "PENDING_DECRYPTION":
                return False
            con.execute("INSERT INTO wa_pr_processed(message_id, chat_id, state, attempts, updated_at) VALUES (?,?,?,0,?) "
                        "ON CONFLICT(message_id) DO UPDATE SET attempts = attempts + 1, updated_at = excluded.updated_at",
                        (message_id, chat_id, "PENDING_DECRYPTION", time.time()))
            return True

    def claim(self, message_id: str, chat_id: str) -> bool:
        """Atomically claim a real (decrypted) message for processing. False = already claimed/processed."""
        with self._lock, self._conn() as con:
            cur = con.execute(
                "INSERT INTO wa_pr_processed(message_id, chat_id, state, updated_at) VALUES (?,?,?,?) "
                "ON CONFLICT(message_id) DO UPDATE SET state = 'CLAIMED', updated_at = excluded.updated_at "
                "WHERE wa_pr_processed.state = 'PENDING_DECRYPTION'",
                (message_id, chat_id, "CLAIMED", time.time()))
            return cur.rowcount == 1

    def set_processed_state(self, message_id: str, state: str) -> None:
        with self._lock, self._conn() as con:
            con.execute("UPDATE wa_pr_processed SET state = ?, updated_at = ? WHERE message_id = ?", (state, time.time(), message_id))

    def pending_decryption(self, max_attempts: int = 1000) -> list[dict[str, Any]]:
        with self._conn() as con:
            return [dict(r) for r in con.execute("SELECT * FROM wa_pr_processed WHERE state = 'PENDING_DECRYPTION' AND attempts < ?",
                                                 (max_attempts,))]

    # ------------------------------------------------------------------ reply log (+ sent ids)
    def start_reply(self, incoming_message_id: str, message_ids: list[str], contact_id: str, chat_id: str, mode: str,
                    grant_id: Optional[str], incoming_text: str) -> Optional[int]:
        """Create the reply record; returns None if a reply for this message already exists (duplicate)."""
        now = time.time()
        with self._lock, self._conn() as con:
            try:
                cur = con.execute(
                    "INSERT INTO wa_pr_replies(incoming_message_id, message_ids, contact_id, chat_id, grant_id, mode, status, "
                    "incoming_enc, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (incoming_message_id, json.dumps(message_ids), contact_id, chat_id, grant_id, mode, "DRAFTING",
                     self.box.encrypt(incoming_text), now, now))
                return int(cur.lastrowid)
            except sqlite3.IntegrityError:
                return None

    def update_reply(self, reply_id: int, **fields: Any) -> None:
        if "text" in fields:
            fields["text_enc"] = self.box.encrypt(fields.pop("text") or "")
        if "quality" in fields:
            fields["quality_json"] = json.dumps(fields.pop("quality"))
        fields["updated_at"] = time.time()
        cols = ", ".join(f"{k} = ?" for k in fields)
        with self._lock, self._conn() as con:
            con.execute(f"UPDATE wa_pr_replies SET {cols} WHERE id = ?", (*fields.values(), reply_id))

    def reply(self, reply_id: int) -> Optional[dict[str, Any]]:
        with self._conn() as con:
            row = con.execute("SELECT * FROM wa_pr_replies WHERE id = ?", (reply_id,)).fetchone()
        return self._reply_row(row) if row else None

    def reply_for_message(self, message_id: str) -> Optional[dict[str, Any]]:
        with self._conn() as con:
            row = con.execute("SELECT * FROM wa_pr_replies WHERE incoming_message_id = ?", (message_id,)).fetchone()
        return self._reply_row(row) if row else None

    def replies(self, contact_id: Optional[str] = None, statuses: Optional[tuple[str, ...]] = None, limit: int = 50) -> list[dict[str, Any]]:
        q, args = "SELECT * FROM wa_pr_replies WHERE 1=1", []
        if contact_id:
            q += " AND contact_id = ?"
            args.append(contact_id)
        if statuses:
            q += f" AND status IN ({','.join('?' * len(statuses))})"
            args.extend(statuses)
        q += " ORDER BY created_at DESC, id DESC LIMIT ?"
        args.append(limit)
        with self._conn() as con:
            rows = con.execute(q, args).fetchall()
        return [self._reply_row(r) for r in rows]

    def _reply_row(self, row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["text"] = self.box.decrypt(d.pop("text_enc") or "")
        d["incoming"] = self.box.decrypt(d.pop("incoming_enc") or "")
        d["message_ids"] = json.loads(d["message_ids"] or "[]")
        d["quality"] = json.loads(d.pop("quality_json") or "null")
        return d

    def is_sent_reply(self, chat_id: str, sent_message_id: str = "", text: str = "", within_s: float = 600.0) -> bool:
        """Was this outgoing message written by JARVIS (so it must not be learned as the owner's style)?"""
        with self._conn() as con:
            if sent_message_id:
                if con.execute("SELECT 1 FROM wa_pr_replies WHERE sent_message_id = ?", (sent_message_id,)).fetchone():
                    return True
            if text:
                h = text_hash(text.strip())
                row = con.execute("SELECT 1 FROM wa_pr_replies WHERE chat_id = ? AND final_hash = ? AND updated_at >= ?",
                                  (chat_id, h, time.time() - within_s)).fetchone()
                return bool(row)
        return False

    # ------------------------------------------------------------------ activity feed (no message content)
    def activity(self, contact_id: str, display_name: str, stage: str, detail: str = "") -> dict[str, Any]:
        now = time.time()
        with self._lock, self._conn() as con:
            con.execute("INSERT INTO wa_pr_activity(ts, contact_id, display_name, stage, detail) VALUES (?,?,?,?,?)",
                        (now, contact_id, display_name, stage, detail[:200]))
            con.execute("DELETE FROM wa_pr_activity WHERE id <= (SELECT max(id) - 2000 FROM wa_pr_activity)")
        return {"ts": now, "contact_id": contact_id, "display_name": display_name, "stage": stage, "detail": detail[:200]}

    def recent_activity(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._conn() as con:
            return [dict(r) for r in con.execute("SELECT * FROM wa_pr_activity ORDER BY id DESC LIMIT ?", (limit,))]
