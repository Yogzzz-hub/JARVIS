"""Universal Operator tools: thin, schema-validated entry points over jarvis.core.operator primitives.

Each tool takes typed arguments (never code, coordinates or raw key strings from a model), runs one primitive,
and returns what was observed. A primitive that could not confirm its effect fails with the reason; one that needs
the owner (CAPTCHA, login, a locked phone) or the owner's OK (a consequential button, sending) says so - the
approval re-runs the same prepared call with ``approved=True``.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import Field

from jarvis.tools.base import Contract, ExecutionMethod, IdempotencyClass, RiskLevel, Tool, ToolDefinition

logger = logging.getLogger("jarvis.tools.operator")

APPROVAL_PREFIX = "APPROVAL_NEEDED: "


class ApprovalNeeded(RuntimeError):
    """The primitive stopped before a consequential step; the owner's OK re-runs it with approved=True."""

    def __init__(self, message: str):
        super().__init__(APPROVAL_PREFIX + message)


class OperatorOutput(Contract):
    ok: bool
    message: str
    verified: Optional[bool] = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    resource: dict[str, Any] = Field(default_factory=dict)


def _finish(out) -> dict[str, Any]:
    """OperatorOutcome -> tool output; failures raise so the executor records them as failures."""
    if not out.ok:
        if out.needs == "approve":
            raise ApprovalNeeded(out.message)
        raise RuntimeError(out.message)
    res = {}
    if out.resource is not None:
        r = out.resource
        res = {"type": r.resource_type, "name": r.display_name, "id": r.canonical_identifier or r.resource_id}
        for k in ("path", "url", "title", "hwnd", "process"):
            if getattr(r, k, None):
                res[k] = getattr(r, k)
    ev = {k: v for k, v in (out.evidence or {}).items() if isinstance(v, (str, int, float, bool, type(None), list, dict))}
    return {"ok": True, "message": out.message, "verified": ev.get("verified", True if out.ok else None),
            "evidence": ev, "resource": res}


class _Hub:
    """Shared primitive instances (one tracker/history, one resource memory, one watch manager)."""

    def __init__(self, resolver=None, launcher=None, working_memory=None):
        from jarvis.core.operator.resources import get_resources
        self.tasks = None             # the service's TaskManager, attached by the runtime (task / build watches)
        self.registry = None          # the tool registry, attached by the runtime (capability audit)
        self.router = None            # the live router, attached by the runtime (dry runs)
        from jarvis.core.operator.windows import get_window_tracker
        self.resolver, self.launcher = resolver, launcher
        self.tracker = get_window_tracker()
        self.resources = get_resources()
        if working_memory is not None:
            self.resources.attach(working_memory)

    @property
    def browser(self):
        from jarvis.core.operator.browser import BrowserOperator
        return BrowserOperator(resources=self.resources)

    def launch(self, name: str) -> bool:
        if not (self.resolver and self.launcher):
            return False
        try:
            self.launcher(self.resolver.resolve(name))
            return True
        except Exception as e:
            logger.info("launch %s failed: %s", name, e)
            return False

    def window(self, query: str, launch: bool = False):
        from jarvis.core.operator.refs import OperatorOutcome
        found = self.tracker.resolve(query=query) if query else self.tracker.resolve()
        if not found.ok and launch and query and found.needs != "clarify" and self.launch(query):
            d = self.tracker.desktop
            d.wait_until(lambda: self.tracker.resolve(query=query).ok, timeout=8.0, interval=0.2)
            found = self.tracker.resolve(query=query)
        if not found.ok and not found.message:
            return OperatorOutcome(False, f"I can't see {query or 'a window'}.")
        return found


_hub: Optional[_Hub] = None


def _get_hub() -> _Hub:
    global _hub
    if _hub is None:
        _hub = _Hub()
    return _hub


def _def(name: str, description: str, input_model, risk=RiskLevel.REVERSIBLE, timeout=15.0, read_only=False,
         tags=(), idempotent=False) -> ToolDefinition:
    return ToolDefinition(name=name, description=description, input_model=input_model, output_model=OperatorOutput,
                          read_only=read_only, risk=risk, timeout_s=timeout, tags=("operator",) + tuple(tags),
                          execution_method=ExecutionMethod.NATIVE,
                          idempotency=IdempotencyClass.IDEMPOTENT if idempotent else IdempotencyClass.NON_IDEMPOTENT)


# ------------------------------------------------------------------------------------------------- window
class WindowOpInput(Contract):
    action: str = Field(default="focus", description="focus | maximize | minimize | restore | fullscreen | close | arrange | "
                                                     "list | resize | move | active | find | info | save_layout | "
                                                     "restore_layout | isolate (minimise every other window)")
    target: str = Field(default="", description="window description: 'previous', 'my editor', 'chrome', 'second chrome', a title word")
    targets: list[str] = Field(default_factory=list, description="windows for side-by-side/stack layouts")
    layout: str = Field(default="", description="left | right | top | bottom | side_by_side | stack | quadrants | center | next_monitor")
    launch: bool = Field(default=False, description="open the app first if no window of it is open")
    direction: str = Field(default="", description="resize: smaller | bigger; move: left | right | other")
    name: str = Field(default="", description="layout name for save_layout / restore_layout")


class WindowOpTool(Tool):
    definition = _def("window_op", "Focus, maximize, minimize, restore, full-screen, close or arrange windows by "
                      "description (previous window, my editor, chrome with YouTube), with foreground history.",
                      WindowOpInput, tags=("window",))

    def run(self, a: WindowOpInput) -> dict[str, Any]:
        hub = _get_hub()
        tr = hub.tracker
        from jarvis.core.operator.refs import OperatorOutcome
        if a.action == "list":
            wins = tr.list()
            return _finish(OperatorOutcome(True, "; ".join(w.title for w in wins[:12]) or "No windows are open.",
                                           evidence={"count": len(wins), "untrusted": True}))
        if a.action == "active" or (a.action == "info" and not a.target):
            return _finish(tr.active())
        if a.action == "find":
            return _finish(tr.find_and_show(a.target))
        if a.action == "isolate":
            keep = hub.window(a.target or "", launch=bool(a.target))
            if not keep.ok:
                return _finish(keep)
            return _finish(tr.isolate(keep.resource))
        if a.action == "save_layout":
            return _finish(tr.save_layout(a.name or a.target))
        if a.action == "restore_layout":
            return _finish(tr.restore_layout(a.name or a.target, launch=hub.launch))
        if a.action == "arrange" and a.targets:
            found = []
            for q in a.targets:
                w = hub.window("" if q in ("current", "this", "it") else q, launch=True)
                if not w.ok:
                    return _finish(w)
                found.append(w.resource)
            return _finish(tr.arrange(found, a.layout or "side_by_side"))
        w = hub.window(a.target, launch=a.launch)
        if not w.ok:
            return _finish(w)
        win = w.resource
        if a.action == "focus":
            return _finish(tr.focus(win))
        if a.action == "close":
            return _finish(tr.close(win))
        if a.action == "arrange":
            tr.focus(win)
            return _finish(tr.arrange([win], a.layout or "left"))
        if a.action in ("maximize", "minimize", "restore", "fullscreen"):
            return _finish(tr.set_state(win, a.action))
        if a.action == "resize":
            return _finish(tr.resize(win, a.direction or "smaller"))
        if a.action == "move":
            return _finish(tr.move_side(win, a.direction or a.layout or "other"))
        if a.action == "info":
            return _finish(OperatorOutcome(True, f"{win.display_name}: {win.process}, "
                                                 f"{tr.desktop.window_state(win.hwnd)}.", resource=win,
                                           evidence={"process": win.process, "untrusted": True}))
        raise RuntimeError(f"Unknown window action '{a.action}'.")


