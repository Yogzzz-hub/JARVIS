"""Universal Operator primitives on the in-memory desktop, browser and phone: each test checks the observable
effect (focus, window state, text buffer, clipboard, page state, phone calls) - not just a returned message."""
from __future__ import annotations

import pytest

from jarvis.core.operator.browser import BrowserOperator, FakeBrowser, WebUIAdapter
from jarvis.core.operator.clip import ClipOperator
from jarvis.core.operator.deliver import DeliverOperator
from jarvis.core.operator.device import DeviceOperator, FakeAdb
from jarvis.core.operator.dictate import LiveDictation
from jarvis.core.operator.ide import IDEOperator
from jarvis.core.operator.media import MediaOperator, parse_seconds
from jarvis.core.operator.platform import FakeDesktop, Monitor, parse_chord, set_desktop
from jarvis.core.operator.refs import ControlRef, app_family
from jarvis.core.operator.resources import OperatorResources
from jarvis.core.operator.screen import ScreenOperator
from jarvis.core.operator.text import EditRequest, TextOperator
from jarvis.core.operator.ui import FakeUIAdapter, UIOperator, UITarget
from jarvis.core.operator.watch import WatchManager
from jarvis.core.operator.windows import WindowTracker


def ctl(name, role, **kw):
    return ControlRef(resource_id=f"c:{name}:{role}", name=name, role=role, platform="fake", **kw)


@pytest.fixture
def desk():
    d = FakeDesktop(monitors=[Monitor(0, 0, 0, 1920, 1040, True), Monitor(1, 1920, 0, 3840, 1040)])
    set_desktop(d)
    yield d
    set_desktop(None)


@pytest.fixture
def world(desk):
    ed = desk.open("notepad.exe", "notes.txt - Notepad", editable=True, text="Meet on Tuesday at noon.")
    br = desk.open("chrome.exe", "YouTube - Google Chrome")
    ag = desk.open("antigravity.exe", "JARVIS - Antigravity", editable=True)
    me = desk.open("python.exe", "JARVIS EDGE")
    tr = WindowTracker(desk)
    for h in (ed, br, ag, me):
        desk.focus(h)
        tr.observe()
    return desk, tr, {"editor": ed, "browser": br, "ide": ag, "jarvis": me}


# ------------------------------------------------------------------------------------------------- platform
def test_chords_are_parsed_against_a_fixed_key_table():
    assert str(parse_chord("Ctrl+Shift+T")) == "ctrl+shift+t"
    assert str(parse_chord("control + esc")) == "ctrl+escape"
    for bad in ("ctrl+rm -rf", "hyper+x", "", "ctrl+notakey"):
        with pytest.raises(ValueError):
            parse_chord(bad)


def test_app_family_reads_process_and_title():
    assert app_family("chrome.exe", "Lo-fi - YouTube - Google Chrome") == "media"
    assert app_family("chrome.exe", "Inbox - Gmail") == "browser"
    assert app_family("antigravity.exe") == "ide"
    assert app_family("notepad.exe") == "editor"


# ------------------------------------------------------------------------------------------------- windows
def test_history_skips_jarvis_and_resolves_previous_and_families(world):
    desk, tr, h = world
    assert tr.current().hwnd == h["ide"]                       # JARVIS in front: the owner's window is the IDE
    assert tr.previous().hwnd == h["browser"]
    assert tr.resolve("go back to my editor").resource.hwnd == h["editor"]
    assert tr.resolve("the browser").resource.hwnd == h["browser"]
    assert tr.resolve("chrome window with youtube").resource.hwnd == h["browser"]
    assert not tr.resolve("excel").ok


def test_focus_and_states_are_verified(world):
    desk, tr, h = world
    ed = tr.resolve("notepad").resource
    assert tr.focus(ed).ok and desk.foreground().hwnd == h["editor"]
    assert tr.set_state(ed, "maximize").ok and desk.window_state(h["editor"]) == "maximized"
    assert tr.set_state(ed, "minimize").ok and desk.foreground().hwnd != h["editor"]
    assert tr.set_state(ed, "restore").ok and desk.window_state(h["editor"]) == "normal"


def test_ambiguous_windows_ask_instead_of_guessing(desk):
    desk.open("chrome.exe", "Docs - Google Chrome")
    desk.open("chrome.exe", "Mail - Google Chrome")
    tr = WindowTracker(desk)                                    # no history: two equal candidates
    out = tr.resolve("chrome")
    assert not out.ok and out.needs == "clarify" and len(out.candidates) == 2
    assert tr.resolve("second chrome").ok


