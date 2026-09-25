"""System tray integration for JARVIS EDGE Desktop UI."""
from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

logger = logging.getLogger("jarvis.ui.tray")


def create_tray_pixmap(color_hex: str = "#00E5FF") -> QPixmap:
    """Generate a clean 24x24 Jarvis Core icon programmatically without external assets."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Outer subtle ring
    painter.setPen(QColor(color_hex).lighter(120))
    painter.setBrush(QColor(10, 15, 25, 200))
    painter.drawEllipse(2, 2, 27, 27)

    # Middle ring
    painter.setPen(QColor(color_hex))
    painter.setBrush(QColor(0, 0, 0, 0))
    painter.drawEllipse(6, 6, 19, 19)

    # Core
    painter.setBrush(QColor(color_hex))
    painter.drawEllipse(11, 11, 9, 9)

    painter.end()
    return pixmap


class JarvisTrayIcon(QSystemTrayIcon):
    """QSystemTrayIcon for JARVIS with rich context menu."""

    dashboardRequested = Signal()
    talkRequested = Signal()
    stopSpeakingRequested = Signal()
    cancelTaskRequested = Signal()
    settingsRequested = Signal()
    restartUIRequested = Signal()
    exitUIRequested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.setToolTip("JARVIS EDGE — Ready")

        self._normal_icon = QIcon(create_tray_pixmap("#00E5FF"))
        self._listening_icon = QIcon(create_tray_pixmap("#00E676"))
        self._busy_icon = QIcon(create_tray_pixmap("#FFB300"))
        self._offline_icon = QIcon(create_tray_pixmap("#757575"))
        self._error_icon = QIcon(create_tray_pixmap("#FF5252"))

        self.setIcon(self._normal_icon)

        # Build Context Menu
        self._menu = QMenu()
        self._build_menu()
        self.setContextMenu(self._menu)

        # Connect tray activation (single/double click)
        self.activated.connect(self._on_activated)

    def _build_menu(self) -> None:
        title_action = QAction("JARVIS EDGE v1.0", self._menu)
        title_action.setEnabled(False)
        self._menu.addAction(title_action)
        self._menu.addSeparator()

        dash_action = QAction("Open Dashboard (Ctrl+Shift+D)", self._menu)
        dash_action.triggered.connect(self.dashboardRequested)
        self._menu.addAction(dash_action)

        talk_action = QAction("Talk (Ctrl+Shift+J)", self._menu)
        talk_action.triggered.connect(self.talkRequested)
        self._menu.addAction(talk_action)

        self._menu.addSeparator()

        stop_action = QAction("Stop Speaking", self._menu)
        stop_action.triggered.connect(self.stopSpeakingRequested)
        self._menu.addAction(stop_action)

        cancel_action = QAction("Cancel Current Task", self._menu)
        cancel_action.triggered.connect(self.cancelTaskRequested)
        self._menu.addAction(cancel_action)

        self._menu.addSeparator()

        settings_action = QAction("Settings", self._menu)
        settings_action.triggered.connect(self.settingsRequested)
        self._menu.addAction(settings_action)

        restart_action = QAction("Restart UI", self._menu)
        restart_action.triggered.connect(self.restartUIRequested)
        self._menu.addAction(restart_action)

        exit_action = QAction("Exit UI (Keeps Jarvis Alive)", self._menu)
        exit_action.triggered.connect(self.exitUIRequested)
        self._menu.addAction(exit_action)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.dashboardRequested.emit()

    @Slot(str)
    def update_state(self, state: str) -> None:
        """Update icon and tooltip based on assistant / connection state."""
        if state == "ONLINE":
            self.setIcon(self._normal_icon)
            self.setToolTip("JARVIS EDGE — Online")
        elif state == "LISTENING":
            self.setIcon(self._listening_icon)
            self.setToolTip("JARVIS EDGE — Listening...")
        elif state in ("EXECUTING", "ROUTING", "PLANNING", "VERIFYING"):
            self.setIcon(self._busy_icon)
            self.setToolTip(f"JARVIS EDGE — {state}")
        elif state == "OFFLINE":
            self.setIcon(self._offline_icon)
            self.setToolTip("JARVIS EDGE — Offline")
        elif state == "ERROR":
            self.setIcon(self._error_icon)
            self.setToolTip("JARVIS EDGE — Error")
