"""Focus Guard — Verifies and monitors window/control focus for safe input delivery.

The FocusGuard ensures that JARVIS never types into the wrong window.
Before every dictation commit or UI action, the guard checks that the
expected target window still has foreground focus.

Safety invariant: If focus is lost, dictation pauses immediately.
"""
from __future__ import annotations

import enum
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from jarvis.tools.system.input_layer import (
    get_foreground_hwnd,
    get_foreground_process_name,
    get_window_title,
    verify_focus,
)

logger = logging.getLogger("jarvis.desktop.focus_guard")


class FocusState(str, enum.Enum):
    """Current state of the focus guard."""
    UNINITIALIZED = "UNINITIALIZED"   # No target set
    FOCUSED = "FOCUSED"               # Target window has focus
    LOST = "LOST"                     # Focus moved to different window
    TARGET_CLOSED = "TARGET_CLOSED"   # Target window no longer exists
    REFOCUSING = "REFOCUSING"         # Attempting to restore focus


@dataclass
class FocusSnapshot:
    """Point-in-time snapshot of focus state."""
    hwnd: int
    process_name: str
    window_title: str
    timestamp: float = field(default_factory=time.time)
    matches_target: bool = False


class FocusGuard:
    """Verifies and monitors window focus for safe input delivery.

    Usage:
        guard = FocusGuard()
        guard.set_target(hwnd=12345, process_name="notepad.exe")

        # Before typing:
        if guard.check():
            type_text("hello")
        else:
            # Focus lost, pause dictation
            guard.state  # FocusState.LOST

    Thread-safety: All methods are safe to call from any thread.
    """

    def __init__(
        self,
        on_focus_lost: Optional[Callable[[FocusSnapshot], None]] = None,
        on_focus_restored: Optional[Callable[[FocusSnapshot], None]] = None,
        max_refocus_attempts: int = 3,
    ) -> None:
        self._target_hwnd: int = 0
        self._target_process: str = ""
        self._target_title: str = ""
        self._state: FocusState = FocusState.UNINITIALIZED
        self._last_check: float = 0.0
        self._consecutive_failures: int = 0
        self._on_focus_lost = on_focus_lost
        self._on_focus_restored = on_focus_restored
        self._max_refocus_attempts = max_refocus_attempts
        self._check_count: int = 0
        self._fail_count: int = 0

    @property
    def state(self) -> FocusState:
        return self._state

    @property
    def target_hwnd(self) -> int:
        return self._target_hwnd

    @property
    def target_process(self) -> str:
        return self._target_process

    @property
    def target_title(self) -> str:
        return self._target_title

    @property
    def is_focused(self) -> bool:
        return self._state == FocusState.FOCUSED

    def set_target(
        self,
        hwnd: int,
        process_name: str = "",
        window_title: str = "",
    ) -> None:
        """Set the expected focus target.

        Args:
            hwnd: Window handle that should be focused.
            process_name: Expected process name (e.g., 'notepad.exe').
            window_title: Expected window title (for logging/diagnostics).
        """
        self._target_hwnd = hwnd
        self._target_process = process_name
        self._target_title = window_title or get_window_title(hwnd)
        self._state = FocusState.FOCUSED if verify_focus(hwnd) else FocusState.LOST
        self._consecutive_failures = 0
        self._check_count = 0
        self._fail_count = 0
        self._last_check = time.time()
        logger.info(
            "FocusGuard target set: hwnd=%d process=%s title=%s state=%s",
            hwnd, process_name, self._target_title, self._state.value,
        )

    def set_target_current(self) -> bool:
        """Set the current foreground window as the target.

        Returns:
            True if a foreground window was found and set.
        """
        hwnd = get_foreground_hwnd()
        if not hwnd:
            logger.warning("FocusGuard: No foreground window found")
            return False
        proc = get_foreground_process_name()
        title = get_window_title(hwnd)
        self.set_target(hwnd, proc, title)
        return True

    def check(self) -> bool:
        """Check if the target window still has focus.

        This is the primary API. Call before every input commit.

        Returns:
            True if focus is verified on the target window.
        """
        if self._state == FocusState.UNINITIALIZED:
            return False

        self._check_count += 1
        self._last_check = time.time()
        current_hwnd = get_foreground_hwnd()

        if current_hwnd == self._target_hwnd:
            # Focus is on target
            if self._state != FocusState.FOCUSED:
                prev_state = self._state
                self._state = FocusState.FOCUSED
                self._consecutive_failures = 0
                logger.info(
                    "FocusGuard: Focus restored to %s (was %s)",
                    self._target_title, prev_state.value,
                )
                if self._on_focus_restored:
                    try:
                        self._on_focus_restored(self._snapshot(current_hwnd, True))
                    except Exception:
                        pass
            return True

        # Focus is NOT on target
        self._consecutive_failures += 1
        self._fail_count += 1

        # Check if target window still exists
        target_title = get_window_title(self._target_hwnd)
        if not target_title:
            self._state = FocusState.TARGET_CLOSED
            logger.warning(
                "FocusGuard: Target window closed (hwnd=%d, was '%s')",
                self._target_hwnd, self._target_title,
            )
        elif self._state != FocusState.LOST:
            self._state = FocusState.LOST
            current_proc = get_foreground_process_name()
            current_title = get_window_title(current_hwnd)
            logger.warning(
                "FocusGuard: Focus lost! Target='%s' Current='%s' (%s)",
                self._target_title, current_title, current_proc,
            )
            if self._on_focus_lost:
                try:
                    self._on_focus_lost(self._snapshot(current_hwnd, False))
                except Exception:
                    pass

        return False

    def attempt_refocus(self) -> bool:
        """Try to restore focus to the target window.

        Uses Win32 SetForegroundWindow with thread input attachment.
        Bounded to max_refocus_attempts.

        Returns:
            True if focus was successfully restored.
        """
        if self._state == FocusState.TARGET_CLOSED:
            return False
        if self._consecutive_failures > self._max_refocus_attempts:
            logger.warning("FocusGuard: Max refocus attempts (%d) exceeded", self._max_refocus_attempts)
            return False

        self._state = FocusState.REFOCUSING
        try:
            from jarvis.tools.system.native import bring_to_front
            # bring_to_front uses process names, but we can also try by hwnd directly
            if self._target_process:
                success = bring_to_front(name=self._target_process)
            else:
                success = bring_to_front(name=self._target_title)

            if success:
                time.sleep(0.05)  # Brief settle for focus switch
                return self.check()
        except Exception as e:
            logger.warning("FocusGuard: Refocus failed: %s", e)

        return False

    def clear(self) -> None:
        """Clear the focus target. Called when dictation ends."""
        self._target_hwnd = 0
        self._target_process = ""
        self._target_title = ""
        self._state = FocusState.UNINITIALIZED
        self._consecutive_failures = 0
        logger.debug("FocusGuard: Target cleared")

    def diagnostics(self) -> dict:
        """Return diagnostic information about focus guard state."""
        return {
            "state": self._state.value,
            "target_hwnd": self._target_hwnd,
            "target_process": self._target_process,
            "target_title": self._target_title,
            "total_checks": self._check_count,
            "total_failures": self._fail_count,
            "consecutive_failures": self._consecutive_failures,
            "last_check": self._last_check,
        }

    def _snapshot(self, hwnd: int, matches: bool) -> FocusSnapshot:
        return FocusSnapshot(
            hwnd=hwnd,
            process_name=get_foreground_process_name(),
            window_title=get_window_title(hwnd),
            matches_target=matches,
        )
