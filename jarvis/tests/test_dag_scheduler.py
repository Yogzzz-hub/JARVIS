"""Tests for DAG Scheduler, structured concurrency, failure isolation, and resource locks (Phase 4)."""

import asyncio
import time
import pytest
from pydantic import BaseModel, Field

from jarvis.core.planner.schema import (
    ConditionDSL,
    ConditionOperator,
    FailurePolicy,
    GraphStatus,
    NodeState,
    TaskGraph,
    TaskNode,
    ValueBinding,
)
from jarvis.core.scheduler.locks import ResourceLockManager
from jarvis.core.scheduler.models import SchedulerConfig
from jarvis.core.scheduler.scheduler import DAGScheduler
from jarvis.tools.base import Contract, RiskLevel, Tool, ToolDefinition
from jarvis.tools.registry import ToolRegistry


# Mock tools for scheduler tests
class MockInput(Contract):
    param: str = "default"
    delay_s: float = 0.0
    fail: bool = False
    resource_key: str = ""
    path: str = ""



class MockOutput(Contract):
    result_text: str
    result_code: int = 0


class MockTool(Tool):
    def __init__(self, name: str, risk: RiskLevel = RiskLevel.READ_ONLY, timeout_s: float = 2.0):
        self.definition = ToolDefinition(
            name=name,
            description=f"Mock tool {name}",
            input_model=MockInput,
            output_model=MockOutput,
            read_only=(risk == RiskLevel.READ_ONLY),
            risk=risk,
            timeout_s=timeout_s,
        )
        self.execution_times: list[tuple[float, float]] = []

    def run(self, input_data: MockInput) -> MockOutput:
        t_start = time.perf_counter()
        if input_data.delay_s > 0:
            time.sleep(input_data.delay_s)
        t_end = time.perf_counter()
        self.execution_times.append((t_start, t_end))
        if input_data.fail:
            raise RuntimeError(f"{self.definition.name} explicitly failed")
        return MockOutput(result_text=f"{self.definition.name}_{input_data.param}", result_code=100)


@pytest.fixture
def mock_registry():
    reg = ToolRegistry()
    t1 = MockTool("tool_a")
    t2 = MockTool("tool_b")
    t3 = MockTool("tool_c")
    t_dest = MockTool("destructive_tool", risk=RiskLevel.DESTRUCTIVE)
    reg.discover([t1, t2, t3, t_dest])
    reg.finalize()
    return reg


@pytest.mark.asyncio
async def test_scheduler_executes_independent_nodes_in_parallel(mock_registry):
    # Two nodes with 0.2s delay each; should execute concurrently in ~0.2-0.3s instead of 0.4s
    t_a = mock_registry.get("tool_a")
    t_b = mock_registry.get("tool_b")
    t_a.execution_times.clear()
    t_b.execution_times.clear()

    graph = TaskGraph(
        goal="Parallel execution test",
        nodes=[
            TaskNode(id="n1", tool="tool_a", args={"delay_s": 0.2, "param": "A"}),
            TaskNode(id="n2", tool="tool_b", args={"delay_s": 0.2, "param": "B"}),
        ],
    )
    scheduler = DAGScheduler(mock_registry, config=SchedulerConfig(max_concurrency=4))
    t0 = time.perf_counter()
    result = await scheduler.execute(graph)
    total_time = time.perf_counter() - t0

    assert result.status == GraphStatus.SUCCESS
    assert set(result.successful_nodes) == {"n1", "n2"}
    # Total time should be significantly less than sequential 0.4s
    assert total_time < 0.38
    # Assert timestamp overlap
    assert len(t_a.execution_times) == 1 and len(t_b.execution_times) == 1
    start_a, end_a = t_a.execution_times[0]
    start_b, end_b = t_b.execution_times[0]
    # Check that intervals overlap
    overlap = max(0.0, min(end_a, end_b) - max(start_a, start_b))
    assert overlap > 0.05, f"Expected timestamp overlap, got overlap={overlap}"


@pytest.mark.asyncio
async def test_scheduler_resolves_value_bindings(mock_registry):
    # n1 -> n2 with output binding
    graph = TaskGraph(
        goal="Binding test",
        nodes=[
            TaskNode(id="n1", tool="tool_a", args={"param": "initial"}),
            TaskNode(
                id="n2",
                tool="tool_b",
                depends_on=["n1"],
                bindings={"param": ValueBinding(node_id="n1", output_path="result_text")},
            ),
        ],
    )
    scheduler = DAGScheduler(mock_registry)
    result = await scheduler.execute(graph)

    assert result.status == GraphStatus.SUCCESS
    n2_res = result.node_results["n2"]
    assert n2_res.state == NodeState.SUCCESS
    assert n2_res.output["result_text"] == "tool_b_tool_a_initial"


