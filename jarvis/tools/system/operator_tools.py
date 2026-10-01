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
    action: str = Field(default="focus", description="focus | maximize | minimize | restore | fullscreen | close | arrange | list")
    target: str = Field(default="", description="window description: 'previous', 'my editor', 'chrome', 'second chrome', a title word")
    targets: list[str] = Field(default_factory=list, description="windows for side-by-side/stack layouts")
    layout: str = Field(default="", description="left | right | top | bottom | side_by_side | stack | quadrants | center | next_monitor")
    launch: bool = Field(default=False, description="open the app first if no window of it is open")


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
                                           evidence={"count": len(wins)}))
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
        raise RuntimeError(f"Unknown window action '{a.action}'.")


# ------------------------------------------------------------------------------------------------- ui
class UIOpInput(Contract):
    action: str = Field(default="click", description="click | check | uncheck | type | read | find | scroll")
    target: str = Field(default="", description="control description: 'the send button', 'search box', 'the second result'")
    text: str = Field(default="", description="text to type (for action=type)")
    surface: str = Field(default="auto", description="auto | desktop | browser | phone | ide")
    window: str = Field(default="", description="window/app the control is in (default: the one in front)")
    direction: str = Field(default="down")
    n: int = Field(default=1, ge=1, le=50)
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
    action: str = Field(description="delete | select | copy | cut | replace | upper | lower | capitalize | undo | redo | insert | press")
    unit: str = Field(default="word", description="char | word | line | sentence | paragraph | all")
    n: int = Field(default=1, ge=1, le=200)
    direction: str = Field(default="back", description="back (before the cursor) | forward")
    find: str = Field(default="")
    replace_with: str = Field(default="")
    all: bool = Field(default=False, description="replace every occurrence")
    text: str = Field(default="", description="text to insert")
    key: str = Field(default="", description="named key action for press: bold, italic, underline, save, new_line, ...")


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
        if a.action == "insert":
            return _finish(op.insert(a.text, expect=cur))
        if a.action == "press":
            return _finish(op.press(a.key, expect=cur, repeat=a.n))
        req = EditRequest(op=a.action, unit=a.unit, n=a.n, direction="all" if a.all else a.direction, find=a.find,
                          replace_with=a.replace_with)
        return _finish(op.edit(req, expect=cur))


# ------------------------------------------------------------------------------------------------- clipboard / screen
class ClipboardOpInput(Contract):
    action: str = Field(default="read", description="read | copy_selection | set | restore")
    text: str = Field(default="")


class ClipboardOpTool(Tool):
    definition = _def("clipboard_op", "Read the clipboard as a typed resource, copy the current selection (waiting "
                      "for the clipboard to change), put text on it, or restore the previous clipboard.",
                      ClipboardOpInput, tags=("clipboard",))

    def run(self, a: ClipboardOpInput) -> dict[str, Any]:
        from jarvis.core.operator.clip import ClipOperator
        c = ClipOperator(resources=_get_hub().resources)
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
                                    "tab_list | back | forward | reload | results | open_result | read | find | scroll")
    target: str = Field(default="", description="url, site name or query; text to find")
    engine: str = Field(default="", description="search engine/site for action=search")
    which: str = Field(default="", description="tab: index, title word, 'first', 'last'")
    ordinal: int = Field(default=1, description="result number (-1 = last)")
    new_tab: bool = Field(default=False)
    direction: str = Field(default="down")
    n: int = Field(default=1, ge=1, le=20)


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
    action: str = Field(description="skip_ads | download_done | ide_done | cancel | list")
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
        if a.action == "cancel":
            n = wm.cancel(kind=a.kind)
            return _finish(OperatorOutcome(True, f"Stopped {n} watch{'es' if n != 1 else ''}." if n else "Nothing was being watched."))
        ws = wm.active()
        return _finish(OperatorOutcome(True, "; ".join(f"{w.kind}: {w.description}" for w in ws) or "Nothing is being watched.",
                                       evidence={"count": len(ws)}))


# ------------------------------------------------------------------------------------------------- IDE / phone
class IDEOpInput(Contract):
    action: str = Field(description="prompt | send | attach | accept | reject | open_file | command | key | read | status")
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
        raise RuntimeError(f"Unknown IDE action '{act}'.")


class PhoneOpInput(Contract):
    action: str = Field(description="tap | type | key | open_app | close_app | media | notifications | screenshot | push | dev")
    target: str = Field(default="", description="control on the phone screen / app name / file path")
    text: str = Field(default="")
    key: str = Field(default="", description="back | home | recents | enter | volume_up | volume_down | wake | lock | ...")
    op: str = Field(default="", description="media op or dev op (logcat, packages, battery, install_apk, uninstall, open_url, ...)")
    arg: str = Field(default="")
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
            return _finish(dev.key(a.key or a.target))
        if act == "open_app":
            return _finish(dev.open_app(a.target))
        if act == "close_app":
            return _finish(dev.close_app(a.target))
        if act == "media":
            return _finish(dev.media(a.op or a.target))
        if act == "notifications":
            return _finish(dev.notifications())
        if act == "screenshot":
            return _finish(dev.screenshot())
        if act == "push":
            return _finish(dev.push(a.target))
        if act == "dev":
            return _finish(dev.dev(a.op, a.arg, approved=a.approved))
        raise RuntimeError(f"Unknown phone action '{act}'.")


def create_operator_tools(resolver=None, launcher=None, working_memory=None) -> list[Tool]:
    global _hub
    _hub = _Hub(resolver=resolver, launcher=launcher, working_memory=working_memory)
    return [WindowOpTool(), UIOpTool(), TextOpTool(), ClipboardOpTool(), ScreenOpTool(), DeliverOpTool(),
            BrowserOpTool(), VideoOpTool(), WatchOpTool(), IDEOpTool(), PhoneOpTool()]
