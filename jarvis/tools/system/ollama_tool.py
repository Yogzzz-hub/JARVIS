from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from typing import Any
from pydantic import Field

from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition

logger = logging.getLogger("jarvis.tools.ollama_chat")


def _get_default_system_prompt() -> str:
    try:
        from jarvis.core.capabilities.context import CapabilityContextBuilder
        return CapabilityContextBuilder.build_chat_system_prompt()
    except Exception:
        return "You are JARVIS, an intelligent, concise AI assistant for Windows. Answer the user's question directly, clearly, and concisely in 1-3 sentences."


class OllamaChatInput(Contract):
    query: str = Field(description="User question, text, or instruction for Ollama")
    system_prompt: str = Field(
        default_factory=_get_default_system_prompt,
        description="System prompt guiding Ollama's behavior",
    )
    timeout_s: float = Field(default=35.0, description="Query timeout in seconds")


class OllamaChatOutput(Contract):
    response: str
    model: str = "llama3.2:latest"
    status: str = "completed"


class OllamaChatTool(Tool):
    definition = ToolDefinition(
        name="ollama_chat",
        description="Directly queries local Ollama LLM to answer questions, explain concepts, generate code, or solve problems dynamically.",
        input_model=OllamaChatInput,
        output_model=OllamaChatOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=35.0,
        tags=("ai", "llm", "chat", "ollama", "reasoning"),
        execution_method=ExecutionMethod.API,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = OllamaChatInput(**arguments)

        query = arguments.query.strip()
        system_prompt = arguments.system_prompt or _get_default_system_prompt()

        payload = {
            "model": "llama3.2:latest",
            "prompt": f"{system_prompt}\n\nUser: {query}\nJARVIS:",
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 256,
            },
        }

        try:
            req = urllib.request.Request(
                "http://127.0.0.1:11434/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=arguments.timeout_s or 25.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            answer = data.get("response", "").strip()
            if not answer:
                answer = "I am here, sir. How can I help you?"
            return {
                "response": answer,
                "model": data.get("model", "llama3.2:latest"),
                "status": "completed",
            }
        except Exception as exc:
            logger.warning("Ollama direct query error: %s", exc)
            return {
                "response": f"Ollama query failed: {exc}",
                "model": "none",
                "status": "error",
            }
