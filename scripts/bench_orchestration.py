"""Benchmark script for JARVIS EDGE Orchestration & Morning Briefing.

Measures:
- Morning workflow parallel gathering latency
- Morning workflow merge & speech generation latency
- Working memory contextual reference resolution latency
- Lane 0 deterministic connector routing latency
"""

from __future__ import annotations

import asyncio
import statistics
import time
from typing import Callable, List, Tuple

from jarvis.workflows.morning_briefing import run_morning_briefing, fetch_system_stats, fetch_recent_downloads
from jarvis.memory.working_memory import WorkingMemory
from jarvis.core.router.router import SmartRouter
from jarvis.core.router.catalog import IntentCatalog
from jarvis.config import ROOT


def run_bench(name: str, domain: str, func: Callable[[], any], iterations: int = 10) -> Tuple[float, float, float]:
    times = []
    # Warm-up
    try:
        func()
    except Exception:
        pass

    for _ in range(iterations):
        t0 = time.perf_counter()
        try:
            func()
        except Exception:
            pass
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000.0)

    times.sort()
    p50 = statistics.median(times)
    p95_idx = int(0.95 * len(times))
    p95 = times[min(p95_idx, len(times) - 1)]
    max_val = max(times)
    return p50, p95, max_val


def main():
    print("=" * 70)
    print("        JARVIS EDGE ORCHESTRATION PERFORMANCE BENCHMARK")
    print("=" * 70)
    print(f"{'OPERATION':<32} | {'DOMAIN':<16} | {'p50 (ms)':<9} | {'p95 (ms)':<9} | {'max (ms)':<9}")
    print("-" * 70)

    wm = WorkingMemory()
    wm.set_feed_items([
        {"id": "1", "title": "First Headline", "url": "https://example.com/1"},
        {"id": "2", "title": "Second Headline", "url": "https://example.com/2"},
        {"id": "3", "title": "Third Headline", "url": "https://example.com/3"},
    ])

    intents_path = ROOT / "core/router/intents.yaml"
    catalog = IntentCatalog(intents_path)
    router = SmartRouter(catalog=catalog)

    benchmarks = [
        ("Morning Workflow Parallel Gather", "INTERNAL/PARALLEL", lambda: asyncio.run(run_morning_briefing(working_memory=wm))),
        ("PC Health Metric Sampling", "INTERNAL", lambda: asyncio.run(fetch_system_stats())),
        ("Recent Downloads Scan", "INTERNAL", lambda: asyncio.run(fetch_recent_downloads())),
        ("Contextual Follow-up Resolution", "INTERNAL", lambda: wm.resolve_reference("open the second one")),
        ("Lane 0 Routing ('show phone')", "INTERNAL", lambda: router.route("show my phone")),
        ("Lane 0 Routing ('good morning')", "INTERNAL", lambda: router.route("good morning jarvis")),
        ("Lane 0 Routing ('send to phone')", "INTERNAL", lambda: router.route("send this file to my phone")),
    ]

    for name, domain, fn in benchmarks:
        p50, p95, max_val = run_bench(name, domain, fn, iterations=5)
        print(f"{name:<32} | {domain:<16} | {p50:>9.2f} | {p95:>9.2f} | {max_val:>9.2f}")

    print("=" * 70)
    print("Orchestration benchmark complete.")


if __name__ == "__main__":
    main()
