"""Side-effect-free Stage 2.1 eligibility boundary; never calls an executor."""
from __future__ import annotations

from enum import Enum


class Decision(str, Enum):
    EXECUTE = "EXECUTE"
    NO_ACTION = "NO_ACTION"
    CLARIFY = "CLARIFY"
    ESCALATE_TO_SEMANTIC_MODEL = "ESCALATE_TO_SEMANTIC_MODEL"
    ESCALATE_TO_PLANNER = "ESCALATE_TO_PLANNER"


NO_ACTION_SPEECH = {"QUESTION", "CAPABILITY_QUERY", "STATEMENT", "HYPOTHETICAL",
                    "NEGATED_COMMAND", "CHAT", "STATUS_QUERY", "INFORMATION_REQUEST",
                    "ACKNOWLEDGEMENT"}


def decide(speech_act: str, *, confidence: float, frame_complete: bool,
           pending_frame: bool = False, policy_approved: bool = False) -> Decision:
    """EXECUTE means eligible after policy; it is never a tool invocation."""
    if speech_act in NO_ACTION_SPEECH:
        return Decision.NO_ACTION
    if speech_act == "AMBIGUOUS":
        return Decision.CLARIFY
    if confidence < .9:
        return Decision.ESCALATE_TO_SEMANTIC_MODEL
    if speech_act == "CORRECTION" and not pending_frame:
        return Decision.CLARIFY
    if speech_act == "META_CONTROL" and not pending_frame:
        return Decision.CLARIFY
    if speech_act not in {"COMMAND", "CORRECTION", "META_CONTROL"}:
        return Decision.ESCALATE_TO_SEMANTIC_MODEL
    if not frame_complete:
        return Decision.ESCALATE_TO_PLANNER
    if not policy_approved:
        return Decision.ESCALATE_TO_PLANNER
    return Decision.EXECUTE
