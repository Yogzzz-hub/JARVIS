"""Unified local LLM client for JARVIS EDGE (Ollama).

Every AI feature (router classification, planner, agent loop, chat, RAG,
WhatsApp composition, browser agent) talks to the model through this one
client so that model selection, timeouts, availability detection and output
cleaning behave identically everywhere.

Design points:
* Model *roles* (``fast``, ``planner``, ``chat``, ``vision``, ``embed``) are
  mapped to whatever models are actually installed. A configured model that is
  not pulled falls back to the best installed alternative instead of failing.
* A short circuit breaker turns "Ollama is not running" into an immediate
  ``LLMUnavailable`` instead of a multi-second timeout on every request, so
  deterministic commands stay fast when the model server is down.
* Thinking models (qwen3, deepseek-r1, ...) are asked not to think for
  latency-sensitive calls, and any ``<think>`` block that still appears is
  stripped before the text reaches the user or a JSON parser.
* Async calls use one ``httpx.AsyncClient`` per event loop; sync calls (tools
  running in worker threads) use a separate ``httpx.Client``.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Iterable, Optional

import httpx

logger = logging.getLogger("jarvis.llm")

DEFAULT_BASE_URL = "http://127.0.0.1:11434"

ROLES = ("fast", "planner", "chat", "vision", "embed")

# Fallback order used when a role has no installed model configured.
ROLE_FALLBACKS: dict[str, tuple[str, ...]] = {
    "fast": ("fast", "chat", "planner"),
    "planner": ("planner", "chat", "fast"),
    "chat": ("chat", "planner", "fast"),
    "vision": ("vision",),
    "embed": ("embed",),
}

# Preferred general-purpose families, best first. Used only when nothing configured is installed.
TEXT_FAMILY_PREFERENCE = (
    "qwen3", "qwen2.5", "llama3.2", "llama3.1", "llama3", "gemma3", "gemma2",
    "phi4", "phi3", "mistral", "granite3", "smollm2",
)
EMBED_MARKERS = ("embed", "minilm", "bge-", "bge:", "e5-", "gte-", "snowflake-arctic", "paraphrase")
VISION_MARKERS = ("-vl", "vl:", "llava", "vision", "moondream", "bakllava", "minicpm-v")
THINKING_FAMILIES = ("qwen3", "deepseek-r1", "qwq", "magistral", "cogito", "phi4-reasoning")

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_UNCLOSED_THINK = re.compile(r"^\s*<think>.*", re.DOTALL | re.IGNORECASE)
_SIZE_TAG = re.compile(r"(\d+(?:\.\d+)?)\s*([bm])\b", re.IGNORECASE)


class LLMError(RuntimeError):
    """The model server answered but the request failed."""


class LLMUnavailable(LLMError):
    """No model server is reachable or no suitable model is installed."""


@dataclass(frozen=True)
class LLMSettings:
    base_url: str = DEFAULT_BASE_URL
    fast_model: str = ""
    planner_model: str = ""
    chat_model: str = ""
    vision_model: str = ""
    embed_model: str = "nomic-embed-text"
    keep_alive: str = "30m"
    timeout_s: float = 60.0
    connect_timeout_s: float = 2.5
    num_ctx: int = 4096
    auto_start: bool = True
    breaker_cooldown_s: float = 10.0
    tags_ttl_s: float = 30.0

    def model_for(self, role: str) -> str:
        return {
            "fast": self.fast_model,
            "planner": self.planner_model,
            "chat": self.chat_model,
            "vision": self.vision_model,
            "embed": self.embed_model,
        }.get(role, "")

    @classmethod
    def from_config(cls, config: Any = None) -> "LLMSettings":
        """Build settings from a ``jarvis.config.Config`` (or the default config file)."""
        if config is None:
            try:
                from jarvis.config import load
                config = load()
            except Exception:
                config = None
        models = getattr(config, "models", None)
        base_url = normalize_base_url(
            os.environ.get("JARVIS_OLLAMA_URL")
            or getattr(models, "base_url", "")
            or os.environ.get("OLLAMA_HOST", "")
            or DEFAULT_BASE_URL
        )
        if models is None:
            return cls(base_url=base_url)
        return cls(
            base_url=base_url,
            fast_model=getattr(models, "fast", "") or "",
            planner_model=getattr(models, "planner", "") or "",
            chat_model=getattr(models, "chat", "") or "",
            vision_model=getattr(models, "vision", "") or "",
            embed_model=getattr(models, "embed", "nomic-embed-text") or "",
            keep_alive=getattr(models, "keep_alive", "30m") or "30m",
            timeout_s=float(getattr(models, "timeout_s", 60.0) or 60.0),
            num_ctx=int(getattr(models, "num_ctx", 4096) or 4096),
            auto_start=bool(getattr(models, "auto_start", True)),
        )


@dataclass
class ChatResult:
    text: str
    model: str
    data: Any = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)


def normalize_base_url(value: str) -> str:
    """Accept ``host:port``, ``0.0.0.0:11434`` or a full URL and return a usable client URL."""
    url = (value or "").strip().rstrip("/")
    if not url:
        return DEFAULT_BASE_URL
    if "://" not in url:
        url = f"http://{url}"
    url = url.replace("://0.0.0.0", "://127.0.0.1")
    if re.match(r"^https?://[^:/]+$", url):
        url += ":11434"
    return url


def strip_thinking(text: str) -> str:
    """Remove reasoning blocks that thinking models may emit inline."""
    if not text:
        return ""
    cleaned = _THINK_BLOCK.sub("", text)
    if "<think>" in cleaned.lower():
        # A truncated reasoning block never closed: nothing after it is an answer.
        cleaned = _UNCLOSED_THINK.sub("", cleaned)
    return cleaned.replace("</think>", "").strip()


def extract_json(text: str) -> Any:
    """Parse JSON from model output, tolerating think blocks, code fences and prose."""
    cleaned = strip_thinking(text)
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        pass
    # Find the first balanced JSON object or array.
    for opener, closer in (("{", "}"), ("[", "]")):
        start = cleaned.find(opener)
        while start != -1:
            depth, in_str, escape = 0, False, False
            for idx in range(start, len(cleaned)):
                ch = cleaned[idx]
                if in_str:
                    if escape:
                        escape = False
                    elif ch == "\\":
                        escape = True
                    elif ch == '"':
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                elif ch == opener:
                    depth += 1
                elif ch == closer:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(cleaned[start: idx + 1])
                        except json.JSONDecodeError:
                            break
            start = cleaned.find(opener, start + 1)
    raise LLMError(f"Model did not return valid JSON: {cleaned[:160]!r}")


def model_size_billions(name: str) -> float | None:
    """Best-effort parameter count from an Ollama tag such as ``qwen3:1.7b``."""
    tag = name.split(":", 1)[1] if ":" in name else name
    match = _SIZE_TAG.search(tag) or _SIZE_TAG.search(name)
    if not match:
        return None
    value = float(match.group(1))
    return value / 1000.0 if match.group(2).lower() == "m" else value


def is_embedding_model(name: str) -> bool:
    low = name.lower()
    return any(marker in low for marker in EMBED_MARKERS)


def is_vision_model(name: str) -> bool:
    low = name.lower()
    return any(marker in low for marker in VISION_MARKERS)


def is_thinking_model(name: str) -> bool:
    low = name.lower()
    return any(low.startswith(f) or f"/{f}" in low for f in THINKING_FAMILIES)


def match_installed(requested: str, installed: Iterable[str]) -> str | None:
    """Match a configured model name against installed tags (``llama3.2`` == ``llama3.2:latest``)."""
    if not requested:
        return None
    names = list(installed)
    req = requested.strip().lower()
    lowered = {n.lower(): n for n in names}
    if req in lowered:
        return lowered[req]
    if ":" not in req:
        if f"{req}:latest" in lowered:
            return lowered[f"{req}:latest"]
        prefixed = sorted(n for n in names if n.lower().startswith(req + ":"))
        if prefixed:
            return prefixed[0]
    elif req.endswith(":latest"):
        base = req[: -len(":latest")]
        if base in lowered:
            return lowered[base]
    return None


def choose_fallback(role: str, installed: Iterable[str]) -> str | None:
    """Pick the most suitable installed model for a role when nothing configured matches."""
    names = list(installed)
    if role == "embed":
        embeds = [n for n in names if is_embedding_model(n)]
        return sorted(embeds)[0] if embeds else None
    if role == "vision":
        vision = [n for n in names if is_vision_model(n)]
        return sorted(vision, key=lambda n: model_size_billions(n) or 99)[0] if vision else None

    text_models = [n for n in names if not is_embedding_model(n) and not is_vision_model(n)]
    if not text_models:
        return None

    def family_rank(name: str) -> int:
        low = name.lower()
        for idx, fam in enumerate(TEXT_FAMILY_PREFERENCE):
            if low.startswith(fam):
                return idx
        return len(TEXT_FAMILY_PREFERENCE)

    def size(name: str) -> float:
        value = model_size_billions(name)
        return 4.0 if value is None else value

    if role == "fast":
        # Smallest capable model keeps routing latency low; family breaks ties.
        return sorted(text_models, key=lambda n: (size(n) > 4.5, family_rank(n), size(n)))[0]
    # chat / planner: best family, then the largest model that still fits typical laptops (<= 9B).
    return sorted(text_models, key=lambda n: (size(n) > 9.0, family_rank(n), -size(n)))[0]


def find_ollama_executable() -> str | None:
    candidates = [os.environ.get("OLLAMA_EXE", ""), shutil.which("ollama") or ""]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(str(Path(local) / "Programs" / "Ollama" / "ollama.exe"))
    candidates += ["/usr/local/bin/ollama", "/usr/bin/ollama", "/opt/homebrew/bin/ollama"]
    for cand in candidates:
        if cand and Path(cand).is_file():
            return cand
    return None


class OllamaClient:
    """Single entry point for local model inference."""

    def __init__(self, settings: LLMSettings | None = None, transport: httpx.BaseTransport | None = None):
        self.settings = settings or LLMSettings()
        self._transport = transport
        self._async_clients: dict[int, httpx.AsyncClient] = {}
        self._sync_client: httpx.Client | None = None
        self._lock = threading.Lock()
        self._models: list[str] = []
        self._models_at = 0.0
        self._down_until = 0.0
        self._last_error = ""
        self._resolved: dict[str, str | None] = {}
        self._no_think_unsupported: set[str] = set()
        self._server_proc: subprocess.Popen | None = None
        self.total_requests = 0
        self.total_failures = 0

    # ------------------------------------------------------------------ plumbing
    @property
    def base_url(self) -> str:
        return self.settings.base_url

    @property
    def last_error(self) -> str:
        return self._last_error

    def _timeout(self, total: float | None) -> httpx.Timeout:
        return httpx.Timeout(total or self.settings.timeout_s, connect=self.settings.connect_timeout_s)

    def _async_client(self) -> httpx.AsyncClient:
        loop = asyncio.get_running_loop()
        key = id(loop)
        client = self._async_clients.get(key)
        if client is None or client.is_closed:
            kwargs: dict[str, Any] = {"base_url": self.base_url, "timeout": self._timeout(None)}
            if self._transport is not None:
                kwargs["transport"] = self._transport
            client = httpx.AsyncClient(**kwargs)
            self._async_clients[key] = client
        return client

    def _client_sync(self) -> httpx.Client:
        with self._lock:
            if self._sync_client is None or self._sync_client.is_closed:
                kwargs: dict[str, Any] = {"base_url": self.base_url, "timeout": self._timeout(None)}
                if self._transport is not None:
                    kwargs["transport"] = self._transport
                self._sync_client = httpx.Client(**kwargs)
            return self._sync_client

    def _breaker_open(self) -> bool:
        return time.monotonic() < self._down_until

    def _trip(self, exc: BaseException) -> None:
        self._down_until = time.monotonic() + self.settings.breaker_cooldown_s
        self._last_error = f"{type(exc).__name__}: {exc}"
        self.total_failures += 1
        logger.info("Ollama unreachable at %s (%s); retry after %.0fs", self.base_url, exc, self.settings.breaker_cooldown_s)
        if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
            self._autostart_async()

    def _reset_breaker(self) -> None:
        self._down_until = 0.0

    def mark_unavailable(self, seconds: float | None = None) -> None:
        self._down_until = time.monotonic() + (seconds or self.settings.breaker_cooldown_s)

    # ------------------------------------------------------------------ discovery
    def _store_models(self, payload: dict[str, Any]) -> list[str]:
        models = [m.get("name") or m.get("model") or "" for m in payload.get("models", [])]
        self._models = [m for m in models if m]
        self._models_at = time.monotonic()
        self._resolved.clear()
        self._reset_breaker()
        return self._models

    def _models_fresh(self) -> bool:
        return bool(self._models_at) and (time.monotonic() - self._models_at) < self.settings.tags_ttl_s

    async def list_models(self, refresh: bool = False) -> list[str]:
        if not refresh and self._models_fresh():
            return list(self._models)
        if self._breaker_open():
            raise LLMUnavailable(f"Ollama is not reachable at {self.base_url}")
        try:
            resp = await self._async_client().get("/api/tags", timeout=httpx.Timeout(8.0, connect=self.settings.connect_timeout_s))
            resp.raise_for_status()
            return list(self._store_models(resp.json()))
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            self._trip(exc)
            self._autostart_async()
            raise LLMUnavailable(f"Ollama is not reachable at {self.base_url}: {exc}") from exc
        except (httpx.TransportError, httpx.HTTPStatusError, ValueError) as exc:
            # The server answered (or is busy loading a model): keep using the last known model list.
            if self._models:
                logger.info("Ollama model list refresh failed (%s); using the cached list", exc)
                return list(self._models)
            self._trip(exc)
            raise LLMUnavailable(f"Ollama is not reachable at {self.base_url}: {exc}") from exc

    def list_models_sync(self, refresh: bool = False) -> list[str]:
        if not refresh and self._models_fresh():
            return list(self._models)
        if self._breaker_open():
            raise LLMUnavailable(f"Ollama is not reachable at {self.base_url}")
        try:
            resp = self._client_sync().get("/api/tags", timeout=httpx.Timeout(8.0, connect=self.settings.connect_timeout_s))
            resp.raise_for_status()
            return list(self._store_models(resp.json()))
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            self._trip(exc)
            raise LLMUnavailable(f"Ollama is not reachable at {self.base_url}: {exc}") from exc
        except (httpx.TransportError, httpx.HTTPStatusError, ValueError) as exc:
            if self._models:
                logger.info("Ollama model list refresh failed (%s); using the cached list", exc)
                return list(self._models)
            self._trip(exc)
            raise LLMUnavailable(f"Ollama is not reachable at {self.base_url}: {exc}") from exc

    async def available(self, refresh: bool = False) -> bool:
        try:
            return bool(await self.list_models(refresh=refresh))
        except LLMUnavailable:
            return False

    def available_sync(self, refresh: bool = False) -> bool:
        try:
            return bool(self.list_models_sync(refresh=refresh))
        except LLMUnavailable:
            return False

    def _resolve_from(self, role: str, installed: list[str]) -> str | None:
        if role in self._resolved:
            return self._resolved[role]
        chosen: str | None = None
        for alias in ROLE_FALLBACKS.get(role, (role,)):
            chosen = match_installed(self.settings.model_for(alias), installed)
            if chosen:
                break
        if not chosen:
            chosen = choose_fallback(role, installed)
        self._resolved[role] = chosen
        if chosen:
            logger.debug("LLM role %s -> %s", role, chosen)
        return chosen

    async def resolve(self, role: str = "chat") -> str:
        installed = await self.list_models()
        chosen = self._resolve_from(role, installed)
        if not chosen:
            raise LLMUnavailable(f"No installed Ollama model suits role '{role}'. Run: ollama pull {self.settings.model_for(role) or 'llama3.2'}")
        return chosen

    def resolve_sync(self, role: str = "chat") -> str:
        installed = self.list_models_sync()
        chosen = self._resolve_from(role, installed)
        if not chosen:
            raise LLMUnavailable(f"No installed Ollama model suits role '{role}'. Run: ollama pull {self.settings.model_for(role) or 'llama3.2'}")
        return chosen

    def cached_model(self, role: str) -> str | None:
        """Model chosen for a role without I/O (None until the first resolution)."""
        return self._resolved.get(role)

    # ------------------------------------------------------------------ requests
    def _chat_payload(
        self,
        model: str,
        messages: list[dict[str, Any]],
        schema: Any,
        tools: list[dict[str, Any]] | None,
        temperature: float,
        max_tokens: int,
        think: bool,
        stream: bool,
        num_ctx: int | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "keep_alive": self.settings.keep_alive,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": num_ctx or self.settings.num_ctx,
            },
        }
        if schema is not None:
            payload["format"] = schema
        if tools:
            payload["tools"] = tools
        if is_thinking_model(model) and model not in self._no_think_unsupported:
            payload["think"] = bool(think)
        return payload

    def _parse_chat(self, model: str, body: dict[str, Any], schema: Any) -> ChatResult:
        message = body.get("message") or {}
        raw = message.get("content") or body.get("response") or ""
        text = strip_thinking(raw)
        timings = {}
        for key in ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration"):
            if key in body:
                timings[key.replace("_duration", "_ms")] = body[key] / 1e6
        data = extract_json(text) if schema is not None else None
        return ChatResult(text=text, model=model, data=data, tool_calls=list(message.get("tool_calls") or []), timings_ms=timings)

    def _handle_http_error(self, model: str, resp: httpx.Response, payload: dict[str, Any]) -> bool:
        """Return True when the request should be retried (after adjusting the payload)."""
        body = resp.text[:300]
        if resp.status_code == 400 and "think" in body.lower() and "think" in payload:
            self._no_think_unsupported.add(model)
            payload.pop("think", None)
            return True
        if resp.status_code == 404 and "not found" in body.lower():
            # Model disappeared (deleted / renamed): force re-resolution next time.
            self._resolved.clear()
            self._models_at = 0.0
        raise LLMError(f"Ollama HTTP {resp.status_code}: {body}")

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        role: str = "chat",
        model: str | None = None,
        schema: Any = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        think: bool = False,
        timeout: float | None = None,
        num_ctx: int | None = None,
    ) -> ChatResult:
        model = model or await self.resolve(role)
        payload = self._chat_payload(model, messages, schema, tools, temperature, max_tokens, think, False, num_ctx)
        self.total_requests += 1
        for _ in range(2):
            try:
                resp = await self._async_client().post("/api/chat", json=payload, timeout=self._timeout(timeout))
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                self._trip(exc)
                raise LLMUnavailable(f"Ollama is not reachable at {self.base_url}") from exc
            except httpx.TimeoutException as exc:
                self.total_failures += 1
                self._last_error = f"timeout after {timeout or self.settings.timeout_s:.0f}s"
                raise LLMError(f"Model {model} timed out") from exc
            if resp.status_code == 200:
                return self._parse_chat(model, resp.json(), schema)
            if not self._handle_http_error(model, resp, payload):
                break
        raise LLMError("Ollama chat request failed")

    def chat_sync(
        self,
        messages: list[dict[str, Any]],
        *,
        role: str = "chat",
        model: str | None = None,
        schema: Any = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        think: bool = False,
        timeout: float | None = None,
        num_ctx: int | None = None,
    ) -> ChatResult:
        model = model or self.resolve_sync(role)
        payload = self._chat_payload(model, messages, schema, None, temperature, max_tokens, think, False, num_ctx)
        self.total_requests += 1
        for _ in range(2):
            try:
                resp = self._client_sync().post("/api/chat", json=payload, timeout=self._timeout(timeout))
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                self._trip(exc)
                raise LLMUnavailable(f"Ollama is not reachable at {self.base_url}") from exc
            except httpx.TimeoutException as exc:
                self.total_failures += 1
                raise LLMError(f"Model {model} timed out") from exc
            if resp.status_code == 200:
                return self._parse_chat(model, resp.json(), schema)
            if not self._handle_http_error(model, resp, payload):
                break
        raise LLMError("Ollama chat request failed")

    async def chat_json(self, messages: list[dict[str, Any]], schema: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("temperature", 0.0)
        result = await self.chat(messages, schema=schema, **kwargs)
        if not isinstance(result.data, dict):
            raise LLMError("Model returned JSON that is not an object")
        result.data.setdefault("_model", result.model)
        return result.data

    def chat_json_sync(self, messages: list[dict[str, Any]], schema: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("temperature", 0.0)
        result = self.chat_sync(messages, schema=schema, **kwargs)
        if not isinstance(result.data, dict):
            raise LLMError("Model returned JSON that is not an object")
        result.data.setdefault("_model", result.model)
        return result.data

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        *,
        role: str = "chat",
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 512,
        timeout: float | None = None,
    ) -> AsyncIterator[str]:
        """Yield cleaned text deltas as the model produces them (think blocks suppressed)."""
        model = model or await self.resolve(role)
        payload = self._chat_payload(model, messages, None, None, temperature, max_tokens, False, True, None)
        self.total_requests += 1
        in_think = False
        try:
            async with self._async_client().stream("POST", "/api/chat", json=payload, timeout=self._timeout(timeout)) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode("utf-8", "ignore")[:300]
                    raise LLMError(f"Ollama HTTP {resp.status_code}: {body}")
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    delta = (chunk.get("message") or {}).get("content", "")
                    out = ""
                    while delta:
                        tag = "</think>" if in_think else "<think>"
                        idx = delta.find(tag)
                        if idx < 0:
                            out += "" if in_think else delta
                            break
                        if not in_think:
                            out += delta[:idx]
                        delta = delta[idx + len(tag):]
                        in_think = not in_think
                    if out:
                        yield out
                    if chunk.get("done"):
                        break
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            self._trip(exc)
            raise LLMUnavailable(f"Ollama is not reachable at {self.base_url}") from exc
        except httpx.TimeoutException as exc:
            self.total_failures += 1
            raise LLMError(f"Model {model} timed out while streaming") from exc
        except httpx.HTTPError as exc:
            self.total_failures += 1
            raise LLMError(f"Streaming from {model} failed: {exc}") from exc

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        if not texts:
            return []
        model = model or await self.resolve("embed")
        client = self._async_client()
        try:
            resp = await client.post("/api/embed", json={"model": model, "input": texts, "keep_alive": self.settings.keep_alive})
            if resp.status_code == 200:
                vectors = resp.json().get("embeddings") or []
                if len(vectors) == len(texts):
                    return vectors
            # Older servers only expose the single-prompt endpoint.
            vectors = []
            for text in texts:
                legacy = await client.post("/api/embeddings", json={"model": model, "prompt": text})
                if legacy.status_code != 200:
                    raise LLMError(f"Embedding failed: HTTP {legacy.status_code}")
                vectors.append(legacy.json().get("embedding") or [])
            return vectors
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            self._trip(exc)
            raise LLMUnavailable(f"Ollama is not reachable at {self.base_url}") from exc

    def embed_sync(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        if not texts:
            return []
        model = model or self.resolve_sync("embed")
        client = self._client_sync()
        try:
            resp = client.post("/api/embed", json={"model": model, "input": texts, "keep_alive": self.settings.keep_alive})
            if resp.status_code == 200:
                vectors = resp.json().get("embeddings") or []
                if len(vectors) == len(texts):
                    return vectors
            vectors = []
            for text in texts:
                legacy = client.post("/api/embeddings", json={"model": model, "prompt": text})
                if legacy.status_code != 200:
                    raise LLMError(f"Embedding failed: HTTP {legacy.status_code}")
                vectors.append(legacy.json().get("embedding") or [])
            return vectors
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            self._trip(exc)
            raise LLMUnavailable(f"Ollama is not reachable at {self.base_url}") from exc

    async def warm(self, role: str = "fast") -> str | None:
        """Load a model into memory so the first real request is not slowed by model load."""
        try:
            model = await self.resolve(role)
            await self._async_client().post(
                "/api/generate",
                json={"model": model, "prompt": "", "keep_alive": self.settings.keep_alive},
                timeout=self._timeout(120.0),
            )
            return model
        except Exception as exc:
            logger.debug("Warm-up of %s model skipped: %s", role, exc)
            return None

    # ------------------------------------------------------------------ server lifecycle
    def start_server(self) -> bool:
        """Spawn ``ollama serve`` in the background if an executable is installed."""
        exe = find_ollama_executable()
        if not exe:
            self._last_error = "Ollama executable not found. Install from https://ollama.com/download"
            return False
        flags = 0
        if sys.platform == "win32":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
        try:
            self._server_proc = subprocess.Popen(
                [exe, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=flags,
                start_new_session=sys.platform != "win32",
            )
            logger.info("Started Ollama server: %s serve (pid %s)", exe, self._server_proc.pid)
            return True
        except OSError as exc:
            self._last_error = f"Could not start Ollama: {exc}"
            return False

    async def ensure_server(self, wait_s: float = 20.0) -> bool:
        """Make sure the model server is reachable, starting it when allowed."""
        if await self.available(refresh=True):
            return True
        if not self.settings.auto_start or not self.start_server():
            return False
        deadline = time.monotonic() + wait_s
        while time.monotonic() < deadline:
            await asyncio.sleep(0.75)
            self._reset_breaker()
            if await self.available(refresh=True):
                return True
        return False

    def _autostart_async(self) -> None:
        """Ollama went away: try to (re)start it in the background, at most once a minute."""
        if not self.settings.auto_start:
            return
        now = time.monotonic()
        if now - getattr(self, "_last_autostart", 0.0) < 60.0:
            return
        self._last_autostart = now
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        async def _bring_up():
            try:
                if await self.ensure_server(wait_s=25.0):
                    logger.info("Ollama is reachable again at %s", self.base_url)
            except Exception as exc:
                logger.debug("Ollama auto-start failed: %s", exc)

        task = loop.create_task(_bring_up())
        self._autostart_task = task

    def seems_up(self) -> bool:
        """Cheap, non-blocking guess: models were listed at some point and the breaker is closed."""
        return bool(self._models) and not self._breaker_open()

    def status(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "reachable": self._models_fresh() and not self._breaker_open(),
            "installed_models": list(self._models),
            "roles": {role: self._resolved.get(role) for role in ROLES},
            "configured": {role: self.settings.model_for(role) for role in ROLES},
            "last_error": self._last_error,
            "requests": self.total_requests,
            "failures": self.total_failures,
        }

    async def aclose(self) -> None:
        for client in list(self._async_clients.values()):
            try:
                await client.aclose()
            except Exception:
                pass
        self._async_clients.clear()
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None


_default_client: OllamaClient | None = None
_default_lock = threading.Lock()


def get_llm() -> OllamaClient:
    """Process-wide client (configured from ``jarvis.toml`` on first use)."""
    global _default_client
    with _default_lock:
        if _default_client is None:
            _default_client = OllamaClient(LLMSettings.from_config())
        return _default_client


def set_llm(client: OllamaClient | None) -> None:
    global _default_client
    with _default_lock:
        _default_client = client
