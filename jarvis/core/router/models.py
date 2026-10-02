from enum import StrEnum
from typing import Any
from uuid import uuid4
from pydantic import Field
from jarvis.tools.base import Contract

class RouteLane(StrEnum):
    LANE_0 = "LANE_0"
    LANE_1 = "LANE_1"
    LANE_2 = "LANE_2"
    LANE_3 = "LANE_3"
    CLARIFY = "CLARIFY"
    REJECT = "REJECT"
    CONTROL = "CONTROL"

class ComplexityLevel(StrEnum):
    SIMPLE = "SIMPLE"
    COMPOUND = "COMPOUND"
    COMPLEX = "COMPLEX"

class RouteSource(StrEnum):
    HOT_CACHE = "HOT_CACHE"
    EXACT = "EXACT"
    GRAMMAR = "GRAMMAR"
    ALIAS = "ALIAS"
    FUZZY = "FUZZY"
    TINY_MODEL = "TINY_MODEL"
    COMPLEXITY_GATE = "COMPLEXITY_GATE"
    CONTROL = "CONTROL"

class ReasonCode(StrEnum):
    EXACT_PATTERN = "EXACT_PATTERN"
    ALIAS_MATCH = "ALIAS_MATCH"
    FUZZY_HIGH_CONFIDENCE = "FUZZY_HIGH_CONFIDENCE"
    LLM_CLASSIFIED = "LLM_CLASSIFIED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    AMBIGUOUS_TOP_TWO = "AMBIGUOUS_TOP_TWO"
    MULTI_STEP = "MULTI_STEP"
    UNKNOWN_INTENT = "UNKNOWN_INTENT"
    NEGATED_ACTION = "NEGATED_ACTION"
    MISSING_REQUIRED_SLOT = "MISSING_REQUIRED_SLOT"
    CONTROL_COMMAND = "CONTROL_COMMAND"
    QUESTION_NOT_COMMAND = "QUESTION_NOT_COMMAND"
    COMPOUND_COMMAND = "COMPOUND_COMMAND"
    POLICY_BLOCKED = "POLICY_BLOCKED"          # refused by safety / domain policy (not ambiguity, not confirmation)

class SubCommand(Contract):
    intent: str
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)

from pydantic import BaseModel, ConfigDict, Field

class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=False)
    request_id: str = Field(default_factory=lambda: uuid4().hex)
    lane: RouteLane
    intent: str | None = None
    slots: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    source: RouteSource
    complexity: ComplexityLevel = ComplexityLevel.SIMPLE
    risk: str | None = None
    missing_slots: list[str] = Field(default_factory=list)
    needs_planner: bool = False
    needs_visual_context: bool = False
    clarification: str | None = None
    normalized_text: str
    routing_ms: float = 0.0
    candidate_count: int = 0
    model_used: str | None = None
    cache_hit: bool = False
    reason_code: str
    subcommands: list[SubCommand] = Field(default_factory=list)
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    breakdown_ms: dict[str, float] = Field(default_factory=dict)
    context_trace: dict[str, Any] | None = None
    # What the decision is waiting for - kept apart so a confirmation is never mistaken for an ambiguity:
    # NEEDS_CLARIFICATION (what / which?), NEEDS_CONFIRMATION (this exact action - yes?), NEEDS_AUTHORIZATION (a person
    # must act, e.g. a sign-in), BLOCKED_BY_POLICY (refused), READY_TO_EXECUTE. None = derived (see ``state``).
    decision_state: str | None = None

    @property
    def state(self) -> str:
        if self.decision_state:
            return self.decision_state
        lane = getattr(self.lane, "value", self.lane)
        if lane == "REJECT":
            return "BLOCKED_BY_POLICY" if (self.slots or {}).get("refused") or self.reason_code == "POLICY_BLOCKED" else "NEGATED"
        if lane == "CLARIFY":
            return "NEEDS_CLARIFICATION"
        if lane == "CONTROL":
            return "CONTROL"
        if lane == "LANE_2":
            return "PLAN" if self.needs_planner else "ANSWER"
        return "READY_TO_EXECUTE" if self.intent else "NEEDS_CLARIFICATION"
