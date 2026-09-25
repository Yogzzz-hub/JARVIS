"""Data contracts for Context Assembly, Conversational Continuity, and Reference Resolution.

Provides structured models for:
- EntityRef and TopicRef (software, models, runtimes, concepts)
- Typed ResourceRef hierarchy (File, Folder, App, Package, Browser, Contact, Device, Draft)
- ResultSet with ordinal indexing
- FollowupType and classifications
- TaskContext, PendingConfirmation, PendingClarification
- Unified WorkingContext
- ReferenceResolution with salience scoring and evidence
"""

from __future__ import annotations

import enum
import os
import time
from uuid import uuid4
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
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


class EntityType(str, enum.Enum):
    SOFTWARE = "SOFTWARE"
    TECHNOLOGY = "TECHNOLOGY"
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    SERVICE = "SERVICE"
    MODEL = "MODEL"
    PACKAGE = "PACKAGE"
    APPLICATION = "APPLICATION"
    TOPIC = "TOPIC"
    PROJECT = "PROJECT"
    FILE = "FILE"
    DEVICE = "DEVICE"
    UNKNOWN = "UNKNOWN"


@dataclass
class EntityRef:
    """Represents a lightweight semantic or topic entity extracted from conversation or knowledge."""
    entity_id: str
    canonical_name: str
    display_name: str = ""
    entity_type: EntityType = EntityType.UNKNOWN
    aliases: List[str] = field(default_factory=list)
    source_turn: int = 0
    confidence: float = 1.0
    salience: float = 1.0
    last_mentioned_at: float = field(default_factory=time.time)
    possible_capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.display_name:
            self.display_name = self.canonical_name


TopicRef = EntityRef


@dataclass
class BaseResourceRef:
    """Base class for all stable, actionable resource references."""
    resource_id: str
    resource_type: str = "UNKNOWN"
    display_name: str = ""
    canonical_identifier: str = ""
    created_at: float = field(default_factory=time.time)
    last_verified: Optional[float] = None
    is_valid: bool = True
    source_query: Optional[str] = None
    result_rank: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def revalidate(self) -> bool:
        """Revalidate resource existence before state-changing action."""
        return self.is_valid


@dataclass
class FileResourceRef(BaseResourceRef):
    canonical_path: str = ""
    size_bytes: int = 0
    extension: str = ""

    def __post_init__(self):
        self.resource_type = "FILE"
        if not self.canonical_identifier and self.canonical_path:
            self.canonical_identifier = self.canonical_path
        if not self.display_name and self.canonical_path:
            self.display_name = os.path.basename(self.canonical_path)
        if not self.extension and self.canonical_path:
            self.extension = os.path.splitext(self.canonical_path)[1].lower()

    def revalidate(self) -> bool:
        self.last_verified = time.time()
        self.is_valid = bool(self.canonical_path and os.path.exists(self.canonical_path))
        return self.is_valid


@dataclass
class FolderResourceRef(BaseResourceRef):
    canonical_path: str = ""

    def __post_init__(self):
        self.resource_type = "FOLDER"
        if not self.canonical_identifier and self.canonical_path:
            self.canonical_identifier = self.canonical_path
        if not self.display_name and self.canonical_path:
            self.display_name = os.path.basename(self.canonical_path.rstrip("/\\")) or self.canonical_path

    def revalidate(self) -> bool:
        self.last_verified = time.time()
        self.is_valid = bool(self.canonical_path and os.path.isdir(self.canonical_path))
        return self.is_valid


@dataclass
class ApplicationResourceRef(BaseResourceRef):
    app_name: str = ""
    target_exe: str = ""
    is_installed: bool = True

    def __post_init__(self):
        self.resource_type = "APPLICATION"
        if not self.canonical_identifier and self.app_name:
            self.canonical_identifier = self.app_name
        if not self.display_name and self.app_name:
            self.display_name = self.app_name


@dataclass
class PackageResourceRef(BaseResourceRef):
    package_id: str = ""
    canonical_name: str = ""
    installer_type: str = "winget"

    def __post_init__(self):
        self.resource_type = "PACKAGE"
        if not self.canonical_identifier and self.package_id:
            self.canonical_identifier = self.package_id
        if not self.display_name and self.canonical_name:
            self.display_name = self.canonical_name


