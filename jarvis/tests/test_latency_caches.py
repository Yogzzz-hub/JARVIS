"""Hot-path caches: repeated classifications, query embeddings, empty knowledge base, prompt prefix."""
from __future__ import annotations

import json

import pytest

from jarvis.core.knowledge.engine import KnowledgeEngine
from jarvis.core.knowledge.models import KnowledgeScopeFilter
from jarvis.core.knowledge.service import KnowledgeService
from jarvis.core.llm.assistant import Assistant
from jarvis.core.router.ollama import OllamaProvider
from jarvis.tests.fake_ollama import FakeOllama


def _classifier_reply(payload):
    return {"intent": "none", "slots": {}, "missing_slots": [], "confidence": 0.9,
            "is_multi_step": False, "is_command": False, "unknown": True}


@pytest.mark.asyncio
async def test_repeated_utterance_is_classified_once():
    fake = FakeOllama(models=["qwen3:1.7b"], responder=_classifier_reply)
    client = fake.client(fast_model="qwen3:1.7b")
    provider = OllamaProvider(client=client)
    try:
        first = await provider.classify("why is the sky blue", [], "r1")
        second = await provider.classify("Why is  the sky blue", [], "r2")
    finally:
        await client.aclose()
    assert len(fake.chat_payloads()) == 1
    assert first.lane == second.lane and second.request_id == "r2"
    assert second.breakdown_ms.get("classifier_cache_hit") == 1.0


@pytest.mark.asyncio
async def test_empty_knowledge_base_skips_embedding(tmp_path):
    fake = FakeOllama(models=["llama3.2:latest", "nomic-embed-text:latest"], responder=lambda p: "ok")
    client = fake.client(embed_model="nomic-embed-text")
    service = KnowledgeService(KnowledgeEngine(tmp_path / "k.db"), embedder=client)
    try:
        assert await service.search_unified("refund policy details", KnowledgeScopeFilter()) == []
    finally:
        await client.aclose()
    assert not [p for p, _ in fake.requests if p == "/api/embed"]


@pytest.mark.asyncio
async def test_query_embeddings_are_cached(tmp_path):
    fake = FakeOllama(models=["llama3.2:latest", "nomic-embed-text:latest"], responder=lambda p: "ok")
    client = fake.client(embed_model="nomic-embed-text")
    engine = KnowledgeEngine(tmp_path / "k.db")
    doc = tmp_path / "policy.md"
    doc.write_text("# Refunds\nRefunds are processed within 14 days of the return.\n", encoding="utf-8")
    service = KnowledgeService(engine, embedder=client)
    try:
        await service.ingest(str(doc))
        await engine.embed_pending(client)
        embeds_before = len([p for p, _ in fake.requests if p == "/api/embed"])
        for _ in range(3):
            hits = await service.search_unified("how long do refunds take", KnowledgeScopeFilter())
            assert hits and "14 days" in hits[0].snippet
    finally:
        await client.aclose()
    assert len([p for p, _ in fake.requests if p == "/api/embed"]) - embeds_before == 1


def test_system_prompt_keeps_a_stable_prefix():
    assistant = Assistant(client=object())
    prompt = assistant.system_prompt(True)
    head, last = prompt.rsplit("\n", 1)
    assert last.startswith("Current local date and time")
    assert "Current local date" not in head
    assert json.dumps(head) == json.dumps(assistant.system_prompt(True).rsplit("\n", 1)[0])
