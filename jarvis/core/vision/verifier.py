"""Visual Verification and Image-Difference Fast Path."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple
import numpy as np
from PIL import Image

from jarvis.core.vision.models import VisualObservation
from jarvis.core.vision.providers.base import VisionProvider

logger = logging.getLogger("jarvis.core.vision.verifier")


class VisualVerifier:
    """Verifies post-action visual state transitions via image difference and VLM inspection."""

    def __init__(self, provider: Optional[VisionProvider] = None) -> None:
        self.provider = provider

    @staticmethod
    def compute_image_difference(img1: Image.Image, img2: Image.Image) -> float:
        """Compute mean absolute RGB difference between two images."""
        a1 = np.array(img1.convert("RGB"))
        a2 = np.array(img2.convert("RGB"))
        if a1.shape != a2.shape:
            return 100.0  # Dimensions changed entirely
        diff = np.abs(a1.astype(float) - a2.astype(float))
        return float(np.mean(diff))

    def verify_transition(
        self,
        before_image: Image.Image,
        after_image: Image.Image,
        before_obs: VisualObservation,
        after_obs: VisualObservation,
        expected_condition: str = "state_change",
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Verify whether an interaction resulted in the expected visual state change.
        
        Returns:
            (success, verification_status, evidence)
        """
        pixel_diff = self.compute_image_difference(before_image, after_image)
        evidence: Dict[str, Any] = {
            "before_hash": before_obs.image_hash,
            "after_hash": after_obs.image_hash,
            "pixel_diff": pixel_diff,
            "expected_condition": expected_condition,
        }

        # 1. If screen didn't change at all, action had no visual effect unless provider explicitly verifies
        if pixel_diff < 0.5 and before_obs.image_hash == after_obs.image_hash:
            if self.provider and expected_condition != "state_change":
                ok, reason = self.provider.verify_visual_state(
                    before_image=before_image,
                    after_image=after_image,
                    expected_condition=expected_condition,
                )
                evidence["provider_reason"] = reason
                if ok:
                    evidence["verified"] = True
                    return True, "VERIFIED", evidence

            logger.warning("Visual state verification failed: screen pixels and hash are unchanged.")
            return False, "SCREEN_UNCHANGED", evidence

        # 2. If provider is available and a specific condition was asserted
        if self.provider and expected_condition != "state_change":
            ok, reason = self.provider.verify_visual_state(
                before_image=before_image,
                after_image=after_image,
                expected_condition=expected_condition,
            )
            evidence["provider_reason"] = reason
            if not ok:
                return False, "FAILED", evidence

        # 3. Successful visual state change
        evidence["verified"] = True
        return True, "VERIFIED", evidence
