"""Reminders, website opening, phone control tools, the browser event loop and the AI web agent."""
from __future__ import annotations

import asyncio
import threading
from datetime import datetime

import pytest

from jarvis.tools.system.assistant_tools import (
    OpenWebsiteTool,
    ReminderService,
    SetReminderTool,
    ListRemindersTool,
    parse_reminder,
    set_reminder_service,
)


# ---------------------------------------------------------------- reminders
@pytest.mark.parametrize("text,task,due", [
    ("drink water in 10 minutes", "drink water", datetime(2026, 9, 25, 14, 10)),
    ("call mom at 6 pm", "call mom", datetime(2026, 9, 25, 18, 0)),
    ("submit the report tomorrow at 10", "submit the report", datetime(2026, 9, 26, 10, 0)),
    ("in half an hour to check the oven", "check the oven", datetime(2026, 9, 25, 14, 30)),
    ("take medicine at 5", "take medicine", datetime(2026, 9, 25, 17, 0)),
    ("pay the bill tonight", "pay the bill", datetime(2026, 9, 25, 20, 0)),
    ("meeting at 9:30 am", "meeting", datetime(2026, 9, 26, 9, 30)),
    ("buy milk", "buy milk", None),
])
def test_parse_reminder(text, task, due):
    got_task, got_due = parse_reminder(text, now=datetime(2026, 9, 25, 14, 0))
    assert got_task == task
    assert got_due == due


def test_reminder_tools_persist_and_fire(tmp_path):
    service = ReminderService(tmp_path / "reminders.json")
    set_reminder_service(service)
    try:
        out = SetReminderTool().run({"text": "stretch in 1 minute"})
        assert "remind you to stretch in 1 minute" in out["message"]
        listing = ListRemindersTool().run({})
        assert listing["count"] == 1 and "stretch" in listing["message"]
        assert service.pop_due() == []
        fired = service.pop_due(now=datetime.now().timestamp() + 120)
        assert [r.text for r in fired] == ["stretch"]
        assert ReminderService(tmp_path / "reminders.json").pending() == [], "fired state survives restart"
    finally:
        set_reminder_service(None)


# ---------------------------------------------------------------- websites
def test_open_website_normalizes_and_rejects_bad_urls():
    opened = []
    tool = OpenWebsiteTool(opener=opened.append)
    out = tool.run({"url": "wikipedia.org", "title": ""})
    assert opened == ["https://wikipedia.org"] and out["message"] == "Opened wikipedia.org."
    with pytest.raises(ValueError):
        tool.run({"url": "not a url at all"})


# ---------------------------------------------------------------- phone
class FakeAndroid:
    adb_bin = "adb"

    def __init__(self):
        self.calls = []

    def execute(self, action_name, arguments=None, action_id="act_direct", **kwargs):  # mirrors BaseConnector.execute
        self.calls.append((action_name, kwargs))
        if action_name == "capture_state":
            return {"status": "SUCCESS", "path": kwargs["destination"], "bytes": 1234}
        return {"status": "SUCCESS", "success": True, "message": f"{action_name} ok"}


@pytest.fixture
def android(monkeypatch):
    fake = FakeAndroid()

    class Manager:
        def get_connector(self, name):
            return fake if name == "android" else None

    monkeypatch.setattr("jarvis.tools.system.phone_tools.get_connector_manager", lambda: Manager())
    return fake


def test_phone_key_input_url_and_screenshot_tools(android):
    from jarvis.tools.system.phone_tools import PhoneInputTool, PhoneKeyTool, PhoneOpenUrlTool, PhoneScreenshotTool

    assert PhoneKeyTool().run({"key": "sleep"})["message"] == "Your phone is locked."
    PhoneKeyTool().run({"key": "volume_up", "times": 3})
    assert [c for c in android.calls if c[1].get("key") == "volume_up"] == [("key", {"key": "volume_up"})] * 3
    PhoneInputTool().run({"action": "text", "text": "hello"})
    assert android.calls[-1][0] == "input" and android.calls[-1][1]["text"] == "hello"
    with pytest.raises(ValueError):
        PhoneInputTool().run({"action": "tap"})
    PhoneOpenUrlTool().run({"url": "example.com"})
    assert android.calls[-1] == ("open_url", {"url": "example.com"})
    shot = PhoneScreenshotTool().run({})
    assert shot["data"]["path"].endswith(".png")


