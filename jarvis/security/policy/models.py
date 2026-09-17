from __future__ import annotations

from enum import StrEnum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from jarvis.tools.base import RiskLevel

class PolicyDecisionType(StrEnum):
    ALLOW = "ALLOW"
    REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"
    DENY = "DENY"
    PAUSE_FOR_USER = "PAUSE_FOR_USER"

class PolicyReasonCode(StrEnum):
    DEFAULT_ALLOW = "DEFAULT_ALLOW"
    EXTERNAL_EFFECT_CONFIRM = "EXTERNAL_EFFECT_CONFIRM"
    DESTRUCTIVE_CONFIRM = "DESTRUCTIVE_CONFIRM"
    PRIVILEGED_CONFIRM = "PRIVILEGED_CONFIRM"
    PROTECTED_PATH = "PROTECTED_PATH"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    UAC_REQUIRED = "UAC_REQUIRED"
    UNKNOWN_TOOL_RISK = "UNKNOWN_TOOL_RISK"
    USER_DENIED = "USER_DENIED"
    POLICY_DENIED = "POLICY_DENIED"
    RAW_SHELL_DENIED = "RAW_SHELL_DENIED"
    POWERSHELL_UNREGISTERED = "POWERSHELL_UNREGISTERED"
    OVERWRITE_DENIED = "OVERWRITE_DENIED"
    TRAVERSAL_ATTACK = "TRAVERSAL_ATTACK"

class PolicyDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    decision: PolicyDecisionType
    risk: RiskLevel
    reason_code: PolicyReasonCode
    rule_id: str
    confirmation_scope: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    evaluated_ms: float = Field(default=0.0, ge=0.0)

    @property
    def is_allowed(self) -> bool:
        return self.decision == PolicyDecisionType.ALLOW

    @property
    def requires_confirmation(self) -> bool:
        return self.decision == PolicyDecisionType.REQUIRE_CONFIRMATION

    @property
    def is_denied(self) -> bool:
        return self.decision == PolicyDecisionType.DENY

    @property
    def pauses_for_user(self) -> bool:
        return self.decision == PolicyDecisionType.PAUSE_FOR_USER
