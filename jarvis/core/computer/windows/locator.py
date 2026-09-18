"""Strict UIA Target Resolution with Confidence Scoring and Ambiguity Detection."""
from __future__ import annotations

import difflib
from typing import List, Optional, Tuple
from jarvis.core.computer.models import TargetConfidence, UIElement, UIObservation


class UIALocator:
    """Resolves structured UI targets strictly according to locator priority rules."""

    @classmethod
    def resolve_target(
        cls,
        observation: UIObservation,
        name: Optional[str] = None,
        automation_id: Optional[str] = None,
        control_type: Optional[str] = None,
        role: Optional[str] = None,
        ancestor_hint: Optional[str] = None,
    ) -> Tuple[Optional[UIElement], TargetConfidence]:
        """Resolve an element with strict ambiguity and confidence scoring.
        
        Resolution Priority:
        1. automation_id + control_type + name
        2. automation_id alone
        3. control_type/role + name (exact)
        4. name (exact)
        5. ancestor_path + name
        6. Substring/Fuzzy match (only if unique)
        """
        candidates: List[UIElement] = observation.elements

        # Filter by control_type/role if specified
        if control_type:
            c_lower = control_type.lower()
            candidates = [c for c in candidates if c_lower in c.control_type.lower() or c_lower in c.role.lower()]

        # 1. automation_id + name
        if automation_id and name:
            matches = [
                c for c in candidates
                if c.automation_id == automation_id and c.name.strip().lower() == name.strip().lower()
            ]
            if len(matches) == 1:
                return matches[0], TargetConfidence.HIGH
            elif len(matches) > 1:
                return None, TargetConfidence.AMBIGUOUS

        # 2. automation_id alone
        if automation_id:
            matches = [c for c in candidates if c.automation_id == automation_id]
            if len(matches) == 1:
                return matches[0], TargetConfidence.HIGH
            elif len(matches) > 1:
                return None, TargetConfidence.AMBIGUOUS

        # 3. Exact name match
        if name:
            name_clean = name.strip().lower()
            matches = [c for c in candidates if c.name.strip().lower() == name_clean]
            if len(matches) == 1:
                return matches[0], TargetConfidence.HIGH
            elif len(matches) > 1:
                # Disambiguate by ancestor if provided
                if ancestor_hint:
                    anc_matches = [m for m in matches if ancestor_hint.lower() in m.ancestor_path.lower()]
                    if len(anc_matches) == 1:
                        return anc_matches[0], TargetConfidence.HIGH
                return None, TargetConfidence.AMBIGUOUS

            # 4. Substring name match
            sub_matches = [c for c in candidates if name_clean in c.name.lower()]
            if len(sub_matches) == 1:
                return sub_matches[0], TargetConfidence.MEDIUM
            elif len(sub_matches) > 1:
                return None, TargetConfidence.AMBIGUOUS

            # 5. Fuzzy match on name
            names = [c.name for c in candidates if c.name]
            close = difflib.get_close_matches(name, names, n=2, cutoff=0.75)
            if len(close) == 1:
                for c in candidates:
                    if c.name == close[0]:
                        return c, TargetConfidence.MEDIUM
            elif len(close) > 1:
                return None, TargetConfidence.AMBIGUOUS

        return None, TargetConfidence.LOW
