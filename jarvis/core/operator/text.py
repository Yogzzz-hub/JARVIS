"""text.* primitives: insert text and edit it ("delete the last three words", "select this line", "replace Tuesday
with Wednesday", "undo that") through a *named* chord table - never raw scripts or coordinates.

Before every keystroke the target window is checked to still be the one the owner meant (``expect``); if focus has
moved, nothing is typed. When the platform can read the field (UIA value / fake buffer), the effect is verified.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from jarvis.core.operator.platform import Chord, Desktop, get_desktop, parse_chord
from jarvis.core.operator.refs import OperatorOutcome, WindowRef

# Named chords: intent -> key sequence. The whole vocabulary of keyboard actions lives here.
CHORDS: dict[str, tuple[str, ...]] = {
    "select_all": ("ctrl+a",), "copy": ("ctrl+c",), "cut": ("ctrl+x",), "paste": ("ctrl+v",),
    "undo": ("ctrl+z",), "redo": ("ctrl+y",), "save": ("ctrl+s",), "save_as": ("ctrl+shift+s",),
    "find": ("ctrl+f",), "replace_dialog": ("ctrl+h",), "new_line": ("enter",), "new_paragraph": ("enter", "enter"),
    "submit": ("enter",), "tab": ("tab",), "escape": ("escape",), "bold": ("ctrl+b",), "italic": ("ctrl+i",),
    "underline": ("ctrl+u",), "print": ("ctrl+p",), "new_document": ("ctrl+n",), "open_document": ("ctrl+o",),
    "close_tab": ("ctrl+w",), "new_tab": ("ctrl+t",), "reopen_tab": ("ctrl+shift+t",), "next_tab": ("ctrl+tab",),
    "previous_tab": ("ctrl+shift+tab",), "zoom_in": ("ctrl+=",), "zoom_out": ("ctrl+-",), "zoom_reset": ("ctrl+0",),
    "refresh": ("f5",), "hard_refresh": ("ctrl+f5",), "back": ("alt+left",), "forward": ("alt+right",),
    "address_bar": ("ctrl+l",), "page_down": ("pagedown",), "page_up": ("pageup",), "top": ("ctrl+home",),
    "bottom": ("ctrl+end",), "switch_window": ("alt+tab",), "show_desktop": ("win+d",), "lock_screen": ("win+l",),
    "task_view": ("win+tab",), "snip": ("win+shift+s",), "emoji_panel": ("win+.",), "clipboard_history": ("win+v",),
    "file_explorer": ("win+e",), "run_dialog": ("win+r",), "settings": ("win+i",), "close_window": ("alt+f4",),
    "fullscreen": ("f11",), "rename": ("f2",), "properties": ("alt+enter",), "context_menu": ("shift+f10",),
    "delete": ("delete",), "backspace": ("backspace",), "home": ("home",), "end": ("end",),
    "volume_up": ("volumeup",), "volume_down": ("volumedown",), "mute": ("volumemute",),
    "play_pause": ("playpause",), "next_track": ("nexttrack",), "previous_track": ("prevtrack",),
    "stop_media": ("stopmedia",), "indent": ("tab",), "outdent": ("shift+tab",), "comment_line": ("ctrl+/",),
    "command_palette": ("ctrl+shift+p",), "quick_open": ("ctrl+p",), "toggle_terminal": ("ctrl+`",),
    "go_to_line": ("ctrl+g",), "duplicate_tab": ("alt+d", "alt+enter"), "bookmark": ("ctrl+d",),
    "history": ("ctrl+h",), "downloads": ("ctrl+j",), "dev_tools": ("f12",), "private_window": ("ctrl+shift+n",),
}
# Chords that leave the text field or the machine state in a way an "edit" must never trigger implicitly.
NEVER_IMPLICIT = {"lock_screen", "close_window", "run_dialog"}

UNITS = ("char", "word", "line", "sentence", "paragraph", "all")
_UNIT_ALIASES = {"character": "char", "characters": "char", "letter": "char", "letters": "char", "chars": "char",
                 "words": "word", "lines": "line", "sentences": "sentence", "paragraphs": "paragraph",
                 "para": "paragraph", "everything": "all", "text": "all", "whole thing": "all"}


def chord_sequence(name: str) -> list[Chord]:
    keys = CHORDS.get(name)
    if keys is None:
        raise KeyError(name)
    return [parse_chord(k) for k in keys]


def normalize_unit(unit: str) -> str:
    u = (unit or "").lower().strip()
    u = _UNIT_ALIASES.get(u, u)
    return u if u in UNITS else ""


@dataclass
class EditRequest:
    op: str                      # delete | select | replace | capitalize | upper | lower | move | undo | redo
    unit: str = "word"
    n: int = 1
    direction: str = "back"      # back (before the caret) | forward
    find: str = ""
    replace_with: str = ""


class TextOperator:
    def __init__(self, desktop: Optional[Desktop] = None):
        self._desktop = desktop

    @property
    def desktop(self) -> Desktop:
        return self._desktop or get_desktop()

    def _guard(self, expect: Optional[WindowRef]) -> Optional[OperatorOutcome]:
        """Never type into a window the owner didn't mean."""
        if expect is None:
            return None
        fg = self.desktop.foreground()
        if not fg or fg.hwnd != expect.hwnd:
            return OperatorOutcome(False, f"{expect.display_name} isn't in front any more, so I stopped typing.",
                                   needs="target_lost", evidence={"expected": expect.hwnd, "found": fg.hwnd if fg else 0})
        return None

    def press(self, name_or_chord: str, expect: Optional[WindowRef] = None, repeat: int = 1) -> OperatorOutcome:
        bad = self._guard(expect)
        if bad:
            return bad
        try:
            seq = chord_sequence(name_or_chord) if name_or_chord in CHORDS else [parse_chord(name_or_chord)]
        except (KeyError, ValueError) as e:
            return OperatorOutcome(False, f"I don't know the key '{name_or_chord}'.", needs="clarify",
                                   evidence={"error": str(e)})
        for _ in range(max(1, min(repeat, 50))):
            for c in seq:
                self.desktop.press(c)
        return OperatorOutcome(True, f"Pressed {name_or_chord.replace('_', ' ')}.",
                               evidence={"keys": [str(c) for c in seq], "repeat": repeat})

    def insert(self, text: str, expect: Optional[WindowRef] = None) -> OperatorOutcome:
        bad = self._guard(expect)
        if bad:
            return bad
        before = self.desktop.focused_text()
        n = self.desktop.type_text(text)
        after = self.desktop.focused_text()
        verified = None if before is None or after is None else (text in after)
        ok = n > 0 and verified is not False
        return OperatorOutcome(ok, "Typed." if ok else "The text didn't go in.",
                               evidence={"chars": n, "verified": verified})

    def edit(self, req: EditRequest, expect: Optional[WindowRef] = None) -> OperatorOutcome:
        bad = self._guard(expect)
        if bad:
            return bad
        d = self.desktop
        before = d.focused_text()
        if req.op in ("undo", "redo"):
            for _ in range(max(1, req.n)):
                d.press(parse_chord("ctrl+z" if req.op == "undo" else "ctrl+y"))
            return self._result(before, f"{req.op.title()} done.")
        if req.op == "replace":
            return self._replace(req, expect)
        unit = normalize_unit(req.unit) or "word"
        self._select(unit, req.n, req.direction)
        if req.op == "select":
            return OperatorOutcome(True, f"Selected {self._describe(unit, req.n)}.")
        if req.op == "delete":
            d.press(parse_chord("backspace"))
            return self._result(before, f"Deleted {self._describe(unit, req.n)}.")
        if req.op in ("upper", "lower", "capitalize"):
            return self._transform(req.op, before)
        if req.op == "copy":
            d.press(parse_chord("ctrl+c"))
            return OperatorOutcome(True, f"Copied {self._describe(unit, req.n)}.")
        if req.op == "cut":
            d.press(parse_chord("ctrl+x"))
            return self._result(before, f"Cut {self._describe(unit, req.n)}.")
        return OperatorOutcome(False, f"I can't {req.op} text yet.", needs="clarify")

    def _select(self, unit: str, n: int, direction: str) -> None:
        d, n = self.desktop, max(1, min(n, 200))
        back = direction != "forward"
        if unit == "all":
            d.press(parse_chord("ctrl+a"))
        elif unit == "char":
            for _ in range(n):
                d.press(parse_chord("shift+left" if back else "shift+right"))
        elif unit == "word":
            for _ in range(n):
                d.press(parse_chord("ctrl+shift+left" if back else "ctrl+shift+right"))
        elif unit == "line":
            # current line: to line start, then extend over n-1 earlier lines
            d.press(parse_chord("end" if back else "home"))
            d.press(parse_chord("shift+home" if back else "shift+end"))
            for _ in range(n - 1):
                d.press(parse_chord("shift+up" if back else "shift+down"))
                d.press(parse_chord("shift+home" if back else "shift+end"))
        elif unit in ("sentence", "paragraph"):
            text = d.focused_text()
            if text is None:                        # can't read the field: a paragraph is a line block
                d.press(parse_chord("shift+home"))
                return
            caret = self._caret_guess(text)
            start, end = self._span(text, caret, unit, n)
            for _ in range(max(0, end - caret)):     # to the end of the sentence the caret is in
                d.press(parse_chord("right"))
            for _ in range(end - start):
                d.press(parse_chord("shift+left"))

    def _caret_guess(self, text: str) -> int:
        buf = getattr(self.desktop, "buffer", None)
        if callable(buf):
            b = buf()
            if b is not None:
                return b.caret
        return len(text)

    @staticmethod
    def _span(text: str, caret: int, unit: str, n: int) -> tuple[int, int]:
        """(start, end) of the n sentences/paragraphs ending with the one the caret is in."""
        pattern = r"[.!?]+[\"')\]]*(\s+|$)" if unit == "sentence" else r"\n\s*\n"
        cuts = [m.end() for m in re.finditer(pattern, text)]
        starts = [0] + [c for c in cuts if c < len(text)]
        probe = max(0, len(text[:caret].rstrip()) - 1)       # last real character at/before the caret
        idx = max(i for i, st in enumerate(starts) if st <= probe)
        end = next((c for c in cuts if c > probe), len(text))
        start = starts[max(0, idx - (max(1, n) - 1))]
        return start, max(end, caret)

    def _transform(self, op: str, before: Optional[str]) -> OperatorOutcome:
        d = self.desktop
        saved = d.clipboard_text()
        d.press(parse_chord("ctrl+c"))
        sel = d.clipboard_text() or ""
        if not sel:
            return OperatorOutcome(False, "Nothing is selected to change.")
        new = sel.upper() if op == "upper" else sel.lower() if op == "lower" else sel[:1].upper() + sel[1:]
        d.type_text(new)
        if saved is not None:
            d.set_clipboard_text(saved)
        return self._result(before, "Changed the case.")

    def _replace(self, req: EditRequest, expect: Optional[WindowRef]) -> OperatorOutcome:
        """Replace text the owner names. Reads the field when possible, so only the named words change."""
        d = self.desktop
        text = d.focused_text()
        if not req.find:
            return OperatorOutcome(False, "Replace what?", needs="clarify")
        if text is None:
            return OperatorOutcome(False, "I can't read this field to find that text; select it and say 'type ...'.",
                                   needs="clarify")
        hits = [m.start() for m in re.finditer(re.escape(req.find), text, re.I)]
        if not hits:
            return OperatorOutcome(False, f"I don't see '{req.find}' in the text.")
        if len(hits) > 1 and req.n != -1 and req.n <= 1 and req.direction != "all":
            # several: the one nearest before the caret is what people mean by "change X to Y"
            caret = self._caret_guess(text)
            before = [h for h in hits if h < caret]
            hits = [before[-1] if before else hits[0]]
        elif req.direction == "all" or req.n == -1:
            new = re.sub(re.escape(req.find), req.replace_with, text, flags=re.I)
            d.press(parse_chord("ctrl+a"))
            d.type_text(new)
            return self._result(text, f"Replaced every '{req.find}'.")
        start = hits[0]
        caret = self._caret_guess(text)
        # Move the caret to the end of the match, then select it backwards: keys only.
        end = start + len(req.find)
        step = "right" if end > caret else "left"
        for _ in range(abs(end - caret)):
            d.press(parse_chord(step))
        for _ in range(len(req.find)):
            d.press(parse_chord("shift+left"))
        d.type_text(req.replace_with)
        return self._result(text, f"Replaced '{req.find}' with '{req.replace_with}'.")

    def _result(self, before: Optional[str], message: str) -> OperatorOutcome:
        after = self.desktop.focused_text()
        if before is None or after is None:
            return OperatorOutcome(True, message, evidence={"verified": None})
        ok = after != before
        return OperatorOutcome(ok, message if ok else "Nothing changed.", evidence={"verified": ok})

    @staticmethod
    def _describe(unit: str, n: int) -> str:
        if unit == "all":
            return "everything"
        return f"the last {n} {unit}s" if n > 1 else f"the last {unit}"
