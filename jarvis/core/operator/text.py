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

    # -- caret, counting, finding, append/prepend, clear, save / save as, plain paste, templates -------------

    def caret(self, unit: str = "word", direction: str = "left", n: int = 1,
               expect: Optional[WindowRef] = None) -> OperatorOutcome:
        bad = self._guard(expect)
        if bad:
            return bad
        unit = normalize_unit(unit) or unit
        d = self.desktop
        if unit in ("document", "doc", "all", "text") or direction in ("start", "end", "top", "bottom", "beginning"):
            start = direction in ("start", "top", "beginning", "left", "up")
            d.press(parse_chord("ctrl+home" if start else "ctrl+end"))
            return OperatorOutcome(True, f"Cursor at the {'start' if start else 'end'} of the document.")
        if unit == "line" and direction in ("left", "right"):
            d.press(parse_chord("home" if direction == "left" else "end"))
            return OperatorOutcome(True, f"Cursor at the {'start' if direction == 'left' else 'end'} of the line.")
        key = {"left": "left", "right": "right", "up": "up", "down": "down", "back": "left", "forward": "right"}.get(direction, "left")
        chord = ("ctrl+" + key) if unit == "word" and key in ("left", "right") else key
        for _ in range(max(1, min(n, 200))):
            d.press(parse_chord(chord))
        return OperatorOutcome(True, f"Moved the cursor {n} {unit}{'s' if n > 1 else ''} {key}.")


    def count(self) -> OperatorOutcome:
        text = self.desktop.focused_text()
        if text is None:
            return OperatorOutcome(False, "I can't read this field to count it.", needs="vision")
        words = len(re.findall(r"\b[\w'-]+\b", text))
        return OperatorOutcome(True, f"{words} word{'s' if words != 1 else ''}, {len(text)} characters.",
                               evidence={"words": words, "chars": len(text), "untrusted": True})


    def find_text(self, query: str, expect: Optional[WindowRef] = None) -> OperatorOutcome:
        bad = self._guard(expect)
        if bad:
            return bad
        d = self.desktop
        text = d.focused_text()
        if text is None:
            d.press(parse_chord("ctrl+f"))
            d.type_text(query)
            return OperatorOutcome(True, f"Searching for '{query}' with the app's Find.", evidence={"verified": None})
        hits = [m.start() for m in re.finditer(re.escape(query), text, re.I)]
        if not hits:
            return OperatorOutcome(False, f"'{query}' isn't in this text.")
        caret = self._caret_guess(text)
        start = hits[0]
        end = start + len(query)
        step = "right" if end > caret else "left"
        for _ in range(abs(end - caret)):
            d.press(parse_chord(step))
        for _ in range(len(query)):
            d.press(parse_chord("shift+left"))
        return OperatorOutcome(True, f"Found '{query}'" + (f" ({len(hits)} times; selected the first)." if len(hits) > 1 else
                                                         " and selected it."), evidence={"count": len(hits)})


    def append(self, text: str, where: str = "end", expect: Optional[WindowRef] = None) -> OperatorOutcome:
        bad = self._guard(expect)
        if bad:
            return bad
        d = self.desktop
        before = d.focused_text()
        d.press(parse_chord("ctrl+end" if where == "end" else "ctrl+home"))
        payload = text
        if where == "end" and before and not before.endswith(("\n", " ")):
            payload = " " + text
        if where != "end":
            payload = text + "\n"
        d.type_text(payload)
        return self._result(before, f"Added it at the {'end' if where == 'end' else 'top'}.")


    def clear(self, expect: Optional[WindowRef] = None) -> OperatorOutcome:
        bad = self._guard(expect)
        if bad:
            return bad
        d = self.desktop
        before = d.focused_text()
        d.press(parse_chord("ctrl+a"))
        d.press(parse_chord("delete"))
        after = d.focused_text()
        if after is None:
            return OperatorOutcome(True, "Cleared the field.", evidence={"verified": None})
        return OperatorOutcome(after == "", "Cleared the field." if after == "" else "The field still has text.",
                               evidence={"verified": after == "", "had": len(before or "")})


    def save(self, name: str = "", expect: Optional[WindowRef] = None) -> OperatorOutcome:
        """Ctrl+S (or Save As with a name). Verified by the window title: the name appears / the unsaved marker goes."""
        bad = self._guard(expect)
        if bad:
            return bad
        d = self.desktop
        win = d.foreground()
        if not name:
            d.press(parse_chord("ctrl+s"))
            ok = d.wait_until(lambda: not (d.foreground() or win).title.startswith("*") and "●" not in (d.foreground() or win).title,
                              timeout=2.0)
            return OperatorOutcome(True, "Saved." if ok else "Pressed save (I can't see a saved marker to confirm).",
                                   evidence={"verified": ok if win and ("*" in win.title or "●" in win.title) else None})
        if re.search(r"[<>:\"|?*]|\.\.", name) or re.match(r"^[a-z]:\\\\windows", name, re.I):
            return OperatorOutcome(False, f"'{name}' isn't a safe file name.", needs="clarify")
        d.press(parse_chord("ctrl+shift+s"))
        dialog = d.wait_until(lambda: (d.foreground() and d.foreground().hwnd != (win.hwnd if win else 0)), timeout=3.0)
        if not dialog:
            return OperatorOutcome(False, "The Save As dialog didn't open.")
        d.press(parse_chord("ctrl+a"))
        d.type_text(name)
        d.press(parse_chord("enter"))
        base = re.split(r"[\\\\/]", name)[-1].lower()
        ok = d.wait_until(lambda: base.split(".")[0] in ((d.foreground() or win).title or "").lower(), timeout=3.0)
        fg = d.foreground()
        if fg and fg.hwnd != (win.hwnd if win else 0) and re.search(r"replace|already exists|confirm", fg.title, re.I):
            return OperatorOutcome(False, f"A file named {name} already exists - Windows is asking whether to replace it. "
                                          "Answer that yourself.", needs="user")
        return OperatorOutcome(ok, f"Saved as {name}." if ok else f"I typed {name} in Save As but the title doesn't show it yet.",
                               evidence={"verified": ok})


    def paste_plain(self, expect: Optional[WindowRef] = None) -> OperatorOutcome:
        bad = self._guard(expect)
        if bad:
            return bad
        d = self.desktop
        text = d.clipboard_text()
        if not text:
            return OperatorOutcome(False, "There's no text on the clipboard to paste.")
        d.set_clipboard_text(text)                       # re-setting as plain text drops rich formats
        before = d.focused_text()
        d.press(parse_chord("ctrl+v"))
        return self._result(before, "Pasted as plain text.")


    def template(self, name: str, expect: Optional[WindowRef] = None, path=None) -> OperatorOutcome:
        import json
        from pathlib import Path
        if path is None:
            from jarvis.config import ROOT
            path = ROOT / "db" / "text_templates.json"
        p = Path(path)
        try:
            templates = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except Exception:
            templates = {}
        key = re.sub(r"[^a-z0-9 ]", " ", name.lower()).replace("template", "").strip()
        hit = templates.get(key) or next((v for k, v in templates.items() if key and (key in k or k in key)), None)
        if hit is None:
            names = ", ".join(sorted(templates)) or "none saved yet"
            return OperatorOutcome(False, f"I don't have a '{name}' template (saved: {names}). Add it to {p.name}.",
                                   needs="clarify")
        return self.insert(hit, expect=expect)
