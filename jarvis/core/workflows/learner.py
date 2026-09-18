"""Workflow learner detecting repeated equivalent execution graphs (Phase 12)."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple
from jarvis.core.workflows.models import (
    WorkflowCandidate,
    WorkflowGraphTemplate,
    WorkflowStatus,
)
from jarvis.core.workflows.normalizer import WorkflowNormalizer


DEFAULT_LEARNING_THRESHOLD = 3


class WorkflowLearner:
    """
    Monitors verified task graphs and detects repeated patterns.
    When a graph pattern reaches the learning threshold (>= 3 equivalent executions),
    it generates a candidate proposal for explicit user approval.
    Invariant: Learner only proposes; it NEVER automatically creates or executes workflows.
    """

    def __init__(self, threshold: int = DEFAULT_LEARNING_THRESHOLD):
        self.threshold = threshold
        self._observed_candidates: Dict[str, WorkflowCandidate] = {}

    def observe_execution(
        self,
        goal: str,
        nodes_data: List[Dict[str, Any]],
        episode_id: str,
        is_verified_success: bool = True,
    ) -> Optional[WorkflowCandidate]:
        """
        Observes a successful verified execution graph.
        Returns a WorkflowCandidate if the pattern reaches the proposal threshold.
        """
        if not is_verified_success or not nodes_data:
            return None

        # Normalize graph
        graph_template, slots = WorkflowNormalizer.normalize_graph(nodes_data)
        shape_hash = graph_template.shape_hash

        if shape_hash in self._observed_candidates:
            candidate = self._observed_candidates[shape_hash]
            candidate.occurrence_count += 1
            candidate.last_used = time.time()
            if episode_id not in candidate.evidence_episodes:
                candidate.evidence_episodes.append(episode_id)

            if candidate.occurrence_count >= self.threshold and candidate.status == WorkflowStatus.PROPOSED:
                return candidate
        else:
            # Generate clean suggested name from goal
            clean_name = self._suggest_workflow_name(goal)
            risk_summary = "DESTRUCTIVE" if any(n.risk == "DESTRUCTIVE" for n in graph_template.nodes) else (
                "EXTERNAL_EFFECT" if any(n.risk == "EXTERNAL_EFFECT" for n in graph_template.nodes) else "READ_ONLY"
            )
            candidate = WorkflowCandidate(
                candidate_id=f"cand_{shape_hash[:8]}",
                name_suggestion=clean_name,
                normalized_goal=goal.strip(),
                graph_shape_hash=shape_hash,
                graph_template=graph_template,
                variable_slots=slots,
                risk_summary=risk_summary,
                occurrence_count=1,
                evidence_episodes=[episode_id],
                status=WorkflowStatus.PROPOSED,
            )
            self._observed_candidates[shape_hash] = candidate
            if candidate.occurrence_count >= self.threshold and candidate.status == WorkflowStatus.PROPOSED:
                return candidate

        return None

    def get_candidate(self, candidate_id: str) -> Optional[WorkflowCandidate]:
        for cand in self._observed_candidates.values():
            if cand.candidate_id == candidate_id:
                return cand
        return None

    def list_candidates(self) -> List[WorkflowCandidate]:
        return list(self._observed_candidates.values())

    def _suggest_workflow_name(self, goal: str) -> str:
        # Strip common conversational prefixes
        clean = goal.lower()
        for prefix in ("can you ", "please ", "i want to ", "jarvis ", "help me "):
            if clean.startswith(prefix):
                clean = clean[len(prefix):]
        words = clean.strip().split()
        if len(words) <= 4:
            return " ".join(words).title()
        return " ".join(words[:4]).title()
