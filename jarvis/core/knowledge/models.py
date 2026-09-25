"""Data contracts for Local Knowledge Engine and explicit RAG Collections (Phase 12 + WhatsApp Omnichannel)."""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


class AccessPolicy(str, enum.Enum):
    PUBLIC = "PUBLIC"
    PROJECT_INTERNAL = "PROJECT_INTERNAL"
    RESTRICTED = "RESTRICTED"


class KnowledgeSourceType(str, enum.Enum):
    LOCAL_FILES = "LOCAL_FILES"
    PROJECTS = "PROJECTS"
    PDF = "PDF"
    DOCUMENTS = "DOCUMENTS"
    USER_MEMORY = "USER_MEMORY"
    WORKFLOW_MEMORY = "WORKFLOW_MEMORY"
    VOICE_CONVERSATIONS = "VOICE_CONVERSATIONS"
    DESKTOP_CONVERSATIONS = "DESKTOP_CONVERSATIONS"
    ANDROID_CONVERSATIONS = "ANDROID_CONVERSATIONS"
    WHATSAPP_CONVERSATIONS = "WHATSAPP_CONVERSATIONS"
    WHATSAPP_DOCUMENTS = "WHATSAPP_DOCUMENTS"
    WHATSAPP_IMAGES = "WHATSAPP_IMAGES"
    WHATSAPP_VOICE_TRANSCRIPTS = "WHATSAPP_VOICE_TRANSCRIPTS"
    RAG_CHUNK = "RAG_CHUNK"
    DURABLE_MEMORY = "DURABLE_MEMORY"
    GOOGLE_DRIVE = "GOOGLE_DRIVE"


class TrustLevel(str, enum.Enum):
    DATA_ONLY = "DATA_ONLY"
    UNTRUSTED_EXTERNAL_CONTENT = "UNTRUSTED_EXTERNAL_CONTENT"
    TRUSTED_USER_INPUT = "TRUSTED_USER_INPUT"
    TRUSTED_SYSTEM = "TRUSTED_SYSTEM"


@dataclass
class KnowledgeScopeFilter:
    """Explicit privacy and ownership scope filter applied strictly BEFORE ranking."""
    allowed_scopes: Set[str] = field(default_factory=lambda: {"scope:user", "scope:device", "scope:documents", "scope:projects"})
    excluded_scopes: Set[str] = field(default_factory=set)

    def is_accessible(self, item_scopes: List[str]) -> bool:
        """Determines if all necessary scopes of an item are permitted."""
        for s in item_scopes:
            if s in self.excluded_scopes:
                return False
        # If item specifies private conversation scopes (e.g. scope:whatsapp:chat:<id>),
        # that exact scope MUST be in allowed_scopes.
        conversation_scopes = [s for s in item_scopes if s.startswith("scope:whatsapp:chat:") or s.startswith("scope:whatsapp:contact:")]
        if conversation_scopes:
            return any(cs in self.allowed_scopes for cs in conversation_scopes)
        # For non-conversation items, at least one scope must match allowed_scopes
        return any(s in self.allowed_scopes for s in item_scopes)


@dataclass
class KnowledgeCollection:
    collection_id: str
    name: str
    source_roots: List[str] = field(default_factory=list)
    file_filters: List[str] = field(default_factory=lambda: [".txt", ".md", ".pdf", ".py"])
    created_at: float = field(default_factory=time.time)
    access_policy: AccessPolicy = AccessPolicy.PUBLIC
    owner_scope: str = "scope:user"


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
    owner_scope: str = "scope:user"
    conversation_scope: str = ""
    privacy_scope: str = "scope:documents"
    trust_level: str = TrustLevel.DATA_ONLY.value


@dataclass
class KnowledgeItem:
    source_type: str  # e.g. WHATSAPP_DOCUMENT, LOCAL_FILES, PDF, etc.
    resource_id: str
    title: str
    snippet: str
    relevance: float
    timestamp: float = field(default_factory=time.time)
    trust: str = TrustLevel.DATA_ONLY.value  # Documents are data, never instruction authority
    owner_scope: str = "scope:user"
    conversation_scope: str = ""
    privacy_scope: str = "scope:documents"
    citation_metadata: Dict[str, Any] = field(default_factory=dict)

    def get_all_scopes(self) -> List[str]:
        scopes = []
        if self.owner_scope:
            scopes.append(self.owner_scope)
        if self.conversation_scope:
            scopes.append(self.conversation_scope)
        if self.privacy_scope:
            scopes.append(self.privacy_scope)
        return scopes
