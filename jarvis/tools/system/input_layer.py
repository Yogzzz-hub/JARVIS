"""Consolidated Win32 Keyboard & Mouse Input Layer for JARVIS EDGE.

Single source of truth for all low-level input simulation.
Replaces duplicate _send_key / _send_combo / _type_unicode across
dictation.py, ide_tools.py, and keyboard_tools.py.

Usage:
    from jarvis.tools.system.input_layer import send_key, send_combo, type_text, VK
"""
from __future__ import annotations

import ctypes
import logging
import os
import time
from typing import Optional, Sequence

logger = logging.getLogger("jarvis.input_layer")

# =====================================================================
# Win32 Keyboard Virtual-Key Constants
# =====================================================================

class VK:
    """Win32 Virtual-Key code constants."""
    BACK = 0x08
    TAB = 0x09
    RETURN = 0x0D
    SHIFT = 0x10
    CONTROL = 0x11
    MENU = 0x12       # Alt
    PAUSE = 0x13
    CAPITAL = 0x14    # Caps Lock
    ESCAPE = 0x1B
    SPACE = 0x20
    PRIOR = 0x21      # Page Up
    NEXT = 0x22       # Page Down
    END = 0x23
    HOME = 0x24
    LEFT = 0x25
    UP = 0x26
    RIGHT = 0x27
    DOWN = 0x28
    SNAPSHOT = 0x2C   # Print Screen
    INSERT = 0x2D
    DELETE = 0x2E
    LWIN = 0x5B
    RWIN = 0x5C
    F1 = 0x70
    F2 = 0x71
    F3 = 0x72
    F4 = 0x73
    F5 = 0x74
    F6 = 0x75
    F7 = 0x76
    F8 = 0x77
    F9 = 0x78
    F10 = 0x79
    F11 = 0x7A
    F12 = 0x7B
    # Letters (for combos like Ctrl+A)
    A = 0x41; B = 0x42; C = 0x43; D = 0x44; E = 0x45; F = 0x46
    G = 0x47; H = 0x48; I = 0x49; J = 0x4A; K = 0x4B; L = 0x4C
    M = 0x4D; N = 0x4E; O = 0x4F; P = 0x50; Q = 0x51; R = 0x52
    S = 0x53; T = 0x54; U = 0x55; V = 0x56; W = 0x57; X = 0x58
    Y = 0x59; Z = 0x5A
    # Numbers
    N0 = 0x30; N1 = 0x31; N2 = 0x32; N3 = 0x33; N4 = 0x34
    N5 = 0x35; N6 = 0x36; N7 = 0x37; N8 = 0x38; N9 = 0x39


# Win32 flags
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

_user32 = None

def _get_user32():
    """Lazy-load user32 DLL handle."""
    global _user32
    if _user32 is None and os.name == "nt":
        _user32 = ctypes.windll.user32
    return _user32


def _ensure_desktop():
    """Attach current thread to interactive Default desktop if possible."""
    if os.name != "nt":
        return
    try:
        u32 = _get_user32()
        if u32:
            hdesk = u32.OpenDesktopW("Default", 0, False, 0x01FF)
            if hdesk:
                u32.SetThreadDesktop(hdesk)
    except Exception:
        pass


# =====================================================================
# Core Input Functions
# =====================================================================

def send_key(vk: int) -> None:
    """Send a single virtual key press + release.

    Args:
        vk: Virtual-key code from VK class.
    """
    if os.name != "nt":
        return
    try:
        u32 = _get_user32()
        u32.keybd_event(vk, 0, 0, 0)
        u32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    except Exception as e:
        logger.warning("Failed to send key 0x%02X: %s", vk, e)


def send_combo(modifiers: Sequence[int], key: int) -> None:
    """Send a keyboard combination (e.g., Ctrl+C, Ctrl+Shift+S).

    Args:
        modifiers: List of modifier VK codes (e.g., [VK.CONTROL, VK.SHIFT]).
        key: The main key VK code.
    """
    if os.name != "nt":
        return
    try:
        u32 = _get_user32()
        for m in modifiers:
            u32.keybd_event(m, 0, 0, 0)
        u32.keybd_event(key, 0, 0, 0)
        u32.keybd_event(key, 0, KEYEVENTF_KEYUP, 0)
        for m in reversed(modifiers):
            u32.keybd_event(m, 0, KEYEVENTF_KEYUP, 0)
    except Exception as e:
        logger.warning("Failed to send combo %s+0x%02X: %s", modifiers, key, e)