@dataclass
class BrowserPageRef(BaseResourceRef):
    url: str = ""
    title: str = ""
    media_state: str = "none"  # playing, paused, none
    position: int = 0

    def __post_init__(self):
        self.resource_type = "BROWSER_PAGE"
        if not self.canonical_identifier and self.url:
            self.canonical_identifier = self.url
        if not self.display_name and self.title:
            self.display_name = self.title


@dataclass
class ContactResourceRef(BaseResourceRef):
    name: str = ""
    phone_number: str = ""
    phone: str = ""
    channel: str = "whatsapp"

    def __post_init__(self):
        self.resource_type = "CONTACT"
        if not self.phone_number and self.phone:
            self.phone_number = self.phone
        elif not self.phone and self.phone_number:
            self.phone = self.phone_number
        if not self.canonical_identifier:
            self.canonical_identifier = self.phone_number or self.name
        if not self.display_name and self.name:
            self.display_name = self.name


@dataclass
class DeviceResourceRef(BaseResourceRef):
    device_id: str = ""
    name: str = ""
    device_type: str = "phone"  # phone, pc
    is_connected: bool = True

    def __post_init__(self):
        self.resource_type = "DEVICE"
        if not self.canonical_identifier and self.device_id:
            self.canonical_identifier = self.device_id
        if not self.display_name and self.name:
            self.display_name = self.name


@dataclass
class DraftResourceRef(BaseResourceRef):
    draft_id: str = ""
    recipient: str = ""
    content: str = ""
    text: str = ""
    channel: str = "whatsapp"

    def __post_init__(self):
        self.resource_type = "DRAFT"
        if not self.content and self.text:
            self.content = self.text
        elif not self.text and self.content:
            self.text = self.content
        if not self.canonical_identifier and self.draft_id:
            self.canonical_identifier = self.draft_id
        if not self.display_name:
            self.display_name = f"Draft for {self.recipient}: {self.content[:30]}..."


@dataclass
class SearchResultRef(BaseResourceRef):
    query: str = ""
    rank: int = 0
    title: str = ""
    snippet: str = ""
    resource: Optional[BaseResourceRef] = None

    def __post_init__(self):
        self.resource_type = "SEARCH_RESULT"
        if not self.canonical_identifier and self.title:
            self.canonical_identifier = self.title


@dataclass
class ScreenshotResourceRef(BaseResourceRef):
    """Tracks a captured screenshot for 'attach that' and 'describe this' workflows."""
    path: str = ""
    source_window: str = ""
    source_app: str = ""
    width: int = 0
    height: int = 0
    file_hash: str = ""
    capture_time: float = 0.0

    def __post_init__(self):
        self.resource_type = "SCREENSHOT"
        if not self.canonical_identifier and self.path:
            self.canonical_identifier = self.path
        if not self.display_name:
            self.display_name = f"Screenshot of {self.source_app or 'desktop'}"
        if not self.capture_time:
            self.capture_time = self.created_at

    def revalidate(self) -> bool:
        self.last_verified = time.time()
        self.is_valid = bool(self.path and os.path.exists(self.path))
        return self.is_valid


@dataclass
class MediaResourceRef(BaseResourceRef):
    """Tracks active media playback for 'pause it', 'play next' workflows."""
    title: str = ""
    url: str = ""
    source: str = ""  # youtube, spotify, local, vlc
    media_state: str = "playing"  # playing, paused, stopped
    position_s: float = 0.0
    duration_s: float = 0.0

    def __post_init__(self):
        self.resource_type = "MEDIA"
        if not self.canonical_identifier:
            self.canonical_identifier = self.url or self.title
        if not self.display_name and self.title:
            self.display_name = self.title


