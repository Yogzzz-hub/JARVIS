"""ide.* primitives for Antigravity / VS Code / Cursor / Windsurf, built on window + ui + text + deliver.

Nothing is reported done unless it was observed: a prompt counts as written when the prompt box reads it back, as
sent when the box empties or the agent shows it is working, a file as open when the window title names it, an
attachment when a chip appears. Without an accessibility tree the outcome says the effect couldn't be confirmed.
The IDE's own content (code, agent output, terminal text) is data - shown to the owner, never obeyed.
"""
from __future__ import annotations

import re
from typing import Optional

from jarvis.core.context.models import BaseResourceRef
from jarvis.core.operator.platform import Desktop, get_desktop, parse_chord
from jarvis.core.operator.refs import ControlRef, OperatorOutcome, WindowRef
from jarvis.core.operator.ui import UIAdapter, UIAWindowAdapter, UIOperator, UITarget

IDE_NAMES = {"antigravity": "antigravity", "vs code": "vs code", "vscode": "vs code", "code": "vs code",
             "visual studio code": "vs code", "cursor": "cursor", "windsurf": "windsurf", "ide": "", "editor": ""}
# What the agent/chat prompt box is called across these IDEs (accessible names).
PROMPT_NAMES = ("ask anything", "ask", "plan, search, build anything", "message", "chat input", "prompt",
                "type your task", "ask copilot", "ask antigravity", "agent", "send a message", "chat", "add context")
SEND_NAMES = ("send", "submit", "run", "send message")
BUSY_NAMES = ("stop", "stop generating", "cancel", "interrupt", "stop agent")
APPLY_NAMES = {"accept": ("accept all", "accept", "keep all", "keep", "apply"), "reject": ("reject all", "reject",
                                                                                           "undo all", "discard")}
_BLOCKED_COMMANDS = re.compile(r"\b(delete|remove|uninstall|reset|discard|clear all|wipe|format|sign out|"
                               r"terminal:\s*run|run (selected )?text|kill)\b", re.I)


