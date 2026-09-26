"""Application entry point and Qt Quick / QML engine lifecycle for JARVIS Desktop UI."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from jarvis.ui.bridge import JarvisUIBridge
from jarvis.ui.controller import JarvisUIController
from jarvis.ui.hotkeys import GlobalHotkeys
from jarvis.ui.metrics import MetricsSampler
from jarvis.ui.models import ActivityListModel
from jarvis.ui.settings import UISettings
from jarvis.ui.state import JarvisUIState
from jarvis.ui.tray import JarvisTrayIcon, create_tray_pixmap

logger = logging.getLogger("jarvis.ui")


def run_app(argv: list[str] | None = None) -> int:
    """Initialize and run the PySide6 QML application."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    logger.info("Initializing JARVIS EDGE Desktop UI...")

    # Ensure UI attaches to the user's interactive desktop on Windows
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
                logger.info("Attached UI thread to interactive 'Default' desktop")
        except Exception as exc:
            logger.debug("Failed to set thread desktop to Default: %s", exc)

    # Enable High DPI scaling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

    # Use QApplication (required for QSystemTrayIcon)
    app = QApplication(argv or sys.argv)
    app.setApplicationName("JARVIS EDGE")
    app.setOrganizationName("JarvisTeam")
    app.setQuitOnLastWindowClosed(False)
    from PySide6.QtCore import QLockFile, QStandardPaths
    lock = QLockFile(str(Path(QStandardPaths.writableLocation(QStandardPaths.TempLocation)) / "jarvis-edge-ui.lock"))
    if not lock.tryLock(0):
        logger.info("JARVIS desktop UI is already running")
        return 0

    # Set Application Icon
    app_icon = QIcon(create_tray_pixmap("#00E5FF"))
    app.setWindowIcon(app_icon)

    # Core UI Components
    settings = UISettings()
    ui_state = JarvisUIState()
    activity_model = ActivityListModel()
    metrics = MetricsSampler(interval_ms=settings.get("metrics_interval_ms", 1000))
    bridge = JarvisUIBridge(
        ws_url="ws://127.0.0.1:8765/ws",
        http_url="http://127.0.0.1:8765",
    )
    controller = JarvisUIController(
        state=ui_state,
        bridge=bridge,
        settings=settings,
        activity_model=activity_model,
        metrics=metrics,
    )

    # Global Hotkeys
    hotkeys = GlobalHotkeys()
    hotkeys.voiceOverlayRequested.connect(controller.startPTT)
    hotkeys.dashboardRequested.connect(controller.showDashboardRequested.emit)
    hotkeys.start()

    # System Tray Icon
    tray = JarvisTrayIcon()
    tray.dashboardRequested.connect(controller.showDashboardRequested.emit)
    tray.talkRequested.connect(controller.startPTT)
    tray.stopSpeakingRequested.connect(controller.stopSpeaking)
    tray.cancelTaskRequested.connect(controller.cancelTask)
    tray.exitUIRequested.connect(app.quit)

    # Update tray icon when assistant/connection state changes
    ui_state.connectionChanged.connect(tray.update_state)
    ui_state.assistantStateChanged.connect(tray.update_state)
    tray.show()

    # Procedural meshes for the 3D reactor (QML module "Jarvis3D"); the UI falls back to 2D without it.
    if os.environ.get("JARVIS_UI_2D", "").strip().lower() in ("1", "true", "yes"):
        settings.override("ui_3d", False)
    try:
        import jarvis.ui.geometry  # noqa: F401  (registers HudRingGeometry / TubeRingGeometry)
    except Exception as exc:
        logger.info("3D reactor unavailable (%s); using the 2D reactor", exc)

    # Setup QML Engine
    engine = QQmlApplicationEngine()
    qml_dir = Path(__file__).parent / "qml"
    engine.addImportPath(str(qml_dir))

    # Expose state, controller, models to QML context
    root_context = engine.rootContext()
    root_context.setContextProperty("uiState", ui_state)
    root_context.setContextProperty("uiController", controller)
    root_context.setContextProperty("uiActivityModel", activity_model)
    root_context.setContextProperty("uiSettings", settings)
    from jarvis.ui.whatsapp_contacts import WhatsAppContactsClient
    whatsapp_contacts = WhatsAppContactsClient(http_url="http://127.0.0.1:8765")
    controller.whatsappPersonalEvent.connect(whatsapp_contacts.on_backend_event)
    root_context.setContextProperty("uiWhatsApp", whatsapp_contacts)

    main_qml = qml_dir / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(main_qml)))

    if not engine.rootObjects():
        logger.error("Failed to load QML root object from %s", main_qml)
        hotkeys.stop()
        return -1

    def _bring_dashboard_to_front() -> None:
        root_objs = engine.rootObjects()
        if not root_objs:
            return
        main_win = root_objs[0]
        try:
            main_win.setVisible(True)
            main_win.showNormal()
            main_win.raise_()
            main_win.requestActivate()
            import win32gui, win32con, win32process, win32api, ctypes
            hwnd = int(main_win.winId())
            if hwnd and win32gui.IsWindow(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                fg_hwnd = win32gui.GetForegroundWindow()
                fg_thread, _ = win32process.GetWindowThreadProcessId(fg_hwnd) if fg_hwnd else (0, 0)
                cur_thread = win32api.GetCurrentThreadId()
                attached = False
                if fg_thread and fg_thread != cur_thread:
                    try:
                        attached = bool(ctypes.windll.user32.AttachThreadInput(cur_thread, fg_thread, True))
                    except Exception:
                        pass
                try:
                    ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
                except Exception:
                    pass
                win32gui.SetWindowPos(
                    hwnd,
                    win32con.HWND_TOPMOST,
                    0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW,
                )
                win32gui.SetWindowPos(
                    hwnd,
                    win32con.HWND_NOTOPMOST,
                    0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW,
                )
                try:
                    win32gui.BringWindowToTop(hwnd)
                    win32gui.SetForegroundWindow(hwnd)
                except Exception:
                    pass
                if attached:
                    try:
                        ctypes.windll.user32.AttachThreadInput(cur_thread, fg_thread, False)
                    except Exception:
                        pass
                logger.info("Dashboard window brought to foreground via Win32")
        except Exception as exc:
            logger.debug("Win32 bring to front error: %s", exc)

    controller.showDashboardRequested.connect(_bring_dashboard_to_front)

    # Start Bridge and Metrics
    bridge.start()
    metrics.start()

    # Clean shutdown handling
    def _cleanup() -> None:
        logger.info("Cleaning up JARVIS UI resources...")
        hotkeys.stop()
        metrics.stop()
        bridge.stop()


    app.aboutToQuit.connect(_cleanup)

    logger.info("JARVIS EDGE Desktop UI successfully launched.")
    return app.exec()


if __name__ == "__main__":
    sys.exit(run_app())
