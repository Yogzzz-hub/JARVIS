"""UI Action Verifier for postcondition validation."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from jarvis.core.computer.models import UIElement, UIObservation


class UIVerifier:
    """Verifies that an interactive action produced its expected postcondition."""

    @staticmethod
    def verify_value(element: UIElement, expected_value: str) -> Tuple[bool, Dict[str, Any]]:
        """Verify that a text or edit control now reflects the expected value."""
        actual = element.value_summary.strip()
        expected = expected_value.strip()
        matched = (actual == expected) or (expected in actual)
        evidence = {
            "check": "value_match",
            "element_id": element.element_id,
            "expected_value": expected,
            "actual_value": actual,
            "verified": matched,
        }
        return matched, evidence

    @staticmethod
    def verify_toggle(element: UIElement, expected_state: bool) -> Tuple[bool, Dict[str, Any]]:
        """Verify that a toggle or checkbox reflects the expected checked/selected state."""
        actual = element.checked if element.checked is not None else element.selected
        matched = (actual == expected_state)
        evidence = {
            "check": "toggle_state",
            "element_id": element.element_id,
            "expected_state": expected_state,
            "actual_state": actual,
            "verified": matched,
        }
        return matched, evidence

    @staticmethod
    def verify_navigation(
        observation_before: UIObservation,
        observation_after: UIObservation,
        expected_url_part: Optional[str] = None,
        expected_title_part: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Verify that navigation or window transition changed URL or title as expected."""
        url_match = True
        if expected_url_part and observation_after.url:
            url_match = expected_url_part.lower() in observation_after.url.lower()

        title_match = True
        if expected_title_part:
            title_match = expected_title_part.lower() in observation_after.window_title.lower()

        # State must have changed
        changed = (observation_before.state_hash != observation_after.state_hash) or (observation_before.url != observation_after.url)
        verified = changed and url_match and title_match

        evidence = {
            "check": "navigation_transition",
            "url_before": observation_before.url,
            "url_after": observation_after.url,
            "title_after": observation_after.window_title,
            "expected_url_part": expected_url_part,
            "expected_title_part": expected_title_part,
            "verified": verified,
        }
        return verified, evidence

    @staticmethod
    def verify_action_occurred(
        observation_before: UIObservation,
        observation_after: UIObservation,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Cheapest check: confirm that state changed following an action."""
        changed = observation_before.state_hash != observation_after.state_hash
        evidence = {
            "check": "state_change",
            "hash_before": observation_before.state_hash,
            "hash_after": observation_after.state_hash,
            "verified": changed,
        }
        return changed, evidence
