"""PC automation: multi-step commands, live voice typing, clipboard / screenshot-paste, phone connect, form autofill."""
from __future__ import annotations

import asyncio

import pytest

from jarvis.core.router.normalize import normalize_text
from jarvis.core.router.ollama import DisabledProvider
from jarvis.core.router.router import SmartRouter


@pytest.fixture(scope="module")
def router():
    return SmartRouter(llm_provider=DisabledProvider())


def route(router, text):
    return asyncio.run(router.route(text))


def steps(d):
    return [(s.tool, s.arguments) for s in d.subcommands]


# ------------------------------------------------------------------ multi-step commands
def test_open_app_then_type_keeps_the_typed_words(router):
    d = route(router, "Open Notepad and type Hello World, wait for me")
    assert d.intent == "compound" and d.lane.value == "LANE_0"
    assert steps(d) == [("open_app", {"name": "notepad"}),
                        ("dictate_text", {"text": "Hello World, wait for me", "target_app": "notepad"})]
    d = route(router, "open notepad and type I will come then we go")  # 'then' inside the text is not a new step
    assert steps(d)[1][1]["text"] == "I will come then we go"


def test_youtube_play_then_volume_is_two_steps(router):
    d = route(router, "open youtube and play lofi music then set volume to 30")
    assert steps(d) == [("play_youtube", {"query": "lofi music"}), ("volume_set", {"percent": 30})]
    single = route(router, "open youtube and play believer")
    assert single.intent == "play_youtube" and single.slots == {"query": "believer"}


@pytest.mark.parametrize("text,tools", [
    ("open chrome then go to gmail.com", ["open_app", "open_website"]),
    ("mute and open spotify", ["volume_mute", "open_app"]),
    ("set volume to 20 and open spotify", ["volume_set", "open_app"]),
    ("close chrome and edge", ["close_app", "close_app"]),
    ("select all and copy", ["pc_quick_action", "pc_quick_action"]),
    ("open notepad, type Dear Sir and press enter", ["open_app", "dictate_text", "keyboard_shortcut"]),
    ("open claude and start voice typing", ["open_app", "dictation_mode_control"]),
])
def test_multi_step_routing(router, text, tools):
    d = route(router, text)
    assert d.intent == "compound" and [s.tool for s in d.subcommands] == tools


def test_steps_that_need_thinking_go_to_the_planner(router):
    d = route(router, "research the best laptop under 60000 and make a note")
    assert d.lane.value == "LANE_2" and d.needs_planner


def test_not_split_messages_corrections_or_single_phrases(router):
    assert route(router, "Open Chrome, wait no, open Firefox.").slots == {"name": "firefox"}
    assert route(router, "search google for tom and jerry").intent == "open_website"
    assert route(router, "open chrome and calculator").slots == {"apps": ["chrome", "calculator"]}
    assert route(router, "tell mom I will come and then call dad").intent != "compound"


# ------------------------------------------------------------------ typing, clipboard, screenshot
@pytest.mark.parametrize("text,slots", [
    ("take a screenshot and paste it here", {"action": "screenshot_paste"}),
    ("take a screenshot and paste it in whatsapp", {"action": "screenshot_paste", "app": "whatsapp"}),
    ("copy this and paste in notepad", {"action": "copy_paste_to_app", "app": "notepad"}),
    ("paste in notepad", {"action": "paste_to_app", "app": "notepad"}),
    ("paste it", {"action": "paste"}),
    ("copy", {"action": "copy"}),
    ("select all", {"action": "select_all"}),
    ("undo that", {"action": "undo"}),
    ("copy screenshot to clipboard", {"action": "screenshot_to_clipboard"}),
])
def test_clipboard_and_screenshot_routing(router, text, slots):
    d = route(router, text)
    assert d.intent == "pc_quick_action" and d.slots == slots


def test_clipboard_words_are_not_typo_corrected():
    assert normalize_text("paste it")[1] == "paste it"  # was corrected to "pause it"
    assert normalize_text("find duplicate files in Downloads")[1] == "find duplicate files in downloads"


def test_type_text_and_dictation_start(router):
    d = route(router, "please type I'm Yoga.")
    assert d.intent == "dictate_text" and d.slots == {"text": "I'm Yoga"}
    assert route(router, "type hello on my phone").intent == "android_input"
    for text, target in [("start voice typing", None), ("type what i say in claude", "claude"), ("dictate in notepad", "notepad")]:
        d = route(router, text)
        assert d.intent == "dictation_mode_control" and d.slots.get("action") == "start"
        assert d.slots.get("target_app") == target


