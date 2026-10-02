"""Conversation context and compound commands: a short follow-up stands for the full command it refers to, an app named
inside a browser opens there, the reply says what really happened, and the new routes found by Blind-9 hold."""
from __future__ import annotations

import asyncio
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from jarvis.core.context.carryover import CarryOver
from jarvis.core.router.models import RouteLane


def _co(*history) -> CarryOver:
    co = CarryOver()
    for text, tool, slots in history:
        co.record(text, tool, slots)
    return co


OPEN_CALC = ("open calculator", "open_app", {"name": "calculator"})
VOLUME_30 = ("set volume to 30", "volume_set", {"percent": 30})


# ------------------------------------------------------------------------------------------------ carry-over rewrites
@pytest.mark.parametrize("history,said,full", [
    ([VOLUME_30], "make it 60", "set volume to 60"),
    ([VOLUME_30], "actually 40%", "set volume to 40"),
    ([VOLUME_30], "no i said 17", "set volume to 17"),
    ([VOLUME_30], "a bit louder", "increase the volume"),
    ([OPEN_CALC], "no, notepad", "open notepad"),
    ([OPEN_CALC], "sorry i meant paint", "open paint"),
    ([OPEN_CALC], "do the same for paint", "open paint"),
    ([OPEN_CALC], "and paint as well", "open paint"),
    ([OPEN_CALC], "close it", "close calculator"),
    ([OPEN_CALC], "open notepad too", "open notepad"),
    ([("open chrome", "open_app", {"name": "chrome"}), OPEN_CALC], "close the first one", "close chrome"),
    ([("open chrome", "open_app", {"name": "chrome"}), OPEN_CALC], "close both", "close chrome and close calculator"),
    ([("search for python tutorials", "search_web", {"query": "python tutorials"})], "now java tutorials",
     "search for java tutorials"),
    ([("what's the weather in chennai", "chat", {"query": "what's the weather in chennai"})], "and in pune?",
     "what's the weather in pune"),
    ([("remind me to call ravi at 5 pm", "set_reminder", {"text": "call ravi at 5 pm"})], "make it 6",
     "remind me to call ravi at 6 pm"),
    ([("open youtube", "open_website", {"url": "https://youtube.com", "title": "YouTube"})], "play lofi on it",
     "play lofi on YouTube"),
    ([("find report.pdf", "find_file", {"query": "report.pdf"})], "open it", "open report.pdf"),
    ([("send ravi i'm late", "send_whatsapp_message", {"recipient": "ravi", "message": "i'm late"})], "also to meena",
     "send meena i'm late"),
])
def test_follow_up_becomes_the_full_command(history, said, full):
    assert _co(*history).rewrite(said) == full


@pytest.mark.parametrize("history,said", [
    ([OPEN_CALC], "no, don't"),                 # a refusal is not a new target
    ([OPEN_CALC], "and then?"),
    ([OPEN_CALC], "thanks"),
    ([OPEN_CALC], "never mind"),
    ([OPEN_CALC], "delete it"),                 # destructive and sharing verbs never take "it" from context
    ([OPEN_CALC], "uninstall it"),
    ([OPEN_CALC], "send it to ravi"),
    ([OPEN_CALC], "make it 60"),                # no number to change
    ([OPEN_CALC], "5"),
    ([("call 9876543210", "android_dial", {"number": "9876543210"})], "make it 9876543211"),   # a new call is said in full
    ([("search for cats", "search_web", {"query": "cats"}), ], "close the first one"),          # results, not apps
    ([("open chrome", "open_app", {"name": "chrome"}), OPEN_CALC], "open the second one"),
    ([], "make it 60"),                         # nothing to refer to: unchanged, so the router asks
    ([], "close it"),
])
def test_unresolvable_or_unsafe_follow_ups_are_left_alone(history, said):
    assert _co(*history).rewrite(said) is None