# ------------------------------------------------------------------------------------------------- ui
class UIOpInput(Contract):
    action: str = Field(default="click", description="click | check | uncheck | type | read | find | scroll | select | "
                                                     "slider | expand | collapse | menu | modal | explain | focus | "
                                                     "next_focus | clear | copy | remove_attachment")
    target: str = Field(default="", description="control description: 'the send button', 'search box', 'the second result'")
    text: str = Field(default="", description="text to type (for action=type)")
    surface: str = Field(default="auto", description="auto | desktop | browser | phone | ide")
    window: str = Field(default="", description="window/app the control is in (default: the one in front)")
    direction: str = Field(default="down")
    n: int = Field(default=1, ge=1, le=50)
    option: str = Field(default="", description="option to choose (select)")
    value: Optional[float] = Field(default=None, description="0-100 position for a slider")
    path: list[str] = Field(default_factory=list, description="menu path, e.g. ['File', 'Export', 'PDF']")
    approved: bool = Field(default=False, description="owner already approved a consequential control")


class UIOpTool(Tool):
    definition = _def("ui_op", "Find a control by role/name/ordinal in the window, web page, IDE or phone screen and "
                      "click it, tick it, type into it, read it or scroll - never by coordinates.",
                      UIOpInput, tags=("ui", "click", "type"))

    def _adapter(self, a: UIOpInput):
        from jarvis.core.operator.refs import OperatorOutcome
        hub = _get_hub()
        if a.surface == "phone":
            from jarvis.core.operator.device import get_device_operator
            dev = get_device_operator()
            r = dev.ready()
            if not r.ok:
                return None, r
            if dev.locked():
                return None, OperatorOutcome(False, "The phone is locked - unlock it yourself and I'll carry on.", needs="user")
            return dev.adapter(), None
        w = hub.window(a.window) if a.window else hub.window("")
        if not w.ok:
            return None, w
        win = w.resource
        if a.surface == "browser" or (a.surface == "auto" and win.family in ("browser", "media")):
            ad = hub.browser.page_adapter()
            if ad is not None:
                return ad, None
        if a.window:
            f = hub.tracker.focus(win)
            if not f.ok:
                return None, f
        from jarvis.core.operator.ui import UIAWindowAdapter
        return UIAWindowAdapter(win.hwnd), None

    def run(self, a: UIOpInput) -> dict[str, Any]:
        from jarvis.core.operator.ui import UIOperator, UITarget
        adapter, bad = self._adapter(a)
        if bad is not None:
            return _finish(bad)
        ui = UIOperator()
        act = a.action
        if act == "select":
            return _finish(ui.select(adapter, a.option or a.text, within=a.target))
        if act == "slider":
            if a.value is None:
                raise RuntimeError("To what level?")
            return _finish(ui.slider(adapter, a.target or "slider", a.value))
        if act in ("expand", "collapse"):
            return _finish(ui.expand(adapter, a.target, open_=act == "expand"))
        if act == "menu":
            return _finish(ui.menu(adapter, a.path or [p.strip() for p in a.target.split(">") if p.strip()]))
        if act == "modal":
            return _finish(ui.modal(adapter))
        if act == "explain":
            return _finish(ui.explain(adapter, a.target))
        if act == "clear":
            return _finish(ui.clear(adapter, a.target))
        if act == "remove_attachment":
            return _finish(ui.remove_attachment(adapter, a.target))
        if act in ("focus", "next_focus"):
            from jarvis.core.operator.refs import OperatorOutcome
            if act == "next_focus" or not a.target:
                from jarvis.core.operator.platform import get_desktop, parse_chord
                for _ in range(a.n):
                    get_desktop().press(parse_chord("tab"))
                return _finish(OperatorOutcome(True, "Moved to the next field.", evidence={"verified": None}))
            found = ui.find(adapter, a.target)
            if not found.ok:
                return _finish(found)
            ok = adapter.focus(found.resource)
            return _finish(OperatorOutcome(bool(ok), f"Focused {found.resource.name}." if ok else
                                           f"{found.resource.name} wouldn't take focus.", resource=found.resource))
        if act == "copy":
            from jarvis.core.operator.clip import ClipOperator
            got = ui.read(adapter, a.target)
            if not got.ok:
                return _finish(got)
            text = (got.evidence or {}).get("value") or got.message
            return _finish(ClipOperator(resources=_get_hub().resources).set_text(str(text)))
        if a.action == "scroll":
            return _finish(ui.scroll(adapter, a.direction, a.n))
        if a.action == "type":
            return _finish(ui.set_value(adapter, a.target or "text box", a.text))
        if a.action == "read":
            return _finish(ui.read(adapter, a.target))
        if a.action == "find":
            return _finish(ui.find(adapter, a.target))
        target = UITarget.parse(a.target)
        if a.action in ("check", "uncheck"):
            found = ui.find(adapter, target)
            if not found.ok:
                return _finish(found)
            state = adapter.toggle_state(found.resource)
            want = a.action == "check"
            if state is not None and state == want:
                from jarvis.core.operator.refs import OperatorOutcome
                return _finish(OperatorOutcome(True, f"{found.resource.name} is already {'on' if want else 'off'}.",
                                               resource=found.resource))
        out = ui.invoke(adapter, target, approved=a.approved)
        if not out.ok and out.needs == "vision":
            out.message = ("I can't read this window's controls. Say 'look at the screen and click ...' and I'll "
                           "find it visually and show you before clicking.")
        return _finish(out)


# ------------------------------------------------------------------------------------------------- text
class TextOpInput(Contract):
    action: str = Field(description="delete | select | copy | cut | replace | upper | lower | capitalize | undo | redo | "
                                    "insert | press | caret | count | find | append | prepend | clear | save | "
                                    "save_as | paste_plain | template")
    unit: str = Field(default="word", description="char | word | line | sentence | paragraph | all")
    n: int = Field(default=1, ge=1, le=200)
    direction: str = Field(default="back", description="back (before the cursor) | forward")
    find: str = Field(default="")
    replace_with: str = Field(default="")
    all: bool = Field(default=False, description="replace every occurrence")
    text: str = Field(default="", description="text to insert")
    key: str = Field(default="", description="named key action for press: bold, italic, underline, save, new_line, ...")
    name: str = Field(default="", description="file name for save_as, template name for template")


