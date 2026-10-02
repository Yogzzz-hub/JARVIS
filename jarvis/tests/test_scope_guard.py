"""Scope, interaction and control guards (jarvis/core/router/scope.py and the router post-steps).

Each case is a construction, not a sentence: a broad or pronoun target, a payment / CAPTCHA / lock-screen / OTP step,
composing versus typing, a definition question, and the phone/Tanglish/control shapes that must keep their own tool.
"""
from __future__ import annotations

import pytest

from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.router.models import RouteLane
from jarvis.core.router.router import SmartRouter


async def _route(text: str):
    return await SmartRouter().route(CommandRequest(text=text))


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [
    "delete everything on my desktop",
    "wipe my documents folder",
    "delete all my files and then shut down",
    "uninstall that one",
    "delete my browser history",
])
async def test_broad_or_unresolved_targets_are_asked_about(text):
    d = await _route(text)
    assert d.lane == RouteLane.CLARIFY, (text, d.lane, d.intent, d.slots)


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [
    "click the buy now button",
    "solve the captcha on this page",
    "unlock my phone without the pin",
    "read the otp from my messages",
])
async def test_payments_security_checks_and_lock_screens_are_refused(text):
    d = await _route(text)
    assert d.lane == RouteLane.REJECT, (text, d.lane, d.intent, d.slots)


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [
    "write my college assignment",
    "give me 3 startup ideas",
    "what's a browser cookie",
    "what is an ip address",
])
async def test_questions_and_compose_requests_run_no_tool(text):
    d = await _route(text)
    assert d.lane == RouteLane.LANE_2 and d.intent is None and not d.needs_planner, (text, d.lane, d.intent)


@pytest.mark.asyncio
@pytest.mark.parametrize("text,intent,slots", [
    ("close all notepad windows", "close_app", {"name": "notepad"}),
    ("install everything", "install_software", {"name": "everything"}),
    ("open everything", "open_app", {"name": "everything"}),
    ("i need chrome for my class, can you install it", "install_software", {"name": "chrome"}),
    ("i think i downloaded my medical prescription last week, where is it", "find_file", {"query": "medical prescription"}),
    ("create a folder named reports on the desktop", "create_folder", {"path": "Desktop/reports"}),
    ("generate a 16 character password", "generate_password", {"length": 16}),
    ("press volume down on my phone 3 times", "android_key", {"key": "volume_down", "times": 3}),
    ("press back on my phone", "android_back", {}),
    ("lock my phone", "android_key", {"key": "sleep"}),
    ("mute the call", "phone_op", {"action": "key", "key": "mute"}),
    ("screenshot eduda", "take_screenshot", {}),
    ("next paatu", "media_control", {}),
    ("what's my ip address", "network_info", {}),
])
async def test_specific_targets_keep_their_tool(text, intent, slots):
    d = await _route(text)
    assert d.lane in (RouteLane.LANE_0, RouteLane.LANE_1) and d.intent == intent, (text, d.lane, d.intent, d.slots)
    for k, v in slots.items():
        assert d.slots.get(k) == v, (text, d.slots)


@pytest.mark.asyncio
async def test_tanglish_next_song_is_the_next_track():
    d = await _route("next paatu")
    assert d.intent == "media_control" and str(d.slots.get("action")).startswith("next")


@pytest.mark.asyncio
async def test_pause_is_not_stop():
    d = await _route("paatu niruthu")
    assert d.intent == "media_control" and d.slots.get("action") == "pause"


@pytest.mark.asyncio
async def test_cancel_current_is_scoped_to_the_foreground_task():
    d = await _route("cancel the current task")
    assert d.intent == "cancel_task" and d.slots.get("scope") == "foreground"


@pytest.mark.asyncio
async def test_a_leading_imperative_is_a_step_not_a_remark():
    d = await _route("close chrome, then lock the pc")
    assert d.lane == RouteLane.LANE_2 and d.needs_planner


def test_shortcut_times_is_bounded():
    from pydantic import ValidationError
    from jarvis.tools.system.keyboard_tools import ShortcutInput
    assert ShortcutInput(key="down", times=3).times == 3
    with pytest.raises(ValidationError):
        ShortcutInput(key="down", times=50)



def test_approving_a_pending_action_grants_only_that_actions_capability():
    from types import SimpleNamespace
    from jarvis.core.commands.service import CommandService
    from jarvis.security.policy.scope import TOOL_CAPABILITY_REQUIREMENTS, get_task_scope_manager
    mgr = get_task_scope_manager()
    scope = mgr.create_scope("approve-test", set())
    try:
        svc = SimpleNamespace()
        svc._grant_tools_scope = lambda task, tools: CommandService._grant_tools_scope(svc, task, tools)
        tool = SimpleNamespace(definition=SimpleNamespace(name="delete_file"))
        CommandService._grant_pending_scope(svc, SimpleNamespace(request_id="approve-test"), {"type": "single", "tool": tool})
        assert scope.granted_capabilities == {TOOL_CAPABILITY_REQUIREMENTS["delete_file"]}
    finally:
        mgr.revoke_scope("approve-test")


def test_deleting_a_file_is_always_confirmed_and_described_honestly():
    from jarvis.security.confirmation.manager import generate_human_summary
    from jarvis.tools.system.file_tools import DeleteFileTool
    tool = DeleteFileTool()
    assert tool.definition.requires_confirmation is True
    summary = generate_human_summary("delete_file", {"path": "notes.txt"}, tool.definition.risk)
    assert "notes.txt" in summary and not summary.lower().startswith("permanently")
