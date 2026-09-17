"""Execution and verification script for Phase 4 Required Demonstrations 1 through 9.

Demonstration 1: Multi-step pipeline (find || create -> copy -> open) with real verification
Demonstration 2: Concurrent searches (find NLP and OS notes) run in parallel
Demonstration 3: Ambiguous file search protection (clarification required, 0 move)
Demonstration 4: Capability gap detection (WhatsApp -> CAPABILITY_GAP, 0 hallucination)
Demonstration 5: Tool injection rejection (delete_everything -> UNKNOWN_TOOL, 0 execution)
Demonstration 6: Synthetic parallel speedup (2x 300ms in ~350ms vs 600ms sequential with timestamp overlap)
Demonstration 7: Plan cache fast path (repeated request yields plan_cache_hit=True, 0 LLM)
Demonstration 8: Resilience when Ollama is stopped (truthfully reports planner unavailable, no crash)
Demonstration 9: Bypass verification (simple commands 'open chrome' and 'find NLP pdf' bypass planner)
"""

import asyncio
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jarvis.core.commands.resolver import resolve
from jarvis.core.planner.adaptive_planner import AdaptivePlanner
from jarvis.core.planner.cache import PlanTemplateCache
from jarvis.core.planner.schema import (
    GraphStatus,
    NodeResult,
    NodeState,
    TaskGraph,
    TaskNode,
    ValueBinding,
)
from jarvis.core.planner.validator import GraphValidator
from jarvis.core.router.models import RouteLane
from jarvis.core.router.router import SmartRouter
from jarvis.core.scheduler.models import SchedulerConfig
from jarvis.core.scheduler.scheduler import DAGScheduler
from jarvis.memory.search.engine import SearchEngine
from jarvis.tools.base import Contract, RiskLevel, Tool, ToolDefinition
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.system.app_resolver import AppResolver
from jarvis.tools.system.file_tools import CopyFileTool, CreateFolderTool, FindFileTool, OpenFileTool
from jarvis.tools.system.native import create_tools


class Demo300msInput(Contract):
    name: str = ""
    delay_s: float = 0.3


class Demo300msOutput(Contract):
    name: str
    elapsed_s: float


class Demo300msTool(Tool):
    def __init__(self, tool_name: str):
        self.definition = ToolDefinition(
            name=tool_name,
            description="Simulated 300ms task",
            input_model=Demo300msInput,
            output_model=Demo300msOutput,
            read_only=True,
            risk=RiskLevel.READ_ONLY,
            timeout_s=2.0,
        )
        self.execution_times: list[tuple[float, float]] = []

    def run(self, input_data: Demo300msInput) -> Demo300msOutput:
        t0 = time.perf_counter()
        time.sleep(input_data.delay_s)
        t1 = time.perf_counter()
        self.execution_times.append((t0, t1))
        return Demo300msOutput(name=input_data.name, elapsed_s=(t1 - t0))


