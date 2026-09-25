"""Execution Generalization Tests for Phase 4 DAG Scheduler.

Tests:
1. Prerequisite Dependency Failure:
   - Upstream failure forces downstream nodes to SKIPPED_DEPENDENCY_FAILED.
   - No downstream execution occurs.
2. Partial Branch Success:
   - Independent branches succeed while failing branch fails/skips.
   - GraphResult status is PARTIAL.
   - Talk-back identifies partial success and specific failing branch.
3. Parallelism Verification:
   - Independent parallel branches execute concurrently.
   - Total runtime is significantly less than sequential sum.
"""

import asyncio
import time
from typing import Any
import pytest
from pydantic import Field

from jarvis.core.planner.schema import (
    FailurePolicy,
    GraphResult,
    GraphStatus,
    NodeResult,
    NodeState,
    TaskGraph,
    TaskNode,
)
from jarvis.core.scheduler.scheduler import DAGScheduler
from jarvis.core.scheduler.models import SchedulerConfig
from jarvis.tools.base import Contract, RiskLevel, Tool, ToolDefinition
from jarvis.tools.registry import ToolRegistry


class MockInput(Contract):
    param: str = ""
    fail: bool = False
    delay_s: float = 0.0
    query: str = ""
    path: str = ""


class MockOutput(Contract):
    result_text: str = ""
    result_code: int = 0
    status: str = "ok"


class MockGenTool(Tool):
    def __init__(self, name: str, risk: RiskLevel = RiskLevel.READ_ONLY, timeout_s: float = 5.0):
        self.definition = ToolDefinition(
            name=name,
            description=f"Mock generalization tool {name}",
            input_model=MockInput,
            output_model=MockOutput,
            read_only=(risk == RiskLevel.READ_ONLY),
            risk=risk,
            timeout_s=timeout_s,
        )
        self.execution_count = 0
        self.execution_times: list[tuple[float, float]] = []

    def run(self, input_data: MockInput) -> MockOutput:
        self.execution_count += 1
        t_start = time.perf_counter()
        if input_data.delay_s > 0:
            time.sleep(input_data.delay_s)
        t_end = time.perf_counter()
        self.execution_times.append((t_start, t_end))
        if input_data.fail:
            raise RuntimeError(f"{self.definition.name} explicitly failed")
        return MockOutput(
            result_text=f"{self.definition.name}_{input_data.param or input_data.query or input_data.path}",
            result_code=100,
        )


@pytest.mark.asyncio
async def test_prerequisite_dependency_failure():
    """Verify that when an upstream node fails, its dependents are skipped and not executed."""
    registry = ToolRegistry()
    
    # n1 fails
    t_find = MockGenTool("find_file")
    t_open = MockGenTool("open_file")
    t_sum = MockGenTool("document_qa")
    
    registry.register(t_find)
    registry.register(t_open)
    registry.register(t_sum)
    
    graph = TaskGraph(
        goal="Find PDF, open it, and summarize it",
        nodes=[
            TaskNode(id="n1", tool="find_file", args={"query": "missing.pdf", "fail": True}, on_failure=FailurePolicy.FAIL_DEPENDENTS),
            TaskNode(id="n2", tool="open_file", args={"path": "dummy"}, depends_on=["n1"], on_failure=FailurePolicy.FAIL_DEPENDENTS),
            TaskNode(id="n3", tool="document_qa", args={"query": "summarize"}, depends_on=["n2"], on_failure=FailurePolicy.FAIL_DEPENDENTS),
        ],
    )
    
    scheduler = DAGScheduler(registry=registry)
    result: GraphResult = await scheduler.execute(graph)
    
    # n1 must be FAILED
    assert result.node_results["n1"].state == NodeState.FAILED
    assert t_find.execution_count == 1
    
    # Downstream n2 and n3 must be SKIPPED_DEPENDENCY_FAILED and NEVER executed
    assert result.node_results["n2"].state == NodeState.SKIPPED_DEPENDENCY_FAILED
    assert t_open.execution_count == 0, "Downstream node executed despite failed prerequisite!"
    
    assert result.node_results["n3"].state == NodeState.SKIPPED_DEPENDENCY_FAILED
    assert t_sum.execution_count == 0, "Downstream node executed despite transitive dependency failure!"
    
    assert result.status == GraphStatus.FAILED
    assert "Dependency resolution blocked" in result.node_results["n2"].error or "failed" in (result.node_results["n1"].error or "").lower()


