"""Unified Ollama client and Lane 1 classifier tests (fake server, no network)."""
from __future__ import annotations

import httpx
import pytest

from jarvis.core.llm.client import (
    LLMSettings,
    LLMUnavailable,
    OllamaClient,
    choose_fallback,
    extract_json,
    match_installed,
    model_size_billions,
    normalize_base_url,
    strip_thinking,
)
from jarvis.core.router.models import RouteLane
from jarvis.core.router.ollama import OllamaProvider
from jarvis.tests.fake_ollama import FakeOllama


def test_normalize_base_url_variants():
    assert normalize_base_url("") == "http://127.0.0.1:11434"
    assert normalize_base_url("0.0.0.0:11434") == "http://127.0.0.1:11434"
    assert normalize_base_url("localhost") == "http://localhost:11434"
    assert normalize_base_url("http://10.0.0.5:9999/") == "http://10.0.0.5:9999"


def test_strip_thinking_and_extract_json():
    assert strip_thinking("<think>plan it</think>Opening Chrome.") == "Opening Chrome."
    assert strip_thinking("<think>never closed ...") == ""
    assert extract_json('<think>x</think>```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! Here it is: {"intent": "open_app", "slots": {"name": "x}"}} done') == {
        "intent": "open_app", "slots": {"name": "x}"}}


def test_model_matching_and_fallbacks():
    installed = ["llama3.2:latest", "qwen3:1.7b", "nomic-embed-text:latest", "qwen2.5vl:3b", "llama3.1:70b"]
    assert match_installed("llama3.2", installed) == "llama3.2:latest"
    assert match_installed("qwen3", installed) == "qwen3:1.7b"
    assert match_installed("mistral", installed) is None
    assert model_size_billions("qwen3:1.7b") == 1.7
    assert model_size_billions("smollm2:360m") == pytest.approx(0.36)
    assert choose_fallback("embed", installed) == "nomic-embed-text:latest"
    assert choose_fallback("vision", installed) == "qwen2.5vl:3b"
    # Fast role prefers a small model; chat never picks a 70B model on a laptop.
    assert choose_fallback("fast", installed) == "qwen3:1.7b"
    assert choose_fallback("chat", installed) in ("qwen3:1.7b", "llama3.2:latest")


@pytest.mark.asyncio
async def test_role_resolution_uses_installed_alternative():
    fake = FakeOllama(models=["llama3.2:latest"])
    client = fake.client(fast_model="qwen3:0.6b", chat_model="llama3.2")
    assert await client.resolve("chat") == "llama3.2:latest"
    # Configured fast model is not pulled -> falls back to the chat model instead of failing.
    assert await client.resolve("fast") == "llama3.2:latest"
    with pytest.raises(LLMUnavailable):
        await client.resolve("embed")


@pytest.mark.asyncio
async def test_chat_json_and_think_flag_for_thinking_models():
    fake = FakeOllama(models=["qwen3:1.7b"], responder=lambda p: '<think>hmm</think>{"ok": true}')
    client = fake.client(chat_model="qwen3:1.7b")
    data = await client.chat_json([{"role": "user", "content": "hi"}], schema={"type": "object"})
    assert data["ok"] is True
    payload = fake.chat_payloads()[-1]
    assert payload["think"] is False
    assert payload["format"] == {"type": "object"}


@pytest.mark.asyncio
async def test_think_flag_dropped_when_server_rejects_it():
    calls = {"n": 0}

    def responder(payload):
        calls["n"] += 1
        if "think" in payload:
            return httpx.Response(400, json={"error": "invalid option: think"})
        return "plain answer"

    fake = FakeOllama(models=["qwen3:4b"], responder=responder)
    client = fake.client()
    result = await client.chat([{"role": "user", "content": "hi"}])
    assert result.text == "plain answer"
    assert calls["n"] == 2
    # Subsequent requests no longer send the unsupported flag.
    await client.chat([{"role": "user", "content": "again"}])
    assert "think" not in fake.chat_payloads()[-1]


@pytest.mark.asyncio
async def test_circuit_breaker_fails_fast_when_server_down():
    fake = FakeOllama(reachable=False)
    client = fake.client(breaker_cooldown_s=60)
    assert await client.available() is False
    with pytest.raises(LLMUnavailable):
        await client.chat([{"role": "user", "content": "hi"}])
    # No new HTTP attempts while the breaker is open.
    fake.reachable = True
    with pytest.raises(LLMUnavailable):
        await client.resolve("chat")
    client.mark_unavailable(0.0)
    client._down_until = 0.0
    assert await client.available(refresh=True) is True