def test_arrange_side_by_side_and_other_monitor(world):
    desk, tr, h = world
    a, b = tr.resolve("chrome").resource, tr.resolve("notepad").resource
    assert tr.arrange([a, b], "side by side").ok
    assert desk.window_rect(h["browser"]) == (0, 0, 960, 1040)
    assert desk.window_rect(h["editor"]) == (960, 0, 1920, 1040)
    assert tr.arrange([a], "next_monitor").ok and desk.window_rect(h["browser"])[0] >= 1920


# ------------------------------------------------------------------------------------------------- ui
def test_ui_target_parsing():
    t = UITarget.parse("the second Send button")
    assert (t.name, t.role, t.ordinal) == ("send", "button", 2)
    t = UITarget.parse("the checkbox next to remember me")
    assert t.role == "checkbox" and t.near == "remember me"
    assert UITarget.parse("search box").editable is True


def test_resolver_scores_asks_on_ties_and_respects_ordinals():
    a = FakeUIAdapter([ctl("Send", "button"), ctl("Send later", "button"), ctl("Save", "button"),
                       ctl("Save", "button"), ctl("Message", "textbox", editable=True)])
    ui = UIOperator()
    assert ui.find(a, "send button").resource.name == "Send"
    tie = ui.find(a, "save")
    assert not tie.ok and tie.needs == "clarify"
    assert ui.find(a, "second save button").ok
    assert not ui.find(a, "upload button").ok


def test_sensitive_and_consequential_controls(world):
    a = FakeUIAdapter([ctl("Password", "textbox", editable=True), ctl("Pay now", "button"),
                       ctl("I'm not a robot", "checkbox")])
    ui = UIOperator()
    assert ui.set_value(a, "password field", "hunter2").needs == "user" and not a.values
    out = ui.invoke(a, "pay now button")
    assert out.needs == "approve" and not a.invoked
    assert ui.invoke(a, "pay now button", approved=True).ok and a.invoked == ["Pay now"]
    assert ui.invoke(a, "not a robot checkbox").needs == "user"


def test_checkbox_toggle_is_verified():
    a = FakeUIAdapter([ctl("Remember me", "checkbox")])
    out = UIOperator().invoke(a, "remember me checkbox")
    assert out.ok and out.evidence["toggled"] is True


# ------------------------------------------------------------------------------------------------- text
def test_text_edits_change_the_buffer(world):
    desk, tr, h = world
    tr.focus(tr.resolve("notepad").resource)
    t = TextOperator(desk)
    buf = desk.buffer(h["editor"])
    assert t.edit(EditRequest("delete", "word", 2)).ok and buf.text == "Meet on Tuesday "
    assert t.edit(EditRequest("undo")).ok and buf.text == "Meet on Tuesday at noon."
    assert t.edit(EditRequest("replace", find="tuesday", replace_with="Wednesday")).ok
    assert buf.text == "Meet on Wednesday at noon."
    desk.buffer(h["editor"]).caret = len(buf.text)
    assert t.edit(EditRequest("select", "all")).ok and buf.selected() == buf.text


def test_typing_refuses_a_window_that_lost_focus(world):
    desk, tr, h = world
    ed = tr.resolve("notepad").resource
    tr.focus(ed)
    desk.focus(h["browser"])
    out = TextOperator(desk).insert("secret plans", expect=ed)
    assert not out.ok and out.needs == "target_lost" and "secret" not in desk.buffer(h["editor"]).text


def test_unknown_named_key_is_refused(world):
    desk, _tr, _h = world
    assert not TextOperator(desk).press("format_disk").ok


# ------------------------------------------------------------------------------------------------- dictation
def test_live_dictation_types_stable_words_and_reconciles(desk):
    from jarvis.core.desktop.dictation_controller import DictationController
    h = desk.open("notepad.exe", "n", editable=True)
    c = DictationController()
    c.set_test_target(hwnd=h)
    c.start()
    live = LiveDictation(c, desk)
    live.begin()
    assert live.feed("Dear") == "Dear"
    assert live.feed("Dear John I hope") == " John I hope"
    assert live.feed("Dear John I hope you are well question") == " you are well"   # 'question' waits for 'mark'
    assert live.finish("Dear John I hope you are well question mark") is True
    assert desk.buffer(h).text == "Dear John I hope you are well?"
    live.begin()
    live.feed("Its fine")
    assert live.finish("It is fine") and desk.buffer(h).text.endswith("It is fine")
    assert "Its" not in desk.buffer(h).text


def test_live_dictation_never_types_commands(desk):
    from jarvis.core.desktop.dictation_controller import DictationController, DictationState
    h = desk.open("notepad.exe", "n", editable=True, text="Hello there")
    c = DictationController()
    c.set_test_target(hwnd=h)
    c.start()
    live = LiveDictation(c, desk)
    live.begin()
    assert live.feed("delete the last") == ""
    assert live.finish("delete the last word") is False                       # the controller runs the edit
    assert desk.buffer(h).text == "Hello there"
    live.begin()
    live.feed("see you")
    assert live.finish("see you tomorrow stop typing")
    assert desk.buffer(h).text.endswith("see you tomorrow") and c.state == DictationState.IDLE


