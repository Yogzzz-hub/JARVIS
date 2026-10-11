"""Typed extension metadata and adapters for the existing runtime.

Registries describe explicit, trusted registrations; they never import plugins,
execute skills, grant capabilities, download models or mutate production routes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class ExtensionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(pattern=r"^[a-zA-Z0-9_.:/-]{1,160}$")
    kind: Literal["engine", "model", "agent", "capability", "skill", "memory", "channel", "benchmark", "voice", "transport"]
    version: str = "1.0"
    health: Literal["READY", "DEGRADED", "UNAVAILABLE"] = "UNAVAILABLE"
    available: bool = False
    capabilities: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    ram_bytes: int | None = Field(default=None, ge=0)
    vram_bytes: int | None = Field(default=None, ge=0)
    configuration: Literal["DEFAULT", "CONFIGURED", "DISABLED"] = "DEFAULT"


class ModelSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    model_id: str
    provider: str = "local"
    engine: str = "ollama"
    path: str | None = None
    revision: str | None = None
    sha256: str | None = None
    parameter_count: str | None = None
    active_parameter_count: str | None = None
    quantization: str | None = None
    context_length: int | None = Field(default=None, gt=0)
    ram_bytes: int | None = Field(default=None, ge=0)
    vram_bytes: int | None = Field(default=None, ge=0)
    modality: tuple[str, ...] = ("text",)
    tool_calling_support: bool | None = None
    structured_output_support: bool | None = None
    coding: bool | None = None
    reasoning: bool | None = None
    multilingual: bool | None = None
    latency_class: str | None = None
    cold_start_ms: float | None = Field(default=None, ge=0)
    warm: bool | None = None
    available: bool = False
    fallback_chain: tuple[str, ...] = ()


class SkillSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    version: str = "1.0"
    description: str
    trust: Literal["CORE", "VERIFIED", "LOCAL_WORKSPACE", "UNREVIEWED"] = "UNREVIEWED"
    source: str
    sha256: str
    required_capabilities: tuple[str, ...] = ()
    optional_capabilities: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    preconditions: tuple[str, ...] = ()
    postconditions: tuple[str, ...] = ()
    risk: Literal["READ_ONLY", "REVERSIBLE", "EXTERNAL_EFFECT", "DESTRUCTIVE", "PRIVILEGED"] = "READ_ONLY"
    benchmark: str | None = None

    def validate_enable(self, allowed_capabilities: set[str]):
        if self.trust == "UNREVIEWED":
            raise ValueError("Review imported skills before enabling")
        if not set(self.required_capabilities) <= allowed_capabilities:
            raise ValueError("Skill requires capabilities outside the approved scope")


class ExtensionRegistry:
    def __init__(self, kind: str):
        self.kind = kind
        self._entries: dict[str, ExtensionSpec] = {}

    def register(self, spec: ExtensionSpec):
        if spec.kind != self.kind:
            raise ValueError("Wrong extension kind")
        if spec.id in self._entries:
            raise ValueError("Duplicate extension")
        self._entries[spec.id] = spec

    def list(self):
        return tuple(self._entries.values())


class InferenceEngine(Protocol):
    async def generate(self, messages: list[dict[str, Any]], **kwargs): ...
    def stream(self, messages: list[dict[str, Any]], **kwargs) -> AsyncIterator[Any]: ...
    async def health(self) -> bool: ...
    async def list_models(self) -> list[str]: ...
    async def capabilities(self, model: str): ...
    def resource_status(self) -> dict[str, Any]: ...


class OllamaEngine:
    """Delegates to the single existing client; no duplicate HTTP/model instance."""
    def __init__(self, client):
        self.client = client

    async def generate(self, messages, **kwargs):
        return await self.client.chat(messages, **kwargs)

    def stream(self, messages, **kwargs):
        return self.client.stream_chat(messages, **kwargs)

    async def health(self):
        return await self.client.available()

    async def list_models(self):
        return await self.client.list_models()

    async def capabilities(self, model):
        return await self.client.model_capabilities(model)

    def resource_status(self):
        # Do not infer VRAM or residency from a cached model name.
        return {"client": self.client.status(), "residency": "NOT_MEASURED"}


@dataclass(frozen=True)
class HardwareProfile:
    cpu: str
    ram_total: int
    ram_available: int
    gpu: str | None = None
    vram_total: int | None = None
    cuda_available: bool | None = None

    def eligible(self, model: ModelSpec):
        if not model.available or model.ram_bytes is None:
            return False  # Unknown resource demand is not an eligibility proof.
        if model.ram_bytes > max(0, self.ram_available - 1024**3):
            return False
        if model.vram_bytes and (self.vram_total is None or model.vram_bytes > self.vram_total):
            return False
        return True


class JarvisKernel:
    """Narrow composition facade; Runtime remains lifecycle implementation."""
    def __init__(self, runtime):
        self.runtime = runtime

    async def start(self):
        await self.runtime.start()

    async def close(self):
        await self.runtime.close()

    def health(self):
        return {"core": "READY" if self.runtime.ready else "UNAVAILABLE",
                "voice": "READY" if self.runtime.voice and self.runtime.voice.is_running else "UNAVAILABLE"}
