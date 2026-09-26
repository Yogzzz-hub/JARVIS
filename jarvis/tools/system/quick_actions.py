"""Fast, deterministic actions: browser tabs/navigation, Windows quick actions and phone quick actions.

No model is involved: each action is a fixed keyboard shortcut (browser, Windows) or a fixed ADB template
(phone), so it runs in milliseconds and always does the same thing.

* ``browser_quick_action`` - new/close/reopen tab, next/previous tab, go to tab N, back/forward, reload, zoom,
  bookmark, history, downloads, incognito, find on page, address bar, scroll, full screen. It acts on the browser
  you are using (Chrome, Edge, Firefox, Brave, Opera); if another app is in front, the most recent browser window
  is brought forward first.
* ``pc_quick_action`` - Task Manager, Settings, File Explorer, Run, clipboard history, emoji panel, snipping,
  task view, virtual desktops, project/display switch, notification centre, quick settings, Windows search.
* ``android_quick_action`` - quick settings, notification shade, settings pages, exact brightness and media volume,
  current app, screen on/off, and an SMS draft that you send yourself.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Literal, Optional

from pydantic import Field

from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition

logger = logging.getLogger("jarvis.tools.quick_actions")

BROWSER_PROCESSES = ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe")

VK_OEM_PLUS, VK_OEM_MINUS, VK_OEM_PERIOD = 0xBB, 0xBD, 0xBE

# action -> (modifiers, key) using names resolved against input_layer.VK at run time
_BROWSER_KEYS: dict[str, tuple[tuple[str, ...], Any]] = {
    "new_tab": (("CONTROL",), "T"), "close_tab": (("CONTROL",), "W"), "reopen_tab": (("CONTROL", "SHIFT"), "T"),
    "next_tab": (("CONTROL",), "TAB"), "previous_tab": (("CONTROL", "SHIFT"), "TAB"), "last_tab": (("CONTROL",), "N9"),
    "back": (("MENU",), "LEFT"), "forward": (("MENU",), "RIGHT"), "reload": ((), "F5"), "hard_reload": (("CONTROL",), "F5"),
    "stop_loading": ((), "ESCAPE"), "home": (("MENU",), "HOME"),
    "zoom_in": (("CONTROL",), VK_OEM_PLUS), "zoom_out": (("CONTROL",), VK_OEM_MINUS), "zoom_reset": (("CONTROL",), "N0"),
    "bookmark": (("CONTROL",), "D"), "history": (("CONTROL",), "H"), "downloads": (("CONTROL",), "J"),
    "new_window": (("CONTROL",), "N"), "incognito": (("CONTROL", "SHIFT"), "N"), "close_window": (("CONTROL", "SHIFT"), "W"),
    "find": (("CONTROL",), "F"), "address_bar": (("CONTROL",), "L"), "scroll_down": ((), "NEXT"), "scroll_up": ((), "PRIOR"),
    "top": ((), "HOME"), "bottom": ((), "END"), "fullscreen": ((), "F11"), "print": (("CONTROL",), "P"),
    "dev_tools": ((), "F12"), "view_source": (("CONTROL",), "U"),
}
BrowserAction = Literal[tuple(sorted(list(_BROWSER_KEYS) + ["go_to_tab"]))]  # type: ignore[valid-type]

_BROWSER_SAID = {
    "new_tab": "Opened a new tab.", "close_tab": "Closed the tab.", "reopen_tab": "Reopened the last closed tab.",
    "next_tab": "Next tab.", "previous_tab": "Previous tab.", "last_tab": "Went to the last tab.", "back": "Went back.",
    "forward": "Went forward.", "reload": "Reloaded the page.", "hard_reload": "Reloaded the page without cache.",
    "stop_loading": "Stopped loading.", "home": "Went to the home page.", "zoom_in": "Zoomed in.", "zoom_out": "Zoomed out.",
    "zoom_reset": "Zoom reset to 100%.", "bookmark": "Bookmark dialog opened.", "history": "Opened history.",
    "downloads": "Opened downloads.", "new_window": "Opened a new window.", "incognito": "Opened a private window.",
    "close_window": "Closed the browser window.", "find": "Find on page is open.", "address_bar": "Address bar selected.",
    "scroll_down": "Scrolled down.", "scroll_up": "Scrolled up.", "top": "Top of the page.", "bottom": "Bottom of the page.",
    "fullscreen": "Toggled full screen.", "print": "Print dialog opened.", "dev_tools": "Toggled developer tools.",
    "view_source": "Opened the page source.",
}

_PC_KEYS: dict[str, tuple[tuple[str, ...], Any, str]] = {
    "task_manager": (("CONTROL", "SHIFT"), "ESCAPE", "Opened Task Manager."),
    "settings": (("LWIN",), "I", "Opened Settings."),
    "file_explorer": (("LWIN",), "E", "Opened File Explorer."),
    "run_dialog": (("LWIN",), "R", "Opened the Run box."),
    "clipboard_history": (("LWIN",), "V", "Opened clipboard history."),
    "emoji_panel": (("LWIN",), VK_OEM_PERIOD, "Opened the emoji panel."),
    "snip": (("LWIN", "SHIFT"), "S", "Snipping tool is ready - drag to capture."),
    "task_view": (("LWIN",), "TAB", "Opened task view."),
    "new_desktop": (("LWIN", "CONTROL"), "D", "Created a new virtual desktop."),
    "next_desktop": (("LWIN", "CONTROL"), "RIGHT", "Switched to the next desktop."),
    "previous_desktop": (("LWIN", "CONTROL"), "LEFT", "Switched to the previous desktop."),
    "close_desktop": (("LWIN", "CONTROL"), "F4", "Closed this virtual desktop."),
    "project_display": (("LWIN",), "P", "Opened display projection options."),
    "notification_center": (("LWIN",), "N", "Opened the notification centre."),
    "quick_settings": (("LWIN",), "A", "Opened quick settings."),
    "windows_search": (("LWIN",), "S", "Opened Windows search."),
    "quick_link_menu": (("LWIN",), "X", "Opened the quick link menu."),
    "action_center": (("LWIN",), "A", "Opened quick settings."),
}
PCAction = Literal[tuple(sorted(_PC_KEYS))]  # type: ignore[valid-type]

PhoneQuickAction = Literal["quick_settings", "notifications_panel", "collapse_panels", "settings", "brightness",
                           "media_volume", "current_app", "screen_off", "screen_on", "sms_draft"]


def _vk(name: Any) -> int:
    from jarvis.tools.system.input_layer import VK
    return name if isinstance(name, int) else getattr(VK, name)


def _press(mods: tuple[str, ...], key: Any) -> None:
    from jarvis.tools.system.input_layer import send_combo, send_key
    if mods:
        send_combo([_vk(m) for m in mods], _vk(key))
    else:
        send_key(_vk(key))


def _focus_browser() -> Optional[str]:
    """Bring a browser window to the front when another app is focused. Returns the browser's process name."""
    if os.name != "nt":
        return None
    from jarvis.tools.system.input_layer import get_foreground_process_name
    current = (get_foreground_process_name() or "").lower()
    if current in BROWSER_PROCESSES:
        return current
    try:
        import ctypes
        from ctypes import wintypes

        import psutil
        user32 = ctypes.windll.user32
        found: list[tuple[int, str]] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _enum(hwnd, _lparam):  # windows are enumerated top-most (most recently used) first
            if user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                try:
                    name = psutil.Process(pid.value).name().lower()
                except Exception:
                    return True
                if name in BROWSER_PROCESSES:
                    found.append((hwnd, name))
                    return False
            return True
        user32.EnumWindows(_enum, 0)
        if not found:
            return None
        hwnd, name = found[0]
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.12)
        return name
    except Exception as exc:
        logger.debug("Could not focus a browser window: %s", exc)
        return None


