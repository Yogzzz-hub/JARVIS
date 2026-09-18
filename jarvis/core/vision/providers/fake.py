"""Deterministic Fake Vision Provider for Headless CI and Unit Testing."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from PIL import Image

from jarvis.core.vision.models import (
    GroundingConfidence,
    VisualCandidate,
    VisualGroundingDecision,
)


class FakeVisionProvider:
    """Zero-GPU deterministic vision provider for automated tests and benchmarks."""

    def __init__(
        self,
        is_available: bool = True,
        return_malformed: bool = False,
    ) -> None:
        self._is_available = is_available
        self.return_malformed = return_malformed
        self._custom_responses: Dict[str, VisualGroundingDecision] = {}
        self._custom_verifications: Dict[str, Tuple[bool, str]] = {}
        self._is_loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    def set_available(self, available: bool) -> None:
        self._is_available = available

    def set_response(self, goal_keyword: str, decision: VisualGroundingDecision) -> None:
        self._custom_responses[goal_keyword.lower()] = decision

    def set_verification(self, condition: str, success: bool, reason: str = "") -> None:
        self._custom_verifications[condition.lower()] = (success, reason)

    def load(self) -> bool:
        if not self._is_available:
            self._is_loaded = False
            return False
        self._is_loaded = True
        return True

    def unload(self) -> None:
        self._is_loaded = False

    def cancel(self) -> None:
        pass

    def analyze(self, image: Image.Image, prompt: str) -> str:
        if not self._is_available:
            return "VISION_UNAVAILABLE"
        return "Screen contains a desktop window with standard application controls."

    def ground(
        self,
        goal: str,
        candidates: List[VisualCandidate],
        image: Image.Image,
        context: Optional[Dict[str, Any]] = None,
    ) -> VisualGroundingDecision:
        if not self._is_available:
            return VisualGroundingDecision(
                match=False,
                confidence=GroundingConfidence.LOW,
                reason_code="VISION_UNAVAILABLE",
            )

        if self.return_malformed:
            return VisualGroundingDecision(
                candidate_id="C_INVALID_999",
                match=True,
                confidence=GroundingConfidence.HIGH,
                reason_code="MALFORMED_CANDIDATE",
            )

        # 1. Check custom overrides
        goal_lower = goal.lower()
        for kw, dec in self._custom_responses.items():
            if kw in goal_lower:
                return dec

        if not candidates:
            return VisualGroundingDecision(
                match=False,
                confidence=GroundingConfidence.LOW,
                reason_code="NO_CANDIDATES",
            )

        # 2. Relational Grounding: e.g. "download next to report.pdf"
        if "next to" in goal_lower:
            parts = goal_lower.split("next to")
            target_kw = parts[0].replace("click", "").replace("tap", "").replace("select", "").strip()
            anchor_kw = parts[1].strip()

            # Find anchor candidate
            anchor_cand = next(
                (c for c in candidates if anchor_kw in (c.visible_text or "").lower()),
                None,
            )
            if anchor_cand:
                # Find candidate to the right or adjacent with matching target_kw
                anchor_cy = (anchor_cand.bbox_pixels[1] + anchor_cand.bbox_pixels[3]) / 2.0
                candidates_in_row = [
                    c for c in candidates
                    if c.candidate_id != anchor_cand.candidate_id
                    and abs((c.bbox_pixels[1] + c.bbox_pixels[3]) / 2.0 - anchor_cy) < 25
                    and target_kw in f"{c.visible_text or ''} {c.icon_description or ''}".lower()
                ]
                if len(candidates_in_row) == 1:
                    return VisualGroundingDecision(
                        candidate_id=candidates_in_row[0].candidate_id,
                        match=True,
                        confidence=GroundingConfidence.HIGH,
                        reason_code="RELATIONAL_ROW_MATCH",
                    )

        # 3. Match candidate by visible_text or icon_description
        matching_cands: List[VisualCandidate] = []
        for c in candidates:
            cand_str = f"{c.visible_text or ''} {c.icon_description or ''}".lower()
            # If goal keywords appear in candidate description
            words = [w for w in goal_lower.replace(".", " ").replace("'", " ").split() if len(w) > 3]
            if any(w in cand_str for w in words):
                matching_cands.append(c)

        if len(matching_cands) == 1:
            return VisualGroundingDecision(
                candidate_id=matching_cands[0].candidate_id,
                match=True,
                confidence=GroundingConfidence.HIGH,
                reason_code="EXACT_KEYWORD_MATCH",
            )
        elif len(matching_cands) > 1:
            # Check if candidates have identical appearance -> AMBIGUOUS
            first_desc = f"{matching_cands[0].visible_text}:{matching_cands[0].icon_description}"
            all_identical = all(
                f"{c.visible_text}:{c.icon_description}" == first_desc
                for c in matching_cands
            )
            if all_identical:
                return VisualGroundingDecision(
                    match=False,
                    confidence=GroundingConfidence.AMBIGUOUS,
                    reason_code="MULTIPLE_IDENTICAL_CANDIDATES",
                    needs_clarification=True,
                    clarification_prompt=f"Found {len(matching_cands)} identical candidates matching '{goal}'. Which one did you mean?",
                )
            return VisualGroundingDecision(
                candidate_id=matching_cands[0].candidate_id,
                match=True,
                confidence=GroundingConfidence.MEDIUM,
                reason_code="MULTIPLE_PARTIAL_MATCHES",
            )

        # No match found
        return VisualGroundingDecision(
            match=False,
            confidence=GroundingConfidence.LOW,
            reason_code="NO_MATCHING_CANDIDATES",
        )

    def verify_visual_state(
        self,
        before_image: Image.Image,
        after_image: Image.Image,
        expected_condition: str,
    ) -> Tuple[bool, str]:
        cond_lower = expected_condition.lower()
        if cond_lower in self._custom_verifications:
            return self._custom_verifications[cond_lower]

        # By default check if images differ
        import numpy as np
        b1 = np.array(before_image.convert("RGB"))
        b2 = np.array(after_image.convert("RGB"))
        if b1.shape != b2.shape:
            return True, "Dimension changed"

        diff = np.abs(b1.astype(int) - b2.astype(int))
        pixel_diff = np.mean(diff)
        if pixel_diff > 1.0:
            return True, f"Visual difference detected ({pixel_diff:.2f})"
        return False, "Screen state unchanged"
