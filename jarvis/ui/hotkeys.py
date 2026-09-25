"""Global hotkeys manager for JARVIS Desktop UI."""
from __future__ import annotations

import ctypes
import logging
import threading
from ctypes import wintypes
from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal, Slot

logger = logging.getLogger("jarvis.ui.hotkeys")

# Windows API constants
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

HOTKEY_PTT_ID = 101       # Ctrl + Shift + J
HOTKEY_DASHBOARD_ID = 102 # Ctrl + Shift + D


class HotkeyListenerThread(QThread):
    """Background thread listening for Windows global hotkey messages."""

    pttTriggered = Signal()
    dashboardTriggered = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._running = False
        self._thread_id = 0

    def run(self) -> None:
        user32 = ctypes.windll.user32
        self._running = True
        self._thread_id = threading.get_native_id()

        # Register Ctrl + Shift + J ('J' is vk 0x4A)
        # Register Ctrl + Shift + D ('D' is vk 0x44)
        reg_dash = user32.RegisterHotKey(None, HOTKEY_DASHBOARD_ID, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, 0x44)

        if not reg_dash:
            logger.warning("Could not register Ctrl+Shift+D hotkey")

        msg = wintypes.MSG()
        while self._running:
            # PeekMessage/GetMessage loop
            res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if res <= 0:
                break
            if msg.message == WM_HOTKEY:
                if msg.wParam == HOTKEY_DASHBOARD_ID:
                    self.dashboardTriggered.emit()

        # Unregister hotkeys on exit
        user32.UnregisterHotKey(None, HOTKEY_DASHBOARD_ID)

    def stop(self) -> None:
        self._running = False
        user32 = ctypes.windll.user32
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)


class GlobalHotkeys(QObject):
    """Safe hotkey manager with Qt signals."""

    voiceOverlayRequested = Signal()
    dashboardRequested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: HotkeyListenerThread | None = None

    def start(self) -> None:
        try:
            self._thread = HotkeyListenerThread(self)
            self._thread.pttTriggered.connect(self.voiceOverlayRequested)
            self._thread.dashboardTriggered.connect(self.dashboardRequested)
            self._thread.start()
        except Exception as exc:
            logger.warning("Failed to start global hotkeys listener: %s", exc)

    def stop(self) -> None:
        if self._thread:
            self._thread.stop()
            self._thread.wait(1000)
            self._thread = None
