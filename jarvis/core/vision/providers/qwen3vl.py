"""Qwen3-VL Local Multimodal Vision Provider."""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image
import httpx

from jarvis.core.vision.models import (
    GroundingConfidence,
    VisualCandidate,
    VisualGroundingDecision,
)
from jarvis.core.vision.preprocessing import encode_image_to_base64

logger = logging.getLogger("jarvis.core.vision.providers.qwen3vl")


class Qwen3VLProvider:
    """Local quantized Qwen3-VL multimodal inference provider via Ollama or local endpoint."""

    def __init__(
        self,
        model_name: str = "qwen3-vl:2b",
        base_url: str = "http://127.0.0.1:11434",
        timeout_s: float = 15.0,
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self._is_loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    def load(self) -> bool:
        """Ping local provider or warm model."""
        try:
            with httpx.Client(timeout=3.0) as client:
                res = client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    self._is_loaded = True
                    return True
        except Exception as e:
            logger.info(f"Local VLM endpoint offline or unreachable ({e}).")
        self._is_loaded = False
        return False

    def unload(self) -> None:
        """Evict model from memory."""
        self._is_loaded = False

    def cancel(self) -> None:
        """Cancel ongoing inference."""
        pass

    def analyze(self, image: Image.Image, prompt: str) -> str:
        """Run read-only visual inspection."""
        b64_img = encode_image_to_base64(image, format="JPEG", quality=85)
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "images": [b64_img],
            "stream": False,
        }
        try:
            with httpx.Client(timeout=self.timeout_s) as client:
                resp = client.post(f"{self.base_url}/api/generate", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("response", "").strip()
                return f"Vision analysis returned HTTP {resp.status_code}"
        except Exception as e:
            return f"VISION_UNAVAILABLE: {e}"

    def ground(
        self,
        goal: str,
        candidates: List[VisualCandidate],
        image: Image.Image,
        context: Optional[Dict[str, Any]] = None,
    ) -> VisualGroundingDecision:
        """Select candidate ID from candidates corresponding to the user's goal."""
        valid_ids = {c.candidate_id for c in candidates}
        if not candidates:
            return VisualGroundingDecision(
                match=False,
                confidence=GroundingConfidence.LOW,
                reason_code="NO_CANDIDATES_AVAILABLE",
            )

        candidate_lines = []
        for c in candidates:
            text_desc = f" text: '{c.visible_text}'" if c.visible_text else ""
            icon_desc = f" icon: '{c.icon_description}'" if c.icon_description else ""
            candidate_lines.append(f"- {c.candidate_id}: {c.candidate_type}{text_desc}{icon_desc}")

        prompt = f"""You are a precise GUI grounding model.
GOAL: {goal}
AVAILABLE VISUAL CANDIDATES:
{chr(10).join(candidate_lines)}

INSTRUCTIONS:
1. Identify which single Candidate ID (e.g. C1, C2) corresponds directly to the GOAL.
2. If none match or multiple identical controls exist without context, set match to false or confidence to AMBIGUOUS.
3. Return ONLY valid JSON in this exact schema, with no additional text:
{{"candidate_id": "C1", "match": true, "confidence": "HIGH", "needs_zoom": false, "needs_clarification": false, "reason_code": "MATCHED_LABEL"}}
"""
        b64_img = encode_image_to_base64(image, format="JPEG", quality=85)
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "images": [b64_img],
            "stream": False,
            "format": "json",
        }

        try:
            with httpx.Client(timeout=self.timeout_s) as client:
                res = client.post(f"{self.base_url}/api/generate", json=payload)
                if res.status_code != 200:
                    return VisualGroundingDecision(
                        match=False,
                        confidence=GroundingConfidence.LOW,
                        reason_code="VISION_UNAVAILABLE",
                    )
                raw_resp = res.json().get("response", "")
                parsed = json.loads(raw_resp)
                cid = parsed.get("candidate_id")

                # Validate candidate exists
                if cid and cid not in valid_ids:
                    return VisualGroundingDecision(
                        match=False,
                        confidence=GroundingConfidence.LOW,
                        reason_code="UNKNOWN_CANDIDATE_RETURNED",
                        needs_clarification=True,
                    )

                conf_str = parsed.get("confidence", "LOW").upper()
                conf = GroundingConfidence[conf_str] if conf_str in GroundingConfidence.__members__ else GroundingConfidence.LOW

                return VisualGroundingDecision(
                    candidate_id=cid,
                    match=parsed.get("match", False),
                    confidence=conf,
                    needs_zoom=parsed.get("needs_zoom", False),
                    needs_clarification=parsed.get("needs_clarification", False),
                    reason_code=parsed.get("reason_code", "VLM_DECISION"),
                )
        except json.JSONDecodeError:
            return VisualGroundingDecision(
                match=False,
                confidence=GroundingConfidence.LOW,
                reason_code="MALFORMED_OUTPUT",
                needs_clarification=True,
            )
        except Exception as e:
            logger.info(f"Qwen3-VL inference failed or endpoint offline ({e}).")
            return VisualGroundingDecision(
                match=False,
                confidence=GroundingConfidence.LOW,
                reason_code="VISION_UNAVAILABLE",
            )

    def verify_visual_state(
        self,
        before_image: Image.Image,
        after_image: Image.Image,
        expected_condition: str,
    ) -> Tuple[bool, str]:
        """Verify state change between before and after images."""
        prompt = f"Did the following condition happen between image 1 and image 2? '{expected_condition}'. Answer YES or NO with reason."
        b64_1 = encode_image_to_base64(before_image)
        b64_2 = encode_image_to_base64(after_image)

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "images": [b64_1, b64_2],
            "stream": False,
        }
        try:
            with httpx.Client(timeout=self.timeout_s) as client:
                res = client.post(f"{self.base_url}/api/generate", json=payload)
                if res.status_code == 200:
                    text = res.json().get("response", "").strip().upper()
                    success = "YES" in text
                    return success, text
        except Exception as e:
            return False, f"VERIFICATION_UNAVAILABLE: {e}"
        return False, "UNKNOWN"
