"""Common UI Contracts, Resource References, Elements and Observations for Computer Agent."""
from __future__ import annotations

from enum import StrEnum
import hashlib
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class UIBackend(StrEnum):
    WINDOWS_UIA = "WINDOWS_UIA"
    BROWSER = "BROWSER"


class TargetConfidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    AMBIGUOUS = "AMBIGUOUS"


class UIAFailureReason(StrEnum):
    WINDOW_NOT_FOUND = "WINDOW_NOT_FOUND"
    ELEMENT_NOT_FOUND = "ELEMENT_NOT_FOUND"
    ELEMENT_AMBIGUOUS = "ELEMENT_AMBIGUOUS"
    PATTERN_UNSUPPORTED = "PATTERN_UNSUPPORTED"
    STALE_ELEMENT = "STALE_ELEMENT"
    ACCESS_DENIED = "ACCESS_DENIED"
    SECURE_DESKTOP = "SECURE_DESKTOP"
    UI_NOT_EXPOSED = "UI_NOT_EXPOSED"


class BrowserFailureReason(StrEnum):
    NAVIGATION_FAILED = "NAVIGATION_FAILED"
    LOCATOR_NOT_FOUND = "LOCATOR_NOT_FOUND"
    LOCATOR_AMBIGUOUS = "LOCATOR_AMBIGUOUS"
    ACTIONABILITY_TIMEOUT = "ACTIONABILITY_TIMEOUT"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    CAPTCHA_REQUIRED = "CAPTCHA_REQUIRED"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    UPLOAD_FAILED = "UPLOAD_FAILED"
    UNEXPECTED_ORIGIN = "UNEXPECTED_ORIGIN"
    PAGE_CLOSED = "PAGE_CLOSED"


class UIResourceRef(BaseModel):
    """Uniform structured reference across window/page/element boundaries."""
    backend: UIBackend
    session_id: str
    window_id: Optional[str] = None
    page_id: Optional[str] = None
    element_id: Optional[str] = None
    role: Optional[str] = None
    name: Optional[str] = None
    automation_id: Optional[str] = None
    control_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UIElement(BaseModel):
    """Structured representation of a single UI control."""
    element_id: str  # Session-scoped or ephemeral e.g. 'uia:w1:e5' or 'B1'
    role: str
    name: str
    control_type: str = "Control"
    automation_id: str = ""
    value_summary: str = ""
    enabled: bool = True
    visible: bool = True
    selected: bool = False
    checked: Optional[bool] = None
    editable: bool = False
    focusable: bool = True
    bounds_metadata: Optional[Dict[str, int]] = None  # Diagnostics only - never coordinate locator
    ancestor_path: str = ""
    actions_supported: List[str] = Field(default_factory=list)

    def is_password_or_credential(self) -> bool:
        """Detect sensitive password or credential fields."""
        check_str = f"{self.name} {self.automation_id} {self.control_type}".lower()
        keywords = ["password", "passwd", "pin", "credential", "otp", "secret", "cvv", "security code"]
        return any(k in check_str for k in keywords)


class UIObservation(BaseModel):
    """Structured observation snapshot of a focused application window or browser page."""
    observation_id: str
    backend: UIBackend
    application: str
    window_title: str
    url: Optional[str] = None
    focused_element_id: Optional[str] = None
    elements: List[UIElement] = Field(default_factory=list)
    generation: int = 1
    timestamp: float = Field(default_factory=time.time)
    state_hash: str = ""
    is_untrusted: bool = True
    quarantine_notes: List[str] = Field(default_factory=list)

    def compute_state_hash(self) -> str:
        """Compute deterministic state fingerprint for loop detection and change verification."""
        components = [
            self.backend.value,
            self.application,
            self.window_title,
            self.url or "",
            str(len(self.elements)),
            ";".join(f"{e.element_id}:{e.role}:{e.name}:{e.value_summary}" for e in self.elements[:50]),
        ]
        raw = "|".join(components).encode("utf-8")
        h = hashlib.sha256(raw).hexdigest()[:16]
        self.state_hash = h
        return h


class InteractionDecision(BaseModel):
    """Strict typed action proposal from interaction controller or micro-planner."""
    action: str
    target_element_id: Optional[str] = None
    arguments: Dict[str, Any] = Field(default_factory=dict)
    expected_postcondition: Dict[str, Any] = Field(default_factory=dict)
    needs_clarification: bool = False
    clarification_prompt: Optional[str] = None


class InteractionOutcome(BaseModel):
    """Verified outcome of a single UI or browser interaction."""
    success: bool
    action: str
    target_element_id: Optional[str] = None
    verification_status: str = "VERIFIED"  # VERIFIED, FAILED, UNCERTAIN, VISION_REQUIRED, PAUSE_FOR_USER, AMBIGUOUS
    evidence: Dict[str, Any] = Field(default_factory=dict)
    failure_reason: Optional[str] = None
    message: str = ""


class VisionRequiredResult(BaseModel):
    """First-class result emitted when UI lacks structured accessibility information."""
    application: str
    goal: str
    structured_failure_reason: str
    available_context: Dict[str, Any] = Field(default_factory=dict)
