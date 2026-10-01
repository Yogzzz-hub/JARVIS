"""The one place that touches the operating system.

Primitives talk to a ``Desktop``: list/focus/arrange windows, press a *named* chord, type text, read and write the
clipboard, capture the screen. ``Win32Desktop`` does it with ctypes on Windows; ``FakeDesktop`` is a faithful
in-memory model (windows, focus history, a text buffer with caret/selection/undo, clipboard) so every primitive and
verifier runs in tests exactly as it runs live.

Nothing here accepts raw coordinates from a model, a raw script, or an arbitrary key string: chords are parsed
against a fixed key table and rejected if unknown.
"""
from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from jarvis.core.operator.refs import WindowRef

logger = logging.getLogger("jarvis.operator.platform")

MODIFIERS = ("ctrl", "shift", "alt", "win")
_KEY_ALIASES = {
    "control": "ctrl", "cmd": "ctrl", "option": "alt", "windows": "win", "super": "win", "return": "enter",
    "esc": "escape", "del": "delete", "bksp": "backspace", "back": "backspace", "pgup": "pageup",
    "page_up": "pageup", "pgdn": "pagedown", "page_down": "pagedown", "arrowleft": "left", "arrowright": "right",
    "arrowup": "up", "arrowdown": "down", "spacebar": "space", "prtsc": "printscreen", "ins": "insert",
}
# Virtual-key codes for the keys a chord may name. Anything else is refused.
VK_CODES: dict[str, int] = {
    "backspace": 0x08, "tab": 0x09, "enter": 0x0D, "escape": 0x1B, "space": 0x20, "pageup": 0x21,
    "pagedown": 0x22, "end": 0x23, "home": 0x24, "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "printscreen": 0x2C, "insert": 0x2D, "delete": 0x2E, "ctrl": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B,
    "volumeup": 0xAF, "volumedown": 0xAE, "volumemute": 0xAD, "playpause": 0xB3, "nexttrack": 0xB0,
    "prevtrack": 0xB1, "stopmedia": 0xB2, "browserback": 0xA6, "browserforward": 0xA7, "browserrefresh": 0xA8,
    "contextmenu": 0x5D, "capslock": 0x14,
    ",": 0xBC, ".": 0xBE, "/": 0xBF, ";": 0xBA, "'": 0xDE, "[": 0xDB, "]": 0xDD, "\\": 0xDC, "-": 0xBD, "=": 0xBB,
    "`": 0xC0, "+": 0xBB,
}
VK_CODES.update({chr(c).lower(): c for c in range(0x41, 0x5B)})
VK_CODES.update({str(d): 0x30 + d for d in range(10)})
VK_CODES.update({f"f{n}": 0x6F + n for n in range(1, 25)})


@dataclass(frozen=True)
class Chord:
    modifiers: tuple[str, ...]
    key: str

    def __str__(self) -> str:
        return "+".join((*self.modifiers, self.key))


def parse_chord(text: str) -> Chord:
    """'Ctrl+Shift+T' -> Chord(('ctrl','shift'), 't'). Raises ValueError for anything not in the key table."""
    parts = [p.strip().lower() for p in re.split(r"\s*\+\s*", (text or "").strip()) if p.strip()]
    if not parts and (text or "").strip() == "+":
        parts = ["+"]
    if not parts:
        raise ValueError("empty chord")
    parts = [_KEY_ALIASES.get(p, p) for p in parts]
    *mods, key = parts
    for m in mods:
        if m not in MODIFIERS:
            raise ValueError(f"unknown modifier {m!r}")
    if key not in VK_CODES:
        raise ValueError(f"unknown key {key!r}")
    order = {m: i for i, m in enumerate(MODIFIERS)}
    return Chord(tuple(sorted(set(mods), key=order.get)), key)


@dataclass
class Monitor:
    index: int
    left: int
    top: int
    right: int
    bottom: int
    primary: bool = False

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


