"""Live dictation: words appear in the target window while the owner is still speaking.

The voice pipeline already produces a *stable prefix* every ~200 ms (words the recogniser will not revise). This
module turns that stream into incremental typing:

    partial -> stable prefix -> hold back what might still be a command -> type only the new words

* No model call per word: holding back is a small, generic prefix test against the dictation command vocabulary
  ("delete the last word", "new paragraph", "stop typing", "type literally ..."), and spoken punctuation that spans
  two words ("question mark", "full stop") waits for its second word.
* An utterance that *starts* like a command is never typed live: the final transcript decides (the controller runs
  it as an edit/control turn).
* Before every insertion the target window is checked. If focus moved, typing stops (TARGET_LOST: the controller
  pauses and keeps the words in its pending buffer for "continue").
* The final transcript reconciles: if the recogniser changed its mind about words already typed, exactly those
  characters are erased and retyped; the final is then marked consumed so the command path does not type it a
  second time (one utterance => typed once).
"""
from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Optional

from jarvis.core.operator.platform import Desktop, get_desktop, parse_chord

logger = logging.getLogger("jarvis.operator.dictate")

# Utterances beginning with these words may be a dictation command: never typed live.
_COMMAND_STARTS = re.compile(
    r"^(?:hey\s+)?(?:jarvis|stop|pause|resume|continue|carry|keep going|done|finish|end|exit|cancel|emergency|"
    r"delete|remove|scratch|erase|replace|change|capitali[sz]e|uppercase|lowercase|make|undo|redo|select|copy|cut|"
    r"paste|backspace|type|write|new|next|paragraph|line|hold on|take a|go on|go back|press|enter|tab|switch|"
    r"open|close|send|save|bold|italic|spell|code mode|normal mode|number mode)\b", re.I)
# Multi-word spoken tokens: a trailing first word waits for the next one.
_SPOKEN_PAIRS = ("question mark", "full stop", "exclamation mark", "exclamation point", "new line", "new paragraph",
                 "open quote", "close quote", "open parenthesis", "close parenthesis", "open paren", "close paren",
                 "open bracket", "close bracket", "open brace", "close brace", "double equals", "not equals",
                 "fat arrow", "next line", "line break", "stop typing", "stop dictation", "stop dictating",
                 "pause typing", "pause dictation", "done typing", "done dictating", "end dictation", "end typing",
                 "finish typing", "exit dictation", "cancel dictation")
_HOLD_FIRST = {p.split()[0] for p in _SPOKEN_PAIRS} | {"jarvis", "hey"}
# A control phrase at the *end* of a dictated utterance ("... see you tomorrow, stop typing").
_TRAILING_CONTROL = re.compile(
    r"^(?P<text>.*?)[\s,.;:!?]*\b(?P<cmd>(?:stop|pause|done|finish|end|exit|cancel)\s+(?:typing|dictation|dictating))"
    r"[.!?]?$", re.I | re.S)


def _words(text: str) -> list[str]:
    return (text or "").split()


def _norm_word(w: str) -> str:
    return re.sub(r"[^\w']", "", w.lower())


@dataclass
class _Utterance:
    committed: list[str] = field(default_factory=list)      # raw words already typed (pre-formatting)
    typed: list[str] = field(default_factory=list)          # formatted chunks exactly as typed, one per commit
    held: bool = False                                      # starts like a command: no live typing at all
    lost: bool = False


