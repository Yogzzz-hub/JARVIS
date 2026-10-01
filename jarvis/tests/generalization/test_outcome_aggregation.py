"""Comprehensive test suite for Outcome Aggregation, DAG Dependency Logic,
Meta-Instruction Routing, and Error Sanitization in JARVIS EDGE.
"""

import asyncio
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock

from jarvis.core.commands.contracts import CommandRequest, CommandResult
from jarvis.core.commands.service import CommandService
from jarvis.core.metrics.clock import Clock
from jarvis.core.planner.schema import (
    FailurePolicy,
    GraphStatus,
    NodeResult,
    NodeState,
    TaskGraph,
    TaskNode,
    ValueBinding,
)
from jarvis.core.response.formatter import ResponseFormatter
from jarvis.core.router.guards import check_negation
from jarvis.core.router.meta_policy import match_meta_policy
from jarvis.core.router.models import RouteLane
from jarvis.core.router.router import SmartRouter
from jarvis.core.router.slots import parse_folder_path
from jarvis.core.scheduler.outcomes import (
    ActionOutcome,
    ActionStatus,
    CommandOutcome,
    CommandStatus,
    ResultAggregator,
)
from jarvis.core.scheduler.scheduler import DAGScheduler
from jarvis.core.tasks.manager import State, Task, TaskManager
from jarvis.security.paths import canonicalize_path, get_known_folder
from jarvis.tools.base import Contract, RiskLevel, Tool, ToolDefinition, ToolResult, VerificationResult
from jarvis.tools.registry import ToolRegistry


class DummyInput(Contract):
    param: str = ""
    fail: bool = False


class DummyOutput(Contract):
    output_text: str = "ok"


class DummyTool(Tool):
    def __init__(self, name: str, fail: bool = False):
        self.definition = ToolDefinition(
            name=name,
            description=f"Dummy tool {name}",
            input_model=DummyInput,
            output_model=DummyOutput,
            read_only=True,
            risk=RiskLevel.READ_ONLY,
        )
        self.fail = fail

    async def run(self, arguments: DummyInput) -> DummyOutput:
        if self.fail or arguments.fail:
            raise RuntimeError(f"Tool {self.definition.name} failed execution")
        return DummyOutput(output_text=f"{self.definition.name} executed")


@pytest.fixture
def registry():
    reg = ToolRegistry()
    reg.register(DummyTool("open_notepad"))
    reg.register(DummyTool("open_calculator", fail=True))
    reg.register(DummyTool("find_pdf"))
    reg.register(DummyTool("open_pdf"))
    return reg