class TextOpTool(Tool):
    definition = _def("text_op", "Edit text in the focused field: delete/select/copy/cut N characters, words, lines, "
                      "sentences; replace X with Y; change case; undo/redo; insert text; press a named key action.",
                      TextOpInput, tags=("text", "edit", "keyboard"))

    def run(self, a: TextOpInput) -> dict[str, Any]:
        from jarvis.core.operator.text import EditRequest, TextOperator
        hub = _get_hub()
        cur = hub.tracker.current()
        if cur is None:
            raise RuntimeError("No window is focused to edit.")
        # JARVIS's own window may be in front (typed command): edits go to the owner's window
        fg = hub.tracker.desktop.foreground()
        if fg is None or fg.hwnd != cur.hwnd:
            f = hub.tracker.focus(cur)
            if not f.ok:
                return _finish(f)
        op = TextOperator()
        act = a.action
        if act == "caret":
            return _finish(op.caret(a.unit, a.direction, a.n, expect=cur))
        if act == "count":
            return _finish(op.count())
        if act == "find":
            return _finish(op.find_text(a.find or a.text, expect=cur))
        if act in ("append", "prepend"):
            return _finish(op.append(a.text, where="end" if act == "append" else "start", expect=cur))
        if act == "clear":
            return _finish(op.clear(expect=cur))
        if act in ("save", "save_as"):
            return _finish(op.save(a.name if act == "save_as" else "", expect=cur))
        if act == "paste_plain":
            return _finish(op.paste_plain(expect=cur))
        if act == "template":
            return _finish(op.template(a.name or a.text, expect=cur))
        if a.action == "insert":
            return _finish(op.insert(a.text, expect=cur))
        if a.action == "press":
            return _finish(op.press(a.key, expect=cur, repeat=a.n))
        req = EditRequest(op=a.action, unit=a.unit, n=a.n, direction="all" if a.all else a.direction, find=a.find,
                          replace_with=a.replace_with)
        return _finish(op.edit(req, expect=cur))


# ------------------------------------------------------------------------------------------------- clipboard / screen
class ClipboardOpInput(Contract):
    action: str = Field(default="read", description="read | copy_selection | set | restore | history | paste_nth | "
                                                    "clear_history")
    text: str = Field(default="")
    n: int = Field(default=1, ge=1, le=25, description="paste_nth: 1 = the latest copy, 2 = the one before, ...")
    paste: bool = Field(default=True, description="paste_nth: paste it (true) or only put it back on the clipboard")


class ClipboardOpTool(Tool):
    definition = _def("clipboard_op", "Read the clipboard as a typed resource, copy the current selection (waiting "
                      "for the clipboard to change), put text on it, or restore the previous clipboard.",
                      ClipboardOpInput, tags=("clipboard",))

    def run(self, a: ClipboardOpInput) -> dict[str, Any]:
        from jarvis.core.operator.clip import ClipOperator
        c = ClipOperator(resources=_get_hub().resources)
        if a.action in ("history", "paste_nth", "clear_history"):
            from jarvis.core.operator.clip import get_clipboard_history
            from jarvis.core.operator.refs import OperatorOutcome
            h = get_clipboard_history()
            h.poll_once()
            if a.action == "history":
                return _finish(h.show())
            if a.action == "clear_history":
                n = h.clear()
                return _finish(OperatorOutcome(True, f"Cleared {n} item{'s' if n != 1 else ''} from the clipboard history."))
            return _finish(h.recall(a.n, paste=a.paste, expect=_get_hub().tracker.current()))
        if a.action == "copy_selection":
            return _finish(c.copy_selection())
        if a.action == "set":
            return _finish(c.set_text(a.text))
        if a.action == "restore":
            return _finish(c.restore())
        return _finish(c.get())


class ScreenOpInput(Contract):
    action: str = Field(default="capture", description="capture | read")
    scope: str = Field(default="screen", description="screen | active | <window description>")
    to_clipboard: bool = Field(default=False)


class ScreenOpTool(Tool):
    definition = _def("screen_op", "Capture the screen, the active window or a named window as a screenshot resource "
                      "(optionally on the clipboard), or read a window's text from its accessibility tree.",
                      ScreenOpInput, risk=RiskLevel.READ_ONLY, read_only=True, tags=("screenshot", "screen"))

    def run(self, a: ScreenOpInput) -> dict[str, Any]:
        from jarvis.core.operator.screen import ScreenOperator
        hub = _get_hub()
        win = None
        if a.scope not in ("screen", "full", "all", ""):
            found = hub.window("" if a.scope in ("active", "current", "window") else a.scope)
            if not found.ok:
                return _finish(found)
            win = found.resource
        s = ScreenOperator(resources=hub.resources)
        if a.action == "read":
            return _finish(s.read(win or hub.tracker.current()))
        return _finish(s.capture(win, to_clipboard=a.to_clipboard))


# ------------------------------------------------------------------------------------------------- deliver
class DeliverOpInput(Contract):
    resource: str = Field(default="it", description="what: 'screenshot', 'the download', 'clipboard', 'it'")
    to: str = Field(description="where: an app/window ('antigravity', 'chrome'), 'phone'")
    field: str = Field(default="", description="control inside the app ('prompt box', 'message box')")
    send: bool = Field(default=False, description="also press send (needs the owner's OK)")
    capture_first: bool = Field(default=False, description="take a new screenshot first")
    scope: str = Field(default="screen", description="what to capture when capture_first")
    how: str = Field(default="paste", description="paste | upload")
    action: str = Field(default="deliver", description="deliver | verify (did it really arrive?)")
    approved: bool = Field(default=False)


class DeliverOpTool(Tool):
    definition = _def("deliver_op", "Put a resource (screenshot, file, download, copied text, answer) into an app or "
                      "control, or onto the phone - as paste/attachment - and verify it arrived. Sending is separate "
                      "and needs approval.", DeliverOpInput, timeout=60.0, tags=("deliver", "attach", "paste"))

    def run(self, a: DeliverOpInput) -> dict[str, Any]:
        from jarvis.core.operator.deliver import DeliverOperator
        from jarvis.core.operator.screen import ScreenOperator
        hub = _get_hub()
        res = None
        if a.action == "verify":
            res, question = hub.resources.resolve(a.resource)
            if res is None:
                raise RuntimeError(question)
            from pathlib import Path
            from jarvis.core.operator.files import ref_path
            name = Path(ref_path(res) or "").name
            if not name:
                raise RuntimeError(f"I can't tell which file {res.display_name} was.")
            if a.to.lower() in ("phone", "my phone", "mobile", "android"):
                from jarvis.core.operator.device import get_device_operator
                return _finish(get_device_operator().has_file(name))
            raise RuntimeError("I can only double-check deliveries to the phone; for an app, look at its window.")
        if a.capture_first:
            win = None
            if a.scope not in ("screen", ""):
                f = hub.window("" if a.scope == "active" else a.scope)
                win = f.resource if f.ok else None
            shot = ScreenOperator(resources=hub.resources).capture(win)
            if not shot.ok:
                return _finish(shot)
            res = shot.resource
        else:
            res, question = hub.resources.resolve(a.resource)
            if res is None:
                raise RuntimeError(question)
        d = DeliverOperator(tracker=hub.tracker)
        if a.to.lower() in ("phone", "my phone", "mobile", "android"):
            return _finish(d.to_phone(res))
        target = a.to
        from jarvis.core.operator.ide import IDE_NAMES, IDEOperator
        if target.lower().strip() in IDE_NAMES and not a.field:
            ide = IDEOperator(tracker=hub.tracker)
            if a.send and not a.approved:
                raise ApprovalNeeded(f"Paste {res.display_name} into {target} and send it?")
            out = ide.attach(res, ide=target)
            if out.ok and a.send:
                return _finish(ide.send(ide=target))
            return _finish(out)
        w = hub.window(target, launch=False)
        if not w.ok:
            return _finish(w)
        adapter = None
        if a.field:
            from jarvis.core.operator.ui import UIAWindowAdapter
            adapter = UIAWindowAdapter(w.resource.hwnd)
        return _finish(d.to_window(res, w.resource, adapter=adapter, field=a.field, send=a.send, approved=a.approved))


