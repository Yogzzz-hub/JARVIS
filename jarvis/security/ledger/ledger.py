from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from jarvis.security.ledger.models import LedgerEntry, LedgerState
from jarvis.tools.base import IdempotencyClass, RiskLevel, VerificationResult

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "db" / "jarvis.db"

class ActionLedger:
    """Action Ledger providing durable persistence and duplicate protection
    for all state-changing and external-effect operations.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._memory_cache: dict[str, LedgerEntry] = {}
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=15000")
        return conn

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS action_ledger (
                    action_id TEXT PRIMARY KEY,
                    fingerprint TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    tool TEXT NOT NULL,
                    risk TEXT NOT NULL,
                    idempotency TEXT NOT NULL,
                    status TEXT NOT NULL,
                    args_hash TEXT NOT NULL,
                    confirmation_ticket TEXT,
                    method TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    verified_at TIMESTAMP,
                    finished_at TIMESTAMP,
                    error_class TEXT,
                    verification_json TEXT,
                    idempotency_key TEXT,
                    provider_ack_json TEXT,
                    target_references_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_action_ledger_fingerprint ON action_ledger(fingerprint);
                CREATE INDEX IF NOT EXISTS idx_action_ledger_status ON action_ledger(status);
                CREATE INDEX IF NOT EXISTS idx_action_ledger_graph ON action_ledger(graph_id);
                """
            )
            # Safe schema migration for pre-existing tables
            cursor = conn.cursor()
            existing_cols = {col[1] for col in cursor.execute("PRAGMA table_info(action_ledger)").fetchall()}
            for col_name in ("idempotency_key", "provider_ack_json", "target_references_json"):
                if col_name not in existing_cols:
                    cursor.execute(f"ALTER TABLE action_ledger ADD COLUMN {col_name} TEXT")
            conn.commit()

    def _is_critical_path(self, risk: RiskLevel) -> bool:
        return risk in (RiskLevel.EXTERNAL_EFFECT, RiskLevel.DESTRUCTIVE, RiskLevel.PRIVILEGED)

    def check_duplicate(
        self,
        fingerprint: str,
        request_id: str = "",
        risk: RiskLevel | None = None,
    ) -> tuple[bool, LedgerEntry | None]:
        """Checks if an identical action was already executed or is currently underway."""
        # 1. Check in-memory cache first for microsecond response
        cached = self._memory_cache.get(fingerprint)
        if cached:
            # Reversible/read-only operations from different user requests should not be suppressed
            if cached.risk in (RiskLevel.READ_ONLY, RiskLevel.REVERSIBLE) and request_id and cached.request_id != request_id:
                return False, None
            if cached.status in (LedgerState.VERIFIED, LedgerState.COMMITTED):
                # A verified action from a different user request without an explicit idempotency key
                # should not permanently suppress subsequent new user actions
                if request_id and cached.request_id != request_id and not cached.idempotency_key:
                    return False, None
                return True, cached
            if cached.status in (LedgerState.STARTED, LedgerState.UNCERTAIN):
                return True, cached

        # 2. Check SQLite ledger
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM action_ledger WHERE fingerprint = ? ORDER BY created_at DESC LIMIT 1",
                (fingerprint,),
            ).fetchone()

            if row:
                row_risk = RiskLevel(row["risk"])
                if row_risk in (RiskLevel.READ_ONLY, RiskLevel.REVERSIBLE) and request_id and row["request_id"] != request_id:
                    return False, None

                entry = self._row_to_entry(row)
                self._memory_cache[fingerprint] = entry
                if entry.status in (LedgerState.VERIFIED, LedgerState.COMMITTED):
                    if request_id and entry.request_id != request_id and not entry.idempotency_key:
                        return False, None
                    return True, entry
                if entry.status in (LedgerState.STARTED, LedgerState.UNCERTAIN):
                    return True, entry

        return False, None

    def prepare_action(
        self,
        action_id: str,
        fingerprint: str,
        request_id: str,
        graph_id: str,
        node_id: str,
        tool: str,
        risk: RiskLevel,
        idempotency: IdempotencyClass,
        args_hash: str,
        confirmation_ticket: str | None = None,
        method: str = "native",
        idempotency_key: str | None = None,
        target_references_json: str | None = None,
    ) -> LedgerEntry:
        """Records action intent in PREPARED state before any execution starts."""
        now = time.time()
        entry = LedgerEntry(
            action_id=action_id,
            fingerprint=fingerprint,
            request_id=request_id,
            graph_id=graph_id,
            node_id=node_id,
            tool=tool,
            risk=risk,
            idempotency=idempotency,
            status=LedgerState.PREPARED,
            args_hash=args_hash,
            confirmation_ticket=confirmation_ticket,
            method=method,
            created_at=now,
            idempotency_key=idempotency_key,
            target_references_json=target_references_json,
        )
        self._memory_cache[fingerprint] = entry

        # Critical path: durable write to SQLite before execution
        if self._is_critical_path(risk):
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO action_ledger
                    (action_id, fingerprint, request_id, graph_id, node_id, tool, risk, idempotency, status, args_hash, confirmation_ticket, method, idempotency_key, target_references_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        action_id, fingerprint, request_id, graph_id, node_id, tool,
                        risk.value, idempotency.value, LedgerState.PREPARED.value,
                        args_hash, confirmation_ticket, method, idempotency_key, target_references_json
                    ),
                )
                conn.commit()

        return entry

    def claim_action(
        self,
        action_id: str,
        fingerprint: str,
        risk: RiskLevel,
        expected_states: tuple[LedgerState, ...] = (LedgerState.PREPARED, LedgerState.AUTHORISED),
        new_state: LedgerState = LedgerState.STARTED,
        idempotency_key: str | None = None,
    ) -> bool:
        """Atomically claims a prepared action using compare-and-swap on SQLite.
        Prevents race conditions where multiple workers try to execute the same action.
        """
        now = time.time()
        claimed = True
        if self._is_critical_path(risk):
            with self._get_conn() as conn:
                placeholders = ",".join("?" for _ in expected_states)
                sql = f"""
                    UPDATE action_ledger
                    SET status = ?, started_at = CURRENT_TIMESTAMP,
                        idempotency_key = coalesce(?, idempotency_key)
                    WHERE action_id = ? AND status IN ({placeholders})
                """
                params = [new_state.value, idempotency_key, action_id] + [s.value for s in expected_states]
                cursor = conn.execute(sql, params)
                conn.commit()
                claimed = cursor.rowcount > 0

        if claimed:
            if fingerprint in self._memory_cache:
                entry = self._memory_cache[fingerprint]
                entry.status = new_state
                entry.started_at = now
                if idempotency_key:
                    entry.idempotency_key = idempotency_key
        return claimed

    def start_action(
        self,
        action_id: str,
        fingerprint: str,
        risk: RiskLevel,
        idempotency_key: str | None = None,
    ) -> bool:
        """Transitions action to STARTED state as the external side effect begins."""
        return self.claim_action(
            action_id=action_id,
            fingerprint=fingerprint,
            risk=risk,
            expected_states=(LedgerState.PREPARED, LedgerState.AUTHORISED),
            new_state=LedgerState.STARTED,
            idempotency_key=idempotency_key,
        )

    def record_external_ack(
        self,
        action_id: str,
        fingerprint: str,
        risk: RiskLevel,
        provider_ack_json: str | None = None,
    ) -> None:
        """Records that an external service acknowledged receipt of the mutation before verification."""
        if fingerprint in self._memory_cache:
            entry = self._memory_cache[fingerprint]
            entry.status = LedgerState.EXTERNALLY_ACKNOWLEDGED
            entry.provider_ack_json = provider_ack_json

        if self._is_critical_path(risk):
            with self._get_conn() as conn:
                conn.execute(
                    """
                    UPDATE action_ledger
                    SET status = ?, provider_ack_json = ?
                    WHERE action_id = ?
                    """,
                    (LedgerState.EXTERNALLY_ACKNOWLEDGED.value, provider_ack_json, action_id),
                )
                conn.commit()

    def record_outcome(
        self,
        action_id: str,
        fingerprint: str,
        risk: RiskLevel,
        status: LedgerState,
        verification_json: str | None = None,
        error_class: str | None = None,
        output_json: str | None = None,
    ) -> None:
        """Records post-execution outcome (VERIFIED, FAILED_SAFE_TO_RETRY, UNCERTAIN, COMMITTED)."""
        now = time.time()
        if fingerprint in self._memory_cache:
            entry = self._memory_cache[fingerprint]
            entry.status = status
            entry.finished_at = now
            entry.verification_json = verification_json
            entry.error_class = error_class
            entry.output_json = output_json
            if status == LedgerState.VERIFIED:
                entry.verified_at = now

        # Write to SQLite (synchronous for critical path, best-effort for others)
        try:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    UPDATE action_ledger
                    SET status = ?, finished_at = CURRENT_TIMESTAMP, verification_json = ?, error_class = ?
                    WHERE action_id = ?
                    """,
                    (status.value, verification_json, error_class, action_id),
                )
                conn.commit()
        except sqlite3.OperationalError:
            pass

    def _row_to_entry(self, row: sqlite3.Row) -> LedgerEntry:
        keys = row.keys()
        return LedgerEntry(
            action_id=row["action_id"],
            fingerprint=row["fingerprint"],
            request_id=row["request_id"],
            graph_id=row["graph_id"],
            node_id=row["node_id"],
            tool=row["tool"],
            risk=RiskLevel(row["risk"]),
            idempotency=IdempotencyClass(row["idempotency"]),
            status=LedgerState(row["status"]),
            args_hash=row["args_hash"],
            confirmation_ticket=row["confirmation_ticket"],
            method=row["method"],
            created_at=time.time(),
            error_class=row["error_class"],
            verification_json=row["verification_json"],
            idempotency_key=row["idempotency_key"] if "idempotency_key" in keys else None,
            provider_ack_json=row["provider_ack_json"] if "provider_ack_json" in keys else None,
            target_references_json=row["target_references_json"] if "target_references_json" in keys else None,
        )

    def get_entry_by_id(self, action_id: str) -> LedgerEntry | None:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM action_ledger WHERE action_id = ?", (action_id,)).fetchone()
            if row:
                return self._row_to_entry(row)
        return None

    def get_unresolved_actions(self) -> list[LedgerEntry]:
        """Returns actions left in PREPARED, STARTED, or UNCERTAIN states for startup recovery."""
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM action_ledger WHERE status IN (?, ?, ?) ORDER BY created_at ASC",
                (LedgerState.PREPARED.value, LedgerState.STARTED.value, LedgerState.UNCERTAIN.value),
            ).fetchall()

            return [self._row_to_entry(row) for row in rows]