@pytest.mark.asyncio
async def test_partial_dag_success_and_independent_branch_failure(registry):
    """Scenario 1 & 2:
    Notepad succeeded while Calculator failed, and PDF was skipped (dependent on Calculator).
    Expected: PARTIAL_SUCCESS, Notepad succeeded, Calculator failed, dependent PDF skipped.
    Critical Assertion: PARTIAL SUCCESS MISLABELED FAILED = 0
    Critical Assertion: WRONG DEPENDENCY SKIP = 0
    """
    scheduler = DAGScheduler(registry=registry)

    # Node 1: Notepad (independent root)
    # Node 2: Calculator (independent root, will fail)
    # Node 3: PDF (dependent on Calculator)
    graph = TaskGraph(
        goal="open notepad, open calculator, and open latest pdf",
        nodes=[
            TaskNode(id="n1", tool="open_notepad", description="Open Notepad"),
            TaskNode(id="n2", tool="open_calculator", description="Open Calculator"),
            TaskNode(id="n3", tool="find_pdf", depends_on=["n2"], description="Find PDF"),
        ],
    )

    result = await scheduler.execute(graph)

    # 1. Independent branch Notepad must succeed
    assert "n1" in result.successful_nodes
    assert result.node_results["n1"].state == NodeState.SUCCESS

    # 2. Calculator must fail
    assert "n2" in result.failed_nodes
    assert result.node_results["n2"].state == NodeState.FAILED

    # 3. Dependent branch PDF must be skipped because upstream n2 failed
    assert "n3" in result.skipped_nodes
    assert result.node_results["n3"].state == NodeState.SKIPPED_DEPENDENCY_FAILED

    # 4. Result aggregation: must be PARTIAL, not FAILED!
    assert result.status == GraphStatus.PARTIAL

    # 5. ResultAggregator outcome verification
    agg = ResultAggregator.aggregate(result.action_outcomes, command_id="test-cmd")
    assert agg.status == CommandStatus.PARTIAL_SUCCESS
    assert agg.successful_count == 1
    assert agg.failed_count == 1
    assert agg.skipped_count == 1

    # Check natural composed outcome message
    msg = agg.message
    assert "Notepad" in msg
    assert "Calculator failed" in msg
    assert "dependent" in msg and "skipped" in msg
    assert "Task graph execution failed" not in msg

    # Critical counter checks
    partial_success_mislabeled_failed = 1 if agg.status == CommandStatus.FAILED else 0
    wrong_dependency_skip = 1 if "n1" in result.skipped_nodes else 0

    assert partial_success_mislabeled_failed == 0
    assert wrong_dependency_skip == 0


@pytest.mark.asyncio
async def test_independent_branch_continues_on_sibling_failure(registry):
    """Scenario:
    Node A (Notepad) succeeds.
    Node B (Calculator) fails.
    Node C (PDF) is INDEPENDENT of Calculator (depends_on=[]).
    Expected: Node C runs and succeeds. Only Node B fails.
    Critical Assertion: WRONG DEPENDENCY SKIP = 0
    """
    scheduler = DAGScheduler(registry=registry)

    # All three nodes are independent roots
    graph = TaskGraph(
        goal="open notepad, open calculator, find pdf",
        nodes=[
            TaskNode(id="n1", tool="open_notepad", description="Open Notepad"),
            TaskNode(id="n2", tool="open_calculator", description="Open Calculator"),
            TaskNode(id="n3", tool="find_pdf", depends_on=[], description="Find PDF"),
        ],
    )

    result = await scheduler.execute(graph)

    # Both independent branches n1 and n3 MUST succeed
    assert "n1" in result.successful_nodes
    assert "n3" in result.successful_nodes
    assert "n2" in result.failed_nodes
    assert len(result.skipped_nodes) == 0

    agg = ResultAggregator.aggregate(result.action_outcomes)
    assert agg.status == CommandStatus.PARTIAL_SUCCESS
    assert agg.successful_count == 2
    assert agg.failed_count == 1
    assert agg.skipped_count == 0

    wrong_dependency_skip = 1 if len(result.skipped_nodes) > 0 else 0
    assert wrong_dependency_skip == 0


@pytest.mark.asyncio
async def test_meta_instruction_routing_and_no_negation_rejection():
    """Scenario:
    Sentences modifying response policy must route to response_policy (RouteLane.CONTROL)
    and NEVER trigger COMMAND_NEGATED.
    Critical Assertion: META INSTRUCTION EXECUTED AS TOOL = 0
    """
    meta_sentences = [
        "If only two actions succeed, don't call the whole task a failure.",
        "Don't say 'done' until all required verification finishes.",
        "keep replies short",
        "tell me exactly what failed",
        "don't automatically retry uncertain sends",
    ]

    meta_instruction_executed_as_tool = 0

    for sentence in meta_sentences:
        # 1. match_meta_policy must detect it
        dec = match_meta_policy(sentence, "req-meta")
        assert dec is not None, f"Failed to match meta policy: {sentence}"
        assert dec.lane == RouteLane.CONTROL
        assert dec.intent == "response_policy"

        # 2. check_negation must NOT mark it as negated tool command
        is_neg, constraints = check_negation(sentence)
        assert is_neg is False, f"Meta instruction incorrectly flagged as negated: {sentence}"

        # 3. SmartRouter routing order check
        router = SmartRouter()
        route_res = await router.route(CommandRequest(text=sentence))
        assert route_res.lane in (RouteLane.CONTROL, RouteLane.LANE_0)
        assert route_res.intent in ("response_policy", "standing_rule")
        assert route_res.reason_code != "NEGATED_ACTION"

        # Check if lane is tool execution lane (LANE_0 with tool intent or LANE_1)
        if route_res.lane == RouteLane.LANE_1 or (route_res.lane == RouteLane.LANE_0 and route_res.intent not in ("response_policy", "standing_rule", "recent_actions")):
            meta_instruction_executed_as_tool += 1

    assert meta_instruction_executed_as_tool == 0


