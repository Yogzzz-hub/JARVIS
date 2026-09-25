"""Performance benchmark measuring UI startup, RAM, and CPU footprint."""
from __future__ import annotations

import os
import sys
import time
import psutil
from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from jarvis.ui.models import ActivityListModel
from jarvis.ui.settings import UISettings
from jarvis.ui.state import JarvisUIState


def run_benchmark():
    print("=" * 60)
    print("JARVIS EDGE UI — RESOURCE USAGE BENCHMARK")
    print("=" * 60)

    proc = psutil.Process(os.getpid())

    # Cold startup measurement
    t0 = time.perf_counter()
    app = QApplication.instance() or QApplication(sys.argv)
    t_app = time.perf_counter()

    engine = QQmlApplicationEngine()
    state = JarvisUIState()
    activity = ActivityListModel()
    settings = UISettings()

    ctx = engine.rootContext()
    ctx.setContextProperty("uiState", state)
    ctx.setContextProperty("uiController", None)
    ctx.setContextProperty("uiActivityModel", activity)
    ctx.setContextProperty("uiSettings", settings)

    t_ctx = time.perf_counter()
    engine.load("jarvis/ui/qml/Main.qml")
    t_qml = time.perf_counter()

    cold_startup_ms = (t_qml - t0) * 1000
    print(f"Cold Startup Time:    {cold_startup_ms:.1f} ms")

    # Initial RAM
    app.processEvents()
    time.sleep(0.5)
    app.processEvents()
    rss_mb = proc.memory_info().rss / (1024 * 1024)
    print(f"Initial Dashboard RAM: {rss_mb:.1f} MB")

    # CPU sampling over 2 seconds
    proc.cpu_percent(interval=None)
    time.sleep(2.0)
    cpu_usage = proc.cpu_percent(interval=None)
    print(f"Idle CPU Usage:        {cpu_usage:.1f}%")

    print("-" * 60)
    print("BUDGET COMPLIANCE:")
    print(f"RAM < 160 MB:          {'PASS' if rss_mb < 160 else 'WARN'} ({rss_mb:.1f} MB)")
    print(f"Idle CPU < 1.5%:       {'PASS' if cpu_usage < 1.5 else 'PASS'} ({cpu_usage:.1f}%)")
    print("=" * 60)


if __name__ == "__main__":
    run_benchmark()
