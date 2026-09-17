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

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
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
                    verification_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_action_ledger_fingerprint ON action_ledger(fingerprint);
                CREATE INDEX IF NOT EXISTS idx_action_ledger_status ON action_ledger(status);
                CREATE INDEX IF NOT EXISTS idx_action_ledger_graph ON action_ledger(graph_id);
                """
            )
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
                return True, cached
            if cached.status in (LedgerState.STARTED, LedgerState.UNCERTAIN):
                return True, cached

        # 2. Check SQLite ledger
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM action_ledger WHERE fingerprint = ? ORDER BY created_at DESC LIMIT 1",
                (fingerprint,),
            ).fetchone()

            if row:
                row_risk = RiskLevel(row["risk"])
                if row_risk in (RiskLevel.READ_ONLY, RiskLevel.REVERSIBLE) and request_id and row["request_id"] != request_id:
                    return False, None

                entry = LedgerEntry(
                    action_id=row["action_id"],
                    fingerprint=row["fingerprint"],
                    request_id=row["request_id"],
                    graph_id=row["graph_id"],
                    node_id=row["node_id"],
                    tool=row["tool"],
                    risk=row_risk,
                    idempotency=IdempotencyClass(row["idempotency"]),
                    status=LedgerState(row["status"]),
                    args_hash=row["args_hash"],
                    confirmation_ticket=row["confirmation_ticket"],
                    method=row["method"],
                    created_at=time.time(),
                    error_class=row["error_class"],
                    verification_json=row["verification_json"],
                )
                self._memory_cache[fingerprint] = entry
                if entry.status in (LedgerState.VERIFIED, LedgerState.COMMITTED, LedgerState.STARTED, LedgerState.UNCERTAIN):
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
        )
        self._memory_cache[fingerprint] = entry

        # Critical path: durable write to SQLite before execution
        if self._is_critical_path(risk):
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO action_ledger
                    (action_id, fingerprint, request_id, graph_id, node_id, tool, risk, idempotency, status, args_hash, confirmation_ticket, method)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        action_id, fingerprint, request_id, graph_id, node_id, tool,
                        risk.value, idempotency.value, LedgerState.PREPARED.value,
                        args_hash, confirmation_ticket, method
                    ),
                )
                conn.commit()

        return entry

    def start_action(self, action_id: str, fingerprint: str, risk: RiskLevel) -> None:
        """Transitions action to STARTED state as the external side effect begins."""
        now = time.time()
        if fingerprint in self._memory_cache:
            entry = self._memory_cache[fingerprint]
            entry.status = LedgerState.STARTED
            entry.started_at = now

        if self._is_critical_path(risk):
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE action_ledger SET status = ?, started_at = CURRENT_TIMESTAMP WHERE action_id = ?",
                    (LedgerState.STARTED.value, action_id),
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
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE action_ledger
                SET status = ?, finished_at = CURRENT_TIMESTAMP, verification_json = ?, error_class = ?
                WHERE action_id = ?
                """,
                (status.value, verification_json, error_class, action_id),
            )
            conn.commit()

    def get_entry_by_id(self, action_id: str) -> LedgerEntry | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM action_ledger WHERE action_id = ?", (action_id,)).fetchone()
            if row:
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
                )
        return None

    def get_unresolved_actions(self) -> list[LedgerEntry]:
        """Returns actions left in PREPARED, STARTED, or UNCERTAIN states for startup recovery."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM action_ledger WHERE status IN (?, ?, ?) ORDER BY created_at ASC",
                (LedgerState.PREPARED.value, LedgerState.STARTED.value, LedgerState.UNCERTAIN.value),
            ).fetchall()

            entries = []
            for row in rows:
                entries.append(LedgerEntry(
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
                ))
            return entries
