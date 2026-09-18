"""Data contracts for Local Knowledge Engine and explicit RAG Collections (Phase 12)."""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class AccessPolicy(str, enum.Enum):
    PUBLIC = "PUBLIC"
    PROJECT_INTERNAL = "PROJECT_INTERNAL"
    RESTRICTED = "RESTRICTED"


@dataclass
class KnowledgeCollection:
    collection_id: str
    name: str
    source_roots: List[str] = field(default_factory=list)
    file_filters: List[str] = field(default_factory=lambda: [".txt", ".md", ".pdf", ".py"])
    created_at: float = field(default_factory=time.time)
    access_policy: AccessPolicy = AccessPolicy.PUBLIC


@dataclass
class KnowledgeChunk:
    chunk_id: str
    collection_id: str
    file_path: str
    section_title: str = ""
    line_start: int = 1
    line_end: int = 1
    content: str = ""
    content_hash: str = ""
    embedding: Optional[List[float]] = None


@dataclass
class KnowledgeItem:
    source_type: str  # LOCAL_FILE, RAG_CHUNK, DURABLE_MEMORY, GOOGLE_DRIVE
    resource_id: str
    title: str
    snippet: str
    relevance: float
    timestamp: float = field(default_factory=time.time)
    trust: str = "DATA_ONLY"  # Documents are data, never instruction authority
    citation_metadata: Dict[str, Any] = field(default_factory=dict)
