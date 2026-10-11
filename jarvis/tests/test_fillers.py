"""Spoken fillers: tool-aware lines in JARVIS's register, at most one per run, only after a silent lull."""
from __future__ import annotations

import asyncio

import pytest

from jarvis.core.response import fillers
from jarvis.core.response.fillers import Announcer, Picker, current_announcer, for_tool


@pytest.mark.parametrize("name,expected", [
    ("read_whatsapp_messages", {"Checking WhatsApp.", "Going through your chats."}),
    ("mcp__jarvis__summarize_whatsapp_messages", {"Checking WhatsApp.", "Going through your chats."}),
    ("gmail_search", {"Checking your mail.", "Reading the inbox."}),
    ("mcp__playwright__browser_click", {"Opening the browser.", "Navigating."}),
    ("phone_screenshot", {"Reaching the device.", "Connecting to your phone."}),
    ("search_web", {"Searching.", "Consulting the record."}),
    ("WebSearch", {"Searching.", "Consulting the record."}),
    ("mcp__github__list_pull_requests", {"Checking the repository.", "Consulting the tracker."}),
    ("find_files", {"Searching your files.", "Retrieving."}),
])
def test_lines_fit_the_tool(name, expected):
    assert for_tool(name) in expected


def test_unknown_tools_get_a_neutral_line_and_lines_never_repeat_back_to_back():
    assert for_tool("Read") in fillers.WORKING
    pick = Picker(["a", "b", "c"])
    seq = [pick() for _ in range(50)]
    assert all(x != y for x, y in zip(seq, seq[1:]))


def test_register_has_no_eager_assistant_speak():
    for line in fillers.WORKING + fillers.ACKNOWLEDGE + fillers.ATTENTION:
        assert "!" not in line and not line.lower().startswith(("let me", "i'm now", "right away"))


def test_announcer_speaks_once_and_only_after_a_lull():
    now = [0.0]
    said: list[str] = []
    a = Announcer(said.append, lull_s=2.5, clock=lambda: now[0])
    assert a.tool_started("search_web") is None           # quick start: the initial ack is enough
    now[0] = 3.0
    assert a.tool_started("gmail_search") in {"Checking your mail.", "Reading the inbox."}
    now[0] = 9.0
    assert a.tool_started("search_web") is None           # one line per run, no progress chatter
    assert len(said) == 1


def test_agent_tool_calls_reach_the_announcer(tmp_path, monkeypatch):
    from jarvis.tests.ai_harness import AIHarness
    import json
    replies = iter([json.dumps({"action": "call_tool", "tool": "get_time", "arguments": {}, "thought": "t"}),
                    json.dumps({"action": "final_answer", "message": "It is noon, sir.", "thought": "t"})])
    h = AIHarness(tmp_path, responder=lambda p: json.loads(next(replies)))
    said: list[str] = []
    monkeypatch.setenv("JARVIS_BRAIN", "ollama")

    async def run():
        token = current_announcer.set(Announcer(said.append, lull_s=0))
        try:
            return await h.agent.run("what time is it, then tell me")
        finally:
            current_announcer.reset(token)

    out = asyncio.run(run())
    asyncio.run(h.close())
    assert [s.tool for s in out.steps] == ["get_time"] and len(said) == 1
