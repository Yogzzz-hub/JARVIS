"""Deterministic Planner Complexity Analyzer for Phase 4.

Classifies incoming user requests into LOW, MEDIUM, or HIGH complexity
based on lexical, syntactic, and semantic signals to guide the planning cascade.
"""

from enum import StrEnum
import re
from typing import Optional


class PlannerComplexity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


TEMPORAL_MARKERS = ("then", "after", "before", "once", "afterwards", "finally", "next")
CONDITIONAL_MARKERS = ("if", "unless", "in case", "only if", "provided that")
PRONOUN_MARKERS = ("it", "them", "that", "those", "both", "all", "which")
ACTION_VERBS = (
    "find", "search", "locate", "copy", "move", "rename", "delete",
    "open", "launch", "start", "create", "make", "list", "view",
    "set", "get", "toggle", "lock", "sleep", "restart", "shutdown"
)


class ComplexityAnalyzer:
    def analyze(self, text: str, likely_tools_count: int = 1) -> PlannerComplexity:
        """Determines complexity level: LOW, MEDIUM, or HIGH."""
        clean = text.lower().strip()
        words = set(re.findall(r"[a-z0-9]+", clean))

        # Count action verbs
        action_count = sum(1 for verb in ACTION_VERBS if verb in words)

        # Detect temporal markers
        temporal_count = sum(1 for m in TEMPORAL_MARKERS if m in words)

        # Detect conditional markers
        conditional_count = sum(1 for m in CONDITIONAL_MARKERS if m in words)

        # Detect pronouns
        pronoun_count = sum(1 for p in PRONOUN_MARKERS if p in words)

        # Ambiguity / questioning markers
        has_question = "?" in text or any(w in words for w in ("what", "which", "how", "can", "could"))

        # Scoring heuristics
        score = 0
        score += action_count * 2
        score += temporal_count * 3
        score += conditional_count * 4
        score += pronoun_count * 1.5
        score += (likely_tools_count - 1) * 2
        if has_question:
            score += 3

        if score <= 3 and action_count <= 2 and conditional_count == 0 and temporal_count == 0:
            return PlannerComplexity.LOW
        elif score <= 8 and conditional_count == 0:
            return PlannerComplexity.MEDIUM
        else:
            return PlannerComplexity.HIGH