class BrowserQuickInput(Contract):
    action: BrowserAction = Field(description="Browser action, e.g. new_tab, close_tab, reopen_tab, next_tab, previous_tab, "
                                              "go_to_tab, back, forward, reload, zoom_in, zoom_out, zoom_reset, bookmark, "
                                              "history, downloads, incognito, find, address_bar, scroll_down, scroll_up, "
                                              "top, bottom, fullscreen")
    tab: Optional[int] = Field(default=None, ge=1, le=9, description="Tab number for go_to_tab (1-8; 9 = last tab)")


class QuickOutput(Contract):
    status: str
    message: str
    action: str = ""


class BrowserQuickActionTool(Tool):
    definition = ToolDefinition(
        name="browser_quick_action",
        description="Instant browser controls in the browser you are using: new/close/reopen tab, next/previous tab, go to "
                    "tab N, back, forward, reload, zoom in/out/reset, bookmark, history, downloads, incognito window, find "
                    "on page, address bar, scroll, top/bottom, full screen.",
        input_model=BrowserQuickInput,
        output_model=QuickOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=5.0,
        tags=("browser", "tab", "navigation", "shortcut", "fast"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = BrowserQuickInput(**arguments)
        if os.name != "nt":
            return {"status": "FAILED", "action": arguments.action, "message": "Browser shortcuts need Windows."}
        browser = _focus_browser()
        if browser is None:
            return {"status": "FAILED", "action": arguments.action,
                    "message": "No browser window is open. Say 'open chrome' first."}
        action = arguments.action
        if action == "go_to_tab":
            n = arguments.tab or 1
            _press(("CONTROL",), f"N{min(n, 9)}")
            msg = "Went to the last tab." if n >= 9 else f"Went to tab {n}."
        else:
            mods, key = _BROWSER_KEYS[action]
            if action == "incognito" and browser == "firefox.exe":
                mods, key = ("CONTROL", "SHIFT"), "P"
            _press(mods, key)
            msg = _BROWSER_SAID.get(action, "Done.")
        return {"status": "SUCCESS", "action": action, "message": msg}


class PCQuickInput(Contract):
    action: PCAction = Field(description="Windows action: task_manager, settings, file_explorer, run_dialog, clipboard_history, "
                                         "emoji_panel, snip, task_view, new_desktop, next_desktop, previous_desktop, "
                                         "close_desktop, project_display, notification_center, quick_settings, windows_search")


class PCQuickActionTool(Tool):
    definition = ToolDefinition(
        name="pc_quick_action",
        description="Instant Windows actions: Task Manager, Settings, File Explorer, Run box, clipboard history, emoji panel, "
                    "snipping (screen clip), task view, new/next/previous/close virtual desktop, project display, "
                    "notification centre, quick settings, Windows search.",
        input_model=PCQuickInput,
        output_model=QuickOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=5.0,
        tags=("windows", "shortcut", "desktop", "fast"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = PCQuickInput(**arguments)
        if os.name != "nt":
            return {"status": "FAILED", "action": arguments.action, "message": "This shortcut needs Windows."}
        mods, key, said = _PC_KEYS[arguments.action]
        _press(mods, key)
        return {"status": "SUCCESS", "action": arguments.action, "message": said}


class PhoneQuickInput(Contract):
    action: PhoneQuickAction = Field(description="quick_settings, notifications_panel, collapse_panels, settings (value = page: "
                                                 "main, wifi, bluetooth, battery, display, sound, location, apps, storage, "
                                                 "hotspot, data_usage), brightness (value 0-100), media_volume (value 0-15), "
                                                 "current_app, screen_off, screen_on, sms_draft (number + text)")
    value: Optional[str] = Field(default=None, max_length=40, description="Settings page, brightness % or volume level")
    number: str = Field(default="", max_length=20, description="Phone number for sms_draft")
    text: str = Field(default="", max_length=300, description="Message for sms_draft (you tap send on the phone)")


class PhoneQuickActionTool(Tool):
    definition = ToolDefinition(
        name="android_quick_action",
        description="Fast phone controls over ADB: quick settings, notification shade, open a settings page (wifi, bluetooth, "
                    "battery, display, sound, location, apps, storage, hotspot), set brightness %, set media volume, which "
                    "app is open, screen on/off, and prepare an SMS for you to send.",
        input_model=PhoneQuickInput,
        output_model=QuickOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=12.0,
        tags=("phone", "android", "adb", "fast"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = PhoneQuickInput(**arguments)
        from jarvis.tools.system.phone_tools import _run
        try:
            value: Any = arguments.value
            if arguments.action in ("brightness", "media_volume") and value is not None:
                value = int(float(str(value).rstrip("%")))
            res = _run("quick", what=arguments.action, value=value, number=arguments.number, text=arguments.text)
        except Exception as exc:
            return {"status": "FAILED", "action": arguments.action, "message": str(exc)}
        return {"status": "SUCCESS" if res["success"] else "FAILED", "action": arguments.action, "message": res["message"]}


def create_quick_action_tools() -> list[Tool]:
    return [BrowserQuickActionTool(), PCQuickActionTool(), PhoneQuickActionTool()]