def test_dictation_types_speech_and_runs_edit_words(monkeypatch):
    from jarvis.tools.productivity import dictation as dm

    typed, keys = [], []
    monkeypatch.setattr(dm, "_type_unicode", typed.append)
    monkeypatch.setattr(dm, "_send_key", lambda vk: keys.append(("key", vk)))
    monkeypatch.setattr(dm, "_send_combo", lambda mods, vk: keys.append(("combo", tuple(mods), vk)))
    mgr = dm.DictationSessionManager()
    monkeypatch.setattr(dm, "_GLOBAL_DICTATION_MANAGER", mgr)
    mgr.refocus_target = lambda: True
    mgr.active_dictation_mode = True

    active, _ = dm.handle_dictation_utterance("open chrome")  # written, never executed
    assert active and typed[-1].lower().startswith("open chrome")
    dm.handle_dictation_utterance("how are you")
    assert typed[-1].startswith(" ")  # separated from the previous phrase
    assert dm.handle_dictation_utterance("new line") == (True, "New line.")
    assert keys[-1] == ("combo", (dm.VK_SHIFT,), dm.VK_RETURN)
    assert dm.handle_dictation_utterance("send it") == (True, "Sent.") and keys[-1] == ("key", dm.VK_RETURN)
    active, msg = dm.handle_dictation_utterance("stop typing")
    assert not active and not mgr.is_active() and "Stopped" in msg


def test_command_service_sends_voice_to_dictation_only_while_active(monkeypatch):
    from jarvis.core.commands.service import CommandService
    from jarvis.tools.productivity import dictation as dm

    mgr = dm.DictationSessionManager()
    monkeypatch.setattr(dm, "_GLOBAL_DICTATION_MANAGER", mgr)
    monkeypatch.setattr(dm, "handle_dictation_utterance", lambda text: (True, f"Typed: {text}"))

    class Req:
        request_id = "r1"
        text = "hello there"
        source = "voice"

    svc = CommandService.__new__(CommandService)
    assert svc._dictation(Req()) is None  # dictation off: normal command handling
    mgr.active_dictation_mode = True
    res = svc._dictation(Req())
    assert res.state == "SUCCESS" and res.message == "Typed: hello there"
    Req.source = "text"
    assert svc._dictation(Req()) is None  # typed commands in the UI are never dictated


def test_pc_quick_actions_are_safe_off_windows():
    import os
    from jarvis.tools.system.quick_actions import PCQuickActionTool, PCQuickInput
    for action in ("paste_to_app", "screenshot_paste", "copy_paste_to_app", "save"):
        PCQuickInput(action=action, app="notepad")  # accepted by the contract
    if os.name != "nt":
        assert PCQuickActionTool().run({"action": "paste_to_app", "app": "notepad"})["status"] == "FAILED"


# ------------------------------------------------------------------ phone connect
@pytest.mark.parametrize("text,slots", [
    ("connect my phone", {}),
    ("connect my phone at 192.168.1.23", {"address": "192.168.1.23"}),
    ("pair my phone with code 123456 at 192.168.1.23:37123", {"pairing_code": "123456", "pair_address": "192.168.1.23:37123"}),
])
def test_phone_connect_routing(router, text, slots):
    d = route(router, text)
    assert d.intent == "android_connect" and d.slots == slots


def test_phone_connect_leaves_transfers_and_ambiguity_alone(router):
    assert route(router, "send this file to my phone").intent != "android_connect"
    assert route(router, "Connect to my phone.").intent != "android_connect"


def _connector(monkeypatch, tmp_path, responses):
    from jarvis.connectors.android import scrcpy
    monkeypatch.setattr(scrcpy, "_PHONE_STATE", tmp_path / "phone.json")
    conn = scrcpy.AndroidScrcpyConnector.__new__(scrcpy.AndroidScrcpyConnector)
    conn.device_id = "old"
    calls = []

    def fake(args, timeout=5.0):
        calls.append((list(args), conn.device_id))
        return responses.get(args[0], (0, "", ""))
    conn._run_adb = fake
    return conn, calls


