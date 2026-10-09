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
    Authorship, AutoReplyGrant, ChatLine, ContactStyleProfile, Direction, ExampleSource, GrantScope, ReplyExample, ReplyMode,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS wa_pr_contacts (
    contact_id TEXT PRIMARY KEY, display_name TEXT NOT NULL DEFAULT '', mode TEXT NOT NULL DEFAULT 'OFF',
    updated_at REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS wa_pr_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT, contact_id TEXT NOT NULL, import_id TEXT NOT NULL, ts REAL NOT NULL,
    direction TEXT NOT NULL, text_enc TEXT NOT NULL, message_id TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL,
    provenance TEXT NOT NULL DEFAULT 'UNKNOWN', reply_to TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_wa_pr_sources_contact ON wa_pr_sources(contact_id, ts);
CREATE TABLE IF NOT EXISTS wa_pr_examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT, contact_id TEXT NOT NULL, context_enc TEXT NOT NULL, reply_enc TEXT NOT NULL,
    ts REAL NOT NULL, source TEXT NOT NULL, split TEXT NOT NULL DEFAULT 'TRAIN', vector BLOB, created_at REAL NOT NULL,
    provenance_verified INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_wa_pr_examples_contact ON wa_pr_examples(contact_id, split);
CREATE TABLE IF NOT EXISTS wa_pr_profiles (
    contact_id TEXT PRIMARY KEY, display_name TEXT NOT NULL DEFAULT '', profile_enc TEXT NOT NULL,
    profile_version INTEGER NOT NULL, updated_at REAL NOT NULL, provenance_verified INTEGER NOT NULL DEFAULT 0
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
CREATE TABLE IF NOT EXISTS wa_pr_feedback (
    reply_id INTEGER PRIMARY KEY, contact_id TEXT NOT NULL, candidate_enc TEXT NOT NULL,
    final_enc TEXT NOT NULL, edit_ratio REAL NOT NULL, sent_message_id TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS wa_pr_stickers (
    sticker_hash TEXT PRIMARY KEY, media_ref_enc TEXT NOT NULL, mime_type TEXT NOT NULL,
    first_seen REAL NOT NULL, last_used REAL, label_enc TEXT
);
CREATE TABLE IF NOT EXISTS wa_pr_sticker_usage (
    message_id TEXT PRIMARY KEY, sticker_hash TEXT NOT NULL, contact_id TEXT NOT NULL,
    context_enc TEXT NOT NULL, context_vector BLOB, conversation_mode TEXT NOT NULL,
    provenance TEXT NOT NULL, used_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wa_pr_sticker_usage_contact ON wa_pr_sticker_usage(contact_id,used_at);
CREATE TABLE IF NOT EXISTS wa_pr_evaluations (
    contact_id TEXT PRIMARY KEY, evaluated_at REAL NOT NULL, samples INTEGER NOT NULL,
    metrics_json TEXT NOT NULL, approved_at REAL
);
CREATE TABLE IF NOT EXISTS wa_pr_legacy_audit (
    message_id TEXT PRIMARY KEY, contact_id TEXT NOT NULL, provenance TEXT NOT NULL,
    confidence REAL NOT NULL, reasons_json TEXT NOT NULL, classified_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS wa_pr_owner_reviews (
    message_id TEXT PRIMARY KEY, contact_id TEXT NOT NULL, original_provenance TEXT NOT NULL,
    decision TEXT NOT NULL, verified_by_owner INTEGER NOT NULL, verified_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS wa_pr_draft_feedback (
    reply_id INTEGER PRIMARY KEY, contact_id TEXT NOT NULL, state TEXT NOT NULL,
    candidate_enc TEXT NOT NULL, final_enc TEXT, edit_ratio REAL,
    sent_message_id TEXT, recorded_at REAL NOT NULL, style_delta_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS wa_pr_draft_feedback_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, reply_id INTEGER NOT NULL, contact_id TEXT NOT NULL,
    state TEXT NOT NULL, candidate_enc TEXT NOT NULL, final_enc TEXT, edit_ratio REAL,
    sent_message_id TEXT, recorded_at REAL NOT NULL, style_delta_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_wa_pr_feedback_events_contact ON wa_pr_draft_feedback_events(contact_id,recorded_at);
CREATE TABLE IF NOT EXISTS wa_pr_holdout_review_cases (
    case_id TEXT PRIMARY KEY, contact_id TEXT NOT NULL, incoming_enc TEXT NOT NULL,
    candidate_enc TEXT NOT NULL, owner_enc TEXT NOT NULL, generated_at REAL NOT NULL,
    rating TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_wa_pr_holdout_cases_contact ON wa_pr_holdout_review_cases(contact_id,generated_at);
CREATE TABLE IF NOT EXISTS wa_brain_index (
    id INTEGER PRIMARY KEY CHECK(id=1), active_version INTEGER NOT NULL DEFAULT 0,
    published_at REAL NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO wa_brain_index(id,active_version,published_at) VALUES(1,0,0);
CREATE TABLE IF NOT EXISTS wa_brain_contact_state (
    contact_id TEXT PRIMARY KEY, source_hash TEXT NOT NULL, index_version INTEGER NOT NULL,
    derived_json TEXT NOT NULL, indexed_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS wa_brain_jobs (
    job_id TEXT PRIMARY KEY, scope TEXT NOT NULL, contact_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL, stage TEXT NOT NULL, processed INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0, warnings_json TEXT NOT NULL DEFAULT '[]',
    metrics_json TEXT NOT NULL DEFAULT '{}',
    error TEXT NOT NULL DEFAULT '', started_at REAL NOT NULL, updated_at REAL NOT NULL,
    new_index_version INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_wa_brain_jobs_updated ON wa_brain_jobs(updated_at DESC);
"""

VECTOR_DIM = 1024


def text_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:24]


def default_db_path() -> Path:
    from jarvis.tools.system.everyday_tools import default_db_path as _p
    return _p()


_MIGRATE_LOCK = threading.Lock()
_MIGRATED: set[str] = set()


class PersonalReplyStore:
    def __init__(self, path: Optional[Path] = None, box: Optional[DataBox] = None) -> None:
        self.path = Path(path) if path else default_db_path()
        self.box = box if box is not None else DataBox()
        self._lock = threading.RLock()
        self._profile_cache: dict[str, tuple[float, ContactStyleProfile | None]] = {}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        key = str(self.path.resolve())
        with _MIGRATE_LOCK:
            if key in _MIGRATED and self._has_schema():
                return
            self._migrate_with_retry()
            _MIGRATED.add(key)

    def _has_schema(self) -> bool:
        try:
            with self._conn() as con:
                return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='wa_brain_jobs'").fetchone() is not None
        except sqlite3.Error:
            return False

    def _migrate_with_retry(self) -> None:
        """Schema setup needs the write lock once per process; a long write elsewhere is waited out, not fatal."""
        delay = 0.25
        for attempt in range(5):
            try:
                self._migrate()
                return
            except sqlite3.OperationalError as exc:
                if attempt == 4 or not any(w in str(exc).lower() for w in ("locked", "busy")):
                    raise
                time.sleep(delay)
                delay = min(2.0, delay * 2)

    def _migrate(self) -> None:
        with self._conn() as con:
            con.executescript(SCHEMA)
            if "note" not in {r[1] for r in con.execute("PRAGMA table_info(wa_pr_grants)").fetchall()}:
                con.execute("ALTER TABLE wa_pr_grants ADD COLUMN note TEXT NOT NULL DEFAULT ''")
            if "provenance" not in {r[1] for r in con.execute("PRAGMA table_info(wa_pr_sources)").fetchall()}:
                con.execute("ALTER TABLE wa_pr_sources ADD COLUMN provenance TEXT NOT NULL DEFAULT 'UNKNOWN'")
                con.execute("UPDATE wa_pr_sources SET provenance='USER_TYPED' "
                            "WHERE direction='USER' AND message_id LIKE 'imp_%' AND import_id!='live'")
            if "reply_to" not in {r[1] for r in con.execute("PRAGMA table_info(wa_pr_sources)").fetchall()}:
                con.execute("ALTER TABLE wa_pr_sources ADD COLUMN reply_to TEXT NOT NULL DEFAULT ''")
            for table, column, declaration in (
                ('wa_pr_sources', 'provenance_confidence', 'REAL NOT NULL DEFAULT 0'),
                ('wa_pr_sources', 'provenance_reasons_json', "TEXT NOT NULL DEFAULT '[]'"),
                ('wa_pr_examples', 'provenance', "TEXT NOT NULL DEFAULT 'UNKNOWN'"),
                ('wa_pr_examples', 'evidence_weight', 'REAL NOT NULL DEFAULT 0'),
                ('wa_pr_sticker_usage', 'provenance_confidence', 'REAL NOT NULL DEFAULT 0'),
                ('wa_pr_profiles', 'evidence_class', "TEXT NOT NULL DEFAULT 'UNKNOWN'"),
                ('wa_pr_draft_feedback', 'style_delta_json', "TEXT NOT NULL DEFAULT '{}'"),
                ('wa_pr_holdout_review_cases', 'dimensions_json', "TEXT NOT NULL DEFAULT '{}'"),
                ('wa_brain_jobs', 'metrics_json', "TEXT NOT NULL DEFAULT '{}'"),
            ):
                if column not in {r[1] for r in con.execute(f'PRAGMA table_info({table})')}:
                    con.execute(f'ALTER TABLE {table} ADD COLUMN {column} {declaration}')
            unverified_exports = [r[0] for r in con.execute(
                "SELECT DISTINCT contact_id FROM wa_pr_sources WHERE message_id LIKE 'imp_%' "
                "AND provenance='USER_TYPED' AND provenance_reasons_json NOT LIKE '%verified_test_fixture%' "
                "AND import_id NOT IN ('live','owner_attested','reviewed_draft')")]
            if unverified_exports:
                marks = ','.join('?' for _ in unverified_exports)
                con.execute("UPDATE wa_pr_sources SET provenance='LEGACY_OWNER_LIKELY', "
                            "provenance_confidence=0.55,provenance_reasons_json='[\"export_owner_direction_unverified\"]' "
                            "WHERE message_id LIKE 'imp_%' AND provenance='USER_TYPED' "
                            "AND provenance_reasons_json NOT LIKE '%verified_test_fixture%' "
                            "AND import_id NOT IN ('live','owner_attested','reviewed_draft')")
                con.execute(f'DELETE FROM wa_pr_profiles WHERE contact_id IN ({marks})', unverified_exports)
                con.execute(f'DELETE FROM wa_pr_examples WHERE contact_id IN ({marks})', unverified_exports)
            if "provenance_verified" not in {r[1] for r in con.execute("PRAGMA table_info(wa_pr_examples)").fetchall()}:
                con.execute("ALTER TABLE wa_pr_examples ADD COLUMN provenance_verified INTEGER NOT NULL DEFAULT 0")
            if "provenance_verified" not in {r[1] for r in con.execute("PRAGMA table_info(wa_pr_profiles)").fetchall()}:
                con.execute("ALTER TABLE wa_pr_profiles ADD COLUMN provenance_verified INTEGER NOT NULL DEFAULT 0")
            if "approved_at" not in {r[1] for r in con.execute("PRAGMA table_info(wa_pr_evaluations)").fetchall()}:
                con.execute("ALTER TABLE wa_pr_evaluations ADD COLUMN approved_at REAL")

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
    def add_sources(self, contact_id: str, lines: Iterable[ChatLine], import_id: str = "",
                    preserve_existing: bool = False) -> int:
        import_id = import_id or uuid.uuid4().hex[:12]
        now = time.time()
        rows = []
        for ln in lines:
            if not ln.text:
                continue
            mid = ln.message_id or "src_" + hashlib.sha256(
                f"{contact_id}\0{ln.timestamp}\0{ln.direction.value}\0{ln.text}".encode()).hexdigest()[:24]
            rows.append((contact_id, import_id, ln.timestamp, ln.direction.value, self.box.encrypt(ln.text), mid, now,
                         Authorship(ln.provenance).value, ln.reply_to, max(0., min(1., ln.provenance_confidence)),
                         json.dumps(ln.provenance_reasons)))
        with self._lock, self._conn() as con:
            existing = {(r[0], r[1]) for r in con.execute(
                "SELECT ts, message_id FROM wa_pr_sources WHERE contact_id = ?", (contact_id,))}
            fresh = []
            for row in rows:
                key = (row[2], row[5])
                if key not in existing:
                    fresh.append(row)
                    existing.add(key)
            con.executemany("INSERT INTO wa_pr_sources(contact_id, import_id, ts, direction, text_enc, message_id, created_at, provenance, reply_to, provenance_confidence, provenance_reasons_json) "
                            "VALUES (?,?,?,?,?,?,?,?,?,?,?)", fresh)
            # The raw WhatsApp inbox is untouched; derived classifications can be rebuilt.
            if not preserve_existing:
                con.executemany("UPDATE wa_pr_sources SET provenance=?,provenance_confidence=?,provenance_reasons_json=? "
                                "WHERE contact_id=? AND message_id=? AND import_id='legacy_inbox' "
                                "AND message_id NOT IN (SELECT message_id FROM wa_pr_owner_reviews)",
                                [(r[7], r[9], r[10], contact_id, r[5]) for r in rows if import_id == 'legacy_inbox'])
            if import_id == 'owner_attested':
                con.executemany("UPDATE wa_pr_sources SET provenance=?,provenance_confidence=?,provenance_reasons_json=? "
                                "WHERE contact_id=? AND message_id=? AND provenance NOT IN ('AUTO_GENERATED','AI_DRAFT')",
                                [(r[7], r[9], r[10], contact_id, r[5]) for r in rows])
            if any(r[3] == Direction.USER.value for r in fresh):
                con.execute("UPDATE wa_pr_evaluations SET approved_at=NULL WHERE contact_id=?", (contact_id,))
        return len(fresh)

    def sources(self, contact_id: str) -> list[ChatLine]:
        with self._conn() as con:
            rows = con.execute("SELECT * FROM wa_pr_sources WHERE contact_id = ? ORDER BY ts, id", (contact_id,)).fetchall()
        return [ChatLine(timestamp=r["ts"], sender="", direction=Direction(r["direction"]),
                         text=self.box.decrypt(r["text_enc"]), message_id=r["message_id"], origin=r["import_id"],
                         provenance=Authorship(r["provenance"]), reply_to=r["reply_to"],
                         provenance_confidence=r['provenance_confidence'],
                         provenance_reasons=json.loads(r['provenance_reasons_json'])) for r in rows]

    def record_legacy_audit(self, rows: list[tuple[str, str, str, float, list[str]]]) -> None:
        with self._lock, self._conn() as con:
            con.executemany("INSERT OR REPLACE INTO wa_pr_legacy_audit VALUES (?,?,?,?,?,?)",
                            [(mid, cid, prov, conf, json.dumps(reasons), time.time())
                             for mid, cid, prov, conf, reasons in rows])

    def review_legacy_rows(self, contact_id: str, decisions: dict[str, bool]) -> dict[str, int]:
        """Owner review changes only derived source metadata for this contact."""
        counts = {'APPROVED': 0, 'REJECTED': 0}
        with self._lock, self._conn() as con:
            for mid, approved in decisions.items():
                row = con.execute("SELECT provenance FROM wa_pr_sources WHERE contact_id=? AND message_id=? "
                                  "AND direction='USER'", (contact_id, mid)).fetchone()
                if not row or row[0] not in ('LEGACY_OWNER_LIKELY','VERIFIED_LEGACY_OWNER','REJECTED_LEGACY'):
                    continue
                original = con.execute("SELECT original_provenance FROM wa_pr_owner_reviews WHERE message_id=?", (mid,)).fetchone()
                target = 'VERIFIED_LEGACY_OWNER' if approved else 'REJECTED_LEGACY'
                now = time.time()
                con.execute("INSERT OR REPLACE INTO wa_pr_owner_reviews VALUES (?,?,?,?,?,?)",
                            (mid, contact_id, original[0] if original else 'LEGACY_OWNER_LIKELY',
                             target, 1, now))
                con.execute("UPDATE wa_pr_sources SET provenance=?,provenance_confidence=?,provenance_reasons_json=? "
                            "WHERE contact_id=? AND message_id=?", (target, 1.0 if approved else 0.0,
                            json.dumps(['owner_reviewed_legacy', 'approved' if approved else 'rejected']), contact_id, mid))
                counts['APPROVED' if approved else 'REJECTED'] += 1
            if counts['APPROVED'] or counts['REJECTED']:
                con.execute("UPDATE wa_pr_evaluations SET approved_at=NULL WHERE contact_id=?", (contact_id,))
        return counts

    def legacy_review_candidates(self, contact_id: str, limit: int = 35) -> list[dict[str, Any]]:
        with self._conn() as con:
            rows = con.execute("SELECT message_id,ts,text_enc,provenance_confidence FROM wa_pr_sources "
                               "WHERE contact_id=? AND direction='USER' AND provenance='LEGACY_OWNER_LIKELY' "
                               "ORDER BY ts,id", (contact_id,)).fetchall()
        if not rows:
            return []
        from jarvis.integrations.whatsapp.personal_reply import language as lang
        # Deterministic coverage of length, language, question and emoji modes,
        # then time-stratified fill. Only this contact's own outgoing text leaves.
        categories: dict[str, list] = {}
        decoded = []
        seen_text: set[str] = set()
        for row in rows:
            body = self.box.decrypt(row['text_enc'])
            normalized = ' '.join(body.casefold().split())
            if not normalized or normalized in seen_text:
                continue
            seen_text.add(normalized)
            decoded.append((row, body))
        with self._conn() as con:
            pair_times = {r[0] for r in con.execute(
                "SELECT ts FROM wa_pr_examples WHERE contact_id=? AND provenance='LEGACY_OWNER_LIKELY'",
                (contact_id,))}
        for row, body in decoded:
            category = ('short' if len(body.split()) <= 3 else 'long' if len(body.split()) >= 15 else 'medium')
            category += '_' + lang.detect(body).label
            if lang.emojis(body): category += '_emoji'
            if '?' in body: category += '_question'
            categories.setdefault(category, []).append((row, body))
        # Include scarce actual reply pairs first. A style sample with no
        # incoming counterpart cannot become a replay evaluation case.
        selected: list = [item for item in decoded if item[0]['ts'] in pair_times][:limit]
        for group in categories.values():
            candidate = group[len(group)//2]
            if candidate not in selected and len(selected) < limit:
                selected.append(candidate)
        if len(selected) < limit:
            remaining = [item for item in decoded if item not in selected]
            step = max(1, len(remaining) // max(1, limit-len(selected)))
            selected.extend(remaining[::step][:limit-len(selected)])
        selected = sorted(selected[:limit], key=lambda item: item[0]['ts'])
        return [{'message_id': r['message_id'], 'timestamp': r['ts'], 'text': text,
                 'confidence': r['provenance_confidence']} for r, text in selected]

    def record_draft_feedback(self, reply_id: int, contact_id: str, state: str, candidate: str,
                              final: str = '', edit_ratio: float | None = None, sent_message_id: str = '',
                              style_delta: dict | None = None) -> None:
        with self._lock, self._conn() as con:
            values = (reply_id, contact_id, state, self.box.encrypt(candidate),
                      self.box.encrypt(final) if final else None, edit_ratio, sent_message_id or None,
                      time.time(), json.dumps(style_delta or {}))
            columns = "(reply_id,contact_id,state,candidate_enc,final_enc,edit_ratio,sent_message_id,recorded_at,style_delta_json)"
            con.execute(f"INSERT INTO wa_pr_draft_feedback_events {columns} VALUES (?,?,?,?,?,?,?,?,?)", values)
            con.execute(f"INSERT OR REPLACE INTO wa_pr_draft_feedback {columns} VALUES (?,?,?,?,?,?,?,?,?)", values)

    def save_holdout_review_case(self, contact_id: str, incoming: str, candidate: str,
                                 owner_actual: str, timestamp: float) -> str:
        # Distinct candidate revisions need separate review records. Preserve any
        # owner rating on an earlier replay instead of silently replacing it.
        case_id = hashlib.sha256(f'{contact_id}|{timestamp}|{owner_actual}|{candidate}'.encode()).hexdigest()[:24]
        with self._lock, self._conn() as con:
            con.execute("INSERT OR IGNORE INTO wa_pr_holdout_review_cases "
                        "(case_id,contact_id,incoming_enc,candidate_enc,owner_enc,generated_at) "
                        "VALUES (?,?,?,?,?,?)",
                        (case_id, contact_id, self.box.encrypt(incoming), self.box.encrypt(candidate),
                         self.box.encrypt(owner_actual), time.time()))
        return case_id

    def holdout_review_cases(self, contact_id: str, limit: int = 5) -> list[dict[str, Any]]:
        with self._conn() as con:
            rows = con.execute("SELECT * FROM wa_pr_holdout_review_cases WHERE contact_id=? "
                               "ORDER BY generated_at DESC LIMIT ?", (contact_id, max(limit * 4, 20))).fetchall()
        unique: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for r in rows:
            incoming = self.box.decrypt(r['incoming_enc'])
            actual = self.box.decrypt(r['owner_enc'])
            key = (incoming, actual)
            if key in seen:
                continue
            seen.add(key)
            unique.append({'case_id': r['case_id'], 'incoming': incoming,
                           'jarvis': self.box.decrypt(r['candidate_enc']),
                           'owner_actual': actual, 'rating': r['rating'],
                           'dimensions': json.loads(r['dimensions_json'] or '{}')})
            if len(unique) >= limit:
                break
        return unique

    def rate_holdout_review_case(self, contact_id: str, case_id: str, rating: str,
                                 dimensions: dict[str, bool | None] | None = None) -> bool:
        if rating not in ('EXACT_STYLE', 'GOOD', 'OKAY', 'BAD_STYLE', 'WRONG_MEANING'):
            raise ValueError('Unsupported holdout rating')
        allowed = {'semantic_correct', 'dyadic_correct', 'language_match',
                   'emoji_appropriate', 'length_appropriate'}
        if dimensions is not None and (set(dimensions) - allowed or
                                       any(value is not None and type(value) is not bool for value in dimensions.values())):
            raise ValueError('Unsupported holdout rating dimensions')
        with self._lock, self._conn() as con:
            result = con.execute("UPDATE wa_pr_holdout_review_cases SET rating=?,dimensions_json=? "
                                 "WHERE contact_id=? AND case_id=?",
                                 (rating, json.dumps(dimensions or {}), contact_id, case_id))
            return result.rowcount == 1

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
                "INSERT INTO wa_pr_examples(contact_id, context_enc, reply_enc, ts, source, split, vector, created_at, provenance_verified, provenance, evidence_weight) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [(contact_id, self.box.encrypt(e.context), self.box.encrypt(e.reply), e.timestamp, ExampleSource(e.source).value,
                  e.split, vectors[i].astype(np.float16).tobytes(), now,
                  int(e.provenance not in (Authorship.LEGACY_OWNER_LIKELY, Authorship.UNKNOWN)), Authorship(e.provenance).value,
                  e.evidence_weight) for i, e in enumerate(examples)])

    def source_fingerprint(self, contact_id: str) -> str:
        """Stable digest of persisted source identity, evidence and text ciphertext."""
        with self._conn() as con:
            return self._source_fingerprint_conn(con, contact_id)

    @staticmethod
    def _source_fingerprint_conn(con: sqlite3.Connection, contact_id: str) -> str:
        digest = hashlib.sha256()
        for row in con.execute("SELECT message_id,ts,direction,provenance,reply_to,text_enc "
                               "FROM wa_pr_sources WHERE contact_id=? ORDER BY ts,id", (contact_id,)):
            digest.update(json.dumps(tuple(row), ensure_ascii=False, separators=(',', ':')).encode())
            digest.update(b'\n')
        return digest.hexdigest()

    def brain_state(self, contact_id: str = "") -> dict[str, Any]:
        with self._conn() as con:
            version, published_at = con.execute(
                "SELECT active_version,published_at FROM wa_brain_index WHERE id=1").fetchone()
            row = con.execute("SELECT * FROM wa_brain_contact_state WHERE contact_id=?", (contact_id,)).fetchone() if contact_id else None
        return {"active_version": version, "published_at": published_at,
                "contact": ({**dict(row), "derived": json.loads(row['derived_json'])} if row else None)}

    def publish_brain_snapshots(self, snapshots: list[dict[str, Any]], job_id: str = "") -> int:
        """Validate then replace every staged contact in one SQLite transaction.

        Readers see either the previous examples/profiles or the new version.
        Source history and owner review decisions are never deleted here.
        """
        if not snapshots:
            return self.brain_state()['active_version']
        for snapshot in snapshots:
            examples, vectors = snapshot['examples'], snapshot['vectors']
            if vectors.shape != (len(examples), VECTOR_DIM) or not np.isfinite(vectors).all():
                raise ValueError('Invalid staged embeddings')
            if any(e.contact_id != snapshot['contact_id'] for e in examples):
                raise ValueError('Cross-contact staged example')
        # Encrypt and pack before taking the write lock: the transaction only swaps rows, so other writers
        # (incoming messages, the ledger, the dashboard) wait milliseconds, not the length of a whole build.
        staged_at = time.time()
        packed = {snapshot['contact_id']: [
            (snapshot['contact_id'], self.box.encrypt(e.context), self.box.encrypt(e.reply), e.timestamp,
             ExampleSource(e.source).value, e.split, snapshot['vectors'][i].astype(np.float16).tobytes(), staged_at,
             int(e.provenance not in (Authorship.LEGACY_OWNER_LIKELY, Authorship.UNKNOWN)),
             Authorship(e.provenance).value, e.evidence_weight) for i, e in enumerate(snapshot['examples'])]
            for snapshot in snapshots}
        with self._lock, self._conn() as con:
            con.execute('BEGIN IMMEDIATE')
            old_version = con.execute('SELECT active_version FROM wa_brain_index WHERE id=1').fetchone()[0]
            new_version = old_version + 1
            for snapshot in snapshots:
                cid = snapshot['contact_id']
                if self._source_fingerprint_conn(con, cid) != snapshot['source_hash']:
                    raise ValueError('Sources changed during intelligence build; retry safely')
                con.execute("DELETE FROM wa_pr_examples WHERE contact_id=? AND source IN ('IMPORT','LIVE_USER','USER_EDITED')", (cid,))
                now = time.time()
                con.executemany(
                    "INSERT INTO wa_pr_examples(contact_id,context_enc,reply_enc,ts,source,split,vector,created_at,provenance_verified,provenance,evidence_weight) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)", packed[cid])
                profile = snapshot['profile']
                if profile and profile.messages_analyzed:
                    pv = (con.execute('SELECT max(profile_version) FROM wa_pr_profile_versions WHERE contact_id=?',
                                      (cid,)).fetchone()[0] or 0) + 1
                    profile.profile_version = pv
                    profile.updated_at = now
                    blob = self.box.encrypt(json.dumps(profile.to_dict(), ensure_ascii=False))
                    con.execute('INSERT INTO wa_pr_profile_versions VALUES(?,?,?,?)', (cid, pv, blob, now))
                    evidence_class = 'VERIFIED' if profile.verified_messages else 'LEGACY'
                    con.execute("INSERT OR REPLACE INTO wa_pr_profiles(contact_id,display_name,profile_enc,profile_version,updated_at,provenance_verified,evidence_class) "
                                "VALUES(?,?,?,?,?,?,?)", (cid, profile.display_name, blob, pv, now,
                                                         int(bool(profile.verified_messages)), evidence_class))
                else:
                    con.execute('DELETE FROM wa_pr_profiles WHERE contact_id=?', (cid,))
                con.execute('UPDATE wa_pr_evaluations SET approved_at=NULL WHERE contact_id=?', (cid,))
                con.execute('INSERT OR REPLACE INTO wa_brain_contact_state VALUES(?,?,?,?,?)',
                            (cid, snapshot['source_hash'], new_version,
                             json.dumps(snapshot['derived'], ensure_ascii=False), now))
            con.execute('UPDATE wa_brain_index SET active_version=?,published_at=? WHERE id=1',
                        (new_version, time.time()))
            if job_id:
                con.execute("UPDATE wa_brain_jobs SET status='RELOADING',stage='HOT_RELOAD',new_index_version=?,updated_at=? "
                            "WHERE job_id=?", (new_version, time.time(), job_id))
        for snapshot in snapshots:
            self._profile_cache.pop(snapshot['contact_id'], None)
        return new_version

    def add_example(self, example: ReplyExample, vector: np.ndarray) -> int:
        if example.source not in (ExampleSource.IMPORT, ExampleSource.LIVE_USER, ExampleSource.USER_EDITED):
            raise ValueError("only owner-authored or owner-approved text may become a style example")
        if example.provenance not in (Authorship.USER_TYPED, Authorship.VERIFIED_MANUAL_OWNER_SEND,
                                      Authorship.USER_EDITED_AI_DRAFT, Authorship.USER_APPROVED_AI_DRAFT,
                                      Authorship.VERIFIED_LEGACY_OWNER, Authorship.LEGACY_OWNER_LIKELY) or example.evidence_weight <= 0:
            raise ValueError("a style example needs positive owner provenance evidence")
        with self._lock, self._conn() as con:
            cur = con.execute(
                "INSERT INTO wa_pr_examples(contact_id, context_enc, reply_enc, ts, source, split, vector, created_at, provenance_verified, provenance, evidence_weight) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (example.contact_id, self.box.encrypt(example.context), self.box.encrypt(example.reply), example.timestamp,
                 ExampleSource(example.source).value, example.split, vector.astype(np.float16).tobytes(), time.time(),
                 int(example.provenance != Authorship.LEGACY_OWNER_LIKELY),
                 Authorship(example.provenance).value, example.evidence_weight))
            return int(cur.lastrowid)

    def record_edit(self, reply_id: int, contact_id: str, candidate: str, final: str,
                    sent_message_id: str, edit_ratio: float) -> None:
        if not sent_message_id or not final.strip() or candidate.strip() == final.strip():
            raise ValueError("Only a changed, actually sent owner edit is feedback evidence")
        with self._lock, self._conn() as con:
            con.execute("INSERT OR IGNORE INTO wa_pr_feedback "
                        "(reply_id,contact_id,candidate_enc,final_enc,edit_ratio,sent_message_id,created_at) "
                        "VALUES (?,?,?,?,?,?,?)", (reply_id, contact_id, self.box.encrypt(candidate),
                        self.box.encrypt(final), max(0.0, min(1.0, edit_ratio)), sent_message_id, time.time()))

    def auto_reply_evaluated(self, contact_id: str) -> bool:
        with self._conn() as conn:
            row = conn.execute("SELECT samples,metrics_json,approved_at FROM wa_pr_evaluations WHERE contact_id=?",
                               (contact_id,)).fetchone()
            verified = conn.execute("SELECT count(*) FROM wa_pr_sources WHERE contact_id=? AND direction='USER' "
                                    "AND provenance IN ('VERIFIED_MANUAL_OWNER_SEND','USER_EDITED_AI_DRAFT')", (contact_id,)).fetchone()[0]
        if verified < 20:
            return False
        if not row or row["samples"] < 20 or row["approved_at"] is None:
            return False
        try:
            metrics = json.loads(row["metrics_json"])
        except (TypeError, ValueError):
            return False
        return bool(metrics.get("unsafe_auto_send_count") == 0 and metrics.get("generated", 0) >= 20)

    def approve_offline_evaluation(self, contact_id: str) -> bool:
        with self._lock, self._conn() as conn:
            verified = conn.execute("SELECT count(*) FROM wa_pr_sources WHERE contact_id=? AND direction='USER' "
                                    "AND provenance IN ('VERIFIED_MANUAL_OWNER_SEND','USER_EDITED_AI_DRAFT')", (contact_id,)).fetchone()[0]
            if verified < 20:
                return False
            row = conn.execute("SELECT samples,metrics_json FROM wa_pr_evaluations WHERE contact_id=?",
                               (contact_id,)).fetchone()
            if not row or row["samples"] < 20:
                return False
            try:
                report = json.loads(row["metrics_json"])
            except (TypeError, ValueError):
                return False
            if report.get("unsafe_auto_send_count") != 0 or report.get("generated", 0) < 20:
                return False
            conn.execute("UPDATE wa_pr_evaluations SET approved_at=? WHERE contact_id=?", (time.time(), contact_id))
            return True

    def examples(self, contact_id: str, splits: tuple[str, ...] = ("TRAIN",)) -> tuple[list[ReplyExample], np.ndarray]:
        marks = ",".join("?" * len(splits))
        with self._conn() as con:
            rows = con.execute(f"SELECT * FROM wa_pr_examples WHERE contact_id = ? AND split IN ({marks}) "
                               "AND source IN ('IMPORT','LIVE_USER','USER_EDITED') "
                               "AND provenance IN ('USER_TYPED','VERIFIED_MANUAL_OWNER_SEND','USER_EDITED_AI_DRAFT',"
                               "'USER_APPROVED_AI_DRAFT','VERIFIED_LEGACY_OWNER','LEGACY_OWNER_LIKELY') "
                               "ORDER BY ts, id",
                               (contact_id, *splits)).fetchall()
        exs, vecs = [], []
        for r in rows:
            exs.append(ReplyExample(contact_id=r["contact_id"], context=self.box.decrypt(r["context_enc"]),
                                    reply=self.box.decrypt(r["reply_enc"]), timestamp=r["ts"], source=ExampleSource(r["source"]),
                                    split=r["split"], example_id=r["id"], provenance=Authorship(r['provenance']),
                                    evidence_weight=r['evidence_weight']))
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
            evidence_class = 'VERIFIED' if profile.verified_messages else 'LEGACY' if profile.legacy_messages else 'UNKNOWN'
            con.execute("INSERT OR REPLACE INTO wa_pr_profiles(contact_id, display_name, profile_enc, profile_version, updated_at, provenance_verified, evidence_class) "
                        "VALUES (?,?,?,?,?,?,?)", (profile.contact_id, profile.display_name, blob, profile.profile_version,
                                                    profile.updated_at, int(bool(profile.verified_messages)), evidence_class))
        self.upsert_contact(profile.contact_id, profile.display_name)
        self._profile_cache.pop(profile.contact_id, None)
        return profile.profile_version

    def load_profile(self, contact_id: str) -> Optional[ContactStyleProfile]:
        hit = self._profile_cache.get(contact_id)
        if hit and time.time() - hit[0] < 60:
            return ContactStyleProfile.from_dict(hit[1].to_dict()) if hit[1] else None
        with self._conn() as con:
            row = con.execute("SELECT profile_enc FROM wa_pr_profiles WHERE contact_id = ? "
                              "AND evidence_class IN ('VERIFIED','LEGACY')",
                              (contact_id,)).fetchone()
        if not row:
            self._profile_cache[contact_id] = (time.time(), None)
            return None
        text = self.box.decrypt(row["profile_enc"])
        profile = ContactStyleProfile.from_dict(json.loads(text)) if text else None
        self._profile_cache[contact_id] = (time.time(), profile)
        return ContactStyleProfile.from_dict(profile.to_dict()) if profile else None

    def profile_versions(self, contact_id: str) -> list[int]:
        with self._conn() as con:
            return [r[0] for r in con.execute("SELECT profile_version FROM wa_pr_profile_versions WHERE contact_id = ? "
                                              "ORDER BY profile_version", (contact_id,))]

    def clear_profile(self, contact_id: str, keep_sources: bool = False) -> None:
        self._profile_cache.pop(contact_id, None)
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
                        "revoked_at, include_untrained, note) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (grant.grant_id, grant.scope.value, json.dumps(grant.contact_ids), grant.mode.value, grant.enabled_at,
                         grant.expires_at, 1 if grant.granted_by_user else 0, grant.revoked_at, 1 if grant.include_untrained else 0,
                         grant.note or ""))

    def grants(self, include_inactive: bool = False) -> list[AutoReplyGrant]:
        q = "SELECT * FROM wa_pr_grants" + ("" if include_inactive else " WHERE revoked_at IS NULL") + " ORDER BY enabled_at"
        with self._conn() as con:
            rows = con.execute(q).fetchall()
        return [AutoReplyGrant(grant_id=r["grant_id"], scope=GrantScope(r["scope"]), contact_ids=json.loads(r["contact_ids"]),
                               enabled_at=r["enabled_at"], expires_at=r["expires_at"], mode=ReplyMode(r["mode"]),
                               granted_by_user=bool(r["granted_by_user"]), revoked_at=r["revoked_at"],
                               include_untrained=bool(r["include_untrained"]),
                               note=(r["note"] if "note" in r.keys() else "") or "") for r in rows]

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
