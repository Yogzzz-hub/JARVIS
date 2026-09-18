"""Visual Target Resolver, Relational Grounding, and Structured UI Cross-Check."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from jarvis.core.computer.models import UIElement
from jarvis.core.vision.models import (
    GroundingConfidence,
    VisualCandidate,
    VisualGroundingDecision,
)

logger = logging.getLogger("jarvis.core.vision.resolver")


class VisualTargetResolver:
    """Combines visual candidate data, structured UI anchors, and spatial relationships."""

    @staticmethod
    def fuse_confidence(
        decision: VisualGroundingDecision,
        candidate: Optional[VisualCandidate],
        has_anchor_support: bool = False,
        candidate_count_matching: int = 1,
    ) -> GroundingConfidence:
        """Deterministically compute final target confidence."""
        if not decision.match or not candidate:
            return GroundingConfidence.LOW

        if candidate_count_matching > 1 and not has_anchor_support:
            return GroundingConfidence.AMBIGUOUS

        # If model is confident, candidate detector is high confidence, and target is unique
        if decision.confidence == GroundingConfidence.HIGH and candidate.detector_confidence >= 0.8:
            return GroundingConfidence.HIGH

        if has_anchor_support and decision.match:
            return GroundingConfidence.HIGH

        if decision.confidence == GroundingConfidence.MEDIUM:
            return GroundingConfidence.MEDIUM

        return GroundingConfidence.LOW

    @staticmethod
    def cross_check_with_structured_ui(
        candidate: VisualCandidate,
        structured_elements: List[UIElement],
        tolerance_pixels: int = 35,
    ) -> Optional[UIElement]:
        """Check if visual candidate aligns spatially with an existing structured control.
        
        If an accessible UIA or DOM control is rediscovered near the candidate,
        JARVIS prefers the structured control over mouse simulation.
        """
        cx, cy = candidate.center_pixel()

        for elem in structured_elements:
            if not elem.bounds_metadata:
                continue
            b = elem.bounds_metadata
            bx1 = b.get("left", 0)
            by1 = b.get("top", 0)
            bx2 = bx1 + b.get("width", 0)
            by2 = by1 + b.get("height", 0)

            # Check if visual candidate center lies within or adjacent to structured bounds
            if (bx1 - tolerance_pixels <= cx <= bx2 + tolerance_pixels and
                by1 - tolerance_pixels <= cy <= by2 + tolerance_pixels):
                logger.info(f"Visual candidate {candidate.candidate_id} matches structured element '{elem.name}' (id: {elem.automation_id})")
                return elem

        return None
