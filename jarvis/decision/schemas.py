"""Typed decision API (System-One style): STATE + QUESTIONS -> typed answers.

Three primitives, never free text:

* CHOICE      - pick one of a closed set of options (with a probability for each option)
* SCORE       - place the request on an ordered scale (value + normalised 0..1 position)
* PROBABILITY - likelihood that a yes/no property holds
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional, Union

ROUTE_FAMILIES: tuple[str, ...] = (
    "APP",          # open / close / switch applications
    "SYSTEM",       # volume, brightness, power, time, settings, diagnostics
    "FILE",         # find / open / move / organise local files
    "RAG",          # questions answered from the user's own documents, notes, chats
    "KNOWLEDGE",    # general knowledge / explanation / writing (LLM, no tool)
    "WEB",          # needs fresh information from the internet
    "BROWSER",      # operate websites (open, search a site, fill forms)
    "DESKTOP",      # click / type / operate any desktop UI, screen understanding
    "MEDIA",        # play / pause / skip music and video
    "PHONE",        # control the Android phone
    "TRANSFER",     # move files between PC and phone
    "WHATSAPP",     # read / send / reply / summarise WhatsApp
    "GOOGLE",       # Gmail, Calendar, Drive
    "REMINDER",     # reminders, notes, timers
    "PACKAGE",      # install / uninstall / update software
    "DEVELOPMENT",  # code, git, terminal, tests
    "WORKFLOW",     # routines, briefings, workspaces
    "PLANNER",      # multi-step goals spanning several families
    "CLARIFY",      # needs more information before anything can happen
    "UNKNOWN",      # unsupported / out of scope / nonsense
)

COMPLEXITY_LEVELS: tuple[str, ...] = ("TRIVIAL", "SIMPLE", "MODERATE", "COMPLEX", "VERY_COMPLEX")
MODEL_CLASSES: tuple[str, ...] = ("NONE", "TINY", "SMALL", "PLANNER", "VISION")
BINARY_HEADS: tuple[str, ...] = (
    "is_action", "needs_llm", "needs_planner", "needs_context", "needs_web",
    "external_effect", "destructive", "ambiguous", "supported",
)


@dataclass
class DecisionState:
    """Compact context vector - never the whole conversation."""
    text: str
    channel: str = "local"
    resources: list[str] = field(default_factory=list)      # e.g. ["FileResource"]
    active_topic_type: str = ""                               # e.g. "ApplicationTopic"
    previous_route: str = ""                                  # last JDE / router family
    pending_task: str = ""                                    # e.g. "web_task"
    pending_confirmation: bool = False
    current_app: str = ""
    unavailable: list[str] = field(default_factory=list)      # families not configured (e.g. ["WHATSAPP"])

    def signature(self) -> str:
        return "|".join([
            self.channel, ",".join(sorted(self.resources)), self.active_topic_type, self.previous_route,
            self.pending_task, "1" if self.pending_confirmation else "0", self.current_app.lower(),
            ",".join(sorted(self.unavailable)),
        ])


@dataclass
class ChoiceQuestion:
    name: str
    options: tuple[str, ...]
    kind: Literal["choice"] = "choice"


@dataclass
class ScoreQuestion:
    name: str
    scale: tuple[str, ...]
    kind: Literal["score"] = "score"


@dataclass
class ProbabilityQuestion:
    name: str
    kind: Literal["probability"] = "probability"


Question = Union[ChoiceQuestion, ScoreQuestion, ProbabilityQuestion]

DEFAULT_QUESTIONS: tuple[Question, ...] = (
    ChoiceQuestion("route_family", ROUTE_FAMILIES),
    ScoreQuestion("complexity", COMPLEXITY_LEVELS),
    *(ProbabilityQuestion(name) for name in BINARY_HEADS),
)


@dataclass
class DecisionRequest:
    state: DecisionState
    questions: tuple[Question, ...] = DEFAULT_QUESTIONS


@dataclass
class ChoiceAnswer:
    value: str
    confidence: float
    probabilities: dict[str, float]
    top_k: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class ScoreAnswer:
    value: str
    score: float  # 0 (first level) .. 1 (last level), expectation over the scale


@dataclass
class ProbabilityAnswer:
    probability: float


Answer = Union[ChoiceAnswer, ScoreAnswer, ProbabilityAnswer]

GateAction = Literal["EXECUTE", "FALLBACK", "CLARIFY", "ABSTAIN", "UNSUPPORTED"]


@dataclass
class Gate:
    """What the application should do with the decision (JDE itself never executes)."""
    action: GateAction
    risk_class: str
    threshold: float
    reason: str = ""


@dataclass
class DecisionResult:
    answers: dict[str, Answer]
    gate: Gate
    model_class: str
    families: list[tuple[str, float]]            # multi-family top-K (for capability retrieval / planner)
    disagreement: bool = False
    availability: str = "AVAILABLE"              # AVAILABLE | NOT_CONFIGURED
    versions: dict[str, str] = field(default_factory=dict)
    latency_ms: float = 0.0
    cache_hit: bool = False
    signals: dict[str, float] = field(default_factory=dict)

    # convenience accessors -------------------------------------------------------------
    @property
    def route(self) -> ChoiceAnswer:
        return self.answers["route_family"]  # type: ignore[return-value]

    def p(self, name: str) -> float:
        ans = self.answers.get(name)
        return ans.probability if isinstance(ans, ProbabilityAnswer) else 0.0

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name, ans in self.answers.items():
            if isinstance(ans, ChoiceAnswer):
                out[name] = {"value": ans.value, "confidence": round(ans.confidence, 4), "top_k": [(k, round(v, 4)) for k, v in ans.top_k]}
            elif isinstance(ans, ScoreAnswer):
                out[name] = {"value": ans.value, "score": round(ans.score, 4)}
            else:
                out[name] = round(ans.probability, 4)
        out["gate"] = asdict(self.gate)
        out["model_class"] = self.model_class
        out["families"] = [(k, round(v, 4)) for k, v in self.families]
        out["disagreement"] = self.disagreement
        out["availability"] = self.availability
        out["versions"] = self.versions
        out["latency_ms"] = round(self.latency_ms, 3)
        out["cache_hit"] = self.cache_hit
        return out


@dataclass
class LabeledExample:
    """One training / evaluation record (semantic labels only - no benchmark ids)."""
    text: str
    route: str
    families: list[str] = field(default_factory=list)
    complexity: int = 1
    is_action: bool = True
    needs_llm: bool = False
    needs_planner: bool = False
    needs_context: bool = False
    needs_web: bool = False
    external_effect: bool = False
    destructive: bool = False
    ambiguous: bool = False
    supported: bool = True
    context: dict[str, Any] = field(default_factory=dict)
    source: str = ""

    def state(self) -> DecisionState:
        c = self.context or {}
        return DecisionState(
            text=self.text, channel=c.get("channel", "local"), resources=list(c.get("resources", [])),
            active_topic_type=c.get("active_topic_type", ""), previous_route=c.get("previous_route", ""),
            pending_task=c.get("pending_task", ""), pending_confirmation=bool(c.get("pending_confirmation", False)),
            current_app=c.get("current_app", ""), unavailable=list(c.get("unavailable", [])),
        )

    def binary(self, head: str) -> int:
        return int(bool(getattr(self, head)))


def optional(v: Optional[str]) -> str:
    return v or ""
