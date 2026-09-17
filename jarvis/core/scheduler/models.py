"""Scheduler data models and configuration (Phase 4)."""

from pydantic import BaseModel, ConfigDict, Field


class SchedulerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_concurrency: int = Field(default=4, ge=1, le=16)
    default_timeout_s: float = Field(default=5.0, gt=0)
    enforce_risk_gate: bool = True
    dry_run: bool = False
    dry_run_policy: bool = False
