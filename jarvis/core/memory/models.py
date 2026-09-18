"""Data models and contracts for layered memory in JARVIS EDGE (Phase 12)."""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class MemoryLayer(str, enum.Enum):
    SESSION = "SESSION"
    WORKING = "WORKING"
    EPISODIC = "EPISODIC"
    SEMANTIC = "SEMANTIC"
    PREFERENCE = "PREFERENCE"
    WORKFLOW = "WORKFLOW"


class MemorySourceType(str, enum.Enum):
    USER_EXPLICIT = "USER_EXPLICIT"
    VERIFIED_ACTION = "VERIFIED_ACTION"
    USER_CORRECTION = "USER_CORRECTION"
    APPROVED_WORKFLOW = "APPROVED_WORKFLOW"
    TRUSTED_SYSTEM_STATE = "TRUSTED_SYSTEM_STATE"
    UNTRUSTED_EXTERNAL_CONTENT = "UNTRUSTED_EXTERNAL_CONTENT"


class MemoryConfidence(str, enum.Enum):
    EXPLICIT = "EXPLICIT"
    VERIFIED = "VERIFIED"
    INFERRED_HIGH = "INFERRED_HIGH"
    INFERRED_LOW = "INFERRED_LOW"


class MemoryStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    QUARANTINED = "QUARANTINED"


@dataclass
class MemoryProvenance:
    source_type: MemorySourceType
    source_reference: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    last_verified: Optional[float] = None
    supersedes_id: Optional[str] = None


@dataclass
class MemoryItem:
    memory_id: str
    layer: MemoryLayer
    kind: str
    key: str
    value: Any
    provenance: MemoryProvenance
    confidence: MemoryConfidence = MemoryConfidence.VERIFIED
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    use_count: int = 0
    successful_use_count: int = 0
    correction_count: int = 0
    expires_at: Optional[float] = None
    status: MemoryStatus = MemoryStatus.ACTIVE

    def is_expired(self, now: Optional[float] = None) -> bool:
        if self.expires_at is None:
            return False
        current = now if now is not None else time.time()
        return current >= self.expires_at

    def to_text_for_search(self) -> str:
        val_str = str(self.value) if not isinstance(self.value, str) else self.value
        return f"{self.key} {self.kind} {val_str}".strip()


@dataclass
class EpisodeRecord:
    episode_id: str
    timestamp: float = field(default_factory=time.time)
    request_id: str = ""
    normalized_goal: str = ""
    tools_used: List[str] = field(default_factory=list)
    resources: List[str] = field(default_factory=list)
    outcome: str = "SUCCESS"  # SUCCESS, FAILURE, PARTIAL, CANCELLED
    verified: bool = True
    duration_ms: float = 0.0
    user_correction: Optional[str] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class MemoryCandidate:
    candidate_id: str
    layer: MemoryLayer
    kind: str
    key: str
    value: Any
    source_type: MemorySourceType
    source_reference: Optional[str] = None
    confidence: MemoryConfidence = MemoryConfidence.INFERRED_HIGH
    ttl_seconds: Optional[float] = None


@dataclass
class MemoryQuery:
    query_text: Optional[str] = None
    layer: Optional[MemoryLayer] = None
    kind: Optional[str] = None
    key: Optional[str] = None
    min_confidence: Optional[MemoryConfidence] = None
    limit: int = 10


@dataclass
class MemoryQueryResult:
    item: MemoryItem
    relevance_score: float
    match_method: str  # EXACT, FTS, SEMANTIC, WORKING
