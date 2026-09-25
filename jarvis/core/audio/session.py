"""Voice session and state machine for JARVIS EDGE.

Tracks complete voice interaction lifecycle from wake detection
through STT to command execution.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from time import perf_counter_ns


class VoiceState(StrEnum):
    """Voice pipeline state machine states."""
    IDLE = "IDLE"
    SLEEPING = "SLEEPING"
    WAKE_DETECTED = "WAKE_DETECTED"
    WAKE_ACK = "WAKE_ACK"
    LISTENING = "LISTENING"
    SPEECH_ACTIVE = "SPEECH_ACTIVE"
    UNDERSTANDING = "UNDERSTANDING"
    FINALIZING = "FINALIZING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PLANNING_EXECUTING = "PLANNING_EXECUTING"
    EXECUTING = "EXECUTING"
    SPEAKING = "SPEAKING"
    FOLLOWUP_WINDOW = "FOLLOWUP_WINDOW"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"
    AUDIO_UNAVAILABLE = "AUDIO_UNAVAILABLE"


# Valid state transitions
_TRANSITIONS: dict[VoiceState, set[VoiceState]] = {
    VoiceState.IDLE: {VoiceState.SLEEPING, VoiceState.WAKE_DETECTED, VoiceState.WAKE_ACK, VoiceState.LISTENING, VoiceState.AUDIO_UNAVAILABLE},
    VoiceState.SLEEPING: {VoiceState.WAKE_DETECTED, VoiceState.WAKE_ACK, VoiceState.LISTENING, VoiceState.AUDIO_UNAVAILABLE},
    VoiceState.WAKE_DETECTED: {VoiceState.WAKE_ACK, VoiceState.LISTENING, VoiceState.IDLE, VoiceState.CANCELLED},
    VoiceState.WAKE_ACK: {VoiceState.LISTENING, VoiceState.IDLE, VoiceState.CANCELLED},
    VoiceState.LISTENING: {VoiceState.SPEECH_ACTIVE, VoiceState.IDLE, VoiceState.SLEEPING, VoiceState.CANCELLED},
    VoiceState.SPEECH_ACTIVE: {VoiceState.UNDERSTANDING, VoiceState.FINALIZING, VoiceState.CANCELLED},
    VoiceState.UNDERSTANDING: {VoiceState.FINALIZING, VoiceState.PLANNING_EXECUTING, VoiceState.EXECUTING, VoiceState.CANCELLED},
    VoiceState.FINALIZING: {VoiceState.ACKNOWLEDGED, VoiceState.PLANNING_EXECUTING, VoiceState.EXECUTING, VoiceState.SPEAKING, VoiceState.IDLE, VoiceState.CANCELLED, VoiceState.ERROR},
    VoiceState.ACKNOWLEDGED: {VoiceState.PLANNING_EXECUTING, VoiceState.EXECUTING, VoiceState.SPEAKING, VoiceState.IDLE},
    VoiceState.PLANNING_EXECUTING: {VoiceState.SPEAKING, VoiceState.FOLLOWUP_WINDOW, VoiceState.IDLE, VoiceState.SLEEPING},
    VoiceState.EXECUTING: {VoiceState.SPEAKING, VoiceState.FOLLOWUP_WINDOW, VoiceState.IDLE, VoiceState.SLEEPING},
    VoiceState.SPEAKING: {VoiceState.FOLLOWUP_WINDOW, VoiceState.LISTENING, VoiceState.IDLE, VoiceState.SLEEPING},
    VoiceState.FOLLOWUP_WINDOW: {VoiceState.LISTENING, VoiceState.SPEECH_ACTIVE, VoiceState.IDLE, VoiceState.SLEEPING},
    VoiceState.CANCELLED: {VoiceState.IDLE, VoiceState.SLEEPING},
    VoiceState.ERROR: {VoiceState.IDLE, VoiceState.SLEEPING},
    VoiceState.AUDIO_UNAVAILABLE: {VoiceState.IDLE, VoiceState.SLEEPING},
}


@dataclass
class VoiceSession:
    """Complete voice interaction session with timing instrumentation.

    Records all latency milestones for speech_end_to_first_action measurement.
    """
    session_id: str = ""
    source: str = "mic"
    state: VoiceState = VoiceState.IDLE
    trace: Any = None

    # Timing milestones (perf_counter_ns)
    wake_timestamp_ns: int = 0
    speech_start_ns: int = 0
    last_speech_frame_ns: int = 0  # Canonical timestamp: last confirmed user speech frame
    first_partial_ns: int = 0
    first_stable_ns: int = 0
    speech_end_ns: int = 0
    final_transcript_ns: int = 0
    route_complete_ns: int = 0
    preview_action_ns: int = 0
    first_action_ns: int = 0
    first_audio_ns: int = 0

    # Audio stats
    audio_frames: int = 0
    dropped_frames: int = 0

    # Transcript stats
    partial_count: int = 0
    revision_count: int = 0
    endpoint_reason: str = ""
    stt_model: str = ""

    # Transcript content
    final_text: str = ""
    stable_prefix: str = ""

    def __post_init__(self):
        if not self.session_id:
            self.session_id = f"vs_{uuid.uuid4().hex[:12]}"

    def transition(self, new_state: VoiceState) -> bool:
        """Transition to new state. Returns True if valid."""
        if new_state in _TRANSITIONS.get(self.state, set()):
            self.state = new_state
            return True
        return False

    # ── Computed latencies ──

    @property
    def canonical_speech_end_ns(self) -> int:
        """Single canonical speech-end reference timestamp."""
        return self.last_speech_frame_ns or self.speech_end_ns

    @property
    def wake_to_speech_ms(self) -> float:
        if self.wake_timestamp_ns and self.speech_start_ns:
            return (self.speech_start_ns - self.wake_timestamp_ns) / 1e6
        return 0.0

    @property
    def speech_to_first_partial_ms(self) -> float:
        if self.speech_start_ns and self.first_partial_ns:
            return (self.first_partial_ns - self.speech_start_ns) / 1e6
        return 0.0

    @property
    def wake_to_first_partial_ms(self) -> float:
        if self.wake_timestamp_ns and self.first_partial_ns:
            return (self.first_partial_ns - self.wake_timestamp_ns) / 1e6
        return 0.0

    @property
    def speech_end_to_final_ms(self) -> float:
        if self.canonical_speech_end_ns and self.final_transcript_ns:
            return (self.final_transcript_ns - self.canonical_speech_end_ns) / 1e6
        return 0.0

    @property
    def speech_end_to_final_transcript_ms(self) -> float:
        return self.speech_end_to_final_ms

    @property
    def speech_end_to_preview_action_ms(self) -> float:
        if self.canonical_speech_end_ns and self.preview_action_ns:
            return (self.preview_action_ns - self.canonical_speech_end_ns) / 1e6
        return 0.0

    @property
    def speech_end_to_committed_action_ms(self) -> float:
        if self.canonical_speech_end_ns and self.first_action_ns:
            return (self.first_action_ns - self.canonical_speech_end_ns) / 1e6
        return 0.0

    @property
    def speech_end_to_intent_ms(self) -> float:
        if self.canonical_speech_end_ns and self.route_complete_ns:
            return (self.route_complete_ns - self.canonical_speech_end_ns) / 1e6
        return 0.0

    @property
    def speech_end_to_first_action_ms(self) -> float:
        return self.speech_end_to_committed_action_ms

    @property
    def speech_end_to_first_audio_ms(self) -> float:
        if self.canonical_speech_end_ns and self.first_audio_ns:
            return (self.first_audio_ns - self.canonical_speech_end_ns) / 1e6
        return 0.0

    @property
    def total_session_ms(self) -> float:
        end = self.first_audio_ns or self.first_action_ns or self.final_transcript_ns or perf_counter_ns()
        start = self.wake_timestamp_ns or self.speech_start_ns or end
        return (end - start) / 1e6

    def timeline(self) -> dict[str, float]:
        """Complete latency timeline in milliseconds."""
        return {
            "wake_to_speech_ms": self.wake_to_speech_ms,
            "speech_to_first_partial_ms": self.speech_to_first_partial_ms,
            "wake_to_first_partial_ms": self.wake_to_first_partial_ms,
            "speech_end_to_final_transcript_ms": self.speech_end_to_final_transcript_ms,
            "speech_end_to_final_ms": self.speech_end_to_final_ms,
            "speech_end_to_preview_action_ms": self.speech_end_to_preview_action_ms,
            "speech_end_to_committed_action_ms": self.speech_end_to_committed_action_ms,
            "speech_end_to_intent_ms": self.speech_end_to_intent_ms,
            "speech_end_to_first_action_ms": self.speech_end_to_first_action_ms,
            "speech_end_to_first_audio_ms": self.speech_end_to_first_audio_ms,
            "total_session_ms": self.total_session_ms,
            "partial_count": self.partial_count,
            "revision_count": self.revision_count,
            "endpoint_reason": self.endpoint_reason,
            "stt_model": self.stt_model,
            "audio_frames": self.audio_frames,
            "dropped_frames": self.dropped_frames,
        }


def on_user_speech_started():
    """Interface for Phase 7 barge-in.

    When implemented, this will pause TTS playback when
    the user starts speaking (interruption).
    """
    pass
