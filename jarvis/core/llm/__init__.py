"""Local language-model layer (Ollama): one client, shared prompts, grounded chat."""
from jarvis.core.llm.client import (
    ChatResult,
    LLMError,
    LLMSettings,
    LLMUnavailable,
    OllamaClient,
    get_llm,
    set_llm,
    strip_thinking,
)

__all__ = [
    "ChatResult",
    "LLMError",
    "LLMSettings",
    "LLMUnavailable",
    "OllamaClient",
    "get_llm",
    "set_llm",
    "strip_thinking",
]