def test_connect_pairs_connects_and_remembers_the_address(monkeypatch, tmp_path):
    from jarvis.connectors.android import scrcpy
    conn, calls = _connector(monkeypatch, tmp_path, {
        "pair": (0, "Successfully paired to 192.168.1.23:37123", ""),
        "connect": (0, "connected to 192.168.1.23:5555", ""),
        "devices": (0, "List of devices attached\n192.168.1.23:5555 device product:x model:Pixel_7 device:y\n", ""),
    })
    out = conn._connect({"pairing_code": "123456", "pair_address": "192.168.1.23:37123", "address": "192.168.1.23"})
    assert out["status"] == "SUCCESS" and "Pixel 7" in out["message"]
    assert [c[0] for c in calls] == [["pair", "192.168.1.23:37123", "123456"], ["connect", "192.168.1.23:5555"], ["devices", "-l"]]
    assert all(dev is None for _, dev in calls) and conn.device_id == "old"  # server commands never target a device
    assert scrcpy._saved_wifi_address() == "192.168.1.23:5555"


def test_connect_explains_what_to_do(monkeypatch, tmp_path):
    conn, _ = _connector(monkeypatch, tmp_path, {"devices": (0, "List of devices attached\nABC123 unauthorized usb:1\n", "")})
    assert "Allow" in conn._connect({})["message"]
    conn, _ = _connector(monkeypatch, tmp_path, {"devices": (0, "List of devices attached\n", "")})
    msg = conn._connect({})["message"]
    assert "USB debugging" in msg and "Wireless debugging" in msg
    with pytest.raises(ValueError):
        conn._connect({"address": "192.168.1.23; reboot"})


def test_find_tool_looks_next_to_scrcpy(tmp_path):
    import os
    from jarvis.connectors.android.scrcpy import find_tool
    exe = "adb.exe" if os.name == "nt" else "adb"
    (tmp_path / exe).write_text("")
    assert find_tool("adb", near=str(tmp_path / "scrcpy")) == str(tmp_path / exe)


# ------------------------------------------------------------------ autofill
def test_autofill_routing(router):
    for text in ("fill this form with my details", "autofill this page", "fill in my details"):
        assert route(router, text).intent == "browser_autofill"


def test_autofill_needs_a_profile_and_reports_what_it_filled(monkeypatch, tmp_path):
    from jarvis.tools.system import autofill

    monkeypatch.setattr(autofill, "PROFILE_PATH", tmp_path / "profile.toml")
    seen = {}

    async def runner(js, args):
        seen["values"] = args[0]
        return {"filled": ["full_name", "email"], "skipped": 1}
    tool = autofill.BrowserAutofillTool(page_runner=runner)
    assert asyncio.run(tool.run({}))["status"] == "NEEDS_SETUP"
    (tmp_path / "profile.toml").write_text('[profile]\nfull_name = "Yogesh Kumar"\nemail = "y@example.com"\n', encoding="utf-8")
    out = asyncio.run(tool.run({}))
    assert out["status"] == "SUCCESS" and "Submit yourself" in out["message"] and "1 sensitive" in out["message"]
    assert seen["values"]["first_name"] == "Yogesh" and seen["values"]["last_name"] == "Kumar"


def test_autofill_script_in_a_real_browser():
    pw = pytest.importorskip("playwright.async_api")
    from jarvis.tools.system.autofill import FIELD_HINTS, FILL_JS

    html = """<form>
    <label for=n>Full Name</label><input id=n name=fullname>
    <input name=email type=email placeholder="Email address">
    <label>Mobile number <input name=mob type=tel></label>
    <label for=p>Password</label><input id=p type=password>
    <label for=o>Enter OTP</label><input id=o name=otp>
    <label for=c>College</label><input id=c name=college value="Already here">
    <label for=s>State</label><select id=s><option>Choose</option><option>Tamil Nadu</option></select>
    </form>"""
    values = {"full_name": "Yogesh K", "first_name": "Yogesh", "last_name": "K", "email": "y@example.com",
              "phone": "9876543210", "college": "RIT", "state": "Tamil Nadu"}

    async def main():
        async with pw.async_playwright() as p:
            try:
                browser = await p.chromium.launch()
            except Exception as exc:  # no browser installed on this machine
                pytest.skip(f"chromium not available: {exc}")
            page = await browser.new_page()
            await page.set_content(html)
            await page.evaluate(FILL_JS, [values, FIELD_HINTS])
            got = {sel: await page.eval_on_selector(sel, "e => e.value") for sel in ("#n", "[name=email]", "[name=mob]", "#p", "#o", "#c", "#s")}
            await browser.close()
            return got

    got = asyncio.run(main())
    assert got["#n"] == "Yogesh K" and got["[name=email]"] == "y@example.com" and got["[name=mob]"] == "9876543210"
    assert got["#p"] == "" and got["#o"] == ""  # never passwords or OTPs
    assert got["#c"] == "Already here" and got["#s"] == "Tamil Nadu"  # never overwrites; selects work
