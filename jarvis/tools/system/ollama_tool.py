from __future__ import annotations

import logging
from typing import Any

from pydantic import Field

from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition

logger = logging.getLogger("jarvis.tools.ollama_chat")


class OllamaChatInput(Contract):
    query: str = Field(min_length=1, max_length=8000, description="User question, text, or instruction for the local AI model")
    system_prompt: str = Field(default="", description="Optional system prompt override")
    timeout_s: float = Field(default=45.0, gt=0, le=300, description="Query timeout in seconds")
    channel: str = Field(default="local", description="Conversation channel used for follow-up memory")
    speakable: bool = Field(default=True, description="Keep the answer short and speech-friendly")


class OllamaChatOutput(Contract):
    response: str
    model: str = ""
    status: str = "completed"
    sources: list[dict] = Field(default_factory=list)
    used_web: bool = False


class OllamaChatTool(Tool):
    """Answers questions with the local model, grounded in RAG, history and (when needed) the web."""

    definition = ToolDefinition(
        name="ollama_chat",
        description="Answers questions, explains concepts, writes or summarizes text using the local AI model, grounded in the user's documents, conversation and live web results.",
        input_model=OllamaChatInput,
        output_model=OllamaChatOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=90.0,
        tags=("ai", "llm", "chat", "ollama", "reasoning", "rag"),
        execution_method=ExecutionMethod.API,
    )

    def __init__(self, assistant: Any = None) -> None:
        self.assistant = assistant

    def _assistant(self):
        if self.assistant is None:
            from jarvis.core.llm.assistant import get_assistant
            return get_assistant()
        return self.assistant

    async def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = OllamaChatInput(**arguments)
        assistant = self._assistant()
        extra = arguments.system_prompt.strip()
        reply = await assistant.respond(
            arguments.query.strip(),
            channel=arguments.channel,
            speakable=arguments.speakable,
            extra_context=f"Additional instructions: {extra}" if extra else "",
        )
        if not reply.ok:
            logger.warning("Local model answer failed: %s", reply.error)
        return {
            "response": reply.text,
            "model": reply.model or "none",
            "status": "completed" if reply.ok else "error",
            "sources": [{k: v for k, v in s.items() if k in ("type", "title", "source")} for s in reply.sources],
            "used_web": reply.used_web,
        }