async def run_demo_1(registry):
    print("\n--- DEMONSTRATION 1: Multi-Step Pipeline (Find || Create -> Copy -> Open) ---")
    req = "Find my NLP notes, copy them into a new folder called NLP Study on Desktop and open the folder."
    planner = AdaptivePlanner(registry=registry)
    plan_res = await planner.plan(req)

    assert plan_res.graph is not None, "Demo 1 failed: could not generate graph"
    assert len(plan_res.graph.nodes) == 4, f"Expected 4 nodes, got {len(plan_res.graph.nodes)}"

    # Setup isolated test directory simulating Desktop
    temp_dir = tempfile.mkdtemp(prefix="jarvis_demo1_")
    try:
        sample_file = Path(temp_dir) / "NLP_Unit_4_Notes.pdf"
        sample_file.write_text("Lecture Notes on Natural Language Processing")

        # Mock find_file to return our sample_file
        dest_folder = Path(temp_dir) / "NLP Study"

        class MockFindTool(Tool):
            definition = registry.get("find_file").definition
            def run(self, inp):
                return {
                    "query": inp.query,
                    "results": [{"file_id": 1, "path": str(sample_file), "name": sample_file.name}],
                    "is_ambiguous": False,
                }

        demo_reg = ToolRegistry()
        for t in registry.list():
            if t.definition.name == "find_file":
                demo_reg.register(MockFindTool())
            else:
                demo_reg.register(t)
        demo_reg.finalize()

        # Update target folder in n2 args to temp directory
        adapted_nodes = []
        for n in plan_res.graph.nodes:
            if n.id == "n2":
                adapted_nodes.append(n.model_copy(update={"args": {"path": str(dest_folder)}}))
            else:
                adapted_nodes.append(n)
        adapted_graph = plan_res.graph.model_copy(update={"nodes": adapted_nodes})

        scheduler = DAGScheduler(demo_reg)
        graph_res = await scheduler.execute(adapted_graph)

        print(f"Graph Status: {graph_res.status}")
        print(f"Successful nodes: {graph_res.successful_nodes}")
        print(f"Parallelism factor: {graph_res.parallelism_factor:.2f}x")

        # Verify actual file copied into folder
        copied_target = dest_folder / sample_file.name
        assert copied_target.exists(), "Verification failed: file was not copied to target folder"
        assert copied_target.read_text() == "Lecture Notes on Natural Language Processing"
        print(f"Verified copied file: {copied_target} ({copied_target.stat().st_size} bytes)")
        print("DEMO 1: PASS")
        return True
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def run_demo_2(registry):
    print("\n--- DEMONSTRATION 2: Concurrent Searches (find NLP and OS notes) ---")
    req = "Find my NLP notes and OS notes"
    planner = AdaptivePlanner(registry=registry)
    plan_res = await planner.plan(req)

    assert plan_res.graph is not None
    assert len(plan_res.graph.nodes) == 2
    n1, n2 = plan_res.graph.nodes[0], plan_res.graph.nodes[1]
    assert n1.tool == "find_file" and n2.tool == "find_file"
    assert n1.depends_on == [] and n2.depends_on == []
    print(f"Plan Nodes: [{n1.id}: {n1.tool}(query='{n1.args.get('query')}')] (root)")
    print(f"            [{n2.id}: {n2.tool}(query='{n2.args.get('query')}')] (root)")
    print("Both searches are independent roots scheduled in parallel (no forced serialization).")
    print("DEMO 2: PASS")
    return True


async def run_demo_3(registry):
    print("\n--- DEMONSTRATION 3: Ambiguous File Protection (clarification, NO MOVE) ---")
    # Simulate ambiguous search returning 2 equally plausible files
    class AmbiguousFindTool(Tool):
        definition = registry.get("find_file").definition
        def run(self, inp):
            return {
                "query": inp.query,
                "results": [
                    {"file_id": 101, "path": "C:\\Docs\\NLP_Unit_4.pdf", "name": "NLP Unit 4.pdf"},
                    {"file_id": 102, "path": "C:\\Docs\\NLP_Unit_5.pdf", "name": "NLP Unit 5.pdf"},
                ],
                "is_ambiguous": True,
                "clarification": "I found two matching NLP files: 'NLP Unit 4.pdf' and 'NLP Unit 5.pdf'. Which one do you mean?",
            }

    amb_reg = ToolRegistry()
    for t in registry.list():
        if t.definition.name == "find_file":
            amb_reg.register(AmbiguousFindTool())
        else:
            amb_reg.register(t)
    amb_reg.finalize()

    # Graph: find_file -> move_file
    graph = TaskGraph(
        goal="Move my NLP notes to Exam folder",
        nodes=[
            TaskNode(id="n1", tool="find_file", args={"query": "NLP notes"}),
            TaskNode(
                id="n2",
                tool="move_file",
                depends_on=["n1"],
                bindings={"source": ValueBinding(node_id="n1", output_path="results[0].path")},
                args={"destination": "C:\\Exam"},
            ),
        ],
    )

    scheduler = DAGScheduler(amb_reg)
    res = await scheduler.execute(graph)

    print(f"Graph Status: {res.status}")
    print(f"User Message: {res.user_message_data}")
    print(f"n2 state:     {res.node_results['n2'].state}")

    assert res.status == GraphStatus.NEEDS_CLARIFICATION, f"Expected NEEDS_CLARIFICATION, got {res.status}"
    assert res.node_results["n2"].state == NodeState.BLOCKED_AMBIGUOUS_INPUT
    assert "Which one do you mean?" in res.user_message_data
    print("Downstream move operation was blocked. Zero accidental state changes.")
    print("DEMO 3: PASS")
    return True