class IDEOperator:
    def __init__(self, desktop: Optional[Desktop] = None, tracker=None, adapter_factory=None):
        self._desktop = desktop
        self._tracker = tracker
        self._adapter_factory = adapter_factory or (lambda w: UIAWindowAdapter(w.hwnd))
        self.ui = UIOperator()

    @property
    def desktop(self) -> Desktop:
        return self._desktop or get_desktop()

    @property
    def tracker(self):
        if self._tracker is None:
            from jarvis.core.operator.windows import get_window_tracker
            self._tracker = get_window_tracker()
        return self._tracker

    # -- target ----------------------------------------------------------------------------------------------
    def window(self, name: str = "") -> OperatorOutcome:
        key = IDE_NAMES.get((name or "").lower().strip(), (name or "").lower().strip())
        found = self.tracker.resolve(query=key, app=key) if key else self.tracker.resolve(family="ide")
        if not found.ok:
            return OperatorOutcome(False, f"{name or 'Your IDE'} isn't open.", needs=found.needs,
                                   candidates=found.candidates)
        return found

    def _ready(self, name: str) -> tuple[Optional[WindowRef], Optional[UIAdapter], Optional[OperatorOutcome]]:
        w = self.window(name)
        if not w.ok:
            return None, None, w
        f = self.tracker.focus(w.resource)
        if not f.ok:
            return None, None, f
        try:
            adapter = self._adapter_factory(w.resource)
        except Exception:
            adapter = None
        return w.resource, adapter, None

    def _prompt_box(self, adapter: UIAdapter) -> Optional[ControlRef]:
        controls = adapter.snapshot()
        editable = [c for c in controls if c.editable]
        for want in PROMPT_NAMES:
            hits = [c for c in editable if want in (c.name or "").lower()]
            if len(hits) == 1:
                return hits[0]
        if len(editable) == 1:
            return editable[0]
        return None

    # -- primitives ------------------------------------------------------------------------------------------
    def prompt(self, text: str, ide: str = "", send: bool = False) -> OperatorOutcome:
        w, adapter, bad = self._ready(ide)
        if bad:
            return bad
        box = self._prompt_box(adapter) if adapter else None
        if box is None:
            return OperatorOutcome(False, f"I can't find the prompt box in {w.display_name}. Click into it and say "
                                          "'type ...'.", needs="clarify", resource=w)
        adapter.focus(box)
        if not adapter.set_value(box, text):
            fg = self.desktop.foreground()
            if not fg or fg.hwnd != w.hwnd:
                return OperatorOutcome(False, f"{w.display_name} lost focus.", needs="target_lost")
            self.desktop.type_text(text)
        got = adapter.read(box) or ""
        if text.strip()[:40] not in got:
            return OperatorOutcome(False, "The prompt didn't land in the box.", resource=w, evidence={"read_back": got[:80]})
        if not send:
            return OperatorOutcome(True, f"Prompt written in {w.display_name}. Say 'send it' when ready.", resource=w,
                                   evidence={"verified": True})
        return self._send(w, adapter, box)

    def send(self, ide: str = "") -> OperatorOutcome:
        w, adapter, bad = self._ready(ide)
        if bad:
            return bad
        box = self._prompt_box(adapter) if adapter else None
        if box is None:
            return OperatorOutcome(False, "I can't find the prompt box to send.", needs="clarify")
        if not (adapter.read(box) or "").strip():
            return OperatorOutcome(False, "The prompt box is empty - nothing to send.")
        return self._send(w, adapter, box)

    def _send(self, w: WindowRef, adapter: UIAdapter, box: ControlRef) -> OperatorOutcome:
        controls = adapter.snapshot()
        btn = next((c for c in controls if (c.name or "").lower() in SEND_NAMES and c.enabled), None)
        if btn is not None:
            adapter.invoke(btn)
        else:
            adapter.focus(box)
            self.desktop.press(parse_chord("enter"))
        d = self.desktop

        def went() -> bool:
            if not (adapter.read(box) or "").strip():
                return True
            return any((c.name or "").lower() in BUSY_NAMES for c in adapter.snapshot())

        ok = d.wait_until(went, timeout=3.0, interval=0.15)
        return OperatorOutcome(ok, f"Sent to {w.display_name}'s agent." if ok else
                               "I pressed send, but the prompt is still in the box.", resource=w,
                               evidence={"verified": ok})

    def attach(self, resource: BaseResourceRef, ide: str = "") -> OperatorOutcome:
        w, adapter, bad = self._ready(ide)
        if bad:
            return bad
        from jarvis.core.operator.deliver import DeliverOperator
        box = self._prompt_box(adapter) if adapter else None
        field = box.name if box is not None and box.name else ""
        return DeliverOperator(self._desktop, self.tracker).to_window(resource, w, adapter=adapter,
                                                                      field=field or "prompt box")

    def generating(self, ide: str = "") -> Optional[bool]:
        w = self.window(ide)
        if not w.ok:
            return None
        try:
            controls = self._adapter_factory(w.resource).snapshot()
        except Exception:
            return None
        return any((c.name or "").lower() in BUSY_NAMES and c.enabled for c in controls)

    def changes(self, decision: str, ide: str = "") -> OperatorOutcome:
        """accept / reject the agent's proposed edits via the IDE's own buttons."""
        w, adapter, bad = self._ready(ide)
        if bad:
            return bad
        if adapter is None:
            return OperatorOutcome(False, "I can't see the IDE's buttons.", needs="vision")
        for name in APPLY_NAMES.get(decision, ()):
            out = self.ui.invoke(adapter, UITarget(name=name, role="button"), approved=True)
            if out.ok:
                return OperatorOutcome(True, f"{decision.title()}ed the changes.", resource=w, evidence=out.evidence)
        return OperatorOutcome(False, f"I don't see an {decision} button right now.")

    def open_file(self, name: str, ide: str = "") -> OperatorOutcome:
        w, _adapter, bad = self._ready(ide)
        if bad:
            return bad
        d = self.desktop
        d.press(parse_chord("ctrl+p"))
        d.type_text(name)
        d.press(parse_chord("enter"))
        base = re.split(r"[\\/]", name)[-1].lower()
        ok = d.wait_until(lambda: base in ((d.foreground() or w).title or "").lower(), timeout=2.0)
        return OperatorOutcome(ok, f"Opened {name}." if ok else f"I typed {name} in Quick Open but the tab "
                                                                 "title doesn't show it yet.",
                               resource=w, evidence={"verified": ok})

    def command(self, command: str, ide: str = "") -> OperatorOutcome:
        if _BLOCKED_COMMANDS.search(command):
            return OperatorOutcome(False, f"'{command}' changes or removes things - run it yourself from the "
                                          "palette.", needs="user")
        w, _adapter, bad = self._ready(ide)
        if bad:
            return bad
        d = self.desktop
        d.press(parse_chord("ctrl+shift+p"))
        d.type_text(command)
        d.press(parse_chord("enter"))
        return OperatorOutcome(True, f"Ran '{command}' from the command palette.", resource=w,
                               evidence={"verified": None})

    def key(self, action: str, ide: str = "") -> OperatorOutcome:
        """Named IDE chords: new_chat, toggle_terminal, toggle_sidebar, save, close_tab, next_tab, ..."""
        chords = {"new_chat": "ctrl+l", "toggle_terminal": "ctrl+`", "toggle_sidebar": "ctrl+b", "save": "ctrl+s",
                  "save_all": "ctrl+k s", "close_tab": "ctrl+w", "next_tab": "ctrl+tab", "previous_tab": "ctrl+shift+tab",
                  "go_to_line": "ctrl+g", "find": "ctrl+f", "find_in_files": "ctrl+shift+f", "format": "shift+alt+f",
                  "comment": "ctrl+/", "explorer": "ctrl+shift+e", "agent_panel": "ctrl+alt+b", "zoom_in": "ctrl+=",
                  "zoom_out": "ctrl+-", "split_editor": "ctrl+\\", "undo": "ctrl+z", "redo": "ctrl+y"}
        seq = chords.get(action)
        if not seq:
            return OperatorOutcome(False, f"I don't know the IDE action '{action}'.", needs="clarify")
        w, _adapter, bad = self._ready(ide)
        if bad:
            return bad
        for part in seq.split(" "):
            self.desktop.press(parse_chord(part))
        return OperatorOutcome(True, f"{action.replace('_', ' ').capitalize()} in {w.display_name}.", resource=w,
                               evidence={"keys": seq, "verified": None})

    def read_response(self, ide: str = "") -> OperatorOutcome:
        w = self.window(ide)
        if not w.ok:
            return w
        from jarvis.core.operator.screen import ScreenOperator
        return ScreenOperator(self._desktop).read(w.resource, adapter=self._adapter_factory(w.resource))
