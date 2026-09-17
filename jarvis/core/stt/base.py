"""STT engine abstractions and contracts for JARVIS EDGE.

Protocol and data contracts for speech-to-text engines.
No router depends directly on whisper/faster-whisper classes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from time import perf_counter_ns
from typing import Protocol, runtime_checkable


@dataclass(slots=True)
class TranscriptPartial:
    """Partial transcript while user is still speaking.

    NOT trusted for state-changing execution.
    """
    session_id: str
    text: str
    start_ms: float = 0.0
    end_ms: float = 0.0
    confidence: float = 0.0
    generated_ns: int = 0

    def __post_init__(self):
        if not self.generated_ns:
            self.generated_ns = perf_counter_ns()


@dataclass(slots=True)
class TranscriptStablePrefix:
    """Stable prefix of transcript — words unchanged across revisions.

    May trigger: normalization, routing hints, READ_ONLY prefetch.
    NEVER triggers state-changing execution.
    """
    session_id: str
    text: str
    stability_score: float = 1.0
    revision_count: int = 0
    generated_ns: int = 0

    def __post_init__(self):
        if not self.generated_ns:
            self.generated_ns = perf_counter_ns()


@dataclass(slots=True)
class TranscriptFinal:
    """Finalized transcript — ready for routing and execution.

    This is the ONLY transcript type that may trigger tool execution.
    """
    session_id: str
    text: str
    language: str = "en"
    duration_ms: float = 0.0
    stt_model: str = ""
    backend: str = ""
    device: str = ""
    stability_score: float = 1.0
    audio_quality: str = "normal"
    finalization_ms: float = 0.0
    segments: list[dict] | None = None
    generated_ns: int = 0

    def __post_init__(self):
        if not self.generated_ns:
            self.generated_ns = perf_counter_ns()


@runtime_checkable
class STTEngine(Protocol):
    """Protocol for speech-to-text engines."""

    async def load(self) -> None: ...
    async def start_session(self, session_id: str) -> None: ...
    async def feed_audio(self, pcm: bytes, sample_rate: int = 16000) -> None: ...
    async def get_partial(self) -> TranscriptPartial | None: ...
    async def finalize(self) -> TranscriptFinal: ...
    async def cancel(self) -> None: ...
    async def unload(self) -> None: ...

    @property
    def is_loaded(self) -> bool: ...

    @property
    def model_name(self) -> str: ...

    @property
    def backend_name(self) -> str: ...

    @property
    def device_name(self) -> str: ...