async def run_demo_4(registry):
    print("\n--- DEMONSTRATION 4: Capability Gap (WhatsApp -> CAPABILITY_GAP, 0 hallucination) ---")
    req = "Send this PDF to Santosh on WhatsApp."
    planner = AdaptivePlanner(registry=registry)
    plan_res = await planner.plan(req)

    print(f"Plan Confidence:       {plan_res.confidence}")
    print(f"Missing Capabilities:  {plan_res.graph.missing_capabilities if plan_res.graph else []}")

    scheduler = DAGScheduler(registry)
    res = await scheduler.execute(plan_res.graph)

    print(f"Graph Status:          {res.status}")
    print(f"Message:               {res.user_message_data}")

    assert res.status == GraphStatus.CAPABILITY_GAP
    assert "whatsapp" in res.user_message_data.lower()
    # Confirm no hallucinated whatsapp tool exists in graph
    for node in plan_res.graph.nodes:
        assert node.tool != "whatsapp_send"
    print("DEMO 4: PASS")
    return True


async def run_demo_5(registry):
    print("\n--- DEMONSTRATION 5: Tool Injection Rejection (delete_everything -> UNKNOWN_TOOL) ---")
    malicious_graph = TaskGraph(
        goal="Delete everything",
        nodes=[
            TaskNode(id="n1", tool="delete_everything", args={}),
        ],
    )
    validator = GraphValidator(registry)
    val_res = validator.validate(malicious_graph)

    print(f"Validation Is Valid: {val_res.is_valid}")
    error_codes = [e.code for e in val_res.errors]
    print(f"Validation Errors:   {error_codes}")

    assert not val_res.is_valid
    assert "UNKNOWN_TOOL" in error_codes
    print("Zero execution allowed on unverified or hallucinated tool names.")
    print("DEMO 5: PASS")
    return True


async def run_demo_6():
    print("\n--- DEMONSTRATION 6: Synthetic Parallel Execution & Timestamp Overlap ---")
    # Synthetic graph: A 300 ms, B 300 ms independent
    # Sequential estimated: ~600 ms, Parallel execution: ~300-400 ms
    t_a = Demo300msTool("task_a")
    t_b = Demo300msTool("task_b")
    synth_reg = ToolRegistry()
    synth_reg.discover([t_a, t_b])
    synth_reg.finalize()

    graph = TaskGraph(
        goal="Synthetic 2x 300ms parallel test",
        nodes=[
            TaskNode(id="n1", tool="task_a", args={"name": "branch_A", "delay_s": 0.3}),
            TaskNode(id="n2", tool="task_b", args={"name": "branch_B", "delay_s": 0.3}),
        ],
    )

    scheduler = DAGScheduler(synth_reg, config=SchedulerConfig(max_concurrency=4))
    t0 = time.perf_counter()
    res = await scheduler.execute(graph)
    total_elapsed = time.perf_counter() - t0

    start_a, end_a = t_a.execution_times[0]
    start_b, end_b = t_b.execution_times[0]
    overlap_s = max(0.0, min(end_a, end_b) - max(start_a, start_b))

    print(f"Branch A Execution Interval: [{start_a - t0:.3f}s - {end_a - t0:.3f}s]")
    print(f"Branch B Execution Interval: [{start_b - t0:.3f}s - {end_b - t0:.3f}s]")
    print(f"Timestamp Overlap:           {overlap_s:.3f} seconds")
    print(f"Total Graph Duration:        {total_elapsed:.3f} seconds (vs ~0.600s sequential)")
    print(f"Parallelism Factor:          {res.parallelism_factor:.2f}x")

    assert total_elapsed < 0.50, f"Expected < 0.50s, took {total_elapsed:.3f}s"
    assert overlap_s > 0.15, f"Expected > 0.15s overlap, got {overlap_s:.3f}s"
    assert res.status == GraphStatus.SUCCESS
    print("DEMO 6: PASS")
    return True


async def run_demo_7(registry):
    print("\n--- DEMONSTRATION 7: Plan Cache Fast Path (Repeated Request Skips LLM) ---")
    cache = PlanTemplateCache(capacity=512)
    planner = AdaptivePlanner(registry=registry, cache=cache)
    req = "find my NLP notes and open it"

    # Step 1: First planning populates cache
    plan_1 = await planner.plan(req)
    assert plan_1.graph is not None
    assert not plan_1.cache_hit

    # Step 2: Next identical execution hits plan cache
    plan_2 = await planner.plan(req)
    print(f"First Execution Cache Hit:  {plan_1.cache_hit} (source={plan_1.source})")
    print(f"Second Execution Cache Hit: {plan_2.cache_hit} (source={plan_2.source})")
    print(f"Second Planning Latency:    {plan_2.planning_ms:.3f} ms")

    t0 = time.perf_counter_ns()
    direct_lookup = cache.get(req, [], registry.get_fingerprint())
    lookup_ms = (time.perf_counter_ns() - t0) / 1e6
    print(f"Direct Plan-Cache Lookup Latency: {lookup_ms:.3f} ms (target < 1ms)")

    assert plan_2.cache_hit is True
    assert plan_2.source == "cache"
    assert lookup_ms < 1.0, f"Cache lookup target < 1ms, got {lookup_ms:.3f}ms"
    assert plan_2.planning_ms < 5.0, f"Expected < 5ms, got {plan_2.planning_ms}ms"
    print("DEMO 7: PASS")
    return True