def test_live_dictation_pauses_when_target_is_lost(desk):
    from jarvis.core.desktop.dictation_controller import DictationController, DictationState
    h = desk.open("notepad.exe", "n", editable=True)
    c = DictationController()
    c.set_test_target(hwnd=h)
    c.start()
    desk.open("chrome.exe", "other")
    live = LiveDictation(c, desk)
    live.begin()
    assert live.feed("private words") == ""
    assert c.state == DictationState.PAUSED and "private words" in c._pending_buffer
    assert desk.buffer(h).text == ""


# ------------------------------------------------------------------------------------------------- clip / screen / deliver
def test_clipboard_copy_waits_for_change(world):
    desk, tr, h = world
    tr.focus(tr.resolve("notepad").resource)
    res = OperatorResources()
    c = ClipOperator(desk, res)
    TextOperator(desk).edit(EditRequest("select", "all"))
    out = c.copy_selection()
    assert out.ok and out.resource.text == "Meet on Tuesday at noon." and res.latest("CLIPBOARD") is out.resource
    desk.buffer(h["editor"]).anchor = None
    assert not c.copy_selection().ok


def test_screenshot_is_a_resource_and_pastes_into_the_ide(world, tmp_path):
    desk, tr, h = world
    res = OperatorResources()
    shot = ScreenOperator(desk, res, folder=tmp_path).capture()
    assert shot.ok and res.resolve("that screenshot")[0] is shot.resource
    prompt = ctl("Ask anything", "textbox", editable=True)
    adapter = FakeUIAdapter([prompt])
    adapter.on_invoke = None
    pasted = []

    def on_key(hwnd, chord):
        if str(chord) == "ctrl+v" and desk.clipboard_has_image():
            pasted.append(hwnd)
            adapter.controls.append(ctl("screenshot.png attachment", "button"))
    desk.on_key = on_key
    out = DeliverOperator(desk, tr).to_window(shot.resource, tr.resolve("antigravity").resource, adapter=adapter)
    assert out.ok and out.evidence["verified"] is True and pasted == [h["ide"]]


def test_delivery_without_visible_effect_is_reported_unconfirmed(world, tmp_path):
    desk, tr, _h = world
    res = OperatorResources()
    shot = ScreenOperator(desk, res, folder=tmp_path).capture()
    out = DeliverOperator(desk, tr).to_window(shot.resource, tr.resolve("chrome").resource,
                                              adapter=FakeUIAdapter([ctl("Comment", "textbox", editable=True)]))
    assert not out.ok and out.evidence["verified"] is False


def test_send_needs_approval(world, tmp_path):
    desk, tr, _h = world
    shot = ScreenOperator(desk, OperatorResources(), folder=tmp_path).capture()
    out = DeliverOperator(desk, tr).to_window(shot.resource, tr.resolve("antigravity").resource, send=True)
    assert out.needs == "approve" and not desk.clipboard_has_image()


def test_unknown_resource_type_asks():
    res = OperatorResources()
    ref, question = res.resolve("the screenshot")
    assert ref is None and "screenshot" in question


# ------------------------------------------------------------------------------------------------- browser / media / watch
def _browser():
    fb = FakeBrowser()
    fb.add_page("https://www.youtube.com/results?search_query=lofi", "lofi - YouTube",
                results=[{"title": "Lofi girl radio", "url": "https://www.youtube.com/watch?v=a"},
                         {"title": "Jazz lofi", "url": "https://www.youtube.com/watch?v=b"},
                         {"title": "Rain lofi", "url": "https://www.youtube.com/watch?v=c"}])
    fb.add_page("https://www.youtube.com/watch?v=c", "Rain lofi - YouTube",
                media={"paused": False, "t": 10.0, "d": 600.0, "rate": 1.0, "muted": False, "volume": 1.0, "ad": True},
                skip_visible=True,
                controls=[{"role": "button", "name": "Subscribe"}, {"role": "textbox", "name": "Search", "editable": True},
                          {"role": "textbox", "name": "Password", "type": "password", "editable": True}])
    fb.add_page("https://mail.google.com", "Inbox - Gmail")
    return fb


def test_tabs_results_and_navigation():
    fb = _browser()
    b = BrowserOperator(fb, OperatorResources())
    assert b.open("lofi", engine="youtube").ok
    assert b.open("gmail").ok
    assert b.tab("switch", "lofi").ok and "lofi" in fb.active().title
    third = b.open_result(3)
    assert third.ok and fb.active().url.endswith("v=c")
    assert b.nav("back").ok and "results" in fb.active().url
    assert b.tab("switch", "9").needs == "clarify"
    assert b.tab("close", "gmail").ok and len(fb.tabs()) == 1


