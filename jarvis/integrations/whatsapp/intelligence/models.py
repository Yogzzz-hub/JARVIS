from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class Resource(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ContactRef(Resource):
    id: str
    display_name: str = ""


class ThreadRef(Resource):
    id: str
    kind: Literal["DIRECT", "GROUP", "BROADCAST"] = "DIRECT"


class MessageRef(Resource):
    id: str
    thread_id: str
    text: str = ""
    timestamp: float = 0
    direction: Literal["IN", "OUT"] = "IN"
    source: Literal["CURRENT_MESSAGE", "RECENT_THREAD", "HISTORICAL_THREAD", "USER_INSTRUCTION", "TOOL_RESULT"] = "RECENT_THREAD"
    authorship: Literal["CONTACT", "USER", "JARVIS", "UNKNOWN"] = "UNKNOWN"


class AttachmentRef(Resource):
    source_revision: int = 1
    id: str
    message_id: str
    thread_id: str
    mime_type: str = ""
    filename: str = ""
    local_cache_ref: str = ""
    downloaded: bool = False
    extracted_text: str = ""


class LinkRef(Resource):
    source_revision: int = 1
    id: str
    message_id: str
    thread_id: str
    url: str
    fetched_at: float = 0
    extracted_text: str = ""


class UnderstandingConfidence(Resource):
    intent: float = 0
    contact: float = 1
    reference: float = 0
    topic: float = 0
    historical_fact: float = 0
    temporal_reference: float = 0
    requested_action: float = 0
    reply_tone: float = 0
    reply_content: float = 0


class SemanticMessageFrame(Resource):
    thread_id: str
    message_id: str = ""
    raw_text: str
    normalized_text: str
    language_mix: str = "UNKNOWN"
    speech_act: str = "UNCLEAR"
    entities: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    temporal_expressions: list[dict[str, Any]] = Field(default_factory=list)
    requested_actions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    negations: list[str] = Field(default_factory=list)
    corrections: list[dict[str, str]] = Field(default_factory=list)
    confidence: UnderstandingConfidence = Field(default_factory=UnderstandingConfidence)


class TopicRef(Resource):
    id: str
    thread_id: str
    label: str
    entities: list[str] = Field(default_factory=list)
    started_at: float
    last_active_at: float
    status: str = "ACTIVE"
    message_ids: list[str] = Field(default_factory=list)


class ThreadItem(Resource):
    id: str
    thread_id: str
    message_id: str
    kind: Literal["QUESTION", "COMMITMENT", "ACTION", "FACT"]
    text: str
    status: Literal["OPEN", "RESOLVED", "SUPERSEDED"] = "OPEN"
    deadline: str = ""
    provenance: Literal["OBSERVED", "USER_CONFIRMED"] = "OBSERVED"


class MessageQuery(Resource):
    thread_ids: list[str] = Field(min_length=1)
    sender_ids: list[str] = Field(default_factory=list)
    keywords: str = ""
    date_start: float | None = None
    date_end: float | None = None
    message_types: list[str] = Field(default_factory=list)
    has_attachment: bool | None = None
    direction: Literal["IN", "OUT"] | None = None
    unread_only: bool = False
    limit: int = Field(default=20, ge=1, le=100)
    sort: Literal["asc", "desc"] = "desc"


class ThreadSummary(Resource):
    thread_id: str
    range_start: float
    range_end: float
    evidence_ids: list[str]
    excerpts: list[str]
    version: int = 1


class ConversationContext(Resource):
    contact: ContactRef
    thread: ThreadRef
    frame: SemanticMessageFrame
    current: MessageRef | None = None
    recent: list[MessageRef] = Field(default_factory=list)
    reply_chain: list[MessageRef] = Field(default_factory=list)
    historical: list[MessageRef] = Field(default_factory=list)
    active_topics: list[TopicRef] = Field(default_factory=list)
    unresolved: list[ThreadItem] = Field(default_factory=list)
    attachments: list[AttachmentRef] = Field(default_factory=list)
    links: list[LinkRef] = Field(default_factory=list)
    summary: ThreadSummary | None = None
    style: dict[str, Any] = Field(default_factory=dict)
    pending_drafts: list[str] = Field(default_factory=list)
    previous_outcomes: list[dict[str, Any]] = Field(default_factory=list)
    history_complete: bool = False
    prompt_chars: int = 0


class GroundingReport(Resource):
    passed: bool
    reasons: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class DraftResource(Resource):
    id: str
    thread_id: str
    contact: ContactRef
    content: str
    attachments: list[str] = Field(default_factory=list)
    grounding_refs: list[str] = Field(default_factory=list)
    created_at: float
    revision: int = 1
    thread_version: int = 0
    status: Literal["DRAFT", "CANCELLED", "STARTED", "SENT", "UNCERTAIN", "FAILED"] = "DRAFT"
    instructions: str = ""
    exclusions: list[str] = Field(default_factory=list)
    validation: GroundingReport | None = None


class ReplyPlan(Resource):
    purpose: str = "reply"
    tone: str = "concise"
    language_mix: str = "ENGLISH"
    length: str = "short"
    required_evidence: list[str] = Field(default_factory=list)
    information_to_avoid: list[str] = Field(default_factory=list)
    attachment_requirements: list[str] = Field(default_factory=list)


class Watcher(Resource):
    id: str
    thread_id: str
    kind: Literal["MESSAGE", "ATTACHMENT", "KEYWORD"]
    keyword: str = ""
    mime_type: str = ""
    expires_at: float
    status: Literal["ACTIVE", "FIRED", "CANCELLED", "EXPIRED"] = "ACTIVE"
    matched_message_id: str = ""
    action: Literal["NOTIFY", "SAVE_ATTACHMENT"] = "NOTIFY"
    destination: str = ""
