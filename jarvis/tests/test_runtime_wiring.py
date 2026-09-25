"""The real Runtime wires one LLM client, RAG, assistant, agent and planner into every AI feature."""
from __future__ import annotations

import pytest

from jarvis.config import Config
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.runtime import Runtime


@pytest.mark.asyncio
async def test_runtime_shares_one_model_client_and_knowledge_base(tmp_path, monkeypatch):
    from jarvis.tools.system import assistant_tools

    monkeypatch.setattr(assistant_tools, "_service", assistant_tools.ReminderService(tmp_path / "reminders.json"))
    runtime = Runtime(Config(), root=tmp_path)
    await runtime.start()
    try:
        from jarvis.core.llm.assistant import get_assistant
        from jarvis.core.llm.client import get_llm
        from jarvis.core.router.ollama import OllamaProvider

        assert get_llm() is runtime.llm
        assert get_assistant() is runtime.assistant
        assert runtime.assistant.knowledge_service is runtime.knowledge_service
        assert isinstance(runtime.router.llm_provider, OllamaProvider)
        assert runtime.router.llm_provider.client is runtime.llm
        assert runtime.router.llm_provider.tool_registry is runtime.registry
        assert runtime.service.agent is runtime.agent and runtime.service.planner.client is runtime.llm

        registry = runtime.registry
        assert registry.get("ollama_chat").assistant is runtime.assistant
        assert registry.get("document_qa").knowledge_service is runtime.knowledge_service
        assert registry.get("knowledge_ingest").knowledge_service is runtime.knowledge_service
        assert registry.get("reply_whatsapp_message").ai is runtime.whatsapp_ai
        for name in ("open_website", "set_reminder", "android_key", "android_dial", "web_task", "knowledge_search"):
            assert registry.contains(name), name

        result = await runtime.service.handle(CommandRequest(text="what time is it", source="test"))
        assert result.state == "SUCCESS"
        result = await runtime.service.handle(CommandRequest(text="remind me to stretch in 5 minutes", source="test"))
        assert result.state == "SUCCESS" and "stretch" in result.message
    finally:
        await runtime.close()
