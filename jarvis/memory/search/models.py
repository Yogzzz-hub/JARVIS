from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class MatchReason(str, Enum):
    EXACT_NAME = "EXACT_NAME"
    NAME_PREFIX = "NAME_PREFIX"
    PATH_MATCH = "PATH_MATCH"
    TYPE_MATCH = "TYPE_MATCH"
    CONTENT_MATCH = "CONTENT_MATCH"
    SEMANTIC_MATCH = "SEMANTIC_MATCH"
    RECENT = "RECENT"
    CONTEXT_REFERENCE = "CONTEXT_REFERENCE"
    USAGE_BOOST = "USAGE_BOOST"

@dataclass
class SearchQuery:
    raw_query: str
    text: str
    type_hint: str | None = None
    temporal_hint: str | None = None
    latest: bool = False
    context_reference: bool = False
    semantic: bool = False
    directory_hint: str | None = None
    tokens: list[str] = field(default_factory=list)

@dataclass
class SearchResult:
    file_id: int
    path: str
    name: str
    extension: str
    score: float
    confidence: float
    match_reasons: list[str] = field(default_factory=list)
    modified_ns: int = 0
    last_opened_ns: int | None = None
    source_signals: dict[str, Any] = field(default_factory=dict)
    excerpt: str | None = None

@dataclass
class SearchResponse:
    results: list[SearchResult]
    search_mode: str
    semantic_used: bool = False
    semantic_state: str = "READY"
    latency_ms: float = 0.0
    is_ambiguous: bool = False
    clarification: str | None = None
    breakdown_ms: dict[str, float] = field(default_factory=dict)
    index_state: dict[str, Any] = field(default_factory=dict)