class LiveDictation:
    """Bridges the recogniser's stable prefix to the DictationController, one utterance at a time."""

    def __init__(self, controller=None, desktop: Optional[Desktop] = None):
        self._controller = controller
        self._desktop = desktop
        self._u: Optional[_Utterance] = None
        self._lock = threading.Lock()
        self.stats = {"live_commits": 0, "live_chars": 0, "reconciled": 0, "held_utterances": 0, "target_lost": 0}

    @property
    def controller(self):
        if self._controller is None:
            from jarvis.core.desktop.dictation_controller import get_dictation_controller
            self._controller = get_dictation_controller()
        return self._controller

    @property
    def desktop(self) -> Desktop:
        return self._desktop or get_desktop()

    def active(self) -> bool:
        from jarvis.core.desktop.dictation_controller import DictationState
        try:
            return self.controller.state in (DictationState.DICTATING, DictationState.CODE_MODE)
        except Exception:
            return False

    # -- utterance lifecycle ----------------------------------------------------------------------------------
    def begin(self) -> None:
        with self._lock:
            self._u = _Utterance()

    def feed(self, stable_prefix: str) -> str:
        """New stable words arrived. Types what is safe to type now; returns the text typed (may be '')."""
        with self._lock:
            if not self.active():
                return ""
            u = self._u or _Utterance()
            self._u = u
            words = _words(stable_prefix)
            if not words or u.lost:
                return ""
            if not u.committed and (u.held or _COMMAND_STARTS.match(" ".join(words[:3]))):
                if not u.held:
                    self.stats["held_utterances"] += 1
                u.held = True
                return ""
            ready = self._safe_prefix(words)
            if self._diverged(u.committed, ready):
                return ""                         # stable words shouldn't change; if they do, the final reconciles
            new = ready[len(u.committed):]
            if not new:
                return ""
            return self._type_words(u, new)

    def finish(self, final_text: str) -> bool:
        """Final transcript for the utterance. Returns True when it was handled here (typed and reconciled), so the
        command path must not type it again; False when it is a command (or nothing was dictated live)."""
        with self._lock:
            u, self._u = self._u, None
            if not self.active():
                return False
            u = u or _Utterance()
            text = (final_text or "").strip()
            if not text:
                return bool(u.committed)
            if u.held or (not u.committed and _COMMAND_STARTS.match(text)):
                return False                      # the controller classifies it as an edit/control/literal turn
            trailing = _TRAILING_CONTROL.match(text)
            body = trailing.group("text").strip() if trailing else text
            words = _words(body)
            common = self._common(u.committed, words)
            if len(common) < len(u.committed):
                if not self._erase(u, len(common)):
                    return True                   # target lost: the controller paused with the words pending
                self.stats["reconciled"] += 1
            rest = words[len(u.committed):]
            if rest:
                self._type_words(u, rest, final=True)
            if trailing:
                ctrl = self.controller
                cmd = trailing.group("cmd").lower()
                if cmd.startswith("pause"):
                    ctrl.pause("user request")
                else:
                    ctrl.stop()
            return True

    def abort(self) -> None:
        """The utterance ended without a final transcript: what was typed was stable and stays."""
        with self._lock:
            self._u = None

    # -- internals --------------------------------------------------------------------------------------------
    @staticmethod
    def _safe_prefix(words: list[str]) -> list[str]:
        """Drop trailing words that may still become a multi-word spoken token or a trailing control phrase."""
        out = list(words)
        while out and _norm_word(out[-1]) in _HOLD_FIRST:
            out.pop()
        return out

    @staticmethod
    def _common(a: list[str], b: list[str]) -> list[str]:
        n = 0
        while n < len(a) and n < len(b) and _norm_word(a[n]) == _norm_word(b[n]):
            n += 1
        return a[:n]

    def _diverged(self, committed: list[str], words: list[str]) -> bool:
        return len(self._common(committed, words)) < len(committed)

    def _focus_ok(self) -> bool:
        ctrl = self.controller
        hwnd = getattr(getattr(ctrl, "target", None), "window_hwnd", 0)
        if not hwnd:
            return True
        fg = self.desktop.foreground()
        if fg is None and getattr(ctrl, "_test_target", None) is not None:
            return bool(ctrl._test_target.focus_verified)
        return bool(fg and fg.hwnd == hwnd)

    def _type_words(self, u: _Utterance, words: list[str], final: bool = False) -> str:
        ctrl = self.controller
        raw = " ".join(words)
        formatted = ctrl._format_text(raw)
        prev_tail = ctrl._committed_text[-1:]
        if not prev_tail:                          # first words of the session: what is already in the field?
            prev_tail = (self.desktop.focused_text() or "")[-1:]
        if prev_tail and not prev_tail.isspace() and formatted[:1] not in ",.;:!?)]}'\"\n" and formatted[:1]:
            formatted = " " + formatted
        if not self._focus_ok():
            u.lost = True
            self.stats["target_lost"] += 1
            ctrl._pending_buffer += formatted
            ctrl.pause("target lost")
            return ""
        n = self.desktop.type_text(formatted)
        u.committed.extend(words)
        u.typed.append(formatted)
        ctrl._buffer.append(formatted)
        ctrl._committed_text += formatted
        ctrl._target.total_committed += n
        ctrl._diagnostics.commits += 1
        ctrl._diagnostics.total_characters += n
        if not final:
            self.stats["live_commits"] += 1
            self.stats["live_chars"] += n
        return formatted

    def _erase(self, u: _Utterance, keep_words: int) -> bool:
        """Erase typed chunks back to ``keep_words`` committed words (whole chunks; then retype the kept words)."""
        if not self._focus_ok():
            u.lost = True
            self.controller.pause("target lost")
            return False
        ctrl = self.controller
        keep = u.committed[:keep_words]
        total = sum(len(c) for c in u.typed)
        for _ in range(total):
            self.desktop.press(parse_chord("backspace"))
        ctrl._committed_text = ctrl._committed_text[: len(ctrl._committed_text) - total]
        u.committed, u.typed = [], []
        if keep:
            self._type_words(u, keep, final=True)
        return True


_live: Optional[LiveDictation] = None


def get_live_dictation() -> LiveDictation:
    global _live
    if _live is None:
        _live = LiveDictation()
    return _live


def set_live_dictation(live: Optional[LiveDictation]) -> None:
    global _live
    _live = live
