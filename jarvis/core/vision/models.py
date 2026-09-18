"""Common Vision Models, Candidates, Grounding Decisions, and Observations."""
from __future__ import annotations

from enum import StrEnum
import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class GroundingConfidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    AMBIGUOUS = "AMBIGUOUS"


class VisionStatus(StrEnum):
    IDLE = "IDLE"
    CAPTURING = "CAPTURING"
    GROUNDING = "GROUNDING"
    VERIFYING = "VERIFYING"
    VISION_REQUIRED = "VISION_REQUIRED"
    PAUSE_FOR_USER = "PAUSE_FOR_USER"
    VISION_UNAVAILABLE = "VISION_UNAVAILABLE"
    STALE_VISUAL_OBSERVATION = "STALE_VISUAL_OBSERVATION"


class BoundingBox(BaseModel):
    """Normalized bounding box representation in range [0.0, 1.0]."""
    x1: float
    y1: float
    x2: float
    y2: float

    def is_valid(self) -> bool:
        """Check whether box has positive dimensions and stays within [0.0, 1.0]."""
        return 0.0 <= self.x1 < self.x2 <= 1.0 and 0.0 <= self.y1 < self.y2 <= 1.0

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center_point(self) -> Tuple[float, float]:
        """Normalized center coordinates."""
        return (self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0

    def to_pixels(self, img_width: int, img_height: int) -> Tuple[int, int, int, int]:
        """Convert normalized coordinates to physical pixel integers."""
        px1 = int(round(self.x1 * img_width))
        py1 = int(round(self.y1 * img_height))
        px2 = int(round(self.x2 * img_width))
        py2 = int(round(self.y2 * img_height))
        return (px1, py1, px2, py2)

    def center_pixel(self, img_width: int, img_height: int) -> Tuple[int, int]:
        """Get integer pixel center."""
        cx, cy = self.center_point
        return int(round(cx * img_width)), int(round(cy * img_height))


class VisualCandidate(BaseModel):
    """Visual interactive UI candidate detected on screen."""
    candidate_id: str  # e.g., 'C1', 'C2'
    bbox_normalized: List[float]  # [x1, y1, x2, y2] in [0.0, 1.0]
    bbox_pixels: List[int]  # [x1, y1, x2, y2] in physical image pixels
    candidate_type: str = "button"  # button, icon, input, tab, menu, link, checkbox
    detector_confidence: float = 1.0
    visible_text: Optional[str] = None
    icon_description: Optional[str] = None
    interactive_probability: float = 0.95
    source: str = "simple_regions"  # simple_regions, omniparser, structured_anchor
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def as_bounding_box(self) -> BoundingBox:
        return BoundingBox(
            x1=self.bbox_normalized[0],
            y1=self.bbox_normalized[1],
            x2=self.bbox_normalized[2],
            y2=self.bbox_normalized[3],
        )

    def center_pixel(self) -> Tuple[int, int]:
        x1, y1, x2, y2 = self.bbox_pixels
        return (x1 + x2) // 2, (y1 + y2) // 2


class VisualObservation(BaseModel):
    """Structured visual observation of a window or capture region."""
    observation_id: str
    request_id: str = ""
    window_id: str = ""
    application: str = ""
    window_title: str = ""
    capture_region: Dict[str, Any] = Field(default_factory=dict)  # left, top, width, height, etc.
    image_width: int
    image_height: int
    dpi_scale: float = 1.0
    generation: int = 1
    candidates: List[VisualCandidate] = Field(default_factory=list)
    created_ns: int = Field(default_factory=time.perf_counter_ns)
    image_hash: str = ""
    is_untrusted: bool = True
    privacy_classification: str = "UNTRUSTED_EXTERNAL_CONTENT"
    quarantine_notes: List[str] = Field(default_factory=list)

    def compute_image_hash(self, raw_bytes: bytes) -> str:
        """Compute perceptual/content SHA-256 fingerprint."""
        h = hashlib.sha256(raw_bytes).hexdigest()[:16]
        self.image_hash = h
        return h


class VisualGroundingDecision(BaseModel):
    """Structured output returned by vision grounding model / resolver."""
    candidate_id: Optional[str] = None
    match: bool = False
    confidence: GroundingConfidence = GroundingConfidence.LOW
    reason_code: str = ""
    needs_zoom: bool = False
    needs_clarification: bool = False
    clarification_prompt: Optional[str] = None
    suggested_action: str = "click"


class VisualActionOutcome(BaseModel):
    """Outcome of a visually-grounded interaction."""
    success: bool
    candidate_id: Optional[str] = None
    verification_status: str = "VERIFIED"  # VERIFIED, FAILED, UNCERTAIN, AMBIGUOUS, PAUSE_FOR_USER, STALE
    physical_click_point: Optional[Tuple[int, int]] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)
    failure_reason: Optional[str] = None
    message: str = ""
