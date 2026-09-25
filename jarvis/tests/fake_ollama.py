"""In-process fake Ollama server for tests (no network, no model download)."""
from __future__ import annotations

import json
from typing import Any, Callable

import httpx

from jarvis.core.llm.client import LLMSettings, OllamaClient


class FakeOllama:
    """Implements the Ollama endpoints JARVIS uses on top of ``httpx.MockTransport``.

    ``responder(payload) -> str | dict`` produces the assistant message content for /api/chat.
    Returning a dict serialises it as JSON (what a model does under ``format``).
    """

    def __init__(
        self,
        models: list[str] | None = None,
        responder: Callable[[dict[str, Any]], Any] | None = None,
        embed_dim: int = 8,
        reachable: bool = True,
    ):
        self.models = models if models is not None else ["llama3.2:latest", "nomic-embed-text:latest"]
        self.responder = responder or (lambda payload: "Hello from the fake model.")
        self.embed_dim = embed_dim
        self.reachable = reachable
        self.requests: list[tuple[str, dict[str, Any]]] = []

    # -- helpers -----------------------------------------------------------
    def chat_payloads(self) -> list[dict[str, Any]]:
        return [p for path, p in self.requests if path == "/api/chat"]

    def _embed(self, text: str) -> list[float]:
        # Deterministic bag-of-letters embedding: similar strings -> similar vectors.
        vec = [0.0] * self.embed_dim
        for ch in text.lower():
            if ch.isalnum():
                vec[ord(ch) % self.embed_dim] += 1.0
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]

    def handler(self, request: httpx.Request) -> httpx.Response:
        if not self.reachable:
            raise httpx.ConnectError("connection refused", request=request)
        path = request.url.path
        payload = json.loads(request.content or b"{}") if request.content else {}
        self.requests.append((path, payload))
        if path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": m} for m in self.models]})
        if path == "/api/chat":
            content = self.responder(payload)
            if isinstance(content, httpx.Response):
                return content
            if not isinstance(content, str):
                content = json.dumps(content)
            if payload.get("stream"):
                lines = []
                for word in content.split(" "):
                    lines.append(json.dumps({"message": {"role": "assistant", "content": word + " "}, "done": False}))
                lines.append(json.dumps({"message": {"role": "assistant", "content": ""}, "done": True}))
                return httpx.Response(200, content=("\n".join(lines) + "\n").encode())
            return httpx.Response(200, json={
                "model": payload.get("model"),
                "message": {"role": "assistant", "content": content},
                "done": True,
                "total_duration": 1_000_000,
            })
        if path == "/api/embed":
            inputs = payload.get("input") or []
            if isinstance(inputs, str):
                inputs = [inputs]
            return httpx.Response(200, json={"embeddings": [self._embed(t) for t in inputs]})
        if path == "/api/generate":
            return httpx.Response(200, json={"response": "", "done": True})
        return httpx.Response(404, json={"error": "not found"})

    def client(self, **settings: Any) -> OllamaClient:
        return OllamaClient(LLMSettings(**settings), transport=httpx.MockTransport(self.handler))
