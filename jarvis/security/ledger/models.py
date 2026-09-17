from __future__ import annotations

from enum import StrEnum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from jarvis.tools.base import RiskLevel, IdempotencyClass

class LedgerState(StrEnum):
    PREPARED = "PREPARED"
    STARTED = "STARTED"
    VERIFIED = "VERIFIED"
    FAILED_SAFE_TO_RETRY = "FAILED_SAFE_TO_RETRY"
    UNCERTAIN = "UNCERTAIN"
    COMMITTED = "COMMITTED"
    CANCELLED = "CANCELLED"

class LedgerEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str
    fingerprint: str
    request_id: str
    graph_id: str
    node_id: str
    tool: str
    risk: RiskLevel
    idempotency: IdempotencyClass
    status: LedgerState
    args_hash: str
    confirmation_ticket: str | None = None
    method: str = "native"
    created_at: float = 0.0
    started_at: float | None = None
    verified_at: float | None = None
    finished_at: float | None = None
    error_class: str | None = None
    verification_json: str | None = None
    output_json: str | None = None

