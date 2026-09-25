from enum import StrEnum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

class RiskLevel(StrEnum):
    READ_ONLY = "READ_ONLY"
    REVERSIBLE = "REVERSIBLE"
    EXTERNAL_EFFECT = "EXTERNAL_EFFECT"
    DESTRUCTIVE = "DESTRUCTIVE"
    PRIVILEGED = "PRIVILEGED"

class ExecutionMethod(StrEnum):
    NATIVE = "NATIVE"
    API = "API"
    CLI = "CLI"
    UIA = "UIA"
    DOM = "DOM"
    VISION = "VISION"
    COORDINATES = "COORDINATES"

class IdempotencyClass(StrEnum):
    IDEMPOTENT = "IDEMPOTENT"
    VERIFY_BEFORE_RETRY = "VERIFY_BEFORE_RETRY"
    NON_IDEMPOTENT = "NON_IDEMPOTENT"

class VerificationStrength(StrEnum):
    NONE = "NONE"
    BASIC = "BASIC"
    STRONG = "STRONG"

class VerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    UNCERTAIN = "UNCERTAIN"

class ToolVariant(Contract):
    method: ExecutionMethod
    priority: int = 1
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    estimated_latency_ms: float = Field(default=5.0, ge=0.0)
    requirements: tuple[str, ...] = ()
    supported_context: tuple[str, ...] = ()
    risk_modifier: RiskLevel | None = None

class ToolDefinition(Contract):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(min_length=1)
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    read_only: bool
    requires_confirmation: bool = False
    risk: RiskLevel
    timeout_s: float = Field(default=5.0, gt=0, le=600)
    version: str = "1.0.0"
    tags: tuple[str, ...] = ()
    execution_method: ExecutionMethod = ExecutionMethod.NATIVE
    idempotency: IdempotencyClass = IdempotencyClass.IDEMPOTENT
    verification_strength: VerificationStrength = VerificationStrength.BASIC
    rollback_supported: bool = False
    variants: tuple[ToolVariant, ...] = ()

    @model_validator(mode="after")
    def consistent(self):
        if self.read_only != (self.risk == RiskLevel.READ_ONLY):
            raise ValueError("read_only must agree with risk")
        for model in (self.input_model, self.output_model):
            if model.model_config.get("extra") != "forbid" or not model.model_config.get("strict"):
                raise ValueError("tool models must be strict and forbid extra fields")
        return self

class ToolResult(Contract):
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = Field(default=0.0, ge=0)
    tool_name: str
    method_used: ExecutionMethod = ExecutionMethod.NATIVE

    @model_validator(mode="after")
    def consistent(self):
        if self.success and self.error or not self.success and not self.error:
            raise ValueError("success/error mismatch")
        return self

class VerificationResult(Contract):
    verified: bool = True
    status: VerificationStatus = VerificationStatus.VERIFIED
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    method: str = "native"
    duration_ms: float = Field(default=0.0, ge=0)
    retry_safe: bool = True
    observed_state: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def consistent(self):
        # Synchronize status and verified
        if self.verified and self.status == VerificationStatus.FAILED:
            object.__setattr__(self, "status", VerificationStatus.VERIFIED)
        elif not self.verified and self.status == VerificationStatus.VERIFIED:
            object.__setattr__(self, "status", VerificationStatus.FAILED)
        
        if self.status == VerificationStatus.VERIFIED:
            if self.error or not self.evidence:
                raise ValueError("verified result needs evidence and no error")
        elif self.status == VerificationStatus.FAILED:
            if not self.error:
                raise ValueError("unverified result needs a reason")
        elif self.status == VerificationStatus.UNCERTAIN:
            if not self.error:
                object.__setattr__(self, "error", "State uncertain")
            if self.verified:
                object.__setattr__(self, "verified", False)
        return self

class Tool:
    definition: ToolDefinition
    def run(self, arguments: BaseModel) -> dict:
        raise NotImplementedError