def test_page_controls_never_fill_passwords():
    fb = _browser()
    b = BrowserOperator(fb, OperatorResources())
    b.open("https://www.youtube.com/watch?v=c")
    ad = WebUIAdapter(fb, fb.active())
    ui = UIOperator()
    assert ui.set_value(ad, "search box", "rain sounds").ok
    assert ui.set_value(ad, "password box", "x").needs == "user"


def test_media_seek_speed_and_skip_ad_verified():
    fb = _browser()
    b = BrowserOperator(fb, OperatorResources())
    b.open("https://www.youtube.com/watch?v=c")
    m = MediaOperator(b, FakeDesktop(), OperatorResources())
    assert m.act("seek_to", 90).ok and fb.tab_obj(fb.active()).media["t"] == 90
    assert m.act("seek_by", -30).ok and fb.tab_obj(fb.active()).media["t"] == 60
    assert m.act("rate", 1.5).ok and fb.tab_obj(fb.active()).media["rate"] == 1.5
    assert m.act("pause").ok and fb.tab_obj(fb.active()).media["paused"] is True
    assert m.act("skip_ad").ok
    assert not m.act("skip_ad").ok                               # nothing left to skip


def test_skip_ad_watch_is_scoped_and_ends_with_the_video():
    fb = _browser()
    b = BrowserOperator(fb, OperatorResources())
    b.open("https://www.youtube.com/watch?v=c")
    clock = [0.0]
    wm = WatchManager(clock=lambda: clock[0])
    assert wm.skip_ads(b).ok and len(wm.active()) == 1
    wm.tick()
    assert fb.tab_obj(fb.active()).media["ad"] is False
    fb.navigate(fb.active(), "https://mail.google.com")         # owner moved on: the watch ends itself
    clock[0] += 5
    wm.tick()
    assert wm.active() == []


def test_parse_seconds():
    assert parse_seconds("1:30") == 90 and parse_seconds("2 minutes") == 120
    assert parse_seconds("1 hour 5 minutes") == 3900 and parse_seconds("45 sec") == 45


# ------------------------------------------------------------------------------------------------- IDE / phone
def test_ide_prompt_write_and_send_are_observed(world):
    desk, tr, h = world
    box = ctl("Ask anything", "textbox", editable=True)
    adapter = FakeUIAdapter([box, ctl("Send", "button")])

    def on_invoke(c):
        if c.name == "Send":
            adapter.values[box.name] = ""
            adapter.controls.append(ctl("Stop generating", "button"))
    adapter.on_invoke = on_invoke
    ide = IDEOperator(desk, tr, adapter_factory=lambda w: adapter)
    out = ide.prompt("add login tests", ide="antigravity")
    assert out.ok and adapter.values[box.name] == "add login tests" and desk.foreground().hwnd == h["ide"]
    assert ide.send("antigravity").ok
    assert ide.generating("antigravity") is True


def test_ide_blocks_destructive_palette_commands(world):
    desk, tr, _h = world
    out = IDEOperator(desk, tr, adapter_factory=lambda w: FakeUIAdapter()).command("Git: Discard All Changes")
    assert not out.ok and out.needs == "user"


_PHONE_XML = ('<hierarchy><node text="WhatsApp" class="android.widget.TextView" clickable="true" bounds="[0,0][100,100]"/>'
              '<node text="" content-desc="Search" class="android.widget.EditText" bounds="[0,200][1000,260]"/>'
              '<node text="PIN" class="android.widget.EditText" password="true" bounds="[0,300][1000,360]"/></hierarchy>')


def test_phone_typed_operations_and_lock_guard():
    adb = FakeAdb(xml=_PHONE_XML)
    dev = DeviceOperator(adb, OperatorResources())
    assert dev.tap("whatsapp").ok and ["shell", "input", "tap", "50", "50"] in adb.calls
    assert dev.type_into("search box", "hello world").ok and adb.typed == ["hello%sworld"]
    assert dev.type_into("pin field", "1234").needs == "user"
    assert not dev.key("format").ok
    assert dev.dev("uninstall", "whatsapp").needs == "approve"
    assert not dev.dev("shell", "rm -rf /").ok
    adb.locked = True
    assert dev.tap("whatsapp").needs == "user"
    assert dev.key("volume_up").ok                               # media keys work on a locked phone


def test_phone_requires_authorized_device():
    dev = DeviceOperator(FakeAdb(authorized=False), OperatorResources())
    assert dev.ready().needs == "user"
