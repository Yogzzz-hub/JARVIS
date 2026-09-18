"""Self-Optimization Engine with offline evaluation and zero self-modifying code (Phase 12)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from jarvis.core.router.adaptive import (
    AdaptiveRoutingPolicy,
    IMMUTABLE_SECURITY_PARAMETERS,
)


@dataclass
class OptimizationProposal:
    proposal_id: str
    parameter: str
    current_value: Any
    proposed_value: Any
    evidence: str
    benchmark_delta: Dict[str, float] = field(default_factory=dict)
    status: str = "PROPOSED"  # PROPOSED, BENCHMARKED, APPLIED, REJECTED, ROLLED_BACK
    created_at: float = field(default_factory=time.time)
    applied_at: Optional[float] = None
    previous_value: Optional[Any] = None


class OptimizationEngine:
    """
    Analyzes system telemetry to propose safe operational threshold optimizations.
    Absolute Invariant: ZERO SELF-MODIFYING CODE.
    Security policies and safety rules are strictly immutable.
    Proposals must be benchmarked offline before promotion.
    """

    def __init__(self, adaptive_router: Optional[AdaptiveRoutingPolicy] = None):
        self.adaptive_router = adaptive_router
        self.proposals: Dict[str, OptimizationProposal] = {}
        self.config_history: List[Dict[str, Any]] = []

    def create_proposal(
        self,
        parameter: str,
        proposed_value: Any,
        evidence: str,
    ) -> Tuple[bool, str, Optional[OptimizationProposal]]:
        """Creates an optimization proposal if the parameter is legally tunable."""
        # 1. Reject immutable security settings
        if parameter in IMMUTABLE_SECURITY_PARAMETERS:
            return False, f"REJECTED_BY_IMMUTABLE_SECURITY_POLICY: parameter '{parameter}' cannot be modified", None

        # 2. Check adaptive router rules
        if self.adaptive_router is not None:
            valid, reason = self.adaptive_router.propose_threshold_tuning(parameter, proposed_value, evidence)
            if not valid:
                return False, reason, None

        proposal_id = f"opt_{int(time.time())}_{parameter[:8]}"
        current_val = getattr(self.adaptive_router, parameter, None) if self.adaptive_router else None
        prop = OptimizationProposal(
            proposal_id=proposal_id,
            parameter=parameter,
            current_value=current_val,
            proposed_value=proposed_value,
            evidence=evidence,
        )
        self.proposals[proposal_id] = prop
        return True, "PROPOSAL_CREATED", prop

    def benchmark_proposal_offline(
        self,
        proposal_id: str,
        benchmark_evaluator: Callable[[str, Any], Dict[str, float]],
    ) -> Tuple[bool, str]:
        """Runs the proposal against an offline stored benchmark corpus."""
        prop = self.proposals.get(proposal_id)
        if not prop:
            return False, "PROPOSAL_NOT_FOUND"

        # Run offline benchmark
        deltas = benchmark_evaluator(prop.parameter, prop.proposed_value)
        prop.benchmark_delta = deltas

        # Check if accuracy regressed
        accuracy_delta = deltas.get("accuracy_delta", 0.0)
        wrong_actions = deltas.get("wrong_actions", 0)

        if wrong_actions > 0 or accuracy_delta < 0.0:
            prop.status = "REJECTED"
            return False, f"BENCHMARK_FAILED: accuracy regressed by {accuracy_delta} with {wrong_actions} wrong actions"

        prop.status = "BENCHMARKED"
        return True, "BENCHMARK_PASSED"

    def apply_proposal(self, proposal_id: str) -> Tuple[bool, str]:
        """Promotes and applies a benchmarked proposal."""
        prop = self.proposals.get(proposal_id)
        if not prop:
            return False, "PROPOSAL_NOT_FOUND"
        if prop.status != "BENCHMARKED":
            return False, f"CANNOT_APPLY: proposal status is {prop.status}, must be BENCHMARKED"

        if self.adaptive_router is not None:
            success = self.adaptive_router.apply_verified_proposal(prop.parameter, prop.proposed_value)
            if success:
                prop.status = "APPLIED"
                prop.applied_at = time.time()
                prop.previous_value = prop.current_value
                self.config_history.append({
                    "proposal_id": prop.proposal_id,
                    "parameter": prop.parameter,
                    "new_value": prop.proposed_value,
                    "timestamp": prop.applied_at,
                })
                return True, "APPLIED"

        return False, "APPLY_FAILED"

    def rollback(self, proposal_id: str) -> bool:
        prop = self.proposals.get(proposal_id)
        if prop and prop.status == "APPLIED" and prop.previous_value is not None:
            if self.adaptive_router is not None:
                self.adaptive_router.apply_verified_proposal(prop.parameter, prop.previous_value)
            prop.status = "ROLLED_BACK"
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_proposals": len(self.proposals),
            "applied_proposals": sum(1 for p in self.proposals.values() if p.status == "APPLIED"),
            "rejected_proposals": sum(1 for p in self.proposals.values() if p.status == "REJECTED"),
            "config_history_count": len(self.config_history),
        }