# ------------------------------------------------------------------------------------------------- browser / video / watch
class BrowserOpInput(Contract):
    action: str = Field(description="open | search | tab_new | tab_close | tab_next | tab_previous | tab_switch | "
                                    "tab_list | back | forward | reload | results | open_result | read | find | scroll"
                                    " | duplicate | stop | url | title | copy_url | heading | site_search | official | "
                                    "detect_login | open_link | upload | download")
    target: str = Field(default="", description="url, site name or query; text to find")
    engine: str = Field(default="", description="search engine/site for action=search")
    which: str = Field(default="", description="tab: index, title word, 'first', 'last'")
    ordinal: int = Field(default=1, description="result number (-1 = last)")
    new_tab: bool = Field(default=False)
    direction: str = Field(default="down")
    n: int = Field(default=1, ge=1, le=20)
    files: list[str] = Field(default_factory=list, description="paths for upload ('it' = the last file/screenshot)")
    read: bool = Field(default=False, description="heading: read the section instead of jumping to it")


class BrowserOpTool(Tool):
    definition = _def("browser_op", "Operate the browser: open/search, tabs (switch by name/number, close, list), back/"
                      "forward/reload, read a page, list and open search results by number, find on page, scroll.",
                      BrowserOpInput, timeout=20.0, tags=("browser", "tabs", "web"))

    def run(self, a: BrowserOpInput) -> dict[str, Any]:
        b = _get_hub().browser
        act = a.action
        if act in ("open", "search"):
            return _finish(b.open(a.target, new_tab=a.new_tab or act == "search", engine=a.engine if act == "search" else ""))
        if act.startswith("tab_"):
            return _finish(b.tab(act[4:], a.which))
        if act in ("back", "forward", "reload"):
            return _finish(b.nav(act, a.n))
        if act == "results":
            return _finish(b.results())
        if act == "open_result":
            return _finish(b.open_result(a.ordinal, title=a.target, new_tab=a.new_tab))
        if act == "read":
            return _finish(b.read_page())
        if act == "find":
            return _finish(b.find_on_page(a.target))
        if act == "scroll":
            return _finish(b.scroll(a.direction, a.n))
        if act in ("url", "title"):
            return _finish(b.info(act))
        if act == "copy_url":
            return _finish(b.copy_url())
        if act == "duplicate":
            return _finish(b.duplicate())
        if act == "stop":
            return _finish(b.stop())
        if act == "heading":
            return _finish(b.heading(a.target, read=a.read))
        if act == "site_search":
            return _finish(b.site_search(a.target))
        if act == "official":
            return _finish(b.official(a.target))
        if act == "detect_login":
            return _finish(b.login_state())
        if act == "open_link":
            return _finish(b.open_link(a.target, new_tab=a.new_tab))
        if act == "upload":
            from jarvis.core.operator.files import FileOperator
            fo, paths = FileOperator(resources=_get_hub().resources), []
            for f in a.files or ["it"]:
                path, question = fo.resolve(f)
                if path is None:
                    raise RuntimeError(question)
                paths.append(str(path))
            return _finish(b.upload(paths, field=a.target))
        if act == "download":
            return _finish(b.download(a.target))
        raise RuntimeError(f"Unknown browser action '{act}'.")


class VideoOpInput(Contract):
    action: str = Field(description="play | pause | toggle | seek_to | seek_by | rate | mute | unmute | volume | restart | "
                                    "next | previous | captions | fullscreen | skip_ad | loop | state")
    value: Optional[float] = Field(default=None, description="seconds for seek, rate for speed, 0-100 for volume")
    relative: bool = Field(default=False, description="rate is a step up/down from the current speed")


class VideoOpTool(Tool):
    definition = _def("video_op", "Control the video/audio the owner is watching: play, pause, seek to a time or by "
                      "seconds, speed, volume, mute, captions, full screen, next, skip a skippable ad, report position.",
                      VideoOpInput, tags=("media", "video", "youtube"))

    def run(self, a: VideoOpInput) -> dict[str, Any]:
        from jarvis.core.operator.media import MediaOperator
        m = MediaOperator(browser=_get_hub().browser)
        value = a.value
        if a.action == "rate" and a.relative:
            st = m.act("state")
            cur = float((st.evidence or {}).get("rate") or 1.0) if st.ok else 1.0
            value = min(4.0, cur + 0.25 * (2 if value and value > 1 else -1)) if value else cur
        return _finish(m.act(a.action, value))


class WatchOpInput(Contract):
    action: str = Field(description="skip_ads | download_done | ide_done | when | cancel | list")
    condition: str = Field(default="", description="for when: download_done | file_appears | window_opened | "
                                                   "window_closed | phone_connected | battery_below | battery_above | "
                                                   "control_appears | control_enabled | ide_done | page_changed | "
                                                   "task_done | captcha | whatsapp_message")
    subject: str = Field(default="", description="what the condition is about: window/app, file name, control, task")
    threshold: Optional[float] = Field(default=None, description="battery percent etc.")
    then: str = Field(default="", description="the owner's own follow-up command, run through JARVIS when it happens")
    notify_phone: bool = Field(default=False, description="also post the notice on the owner's phone")
    kind: str = Field(default="", description="watch kind for cancel (skip_ad, download, ide)")
    ide: str = Field(default="")
    folder: str = Field(default="", description="downloads folder (default: the owner's Downloads)")
    minutes: float = Field(default=60.0, ge=1, le=240, description="how long the watch may run")


class WatchOpTool(Tool):
    definition = _def("watch_op", "Start, list or cancel a scoped, time-limited watch: skip ads when the Skip button "
                      "appears (this video only), tell when a download finishes, tell when the IDE agent is done.",
                      WatchOpInput, tags=("watch", "background"))

    def run(self, a: WatchOpInput) -> dict[str, Any]:
        from jarvis.core.operator.refs import OperatorOutcome
        from jarvis.core.operator.watch import get_watch_manager
        hub = _get_hub()
        wm = get_watch_manager()
        if a.action == "skip_ads":
            return _finish(wm.skip_ads(hub.browser, timeout_s=a.minutes * 60))
        if a.action == "download_done" and a.then:
            pred, desc = _condition(hub, a.model_copy(update={"condition": "download_done"}))
            return _finish(wm.when("download", desc, pred, then=a.then.strip(), timeout_s=a.minutes * 60))
        if a.action == "download_done":
            folder = a.folder
            if not folder:
                from jarvis.tools.system.window_management_tools import get_known_folder_path
                folder = get_known_folder_path("downloads")
            return _finish(wm.download_done(folder, resources=hub.resources, timeout_s=a.minutes * 60))
        if a.action == "ide_done":
            from jarvis.core.operator.ide import IDEOperator
            ide = IDEOperator(tracker=hub.tracker)
            if ide.generating(a.ide) is None:
                raise RuntimeError(f"I can't see {a.ide or 'the IDE'}'s agent panel to watch it.")
            return _finish(wm.until("ide", f"{a.ide or 'the IDE'} agent finishes",
                                    lambda: ide.generating(a.ide) is False, f"{a.ide or 'The IDE'} agent is done.",
                                    interval=2.0, timeout_s=a.minutes * 60))
        if a.action == "when":
            pred, desc = _condition(hub, a)
            phone = None
            if a.notify_phone:
                from jarvis.core.operator.device import get_device_operator
                phone = lambda text: get_device_operator().notify(text)  # noqa: E731
            return _finish(wm.when("when", desc, pred, then=a.then.strip(), interval=2.0, timeout_s=a.minutes * 60,
                                   also_notify=phone))
        if a.action == "cancel":
            n = wm.cancel(kind=a.kind)
            return _finish(OperatorOutcome(True, f"Stopped {n} watch{'es' if n != 1 else ''}." if n else "Nothing was being watched."))
        ws = wm.active()
        return _finish(OperatorOutcome(True, "; ".join(f"{w.kind}: {w.description}" for w in ws) or "Nothing is being watched.",
                                       evidence={"count": len(ws)}))


