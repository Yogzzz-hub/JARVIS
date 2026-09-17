"""Long-task Progress Tracker for JARVIS EDGE Phase 7.

Ensures silent execution during normal tasks, while allowing at most ONE
short, truthful progress cue ("Still working on it.") if a task exceeds
the long-task threshold (default 15–20s).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Callable, Dict, Optional

logger = logging.getLogger("jarvis.response.progress")


class ProgressTracker:
    """Tracks long-running tasks and emits at most one truthful progress cue."""

    def __init__(
        self,
        progress_threshold_seconds: float = 15.0,
        cue_phrase: str = "Still working on it.",
    ) -> None:
        self.threshold_seconds = progress_threshold_seconds
        self.cue_phrase = cue_phrase
        self._active_timers: Dict[str, asyncio.Task] = {}
        self._cued_requests: set[str] = set()

    def start_tracking(
        self,
        request_id: str,
        is_active_fn: Callable[[], bool],
        on_progress_cue: Callable[[str, str], None],
    ) -> None:
        """Start tracking a task for long-duration progress notification."""
        self.cancel(request_id)

        async def _timer_worker():
            try:
                await asyncio.sleep(self.threshold_seconds)
                # Verify task is still running and hasn't received a cue
                if request_id not in self._cued_requests and is_active_fn():
                    self._cued_requests.add(request_id)
                    logger.info("Long task progress cue triggered for %s", request_id)
                    on_progress_cue(request_id, self.cue_phrase)
            except asyncio.CancelledError:
                pass
            finally:
                self._active_timers.pop(request_id, None)

        self._active_timers[request_id] = asyncio.create_task(_timer_worker())

    def cancel(self, request_id: str) -> None:
        """Cancel tracking when task finishes or is aborted."""
        timer = self._active_timers.pop(request_id, None)
        if timer and not timer.done():
            timer.cancel()
        self._cued_requests.discard(request_id)

    def is_cued(self, request_id: str) -> bool:
        """Check if request has already received a progress cue."""
        return request_id in self._cued_requests
