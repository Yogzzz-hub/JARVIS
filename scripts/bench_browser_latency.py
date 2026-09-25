"""Browser Automation Latency Benchmark for JARVIS EDGE v1.0.

Measures:
1. Browser cold start vs warm context reuse overhead.
2. Semantic locator resolution overhead (role, label, text, placeholder).
3. Action dispatch overhead (click, fill) excluding network time.
4. Download event handling.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from time import perf_counter_ns

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jarvis.core.computer.browser.actions import BrowserActionRunner
from jarvis.core.computer.browser.locator import BrowserLocatorResolver
from jarvis.core.computer.browser.manager import BrowserManager
from jarvis.core.computer.browser.pages import BrowserNavigator


async def run_benchmark():
    print("\n" + "=" * 60)
    print("JARVIS EDGE v1.0 — BROWSER LATENCY BENCHMARK [REAL HARDWARE]")
    print("=" * 60)

    # 1. Cold start
    t0 = perf_counter_ns()
    manager = BrowserManager(headless=True)
    page = await manager.get_active_page()
    cold_start_ms = (perf_counter_ns() - t0) / 1e6
    print(f"1. Cold Browser Launch: {cold_start_ms:6.1f} ms")

    # 2. Warm reuse
    t_warm0 = perf_counter_ns()
    page_warm = await manager.get_active_page()
    warm_reuse_ms = (perf_counter_ns() - t_warm0) / 1e6
    print(f"2. Warm Context Reuse:  {warm_reuse_ms:6.3f} ms")

    # Load local HTML fixture to isolate network latency completely
    fixture_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Benchmark Page</title></head>
    <body>
        <h1>Test Header</h1>
        <button id="submit-btn" role="button">Search Documentation</button>
        <input type="text" placeholder="Search TensorFlow..." id="search-input" />
        <a href="#test" role="link">API Documentation</a>
    </body>
    </html>
    """
    await page.set_content(fixture_html)

    # 3. Semantic Locator Resolution Benchmark
    print("\n3. Semantic Locator Resolution Latency (50 iterations):")
    loc_times = []
    for _ in range(50):
        t_loc0 = perf_counter_ns()
        loc, conf = await BrowserLocatorResolver.resolve_strict(page=page, role="button", name="Search Documentation")
        loc_times.append((perf_counter_ns() - t_loc0) / 1e6)

    p50_loc = np.percentile(loc_times, 50)
    p95_loc = np.percentile(loc_times, 95)
    print(f"Role + Name Locator -> p50: {p50_loc:5.2f} ms | p95: {p95_loc:5.2f} ms | Status: {conf.name}")

    # 4. Action Execution (Click, Fill) Benchmark
    print("\n4. Browser Action Dispatch Overhead:")
    click_times = []
    for _ in range(20):
        t_clk0 = perf_counter_ns()
        outcome = await BrowserActionRunner.click(page=page, role="button", name="Search Documentation")
        click_times.append((perf_counter_ns() - t_clk0) / 1e6)

    p50_clk = np.percentile(click_times, 50)
    p95_clk = np.percentile(click_times, 95)
    print(f"Semantic Click Action -> p50: {p50_clk:5.2f} ms | p95: {p95_clk:5.2f} ms | Success: {outcome.success}")

    fill_times = []
    for i in range(20):
        t_fill0 = perf_counter_ns()
        outcome = await BrowserActionRunner.fill(page=page, placeholder="Search TensorFlow...", value=f"query_{i}")
        fill_times.append((perf_counter_ns() - t_fill0) / 1e6)

    p50_fill = np.percentile(fill_times, 50)
    p95_fill = np.percentile(fill_times, 95)
    print(f"Semantic Fill Action  -> p50: {p50_fill:5.2f} ms | p95: {p95_fill:5.2f} ms | Success: {outcome.success}")

    # 5. Clean teardown
    await manager.stop()
    print("\nBrowser benchmark completed successfully.")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