def test_closed_apps_leave_the_ordinal_list_and_old_turns_expire(monkeypatch):
    co = _co(("open chrome", "open_app", {"name": "chrome"}), OPEN_CALC, ("close chrome", "close_app", {"name": "chrome"}))
    assert co.apps == ["calculator"]
    assert co.rewrite("close the first one") == "close calculator"
    import jarvis.core.context.carryover as m
    real = m.time.monotonic
    monkeypatch.setattr(m.time, "monotonic", lambda: real() + m.TTL_S + 1)
    assert co.rewrite("make it 60") is None and co.last() is None


# ------------------------------------------------------------------------------------------------ full stack
def _harness(tmp_path):
    from jarvis.tests.ai_harness import AIHarness
    from jarvis.tools.base import VerificationResult
    from tests.context.runner import CALLS, _recorder

    h = AIHarness(tmp_path, responder=lambda p: {"message": "OK."}, reachable=False)
    for tool in h.registry.list():
        tool.run = _recorder(tool)

    async def _ok(tool_name, result, arguments, cancellation):
        return VerificationResult(verified=True, confidence=1.0, evidence={"stub": True})
    h.service.verifier.verify = _ok
    return h, CALLS


async def _turns(h, calls, texts):
    out = []
    for text in texts:
        calls.clear()
        res = await h.say(text)
        out.append((list(calls), res))
        if res.state == "WAITING_CONFIRMATION":
            pending = h.service._pending_execution or {}
            out[-1] = ([(pending["tool"].definition.name, dict(pending["arguments"]))] if pending.get("tool") else [], res)
            h.service._pending_execution = None
    await h.close()
    return out


def test_volume_follow_ups_change_the_last_setting(tmp_path):
    h, calls = _harness(tmp_path)
    out = asyncio.run(_turns(h, calls, ["set volume to 30", "make it 60", "actually 40"]))
    assert [c[0][1]["percent"] for c, _ in out] == [30, 60, 40]


def test_ordinal_and_pronoun_refer_to_the_apps_just_opened(tmp_path):
    h, calls = _harness(tmp_path)
    out = asyncio.run(_turns(h, calls, ["open chrome", "open calculator too", "close the first one", "close it"]))
    assert out[1][0][0] == ("open_app", {"name": "calculator"})
    assert out[2][0][0] == ("close_app", {"name": "chrome"})
    assert out[3][0][0] == ("close_app", {"name": "calculator"})


def test_carried_over_send_still_asks_for_confirmation(tmp_path):
    h, calls = _harness(tmp_path)
    out = asyncio.run(_turns(h, calls, ["send ravi i'm late", "also to meena"]))
    tool, args = out[1][0][0]
    assert out[1][1].state == "WAITING_CONFIRMATION"
    assert tool == "send_whatsapp_message" and args["recipient"].lower() == "meena" and "late" in args["message"]


def test_unrelated_complete_command_ignores_context(tmp_path):
    h, calls = _harness(tmp_path)
    out = asyncio.run(_turns(h, calls, ["open notepad", "what time is it", "delete it"]))
    assert out[1][0][0][0] == "get_time"
    assert not any(c[0] == "delete_file" for c in out[2][0])   # never "delete notepad"


def test_app_in_a_browser_opens_in_that_browser_and_says_so(tmp_path):
    h, calls = _harness(tmp_path)
    for text in ("open calculator on chrome", "on calculator on chrome"):
        out = asyncio.run(_turns(*_harness(tmp_path), [text]))
        tool, args = out[0][0][0]
        assert tool == "open_website" and args["browser"] == "chrome" and "calculator" in args["url"]
        assert "calculator" in args["title"].lower() and "chrome" in args["title"].lower()
    asyncio.run(h.close())


def test_open_app_reply_never_claims_what_did_not_open():
    from jarvis.core.response.formatter import ResponseFormatter
    said = ResponseFormatter.format_verified_tool(
        "open_app", {"name": "Chrome", "canonical_name": "Chrome", "target": "chrome.exe", "requested": "calculator on chrome"})
    assert said.startswith("I opened Chrome, but not calculator")
    assert ResponseFormatter.format_verified_tool(
        "open_app", {"name": "Visual Studio Code", "target": "code.exe", "requested": "vs code"}) == "Visual Studio Code is open."


