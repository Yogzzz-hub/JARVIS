#!/usr/bin/env python3
"""
JARVIS EDGE - Phase 12 End-to-End Intelligence Benchmark
Measures high-precision latency percentiles across:
  - working_memory_lookup
  - context_assembly (simple command & complex contextual)
  - memory_structured_lookup
  - memory_fts
  - reference_resolution
  - workflow_match
  - workflow_bind
  - adaptive_route
  - prefetch_overhead
  - specialist_fanout
  - result_merge
  - resource_governor_decision
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from jarvis.core.memory import (
    BoundedWorkingMemory,
    SQLiteMemoryStore,
    MemoryItem,
    MemoryLayer,
    MemoryProvenance,
    MemorySourceType,
)
from jarvis.core.context import ContextAssembler, ReferenceResolver, ProjectContext
from jarvis.core.workflows import (
    WorkflowLibrary,
    WorkflowCandidate,
    WorkflowGraphTemplate,
    WorkflowNodeTemplate,
    WorkflowSlot,
)
from jarvis.core.router.adaptive import AdaptiveRoutingPolicy
from jarvis.core.resources import ResourceGovernor, ModelProfile, ModelRole
from jarvis.core.prefetch import PrefetchEngine
from jarvis.core.specialists import (
    SpecialistCoordinator,
    SpecialistResult,
    SpecialistType,
    SourceTrust,
    SpecialistFact,
)


def percentile(data: List[float], p: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * p)
    idx = min(idx, len(sorted_data) - 1)
    return sorted_data[idx]


def run_benchmark_sync(name: str, fn: Callable[[], Any], iterations: int = 200, warmup: int = 20) -> Dict[str, float]:
    for _ in range(warmup):
        fn()
    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)  # ms

    return {
        "operation": name,
        "iterations": iterations,
        "p50_ms": round(percentile(latencies, 0.50), 4),
        "p95_ms": round(percentile(latencies, 0.95), 4),
        "p99_ms": round(percentile(latencies, 0.99), 4),
        "mean_ms": round(sum(latencies) / len(latencies), 4),
        "max_ms": round(max(latencies), 4),
    }


def main():
    print("=" * 75)
    print("JARVIS EDGE — Phase 12 Intelligence Latency & Scale Benchmark")
    print("=" * 75)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "bench_memory.db"
        wf_path = Path(tmpdir) / "bench_wf.db"

        store = SQLiteMemoryStore(str(db_path))
        wm = BoundedWorkingMemory(max_items=50)
        resolver = ReferenceResolver(wm, store)
        assembler = ContextAssembler(wm, store, resolver)
        wf_lib = WorkflowLibrary(str(wf_path))
        governor = ResourceGovernor()
        governor.register_model(ModelProfile("qwen3_planner", [ModelRole.PLANNER], 350.0, 1200.0, 1.2, 0.25, {}))
        governor.register_model(ModelProfile("qwen3_vision", [ModelRole.VISION], 400.0, 1800.0, 1.5, 0.45, {}))
        prefetch = PrefetchEngine()
        router = AdaptiveRoutingPolicy(wf_lib)
        coordinator = SpecialistCoordinator()

        # Seed working memory
        wm.record_file_opened("C:\\Projects\\RITGate\\main.py")
        wm.record_folder_selected("C:\\Projects\\RITGate")
        wm.record_search_results([
            {"path": "C:\\Docs\\NLP_Notes_v1.pdf", "name": "NLP_Notes_v1.pdf"},
            {"path": "C:\\Docs\\NLP_Notes_v2.pdf", "name": "NLP_Notes_v2.pdf"},
            {"path": "C:\\Docs\\NLP_Notes_v3.pdf", "name": "NLP_Notes_v3.pdf"},
        ])
        wm.set_current_project("RIT Gate")

        # Seed 1,000 memory items to test scale
        print("Populating 1,000 memory items for scale evaluation...")
        for i in range(1000):
            store.store(MemoryItem(
                memory_id=f"mem_{i}",
                layer=MemoryLayer.SEMANTIC if i % 2 == 0 else MemoryLayer.PREFERENCE,
                kind="file_alias" if i % 3 == 0 else "preference",
                key=f"key_{i}",
                value=f"value_for_item_{i} referencing study notes and project files",
                provenance=MemoryProvenance(source_type=MemorySourceType.USER_EXPLICIT),
            ))

        # Seed approved workflow
        cand = WorkflowCandidate(
            candidate_id="cand_nlp_prep",
            name_suggestion="Prepare NLP Notes",
            normalized_goal="prepare nlp notes",
            graph_shape_hash="shape_abc123",
            graph_template=WorkflowGraphTemplate(nodes=[
                WorkflowNodeTemplate("node_0", "find_file", {"query": "NLP Notes.pdf"}, risk="READ_ONLY"),
                WorkflowNodeTemplate("node_1", "create_dir", {"path": "{{dst_dir}}"}, risk="EXTERNAL_EFFECT", depends_on=["node_0"]),
                WorkflowNodeTemplate("node_2", "copy_file", {"src": "{{src_file}}", "dst": "{{dst_dir}}"}, risk="EXTERNAL_EFFECT", depends_on=["node_1"]),
            ]),
            variable_slots=[
                WorkflowSlot("dst_dir", "Path", "Destination folder"),
                WorkflowSlot("src_file", "Path", "Source file"),
            ],
            risk_summary="EXTERNAL_EFFECT",
            occurrence_count=3,
        )
        approved_wf = wf_lib.approve_candidate(cand, custom_name="Prepare NLP Notes")

        # Define benchmark routines
        benchmarks = [
            ("working_memory_lookup", lambda: wm.get_last_opened_file()),
            ("context_assembly_fastpath", lambda: assembler.assemble("open calculator")),
            ("context_assembly_contextual", lambda: assembler.assemble("open the second one")),
            ("memory_structured_lookup", lambda: store.get_exact("key_500")),
            ("memory_fts", lambda: store.search_fts("referencing study notes", limit=5)),
            ("reference_resolution_ordinal", lambda: resolver.resolve("open the second one")),
            ("reference_resolution_pronoun", lambda: resolver.resolve("open it again")),
            ("workflow_match", lambda: wf_lib.find_matching_workflow("prepare nlp notes")),
            ("workflow_bind", lambda: wf_lib.bind_parameters(approved_wf, {"dst_dir": "C:\\Exams", "src_file": "C:\\Docs\\NLP.pdf"})),
            ("adaptive_route_workflow_fastpath", lambda: router.check_workflow_fast_path("prepare nlp notes")),
            ("prefetch_policy_overhead", lambda: prefetch.can_speculate("find_files")),
            ("resource_governor_decision", lambda: governor.evaluate_pressure_and_evict(60.0, 1000.0)),
        ]

        async def bench_specialists():
            mock_res1 = SpecialistResult(SpecialistType.FILE, "SUCCESS", facts=[SpecialistFact("f1", SpecialistType.FILE, "found")])
            mock_res2 = SpecialistResult(SpecialistType.GOOGLE, "SUCCESS", facts=[SpecialistFact("f2", SpecialistType.GOOGLE, "received")])
            async def _run_f():
                return mock_res1
            async def _run_g():
                return mock_res2
            res = await coordinator.execute_parallel([
                (SpecialistType.FILE, _run_f),
                (SpecialistType.GOOGLE, _run_g),
            ])
            return res

        results = []
        for name, fn in benchmarks:
            res = run_benchmark_sync(name, fn, iterations=300, warmup=30)
            results.append(res)

        # Measure async specialist fanout within an event loop
        async def run_specialists_bench(n: int = 100) -> List[float]:
            # Warmup
            for _ in range(10):
                await bench_specialists()
            lats = []
            for _ in range(n):
                t0 = time.perf_counter()
                await bench_specialists()
                t1 = time.perf_counter()
                lats.append((t1 - t0) * 1000.0)
            return lats

        specialist_latencies = asyncio.run(run_specialists_bench(100))

        results.append({
            "operation": "specialist_fanout_and_merge",
            "iterations": 100,
            "p50_ms": round(percentile(specialist_latencies, 0.50), 4),
            "p95_ms": round(percentile(specialist_latencies, 0.95), 4),
            "p99_ms": round(percentile(specialist_latencies, 0.99), 4),
            "mean_ms": round(sum(specialist_latencies) / len(specialist_latencies), 4),
            "max_ms": round(max(specialist_latencies), 4),
        })

        # Print clean results table
        print("\n" + f"{'Operation':<32} | {'p50 (ms)':<9} | {'p95 (ms)':<9} | {'p99 (ms)':<9} | {'Mean (ms)':<9} | {'Target':<12} | {'Status'}")
        print("-" * 105)

        targets = {
            "working_memory_lookup": 1.0,
            "context_assembly_fastpath": 1.0,
            "context_assembly_contextual": 2.0,
            "memory_structured_lookup": 3.0,
            "memory_fts": 10.0,
            "reference_resolution_ordinal": 2.0,
            "reference_resolution_pronoun": 2.0,
            "workflow_match": 2.0,
            "workflow_bind": 3.0,
            "adaptive_route_workflow_fastpath": 2.0,
            "prefetch_policy_overhead": 1.0,
            "resource_governor_decision": 1.0,
            "specialist_fanout_and_merge": 15.0,
        }

        for r in results:
            op = r["operation"]
            p95 = r["p95_ms"]
            tgt = targets.get(op, 5.0)
            status = "PASS" if p95 <= tgt else "REGRESSION"
            print(f"{op:<32} | {r['p50_ms']:<9.4f} | {r['p95_ms']:<9.4f} | {r['p99_ms']:<9.4f} | {r['mean_ms']:<9.4f} | < {tgt:<10.1f} | {status}")

        # Save metrics
        out_file = REPO_ROOT / "docs" / "intelligence-benchmark.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump({
                "phase": 12,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "scale_memory_items": 1000,
                "benchmarks": results,
            }, f, indent=2)
        print(f"\n[OK] Benchmark metrics saved to {out_file}")


if __name__ == "__main__":
    main()
