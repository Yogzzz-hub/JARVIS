from __future__ import annotations

from enum import StrEnum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from jarvis.tools.base import RiskLevel, IdempotencyClass

class LedgerState(StrEnum):
    REQUESTED = "REQUESTED"
    PREPARED = "PREPARED"
    AUTHORISED = "AUTHORISED"
    STARTED = "STARTED"
    EXTERNALLY_ACKNOWLEDGED = "EXTERNALLY_ACKNOWLEDGED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    FAILED_SAFE_TO_RETRY = "FAILED_SAFE_TO_RETRY"
    UNCERTAIN = "UNCERTAIN"
    OUTCOME_UNKNOWN = "UNCERTAIN"  # Alias for UNCERTAIN / outcome-unknown
    COMMITTED = "COMMITTED"
    CANCELLED = "CANCELLED"

class LedgerEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

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
    idempotency_key: str | None = None
    provider_ack_json: str | None = None
    target_references_json: str | None = None

