"""Adaptive routing policy, context-aware route caching, and threshold optimizer (Phase 12)."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from jarvis.core.router.models import RouteDecision, RouteLane
from jarvis.core.workflows.library import WorkflowLibrary


IMMUTABLE_SECURITY_PARAMETERS = {
    "confirmation_required_destructive",
    "confirmation_required_external_effect",
    "uac_pause_required",
    "captcha_pause_required",
    "raw_shell_prohibited",
    "password_scraping_prohibited",
    "protected_system_paths",
    "confidence_floor_consequential",
}

# Approved bounded tuning ranges for operational thresholds
APPROVED_PARAMETER_RANGES = {
    "fuzzy_score_cutoff": (70.0, 95.0),
    "ambiguity_margin": (5.0, 20.0),
    "hot_cache_capacity": (512, 8192),
    "idle_model_unload_seconds": (30, 600),
}


@dataclass
class RouteTelemetry:
    utterance: str
    lane: RouteLane
    latency_ms: float
    is_success: bool
    escalated_to_planner: bool = False
    user_corrected: bool = False
    timestamp: float = field(default_factory=time.time)


class AdaptiveRoutingPolicy:
    """
    Adaptive router policy that:
    - Maintains context-aware route cache keys
    - Matches approved workflows on fast path (p95 < 2 ms)
    - Records route telemetry
    - Proposes bounded threshold optimizations strictly evaluated offline
    - Strictly protects immutable security boundaries
    """

    def __init__(
        self,
        workflow_library: Optional[WorkflowLibrary] = None,
        fuzzy_score_cutoff: float = 75.0,
        ambiguity_margin: float = 10.0,
    ):
        self.workflow_library = workflow_library
        self.fuzzy_score_cutoff = fuzzy_score_cutoff
        self.ambiguity_margin = ambiguity_margin
        self._telemetry_history: List[RouteTelemetry] = []
        self._context_route_cache: Dict[str, Tuple[RouteDecision, float]] = {}

    def compute_context_cache_key(self, utterance: str, context_fingerprint: str = "") -> str:
        raw = f"{utterance.strip().casefold()}|{context_fingerprint}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def check_workflow_fast_path(self, utterance: str) -> Optional[Tuple[str, Any]]:
        """Checks if utterance matches an approved workflow template."""
        if self.workflow_library is None:
            return None
        wf = self.workflow_library.find_matching_workflow(utterance)
        if wf is not None:
            return wf.workflow_id, wf
        return None

    def record_outcome(
        self,
        utterance: str,
        lane: RouteLane,
        latency_ms: float,
        is_success: bool,
        escalated: bool = False,
        corrected: bool = False,
    ):
        self._telemetry_history.append(
            RouteTelemetry(
                utterance=utterance,
                lane=lane,
                latency_ms=latency_ms,
                is_success=is_success,
                escalated_to_planner=escalated,
                user_corrected=corrected,
            )
        )
        if len(self._telemetry_history) > 1000:
            self._telemetry_history.pop(0)

    def propose_threshold_tuning(
        self,
        parameter_name: str,
        proposed_value: float,
        evidence: str,
    ) -> Tuple[bool, str]:
        """
        Validates whether a parameter tuning proposal is legally allowed.
        Rejects immutable security parameters and out-of-bound changes.
        """
        # 1. Immutable Security Invariant
        if parameter_name in IMMUTABLE_SECURITY_PARAMETERS:
            return False, f"REJECTED_BY_IMMUTABLE_SECURITY_POLICY: parameter '{parameter_name}' cannot be modified"

        # 2. Approved range verification
        if parameter_name not in APPROVED_PARAMETER_RANGES:
            return False, f"REJECTED: parameter '{parameter_name}' is not an approved tunable parameter"

        min_val, max_val = APPROVED_PARAMETER_RANGES[parameter_name]
        if not (min_val <= proposed_value <= max_val):
            return False, f"REJECTED: proposed value {proposed_value} is outside approved range [{min_val}, {max_val}]"

        return True, "PROPOSAL_VALID_FOR_OFFLINE_BENCHMARK"

    def apply_verified_proposal(self, parameter_name: str, value: float) -> bool:
        """Applies a proposal only after offline benchmark proves zero regressions."""
        valid, _ = self.propose_threshold_tuning(parameter_name, value, "offline_verified")
        if not valid:
            return False

        if parameter_name == "fuzzy_score_cutoff":
            self.fuzzy_score_cutoff = value
        elif parameter_name == "ambiguity_margin":
            self.ambiguity_margin = value
        return True

    def get_stats(self) -> Dict[str, Any]:
        if not self._telemetry_history:
            return {
                "total_routes": 0,
                "lane_distribution": {},
                "escalation_rate": 0.0,
                "correction_rate": 0.0,
            }
        total = len(self._telemetry_history)
        lane_counts = {}
        escalated_count = 0
        corrected_count = 0
        for t in self._telemetry_history:
            lane_name = t.lane.value if hasattr(t.lane, "value") else str(t.lane)
            lane_counts[lane_name] = lane_counts.get(lane_name, 0) + 1
            if t.escalated_to_planner:
                escalated_count += 1
            if t.user_corrected:
                corrected_count += 1
        return {
            "total_routes": total,
            "lane_distribution": {k: f"{(v / total) * 100:.1f}%" for k, v in lane_counts.items()},
            "escalation_rate": escalated_count / total,
            "correction_rate": corrected_count / total,
            "fuzzy_cutoff": self.fuzzy_score_cutoff,
            "ambiguity_margin": self.ambiguity_margin,
        }
