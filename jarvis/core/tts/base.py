"""TTS Abstraction and Protocols for JARVIS EDGE Phase 7.

Defines the TTSEngine protocol, TTSChunk streaming payload, and optional
ResponsePolisher protocol.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterable, Optional, Protocol, runtime_checkable


@dataclass
class TTSChunk:
    """A streaming chunk of raw PCM audio."""
    pcm: bytes
    sample_rate: int = 22050
    sample_width: int = 2
    channels: int = 1
    is_final: bool = False
    first_chunk: bool = False
    text: str = ""
    duration_ms: float = 0.0


@runtime_checkable
class TTSEngine(Protocol):
    """Protocol that every local TTS engine must satisfy."""

    @property
    def backend_name(self) -> str:
        """Name of the backend (e.g. 'piper', 'sapi', 'mock')."""
        ...

    @property
    def is_loaded(self) -> bool:
        """Whether the model/engine is warm in memory."""
        ...

    def load(self) -> None:
        """Warm or initialize the model into memory."""
        ...

    def synthesize(self, text: str) -> bytes:
        """Synthesize complete text to canonical PCM16 bytes."""
        ...

    async def stream(self, text: str) -> AsyncIterable[TTSChunk]:
        """Stream synthesized audio chunks sentence by sentence."""
        ...

    def cancel(self) -> None:
        """Cancel ongoing synthesis."""
        ...

    def unload(self) -> None:
        """Free model resources from memory."""
        ...


@runtime_checkable
class ResponsePolisher(Protocol):
    """Optional factual rephrasing protocol (disabled by default).

    CRITICAL RULE: Cannot alter verified outcome (SUCCESS/FAILED/UNCERTAIN/PARTIAL).
    """

    def polish(self, verified_text: str, context: Optional[dict] = None) -> str:
        """Rephrase verified facts without changing semantics."""
        ...
