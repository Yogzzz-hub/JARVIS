"""Mouse / keyboard control for screen-level automation (any app, not just browsers).

pyautogui does the work on Windows; text outside plain ASCII is pasted through the clipboard so
names and messages in any language type correctly. The backend is injectable for tests.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Optional

logger = logging.getLogger("jarvis.tools.input")

_KEY_ALIASES = {
    "control": "ctrl", "ctl": "ctrl", "return": "enter", "escape": "esc", "windows": "win", "window": "win",
    "cmd": "win", "super": "win", "del": "delete", "pgup": "pageup", "pgdn": "pagedown", "arrowup": "up",
    "arrowdown": "down", "arrowleft": "left", "arrowright": "right", "spacebar": "space",
}

_backend: Any = None


def backend() -> Any:
    global _backend
    if _backend is None:
        try:
            import pyautogui

            pyautogui.FAILSAFE = True   # slam the mouse into a screen corner to abort
            pyautogui.PAUSE = 0.05
            _backend = pyautogui
        except Exception as exc:  # headless / not installed
            raise RuntimeError("Screen control needs pyautogui (pip install -e .[windows]).") from exc
    return _backend


def set_backend(obj: Optional[Any]) -> None:
    global _backend
    _backend = obj


def parse_keys(combo: str) -> list[str]:
    parts = [p.strip().lower() for p in re.split(r"\s*\+\s*|\s+", combo or "") if p.strip()]
    return [_KEY_ALIASES.get(p, p) for p in parts]


def click(x: int, y: int, button: str = "left", double: bool = False) -> None:
    b = backend()
    b.moveTo(int(x), int(y), duration=0.12)
    b.click(int(x), int(y), clicks=2 if double else 1, interval=0.08, button=button)


def type_text(text: str) -> None:
    b = backend()
    if text.isascii():
        b.write(text, interval=0.012)
        return
    try:
        import pyperclip

        previous = pyperclip.paste()
        pyperclip.copy(text)
        b.hotkey("ctrl", "v")
        time.sleep(0.15)
        pyperclip.copy(previous)
    except Exception:
        b.write(text.encode("ascii", "ignore").decode(), interval=0.012)


def press(combo: str) -> None:
    keys = parse_keys(combo)
    if not keys:
        raise ValueError("No keys given")
    b = backend()
    if len(keys) == 1:
        b.press(keys[0])
    else:
        b.hotkey(*keys)


def scroll(amount: int) -> None:
    backend().scroll(int(amount))


def screen_size() -> tuple[int, int]:
    size = backend().size()
    return int(size[0]), int(size[1])
