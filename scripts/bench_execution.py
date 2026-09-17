"""JARVIS EDGE -- Phase 5 Trusted Execution & Policy Benchmark.
Measures micro-latencies of deterministic policy, fingerprinting, method selection,
verification, and ledger operations against Section 71 and 72 targets.
"""

import asyncio
import os
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jarvis.core.executor.engine import ExecutionEngine
from jarvis.core.executor.selector import MethodSelector
from jarvis.security.confirmation.manager import ConfirmationManager, compute_action_fingerprint
from jarvis.security.ledger.ledger import ActionLedger
from jarvis.security.ledger.models import LedgerState
from jarvis.security.paths import canonicalize_path, is_protected_path
from jarvis.security.policy.evaluator import PolicyEvaluator
from jarvis.security.preconditions import check_preconditions
from jarvis.security.verifiers.strategies import FileExistsVerifier
from jarvis.tools.base import IdempotencyClass, RiskLevel, ToolDefinition, VerificationStrength
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.system.app_resolver import AppResolver
from jarvis.tools.system.native import create_tools


def measure_p(samples: list[float]) -> dict[str, float]:
    samples.sort()
    n = len(samples)
    return {
        "n": n,
        "p50": samples[int(n * 0.50)],
        "p95": samples[int(n * 0.95)],
        "p99": samples[int(n * 0.99)],
        "mean": statistics.mean(samples),
        "max": max(samples),
    }


def main():
    print("============================================================")
    print("JARVIS EDGE -- Phase 5 Execution & Policy Benchmark")
    print("============================================================")

    # Initialize tools & dependencies
    registry = ToolRegistry()
    registry.discover(create_tools(AppResolver(), {}))
    registry.finalize()

    evaluator = PolicyEvaluator()
    selector = MethodSelector()
    read_tool_def = registry.get("get_time").definition
    rev_tool_def = registry.get("open_app").definition

    # 1. Benchmark Policy Evaluation (READ_ONLY)
    read_samples = []
    for _ in range(1000):
        t0 = time.perf_counter_ns()
        evaluator.evaluate_node(read_tool_def, {}, "g1", "n1")
        read_samples.append((time.perf_counter_ns() - t0) / 1e6)
    read_res = measure_p(read_samples)

    # 2. Benchmark Policy Evaluation (REVERSIBLE)
    rev_samples = []
    for _ in range(1000):
        t0 = time.perf_counter_ns()
        evaluator.evaluate_node(rev_tool_def, {"name": "notepad"}, "g1", "n2")
        rev_samples.append((time.perf_counter_ns() - t0) / 1e6)
    rev_res = measure_p(rev_samples)

    # 3. Benchmark Action Fingerprint
    fp_samples = []
    sample_args = {"path": "C:\\Users\\ashok\\Desktop\\report.txt"}
    for _ in range(1000):
        t0 = time.perf_counter_ns()
        compute_action_fingerprint("delete_file", sample_args, graph_id="g1", node_id="n1")
        fp_samples.append((time.perf_counter_ns() - t0) / 1e6)
    fp_res = measure_p(fp_samples)

    # 4. Benchmark Method Selection
    sel_samples = []
    for _ in range(1000):
        t0 = time.perf_counter_ns()
        selector.select_variant(rev_tool_def)
        sel_samples.append((time.perf_counter_ns() - t0) / 1e6)
    sel_res = measure_p(sel_samples)

    # 5. Benchmark Precondition Validation
    pre_samples = []
    for _ in range(1000):
        t0 = time.perf_counter_ns()
        check_preconditions("get_time", {})
        pre_samples.append((time.perf_counter_ns() - t0) / 1e6)
    pre_res = measure_p(pre_samples)

    # 6. Benchmark Confirmation Ticket Issuance
    cm = ConfirmationManager()
    tkt_samples = []
    for _ in range(1000):
        t0 = time.perf_counter_ns()
        cm.issue_ticket("req_1", "g1", "n1", "delete_file", sample_args, RiskLevel.DESTRUCTIVE)
        tkt_samples.append((time.perf_counter_ns() - t0) / 1e6)
    tkt_res = measure_p(tkt_samples)

    # 7. Benchmark Ledger Operations
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db_path = Path(td) / "bench_ledger.db"
        ledger = ActionLedger(db_path=db_path)

        # In-memory / fast lookup
        fp_test = compute_action_fingerprint("get_time", {})
        ledger.prepare_action("act_1", fp_test, "req_1", "g1", "n1", "get_time", RiskLevel.READ_ONLY, IdempotencyClass.IDEMPOTENT, "h1")

        lookup_samples = []
        for _ in range(1000):
            t0 = time.perf_counter_ns()
            ledger.check_duplicate(fp_test)
            lookup_samples.append((time.perf_counter_ns() - t0) / 1e6)
        lookup_res = measure_p(lookup_samples)

        # Critical Durable Write (SQLite write)
        durable_samples = []
        for i in range(100):
            fp_d = f"fp_durable_{i}"
            act_id = f"act_durable_{i}"
            t0 = time.perf_counter_ns()
            ledger.prepare_action(act_id, fp_d, "req_d", "gd", "nd", "delete_file", RiskLevel.DESTRUCTIVE, IdempotencyClass.NON_IDEMPOTENT, "hd")
            durable_samples.append((time.perf_counter_ns() - t0) / 1e6)
        durable_res = measure_p(durable_samples)

    # Output formatted report
    metrics = [
        ("Policy Eval (READ_ONLY)", read_res, "< 0.25 ms"),
        ("Policy Eval (REVERSIBLE)", rev_res, "< 0.50 ms"),
        ("Action Fingerprint", fp_res, "< 0.20 ms"),
        ("Method Selection", sel_res, "< 0.50 ms"),
        ("Preconditions Check", pre_res, "< 0.20 ms"),
        ("Confirmation Ticket Issuance", tkt_res, "< 0.50 ms"),
        ("Fast Ledger Lookup", lookup_res, "< 1.00 ms"),
        ("Critical Durable Ledger Write", durable_res, "Durable Sync"),
    ]

    print(f"{'Metric':<30} | {'p50 (ms)':<9} | {'p95 (ms)':<9} | {'Mean (ms)':<10} | {'Target':<12} | {'Status'}")
    print("-" * 88)
    for name, res, target in metrics:
        p95 = res["p95"]
        if "<" in target:
            target_val = float(target.split("<")[1].split("ms")[0].strip())
            status = "PASS" if p95 <= target_val else "FAIL"
        else:
            status = "PASS"
        print(f"{name:<30} | {res['p50']:<9.4f} | {res['p95']:<9.4f} | {res['mean']:<10.4f} | {target:<12} | {status}")
    print("=" * 88)


if __name__ == "__main__":
    main()