def _condition(hub: "_Hub", a: "WatchOpInput"):
    """Condition name + subject -> (predicate, description). Predicates only observe; they never act."""
    cond, subj = a.condition, a.subject.strip()
    tr = hub.tracker
    if cond in ("window_opened", "window_closed", "app_opened", "app_closed"):
        if not subj:
            cur = tr.current()
            if cur is None:
                raise RuntimeError("Which window should I watch?")
            subj = cur.display_name
        want_open = cond.endswith("opened")
        return ((lambda: tr.resolve(query=subj).ok == want_open),
                f"{subj} {'opens' if want_open else 'closes'}")
    if cond in ("download_done", "file_appears"):
        from jarvis.core.operator.files import downloads_dir
        from pathlib import Path
        folder = Path(a.folder).expanduser() if a.folder else downloads_dir()
        partial = {".crdownload", ".part", ".tmp", ".download"}
        before = {p.name for p in folder.glob("*")} if folder.exists() else set()

        from jarvis.core.operator.files import TYPE_EXT
        exts = TYPE_EXT.get(subj.lower()) or TYPE_EXT.get(subj.lower() + "s") or ()

        def wanted(p) -> bool:
            if exts:
                return p.suffix.lower() in exts
            return not subj or subj.lower() in p.name.lower()

        def appeared() -> bool:
            if not folder.exists():
                return False
            busy = any(p.suffix.lower() in partial for p in folder.iterdir())
            new = [p for p in folder.iterdir() if p.name not in before and p.suffix.lower() not in partial
                   and p.is_file() and wanted(p)]
            if new and not busy:
                from jarvis.core.operator.refs import DownloadResource
                p = max(new, key=lambda x: x.stat().st_mtime)
                hub.resources.record(DownloadResource(resource_id=f"dl:{p}", path=str(p), filename=p.name))
                return True
            return False
        what = f"{subj} appears in {folder.name}" if subj else f"the download in {folder.name} finishes"
        return appeared, what
    if cond == "whatsapp_message":
        # observes the inbox only: a new one-to-one message (from that person, if named) since the watch started.
        # Group messages never count, and the message itself is not read out - only who wrote.
        from jarvis.integrations.whatsapp.ai import get_whatsapp_ai
        inbox = get_whatsapp_ai().inbox
        who = subj.casefold()

        def incoming() -> list:
            return [m for m in inbox.get_recent(limit=60, include_groups=False) if not getattr(m, "is_from_me", False)
                    and (not who or who in (m.sender_display_name or "").casefold().split()
                         or (m.sender_display_name or "").casefold().startswith(who))]
        seen = {m.message_id for m in incoming()}
        return ((lambda: any(m.message_id not in seen for m in incoming())),
                f"{subj or 'someone'} messages you on WhatsApp")
    if cond in ("phone_connected", "device_online"):
        from jarvis.core.operator.device import get_device_operator
        dev = get_device_operator()
        return (lambda: dev.ready().ok), "your phone is connected"
    if cond in ("battery_below", "battery_above", "battery_full"):
        import psutil
        level = a.threshold if a.threshold is not None else (100 if cond == "battery_full" else 20)
        below = cond == "battery_below"
        if subj.lower() in ("phone", "my phone", "mobile"):
            from jarvis.core.operator.device import get_device_operator
            dev = get_device_operator()

            def read() -> Optional[float]:
                out = dev.status("battery")
                return (out.evidence or {}).get("level") if out.ok else None
        else:
            def read() -> Optional[float]:
                b = getattr(psutil, "sensors_battery", lambda: None)()
                return b.percent if b else None
        if read() is None:
            raise RuntimeError("I can't read that battery level.")
        return ((lambda: (lambda v: v is not None and (v <= level if below else v >= level))(read())),
                f"{'the phone' if subj else 'the'} battery {'drops to' if below else 'reaches'} {level:.0f}%")
    if cond in ("control_appears", "control_enabled"):
        from jarvis.core.operator.ui import UIAWindowAdapter, UIOperator, UITarget
        cur = tr.current()
        if cur is None or not subj:
            raise RuntimeError("Which button should I watch for?")
        ui, target = UIOperator(), UITarget.parse(subj)
        page = hub.browser.page_adapter() if cur.family in ("browser", "media") else None
        adapter = page or UIAWindowAdapter(cur.hwnd)

        def present() -> bool:
            hit = ui.resolver.resolve(adapter.snapshot(), target)
            return hit.ok and (cond == "control_appears" or bool(getattr(hit.resource, "enabled", True)))
        return present, f"the {subj} {'appears' if cond == 'control_appears' else 'is enabled'}"
    if cond == "ide_done":
        from jarvis.core.operator.ide import IDEOperator
        ide = IDEOperator(tracker=tr)
        if ide.generating(subj) is None:
            raise RuntimeError(f"I can't see {subj or 'the IDE'}'s agent panel to watch it.")
        return (lambda: ide.generating(subj) is False), f"{subj or 'the IDE'} agent finishes"
    if cond in ("page_changed", "page_loaded"):
        b = hub.browser
        tab = b.backend.active()
        if tab is None:
            raise RuntimeError("No browser tab is open to watch.")
        start = (tab.url, tab.title)

        def changed() -> bool:
            t = b.backend.active()
            return t is not None and (t.url, t.title) != start
        return changed, "the page changes"
    if cond == "captcha":
        b = hub.browser

        def solved() -> bool:
            st = b.login_state()
            return not (st.evidence or {}).get("captcha", False)
        return solved, "you've finished the CAPTCHA"
    if cond in ("task_done", "task_failed", "build_done", "build_failed"):
        from jarvis.core.tasks.scope import get_scope_manager
        tm = hub.tasks
        me = getattr(get_scope_manager().current(), "task_id", "")
        running = [t for t in tm.active_tasks() if t.request_id != me] if tm is not None else []
        if subj and running:
            running = [t for t in running if subj.lower() in (t.raw_text or "").lower()] or running
        if not running:
            raise RuntimeError("Nothing is running in JARVIS right now for me to watch - start it first "
                               "(for example 'run the tests').")
        tracked = [t.request_id for t in running]
        fail_only = cond.endswith("failed")

        def finished():
            tasks = [tm.get(rid) for rid in tracked]
            if any(t is not None and t.active for t in tasks):
                return None
            failed = any(t is not None and getattr(t.result, "state", "") in ("FAILED", "UNCERTAIN") for t in tasks)
            if fail_only and not failed:
                return "done_silent"
            return "done"
        what = running[0].raw_text[:60]
        return finished, (f"'{what}' fails" if fail_only else f"'{what}' finishes")
    raise RuntimeError(f"I can't watch for '{cond or 'that'}' yet.")


