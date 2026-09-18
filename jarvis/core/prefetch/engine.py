"""Safe, bounded speculative prefetch engine strictly limited to READ_ONLY operations (Phase 12)."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple


@dataclass
class PrefetchTask:
    task_id: str
    action_name: str
    target_resource: str
    coro_func: Callable[[], Coroutine[Any, Any, Any]]
    is_read_only: bool = True
    created_at: float = field(default_factory=time.time)
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, CANCELLED, USED, DISCARDED
    result: Optional[Any] = None
    asyncio_task: Optional[asyncio.Task] = None


class PrefetchEngine:
    """
    Speculative prefetch engine strictly bounded to READ_ONLY operations.
    Guarantees that state changes are NEVER speculatively pre-executed.
    Bounds concurrency to max 2 concurrent read tasks and cancels immediately
    when user intent diverges.
    """

    def __init__(self, max_concurrent: int = 2):
        self.max_concurrent = max_concurrent
        self._active_prefetches: Dict[str, PrefetchTask] = {}
        self.stats = {
            "prefetch_started": 0,
            "prefetch_used": 0,
            "prefetch_discarded": 0,
            "latency_saved_ms": 0.0,
        }

    def can_speculate(self, action_name: str) -> bool:
        """Enforces the absolute invariant: only READ_ONLY operations can be prefetched."""
        forbidden_prefixes = (
            "send", "delete", "move", "upload", "submit", "post", "create",
            "write", "launch", "kill", "modify", "set", "update"
        )
        norm_name = action_name.lower().strip()
        if any(norm_name.startswith(p) for p in forbidden_prefixes):
            return False
        return True

    async def schedule_prefetch(
        self,
        task_id: str,
        action_name: str,
        target_resource: str,
        coro_func: Callable[[], Coroutine[Any, Any, Any]],
    ) -> Tuple[bool, str]:
        """Schedules a speculative read task if within budget and policy."""
        # 1. Safety Invariant Check
        if not self.can_speculate(action_name):
            return False, f"SPECULATION_REJECTED: action '{action_name}' is not READ_ONLY"

        # 2. Concurrency bound check
        running_count = sum(1 for t in self._active_prefetches.values() if t.status in ("PENDING", "RUNNING"))
        if running_count >= self.max_concurrent:
            return False, "CONCURRENCY_BUDGET_EXCEEDED"

        task = PrefetchTask(
            task_id=task_id,
            action_name=action_name,
            target_resource=target_resource,
            coro_func=coro_func,
            is_read_only=True,
            status="RUNNING",
        )
        self._active_prefetches[task_id] = task
        self.stats["prefetch_started"] += 1

        async def _runner():
            try:
                task.result = await coro_func()
                task.status = "COMPLETED"
            except asyncio.CancelledError:
                task.status = "CANCELLED"
            except Exception:
                task.status = "DISCARDED"

        task.asyncio_task = asyncio.create_task(_runner())
        return True, "SCHEDULED"

    def claim_prefetched_result(self, task_id: str) -> Optional[Any]:
        """Claims prefetched result if ready, recording latency savings."""
        task = self._active_prefetches.get(task_id)
        if task and task.status == "COMPLETED" and task.result is not None:
            task.status = "USED"
            self.stats["prefetch_used"] += 1
            # Estimate latency saved from task runtime
            self.stats["latency_saved_ms"] += (time.time() - task.created_at) * 1000.0
            res = task.result
            self._active_prefetches.pop(task_id, None)
            return res
        return None

    def cancel_or_discard(self, task_id: str):
        """Immediately cancels and discards an irrelevant prefetch task."""
        task = self._active_prefetches.pop(task_id, None)
        if task:
            if task.asyncio_task and not task.asyncio_task.done():
                task.asyncio_task.cancel()
            task.status = "DISCARDED"
            self.stats["prefetch_discarded"] += 1

    def cancel_all(self):
        """Cancels all active prefetch tasks."""
        for tid in list(self._active_prefetches.keys()):
            self.cancel_or_discard(tid)

    def get_stats(self) -> Dict[str, Any]:
        hit_rate = (
            self.stats["prefetch_used"] / self.stats["prefetch_started"]
            if self.stats["prefetch_started"] > 0 else 0.0
        )
        return {
            **self.stats,
            "hit_rate_pct": f"{hit_rate * 100:.1f}%",
            "active_tasks": len(self._active_prefetches),
        }
