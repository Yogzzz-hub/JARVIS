"""Candidate-First Grounding and Bounded Multi-Pass Execution."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image

from jarvis.core.vision.crop import ImageCropManager
from jarvis.core.vision.models import (
    GroundingConfidence,
    VisualCandidate,
    VisualGroundingDecision,
)
from jarvis.core.vision.providers.base import VisionProvider

logger = logging.getLogger("jarvis.core.vision.grounding")


class VisionGrounder:
    """Orchestrates candidate-first visual grounding with bounded zoom-crop passes."""

    def __init__(self, provider: VisionProvider, max_passes: int = 2) -> None:
        self.provider = provider
        self.max_passes = min(max_passes, 2)  # Strictly max 2 passes per step

    def ground_target(
        self,
        goal: str,
        image: Image.Image,
        candidates: List[VisualCandidate],
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[VisualGroundingDecision, int]:
        """Perform candidate grounding with optional adaptive zoom-crop pass.
        
        Returns:
            (grounding_decision, passes_performed)
        """
        if not candidates:
            return (
                VisualGroundingDecision(
                    match=False,
                    confidence=GroundingConfidence.LOW,
                    reason_code="NO_CANDIDATES",
                ),
                1,
            )

        # Pass 1: Global window grounding
        decision_p1 = self.provider.ground(
            goal=goal,
            candidates=candidates,
            image=image,
            context=context,
        )

        # If confident or zoom not needed, return immediately
        if (
            decision_p1.confidence == GroundingConfidence.HIGH
            or not decision_p1.needs_zoom
            or self.max_passes <= 1
            or not decision_p1.candidate_id
        ):
            return decision_p1, 1

        # Pass 2: Zoom-crop pass on suspected candidate
        suspected_cand = next(
            (c for c in candidates if c.candidate_id == decision_p1.candidate_id),
            None,
        )
        if not suspected_cand:
            return decision_p1, 1

        try:
            cropped_img, crop_box_norm, _ = ImageCropManager.adaptive_zoom_crop(
                image=image,
                suspected_box=suspected_cand.as_bounding_box(),
                padding_ratio=0.35,
            )
            # Re-evaluate in zoomed region
            decision_p2 = self.provider.ground(
                goal=goal,
                candidates=[suspected_cand],
                image=cropped_img,
                context=context,
            )
            # If pass 2 produced a confident match, promote it
            if decision_p2.match:
                decision_p2.confidence = GroundingConfidence.HIGH
                decision_p2.reason_code = f"{decision_p2.reason_code}_ZOOM_CONFIRMED"
                return decision_p2, 2
        except Exception as e:
            logger.warning(f"Adaptive zoom-crop pass encountered error: {e}")

        return decision_p1, 2
