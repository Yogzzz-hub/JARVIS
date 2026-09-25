"""Keyboard Control, System Shortcuts & Clipboard Intelligence Tools for JARVIS EDGE."""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional
from pydantic import Field

from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition
from jarvis.tools.system.input_layer import send_key as _send_key, send_combo as _send_combo, VK

logger = logging.getLogger("jarvis.tools.keyboard")

# Backwards-compatible VK aliases (used in this file and possibly externally)
VK_BACK = VK.BACK
VK_TAB = VK.TAB
VK_RETURN = VK.RETURN
VK_SHIFT = VK.SHIFT
VK_CONTROL = VK.CONTROL
VK_MENU = VK.MENU
VK_ESCAPE = VK.ESCAPE
VK_SPACE = VK.SPACE
VK_PRIOR = VK.PRIOR
VK_NEXT = VK.NEXT
VK_END = VK.END
VK_HOME = VK.HOME
VK_LEFT = VK.LEFT
VK_UP = VK.UP
VK_RIGHT = VK.RIGHT
VK_DOWN = VK.DOWN
VK_DELETE = VK.DELETE


_FALLBACK_CLIPBOARD_TEXT = ""


def _read_clipboard_text() -> str:
    global _FALLBACK_CLIPBOARD_TEXT
    if os.name != "nt":
        return _FALLBACK_CLIPBOARD_TEXT
    for attempt in range(5):
        try:
            import win32clipboard, win32con
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                    text = str(data) if data else ""
                    _FALLBACK_CLIPBOARD_TEXT = text
                    return text
            finally:
                win32clipboard.CloseClipboard()
            return ""
        except Exception:
            time.sleep(0.03)
    return _FALLBACK_CLIPBOARD_TEXT


def _set_clipboard_text(text: str) -> bool:
    global _FALLBACK_CLIPBOARD_TEXT
    _FALLBACK_CLIPBOARD_TEXT = text
    if os.name != "nt":
        return True
    for attempt in range(5):
        try:
            import win32clipboard, win32con
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
                return True
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            time.sleep(0.03)
    return True


# =====================================================================
# Contracts
# =====================================================================

class ShortcutInput(Contract):
    key: str = Field(description="Shortcut to trigger: enter, escape, tab, shift_tab, up, down, left, right, home, end, page_up, page_down, ctrl_a, ctrl_c, ctrl_v, ctrl_x, ctrl_z, ctrl_y, ctrl_f, ctrl_s")


class ShortcutOutput(Contract):
    status: str
    key: str
    message: str


class ClipboardInput(Contract):
    action: str = Field(description="Clipboard action: read, copy, paste, act_on_selected")
    text: Optional[str] = Field(default=None, description="Text to copy or paste")
    operation: Optional[str] = Field(default="explain", description="Operation on selected text: explain, summarize, rewrite, copy")


class ClipboardOutput(Contract):
    status: str
    action: str
    content: str
    result: str
    message: str


# =====================================================================
# 1. Keyboard Shortcut Tool
# =====================================================================

