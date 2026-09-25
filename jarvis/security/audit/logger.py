from __future__ import annotations

import logging
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from jarvis.tools.base import RiskLevel

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "db" / "jarvis.db"

# Regex patterns for credential and secret redaction
SENSITIVE_PATTERNS = [
    (re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?([^'\"\s]+)"), r"\1: [REDACTED]"),
    (re.compile(r"(?i)(token|bearer|api[_-]?key|secret)\s*[:=]\s*['\"]?([^'\"\s]+)"), r"\1: [REDACTED]"),
    (re.compile(r"(?i)\bbearer\s+[a-zA-Z0-9_\-\.]{15,}\b"), "Bearer [REDACTED]"),
]

def redact_sensitive_text(text: str) -> str:
    """Redacts secrets, tokens, and credentials from log strings."""
    redacted = text
    for pattern, repl in SENSITIVE_PATTERNS:
        redacted = pattern.sub(repl, redacted)
    return redacted

class AuditEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit_id: str
    request_id: str
    graph_id: str
    node_id: str
    timestamp: float = Field(default_factory=time.time)
    tool: str
    method: str
    risk: RiskLevel
    decision: str
    confirmation_ticket_id: str | None = None
    action_fingerprint: str
    result_status: str
    verification_summary: str | None = None
    duration_ms: float = 0.0

class AuditLogger:
    """Append-only, security-hardened audit logger with automatic credential redaction."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
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
                CREATE TABLE IF NOT EXISTS audit_log (
                    audit_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    tool TEXT NOT NULL,
                    method TEXT NOT NULL,
                    risk TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    confirmation_ticket_id TEXT,
                    action_fingerprint TEXT NOT NULL,
                    result_status TEXT NOT NULL,
                    verification_summary TEXT,
                    duration_ms REAL DEFAULT 0.0
                );
                CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
                CREATE INDEX IF NOT EXISTS idx_audit_log_tool ON audit_log(tool);
                """
            )
            conn.commit()

    def log(
        self,
        request_id: str,
        graph_id: str,
        node_id: str,
        tool: str,
        method: str,
        risk: RiskLevel,
        decision: str,
        action_fingerprint: str,
        result_status: str,
        confirmation_ticket_id: str | None = None,
        verification_summary: str | None = None,
        duration_ms: float = 0.0,
        sync_write: bool = False,
    ) -> AuditEntry:
        audit_id = f"aud_{uuid.uuid4().hex[:12]}"
        redacted_summary = redact_sensitive_text(verification_summary) if verification_summary else None

        entry = AuditEntry(
            audit_id=audit_id,
            request_id=request_id,
            graph_id=graph_id,
            node_id=node_id,
            tool=tool,
            method=method,
            risk=risk,
            decision=decision,
            confirmation_ticket_id=confirmation_ticket_id,
            action_fingerprint=action_fingerprint,
            result_status=result_status,
            verification_summary=redacted_summary,
            duration_ms=duration_ms,
        )

        for attempt in range(5):
            try:
                with self._get_conn() as conn:
                    conn.execute(
                        """
                        INSERT INTO audit_log
                        (audit_id, request_id, graph_id, node_id, tool, method, risk, decision, confirmation_ticket_id, action_fingerprint, result_status, verification_summary, duration_ms)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            entry.audit_id, entry.request_id, entry.graph_id, entry.node_id,
                            entry.tool, entry.method, entry.risk.value, entry.decision,
                            entry.confirmation_ticket_id, entry.action_fingerprint,
                            entry.result_status, entry.verification_summary, entry.duration_ms
                        ),
                    )
                    conn.commit()
                break
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() and attempt < 4:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                logging.getLogger("jarvis.audit").warning("Failed to record audit log: %s", e)
                break

        return entry
