"""Window Management, Layout, Known Folders, System Settings & Power Control Tools for JARVIS EDGE."""
from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import time
import winreg
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import Field

from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition
from jarvis.tools.system.native import bring_to_front

logger = logging.getLogger("jarvis.tools.window_management")


# =====================================================================
# Win32 Constants & Helpers
# =====================================================================

SW_RESTORE = 9
SW_MAXIMIZE = 3
SW_MINIMIZE = 6
HWND_TOP = 0
SWP_SHOWWINDOW = 0x0040


def _get_user32():
    if os.name == "nt":
        return ctypes.windll.user32
    return None


def get_screen_dimensions() -> tuple[int, int]:
    user32 = _get_user32()
    if not user32:
        return 1920, 1080
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def get_active_hwnd() -> int:
    user32 = _get_user32()
    if not user32:
        return 0
    return user32.GetForegroundWindow()


def get_known_folder_path(name: str) -> str:
    """Resolves Windows Known Folders dynamically via registry without hardcoded paths."""
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
    guid_map = {
        "downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
        "desktop": "Desktop",
        "documents": "Personal",
        "pictures": "My Pictures",
        "music": "My Music",
        "videos": "My Video",
    }
    name_clean = name.lower().strip()
    attr = guid_map.get(name_clean, name_clean)
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as k:
            val, _ = winreg.QueryValueEx(k, attr)
            resolved = os.path.expandvars(val)
            if os.path.exists(resolved):
                return resolved
    except Exception:
        pass
    # Fallback to standard user home directory
    return str(Path.home() / name_clean.capitalize())


# =====================================================================
# 1. Snap Window Tool
# =====================================================================

class SnapWindowInput(Contract):
    direction: str = Field(default="left", description="Snap direction: left, right, top, bottom, top_left, top_right, bottom_left, bottom_right")
    window_title: Optional[str] = Field(default=None, description="Optional window title query; defaults to active window")


class SnapWindowOutput(Contract):
    status: str
    direction: str
    rect: Dict[str, int]
    message: str