@pytest.mark.asyncio
async def test_partial_branch_failure():
    """Verify independent branches succeed while dependent failing branch skips, yielding PARTIAL."""
    registry = ToolRegistry()
    
    t_calc = MockGenTool("open_calc")
    t_note = MockGenTool("open_notepad")
    t_find = MockGenTool("find_pdf")
    t_open = MockGenTool("open_pdf")
    
    registry.register(t_calc)
    registry.register(t_note)
    registry.register(t_find)
    registry.register(t_open)
    
    graph = TaskGraph(
        goal="Open Calculator, open Notepad, find PDF and open it",
        nodes=[
            TaskNode(id="n1", tool="open_calc", args={}),
            TaskNode(id="n2", tool="open_notepad", args={}),
            TaskNode(id="n3", tool="find_pdf", args={"fail": True}, on_failure=FailurePolicy.FAIL_DEPENDENTS),
            TaskNode(id="n4", tool="open_pdf", args={}, depends_on=["n3"]),
        ],
    )
    
    scheduler = DAGScheduler(registry=registry)
    result: GraphResult = await scheduler.execute(graph)
    
    # Independent branches succeed
    assert result.node_results["n1"].state == NodeState.SUCCESS
    assert result.node_results["n2"].state == NodeState.SUCCESS
    assert t_calc.execution_count == 1
    assert t_note.execution_count == 1
    
    # Dependent failing branch
    assert result.node_results["n3"].state == NodeState.FAILED
    assert result.node_results["n4"].state == NodeState.SKIPPED_DEPENDENCY_FAILED
    assert t_open.execution_count == 0
    
    # Overall graph is PARTIAL
    assert result.status == GraphStatus.PARTIAL
    assert set(result.successful_nodes) == {"n1", "n2"}
    assert "n3" in result.failed_nodes
    assert "n4" in result.skipped_nodes
    assert "Completed 2 of 4 steps" in result.user_message_data


@pytest.mark.asyncio
async def test_parallelism_execution():
    """Verify independent branches execute concurrently with actual runtime << sequential runtime."""
    registry = ToolRegistry()
    
    delay = 0.15  # 150 ms delay per tool
    t1 = MockGenTool("tool_a")
    t2 = MockGenTool("tool_b")
    t3 = MockGenTool("tool_c")
    
    registry.register(t1)
    registry.register(t2)
    registry.register(t3)
    
    graph = TaskGraph(
        goal="Execute three independent operations in parallel",
        nodes=[
            TaskNode(id="n1", tool="tool_a", args={"delay_s": delay}),
            TaskNode(id="n2", tool="tool_b", args={"delay_s": delay}),
            TaskNode(id="n3", tool="tool_c", args={"delay_s": delay}),
        ],
    )
    
    scheduler = DAGScheduler(registry=registry, config=SchedulerConfig(max_concurrency=4))
    
    t_start = time.perf_counter()
    result: GraphResult = await scheduler.execute(graph)
    elapsed = time.perf_counter() - t_start
    
    # Sequential runtime would be 3 * 0.15 = 0.45s
    # Concurrent runtime should be ~0.15s - 0.28s
    assert result.status == GraphStatus.SUCCESS
    assert len(result.successful_nodes) == 3
    assert elapsed < 0.35, f"Execution was sequential! Elapsed: {elapsed:.3f}s, expected < 0.35s"
    assert result.parallelism_factor > 1.2, f"Parallelism factor was {result.parallelism_factor}, expected > 1.2"