@pytest.mark.asyncio
async def test_stale_plan_prevention_on_meta_instruction(tmp_path):
    """Scenario:
    When a meta-instruction is processed, an existing pending execution or prior plan
    must NEVER be replayed.
    Critical Assertion: STALE PLAN REPLAY = 0
    """
    from jarvis.tests.ai_harness import AIHarness
    harness = AIHarness(tmp_path, responder=lambda p: "ok")
    service = harness.service

    # Simulate a pending graph execution in the service
    mock_graph = TaskGraph(goal="old task", nodes=[TaskNode(id="n1", tool="open_notepad")])
    service._pending_execution = {"type": "graph", "graph": mock_graph}

    req = CommandRequest(text="Don't say 'done' until all required verification finishes.")
    result = await service.handle(req)

    # 1. Command must succeed cleanly with policy update confirmation
    assert result.state == "SUCCESS"
    assert "verification" in result.message.lower()

    # 2. The pending execution must NOT have been consumed or executed by this meta instruction!
    # STALE PLAN REPLAY MUST BE 0
    stale_plan_replay = 0 if service._pending_execution is not None else 1
    assert stale_plan_replay == 0


@pytest.mark.asyncio
async def test_verification_rule_and_false_verified_prevention(tmp_path):
    """Scenario:
    Execution success != verification success.
    If verifier fails or returns verified=False, task must NEVER be finalized as SUCCESS/COMPLETED.
    Critical Assertion: FALSE VERIFIED = 0
    """
    from jarvis.tests.ai_harness import AIHarness
    harness = AIHarness(tmp_path, responder=lambda p: "ok")
    service = harness.service
    task = Task(request_id="task-verif-test", source="cli", raw_text="test action", clock=Clock(), state=State.VERIFYING)

    # Tool returned success, but verifier returned verified=False
    tool_res = ToolResult(success=True, data={"result": "created"}, tool_name="test_tool")
    failed_verif = VerificationResult(verified=False, confidence=0.0, error="Element was not created")

    res = service._finalize(
        task=task,
        state=State.SUCCESS,  # Attempting to finalize as SUCCESS
        message="Done.",
        tool_result=tool_res,
        verification=failed_verif,
        clock=Clock(),
        current=task,
    )

    # The safety guard MUST intercept and reject premature SUCCESS
    assert res.state != "SUCCESS"
    assert res.state != "COMPLETED"
    assert res.state in ("FAILED", "UNCERTAIN")

    false_verified = 1 if res.state in ("SUCCESS", "COMPLETED") else 0
    assert false_verified == 0


