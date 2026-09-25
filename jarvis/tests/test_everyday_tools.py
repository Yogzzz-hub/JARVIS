"""Everyday offline tools, voice shortcuts, "do that again", relative volume intents (end to end through the service)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

import pytest
from pydantic import Field

from jarvis.tests.ai_harness import AIHarness
from jarvis.tools.base import Contract, RiskLevel, Tool, ToolDefinition
from jarvis.tools.system import everyday_tools as ev
from jarvis.tools.system.assistant_tools import ReminderService, set_reminder_service


# ------------------------------------------------------------------ pure functions
@pytest.mark.parametrize("text, expected", [
    ("what is 25 times 4", "100"),
    ("what is 25 * 4 + 10", "110"),
    ("calculate 15% of 240", "36"),
    ("square root of 144", "12"),
    ("what's 2 to the power of 10", "1,024"),
    ("what is 7 factorial", "5,040"),
    ("100 km to miles", "62.1371 miles"),
    ("convert 30 celsius to fahrenheit", "86°F"),
    ("5 kg in pounds", "11.0231 pounds"),
    ("2 gb in mb", "2,048 mb"),
    ("12 is what percent of 48", "25%"),
    ("what's 10% tip on 500", "550 in total"),
    ("is 2028 a leap year", "Yes"),
    ("10 divided by 0", "division by zero"),
])
def test_quick_answer_values(text, expected):
    assert expected in ev.quick_answer(text)


def test_quick_answer_dates_are_relative_to_now():
    now = datetime(2026, 12, 20, 10, 0)
    assert ev.quick_answer("how many days until christmas", now).startswith("5 days")
    assert "Wednesday, 30 December 2026" in ev.quick_answer("what day is it in 10 days", now)
    assert ev.quick_answer("what day is january 1", now).endswith("is a Friday.")


@pytest.mark.parametrize("text", ["what is photosynthesis", "open chrome", "what time is it", "what is 5", "set volume to 40",
                                  "remind me in 10 minutes", "delete file 1-2", "how are you"])
def test_quick_answer_leaves_other_requests_alone(text):
    assert ev.quick_answer(text) is None


def test_safe_eval_rejects_code():
    for expr in ("__import__('os')", "open('x')", "(1).__class__", "9**9**9"):
        with pytest.raises(Exception):
            ev.safe_eval(expr)


def test_split_steps_turns_descriptions_into_commands():
    assert ev.split_steps("opens notion and plays lofi music") == ["open notion", "play lofi music"]
    assert ev.split_steps("open chrome, open spotify then set volume to 20") == ["open chrome", "open spotify", "set volume to 20"]
    assert ev.split_steps("send hi and bye to mom") == ["send hi and bye to mom"]


def test_password_is_strong_and_never_returned():
    copied = []
    tool = ev.GeneratePasswordTool(clipboard=lambda pw: copied.append(pw) or True)
    out = tool.run({"length": 20})
    pw = copied[0]
    assert len(pw) == 20 and any(c.isdigit() for c in pw) and any(c.isupper() for c in pw) and any(c.islower() for c in pw)
    assert pw not in json.dumps(out)


def test_stopwatch_with_fake_clock():
    now = [100.0]
    sw = ev.StopwatchTool(clock=lambda: now[0])
    sw.run({"action": "start"})
    now[0] += 65
    assert "Lap 1: 1 minute 5 seconds" in sw.run({"action": "lap"})["message"]
    now[0] += 5
    assert sw.run({"action": "stop"})["data"]["seconds"] == 70
    assert sw.run({"action": "reset"})["message"] == "Stopwatch reset."


def test_memory_refuses_secrets(tmp_path):
    ev.set_store(ev.PersonalStore(tmp_path / "p.db"))
    try:
        out = ev.RememberFactTool().run({"fact": "my bank password is hunter2"})
        assert out["data"]["stored"] is False and ev.get_store().facts() == []
    finally:
        ev.set_store(None)


# ------------------------------------------------------------------ through the real service
class FakeVolume:
    def __init__(self):
        self.level = 40


class _Pct(Contract):
    percent: int = Field(ge=0, le=100)


class _PctOut(Contract):
    percent: float


class _Empty(Contract):
    pass


class VolumeGet(Tool):
    definition = ToolDefinition(name="volume_get", description="Read volume", input_model=_Empty, output_model=_PctOut,
                                read_only=True, risk=RiskLevel.READ_ONLY)

    def __init__(self, vol):
        self.vol = vol

    def run(self, arguments):
        return {"percent": self.vol.level}


class VolumeSet(Tool):
    definition = ToolDefinition(name="volume_set", description="Set volume", input_model=_Pct, output_model=_PctOut,
                                read_only=False, risk=RiskLevel.REVERSIBLE)

    def __init__(self, vol):
        self.vol = vol

    def run(self, arguments):
        self.vol.level = arguments["percent"] if isinstance(arguments, dict) else arguments.percent
        return {"percent": self.vol.level}


@pytest.fixture
async def stack(tmp_path, monkeypatch):
    ev.set_store(ev.PersonalStore(tmp_path / "jarvis.db"))
    set_reminder_service(ReminderService(tmp_path / "reminders.json"))
    vol = FakeVolume()
    h = AIHarness(tmp_path, responder=lambda p: "OK.", extra_tools=[VolumeGet(vol), VolumeSet(vol)])
    for alias in ("volume_up", "volume_down", "mute", "unmute"):
        h.registry.register_alias(alias, "volume_set")
    h.vol = vol
    import jarvis.tools.system.native as native
    monkeypatch.setattr(native, "volume", lambda percent=None: vol.level)  # the verifier reads the volume back
    yield h
    await h.close()
    ev.set_store(None)
    set_reminder_service(None)


async def test_quick_answers_are_instant_and_offline(stack):
    r = await stack.say("what is 25 times 4")
    assert r.state == "SUCCESS" and "100" in r.message
    assert not stack.fake.chat_payloads()  # no LLM call


async def test_todo_list_round_trip(stack):
    assert "Added 'buy milk'" in (await stack.say("add buy milk to my to-do list")).message
    await stack.say("add call the plumber to my todo list")
    listed = (await stack.say("show my to-do list")).message
    assert "1. buy milk" in listed and "2. call the plumber" in listed
    assert "Marked 'buy milk' as done" in (await stack.say("mark buy milk as done")).message
    assert "buy milk" not in (await stack.say("what's on my to-do list")).message


async def test_remember_recall_and_rag_index(stack):
    assert (await stack.say("remember that my car is parked on level 2 near pillar B7")).state == "SUCCESS"
    assert "level 2" in (await stack.say("where did i park")).message
    assert "level 2" in (await stack.say("what do you remember about my car")).message
    hits = stack.knowledge.knowledge_engine.search("where is the car parked pillar", limit=3)
    assert any("pillar B7" in h.snippet for h in hits)
    assert "forgotten" in (await stack.say("forget that my car is parked on level 2")).message
    assert "don't have anything" in (await stack.say("what do you remember about my car")).message


async def test_voice_shortcut_runs_every_step_through_the_router(stack):
    r = await stack.say("when i say movie time, set volume to 30 and flip a coin")
    assert r.state == "SUCCESS" and "movie time" in r.message
    r = await stack.say("Movie time!")
    assert r.state == "SUCCESS"
    assert stack.vol.level == 30 and ("heads" in r.message or "tails" in r.message)
    assert "movie time" in (await stack.say("list my shortcuts")).message
    await stack.say("delete the shortcut movie time")
    assert "no shortcuts" in (await stack.say("list my shortcuts")).message


async def test_do_that_again_repeats_last_command(stack):
    await stack.say("add water plants to my to-do list")
    r = await stack.say("do that again")
    assert r.state == "SUCCESS"
    assert [t for _, t, _ in ev.get_store().todos()] == ["water plants", "water plants"]


async def test_relative_volume_and_mute_reach_a_real_tool(stack):
    stack.vol.level = 40
    assert (await stack.say("can't hear anything from the speakers")).state == "SUCCESS"
    assert stack.vol.level == 50
    assert (await stack.say("total silence please")).state == "SUCCESS"
    assert stack.vol.level == 0


async def test_timer_is_a_reminder_with_a_clear_message(stack):
    r = await stack.say("set a timer for 5 minutes")
    assert r.state == "SUCCESS" and "Timer set for 5 minutes" in r.message


async def test_recycle_bin_always_needs_confirmation(stack):
    r = await stack.say("empty the recycle bin")
    assert r.state == "WAITING_CONFIRMATION"


def test_command_history_reads_the_requests_table(tmp_path):
    db = tmp_path / "jarvis.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE requests (id INTEGER PRIMARY KEY, request_id TEXT, payload TEXT)")
    for text in ("open chrome", "what is 2+2", "what did i ask you"):
        con.execute("INSERT INTO requests(request_id, payload) VALUES (?, ?)", ("r", json.dumps({"text": text})))
    con.commit()
    con.close()
    ev.set_store(ev.PersonalStore(db))
    try:
        msg = ev.CommandHistoryTool().run({"limit": 5})["message"]
        assert "'what is 2+2'; 'open chrome'" in msg and "what did i ask" not in msg
    finally:
        ev.set_store(None)
