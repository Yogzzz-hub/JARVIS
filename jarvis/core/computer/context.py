"""UI Session Context, Ephemeral ID Management, and Generation Tracking."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from jarvis.core.computer.models import UIElement, UIObservation, TargetConfidence


class SessionContext:
    """Manages ephemeral IDs, generation counters, and stale element validation."""

    def __init__(self, session_id: str = "default") -> None:
        self.session_id = session_id
        self.generation: int = 1
        self.current_observation: Optional[UIObservation] = None
        self._ephemeral_to_element: Dict[str, UIElement] = {}
        self._element_to_ephemeral: Dict[str, str] = {}
        self._generation_elements: Dict[int, Dict[str, UIElement]] = {}
        self.last_state_hash: str = ""
        self.stall_counter: int = 0

    def new_generation(self) -> int:
        """Increment generation counter when UI changes."""
        self.generation += 1
        self._ephemeral_to_element.clear()
        self._element_to_ephemeral.clear()
        return self.generation

    def register_observation(self, observation: UIObservation) -> None:
        """Register fresh observation and assign compact ephemeral labels."""
        self.current_observation = observation
        self.generation = observation.generation
        self._ephemeral_to_element.clear()
        self._element_to_ephemeral.clear()

        # Check for stalled loop by comparing state hash
        new_hash = observation.compute_state_hash()
        if not self.last_state_hash:
            self.last_state_hash = new_hash
            self.stall_counter = 1
        elif new_hash == self.last_state_hash:
            self.stall_counter += 1
        else:
            self.stall_counter = 1
            self.last_state_hash = new_hash

        # Assign compact IDs e.g. B1, L2, I3
        type_counters = {"button": 1, "link": 1, "input": 1, "check": 1, "other": 1}
        for elem in observation.elements:
            role_lower = elem.role.lower()
            if "button" in role_lower:
                prefix = "B"
                idx = type_counters["button"]
                type_counters["button"] += 1
            elif "link" in role_lower:
                prefix = "L"
                idx = type_counters["link"]
                type_counters["link"] += 1
            elif any(t in role_lower for t in ["textbox", "input", "edit", "combobox"]):
                prefix = "I"
                idx = type_counters["input"]
                type_counters["input"] += 1
            elif any(t in role_lower for t in ["checkbox", "radio"]):
                prefix = "C"
                idx = type_counters["check"]
                type_counters["check"] += 1
            else:
                prefix = "E"
                idx = type_counters["other"]
                type_counters["other"] += 1

            e_id = f"{prefix}{idx}"
            self._ephemeral_to_element[e_id] = elem
            self._element_to_ephemeral[elem.element_id] = e_id

        self._generation_elements[self.generation] = dict(self._ephemeral_to_element)

    def resolve_element(self, target_identifier: str, expected_generation: Optional[int] = None) -> tuple[Optional[UIElement], TargetConfidence]:
        """Resolve an ephemeral (e.g. 'B1') or session ID with stale element protection."""
        if expected_generation is not None and expected_generation != self.generation:
            # Stale generation check
            return None, TargetConfidence.AMBIGUOUS

        # Check ephemeral ID first
        if target_identifier in self._ephemeral_to_element:
            return self._ephemeral_to_element[target_identifier], TargetConfidence.HIGH

        # Check by element_id
        for elem in self._ephemeral_to_element.values():
            if elem.element_id == target_identifier:
                return elem, TargetConfidence.HIGH

        # Check by automation_id
        matches = [e for e in self._ephemeral_to_element.values() if e.automation_id and e.automation_id == target_identifier]
        if len(matches) == 1:
            return matches[0], TargetConfidence.HIGH
        elif len(matches) > 1:
            return None, TargetConfidence.AMBIGUOUS

        # Check by name exactly
        name_matches = [e for e in self._ephemeral_to_element.values() if e.name.strip().lower() == target_identifier.strip().lower()]
        if len(name_matches) == 1:
            return name_matches[0], TargetConfidence.HIGH
        elif len(name_matches) > 1:
            return None, TargetConfidence.AMBIGUOUS

        return None, TargetConfidence.LOW

    def is_stalled(self, threshold: int = 3) -> bool:
        """Detect repeated interactions yielding identical state."""
        return self.stall_counter >= threshold
