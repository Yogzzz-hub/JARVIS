"""Windows UI Automation Backend Interface and Adapter."""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("jarvis.computer.windows")

try:
    import uiautomation as auto
    import win32gui
    import win32process
    import win32con
    HAS_WINDOWS_NATIVE = True
except ImportError:
    auto = None
    win32gui = None
    win32process = None
    win32con = None
    HAS_WINDOWS_NATIVE = False


class WindowsUIABackend:
    """Production Windows UI Automation Backend using uiautomation and pywin32."""

    def __init__(self) -> None:
        self.is_available = HAS_WINDOWS_NATIVE

    def list_windows(self) -> List[Dict[str, Any]]:
        """List active desktop windows with PID, title, foreground state, and hwnd."""
        if not self.is_available:
            return []

        results = []
        try:
            fg_hwnd = win32gui.GetForegroundWindow()

            def enum_windows_callback(hwnd: int, extra: Any) -> bool:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                title = win32gui.GetWindowText(hwnd).strip()
                if not title:
                    return True

                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                # Filter out shell tray, tooltips, program manager
                class_name = win32gui.GetClassName(hwnd)
                if class_name in ("Progman", "Shell_TrayWnd", "Button"):
                    return True

                results.append({
                    "window_id": str(hwnd),
                    "hwnd": hwnd,
                    "process_id": pid,
                    "window_title": title,
                    "class_name": class_name,
                    "foreground": (hwnd == fg_hwnd),
                    "enabled": bool(win32gui.IsWindowEnabled(hwnd)),
                })
                return True

            win32gui.EnumWindows(enum_windows_callback, None)
        except Exception as e:
            logger.warning(f"Failed to enumerate windows: {e}")
        return results

    def find_window_control(self, window_id: str) -> Optional[Any]:
        """Find a UIA Control given an hwnd or window_id."""
        if not self.is_available:
            return None
        try:
            hwnd = int(window_id)
            ctrl = auto.ControlFromHandle(hwnd)
            return ctrl
        except Exception as e:
            logger.warning(f"Failed to get control for window_id {window_id}: {e}")
            return None

    def get_focused_control(self) -> Optional[Any]:
        """Get currently focused UIA Control."""
        if not self.is_available:
            return None
        try:
            return auto.GetFocusedControl()
        except Exception:
            return None

    def focus_window(self, window_id: str) -> bool:
        """Bring window to foreground."""
        if not self.is_available:
            return False
        try:
            hwnd = int(window_id)
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.05)
            return True
        except Exception as e:
            logger.warning(f"Failed to focus window {window_id}: {e}")
            return False
