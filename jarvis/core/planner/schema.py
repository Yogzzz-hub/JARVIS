"""Task Graph contracts and Pydantic schemas for Phase 4."""

from enum import StrEnum
from typing import Any, Optional, Union
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field


class FailurePolicy(StrEnum):
    FAIL_DEPENDENTS = "FAIL_DEPENDENTS"
    CONTINUE_INDEPENDENT = "CONTINUE_INDEPENDENT"
    OPTIONAL = "OPTIONAL"


class ConditionOperator(StrEnum):
    EQ = "EQ"
    NE = "NE"
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"
    EXISTS = "EXISTS"
    NOT_EXISTS = "NOT_EXISTS"
    IS_TRUE = "IS_TRUE"
    IS_FALSE = "IS_FALSE"


class ValueBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    node_id: str = Field(pattern=r"^n[1-9][0-9]*$")
    output_path: str = Field(min_length=1)


class ConditionDSL(BaseModel):
    model_config = ConfigDict(extra="forbid")
    left: Union[ValueBinding, str, int, float, bool, None]
    operator: ConditionOperator
    right: Optional[Union[ValueBinding, str, int, float, bool, None]] = None


class TaskNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^n[1-9][0-9]*$")
    tool: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    args: dict[str, Any] = Field(default_factory=dict)
    bindings: dict[str, ValueBinding] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    condition: Optional[ConditionDSL] = None
    on_failure: FailurePolicy = FailurePolicy.FAIL_DEPENDENTS
    description: str = Field(default="", max_length=200)


class CapabilityGap(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capability: str
    reason: str
    related_tools: list[str] = Field(default_factory=list)


class BlockingQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str
    parameter: Optional[str] = None
    options: list[str] = Field(default_factory=list)


class TaskGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")
    graph_id: str = Field(default_factory=lambda: f"g_{uuid4().hex[:12]}")
    goal: str
    goal_summary: str = ""
    nodes: list[TaskNode] = Field(default_factory=list)
    blocking_questions: list[BlockingQuestion] = Field(default_factory=list)
    missing_capabilities: list[CapabilityGap] = Field(default_factory=list)
    planner_model: Optional[str] = None
    registry_version: str = "v1.0.0"
    schema_version: str = "1.0.0"


class GraphStatus(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    CAPABILITY_GAP = "CAPABILITY_GAP"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"


class PlanConfidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class NodeState(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED_DEPENDENCY_FAILED = "SKIPPED_DEPENDENCY_FAILED"
    SKIPPED_CONDITION_FALSE = "SKIPPED_CONDITION_FALSE"
    BLOCKED_AMBIGUOUS_INPUT = "BLOCKED_AMBIGUOUS_INPUT"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"


class NodeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    node_id: str
    tool: str
    state: NodeState
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    start_time: float = 0.0
    end_time: float = 0.0


class GraphResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    graph_id: str
    status: GraphStatus
    node_results: dict[str, NodeResult] = Field(default_factory=dict)
    successful_nodes: list[str] = Field(default_factory=list)
    failed_nodes: list[str] = Field(default_factory=list)
    skipped_nodes: list[str] = Field(default_factory=list)
    verification_summary: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0.0
    first_action_ms: float = 0.0
    parallelism_factor: float = 1.0
    user_message_data: str = ""
    needs_policy_confirmation: bool = False
    plan_cache_hit: bool = False


def format_ascii_dag(graph: TaskGraph) -> str:
    """Renders a readable ASCII representation of a TaskGraph."""
    lines = [
        f"Goal: {graph.goal}",
        f"Summary: {graph.goal_summary or 'Multi-step task graph'}",
        f"Nodes ({len(graph.nodes)}):",
    ]
    for n in graph.nodes:
        dep_str = f" <- depends on [{', '.join(n.depends_on)}]" if n.depends_on else " (root)"
        bind_str = f", bindings={list(n.bindings.keys())}" if n.bindings else ""
        lines.append(f"  [{n.id}] {n.tool}({', '.join(f'{k}={v!r}' for k, v in n.args.items())}{bind_str}){dep_str}")

    lines.append("\nExecution DAG:")
    # Build visual level groups
    roots = [n for n in graph.nodes if not n.depends_on]
    intermediates = [n for n in graph.nodes if n.depends_on and any(n.id in other.depends_on for other in graph.nodes)]
    leaves = [n for n in graph.nodes if n.depends_on and not any(n.id in other.depends_on for other in graph.nodes)]

    if len(roots) == 2 and len(graph.nodes) >= 3:
        r1, r2 = roots[0], roots[1]
        next_nodes = [n for n in graph.nodes if r1.id in n.depends_on or r2.id in n.depends_on]
        chain = " -> ".join(f"[{n.id} {n.tool}]" for n in next_nodes)
        lines.append(f"  [{r1.id} {r1.tool}] -----+")
        lines.append(f"                    +--> {chain}")
        lines.append(f"  [{r2.id} {r2.tool}] -----+")
    elif len(roots) == 1 and len(graph.nodes) > 1:
        chain = " --> ".join(f"[{n.id} {n.tool}]" for n in graph.nodes)
        lines.append(f"  {chain}")
    else:
        for n in graph.nodes:
            deps = f" -> depends on {n.depends_on}" if n.depends_on else ""
            lines.append(f"  [{n.id}: {n.tool}]{deps}")

    return "\n".join(lines)