def type_unicode(text: str) -> int:
    """Type text character-by-character using Unicode key events.

    Handles newlines (\\n → VK_RETURN) and tabs (\\t → VK_TAB).
    Returns the number of characters typed.

    Args:
        text: The text to type.

    Returns:
        Number of characters successfully sent.
    """
    if os.name != "nt" or not text:
        return 0
    typed = 0
    try:
        u32 = _get_user32()
        for ch in text:
            if ch == "\n":
                send_key(VK.RETURN)
            elif ch == "\t":
                send_key(VK.TAB)
            else:
                val = ord(ch)
                u32.keybd_event(0, val, KEYEVENTF_UNICODE, 0)
                u32.keybd_event(0, val, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0)
            typed += 1
    except Exception as e:
        logger.warning("Failed to type unicode text (typed %d/%d chars): %s", typed, len(text), e)
    return typed


def type_text(text: str, method: str = "auto") -> tuple[int, str]:
    """Type text using the best available method.

    Args:
        text: Text to type.
        method: 'unicode' for char-by-char, 'clipboard' for Ctrl+V,
                'auto' to choose based on text length.

    Returns:
        Tuple of (characters_typed, method_used).
    """
    if not text:
        return 0, method

    if method == "auto":
        # Use clipboard for large text (>200 chars) — much faster
        method = "clipboard" if len(text) > 200 else "unicode"

    if method == "clipboard":
        return _type_via_clipboard(text), "clipboard"
    else:
        return type_unicode(text), "unicode"


def _type_via_clipboard(text: str) -> int:
    """Type text by temporarily setting clipboard and pressing Ctrl+V.

    Preserves original clipboard contents.
    """
    if os.name != "nt":
        return 0

    original = None
    try:
        import win32clipboard
        # Save original clipboard
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                original = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
        except Exception:
            pass

        # Set text to clipboard
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()

        # Paste
        time.sleep(0.02)  # Clipboard settle
        send_combo([VK.CONTROL], VK.V)
        time.sleep(0.05)  # Paste settle

        # Restore original clipboard
        if original is not None:
            time.sleep(0.05)
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(original, win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
            except Exception:
                pass

        return len(text)
    except ImportError:
        logger.warning("win32clipboard not available, falling back to unicode typing")
        return type_unicode(text)
    except Exception as e:
        logger.warning("Clipboard paste failed: %s, falling back to unicode typing", e)
        return type_unicode(text)


# =====================================================================
# Focus Utilities
# =====================================================================

def get_foreground_hwnd() -> int:
    """Get the handle of the current foreground window.

    Returns:
        Window handle (HWND), or 0 if unavailable.
    """
    if os.name != "nt":
        return 0
    try:
        u32 = _get_user32()
        return u32.GetForegroundWindow() or 0
    except Exception:
        return 0


def get_foreground_process_name() -> str:
    """Get the process name of the current foreground window.

    Returns:
        Process name (e.g., 'notepad.exe'), or '' if unavailable.
    """
    hwnd = get_foreground_hwnd()
    if not hwnd:
        return ""
    try:
        import psutil
        pid = ctypes.c_ulong()
        _get_user32().GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value:
            return psutil.Process(pid.value).name()
    except Exception:
        pass
    return ""


def get_window_title(hwnd: int) -> str:
    """Get the title of a window by handle.

    Args:
        hwnd: Window handle.

    Returns:
        Window title string, or '' if unavailable.
    """
    if os.name != "nt" or not hwnd:
        return ""
    try:
        u32 = _get_user32()
        length = u32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        u32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value.strip()
    except Exception:
        return ""


def verify_focus(expected_hwnd: int) -> bool:
    """Check if the expected window still has foreground focus.

    Args:
        expected_hwnd: The window handle that should be focused.

    Returns:
        True if the expected window is still the foreground window.
    """
    return get_foreground_hwnd() == expected_hwnd and expected_hwnd != 0
