"""Bounded system metrics collector (CPU, RAM, GPU) for JARVIS Desktop UI."""
from __future__ import annotations

import logging
import subprocess
from typing import NamedTuple

import psutil
from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger("jarvis.ui.metrics")


class SystemMetrics(NamedTuple):
    cpu_percent: float
    ram_percent: float
    gpu_percent: float
    vram_mb: float


class MetricsSampler(QObject):
    """Samples host hardware metrics on a bounded timer."""

    metricsSampled = Signal(float, float, float, float)  # cpu, ram, gpu, vram

    def __init__(self, interval_ms: int = 1000, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._interval_ms = interval_ms
        self._timer = QTimer(self)
        self._timer.setInterval(self._interval_ms)
        self._timer.timeout.connect(self.sample)
        self._has_gpu = True

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        if self._timer.isActive():
            self._timer.stop()

    def set_interval(self, interval_ms: int) -> None:
        self._interval_ms = interval_ms
        if self._timer.isActive():
            self._timer.setInterval(interval_ms)

    def sample(self) -> None:
        """Sample current CPU, RAM, and GPU/VRAM with zero high-frequency overhead."""
        try:
            # CPU and RAM via psutil
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent

            gpu = 0.0
            vram = 0.0

            # GPU sampling if available
            if self._has_gpu:
                try:
                    # Windows nvidia-smi quick query
                    cmd = ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"]
                    result = subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        text=True,
                        timeout=0.3,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        parts = result.stdout.strip().split("\n")[0].split(",")
                        gpu = float(parts[0].strip())
                        vram = float(parts[1].strip())
                except Exception:
                    # Disable further nvidia-smi calls to avoid child process spawn overhead
                    self._has_gpu = False

            self.metricsSampled.emit(cpu, ram, gpu, vram)
        except Exception as exc:
            logger.debug("Metrics sampling error: %s", exc)