@pytest.mark.asyncio
async def test_duplicate_final_response_deduplication(tmp_path):
    """Scenario:
    One command_id must produce exactly ONE final user-facing outcome.
    Subsequent finalize calls for the same command_id must return the existing finalized outcome.
    Critical Assertion: DUPLICATE FINAL RESPONSE = 0
    """
    from jarvis.tests.ai_harness import AIHarness
    harness = AIHarness(tmp_path, responder=lambda p: "ok")
    service = harness.service
    task = Task(request_id="task-dedup-1", source="cli", raw_text="test action", clock=Clock(), state=State.VERIFYING)

    res1 = service._finalize(
        task=task,
        state=State.SUCCESS,
        message="Final response 1",
        tool_result=ToolResult(success=True, data={}, tool_name="test_tool"),
        verification=VerificationResult(verified=True, confidence=1.0, evidence={"verified": True}),
        clock=Clock(),
        current=task,
    )

    # Second call for the same task
    res2 = service._finalize(
        task=task,
        state=State.FAILED,
        message="Duplicate response 2",
        tool_result=ToolResult(success=False, error="Duplicate error", tool_name="test_tool"),
        verification=None,
        clock=Clock(),
        current=task,
    )

    # Must be identical object and content
    assert res1.message == res2.message == "Final response 1"
    assert res1.state == res2.state == "SUCCESS"
    assert res1.outcome_version == res2.outcome_version == 1

    duplicate_final_response = 0 if res1 is res2 else 1
    assert duplicate_final_response == 0


def test_raw_internal_path_leak_prevention_and_desktop_recovery():
    """Scenario:
    Error containing raw workspace internal desktop path must be sanitized to:
    "I couldn't access the configured Desktop location."
    Desktop path slot must resolve to real Windows Known Folder.
    Critical Assertion: RAW INTERNAL PATH LEAK = 0
    """
    raw_error = (
        r"[WinError 2] The system cannot find the file specified: "
        r"'C:\Users\ashok\OneDrive\Desktop\New folder (2)\Desktop'"
    )

    sanitized = ResponseFormatter.sanitize_error(raw_error, tool_name="list_directory")

    # 1. Must NOT leak raw internal path
    assert "New folder (2)" not in sanitized
    assert "WinError" not in sanitized
    assert r"C:\Users" not in sanitized

    # 2. Must match expected human-facing response
    assert sanitized == "I couldn't access the configured Desktop location."

    # 3. Canonicalize path recovery check
    resolved_desktop = canonicalize_path("Desktop")
    assert resolved_desktop.exists()
    assert "New folder (2)\\Desktop" not in str(resolved_desktop)

    raw_internal_path_leak = 1 if "New folder (2)" in sanitized or r"C:\Users" in sanitized else 0
    assert raw_internal_path_leak == 0


def test_result_aggregator_uncertain_and_completed_states():
    """Scenario:
    ResultAggregator status mapping:
    - all verified => COMPLETED
    - zero succeed => FAILED
    - uncertain => UNCERTAIN
    """
    # 1. All verified => COMPLETED
    completed_outcomes = [
        ActionOutcome(step_id="n1", capability="Notepad", status=ActionStatus.VERIFIED_SUCCESS),
        ActionOutcome(step_id="n2", capability="Calculator", status=ActionStatus.VERIFIED_SUCCESS),
    ]
    comp_res = ResultAggregator.aggregate(completed_outcomes)
    assert comp_res.status == CommandStatus.COMPLETED
    assert comp_res.verified is True
    assert "Completed all 2 steps" in comp_res.message

    # 2. Zero succeed => FAILED
    failed_outcomes = [
        ActionOutcome(step_id="n1", capability="Calculator", status=ActionStatus.FAILED, reason="App not found"),
    ]
    fail_res = ResultAggregator.aggregate(failed_outcomes)
    assert fail_res.status == CommandStatus.FAILED
    assert fail_res.verified is False

    # 3. Uncertain => UNCERTAIN
    uncertain_outcomes = [
        ActionOutcome(step_id="n1", capability="SendFile", status=ActionStatus.UNCERTAIN),
    ]
    unc_res = ResultAggregator.aggregate(uncertain_outcomes)
    assert unc_res.status == CommandStatus.UNCERTAIN
    assert unc_res.verified is False
    assert "couldn't verify" in unc_res.message