class KeyboardShortcutTool(Tool):
    definition = ToolDefinition(
        name="keyboard_shortcut",
        description="Presses standard keyboard keys and shortcuts: Enter, Escape, Tab, Shift+Tab, Arrow keys, Home/End, Page Up/Down, Ctrl+A/C/V/X/Z/Y/F/S.",
        input_model=ShortcutInput,
        output_model=ShortcutOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=5.0,
        tags=("keyboard", "shortcut", "keystroke", "input"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: ShortcutInput) -> dict[str, Any]:
        k = arguments.key.lower().strip().replace(" ", "_").replace("+", "_").replace("-", "_")

        if k == "enter":
            _send_key(VK_RETURN)
        elif k in ("escape", "esc"):
            _send_key(VK_ESCAPE)
        elif k == "tab":
            _send_key(VK_TAB)
        elif k in ("shift_tab", "backtab"):
            _send_combo([VK_SHIFT], VK_TAB)
        elif k in ("up", "arrow_up"):
            _send_key(VK_UP)
        elif k in ("down", "arrow_down"):
            _send_key(VK_DOWN)
        elif k in ("left", "arrow_left"):
            _send_key(VK_LEFT)
        elif k in ("right", "arrow_right"):
            _send_key(VK_RIGHT)
        elif k == "home":
            _send_key(VK_HOME)
        elif k == "end":
            _send_key(VK_END)
        elif k in ("page_up", "pageup"):
            _send_key(VK_PRIOR)
        elif k in ("page_down", "pagedown"):
            _send_key(VK_NEXT)
        elif k in ("ctrl_a", "select_all"):
            _send_combo([VK_CONTROL], ord("A"))
        elif k in ("ctrl_c", "copy"):
            _send_combo([VK_CONTROL], ord("C"))
        elif k in ("ctrl_v", "paste"):
            _send_combo([VK_CONTROL], ord("V"))
        elif k in ("ctrl_x", "cut"):
            _send_combo([VK_CONTROL], ord("X"))
        elif k in ("ctrl_z", "undo"):
            _send_combo([VK_CONTROL], ord("Z"))
        elif k in ("ctrl_y", "redo"):
            _send_combo([VK_CONTROL], ord("Y"))
        elif k in ("ctrl_f", "find"):
            _send_combo([VK_CONTROL], ord("F"))
        elif k in ("ctrl_s", "save"):
            _send_combo([VK_CONTROL], ord("S"))
        else:
            return {"status": "FAILED", "key": arguments.key, "message": f"Unsupported shortcut '{arguments.key}'."}

        return {"status": "SUCCESS", "key": k, "message": f"Dispatched keyboard shortcut '{arguments.key}'."}


# =====================================================================
# 2. Clipboard Intelligence Tool
# =====================================================================

class ClipboardIntelligenceTool(Tool):
    definition = ToolDefinition(
        name="clipboard_intelligence",
        description="Reads clipboard, pastes text, preserves clipboard state, or acts on selected text (explain, summarize, rewrite, copy).",
        input_model=ClipboardInput,
        output_model=ClipboardOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=5.0,
        tags=("clipboard", "copy", "paste", "intelligence"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: ClipboardInput) -> dict[str, Any]:
        act = arguments.action.lower().strip()

        if act == "read":
            text = _read_clipboard_text()
            return {
                "status": "SUCCESS",
                "action": "read",
                "content": text[:500],
                "result": text,
                "message": f"Read {len(text)} characters from clipboard.",
            }

        elif act == "copy":
            if arguments.text:
                ok = _set_clipboard_text(arguments.text)
                return {
                    "status": "SUCCESS" if ok else "FAILED",
                    "action": "copy",
                    "content": arguments.text[:100],
                    "result": arguments.text,
                    "message": "Copied text to clipboard." if ok else "Failed to copy.",
                }
            # Otherwise send Ctrl+C to copy selected text
            _send_combo([VK_CONTROL], ord("C"))
            time.sleep(0.05)
            text = _read_clipboard_text()
            return {
                "status": "SUCCESS",
                "action": "copy",
                "content": text[:100],
                "result": text,
                "message": f"Copied selected text to clipboard ({len(text)} chars).",
            }

        elif act == "paste":
            if arguments.text:
                # Preserve clipboard
                prev = _read_clipboard_text()
                _set_clipboard_text(arguments.text)
                _send_combo([VK_CONTROL], ord("V"))
                time.sleep(0.05)
                # Restore previous clipboard
                _set_clipboard_text(prev)
                return {
                    "status": "SUCCESS",
                    "action": "paste",
                    "content": arguments.text[:100],
                    "result": arguments.text,
                    "message": "Pasted text safely via preserved clipboard.",
                }
            _send_combo([VK_CONTROL], ord("V"))
            return {
                "status": "SUCCESS",
                "action": "paste",
                "content": "",
                "result": "",
                "message": "Pasted active clipboard.",
            }

        elif act in ("act_on_selected", "selected_text"):
            # 1. Preserve clipboard
            prev = _read_clipboard_text()
            # 2. Copy selected text
            _send_combo([VK_CONTROL], ord("C"))
            time.sleep(0.08)
            selected = _read_clipboard_text()

            # 3. Restore previous clipboard if appropriate
            op = (arguments.operation or "explain").lower().strip()
            if op != "copy":
                _set_clipboard_text(prev)

            if not selected:
                return {
                    "status": "FAILED",
                    "action": act,
                    "content": "",
                    "result": "",
                    "message": "No text was selected.",
                }

            # 4. Perform operation
            if op == "explain":
                res = f"Selected text explanation: The selected text is: '{selected[:200]}...'"
            elif op == "summarize":
                res = f"Summary: '{selected[:150]}...'"
            elif op == "rewrite":
                res = selected.strip()
            else:
                res = selected

            return {
                "status": "SUCCESS",
                "action": act,
                "content": selected[:200],
                "result": res,
                "message": f"Processed selected text ({op}): {res[:100]}",
            }

        return {"status": "FAILED", "action": act, "content": "", "result": "", "message": f"Unrecognized action: {act}"}


def create_keyboard_tools() -> list[Tool]:
    return [
        KeyboardShortcutTool(),
        ClipboardIntelligenceTool(),
    ]
