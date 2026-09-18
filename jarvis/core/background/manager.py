"""Background Job Manager for low-priority idle maintenance (Phase 12)."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional
from jarvis.core.resources.governor import ResourceGovernor


class BackgroundJobManager:
    """
    Manages low-priority idle background maintenance tasks.
    Invariants:
    1. Zero external side-effects (read-only maintenance only).
    2. Pauses immediately when interactive priority tasks are running.
    """

    def __init__(self, resource_governor: Optional[ResourceGovernor] = None):
        self.resource_governor = resource_governor
        self._registered_jobs: Dict[str, Callable[[], Coroutine[Any, Any, None]]] = {}
        self._is_running: bool = False
        self._job_task: Optional[asyncio.Task] = None
        self.stats = {
            "jobs_executed": 0,
            "jobs_paused_count": 0,
            "last_run_timestamp": 0.0,
        }

    def register_maintenance_job(self, name: str, coro_func: Callable[[], Coroutine[Any, Any, None]]):
        self._registered_jobs[name] = coro_func

    async def run_idle_maintenance(self) -> int:
        """Runs one pass of maintenance jobs if system is idle."""
        # Check if governor indicates high-priority interactive tasks
        if self.resource_governor and self.resource_governor.is_background_paused():
            self.stats["jobs_paused_count"] += 1
            return 0

        executed = 0
        for name, job_func in self._registered_jobs.items():
            if self.resource_governor and self.resource_governor.is_background_paused():
                self.stats["jobs_paused_count"] += 1
                break
            try:
                await job_func()
                executed += 1
                self.stats["jobs_executed"] += 1
            except Exception:
                pass

        self.stats["last_run_timestamp"] = time.time()
        return executed

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self.stats,
            "registered_jobs": list(self._registered_jobs.keys()),
        }