# ------------------------------------------------------------------------------------------------- IDE / phone
class IDEOpInput(Contract):
    action: str = Field(description="prompt | send | attach | accept | reject | open_file | command | key | read | status | "
                                    "focus | tab_next | tab_previous | tab_close | cancel | copy_response | definition | "
                                    "references | rename | format | save | save_all | remove_attachment | "
                                    "list_attachments | docs | read_error | copy_error | open_project | find_symbol | search")
    ide: str = Field(default="", description="antigravity | vs code | cursor | windsurf (default: the IDE in use)")
    text: str = Field(default="", description="prompt text / command name / file name")
    send: bool = Field(default=False)
    name: str = Field(default="", description="named IDE key action for action=key")
    resource: str = Field(default="it", description="resource to attach")


class IDEOpTool(Tool):
    definition = _def("ide_op", "Work in Antigravity / VS Code / Cursor: write (and send) a prompt to the agent, attach "
                      "a screenshot/file, accept or reject its changes, open a file, run a palette command, read its "
                      "reply, check whether it is still generating - each verified in the IDE's UI.",
                      IDEOpInput, timeout=30.0, tags=("ide", "antigravity", "vscode"))

    def run(self, a: IDEOpInput) -> dict[str, Any]:
        from jarvis.core.operator.ide import IDEOperator
        from jarvis.core.operator.refs import OperatorOutcome
        hub = _get_hub()
        ide = IDEOperator(tracker=hub.tracker)
        act = a.action
        if act == "prompt":
            return _finish(ide.prompt(a.text, ide=a.ide, send=a.send))
        if act == "send":
            return _finish(ide.send(ide=a.ide))
        if act == "attach":
            res, q = hub.resources.resolve(a.resource)
            if res is None:
                raise RuntimeError(q)
            return _finish(ide.attach(res, ide=a.ide))
        if act in ("accept", "reject"):
            return _finish(ide.changes(act, ide=a.ide))
        if act == "open_file":
            return _finish(ide.open_file(a.text, ide=a.ide))
        if act == "command":
            return _finish(ide.command(a.text, ide=a.ide))
        if act == "key":
            return _finish(ide.key(a.name, ide=a.ide))
        if act == "read":
            return _finish(ide.read_response(ide=a.ide))
        if act == "status":
            g = ide.generating(a.ide)
            if g is None:
                raise RuntimeError(f"I can't see {a.ide or 'the IDE'}'s agent panel.")
            return _finish(OperatorOutcome(True, "Still working." if g else "It's done."))
        keys = {"tab_next": "next_tab", "tab_previous": "previous_tab", "tab_close": "close_tab", "definition": "definition",
                "references": "references", "format": "format", "save": "save", "save_all": "save_all"}
        if act in keys:
            return _finish(ide.key(keys[act], ide=a.ide))
        if act == "focus":
            return _finish(ide.panel(a.text or a.name or "agent", ide=a.ide))
        if act == "cancel":
            return _finish(ide.stop(a.ide))
        if act in ("copy_response", "copy_error"):
            from jarvis.core.operator.clip import ClipOperator
            got = ide.problems(a.ide) if act == "copy_error" else ide.read_response(ide=a.ide)
            if not got.ok:
                return _finish(got)
            return _finish(ClipOperator(resources=hub.resources).set_text(got.message))
        if act == "read_error":
            return _finish(ide.problems(a.ide))
        if act == "rename":
            return _finish(ide.rename_symbol(a.text, ide=a.ide))
        if act in ("remove_attachment", "list_attachments"):
            return _finish(ide.attachments(a.ide, remove=(a.text or "first") if act == "remove_attachment" else ""))
        if act in ("find_symbol", "search", "open_project"):
            kind = {"find_symbol": "symbol", "search": "search", "open_project": "open_recent"}[act]
            return _finish(ide.goto(kind, a.text, ide=a.ide))
        if act == "docs":
            # the symbol is the one named, else the editor's selection (clipboard restored); docs open in the browser
            word = a.text
            if not word:
                import re
                from jarvis.core.operator.clip import ClipOperator
                clip = ClipOperator(resources=hub.resources)
                got = clip.copy_selection()
                sel = getattr(got.resource, "text", "") if got.ok else ""
                clip.restore()
                m = re.search(r"[A-Za-z_][\w.]*", sel or "")
                word = m.group(0)[:80] if m else ""
            if not word:
                raise RuntimeError("Which symbol? Select it first or tell me its name.")
            return _finish(hub.browser.official(word))
        raise RuntimeError(f"Unknown IDE action '{act}'.")


class PhoneOpInput(Contract):
    action: str = Field(description="tap | type | key | open_app | close_app | media | notifications | screenshot | push | "
                                    "dev | recent | previous_app | settings | volume | media_state | current_app | "
                                    "relaunch | installed | ui_tree | read_screen | find | focus | clear | swipe | "
                                    "open_notification | dismiss_notification | status | pull | open_url | pc_url | "
                                    "record | logs | clipboard | dictate | notify")
    target: str = Field(default="", description="control on the phone screen / app name / file path")
    text: str = Field(default="")
    key: str = Field(default="", description="back | home | recents | enter | volume_up | volume_down | wake | lock | ...")
    op: str = Field(default="", description="media op or dev op (logcat, packages, battery, install_apk, uninstall, open_url, ...)")
    arg: str = Field(default="")
    value: Optional[float] = Field(default=None, description="volume percent / seek seconds")
    app: str = Field(default="", description="app filter (notifications, settings, logs)")
    approved: bool = Field(default=False)


class PhoneOpTool(Tool):
    definition = _def("phone_op", "Operate the owner's authorized Android phone with typed operations: tap a control "
                      "by its text, type into a field, keys, open/close apps, media, notifications, screenshot, push a "
                      "file, allow-listed developer operations. Never unlocks or enters PINs.",
                      PhoneOpInput, timeout=60.0, tags=("phone", "android", "adb"))

    def run(self, a: PhoneOpInput) -> dict[str, Any]:
        from jarvis.core.operator.device import get_device_operator
        dev = get_device_operator()
        dev._res = _get_hub().resources
        act = a.action
        if act == "tap":
            return _finish(dev.tap(a.target, approved=a.approved))
        if act == "type":
            return _finish(dev.type_into(a.target, a.text))
        if act == "key":
            if (a.key or a.target) == "previous_app":
                return _finish(dev.previous_app())
            return _finish(dev.key(a.key or a.target))
        if act == "open_app":
            return _finish(dev.open_app(a.target))
        if act == "close_app":
            return _finish(dev.close_app(a.target))
        if act == "media":
            return _finish(dev.media(a.op or a.target, seconds=a.value or 0))
        if act == "notifications":
            if a.app or a.arg:
                return _finish(dev.notifications_filtered(app=a.app, sender=a.arg))
            return _finish(dev.notifications())
        if act == "screenshot":
            return _finish(dev.screenshot())
        if act == "push":
            return _finish(dev.push(a.target))
        if act == "dev":
            return _finish(dev.dev(a.op, a.arg, approved=a.approved))
        simple = {"recent": dev.recents, "previous_app": dev.previous_app, "media_state": dev.media_state,
                  "current_app": dev.current_app, "ui_tree": dev.ui_tree, "read_screen": dev.read_screen,
                  "clipboard": dev.clipboard}
        if act == "pc_url":
            got = dev.page_url()
            if not got.ok:
                return _finish(got)
            return _finish(_get_hub().browser.open(got.evidence["url"], new_tab=True))
        if act in simple:
            return _finish(simple[act]())
        if act == "settings":
            return _finish(dev.settings(a.target or "settings", app=a.app))
        if act == "volume":
            if a.value is None:
                raise RuntimeError("To what level?")
            return _finish(dev.volume(a.value))
        if act in ("relaunch", "installed"):
            return _finish(getattr(dev, act)(a.target or a.app))
        if act in ("find", "focus", "clear"):
            return _finish(getattr(dev, act)(a.target))
        if act == "dictate":
            out = dev.focus(a.target or "text field")
            if out.ok:
                out.message += " Say 'type …' and I'll type it into that box on the phone."
            return _finish(out)
        if act == "swipe":
            return _finish(dev.swipe(a.target or a.op or "up"))
        if act == "open_notification":
            return _finish(dev.open_notification(a.app or a.target))
        if act == "dismiss_notification":
            return _finish(dev.dismiss_notification(a.app or a.target))
        if act == "status":
            return _finish(dev.status(a.target or a.op or "battery"))
        if act == "pull":
            return _finish(dev.pull(a.target or "screenshot", when=a.arg or "latest"))
        if act == "open_url":
            url = a.target
            if not url:
                tab = _get_hub().browser.backend.active()
                url = getattr(tab, "url", "") if tab else ""
            if not url:
                raise RuntimeError("Which page? I can't see a URL in the browser.")
            return _finish(dev.open_url(url))
        if act == "record":
            return _finish(dev.record(a.op or a.target or "start"))
        if act == "logs":
            return _finish(dev.app_logs(a.app or a.target))
        if act == "notify":
            return _finish(dev.notify(a.text or a.target))
        raise RuntimeError(f"Unknown phone action '{act}'.")