async def run_demo_8(registry):
    print("\n--- DEMONSTRATION 8: Resilience When Ollama Is Stopped ---")
    # Verify simple commands still resolve
    simple_req = "volume 50"
    tool_name, args = resolve(simple_req)
    print(f"Simple command '{simple_req}' resolved offline: tool={tool_name}, args={args}")
    assert tool_name == "volume_set"


    # Complex uncached request with Ollama offline: truthfully reports unavailable, no crash
    offline_planner = AdaptivePlanner(registry=registry, ollama_url="http://127.0.0.1:9999")  # Invalid port
    complex_uncached = "analyze the quarterly financial revenue variance and if greater than 10 percent alert accounting"
    plan_res = await offline_planner.plan(complex_uncached)

    print(f"Complex Request Planning Result: graph={plan_res.graph}, source={plan_res.source}")
    print(f"Truthful Error Message:          {plan_res.error}")

    assert plan_res.graph is None
    assert plan_res.source == "unavailable"
    assert plan_res.error is not None
    print("Zero application crash when Ollama is offline.")
    print("DEMO 8: PASS")
    return True


async def run_demo_9(registry):
    print("\n--- DEMONSTRATION 9: Bypass Verification (Simple Commands Bypass Planner) ---")
    router = SmartRouter()

    # Case 1: "open chrome"
    decision1 = await router.route(resolve("open chrome", registry)) if hasattr(router, "_test") else await router.route_text("open chrome") if hasattr(router, "route_text") else None
    # Let's inspect router call
    from jarvis.core.commands.contracts import CommandRequest
    d1 = await router.route(CommandRequest(text="open chrome", source="cli"))
    print(f"Request: 'open chrome' -> lane={d1.lane}, needs_planner={d1.needs_planner}, intent={d1.intent}")
    assert d1.needs_planner is False
    assert d1.lane in (RouteLane.LANE_0, RouteLane.LANE_1)

    # Case 2: "find NLP pdf"
    d2 = await router.route(CommandRequest(text="find NLP pdf", source="cli"))
    print(f"Request: 'find NLP pdf' -> lane={d2.lane}, needs_planner={d2.needs_planner}, intent={d2.intent}")
    assert d2.needs_planner is False
    assert d2.lane in (RouteLane.LANE_0, RouteLane.LANE_1)

    # Case 3: "volume 30"
    d3 = await router.route(CommandRequest(text="volume 30", source="cli"))
    print(f"Request: 'volume 30' -> lane={d3.lane}, needs_planner={d3.needs_planner}, intent={d3.intent}")
    assert d3.needs_planner is False

    print("All simple single-turn requests bypass the planner completely.")
    print("DEMO 9: PASS")
    return True


async def main():
    print("============================================================")
    print("JARVIS EDGE — Phase 4 Demonstrations Suite (1-9)")
    print("============================================================")

    registry = ToolRegistry()
    registry.discover(create_tools(AppResolver(), {}))
    registry.finalize()

    results = []
    results.append(("Demo 1: Multi-step pipeline", await run_demo_1(registry)))
    results.append(("Demo 2: Concurrent searches", await run_demo_2(registry)))
    results.append(("Demo 3: Ambiguous file search", await run_demo_3(registry)))
    results.append(("Demo 4: Capability gap detection", await run_demo_4(registry)))
    results.append(("Demo 5: Tool injection rejection", await run_demo_5(registry)))
    results.append(("Demo 6: Synthetic parallel speedup", await run_demo_6()))
    results.append(("Demo 7: Plan cache fast path", await run_demo_7(registry)))
    results.append(("Demo 8: Resilience when Ollama stopped", await run_demo_8(registry)))
    results.append(("Demo 9: Bypass verification", await run_demo_9(registry)))

    print("\n============================================================")
    print("DEMONSTRATIONS SUMMARY")
    print("============================================================")
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"{name:45}: {status}")
    print("============================================================")
    if all_passed:
        print("ALL 9 PHASE 4 DEMONSTRATIONS PASSED SUCCESSFULLY!")
    else:
        print("SOME DEMONSTRATIONS FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
