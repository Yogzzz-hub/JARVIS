"""Data contracts for Context Assembly and Reference Resolution (Phase 12)."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from jarvis.core.memory.models import MemoryItem


class ReferenceConfidence(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    AMBIGUOUS = "AMBIGUOUS"


class OperationalMode(str, enum.Enum):
    DEFAULT = "DEFAULT"
    FOCUS = "FOCUS"
    STUDY = "STUDY"
    CODING = "CODING"
    PRESENTATION = "PRESENTATION"


@dataclass
class ReferenceResolution:
    referent: Optional[Any] = None
    referent_type: str = "UNKNOWN"  # FILE, FOLDER, APP, PROJECT, SEARCH_RESULT
    confidence: ReferenceConfidence = ReferenceConfidence.LOW
    source: str = "UNKNOWN"
    candidates: List[Any] = field(default_factory=list)
    clarification_prompt: Optional[str] = None

    def is_reliable_for_action(self) -> bool:
        """State-changing actions strictly require HIGH confidence."""
        return self.confidence == ReferenceConfidence.HIGH and self.referent is not None


@dataclass
class ProjectContext:
    project_id: str
    name: str
    roots: List[str] = field(default_factory=list)
    recent_files: List[str] = field(default_factory=list)
    recent_apps: List[str] = field(default_factory=list)
    knowledge_collection: Optional[str] = None
    recent_tasks: List[str] = field(default_factory=list)


@dataclass
class ContextPacket:
    request: str
    working_context: Dict[str, Any] = field(default_factory=dict)
    resolved_references: Dict[str, ReferenceResolution] = field(default_factory=dict)
    relevant_memories: List[MemoryItem] = field(default_factory=list)
    active_project: Optional[ProjectContext] = None
    current_mode: OperationalMode = OperationalMode.DEFAULT
    token_estimate: int = 0
    workflow_match_id: Optional[str] = None
    explanation: Dict[str, Any] = field(default_factory=dict)