# ------------------------------------------------------------------------------------------------- files
class FileOpInput(Contract):
    action: str = Field(description="search | open | reveal | open_folder | copy_path | duplicate | open_with | open_newest | "
                                    "open_latest_download | relocate | verify | verify_deleted | restore")
    target: str = Field(default="", description="'this' / 'that download' / a path / a file name")
    folder: str = Field(default="", description="folder to search (default: home, or Downloads for newest)")
    types: list[str] = Field(default_factory=list, description="pdf | images | videos | documents | ... or '.ext'")
    min_size: str = Field(default="", description="'20 MB'")
    max_size: str = Field(default="", description="'200 MB'")
    sort: str = Field(default="newest", description="newest | oldest | largest | smallest")
    limit: int = Field(default=10, ge=1, le=50)
    app: str = Field(default="", description="app for open_with ('edge', 'an editor')")
    destination: str = Field(default="", description="where the file should now be (verify)")
    folder_path: bool = Field(default=False, description="copy_path: the containing folder's path")


class FileOpTool(Tool):
    definition = _def("file_op", "Work with a specific file: filter by type/size and sort by size or age, reveal it in "
                      "Explorer, open its folder, copy its path, duplicate it, open it with a chosen app, open the newest "
                      "download, find a moved file again, verify a move or delete, restore from the Recycle Bin.",
                      FileOpInput, tags=("files",))

    def run(self, a: FileOpInput) -> dict[str, Any]:
        from jarvis.core.operator.files import TYPE_EXT, FileOperator, parse_size
        hub = _get_hub()
        f = FileOperator(resources=hub.resources)
        types = tuple(sorted({e for t in a.types for e in TYPE_EXT.get(t.lower().strip(), (t if t.startswith(".") else "",)) if e}))
        folder = a.folder
        if folder in ("here", "this folder", "current"):
            p, _ = f.resolve("")
            folder = str(p if p is not None and p.is_dir() else p.parent) if p is not None else ""
        act = a.action
        if act == "search":
            return _finish(f.search(folder, types, parse_size(a.min_size) or 0, parse_size(a.max_size) or 0,
                                    a.sort, a.limit, name_part=a.target))
        if act == "open":
            p, question = f.resolve(a.target)
            if p is None:
                raise RuntimeError(question)
            return _finish(f.open(p))
        if act in ("open_newest", "open_latest_download"):
            got = f.newest(folder if act == "open_newest" else "", types)
            if not got.ok:
                return _finish(got)
            from pathlib import Path
            return _finish(f.open(Path(got.evidence["path"])))
        if act == "reveal":
            return _finish(f.reveal(a.target))
        if act == "open_folder":
            return _finish(f.open_folder(a.target))
        if act == "copy_path":
            return _finish(f.copy_path(a.target, folder=a.folder_path))
        if act == "duplicate":
            return _finish(f.duplicate(a.target))
        if act == "open_with":
            return _finish(f.open_with(a.target, a.app))
        if act == "relocate":
            return _finish(f.relocate(a.target, folder))
        if act in ("verify", "verify_deleted"):
            return _finish(f.verify(a.target, "deleted" if act == "verify_deleted" else "moved", a.destination))
        if act == "restore":
            return _finish(f.restore_from_recycle_bin(a.target))
        raise RuntimeError(f"Unknown file action '{act}'.")


# ------------------------------------------------------------------------------------------------- system / workflows
class SystemOpInput(Contract):
    action: str = Field(description="status | models | audio | audit | running | restart_app | theme")
    what: str = Field(default="all", description="status: cpu | ram | gpu | disk | network | uptime | battery | all")
    op: str = Field(default="list", description="models: list | loaded | unload | warm; audio: list | switch")
    target: str = Field(default="", description="model name/role or audio device")


class SystemOpTool(Tool):
    definition = _def("system_op", "Measured PC and JARVIS state: CPU/RAM/GPU/disk/network/uptime, which local Ollama "
                      "models are installed or loaded (and unload/warm one), audio devices, and an audit of what this "
                      "task may use. Never looked up on the web.", SystemOpInput, tags=("system", "status"))

    def run(self, a: SystemOpInput) -> dict[str, Any]:
        from jarvis.core.operator.system import SystemOperator
        s = SystemOperator(registry=_get_hub().registry)
        if a.action == "status":
            return _finish(s.status(a.what))
        if a.action == "models":
            return _finish(s.models(a.op, a.target))
        if a.action == "audio":
            return _finish(s.audio(a.op, a.target))
        if a.action == "audit":
            return _finish(s.audit())
        hub = _get_hub()
        if a.action == "running":
            return _finish(s.running(a.target, tracker=hub.tracker))
        if a.action == "restart_app":
            return _finish(s.restart_app(a.target, tracker=hub.tracker, launch=hub.launch))
        if a.action == "theme":
            return _finish(s.theme(a.target or a.what))
        raise RuntimeError(f"Unknown system action '{a.action}'.")


class WorkflowOpInput(Contract):
    action: str = Field(description="run | preview | create | clone | enable | disable | schedule | cancel_schedule | list | "
                                    "run_at | trigger | event_trigger | list_triggers | cancel_trigger")
    name: str = Field(default="", description="workflow name")
    steps: list[str] = Field(default_factory=list, description="create: the owner's own commands, in order")
    new_name: str = Field(default="", description="clone: name of the copy")
    when: str = Field(default="", description="schedule: 'weekdays at 9', 'every 30 minutes'")
    override: str = Field(default="", description="run: a folder to use instead of the one in the saved steps")
    command: str = Field(default="", description="run_at / trigger: the owner's own command to run later")
    condition: str = Field(default="", description="trigger: app_opened | app_closed | phone_connected | "
                                                   "phone_disconnected | battery_below | battery_above | download_done")
    subject: str = Field(default="", description="trigger: the app name for app_opened / app_closed")
    threshold: Optional[float] = Field(default=None, description="trigger: battery percentage")
    event_name: str = Field(default="", description="event_trigger: registered event name")
    chat_id: str = Field(default="", description="event_trigger: verified direct chat JID")
    message_type: str = Field(default="", description="event_trigger: optional text/image/document/voice_note filter")
    ref: str = Field(default="", description="cancel_trigger: which one (a word from its command, its number, or empty)")