class Desktop:
    """Operating-system surface the primitives use."""

    name = "abstract"

    def list_windows(self) -> list[WindowRef]: raise NotImplementedError
    def foreground(self) -> Optional[WindowRef]: raise NotImplementedError
    def focus(self, hwnd: int) -> bool: raise NotImplementedError
    def window_state(self, hwnd: int) -> str: raise NotImplementedError       # normal | minimized | maximized
    def set_window_state(self, hwnd: int, state: str) -> bool: raise NotImplementedError
    def close_window(self, hwnd: int) -> bool: raise NotImplementedError
    def window_rect(self, hwnd: int) -> tuple[int, int, int, int]: raise NotImplementedError
    def move_window(self, hwnd: int, rect: tuple[int, int, int, int]) -> bool: raise NotImplementedError
    def monitors(self) -> list[Monitor]: raise NotImplementedError
    def press(self, chord: Chord) -> None: raise NotImplementedError
    def type_text(self, text: str) -> int: raise NotImplementedError
    def clipboard_text(self) -> Optional[str]: raise NotImplementedError
    def set_clipboard_text(self, text: str) -> bool: raise NotImplementedError
    def clipboard_files(self) -> list[str]: return []
    def set_clipboard_image(self, path: str) -> bool: return False
    def set_clipboard_files(self, paths: list[str]) -> bool: return False
    def clipboard_has_image(self) -> bool: return False
    def capture(self, path: str, hwnd: int = 0) -> tuple[int, int]: raise NotImplementedError
    def focused_text(self) -> Optional[str]:
        """Text of the focused editable control when the platform can read it (UIA value), else None."""
        return None

    def wait_until(self, predicate: Callable[[], bool], timeout: float = 2.0, interval: float = 0.03) -> bool:
        """Wait on observable state, never a fixed sleep: returns as soon as the predicate holds."""
        deadline = time.monotonic() + timeout
        while True:
            try:
                if predicate():
                    return True
            except Exception:
                pass
            if time.monotonic() >= deadline:
                return False
            time.sleep(interval)


# ---------------------------------------------------------------------------------------------------------------
# Fake desktop (tests, benchmarks, CI)
# ---------------------------------------------------------------------------------------------------------------

