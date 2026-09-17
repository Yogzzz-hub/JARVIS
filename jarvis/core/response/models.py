"""Response models and contracts for JARVIS EDGE Phase 7.

Defines ResponseType, ResponsePriority, SpokenResponse, ResponseLifecycle,
and Confirmation contracts.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from time import perf_counter_ns
from typing import Any, Optional


class ResponseType(str, Enum):
    """Types of responses emitted by the response engine."""
    ACK = "ack"
    FINAL = "final"
    CONFIRMATION = "confirmation"
    ERROR = "error"
    PROGRESS = "progress"
    CANCELLED = "cancelled"


class ResponsePriority(IntEnum):
    """Audio output priority levels. Lower number = higher priority."""
    EMERGENCY = 1    # Task cancellation, emergency stop
    CONFIRMATION = 2 # Action verification/confirmation questions
    FINAL = 3        # Verified task results
    PROGRESS = 4     # Long-task single progress cue
    ACK = 5          # Instant pre-generated acknowledgement


class ResponseLifecycle(str, Enum):
    """Response lifecycle state tracking for idempotency."""
    NONE = "none"
    ACK_SENT = "ack_sent"
    FINAL_QUEUED = "final_queued"
    FINAL_STARTED = "final_started"
    FINAL_COMPLETED = "final_completed"


class DeliveryStatus(str, Enum):
    """Delivery status of spoken audio."""
    PENDING = "pending"
    PLAYING = "playing"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    DROPPED_STALE = "dropped_stale"
    FAILED_FALLBACK = "failed_fallback"


@dataclass
class SpokenResponse:
    """Represents a speech output payload."""
    text: str
    type: ResponseType
    request_id: str
    response_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    priority: int = ResponsePriority.FINAL
    interruptible: bool = True
    created_ns: int = field(default_factory=perf_counter_ns)
    source: str = "core"
    verified_status: str = "verified"
    audio_bytes: Optional[bytes] = None
    sample_rate: int = 22050
    duration_ms: float = 0.0
    delivery_status: DeliveryStatus = DeliveryStatus.PENDING

    # Latency instrumentation
    tts_start_ns: int = 0
    first_pcm_ready_ns: int = 0
    first_audio_device_write_ns: int = 0
    playback_started_ns: int = 0
    playback_finished_ns: int = 0


class ConfirmationIntent(str, Enum):
    """Intent parsed from user voice confirmation."""
    AFFIRMATIVE = "affirmative"
    NEGATIVE = "negative"
    AMBIGUOUS = "ambiguous"


class SpokenConfirmationParser:
    """Deterministic grammar parser for spoken confirmation."""

    AFFIRMATIVE_WORDS = {
        "yes", "yeah", "yep", "confirm", "go ahead", "do it",
        "sure", "proceed", "accepted", "approved", "ok", "okay"
    }

    NEGATIVE_WORDS = {
        "no", "nope", "cancel", "stop", "don't", "dont",
        "abort", "reject", "negative", "never mind", "nevermind"
    }

    @classmethod
    def parse(cls, text: str) -> ConfirmationIntent:
        """Deterministically parse text against confirmation grammar."""
        clean = re.sub(r"[^\w\s]", "", text.strip().lower())
        tokens = clean.split()
        if not tokens:
            return ConfirmationIntent.AMBIGUOUS

        # Single word or exact phrase matching
        if clean in cls.AFFIRMATIVE_WORDS:
            return ConfirmationIntent.AFFIRMATIVE
        if clean in cls.NEGATIVE_WORDS:
            return ConfirmationIntent.NEGATIVE

        # Token set matching
        token_set = set(tokens)
        aff_overlap = token_set & cls.AFFIRMATIVE_WORDS
        neg_overlap = token_set & cls.NEGATIVE_WORDS

        if aff_overlap and not neg_overlap:
            return ConfirmationIntent.AFFIRMATIVE
        if neg_overlap and not aff_overlap:
            return ConfirmationIntent.NEGATIVE

        return ConfirmationIntent.AMBIGUOUS