def _recent_commands(tasks, limit: int = 5) -> list[str]:
    """'save these steps as a workflow': the owner's own last commands that succeeded (oldest first), not questions
    about JARVIS, not workflow commands themselves, not the current request."""
    if tasks is None:
        return []
    from jarvis.core.tasks.scope import get_scope_manager
    me = getattr(get_scope_manager().current(), "task_id", "")
    out = []
    for t in tasks.recent(40):
        state = str(getattr(t.result, "state", "") or "")
        if t.request_id == me or state not in ("SUCCESS", "COMPLETED") or (t.intent or "") in (
                "workflow_op", "task_status", "recent_actions", "previous_outcome", "standing_rule"):
            continue
        out.append(t.raw_text)
        if len(out) >= limit:
            break
    return list(reversed(out))


class WorkflowOpTool(Tool):
    definition = _def("workflow_op", "Owner-authored workflows: save a named list of commands, preview it, run it "
                      "(each step goes through JARVIS normally and the run stops at the first failure), clone, enable, "
                      "disable, schedule or cancel a schedule.", WorkflowOpInput, tags=("workflow", "routine"))

    def run(self, a: WorkflowOpInput) -> dict[str, Any]:
        from jarvis.core.operator.workflows import get_workflows
        w = get_workflows()
        name = a.name or "default"
        act = a.action
        if act == "create":
            steps = a.steps or _recent_commands(_get_hub().tasks)
            if not steps:
                raise RuntimeError("Which steps? Tell me the commands in order, or run them first and then say "
                                   "'save these steps as a workflow'.")
            return _finish(w.create(name, steps))
        if act == "clone":
            return _finish(w.clone(name, a.new_name))
        if act == "preview":
            return _finish(w.preview(name))
        if act in ("enable", "disable"):
            return _finish(w.set_enabled(name, act == "enable"))
        if act == "schedule":
            return _finish(w.schedule(name, a.when))
        if act == "cancel_schedule":
            return _finish(w.cancel_schedule(a.name))
        if act == "list":
            return _finish(w.list())
        if act in ("run_at", "trigger", "event_trigger", "list_triggers", "cancel_trigger"):
            from jarvis.core.operator.automations import get_automations
            auto = get_automations()
            if act == "run_at":
                return _finish(auto.run_at(a.command, a.when))
            if act == "trigger":
                return _finish(auto.add_trigger(a.condition, a.command, a.subject, a.threshold))
            if act == "event_trigger":
                from jarvis.core.commands.provenance import owner_command
                from jarvis.core.operator.refs import OperatorOutcome
                if not owner_command.get():
                    return _finish(OperatorOutcome(False, "Only an authenticated owner request can save an event automation.",
                                                   needs="owner_authorization"))
                return _finish(auto.add_event_trigger(a.event_name, a.command,
                                                       chat_id=a.chat_id, message_type=a.message_type))
            if act == "list_triggers":
                return _finish(auto.list())
            return _finish(auto.cancel(a.ref))
        if act == "run":
            return _finish(w.run(name, override=a.override))
        raise RuntimeError(f"Unknown workflow action '{act}'.")


# ------------------------------------------------------------------------------------------------- dry run
class ExplainRouteInput(Contract):
    command: str = Field(description="the command to explain without running it")


class ExplainRouteTool(Tool):
    definition = _def("explain_route", "Dry run: say which capability a command would use, with which details, whether "
                      "it changes anything and whether it would ask first - without running it.", ExplainRouteInput,
                      risk=RiskLevel.READ_ONLY, read_only=True, tags=("dry_run", "explain"))

    def run(self, a: ExplainRouteInput) -> dict[str, Any]:
        import asyncio
        from jarvis.core.operator.refs import OperatorOutcome
        hub = _get_hub()
        router = hub.router
        if router is None:
            from jarvis.core.router.ollama import DisabledProvider
            from jarvis.core.router.router import SmartRouter
            router = SmartRouter(llm_provider=DisabledProvider())
        import concurrent.futures
        # its own short-lived thread and loop: works whether or not the caller is inside an event loop
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            d = pool.submit(lambda: asyncio.run(router.route(a.command))).result(timeout=30)
        return _finish(OperatorOutcome(True, describe_route(d, hub.registry, a.command), evidence={
            "intent": d.intent, "lane": getattr(d.lane, "value", str(d.lane)),
            "slots": {k: v for k, v in (d.slots or {}).items() if isinstance(v, (str, int, float, bool))}, "dry_run": True}))


def describe_route(d, registry, command: str) -> str:
    lane = getattr(d.lane, "value", str(d.lane))
    if lane == "REJECT":
        why = (d.clarification or "it was negated or is unsafe").rstrip(". ")
        return f"\"{command}\" would be refused: {why}. Nothing was done."
    if lane == "CLARIFY":
        return f"For \"{command}\" I would first ask: {d.clarification or 'which one you mean'}. Nothing was done."
    if lane == "LANE_2" or not d.intent:
        return (f"\"{command}\" needs thinking: the planner would break it into steps and show you anything that changes "
                "something before it runs. Nothing was done.")
    if d.intent == "compound":
        steps = ", then ".join(s.tool.replace("_", " ") for s in d.subcommands)
        return f"\"{command}\" would run {len(d.subcommands)} steps: {steps}. Nothing was done."
    details = ", ".join(f"{k} {v}" for k, v in (d.slots or {}).items()
                        if k not in ("qualifiers", "pronoun") and isinstance(v, (str, int, float)) and str(v))
    risk, asks = "", ""
    try:
        if registry is not None and registry.contains(d.intent):
            tool_def = registry.get(d.intent).definition
            r = str(tool_def.risk)
            risk = {"READ_ONLY": "only reads", "REVERSIBLE": "changes something you can undo",
                    "EXTERNAL_EFFECT": "has an effect outside this PC", "DESTRUCTIVE": "removes or overwrites something",
                    "PRIVILEGED": "needs administrator rights"}.get(r, r.lower())
            # the same policy the executor applies - not a guess
            from jarvis.security.policy.evaluator import PolicyEvaluator
            pol = PolicyEvaluator().evaluate_node(tool_def, dict(d.slots or {}))
            asks = " and would ask you to confirm first" if pol.requires_confirmation or pol.pauses_for_user else \
                " and would not be allowed" if pol.is_denied else ""
    except Exception:
        pass
    what = d.intent.replace("_", " ")
    return (f"\"{command}\" would use {what}" + (f" ({details})" if details else "") +
            (f"; it {risk}{asks}" if risk else "") + ". Nothing was done.")


def create_operator_tools(resolver=None, launcher=None, working_memory=None) -> list[Tool]:
    global _hub
    _hub = _Hub(resolver=resolver, launcher=launcher, working_memory=working_memory)
    return [WindowOpTool(), UIOpTool(), TextOpTool(), ClipboardOpTool(), ScreenOpTool(), DeliverOpTool(),
            BrowserOpTool(), VideoOpTool(), WatchOpTool(), IDEOpTool(), PhoneOpTool(), FileOpTool(),
            SystemOpTool(), WorkflowOpTool(), ExplainRouteTool()]