@dataclass
class TextBuffer:
    """An editable text box: caret, selection anchor and an undo stack, edited only through chords and typing."""
    text: str = ""
    caret: int = 0
    anchor: Optional[int] = None
    undo: list[tuple[str, int]] = field(default_factory=list)
    redo: list[tuple[str, int]] = field(default_factory=list)

    def selection(self) -> tuple[int, int]:
        if self.anchor is None or self.anchor == self.caret:
            return self.caret, self.caret
        return min(self.anchor, self.caret), max(self.anchor, self.caret)

    def selected(self) -> str:
        a, b = self.selection()
        return self.text[a:b]

    def _snapshot(self):
        self.undo.append((self.text, self.caret))
        self.redo.clear()

    def replace_selection(self, s: str) -> None:
        self._snapshot()
        a, b = self.selection()
        self.text = self.text[:a] + s + self.text[b:]
        self.caret, self.anchor = a + len(s), None

    def _word_left(self, i: int) -> int:
        while i > 0 and self.text[i - 1].isspace():
            i -= 1
        while i > 0 and not self.text[i - 1].isspace():
            i -= 1
        return i

    def _word_right(self, i: int) -> int:
        n = len(self.text)
        while i < n and not self.text[i].isspace():
            i += 1
        while i < n and self.text[i].isspace():
            i += 1
        return i

    def _line_start(self, i: int) -> int:
        return self.text.rfind("\n", 0, i) + 1

    def _line_end(self, i: int) -> int:
        j = self.text.find("\n", i)
        return len(self.text) if j < 0 else j

    def key(self, chord: Chord) -> Optional[str]:
        """Apply one chord. Returns a clipboard action ('copy'/'cut'/'paste') for the desktop to finish."""
        m, k = set(chord.modifiers), chord.key
        shift, ctrl = "shift" in m, "ctrl" in m
        if ctrl and k == "a":
            self.anchor, self.caret = 0, len(self.text)
            return None
        if ctrl and k in ("c", "x", "v"):
            return {"c": "copy", "x": "cut", "v": "paste"}[k]
        if ctrl and k == "z":
            if self.undo:
                self.redo.append((self.text, self.caret))
                self.text, self.caret = self.undo.pop()
                self.anchor = None
            return None
        if ctrl and k == "y" or ctrl and shift and k == "z":
            if self.redo:
                self.undo.append((self.text, self.caret))
                self.text, self.caret = self.redo.pop()
                self.anchor = None
            return None
        moves = {
            "left": (lambda i: self._word_left(i)) if ctrl else (lambda i: max(0, i - 1)),
            "right": (lambda i: self._word_right(i)) if ctrl else (lambda i: min(len(self.text), i + 1)),
            "home": (lambda i: 0) if ctrl else self._line_start,
            "end": (lambda i: len(self.text)) if ctrl else self._line_end,
            "up": lambda i: max(0, self._line_start(i) - 1) if self._line_start(i) else 0,
            "down": lambda i: min(len(self.text), self._line_end(i) + 1),
        }
        if k in moves:
            target = moves[k](self.caret)
            if shift:
                if self.anchor is None:
                    self.anchor = self.caret
            else:
                if self.anchor is not None and self.anchor != self.caret and k in ("left", "right") and not ctrl:
                    a, b = self.selection()
                    target = a if k == "left" else b
                self.anchor = None
            self.caret = target
            return None
        if k in ("backspace", "delete"):
            a, b = self.selection()
            if a == b:
                if k == "backspace":
                    a = self._word_left(self.caret) if ctrl else max(0, self.caret - 1)
                    b = self.caret
                else:
                    a, b = self.caret, (self._word_right(self.caret) if ctrl else min(len(self.text), self.caret + 1))
            self.anchor, self.caret = a, b
            if a != b:
                self.replace_selection("")
            else:
                self.anchor = None
            return None
        if k == "enter" and not m - {"shift"}:
            self.replace_selection("\n")
            return None
        if k == "tab" and not m:
            self.replace_selection("\t")
            return None
        return None


@dataclass
class FakeWindow:
    hwnd: int
    process: str
    title: str
    state: str = "normal"
    rect: tuple[int, int, int, int] = (100, 100, 900, 700)
    buffer: Optional[TextBuffer] = None
    pid: int = 0
    keys: list[str] = field(default_factory=list)


