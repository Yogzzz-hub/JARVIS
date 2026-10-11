"""Claude Code as the brain (headless, through the Claude Agent SDK) - driven by a scripted fake of the SDK, so no
login or network is needed. Covers the tool gate, streaming, safe tools running through JARVIS's own executor,
risky tools pausing for confirmation, and the fallback when the local model is down."""
from __future__ import annotations

import asyncio

import pytest

claude_agent_sdk = pytest.importorskip("claude_agent_sdk")

from jarvis.core.brain import claude_code as cc
from jarvis.core.brain.claude_code import ClaudeCodeBrain, decide_tool
from jarvis.core.llm.streaming import StreamSink
from jarvis.tests.ai_harness import AIHarness


# ------------------------------------------------------------------------------------------------- permission gate
@pytest.mark.parametrize("name,allowed", [
    ("Read", True), ("WebSearch", True), ("Grep", True), ("Agent", True),
    ("Bash", False), ("Write", False), ("Edit", False), ("KillShell", False),
    ("mcp__jarvis__send_whatsapp_message", True),          # JARVIS's own server gates itself (confirmation flow)
    ("mcp__exa__web_search_exa", True),                     # read-only server
    ("mcp__higgsfield__generate_image", True),              # generation runs
    ("mcp__higgsfield__delete_character", False),          # ...acting on the world does not
    ("mcp__android__list_devices", True),                   # read verb
    ("mcp__android__install_apk", False),
    ("mcp__twilio__make_outbound_call", False),             # verb hidden in the middle
    ("mcp__openrouter__send-message", True),                # explicit exemption: asking another model
    ("SomethingNew", False),                                # unknown -> default deny
])
def test_tool_gate_is_default_deny_for_effects(name, allowed, monkeypatch):
    monkeypatch.delenv("JARVIS_ALLOW_WRITES", raising=False)
    assert decide_tool(name) is allowed


def test_writes_flag_opens_the_write_tools(monkeypatch):
    monkeypatch.setenv("JARVIS_ALLOW_WRITES", "1")
    assert decide_tool("Bash") and decide_tool("mcp__android__install_apk")


@pytest.mark.parametrize("value,mode", [("", "auto"), ("claude", "claude"), ("claude-code", "claude"),
                                        ("OLLAMA", "ollama"), ("nonsense", "auto")])
def test_brain_mode(value, mode, monkeypatch):
    monkeypatch.setenv("JARVIS_BRAIN", value or "auto")
    assert cc.brain_mode() == mode


