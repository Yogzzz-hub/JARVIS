"""Interaction Controller and Bounded Action Loop."""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional
from jarvis.core.computer.models import (
    InteractionDecision,
    InteractionOutcome,
    TargetConfidence,
    UIBackend,
    UIObservation,
    VisionRequiredResult,
)
from jarvis.core.computer.context import SessionContext
from jarvis.core.computer.verifier import UIVerifier

logger = logging.getLogger("jarvis.computer.interaction.controller")


class InteractionController:
    """Orchestrates bounded interaction loops across Windows UIA and Playwright Browser."""

    def __init__(
        self,
        max_steps: int = 12,
        max_replans: int = 2,
        session_id: str = "default",
    ) -> None:
        self.max_steps = min(max_steps, 20)
        self.max_replans = max_replans
        self.context = SessionContext(session_id=session_id)
        self.step_history: List[InteractionOutcome] = []
        self.replan_count: int = 0

    def evaluate_preconditions(
        self,
        observation: UIObservation,
        target_name: Optional[str] = None,
    ) -> tuple[bool, str, Optional[Dict[str, Any]]]:
        """Check safety preconditions on the current observation."""
        # 1. Blank or unexposed accessibility tree -> VISION_REQUIRED
        interactive_elements = [e for e in observation.elements if e.control_type != "WindowControl"]
        if not interactive_elements:
            return False, "VISION_REQUIRED", {
                "application": observation.application,
                "goal": target_name or "",
                "structured_failure_reason": "No accessible controls exposed in window or page.",
            }

        # 2. Check for UAC / Secure Desktop
        if "credential" in observation.window_title.lower() or "user account control" in observation.window_title.lower():
            return False, "PAUSE_FOR_USER", {"reason": "UAC / Secure Desktop prompt detected."}

        # 3. Check for CAPTCHA
        captcha_found = any(
            "captcha" in (e.name + e.automation_id).lower() for e in observation.elements
        )
        if captcha_found:
            return False, "PAUSE_FOR_USER", {"reason": "CAPTCHA challenge detected on screen."}

        # 4. Check for Password fields if target is password
        if target_name:
            for e in observation.elements:
                if target_name.lower() in e.name.lower() and e.is_password_or_credential():
                    return False, "PAUSE_FOR_USER", {"reason": "Password/credential field targeted."}

        # 5. Stalled interaction check
        if self.context.is_stalled(threshold=3):
            return False, "INTERACTION_STALLED", {"reason": "UI state unchanged after 3 consecutive actions."}

        return True, "OK", None

    def record_step(self, outcome: InteractionOutcome) -> None:
        """Record outcome in history and check step budget."""
        self.step_history.append(outcome)
        if len(self.step_history) >= self.max_steps:
            logger.warning(f"Maximum interaction step limit ({self.max_steps}) reached.")