@dataclass
class TextResourceRef(BaseResourceRef):
    """Tracks selected or extracted text for 'explain that', 'rewrite that' workflows."""
    text: str = ""
    source_app: str = ""
    source_window: str = ""
    selection_type: str = "clipboard"  # clipboard, uia, browser

    def __post_init__(self):
        self.resource_type = "TEXT"
        if not self.canonical_identifier and self.text:
            self.canonical_identifier = self.text[:64]
        if not self.display_name:
            preview = self.text[:40] + "..." if len(self.text) > 40 else self.text
            self.display_name = f"Text from {self.source_app}: {preview}"


@dataclass
class ResultSet:
    """Stores ordered / numbered query results for ordinal follow-up resolution."""
    result_set_id: str
    query: str = ""
    item_type: str = "FILE"
    resources: List[BaseResourceRef] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    active: bool = True

    def get_by_ordinal(self, idx: int) -> Optional[BaseResourceRef]:
        if not self.resources:
            return None
        if idx == -1:
            return self.resources[-1]
        if 0 <= idx < len(self.resources):
            return self.resources[idx]
        return None


class FollowupType(str, enum.Enum):
    PRONOUN_REFERENCE = "PRONOUN_REFERENCE"
    ORDINAL_REFERENCE = "ORDINAL_REFERENCE"
    ELLIPSIS = "ELLIPSIS"
    REFINEMENT = "REFINEMENT"
    CONTINUATION = "CONTINUATION"
    SLOT_OVERRIDE = "SLOT_OVERRIDE"
    CORRECTION = "CORRECTION"
    COMPARISON = "COMPARISON"
    ACTION_ON_RESULT = "ACTION_ON_RESULT"
    TOPIC_FOLLOWUP = "TOPIC_FOLLOWUP"
    ACTION_ON_TOPIC = "ACTION_ON_TOPIC"
    ACTION_AFTER_FAILURE = "ACTION_AFTER_FAILURE"
    CONSTRAINT_UPDATE = "CONSTRAINT_UPDATE"
    CONFIRMATION = "CONFIRMATION"
    CANCELLATION = "CANCELLATION"
    RETRY = "RETRY"
    EXPLANATION = "EXPLANATION"
    WHY_QUERY = "WHY_QUERY"
    TOPIC_SWITCH = "TOPIC_SWITCH"
    STANDALONE = "STANDALONE"


@dataclass
class FollowupClassification:
    followup_type: FollowupType = FollowupType.STANDALONE
    confidence: float = 1.0
    extracted_pronouns: List[str] = field(default_factory=list)
    extracted_ordinals: List[int] = field(default_factory=list)
    extracted_overrides: Dict[str, Any] = field(default_factory=dict)
    target_hint: Optional[str] = None


@dataclass
class PendingClarification:
    clarification_id: str = field(default_factory=lambda: uuid4().hex)
    original_utterance: str = ""
    original_intent: str = ""
    resolved_slots: Dict[str, Any] = field(default_factory=dict)
    missing_slots: List[str] = field(default_factory=list)
    candidate_values: List[Any] = field(default_factory=list)
    prompt_message: str = ""
    context_snapshot: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def __init__(
        self,
        clarification_id: Optional[str] = None,
        original_utterance: str = "",
        original_intent: str = "",
        resolved_slots: Optional[Dict[str, Any]] = None,
        missing_slots: Optional[List[str]] = None,
        candidate_values: Optional[List[Any]] = None,
        candidate_names: Optional[List[Any]] = None,
        missing_slot: Optional[str] = None,
        prompt_message: str = "",
        context_snapshot: Optional[Dict[str, Any]] = None,
        created_at: Optional[float] = None,
    ):
        self.clarification_id = clarification_id or uuid4().hex
        self.original_utterance = original_utterance
        self.original_intent = original_intent
        self.resolved_slots = resolved_slots or {}
        if missing_slots is not None:
            self.missing_slots = list(missing_slots)
        elif missing_slot is not None:
            self.missing_slots = [missing_slot]
        else:
            self.missing_slots = []
        self.candidate_values = candidate_values or candidate_names or []
        self.prompt_message = prompt_message
        self.context_snapshot = context_snapshot or {}
        self.created_at = created_at or time.time()

    @property
    def candidate_names(self) -> List[Any]:
        return self.candidate_values

    @candidate_names.setter
    def candidate_names(self, val: List[Any]) -> None:
        self.candidate_values = val


