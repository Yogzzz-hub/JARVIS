"""Data models and contracts for Workflow Learning and Templates (Phase 12)."""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class WorkflowStatus(str, enum.Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    DISABLED = "DISABLED"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"


@dataclass
class WorkflowSlot:
    name: str
    slot_type: str  # str, int, Path, FolderRef, FileRef
    default_value: Optional[Any] = None
    description: str = ""


@dataclass
class WorkflowNodeTemplate:
    node_template_id: str
    tool: str
    args_template: Dict[str, Any]
    depends_on: List[str] = field(default_factory=list)
    risk: str = "READ_ONLY"  # READ_ONLY, EXTERNAL_EFFECT, DESTRUCTIVE
    idempotency: str = "IDEMPOTENT"


@dataclass
class WorkflowGraphTemplate:
    nodes: List[WorkflowNodeTemplate] = field(default_factory=list)
    shape_hash: str = ""


@dataclass
class WorkflowCandidate:
    candidate_id: str
    name_suggestion: str
    normalized_goal: str
    graph_shape_hash: str
    graph_template: WorkflowGraphTemplate
    variable_slots: List[WorkflowSlot] = field(default_factory=list)
    risk_summary: str = "READ_ONLY"
    occurrence_count: int = 1
    evidence_episodes: List[str] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.PROPOSED
    last_used: float = field(default_factory=time.time)


@dataclass
class ApprovedWorkflow:
    workflow_id: str
    name: str
    description: str
    input_schema: List[WorkflowSlot] = field(default_factory=list)
    graph_template: WorkflowGraphTemplate = field(default_factory=WorkflowGraphTemplate)
    required_tools: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    risk_profile: str = "READ_ONLY"
    registry_fingerprint: str = "v1"
    schema_version: str = "1.0"
    created_at: float = field(default_factory=time.time)
    approved_at: Optional[float] = None
    version: int = 1
    status: WorkflowStatus = WorkflowStatus.APPROVED
    success_count: int = 0
    failure_count: int = 0
    avg_latency_ms: float = 0.0
    last_success: Optional[float] = None
    last_failure: Optional[float] = None

    def is_quarantined(self) -> bool:
        return self.status == WorkflowStatus.QUARANTINED or (self.failure_count >= 3 and self.success_count == 0)