class FakeDesktop(Desktop):
    """In-memory desktop. Windows with an editable buffer behave like a text box; every chord is logged."""

    name = "fake"

    def __init__(self, monitors: Optional[list[Monitor]] = None):
        self._windows: dict[int, FakeWindow] = {}
        self._z: list[int] = []                      # z-order, front last
        self._next = 1000
        self.clipboard: object = ""
        self.keys: list[tuple[int, str]] = []        # (hwnd, chord) log
        self.typed: list[tuple[int, str]] = []
        self.captures: list[tuple[str, int]] = []
        self._monitors = monitors or [Monitor(0, 0, 0, 1920, 1040, primary=True)]
        self.on_key: Optional[Callable[[int, Chord], None]] = None     # adapters (fake browser/IDE) hook keys here

    # -- setup -----------------------------------------------------------------------------------------------
    def open(self, process: str, title: str, editable: bool = False, text: str = "", focus: bool = True) -> int:
        self._next += 1
        hwnd = self._next
        buf = TextBuffer(text=text, caret=len(text)) if editable else None
        self._windows[hwnd] = FakeWindow(hwnd, process, title, buffer=buf, pid=hwnd * 4)
        self._z.append(hwnd)
        if not focus and len(self._z) > 1:
            self._z.insert(0, self._z.pop())
        return hwnd

    def window(self, hwnd: int) -> FakeWindow:
        return self._windows[hwnd]

    def buffer(self, hwnd: Optional[int] = None) -> Optional[TextBuffer]:
        w = self._windows.get(hwnd or (self._z[-1] if self._z else 0))
        return w.buffer if w else None

    def _ref(self, w: FakeWindow) -> WindowRef:
        return WindowRef(resource_id=f"win:{w.hwnd}", resource_type="WINDOW", display_name="",
                         canonical_identifier="", hwnd=w.hwnd, process=w.process, title=w.title, pid=w.pid)

    # -- Desktop ---------------------------------------------------------------------------------------------
    def list_windows(self) -> list[WindowRef]:
        return [self._ref(self._windows[h]) for h in reversed(self._z)]

    def foreground(self) -> Optional[WindowRef]:
        for h in reversed(self._z):
            w = self._windows[h]
            if w.state != "minimized":
                return self._ref(w)
        return None

    def focus(self, hwnd: int) -> bool:
        if hwnd not in self._windows:
            return False
        w = self._windows[hwnd]
        if w.state == "minimized":
            w.state = "normal"
        self._z.remove(hwnd)
        self._z.append(hwnd)
        return True

    def window_state(self, hwnd: int) -> str:
        return self._windows[hwnd].state if hwnd in self._windows else ""

    def set_window_state(self, hwnd: int, state: str) -> bool:
        if hwnd not in self._windows:
            return False
        w = self._windows[hwnd]
        w.state = {"restore": "normal", "fullscreen": "fullscreen"}.get(state, state)
        if state == "minimized":
            self._z.remove(hwnd)
            self._z.insert(0, hwnd)
        elif state in ("maximized", "normal", "restore", "fullscreen"):
            self.focus(hwnd)
        return True

    def close_window(self, hwnd: int) -> bool:
        if hwnd not in self._windows:
            return False
        self._windows.pop(hwnd)
        self._z.remove(hwnd)
        return True

    def window_rect(self, hwnd: int) -> tuple[int, int, int, int]:
        return self._windows[hwnd].rect

    def move_window(self, hwnd: int, rect: tuple[int, int, int, int]) -> bool:
        if hwnd not in self._windows:
            return False
        self._windows[hwnd].rect = tuple(rect)
        self._windows[hwnd].state = "normal"
        return True

    def monitors(self) -> list[Monitor]:
        return list(self._monitors)

    def press(self, chord: Chord) -> None:
        fg = self.foreground()
        hwnd = fg.hwnd if fg else 0
        self.keys.append((hwnd, str(chord)))
        if hwnd:
            self._windows[hwnd].keys.append(str(chord))
        if self.on_key:
            self.on_key(hwnd, chord)
        buf = self.buffer(hwnd) if hwnd else None
        if buf is None:
            return
        action = buf.key(chord)
        if action in ("copy", "cut"):
            if buf.selected():
                self.clipboard = buf.selected()
                if action == "cut":
                    buf.replace_selection("")
        elif action == "paste" and isinstance(self.clipboard, str):
            buf.replace_selection(self.clipboard)

    def type_text(self, text: str) -> int:
        fg = self.foreground()
        if not fg:
            return 0
        self.typed.append((fg.hwnd, text))
        buf = self.buffer(fg.hwnd)
        if buf is not None:
            buf.replace_selection(text)
        return len(text)

    def clipboard_text(self) -> Optional[str]:
        return self.clipboard if isinstance(self.clipboard, str) else None

    def set_clipboard_text(self, text: str) -> bool:
        self.clipboard = text
        return True

    def clipboard_files(self) -> list[str]:
        return list(self.clipboard) if isinstance(self.clipboard, list) else []

    def set_clipboard_image(self, path: str) -> bool:
        self.clipboard = ("image", path)
        return True

    def clipboard_has_image(self) -> bool:
        return isinstance(self.clipboard, tuple) and self.clipboard[:1] == ("image",)

    def set_clipboard_files(self, paths: list[str]) -> bool:
        self.clipboard = list(paths)
        return True

    def capture(self, path: str, hwnd: int = 0) -> tuple[int, int]:
        self.captures.append((path, hwnd))
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n" + f"fake:{hwnd}".encode())
        except OSError:
            pass
        if hwnd and hwnd in self._windows:
            l, t, r, b = self._windows[hwnd].rect
            return r - l, b - t
        m = self._monitors[0]
        return m.width, m.height

    def focused_text(self) -> Optional[str]:
        buf = self.buffer()
        return buf.text if buf is not None else None

    def wait_until(self, predicate, timeout: float = 2.0, interval: float = 0.0) -> bool:
        # The fake world changes synchronously, so a wait is a single observation.
        try:
            return bool(predicate())
        except Exception:
            return False