def test_phone_dial_resolves_contacts(android, monkeypatch):
    from jarvis.integrations.whatsapp.contact_resolver import ContactEntry, ContactResolver
    from jarvis.tools.system.phone_tools import PhoneDialTool

    monkeypatch.setattr(
        "jarvis.integrations.whatsapp.contact_resolver.ContactResolver.__init__",
        lambda self, contacts=None: setattr(self, "_contacts", [ContactEntry(jid="919999999999@s.whatsapp.net", display_name="Priya", phone_number="+91 99999 99999")]),
    )
    out = PhoneDialTool().run({"number": "Priya"})
    assert android.calls[-1] == ("dial", {"number": "+919999999999"})
    assert "Priya" in out["message"]
    PhoneDialTool().run({"number": "98765 43210"})
    assert android.calls[-1] == ("dial", {"number": "9876543210"})
    with pytest.raises(ValueError):
        PhoneDialTool().run({"number": "Nobody Known"})


def test_phone_tools_explain_missing_adb(monkeypatch):
    from jarvis.tools.system.phone_tools import PhoneKeyTool

    class NoAdb:
        adb_bin = None

    class Manager:
        def get_connector(self, name):
            return NoAdb()

    monkeypatch.setattr("jarvis.tools.system.phone_tools.get_connector_manager", lambda: Manager())
    with pytest.raises(RuntimeError, match="ADB was not found"):
        PhoneKeyTool().run({"key": "home"})


# ---------------------------------------------------------------- browser loop
def test_browser_loop_keeps_one_event_loop_across_worker_threads():
    from jarvis.core.computer.browser.loop import BrowserLoop

    loop_owner = BrowserLoop()
    seen = []

    async def which_loop():
        return id(asyncio.get_running_loop())

    def worker():
        seen.append(loop_owner.run(which_loop(), timeout=5))

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(seen)) == 1, "every browser call must run on the same loop (Playwright objects are loop-bound)"
    with pytest.raises(TimeoutError):
        loop_owner.run(asyncio.sleep(2), timeout=0.2)
    loop_owner.stop()


# ---------------------------------------------------------------- web agent
class FakePage:
    def __init__(self):
        self.url = "about:blank"
        self.actions = []
        self.stage = 0

    async def goto(self, url, **kwargs):
        self.url = url
        self.actions.append(("goto", url))

    async def evaluate(self, script, max_items):
        if self.stage == 0:
            return {"url": self.url, "title": "Search", "text": "Search results page", "sensitive": False,
                    "elements": [{"i": 1, "tag": "input", "type": "text", "label": "Search", "href": ""},
                                 {"i": 2, "tag": "a", "type": "", "label": "Sony WH-1000XM5 - price", "href": "/p/1"}]}
        if self.stage == 1:
            return {"url": self.url + "/p/1", "title": "Sony WH-1000XM5", "text": "Price: Rs 29,990. Buy now.",
                    "sensitive": False, "elements": [{"i": 1, "tag": "button", "type": "", "label": "Buy now", "href": ""}]}
        return {"url": self.url, "title": "Login", "text": "Sign in", "sensitive": True, "elements": []}

    async def click(self, selector, timeout=0):
        self.actions.append(("click", selector))
        self.stage += 1

    async def wait_for_load_state(self, *a, **k):
        pass


class FakeManager:
    def __init__(self, page):
        self.page = page

    async def get_active_page(self):
        return self.page


