"""Data contracts for bounded specialists and structured result merging (Phase 12)."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class SpecialistType(str, enum.Enum):
    FILE = "FILE"
    GOOGLE = "GOOGLE"
    BROWSER = "BROWSER"
    DESKTOP = "DESKTOP"
    VISION = "VISION"
    KNOWLEDGE = "KNOWLEDGE"


class SourceTrust(str, enum.Enum):
    TRUSTED_SYSTEM = "TRUSTED_SYSTEM"
    USER_EXPLICIT = "USER_EXPLICIT"
    VERIFIED_LOCAL_STATE = "VERIFIED_LOCAL_STATE"
    AUTHENTICATED_PROVIDER_DATA = "AUTHENTICATED_PROVIDER_DATA"
    UNTRUSTED_EXTERNAL_CONTENT = "UNTRUSTED_EXTERNAL_CONTENT"


@dataclass
class SpecialistFact:
    fact_id: str
    specialist: SpecialistType
    statement: str
    resource_ref: Optional[str] = None
    trust: SourceTrust = SourceTrust.VERIFIED_LOCAL_STATE
    confidence: float = 1.0


@dataclass
class SpecialistResult:
    specialist: SpecialistType
    status: str  # SUCCESS, FAILURE, PARTIAL, CANCELLED
    facts: List[SpecialistFact] = field(default_factory=list)
    resource_refs: List[str] = field(default_factory=list)
    proposed_nodes: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    latency_ms: float = 0.0


@dataclass
class MergedResult:
    status: str  # SUCCESS, PARTIAL, FAILURE
    facts: List[SpecialistFact] = field(default_factory=list)
    resource_refs: List[str] = field(default_factory=list)
    discrepancies: List[str] = field(default_factory=list)
    participating_specialists: List[SpecialistType] = field(default_factory=list)
    latency_ms: float = 0.0