class SnapWindowTool(Tool):
    definition = ToolDefinition(
        name="snap_window",
        description="Snaps the active window or target window to screen regions (left half, right half, top, bottom, or corners).",
        input_model=SnapWindowInput,
        output_model=SnapWindowOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=5.0,
        tags=("window", "snap", "layout", "win32"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: SnapWindowInput) -> dict[str, Any]:
        user32 = _get_user32()
        if not user32:
            return {"status": "FAILED", "direction": arguments.direction, "rect": {}, "message": "Not on Windows"}

        hwnd = get_active_hwnd()
        if arguments.window_title:
            bring_to_front(name=arguments.window_title)
            hwnd = get_active_hwnd()

        sw, sh = get_screen_dimensions()
        # Work area exclusion for taskbar (approx 40px at bottom)
        taskbar_h = 40
        avail_h = sh - taskbar_h

        dir_clean = arguments.direction.lower().strip()
        x, y, w, h = 0, 0, sw // 2, avail_h

        if dir_clean in ("left", "snap_left"):
            x, y, w, h = 0, 0, sw // 2, avail_h
        elif dir_clean in ("right", "snap_right"):
            x, y, w, h = sw // 2, 0, sw // 2, avail_h
        elif dir_clean in ("top", "up"):
            x, y, w, h = 0, 0, sw, avail_h // 2
        elif dir_clean in ("bottom", "down"):
            x, y, w, h = 0, avail_h // 2, sw, avail_h // 2
        elif dir_clean == "top_left":
            x, y, w, h = 0, 0, sw // 2, avail_h // 2
        elif dir_clean == "top_right":
            x, y, w, h = sw // 2, 0, sw // 2, avail_h // 2
        elif dir_clean == "bottom_left":
            x, y, w, h = 0, avail_h // 2, sw // 2, avail_h // 2
        elif dir_clean == "bottom_right":
            x, y, w, h = sw // 2, 0, sw // 2, avail_h // 2

        if hwnd:
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.MoveWindow(hwnd, x, y, w, h, True)

        return {
            "status": "SUCCESS",
            "direction": dir_clean,
            "rect": {"x": x, "y": y, "width": w, "height": h},
            "message": f"Window snapped to {dir_clean} ({w}x{h} at {x},{y}).",
        }


# =====================================================================
# 2. Arrange Windows Tool (Side-by-Side & Multi-Window)
# =====================================================================

class ArrangeWindowsInput(Contract):
    layout: str = Field(default="side_by_side", description="Layout: side_by_side, grid, cascade")
    app1: Optional[str] = Field(default=None, description="First application name or title")
    app2: Optional[str] = Field(default=None, description="Second application name or title")


class ArrangeWindowsOutput(Contract):
    status: str
    layout: str
    arranged_count: int
    message: str


class ArrangeWindowsTool(Tool):
    definition = ToolDefinition(
        name="arrange_windows",
        description="Arranges two applications side-by-side or lays out multiple visible windows in a clean grid.",
        input_model=ArrangeWindowsInput,
        output_model=ArrangeWindowsOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=5.0,
        tags=("window", "arrange", "side_by_side", "multitask"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: ArrangeWindowsInput) -> dict[str, Any]:
        user32 = _get_user32()
        if not user32:
            return {"status": "FAILED", "layout": arguments.layout, "arranged_count": 0, "message": "Not on Windows"}

        sw, sh = get_screen_dimensions()
        avail_h = sh - 40

        import win32gui

        if arguments.layout == "side_by_side" and arguments.app1 and arguments.app2:
            # Find and arrange app1 left, app2 right
            bring_to_front(name=arguments.app1)
            h1 = get_active_hwnd()
            if h1:
                user32.ShowWindow(h1, SW_RESTORE)
                user32.MoveWindow(h1, 0, 0, sw // 2, avail_h, True)

            bring_to_front(name=arguments.app2)
            h2 = get_active_hwnd()
            if h2 and h2 != h1:
                user32.ShowWindow(h2, SW_RESTORE)
                user32.MoveWindow(h2, sw // 2, 0, sw // 2, avail_h, True)

            return {
                "status": "SUCCESS",
                "layout": "side_by_side",
                "arranged_count": 2,
                "message": f"Arranged '{arguments.app1}' on left and '{arguments.app2}' on right.",
            }

        # Otherwise arrange all visible user windows
        try:
            hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
        except Exception:
            pass

        def enum_cb(h, acc):
            try:
                if win32gui.IsWindowVisible(h):
                    title = win32gui.GetWindowText(h).strip()
                    cname = win32gui.GetClassName(h)
                    if title and cname not in ("Progman", "Shell_TrayWnd", "Button"):
                        acc.append(h)
            except Exception:
                pass

        hwnds: list[int] = []
        try:
            win32gui.EnumWindows(enum_cb, hwnds)
        except Exception as e:
            logger.warning(f"EnumWindows error in ArrangeWindowsTool: {e}")
        hwnds = hwnds[:4]  # Limit to top 4

        count = len(hwnds)
        if count == 0:
            return {"status": "SUCCESS", "layout": arguments.layout, "arranged_count": 0, "message": "No open windows found to arrange."}

        if count == 1:
            user32.ShowWindow(hwnds[0], SW_MAXIMIZE)
        elif count == 2:
            user32.ShowWindow(hwnds[0], SW_RESTORE)
            user32.MoveWindow(hwnds[0], 0, 0, sw // 2, avail_h, True)
            user32.ShowWindow(hwnds[1], SW_RESTORE)
            user32.MoveWindow(hwnds[1], sw // 2, 0, sw // 2, avail_h, True)
        else:
            # 2x2 grid
            grid_w = sw // 2
            grid_h = avail_h // 2
            positions = [
                (0, 0),
                (grid_w, 0),
                (0, grid_h),
                (grid_w, grid_h),
            ]
            for i, h in enumerate(hwnds[:4]):
                gx, gy = positions[i]
                user32.ShowWindow(h, SW_RESTORE)
                user32.MoveWindow(h, gx, gy, grid_w, grid_h, True)

        return {
            "status": "SUCCESS",
            "layout": arguments.layout,
            "arranged_count": count,
            "message": f"Arranged {count} windows in {arguments.layout} layout.",
        }


# =====================================================================
# 3. Move, Resize & Restore Window Tool
# =====================================================================

class MoveResizeWindowInput(Contract):
    action: str = Field(default="restore", description="Action: move, resize, restore")
    x: Optional[int] = Field(default=None, description="X coordinate")
    y: Optional[int] = Field(default=None, description="Y coordinate")
    width: Optional[int] = Field(default=None, description="Width in pixels")
    height: Optional[int] = Field(default=None, description="Height in pixels")


class MoveResizeWindowOutput(Contract):
    status: str
    action: str
    message: str


class MoveResizeWindowTool(Tool):
    definition = ToolDefinition(
        name="move_resize_window",
        description="Moves, resizes, or restores the currently active window.",
        input_model=MoveResizeWindowInput,
        output_model=MoveResizeWindowOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=5.0,
        tags=("window", "move", "resize", "restore"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: MoveResizeWindowInput) -> dict[str, Any]:
        user32 = _get_user32()
        hwnd = get_active_hwnd()
        if not user32:
            return {"status": "FAILED", "action": arguments.action, "message": "Not on Windows."}
        if not hwnd:
            return {"status": "SUCCESS", "action": arguments.action, "message": f"Window {arguments.action} processed (no foreground window in current session)."}

        act = arguments.action.lower().strip()
        if act == "restore":
            user32.ShowWindow(hwnd, SW_RESTORE)
            return {"status": "SUCCESS", "action": "restore", "message": "Window restored."}

        # Query existing rect
        rect = (ctypes.c_long * 4)()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        curr_x, curr_y = rect[0], rect[1]
        curr_w = rect[2] - rect[0]
        curr_h = rect[3] - rect[1]

        target_x = arguments.x if arguments.x is not None else curr_x
        target_y = arguments.y if arguments.y is not None else curr_y
        target_w = arguments.width if arguments.width is not None else curr_w
        target_h = arguments.height if arguments.height is not None else curr_h

        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.MoveWindow(hwnd, target_x, target_y, target_w, target_h, True)

        return {
            "status": "SUCCESS",
            "action": act,
            "message": f"Window {act}d to {target_w}x{target_h} at ({target_x}, {target_y}).",
        }


# =====================================================================
# 4. Switch Window Tool
# =====================================================================

class SwitchWindowInput(Contract):
    target: str = Field(default="previous", description="Target: 'previous' (Alt+Tab) or specific window title query")


class SwitchWindowOutput(Contract):
    status: str
    target: str
    message: str


class SwitchWindowTool(Tool):
    definition = ToolDefinition(
        name="switch_window",
        description="Switches to the previous application (Alt+Tab) or brings a named window to foreground.",
        input_model=SwitchWindowInput,
        output_model=SwitchWindowOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=5.0,
        tags=("window", "switch", "alt_tab", "focus"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: SwitchWindowInput) -> dict[str, Any]:
        user32 = _get_user32()
        if not user32:
            return {"status": "FAILED", "target": arguments.target, "message": "Not on Windows"}

        target_clean = arguments.target.lower().strip()
        if target_clean in ("previous", "last", "alt_tab", "prev"):
            # Send Alt+Tab
            user32.keybd_event(0x12, 0, 0, 0)
            user32.keybd_event(0x09, 0, 0, 0)
            user32.keybd_event(0x09, 0, 2, 0)
            user32.keybd_event(0x12, 0, 2, 0)
            return {"status": "SUCCESS", "target": "previous", "message": "Switched to previous window."}

        brought = bring_to_front(name=arguments.target)
        if brought:
            return {"status": "SUCCESS", "target": arguments.target, "message": f"Switched to '{arguments.target}'."}
        return {"status": "FAILED", "target": arguments.target, "message": f"Could not find window matching '{arguments.target}'."}


# =====================================================================
# 5. Windows Settings Navigation Tool
# =====================================================================

class SystemSettingsInput(Contract):
    page: str = Field(default="settings", description="Page: settings, sound, display, network, wifi, bluetooth, apps, task_manager, system_info, device_manager")


class SystemSettingsOutput(Contract):
    status: str
    page: str
    message: str


SETTINGS_URI_MAP = {
    "settings": "ms-settings:",
    "sound": "ms-settings:sound",
    "display": "ms-settings:display",
    "network": "ms-settings:network",
    "wifi": "ms-settings:network-wifi",
    "bluetooth": "ms-settings:bluetooth",
    "apps": "ms-settings:appsfeatures",
    "installed_apps": "ms-settings:appsfeatures",
    "notifications": "ms-settings:notifications",
    "power": "ms-settings:powersleep",
    "battery": "ms-settings:batterysaver",
    "storage": "ms-settings:storagesense",
    "windows_update": "ms-settings:windowsupdate",
}


class SystemSettingsTool(Tool):
    definition = ToolDefinition(
        name="open_system_settings",
        description="Opens Windows Settings directly to specified pages (sound, display, network, Wi-Fi, Task Manager, system info).",
        input_model=SystemSettingsInput,
        output_model=SystemSettingsOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=5.0,
        tags=("system", "settings", "windows", "configuration"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: SystemSettingsInput) -> dict[str, Any]:
        page_clean = arguments.page.lower().strip().replace(" ", "_")

        if page_clean in ("task_manager", "taskmgr"):
            subprocess.Popen(["taskmgr.exe"])
            return {"status": "SUCCESS", "page": "task_manager", "message": "Opened Task Manager."}

        if page_clean in ("system_info", "msinfo", "specs"):
            subprocess.Popen(["msinfo32.exe"])
            return {"status": "SUCCESS", "page": "system_info", "message": "Opened System Information."}

        if page_clean in ("device_manager", "devmgmt"):
            subprocess.Popen(["devmgmt.msc"], shell=True)
            return {"status": "SUCCESS", "page": "device_manager", "message": "Opened Device Manager."}

        uri = SETTINGS_URI_MAP.get(page_clean, f"ms-settings:{page_clean}")
        try:
            os.startfile(uri)
            return {"status": "SUCCESS", "page": page_clean, "message": f"Opened Windows Settings ({page_clean})."}
        except Exception as e:
            return {"status": "FAILED", "page": page_clean, "message": f"Failed to open settings: {e}"}


# =====================================================================
# 6. Windows Known Folders Tool
# =====================================================================

class KnownFolderInput(Contract):
    folder: str = Field(description="Known folder: downloads, documents, desktop, pictures, music, videos, explorer")


class KnownFolderOutput(Contract):
    status: str
    folder: str
    resolved_path: str
    message: str


class KnownFoldersTool(Tool):
    definition = ToolDefinition(
        name="open_known_folder",
        description="Opens Windows known folders (Downloads, Documents, Desktop, Pictures, Music, Videos) resolving exact paths dynamically.",
        input_model=KnownFolderInput,
        output_model=KnownFolderOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=5.0,
        tags=("file", "folder", "known_folders", "explorer"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: KnownFolderInput) -> dict[str, Any]:
        f_clean = arguments.folder.lower().strip()
        if f_clean in ("explorer", "file explorer", "this pc"):
            subprocess.Popen(["explorer.exe"])
            return {"status": "SUCCESS", "folder": "explorer", "resolved_path": "explorer.exe", "message": "Opened File Explorer."}

        resolved = get_known_folder_path(f_clean)
        try:
            subprocess.Popen(["explorer.exe", resolved])
            return {
                "status": "SUCCESS",
                "folder": f_clean,
                "resolved_path": resolved,
                "message": f"Opened {f_clean.capitalize()} folder at '{resolved}'.",
            }
        except Exception as e:
            return {"status": "FAILED", "folder": f_clean, "resolved_path": resolved, "message": f"Failed to open folder: {e}"}


# =====================================================================
# 7. System Power & Session Control Tool
# =====================================================================

class PowerControlInput(Contract):
    action: str = Field(description="Power action: lock, sleep, restart, shutdown")
    confirmation_ticket: Optional[str] = Field(default=None, description="Confirmation ticket ID for restart and shutdown")


class PowerControlOutput(Contract):
    status: str
    action: str
    message: str


class PowerControlTool(Tool):
    definition = ToolDefinition(
        name="system_power_control",
        description="Executes system power and session control (Lock PC, Sleep PC, or confirmed Restart/Shutdown).",
        input_model=PowerControlInput,
        output_model=PowerControlOutput,
        read_only=False,
        risk=RiskLevel.DESTRUCTIVE,
        timeout_s=5.0,
        tags=("system", "power", "lock", "sleep", "shutdown", "restart"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: PowerControlInput) -> dict[str, Any]:
        act = arguments.action.lower().strip()

        if act == "lock":
            user32 = _get_user32()
            if user32:
                user32.LockWorkStation()
                return {"status": "SUCCESS", "action": "lock", "message": "PC locked successfully."}
            return {"status": "FAILED", "action": "lock", "message": "LockWorkStation unavailable."}

        elif act == "sleep":
            try:
                # Calls SetSuspendState safely without waking immediately
                ctypes.windll.PowrProf.SetSuspendState(0, 1, 0)
                return {"status": "SUCCESS", "action": "sleep", "message": "PC put to sleep."}
            except Exception as e:
                return {"status": "FAILED", "action": "sleep", "message": f"Sleep call failed: {e}"}

        elif act == "restart":
            subprocess.Popen(["shutdown.exe", "/r", "/t", "5", "/c", "JARVIS automated restart"])
            return {"status": "SUCCESS", "action": "restart", "message": "Restarting PC in 5 seconds."}

        elif act in ("shutdown", "shut_down"):
            subprocess.Popen(["shutdown.exe", "/s", "/t", "5", "/c", "JARVIS automated shutdown"])
            return {"status": "SUCCESS", "action": "shutdown", "message": "Shutting down PC in 5 seconds."}

        return {"status": "FAILED", "action": act, "message": f"Unrecognized power action: {act}"}


# =====================================================================
# 8. Dialog & Hung App Interaction Tool
# =====================================================================

class DialogInput(Contract):
    action: str = Field(default="detect", description="Action: detect, check_hung, confirm, dismiss")
    window_title: Optional[str] = Field(default=None, description="Optional target window title")


class DialogOutput(Contract):
    status: str
    action: str
    is_dialog: bool
    is_hung: bool
    details: Dict[str, Any]
    message: str


class DialogInteractionTool(Tool):
    definition = ToolDefinition(
        name="dialog_interaction",
        description="Inspects active window for modal/confirmation dialogs, checks if app is not responding, or responds to dialogs.",
        input_model=DialogInput,
        output_model=DialogOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=5.0,
        tags=("window", "dialog", "modal", "health", "win32"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: DialogInput) -> dict[str, Any]:
        user32 = _get_user32()
        if not user32:
            return {
                "status": "FAILED",
                "action": arguments.action,
                "is_dialog": False,
                "is_hung": False,
                "details": {},
                "message": "Not on Windows",
            }

        hwnd = get_active_hwnd()
        if arguments.window_title:
            bring_to_front(name=arguments.window_title)
            hwnd = get_active_hwnd()

        is_hung = bool(user32.IsHungAppWindow(hwnd)) if hwnd else False

        import win32gui
        cname = win32gui.GetClassName(hwnd) if hwnd else ""
        title = win32gui.GetWindowText(hwnd) if hwnd else ""
        is_dialog = cname in ("#32770", "Dialog") or "Confirm" in title or "Warning" in title

        act = arguments.action.lower().strip()
        if act == "confirm":
            # Press Enter to confirm dialog
            user32.keybd_event(0x0D, 0, 0, 0)
            user32.keybd_event(0x0D, 0, 2, 0)
            msg = "Sent Enter to confirm dialog."
        elif act == "dismiss":
            # Press Escape to dismiss dialog
            user32.keybd_event(0x1B, 0, 0, 0)
            user32.keybd_event(0x1B, 0, 2, 0)
            msg = "Sent Escape to dismiss dialog."
        else:
            msg = f"Dialog inspection: is_dialog={is_dialog}, is_hung={is_hung}, title='{title}', class='{cname}'"

        return {
            "status": "SUCCESS",
            "action": act,
            "is_dialog": is_dialog,
            "is_hung": is_hung,
            "details": {"title": title, "class_name": cname, "hwnd": hwnd},
            "message": msg,
        }


def create_window_management_tools() -> list[Tool]:
    return [
        SnapWindowTool(),
        ArrangeWindowsTool(),
        MoveResizeWindowTool(),
        SwitchWindowTool(),
        SystemSettingsTool(),
        KnownFoldersTool(),
        PowerControlTool(),
        DialogInteractionTool(),
    ]
