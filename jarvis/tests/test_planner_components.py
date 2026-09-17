"""Tests for PlanTemplateCache, ToolRetriever, DeterministicDecomposer, and ComplexityAnalyzer (Phase 4)."""

import os
import tempfile
import time
import pytest

from jarvis.core.planner.cache import PlanTemplateCache
from jarvis.core.planner.complexity import ComplexityAnalyzer, PlannerComplexity
from jarvis.core.planner.decomposer import DeterministicDecomposer
from jarvis.core.planner.schema import TaskGraph, TaskNode, ValueBinding
from jarvis.core.planner.tool_retriever import ToolRetriever
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.system.app_resolver import AppResolver
from jarvis.tools.system.native import create_tools


@pytest.fixture
def registry():
    reg = ToolRegistry()
    reg.discover(create_tools(AppResolver(), {}))
    reg.finalize()
    return reg


def test_plan_cache_hit_and_miss(registry):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name

    try:
        # Initialize schema in temp db
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS plan_cache (
                template_id TEXT PRIMARY KEY,
                task_signature TEXT NOT NULL UNIQUE,
                tool_registry_fingerprint TEXT NOT NULL,
                graph_template_json TEXT NOT NULL,
                hit_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.commit()
        conn.close()

        cache = PlanTemplateCache(capacity=512, db_path=db_path)
        fp = registry.get_fingerprint()

        # Initial miss
        miss = cache.get("find my NLP PDF and copy it to Desktop", ["find_file", "copy_file"], fp)
        assert miss is None
        assert cache.misses == 1

        # Populate cache
        graph = TaskGraph(
            goal="find my NLP PDF and copy it to Desktop",
            nodes=[
                TaskNode(id="n1", tool="find_file", args={"query": "NLP"}),
                TaskNode(
                    id="n2",
                    tool="copy_file",
                    depends_on=["n1"],
                    bindings={"source": ValueBinding(node_id="n1", output_path="results[0].path")},
                    args={"destination": "Desktop"},
                ),
            ],
        )

        # Record 3 successful executions to trigger promotion
        for _ in range(3):
            cache.record_execution(
                "find my NLP PDF and copy it to Desktop",
                ["find_file", "copy_file"],
                graph,
                True,
                fp,
            )

        assert cache.promoted >= 1

        # Warmup and measure lookup latency
        cache.get("find my NLP PDF and copy it to Desktop", ["find_file", "copy_file"], fp)
        latencies = []
        for _ in range(5):
            t0 = time.perf_counter_ns()
            hit = cache.get("find my NLP PDF and copy it to Desktop", ["find_file", "copy_file"], fp)
            latencies.append((time.perf_counter_ns() - t0) / 1e6)
        lookup_ms = min(latencies)

        assert hit is not None
        assert cache.hits >= 1
        assert lookup_ms < 1.0, f"Cache lookup took {lookup_ms:.3f}ms (target < 1ms)"

        # Invalidation on fingerprint change
        stale_hit = cache.get("find my NLP PDF and copy it to Desktop", ["find_file", "copy_file"], "different_fp")
        assert stale_hit is None
        assert cache.invalidated >= 1
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_tool_retriever_recall(registry):
    retriever = ToolRetriever(registry, default_top_k=12)

    # Test 1: File copy request
    schemas1 = retriever.retrieve("find my NLP PDF and copy it to Desktop")
    names1 = [s.name for s in schemas1]
    assert "find_file" in names1
    assert "copy_file" in names1
    assert "create_folder" in names1

    # Test 2: Audio adjustment
    schemas2 = retriever.retrieve("turn up the sound volume and mute mic")
    names2 = [s.name for s in schemas2]
    assert "volume_set" in names2 or "volume_get" in names2 or "mute_toggle" in names2

    # Test 3: System spec check
    schemas3 = retriever.retrieve("check battery level and system specs")
    names3 = [s.name for s in schemas3]
    assert "battery_status" in names3 or "system_info" in names3


def test_deterministic_decomposer_patterns():
    decomposer = DeterministicDecomposer()

    # Pattern 1: Find and open
    g1 = decomposer.decompose("find my NLP notes and open it")
    assert g1 is not None
    assert len(g1.nodes) == 2
    assert g1.nodes[0].tool == "find_file"
    assert g1.nodes[1].tool == "open_file"
    assert g1.nodes[1].depends_on == ["n1"]

    # Pattern 2: Find and copy
    g2 = decomposer.decompose("find my OS notes and copy it to Desktop")
    assert g2 is not None
    assert len(g2.nodes) == 2
    assert g2.nodes[0].tool == "find_file"
    assert g2.nodes[1].tool == "copy_file"

    # Pattern 3: Dual search (parallel)
    g3 = decomposer.decompose("Find my NLP notes and OS notes")
    assert g3 is not None
    assert len(g3.nodes) == 2
    assert g3.nodes[0].tool == "find_file"
    assert g3.nodes[1].tool == "find_file"
    # Neither depends on the other (parallel!)
    assert g3.nodes[0].depends_on == []
    assert g3.nodes[1].depends_on == []

    # Pattern 4: Create folder, find, copy, open (Demo 1)
    g4 = decomposer.decompose(
        "Find my NLP notes, copy them into a new folder called NLP Study on Desktop and open the folder."
    )
    assert g4 is not None
    assert len(g4.nodes) == 4
    tools = [n.tool for n in g4.nodes]
    assert tools == ["find_file", "create_folder", "copy_file", "open_file"]
    # n1 and n2 are independent roots
    assert g4.nodes[0].depends_on == []
    assert g4.nodes[1].depends_on == []
    # n3 depends on both
    assert set(g4.nodes[2].depends_on) == {"n1", "n2"}


def test_complexity_analyzer():
    analyzer = ComplexityAnalyzer()

    # Simple / Low
    c1 = analyzer.analyze("find my report")
    assert c1 == PlannerComplexity.LOW

    # Medium
    c2 = analyzer.analyze("find NLP notes and copy them to Desktop")
    assert c2 in (PlannerComplexity.LOW, PlannerComplexity.MEDIUM)

    # High (conditionals, temporal phrases, multiple constraints)
    c3 = analyzer.analyze("if the file exists then find my NLP PDF, otherwise search downloads, then copy and open it")
    assert c3 == PlannerComplexity.HIGH