@dataclass
class PendingConfirmation:
    ticket_id: str = ""
    intent: str = ""
    slots: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    risk_level: str = "EXTERNAL_EFFECT"
    prepared_action: Optional[Any] = None
    created_at: float = field(default_factory=time.time)

    def __init__(
        self,
        ticket_id: str = "",
        intent: str = "",
        action: Optional[str] = None,
        slots: Optional[Dict[str, Any]] = None,
        prepared_slots: Optional[Dict[str, Any]] = None,
        summary: str = "",
        human_summary: Optional[str] = None,
        risk_level: str = "EXTERNAL_EFFECT",
        prepared_action: Optional[Any] = None,
        created_at: Optional[float] = None,
    ):
        self.ticket_id = ticket_id
        self.intent = action or intent
        self.slots = prepared_slots if prepared_slots is not None else (slots or {})
        self.summary = human_summary if human_summary is not None else summary
        self.risk_level = risk_level
        self.prepared_action = prepared_action
        self.created_at = created_at or time.time()

    @property
    def action(self) -> str:
        return self.intent

    @property
    def human_summary(self) -> str:
        return self.summary

    @property
    def prepared_slots(self) -> Dict[str, Any]:
        return self.slots


@dataclass
class TaskContext:
    task_id: str
    original_goal: str
    current_step: int = 1
    active_resources: List[BaseResourceRef] = field(default_factory=list)
    status: str = "ACTIVE"
    created_at: float = field(default_factory=time.time)


@dataclass
class ReferenceResolution:
    referent: Optional[Any] = None
    referent_type: str = "UNKNOWN"  # FILE, FOLDER, APP, PACKAGE, PROJECT, SEARCH_RESULT, CONTACT, DEVICE, TOPIC
    confidence: ReferenceConfidence = ReferenceConfidence.LOW
    source: str = "UNKNOWN"
    candidates: List[Any] = field(default_factory=list)
    clarification_prompt: Optional[str] = None
    phrase: Optional[str] = None
    evidence: List[str] = field(default_factory=list)
    alternatives: List[Any] = field(default_factory=list)
    score: float = 0.0
    resolved_entity: Optional[EntityRef] = None
    resolved_resource: Optional[BaseResourceRef] = None

    @property
    def target(self) -> Any:
        return self.referent

    @target.setter
    def target(self, val: Any) -> None:
        self.referent = val

    @property
    def target_type(self) -> str:
        return self.referent_type

    @target_type.setter
    def target_type(self, val: str) -> None:
        self.referent_type = val

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
class WorkingContext:
    """Holds active conversational working state across interaction turns."""
    conversation_id: str = "default"
    active_topic: Optional[TopicRef] = None
    topic_stack: List[TopicRef] = field(default_factory=list)
    active_task: Optional[TaskContext] = None
    current_resource: Optional[BaseResourceRef] = None
    selected_resource: Optional[BaseResourceRef] = None
    recent_resources: List[BaseResourceRef] = field(default_factory=list)
    recent_entities: List[EntityRef] = field(default_factory=list)
    recent_result_sets: List[ResultSet] = field(default_factory=list)
    recent_actions: List[Dict[str, Any]] = field(default_factory=list)
    recent_answers: List[Dict[str, Any]] = field(default_factory=list)
    pending_confirmation: Optional[PendingConfirmation] = None
    pending_clarification: Optional[PendingClarification] = None
    pending_draft: Optional[DraftResourceRef] = None
    current_browser_resource: Optional[Any] = None
    current_file_resource: Optional[Any] = None
    current_contact: Optional[Any] = None
    current_device: Optional[Any] = None
    current_application: Optional[Any] = None
    active_project: Optional[str] = None
    recent_failures: List[Dict[str, Any]] = field(default_factory=list)
    constraints: List[Dict[str, Any]] = field(default_factory=list)
    last_user_intent: Optional[str] = None
    last_command_outcome: Optional[Dict[str, Any]] = None
    turn_index: int = 0


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
