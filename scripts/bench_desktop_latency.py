"""Desktop Automation & UIA Latency Benchmark for JARVIS EDGE v1.0.

Measures:
1. AppCatalog / AppResolver executable resolution latency.
2. Win32 / UIA top-level window lookup and control pattern resolve.
3. Lightweight process and window verification without fixed sleeps.
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

from jarvis.security.verifiers.strategies import ProcessRunningVerifier, WindowExistsVerifier
from jarvis.tools.system.app_resolver import AppResolver


async def run_benchmark():
    print("\n" + "=" * 60)
    print("JARVIS EDGE v1.0 — DESKTOP AUTOMATION & UIA BENCHMARK [REAL HARDWARE]")
    print("=" * 60)

    # 1. AppResolver Lookup Benchmark
    print("\n1. AppResolver Executable Resolution Latency (100 iterations):")
    resolver = AppResolver()
    t_b0 = perf_counter_ns()
    resolver.build()
    build_ms = (perf_counter_ns() - t_b0) / 1e6
    print(f"App Catalog build/index time: {build_ms:.2f} ms ({len(resolver.cache)} applications indexed)")

    apps = ["chrome", "notepad", "calculator", "terminal", "cmd", "vscode", "explorer"]
    resolve_times = []
    for app_name in apps * 15:
        t0 = perf_counter_ns()
        target = resolver.resolve(app_name)
        resolve_times.append((perf_counter_ns() - t0) / 1e6)

    p50_res = np.percentile(resolve_times, 50)
    p95_res = np.percentile(resolve_times, 95)
    print(f"App resolution -> p50: {p50_res:6.4f} ms | p95: {p95_res:6.4f} ms")

    # 2. Top-Level Window Resolution Latency
    print("\n2. Win32 Top-Level Window Lookup (50 iterations):")
    win_times = []
    try:
        import win32gui
        for _ in range(50):
            t0 = perf_counter_ns()
            top_windows = []

            def _enum_cb(hwnd, extra):
                if win32gui.IsWindowVisible(hwnd):
                    txt = win32gui.GetWindowText(hwnd)
                    if txt:
                        top_windows.append((hwnd, txt))
                return True

            win32gui.EnumWindows(_enum_cb, None)
            win_times.append((perf_counter_ns() - t0) / 1e6)

        p50_win = np.percentile(win_times, 50)
        p95_win = np.percentile(win_times, 95)
        print(f"Enum top-level windows ({len(top_windows)} visible) -> p50: {p50_win:5.2f} ms | p95: {p95_win:5.2f} ms")
    except Exception as e:
        print(f"Window enumeration error: {e}")

    # 3. ProcessRunningVerifier Benchmark (event-driven ladder without fixed sleeps)
    print("\n3. Process Running Verifier (20 iterations on active processes):")
    proc_verifier = ProcessRunningVerifier()
    proc_times = []
    for _ in range(20):
        t0 = perf_counter_ns()
        v_res = await proc_verifier.verify("python.exe", timeout_s=0.5)
        proc_times.append(v_res.duration_ms)

    p50_proc = np.percentile(proc_times, 50)
    p95_proc = np.percentile(proc_times, 95)
    print(f"Process verification -> p50: {p50_proc:5.2f} ms | p95: {p95_proc:5.2f} ms | Verified: {v_res.verified}")

    # 4. WindowExistsVerifier Benchmark
    print("\n4. Window Exists Verifier:")
    win_verifier = WindowExistsVerifier()
    t0 = perf_counter_ns()
    w_res = await win_verifier.verify("explorer.exe")
    print(f"Window verification latency: {w_res.duration_ms:5.3f} ms | Status: {w_res.status.value}")

    print("\nDesktop benchmark completed successfully.")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