@pytest.mark.asyncio
async def test_web_agent_browses_and_reports_answer():
    from jarvis.core.computer.browser.loop import BrowserLoop
    from jarvis.tests.fake_ollama import FakeOllama
    from jarvis.tools.system.web_agent import WebTaskTool

    decisions = [
        {"thought": "open product", "action": "click", "index": 2, "text": "", "submit": False, "url": "", "answer": ""},
        {"thought": "found", "action": "done", "index": 0, "text": "", "submit": False, "url": "", "answer": "It costs Rs 29,990."},
    ]
    fake = FakeOllama(responder=lambda p: decisions.pop(0))
    page = FakePage()
    loop = BrowserLoop()
    tool = WebTaskTool(client=fake.client(planner_model="llama3.2"), browser_loop=loop, manager_factory=lambda: FakeManager(page))
    try:
        out = await tool.run({"goal": "find the price of Sony WH-1000XM5"})
        assert out["success"] and out["message"] == "It costs Rs 29,990."
        assert page.actions[0][0] == "goto" and "duckduckgo.com" in page.actions[0][1]
        assert ("click", '[data-jarvis-idx="2"]') in page.actions
        prompt = fake.chat_payloads()[0]["messages"][-1]["content"]
        assert "untrusted data" in prompt and "[2] a: Sony WH-1000XM5 - price" in prompt
    finally:
        loop.stop()


@pytest.mark.asyncio
async def test_web_agent_refuses_to_buy_and_stops_at_logins():
    from jarvis.core.computer.browser.loop import BrowserLoop
    from jarvis.tests.fake_ollama import FakeOllama
    from jarvis.tools.system.web_agent import WebTaskTool

    page = FakePage()
    page.stage = 1
    fake = FakeOllama(responder=lambda p: {"thought": "buy", "action": "click", "index": 1, "text": "", "submit": False, "url": "", "answer": ""})
    loop = BrowserLoop()
    tool = WebTaskTool(client=fake.client(), browser_loop=loop, manager_factory=lambda: FakeManager(page))
    try:
        out = await tool.run({"goal": "buy the headphones", "start_url": "shop.example.com"})
        assert not out["success"] and "Buy now" in out["message"]
        assert not [a for a in page.actions if a[0] == "click"], "never clicks purchase buttons"

        page.stage = 2
        out = await tool.run({"goal": "check my orders", "start_url": "shop.example.com"})
        assert not out["success"] and "login" in out["message"].lower()
    finally:
        loop.stop()


# ---------------------------------------------------------------- agent guards
@pytest.mark.asyncio
async def test_agent_rejects_unknown_tools_and_stops_on_repeats():
    from jarvis.core.agent import AgentRunner
    from jarvis.tests.ai_harness import HARDWARE
    from jarvis.tests.fake_ollama import FakeOllama
    from jarvis.tools.registry import ToolRegistry
    from jarvis.tools.system.app_resolver import AppResolver
    from jarvis.tools.system.native import create_tools
    from jarvis.core.executor.engine import ExecutionEngine

    registry = ToolRegistry()
    registry.discover(create_tools(AppResolver({}), HARDWARE))
    registry.finalize()
    decisions = [
        {"thought": "", "action": "call_tool", "tool": "format_hard_drive", "arguments": {}, "message": ""},
        {"thought": "", "action": "call_tool", "tool": "get_time", "arguments": {}, "message": ""},
        {"thought": "", "action": "call_tool", "tool": "get_time", "arguments": {}, "message": ""},
    ]
    fake = FakeOllama(responder=lambda p: decisions.pop(0) if decisions else {"thought": "", "action": "final_answer", "tool": "none", "arguments": {}, "message": "x"})
    agent = AgentRunner(registry, ExecutionEngine(), client=fake.client())
    outcome = await agent.run("what time is it right now")
    assert outcome.status == "done"
    tools = [s.tool for s in outcome.steps]
    assert tools == ["format_hard_drive", "get_time"], "hallucinated tool rejected, repeated call stopped"
    assert outcome.steps[0].success is False

    offline = AgentRunner(registry, ExecutionEngine(), client=FakeOllama(reachable=False).client())
    assert (await offline.run("anything")).status == "unavailable"