# ---------------------------------------------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------------------------------------------

class Win32Desktop(Desktop):
    """ctypes implementation. Loaded lazily; every call degrades to a no-op/False off Windows."""

    name = "win32"
    _SKIP_CLASSES = {"Progman", "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "MSCTFIME UI", "IME",
                     "Windows.UI.Core.CoreWindow", "WorkerW", "Button", "tooltips_class32"}

    def __init__(self):
        import ctypes
        import ctypes.wintypes
        self._ct = ctypes
        self._wt = ctypes.wintypes
        self.u32 = ctypes.windll.user32 if os.name == "nt" else None

    # -- helpers ---------------------------------------------------------------------------------------------
    def _attach_desktop(self):
        try:
            h = self.u32.OpenDesktopW("Default", 0, False, 0x01FF)
            if h:
                self.u32.SetThreadDesktop(h)
        except Exception:
            pass

    def _title(self, hwnd: int) -> str:
        n = self.u32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return ""
        buf = self._ct.create_unicode_buffer(n + 1)
        self.u32.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value.strip()

    def _class(self, hwnd: int) -> str:
        buf = self._ct.create_unicode_buffer(256)
        self.u32.GetClassNameW(hwnd, buf, 256)
        return buf.value

    def _pid_proc(self, hwnd: int) -> tuple[int, str]:
        pid = self._ct.c_ulong()
        self.u32.GetWindowThreadProcessId(hwnd, self._ct.byref(pid))
        name = ""
        try:
            import psutil
            name = psutil.Process(pid.value).name().lower()
        except Exception:
            pass
        return pid.value, name

    def _ref(self, hwnd: int) -> Optional[WindowRef]:
        if not hwnd:
            return None
        pid, proc = self._pid_proc(hwnd)
        return WindowRef(resource_id=f"win:{hwnd}", resource_type="WINDOW", display_name="", canonical_identifier="",
                         hwnd=hwnd, process=proc, title=self._title(hwnd), pid=pid)

    # -- Desktop ---------------------------------------------------------------------------------------------
    def list_windows(self) -> list[WindowRef]:
        if not self.u32:
            return []
        self._attach_desktop()
        out: list[WindowRef] = []
        GW_OWNER, GWL_EXSTYLE, WS_EX_TOOLWINDOW = 4, -20, 0x00000080
        proto = self._ct.WINFUNCTYPE(self._ct.c_bool, self._wt.HWND, self._wt.LPARAM)

        def cb(hwnd, _):
            try:
                if not self.u32.IsWindowVisible(hwnd) or self.u32.GetWindow(hwnd, GW_OWNER):
                    return True
                if self.u32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
                    return True
                if self._class(hwnd) in self._SKIP_CLASSES or not self._title(hwnd):
                    return True
                ref = self._ref(hwnd)
                if ref:
                    out.append(ref)
            except Exception:
                pass
            return True

        self.u32.EnumWindows(proto(cb), 0)      # EnumWindows walks top-to-bottom z-order: front first
        return out

    def foreground(self) -> Optional[WindowRef]:
        if not self.u32:
            return None
        self._attach_desktop()
        return self._ref(self.u32.GetForegroundWindow())

    def focus(self, hwnd: int) -> bool:
        if not self.u32 or not hwnd or not self.u32.IsWindow(hwnd):
            return False
        self._attach_desktop()
        if self.u32.IsIconic(hwnd):
            self.u32.ShowWindow(hwnd, 9)                       # SW_RESTORE
        fg = self.u32.GetForegroundWindow()
        cur = self._ct.windll.kernel32.GetCurrentThreadId()
        fg_thread = self.u32.GetWindowThreadProcessId(fg, None) if fg else 0
        attached = False
        try:
            if fg_thread and fg_thread != cur:
                attached = bool(self.u32.AttachThreadInput(cur, fg_thread, True))
            # A lone Alt tap lifts Windows' foreground lock for this process (no visible effect).
            self.u32.keybd_event(0x12, 0, 0, 0)
            self.u32.keybd_event(0x12, 0, 2, 0)
            self.u32.BringWindowToTop(hwnd)
            self.u32.SetForegroundWindow(hwnd)
        finally:
            if attached:
                self.u32.AttachThreadInput(cur, fg_thread, False)
        return self.wait_until(lambda: self.u32.GetForegroundWindow() == hwnd, timeout=1.0)

    def window_state(self, hwnd: int) -> str:
        if not self.u32 or not hwnd:
            return ""
        if self.u32.IsIconic(hwnd):
            return "minimized"
        if self.u32.IsZoomed(hwnd):
            return "maximized"
        return "normal"

    def set_window_state(self, hwnd: int, state: str) -> bool:
        if not self.u32 or not hwnd:
            return False
        if state == "fullscreen":
            self.focus(hwnd)
            self.press(parse_chord("f11"))
            return True
        cmd = {"maximized": 3, "minimized": 6, "normal": 9, "restore": 9}.get(state)
        if cmd is None:
            return False
        self.u32.ShowWindow(hwnd, cmd)
        want = "normal" if state == "restore" else state
        return self.wait_until(lambda: self.window_state(hwnd) == want, timeout=1.0)

    def close_window(self, hwnd: int) -> bool:
        if not self.u32 or not hwnd:
            return False
        self.u32.PostMessageW(hwnd, 0x0010, 0, 0)               # WM_CLOSE: the app may still ask to save
        return True

    def window_rect(self, hwnd: int) -> tuple[int, int, int, int]:
        r = self._wt.RECT()
        if self.u32 and self.u32.GetWindowRect(hwnd, self._ct.byref(r)):
            return r.left, r.top, r.right, r.bottom
        return 0, 0, 0, 0

    def move_window(self, hwnd: int, rect: tuple[int, int, int, int]) -> bool:
        if not self.u32 or not hwnd:
            return False
        l, t, r, b = rect
        self.u32.ShowWindow(hwnd, 9)
        return bool(self.u32.MoveWindow(hwnd, l, t, r - l, b - t, True))

    def monitors(self) -> list[Monitor]:
        if not self.u32:
            return [Monitor(0, 0, 0, 1920, 1040, primary=True)]
        found: list[Monitor] = []

        class MONITORINFO(self._ct.Structure):
            _fields_ = [("cbSize", self._wt.DWORD), ("rcMonitor", self._wt.RECT), ("rcWork", self._wt.RECT),
                        ("dwFlags", self._wt.DWORD)]

        proto = self._ct.WINFUNCTYPE(self._ct.c_int, self._wt.HMONITOR, self._wt.HDC,
                                     self._ct.POINTER(self._wt.RECT), self._wt.LPARAM)

        def cb(hmon, _hdc, _rect, _lp):
            mi = MONITORINFO()
            mi.cbSize = self._ct.sizeof(MONITORINFO)
            if self.u32.GetMonitorInfoW(hmon, self._ct.byref(mi)):
                w = mi.rcWork
                found.append(Monitor(len(found), w.left, w.top, w.right, w.bottom, primary=bool(mi.dwFlags & 1)))
            return 1

        self.u32.EnumDisplayMonitors(0, 0, proto(cb), 0)
        return found or [Monitor(0, 0, 0, 1920, 1040, primary=True)]

    def press(self, chord: Chord) -> None:
        if not self.u32:
            return
        self._attach_desktop()
        ext = {"left", "right", "up", "down", "home", "end", "pageup", "pagedown", "insert", "delete"}
        down = [VK_CODES[m] for m in chord.modifiers] + [VK_CODES[chord.key]]
        for vk in down:
            self.u32.keybd_event(vk, 0, 0x1 if chord.key in ext and vk == down[-1] else 0, 0)
        for vk in reversed(down):
            self.u32.keybd_event(vk, 0, (0x1 if chord.key in ext and vk == down[-1] else 0) | 0x2, 0)

    def type_text(self, text: str) -> int:
        from jarvis.tools.system.input_layer import type_text
        n, _ = type_text(text)
        return n

    def clipboard_text(self) -> Optional[str]:
        try:
            import win32clipboard as wc
            wc.OpenClipboard()
            try:
                if wc.IsClipboardFormatAvailable(wc.CF_UNICODETEXT):
                    return wc.GetClipboardData(wc.CF_UNICODETEXT)
            finally:
                wc.CloseClipboard()
        except Exception:
            pass
        return None

    def set_clipboard_text(self, text: str) -> bool:
        try:
            import win32clipboard as wc
            wc.OpenClipboard()
            try:
                wc.EmptyClipboard()
                wc.SetClipboardText(text, wc.CF_UNICODETEXT)
            finally:
                wc.CloseClipboard()
            return True
        except Exception:
            return False

    def clipboard_files(self) -> list[str]:
        try:
            import win32clipboard as wc
            wc.OpenClipboard()
            try:
                if wc.IsClipboardFormatAvailable(wc.CF_HDROP):
                    return list(wc.GetClipboardData(wc.CF_HDROP))
            finally:
                wc.CloseClipboard()
        except Exception:
            pass
        return []

    def clipboard_has_image(self) -> bool:
        try:
            import win32clipboard as wc
            wc.OpenClipboard()
            try:
                return bool(wc.IsClipboardFormatAvailable(wc.CF_DIB))
            finally:
                wc.CloseClipboard()
        except Exception:
            return False

    def set_clipboard_image(self, path: str) -> bool:
        try:
            import io
            import win32clipboard as wc
            from PIL import Image
            out = io.BytesIO()
            Image.open(path).convert("RGB").save(out, "BMP")
            data = out.getvalue()[14:]                         # drop the BMP file header: CF_DIB wants the DIB
            wc.OpenClipboard()
            try:
                wc.EmptyClipboard()
                wc.SetClipboardData(wc.CF_DIB, data)
            finally:
                wc.CloseClipboard()
            return True
        except Exception as e:
            logger.debug("image to clipboard failed: %s", e)
            return False

    def set_clipboard_files(self, paths: list[str]) -> bool:
        """CF_HDROP: what Explorer puts there on Ctrl+C - chat apps and IDEs accept it as an attachment paste."""
        try:
            import struct
            import win32clipboard as wc
            body = ("\0".join(os.path.abspath(p) for p in paths) + "\0\0").encode("utf-16-le")
            header = struct.pack("IiiII", 20, 0, 0, 0, 1)          # DROPFILES: offset 20, wide chars
            wc.OpenClipboard()
            try:
                wc.EmptyClipboard()
                wc.SetClipboardData(wc.CF_HDROP, header + body)
            finally:
                wc.CloseClipboard()
            return True
        except Exception as e:
            logger.debug("files to clipboard failed: %s", e)
            return False

    def capture(self, path: str, hwnd: int = 0) -> tuple[int, int]:
        from PIL import ImageGrab
        self._attach_desktop()
        bbox = None
        if hwnd:
            l, t, r, b = self.window_rect(hwnd)
            if r > l and b > t:
                bbox = (l, t, r, b)
        img = ImageGrab.grab(bbox=bbox, all_screens=bbox is None)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        img.save(path)
        return img.size

    def focused_text(self) -> Optional[str]:
        try:
            import uiautomation as auto
            ctrl = auto.GetFocusedControl()
            vp = ctrl.GetValuePattern() if ctrl else None
            return vp.Value if vp else None
        except Exception:
            return None


_desktop: Optional[Desktop] = None


def get_desktop() -> Desktop:
    global _desktop
    if _desktop is None:
        _desktop = Win32Desktop() if os.name == "nt" else FakeDesktop()
    return _desktop


def set_desktop(desktop: Optional[Desktop]) -> None:
    """Tests install a FakeDesktop; ``None`` resets to the platform default."""
    global _desktop
    _desktop = desktop