def test_opened_name_comes_from_the_launch_target():
    from jarvis.tools.system.app_resolver import opened_name
    assert opened_name(SimpleNamespace(path=r"C:\Program Files\Google\Chrome\Application\chrome.exe")) == "Chrome"
    assert opened_name(SimpleNamespace(path="")) == ""


def test_bare_pause_and_resume_control_the_media_when_nothing_is_running(tmp_path):
    h, calls = _harness(tmp_path)
    out = asyncio.run(_turns(h, calls, ["pause", "resume"]))
    assert out[0][0][0] == ("media_control", {"action": "pause"})
    assert out[1][0][0] == ("media_control", {"action": "play"})


# ------------------------------------------------------------------------------------------------ routes
@pytest.fixture(scope="module")
def router():
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter
    return SmartRouter(llm_provider=DisabledProvider())


@pytest.mark.parametrize("text,intent,slots", [
    ("find report.pdf", "find_file", {"query": "report.pdf"}),
    ("find my resume pdf", "find_file", {"query": "resume"}),
    ("find pdfs from last week", "find_file", {"query": "*"}),
    ("set an alarm for 7 am", "set_reminder", {"text": "at 7 am to wake up"}),
    ("wake me up at 8:15 am", "set_reminder", {"text": "at 8:15 am to wake up"}),
    ("what reminders do i have", "list_reminders", {}),
    ("after 45 minutes pause the music", "workflow_op", {"when": "in 45 minutes"}),
    ("show the scheduled jobs", "workflow_op", {"action": "list_triggers"}),
    ("go to the paint window", "switch_window", {"target": "paint"}),
    ("how much charge is on my phone", "android_status", {}),
    ("hey there", "wake_greeting", {}),
    ("zip main.py", "compress_files", {"path": "main.py"}),
    ("compress my project folder", "compress_files", {"path": "project"}),
    ("rleoad the page", "browser_quick_action", {"action": "reload"}),
    ("open calculator on chrome", "open_website", {"browser": "chrome"}),
])
def test_blind9_shapes_route(router, text, intent, slots):
    d = asyncio.run(router.route(text))
    assert d.intent == intent, (text, d.lane, d.intent, d.slots)
    for k, v in slots.items():
        assert d.slots.get(k) == v, (text, d.slots)


def test_search_query_drops_courtesy_words(router):
    d = asyncio.run(router.route("look up javascript promises for me"))
    assert d.slots["url"].endswith("q=javascript+promises")


@pytest.mark.parametrize("text", ["wipe the d drive", "erase my hard drive"])
def test_wiping_a_drive_is_refused(router, text):
    assert asyncio.run(router.route(text)).lane == RouteLane.REJECT


@pytest.mark.parametrize("text", ["stop that", "stop it", "cancel it"])
def test_stop_that_is_a_stop_not_dictation(router, text):
    d = asyncio.run(router.route(text))
    assert d.intent == "cancel_task", (text, d.lane, d.intent)


def test_zip_tool_writes_a_checked_archive_and_never_overwrites(tmp_path):
    from jarvis.tools.system.file_tools import CompressFilesTool
    f = tmp_path / "notes.txt"
    f.write_text("hello")
    tool = CompressFilesTool()
    first, second = tool.run({"path": str(f)}), tool.run({"path": str(f)})
    assert first.status == "SUCCESS" and Path(first.archive).name == "notes.zip"
    assert Path(second.archive).name == "notes (2).zip"
    with zipfile.ZipFile(first.archive) as zf:
        assert zf.read("notes.txt") == b"hello"
    assert tool.run({"path": str(tmp_path / "missing.txt")}).status == "NOT_FOUND"
