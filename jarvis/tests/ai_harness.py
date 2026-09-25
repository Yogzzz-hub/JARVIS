"""Full AI stack for integration tests: real router/planner/agent/RAG, fake Ollama + fake WhatsApp."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Iterable

from pydantic import Field

from jarvis.core.agent import AgentRunner
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.commands.service import CommandService
from jarvis.core.events.bus import EventBus
from jarvis.core.executor.engine import ExecutionEngine
from jarvis.core.knowledge.engine import KnowledgeEngine
from jarvis.core.knowledge.service import KnowledgeService
from jarvis.core.llm.assistant import Assistant, set_assistant
from jarvis.core.llm.client import set_llm
from jarvis.core.planner.adaptive_planner import AdaptivePlanner
from jarvis.core.response.engine import ResponseEngine
from jarvis.core.router.ollama import OllamaProvider
from jarvis.core.router.router import SmartRouter
from jarvis.core.scheduler.scheduler import DAGScheduler
from jarvis.core.tasks.manager import TaskManager
from jarvis.core.verifier.service import Verifier
from jarvis.integrations.whatsapp.ai import WhatsAppAI, set_whatsapp_ai
from jarvis.integrations.whatsapp.fake_transport import FakeWhatsAppTransport
from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
from jarvis.memory.working_memory import WorkingMemory
from jarvis.tests.fake_ollama import FakeOllama
from jarvis.tools.base import Contract, RiskLevel, Tool, ToolDefinition
from jarvis.tools.registry import ToolRegistry

HARDWARE = {"os": "test", "python": "3.12", "cpu": "cpu", "ram_total_mb": 1.0, "gpu_name": None, "gpu_vram_mb": None}


class DummyWriter:
    error = None
    dropped = 0

    def enqueue(self, *args, **kwargs):
        pass

    async def start(self):
        pass

    async def close(self):
        pass


class DummyMetrics:
    dropped = 0

    def record(self, *args, **kwargs):
        pass


class FakeSearchInput(Contract):
    query: str = Field(min_length=1)
    max_results: int = 5


class FakeSearchOutput(Contract):
    query: str
    summary: str
    results: list[dict]
    count: int


class FakeSearchTool(Tool):
    definition = ToolDefinition(
        name="search_web", description="Searches the web for live information.", input_model=FakeSearchInput,
        output_model=FakeSearchOutput, read_only=True, risk=RiskLevel.READ_ONLY,
    )

    def __init__(self, summary: str = "Chennai: 31C and sunny.") -> None:
        self.summary = summary
        self.queries: list[str] = []

    def run(self, arguments):
        query = arguments["query"] if isinstance(arguments, dict) else arguments.query
        self.queries.append(query)
        return {"query": query, "summary": self.summary,
                "results": [{"title": "Weather", "snippet": self.summary, "url": "https://example.com"}], "count": 1}


def route_by_prompt(rules: list[tuple[str, Any]], default: Any = "OK.") -> Callable[[dict], Any]:
    """Responder that answers based on a marker found in the system/user prompt.

    Each rule is (marker, answer); answer may be a value, a callable(payload), or a list used as a queue.
    """
    def responder(payload: dict) -> Any:
        text = "\n".join(str(m.get("content", "")) for m in payload.get("messages", []))
        for marker, answer in rules:
            if marker in text:
                if isinstance(answer, list):
                    return answer.pop(0) if len(answer) > 1 else answer[0]
                return answer(payload) if callable(answer) else answer
        return default(payload) if callable(default) else default
    return responder


class AIHarness:
    def __init__(self, tmp_path: Path, responder: Callable[[dict], Any], reachable: bool = True,
                 extra_tools: Iterable[Tool] = (), models: list[str] | None = None):
        from jarvis.tools.system.app_resolver import AppResolver
        from jarvis.tools.system.native import create_tools

        self.fake = FakeOllama(models=models or ["llama3.2:latest", "nomic-embed-text:latest"], responder=responder, reachable=reachable)
        self.llm = self.fake.client(fast_model="llama3.2", planner_model="llama3.2", chat_model="llama3.2", embed_model="nomic-embed-text")
        set_llm(self.llm)

        self.search = FakeSearchTool()
        replaced = {"search_web": self.search}
        for tool in extra_tools:
            replaced[tool.definition.name] = tool
        tools = [t for t in create_tools(AppResolver({}), HARDWARE) if t.definition.name not in replaced] + list(replaced.values())
        self.registry = ToolRegistry()
        self.registry.discover(tools)
        self.registry.finalize()

        self.transport = FakeWhatsAppTransport()
        self.registry.get("send_whatsapp_message").transport = self.transport

        self.inbox = WhatsAppInbox(tmp_path / "inbox.db")
        self.knowledge = KnowledgeService(KnowledgeEngine(tmp_path / "knowledge.db"), embedder=self.llm)
        self.assistant = Assistant(client=self.llm, registry=self.registry, knowledge_service=self.knowledge)
        set_assistant(self.assistant)
        self.whatsapp_ai = WhatsAppAI(client=self.llm, inbox=self.inbox, owner_name="Ashok")
        set_whatsapp_ai(self.whatsapp_ai)
        for tool in self.registry.list():
            if hasattr(tool, "assistant") and getattr(tool, "assistant") is None:
                tool.assistant = self.assistant
            if hasattr(tool, "knowledge_service") and getattr(tool, "knowledge_service") is None:
                tool.knowledge_service = self.knowledge
            if tool.definition.name == "reply_whatsapp_message":
                tool.ai = self.whatsapp_ai

        self.bus = EventBus()
        self.writer = DummyWriter()
        self.tasks = TaskManager(self.bus, self.writer)
        self.executor = ExecutionEngine()
        self.verifier = Verifier()
        self.memory = WorkingMemory()
        self.router = SmartRouter(
            llm_provider=OllamaProvider(client=self.llm, tool_registry=self.registry),
            tool_registry=self.registry,
            working_memory=self.memory,
        )
        self.agent = AgentRunner(self.registry, self.executor, self.verifier, client=self.llm,
                                 capability_retriever=self.router.capability_retriever)
        self.service = CommandService(
            self.registry, self.executor, self.verifier, ResponseEngine(), self.tasks, self.bus, self.writer, DummyMetrics(),
            router=self.router, planner=AdaptivePlanner(registry=self.registry, client=self.llm),
            scheduler=DAGScheduler(registry=self.registry, executor=self.executor), working_memory=self.memory,
            assistant=self.assistant, agent=self.agent, whatsapp_ai=self.whatsapp_ai,
        )

    async def say(self, text: str, source: str = "test", **kwargs: Any):
        return await self.service.handle(CommandRequest(text=text, source=source, **kwargs))

    def chat_payloads(self, marker: str = "") -> list[dict]:
        out = []
        for p in self.fake.chat_payloads():
            body = json.dumps(p.get("messages", []))
            if marker in body:
                out.append(p)
        return out

    async def close(self):
        await self.service.close()
        await self.llm.aclose()
        set_llm(None)
        set_assistant(None)
        set_whatsapp_ai(None)