@pytest.mark.asyncio
async def test_scheduler_failure_isolation(mock_registry):
    # n1 (fails) -> n2 (dependent, should be skipped)
    # n3 (independent, should succeed!)
    graph = TaskGraph(
        goal="Failure isolation test",
        nodes=[
            TaskNode(id="n1", tool="tool_a", args={"fail": True}, on_failure=FailurePolicy.FAIL_DEPENDENTS),
            TaskNode(id="n2", tool="tool_b", depends_on=["n1"]),
            TaskNode(id="n3", tool="tool_c", args={"param": "independent"}),
        ],
    )
    scheduler = DAGScheduler(mock_registry)
    result = await scheduler.execute(graph)

    assert result.status == GraphStatus.PARTIAL
    assert result.node_results["n1"].state == NodeState.FAILED
    assert result.node_results["n2"].state == NodeState.SKIPPED_DEPENDENCY_FAILED
    assert result.node_results["n3"].state == NodeState.SUCCESS
    assert "n3" in result.successful_nodes


@pytest.mark.asyncio
async def test_scheduler_condition_evaluation(mock_registry):
    # n1 produces result_code = 100
    # n2 condition: result_code EQ 100 -> executes
    # n3 condition: result_code EQ 999 -> skipped
    graph = TaskGraph(
        goal="Condition evaluation test",
        nodes=[
            TaskNode(id="n1", tool="tool_a", args={"param": "base"}),
            TaskNode(
                id="n2",
                tool="tool_b",
                depends_on=["n1"],
                condition=ConditionDSL(
                    left=ValueBinding(node_id="n1", output_path="result_code"),
                    operator=ConditionOperator.EQ,
                    right=100,
                ),
            ),
            TaskNode(
                id="n3",
                tool="tool_c",
                depends_on=["n1"],
                condition=ConditionDSL(
                    left=ValueBinding(node_id="n1", output_path="result_code"),
                    operator=ConditionOperator.EQ,
                    right=999,
                ),
            ),
        ],
    )
    scheduler = DAGScheduler(mock_registry)
    result = await scheduler.execute(graph)

    assert result.status in (GraphStatus.SUCCESS, GraphStatus.PARTIAL)
    assert result.node_results["n2"].state == NodeState.SUCCESS
    assert result.node_results["n3"].state == NodeState.SKIPPED_CONDITION_FALSE



@pytest.mark.asyncio
async def test_scheduler_risk_gate_intercepts_destructive(mock_registry):
    graph = TaskGraph(
        goal="Destructive action test",
        nodes=[
            TaskNode(id="n1", tool="destructive_tool", args={"param": "delete"}),
        ],
    )
    scheduler = DAGScheduler(mock_registry, config=SchedulerConfig(enforce_risk_gate=True))
    result = await scheduler.execute(graph)

    assert result.status == GraphStatus.NEEDS_CONFIRMATION
    assert result.needs_policy_confirmation is True
    assert result.node_results["n1"].state == NodeState.FAILED
    assert result.node_results["n1"].error == "NEEDS_POLICY_CONFIRMATION"


@pytest.mark.asyncio
async def test_scheduler_resource_locks_serialize_conflicts(mock_registry):
    # Two nodes attempting to access the same resource key: file:c:\target.txt
    t_a = mock_registry.get("tool_a")
    t_b = mock_registry.get("tool_b")
    t_a.execution_times.clear()
    t_b.execution_times.clear()

    # Note: args specify path="C:\\target.txt"
    graph = TaskGraph(
        goal="Resource lock test",
        nodes=[
            TaskNode(id="n1", tool="tool_a", args={"delay_s": 0.15, "param": "A", "path": "C:\\target.txt"}),
            TaskNode(id="n2", tool="tool_b", args={"delay_s": 0.15, "param": "B", "path": "C:\\target.txt"}),
        ],
    )
    scheduler = DAGScheduler(mock_registry, config=SchedulerConfig(max_concurrency=4))
    result = await scheduler.execute(graph)

    assert result.status == GraphStatus.SUCCESS
    # Because both share file:c:\target.txt, their execution times MUST NOT overlap
    start_a, end_a = t_a.execution_times[0]
    start_b, end_b = t_b.execution_times[0]
    overlap = max(0.0, min(end_a, end_b) - max(start_a, start_b))
    assert overlap < 0.02, f"Expected serialized execution due to lock, but overlap={overlap}"