@pytest.mark.asyncio
async def test_stream_chat_yields_text():
    fake = FakeOllama(responder=lambda p: "one two three")
    client = fake.client(chat_model="llama3.2")
    parts = [d async for d in client.stream_chat([{"role": "user", "content": "count"}])]
    assert "".join(parts).split() == ["one", "two", "three"]


def test_sync_chat_and_embed_from_worker_thread():
    fake = FakeOllama()
    client = fake.client(chat_model="llama3.2", embed_model="nomic-embed-text")
    assert client.chat_sync([{"role": "user", "content": "hi"}]).text == "Hello from the fake model."
    vectors = client.embed_sync(["alpha", "beta"])
    assert len(vectors) == 2 and len(vectors[0]) == 8


class _Registry:
    """Minimal registry facade over real tools for the classifier."""

    def __init__(self):
        from jarvis.tools.system.app_resolver import AppResolver
        from jarvis.tools.system.native import create_tools
        from jarvis.tools.registry import ToolRegistry
        self.reg = ToolRegistry()
        self.reg.discover(create_tools(AppResolver({}), {"os": "x", "python": "3", "cpu": "c", "ram_total_mb": 1.0, "gpu_name": None, "gpu_vram_mb": None}))
        self.reg.finalize()


@pytest.fixture(scope="module")
def registry():
    return _Registry().reg


@pytest.mark.asyncio
async def test_classifier_constrains_intent_and_validates_slots(registry):
    def responder(payload):
        enum = payload["format"]["properties"]["intent"]["enum"]
        assert "none" in enum and "send_whatsapp_message" in enum
        return {"intent": "send_whatsapp_message", "slots": {"recipient": "Mom", "message": "I'll be late", "bogus": 1},
                "missing_slots": [], "confidence": 0.9, "is_multi_step": False, "is_command": True, "unknown": False}

    fake = FakeOllama(responder=responder)
    provider = OllamaProvider(client=fake.client(fast_model="llama3.2"), tool_registry=registry)
    dec = await provider.classify("ping mum on whatsapp that I'll be late", [], "r1")
    assert dec.lane == RouteLane.LANE_1
    assert dec.intent == "send_whatsapp_message"
    assert dec.slots == {"recipient": "Mom", "message": "I'll be late"}


@pytest.mark.asyncio
async def test_classifier_reports_missing_required_argument(registry):
    fake = FakeOllama(responder=lambda p: {"intent": "volume_set", "slots": {}, "missing_slots": [], "confidence": 0.8,
                                            "is_multi_step": False, "is_command": True, "unknown": False})
    provider = OllamaProvider(client=fake.client(), tool_registry=registry)
    dec = await provider.classify("change the volume", [], "r2")
    assert dec.lane == RouteLane.CLARIFY
    assert dec.missing_slots == ["percent"]


@pytest.mark.asyncio
async def test_classifier_low_confidence_and_multistep(registry):
    fake = FakeOllama(responder=lambda p: {"intent": "open_app", "slots": {"name": "x"}, "missing_slots": [], "confidence": 0.2,
                                            "is_multi_step": False, "is_command": True, "unknown": False})
    provider = OllamaProvider(client=fake.client(), tool_registry=registry)
    assert (await provider.classify("blorp the zibble", [], "r3")).lane == RouteLane.CLARIFY

    fake.responder = lambda p: {"intent": "none", "slots": {}, "missing_slots": [], "confidence": 0.9,
                                "is_multi_step": True, "is_command": True, "unknown": False}
    dec = await provider.classify("open chrome, then mute and message mom", [], "r4")
    assert dec.lane == RouteLane.LANE_2 and dec.needs_planner


@pytest.mark.asyncio
async def test_classifier_unavailable_reports_model_down(registry):
    fake = FakeOllama(reachable=False)
    provider = OllamaProvider(client=fake.client(), tool_registry=registry)
    dec = await provider.classify("zzqx unusual request", [], "r5")
    assert dec.lane == RouteLane.CLARIFY
    assert dec.context_trace["llm_unavailable"]
    assert "can't reach my local AI" in dec.clarification and "deterministic" not in dec.clarification


@pytest.mark.asyncio
async def test_classifier_hiccup_is_not_reported_as_model_down(registry):
    import httpx
    fake = FakeOllama(responder=lambda p: httpx.Response(500, json={"error": "model is loading"}))
    provider = OllamaProvider(client=fake.client(), tool_registry=registry)
    dec = await provider.classify("zzqx unusual request", [], "r6")
    assert dec.lane == RouteLane.CLARIFY and not (dec.context_trace or {}).get("llm_unavailable")
    assert "unavailable" not in dec.clarification.lower()
