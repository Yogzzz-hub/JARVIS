"""Vision computer control: find & click anything on screen, multi-step desktop goals, safety stops."""
from __future__ import annotations

import json

import pytest

from jarvis.tests.fake_ollama import FakeOllama
from jarvis.tools.system import input_control
from jarvis.tools.system.computer_use import ComputerTaskTool, ScreenClickTool, accessible_name, risky_step


class FakeInput:
    def __init__(self):
        self.events = []

    def size(self):
        return (2732, 1536)   # a 200% laptop screen; screenshots are sent at 1366 wide

    def moveTo(self, x, y, duration=0):
        pass

    def click(self, x, y, clicks=1, interval=0, button="left"):
        self.events.append(("click", x, y, clicks, button))

    def write(self, text, interval=0):
        self.events.append(("type", text))

    def press(self, key):
        self.events.append(("key", key))

    def hotkey(self, *keys):
        self.events.append(("key", "+".join(keys)))

    def scroll(self, n):
        self.events.append(("scroll", n))


@pytest.fixture
def fake_input():
    fake = FakeInput()
    input_control.set_backend(fake)
    yield fake
    input_control.set_backend(None)


def _shot():
    return "aW1n", 2.0, (1366, 768)


def _client(replies):
    it = iter(replies)
    fake = FakeOllama(models=["llama3.2:latest", "qwen2.5vl:3b"], responder=lambda p: next(it))
    return fake, fake.client(vision_model="qwen2.5vl:3b")


@pytest.mark.asyncio
async def test_screen_click_scales_vision_coordinates_to_the_real_screen(fake_input):
    fake, client = _client([{"found": True, "x": 600, "y": 300, "label": "Save"}])
    tool = ScreenClickTool(client=client, capture_fn=_shot)
    tool.use_accessibility = False
    try:
        res = await tool.run({"target": "the blue save icon"})
    finally:
        await client.aclose()
    assert res["success"] and fake_input.events == [("click", 1200, 600, 1, "left")]
    assert fake.chat_payloads()[-1]["messages"][0]["images"] == ["aW1n"]


@pytest.mark.asyncio
async def test_screen_click_reports_when_not_visible(fake_input):
    _fake, client = _client([{"found": False, "x": 0, "y": 0, "label": ""}])
    tool = ScreenClickTool(client=client, capture_fn=_shot)
    tool.use_accessibility = False
    try:
        res = await tool.run({"target": "the Export button"})
    finally:
        await client.aclose()
    assert not res["success"] and "can't see" in res["message"] and not fake_input.events


def _step(action, x=0, y=0, label="", text="", keys="", answer=""):
    return {"thought": "", "action": action, "x": x, "y": y, "target_label": label, "text": text, "keys": keys, "answer": answer}


@pytest.mark.asyncio
async def test_computer_task_runs_steps_until_done(fake_input):
    _fake, client = _client([
        _step("click", 100, 50, "Search box"),
        _step("type", text="dark mode"),
        _step("key", keys="enter"),
        _step("done", answer="Dark mode is on."),
    ])
    tool = ComputerTaskTool(client=client, capture_fn=_shot, settle_s=0)
    try:
        res = await tool.run({"goal": "in Settings turn on dark mode"})
    finally:
        await client.aclose()
    assert res["success"] and res["message"] == "Dark mode is on."
    assert fake_input.events == [("click", 200, 100, 1, "left"), ("type", "dark mode"), ("key", "enter")]


@pytest.mark.asyncio
async def test_computer_task_stops_before_risky_clicks_and_secrets(fake_input):
    _fake, client = _client([_step("click", 10, 10, "Send email")])
    tool = ComputerTaskTool(client=client, capture_fn=_shot, settle_s=0)
    try:
        res = await tool.run({"goal": "write a draft to Priya about the report"})
    finally:
        await client.aclose()
    assert not res["success"] and "confirm yourself" in res["message"] and not fake_input.events

    _fake, client = _client([_step("type", label="Password", text="hunter2")])
    tool = ComputerTaskTool(client=client, capture_fn=_shot, settle_s=0)
    try:
        res = await tool.run({"goal": "log in to the portal"})
    finally:
        await client.aclose()
    assert not res["success"] and "password" in res["message"] and not fake_input.events


@pytest.mark.asyncio
async def test_computer_task_gives_up_when_stuck(fake_input):
    _fake, client = _client([_step("click", 10, 10, "Next")] * 5)
    tool = ComputerTaskTool(client=client, capture_fn=_shot, settle_s=0)
    try:
        res = await tool.run({"goal": "finish the wizard"})
    finally:
        await client.aclose()
    assert not res["success"] and "same step" in res["message"]


def test_accessible_names_and_risk_words():
    assert accessible_name("the Save button") == "Save"
    assert accessible_name("the blue download icon") == ""
    assert risky_step("Send", "write an email to Rahul") == "Send"
    assert risky_step("Send", "send the email to Rahul") is None
    assert risky_step("Next", "anything") is None
    assert input_control.parse_keys("Control + Shift + Escape") == ["ctrl", "shift", "esc"]


@pytest.mark.asyncio
@pytest.mark.parametrize("text,intent", [
    ("click the save button", "screen_click"),
    ("right click the desktop", "screen_click"),
    ("use my computer to turn on dark mode in settings", "computer_task"),
    ("in excel make the first row bold", "computer_task"),
    ("press enter", "keyboard_shortcut"),
    ("in 10 minutes remind me to call mom", "set_reminder"),
])
async def test_screen_control_routing(text, intent):
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter
    from jarvis.memory.working_memory import WorkingMemory

    dec = await SmartRouter(llm_provider=DisabledProvider(), working_memory=WorkingMemory()).route(text)
    assert dec.intent == intent, (text, dec)


@pytest.mark.asyncio
async def test_continue_resumes_a_paused_browser_task():
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter
    from jarvis.memory.working_memory import WorkingMemory
    from jarvis.tools.system.web_agent import WebTaskTool

    router = SmartRouter(llm_provider=DisabledProvider(), working_memory=WorkingMemory())
    dec = await router.route("I have logged in")
    assert dec.intent == "web_task" and dec.slots == {"resume": True}
    WebTaskTool._pending_goal = "check my train booking"
    try:
        dec = await router.route("continue")
        assert dec.intent == "web_task" and dec.slots == {"resume": True}
    finally:
        WebTaskTool._pending_goal = ""
