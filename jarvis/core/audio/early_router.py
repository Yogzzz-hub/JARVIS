"""Early route preview and READ-ONLY prefetch for JARVIS EDGE.

Runs cheap Phase-2 normalization + Lane-0 preview on stable prefix
text while the user is still speaking. Only READ_ONLY prefetch is
permitted — state-changing actions are absolutely prohibited.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from time import perf_counter_ns
from typing import Any

from jarvis.core.stt.base import TranscriptStablePrefix

logger = logging.getLogger("jarvis.audio.early_router")


@dataclass(slots=True)
class PredictedRoute:
    """Cached route prediction from stable prefix."""
    prefetch_id: str
    session_id: str
    stable_text: str
    intent: str | None = None
    is_deterministic: bool = False
    is_complete: bool = False
    timestamp_ns: int = 0

    def __post_init__(self):
        if not self.prefetch_id:
            self.prefetch_id = f"pf_{uuid.uuid4().hex[:8]}"
        if not self.timestamp_ns:
            self.timestamp_ns = perf_counter_ns()


@dataclass(slots=True)
class PrefetchResult:
    """Result from a speculative READ_ONLY prefetch."""
    prefetch_id: str
    session_id: str
    tool: str
    data: dict = field(default_factory=dict)
    cancelled: bool = False


# Tools that are absolutely prohibited for speculative prefetch
_PROHIBITED_PREFETCH_TOOLS = frozenset({
    "open_app", "close_app", "move_file", "rename_file", "delete_file",
    "copy_file", "create_file", "create_folder", "delete_folder",
    "send_email", "send_webhook", "install_software", "change_volume",
    "set_volume", "volume", "shutdown", "restart", "lock",
    "screenshot", "launch", "execute", "run",
})

# Only these risk levels are allowed for prefetch
_ALLOWED_PREFETCH_RISKS = frozenset({"READ_ONLY"})


class EarlyRoutePreview:
    """Runs early routing on stable transcript prefixes.

    ABSOLUTE RULES:
    1. Partial transcript NEVER triggers state-changing execution
    2. Only READ_ONLY prefetch is permitted
    3. Every prefetch has a session_id for cancellation
    4. If transcript changes materially, cancel/discard result
    """

    def __init__(self, router: Any = None):
        self._router = router
        self._current_prediction: PredictedRoute | None = None
        self._prefetch_results: dict[str, PrefetchResult] = {}
        self._cancelled: set[str] = set()

    async def preview(self, stable: TranscriptStablePrefix) -> PredictedRoute | None:
        """Run cheap Lane-0 preview on stable prefix text.

        Returns PredictedRoute if a deterministic intent is found.
        Does NOT execute anything.
        """
        if not stable.text or not self._router:
            return None

        try:
            # Use router's normalization and pattern matching only
            from jarvis.core.router.normalize import normalize_text
            from jarvis.core.router.control import match_control

            # Check control first
            ctrl = match_control(stable.text, "preview")
            if ctrl:
                prediction = PredictedRoute(
                    prefetch_id="",
                    session_id=stable.session_id,
                    stable_text=stable.text,
                    intent=ctrl.intent,
                    is_deterministic=True,
                    is_complete=True,
                )
                self._current_prediction = prediction
                return prediction

            # Run normalization + pattern matching
            _, normalized = normalize_text(stable.text)
            if not normalized:
                return None

            decision = await self._router.route(stable.text)

            prediction = PredictedRoute(
                prefetch_id="",
                session_id=stable.session_id,
                stable_text=stable.text,
                intent=decision.intent if decision else None,
                is_deterministic=decision.lane.value == "LANE_0" if decision else False,
                is_complete=bool(decision and decision.intent),
            )
            self._current_prediction = prediction
            return prediction

        except Exception as exc:
            logger.debug("Early route preview failed: %s", exc)
            return None

    def is_prefetch_safe(self, tool_name: str, risk_level: str = "") -> bool:
        """Check if a tool is safe for speculative prefetch.

        Only READ_ONLY tools are permitted. State-changing tools
        are absolutely prohibited.
        """
        if tool_name in _PROHIBITED_PREFETCH_TOOLS:
            return False
        if risk_level and risk_level not in _ALLOWED_PREFETCH_RISKS:
            return False
        return True

    def cancel_prefetch(self, session_id: str) -> int:
        """Cancel all prefetches for a session. Returns count cancelled."""
        count = 0
        for pid, result in list(self._prefetch_results.items()):
            if result.session_id == session_id:
                result.cancelled = True
                self._cancelled.add(pid)
                count += 1
        return count

    def get_prediction(self) -> PredictedRoute | None:
        """Get current route prediction (may be None)."""
        return self._current_prediction

    def reset(self) -> None:
        """Reset for new session."""
        self._current_prediction = None
        self._prefetch_results.clear()
        self._cancelled.clear()