# ------------------------------------------------------------------------------------------------- fake SDK
def _delta(text):
    return claude_agent_sdk.StreamEvent(uuid="u", session_id="s", event={
        "type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}})


def _result(text, subtype="success"):
    return claude_agent_sdk.ResultMessage(subtype=subtype, duration_ms=1, duration_api_ms=1, is_error=subtype != "success",
                                          num_turns=1, session_id="s", result=text, total_cost_usd=0.001)


class FakeSDK:
    """Stands in for query() / create_sdk_mcp_server(): runs a script of tool calls against the real handlers."""

    def __init__(self, monkeypatch, calls=(), reply="The task is complete, sir.", fail: Exception | None = None):
        self.calls, self.reply, self.fail = list(calls), reply, fail
        self.options = None
        self.tool_results: list[dict] = []
        self.tools: dict = {}
        monkeypatch.setattr(claude_agent_sdk, "create_sdk_mcp_server", self.create_server)
        monkeypatch.setattr(claude_agent_sdk, "query", self.query)

    def create_server(self, name, version="1.0.0", tools=None):
        self.tools = {t.name: t for t in tools or []}
        return {"type": "sdk", "name": name, "tools": self.tools}

    async def query(self, *, prompt, options=None, transport=None):
        self.options = options
        async for _ in prompt:
            pass
        if self.fail is not None:
            raise self.fail
        for name, args in self.calls:
            verdict = await options.can_use_tool(f"mcp__jarvis__{name}", args, None)
            assert verdict.behavior == "allow"
            self.tool_results.append(await self.tools[name].handler(args))
        for piece in self.reply.split(" "):
            yield _delta(piece + " ")
        yield _result(self.reply)


@pytest.fixture
def harness(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_BRAIN", "auto")
    monkeypatch.setenv("JARVIS_CLAUDE_MCP", "0")
    monkeypatch.setattr(cc, "_brain", ClaudeCodeBrain())
    h = AIHarness(tmp_path, responder=lambda p: {"message": "OK."}, reachable=False)   # the local model is down
    yield h
    asyncio.run(h.close())


# ------------------------------------------------------------------------------------------------- behaviour
def test_answer_streams_into_the_speech_sink(monkeypatch):
    FakeSDK(monkeypatch, reply="Paris is the capital of France, sir.")
    spoken: list[str] = []
    sink = StreamSink(on_sentence=spoken.append)
    text = asyncio.run(ClaudeCodeBrain().answer("Be brief.", [{"role": "user", "content": "capital of france"}], sink))
    assert text == "Paris is the capital of France, sir."
    assert "".join(spoken).replace(" ", "") == text.replace(" ", "") and sink.closed


def test_options_disable_settings_and_write_builtins(monkeypatch):
    monkeypatch.delenv("JARVIS_ALLOW_WRITES", raising=False)
    fake = FakeSDK(monkeypatch)
    asyncio.run(ClaudeCodeBrain().answer("", [{"role": "user", "content": "hi"}]))
    opts = fake.options
    assert opts.setting_sources == [] and "Bash" in opts.disallowed_tools and opts.include_partial_messages
    assert opts.model == cc.DEFAULT_MODEL and opts.allowed_tools == ["WebSearch", "WebFetch"]


def test_agent_runs_safe_tools_through_jarvis_and_pauses_risky_ones(harness, monkeypatch):
    fake = FakeSDK(monkeypatch, calls=[("get_time", {}),
                                       ("send_whatsapp_message", {"recipient": "Amma", "message": "Reached home"})])
    out = asyncio.run(harness.agent.run("tell amma I reached home and tell me the time"))
    assert out.status == "needs_confirmation" and out.pending.tool == "send_whatsapp_message"
    assert [s.tool for s in out.steps] == ["get_time"] and out.steps[0].success         # ran via the executor
    assert harness.transport.sent == [] if hasattr(harness.transport, "sent") else True    # nothing was sent
    assert fake.tool_results[1]["is_error"] and "PAUSED" in fake.tool_results[1]["content"][0]["text"]
    assert out.model.startswith("claude-code:")
    # the owner approves: the paused call runs through JARVIS and Claude continues without repeating it
    FakeSDK(monkeypatch, reply="Message sent, sir.")
    done = asyncio.run(harness.agent.run(out.state["goal"], state=out.state, confirmed=True))
    assert done.status == "done" and [s.tool for s in done.steps] == ["get_time", "send_whatsapp_message"]


def test_unavailable_claude_falls_back_to_the_local_message(harness, monkeypatch):
    FakeSDK(monkeypatch, fail=RuntimeError("Not logged in - please run /login"))
    out = asyncio.run(harness.agent.run("plan my evening"))
    assert out.status == "unavailable" and "Ollama" in out.message
    assert not cc.get_claude_brain().available()      # breaker tripped: no retry storm on every request


def test_ollama_mode_never_uses_claude(harness, monkeypatch):
    monkeypatch.setenv("JARVIS_BRAIN", "ollama")
    fake = FakeSDK(monkeypatch)
    out = asyncio.run(harness.agent.run("plan my evening"))
    assert out.status == "unavailable" and fake.options is None


def test_chat_answer_uses_claude_when_the_local_model_is_down(harness, monkeypatch):
    FakeSDK(monkeypatch, reply="Mount Everest is eight thousand eight hundred and forty-nine metres tall, sir.")
    reply = asyncio.run(harness.assistant.respond("how tall is mount everest", use_web=False, use_knowledge=False))
    assert reply.ok and "Everest" in reply.text and reply.model.startswith("claude-code:")
