"""Unified Latency Observability System for JARVIS EDGE.

Every request receives:
- request_id
- session_id
- utterance_id
- task_id

All timestamps use a single monotonic clock: time.perf_counter_ns().
Zero mixing of wall-clock and monotonic timestamps.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from time import perf_counter_ns
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("jarvis.metrics.latency_trace")

now_ns = perf_counter_ns


@dataclass
class LatencyTrace:
    """High-resolution unified latency trace across voice, routing, tools, and response."""

    request_id: str = field(default_factory=lambda: f"req_{uuid.uuid4().hex[:12]}")
    session_id: str = field(default_factory=lambda: f"ses_{uuid.uuid4().hex[:12]}")
    utterance_id: str = field(default_factory=lambda: f"utt_{uuid.uuid4().hex[:12]}")
    task_id: str = field(default_factory=lambda: f"tsk_{uuid.uuid4().hex[:12]}")

    # 33 Canonical Milestone Timestamps (all in perf_counter_ns)
    audio_callback_received: int = 0
    wake_frame_received: int = 0
    wake_inference_started: int = 0
    wake_detected: int = 0
    ui_wake_event_sent: int = 0
    ui_window_show_requested: int = 0
    ui_first_frame_visible: int = 0
    wake_ack_requested: int = 0
    wake_ack_output_started: int = 0

    speech_started: int = 0
    first_audio_frame: int = 0
    last_confirmed_speech_frame: int = 0
    stt_update_started: int = 0
    first_partial_text: int = 0
    first_stable_partial: int = 0
    final_transcript: int = 0

    router_started: int = 0
    router_finished: int = 0

    model_requested: int = 0
    model_first_token: int = 0
    model_finished: int = 0

    planner_started: int = 0
    planner_finished: int = 0

    tool_started: int = 0
    first_external_action: int = 0
    tool_finished: int = 0

    verification_started: int = 0
    verification_finished: int = 0

    response_ready: int = 0

    tts_enqueued: int = 0
    tts_synthesis_started: int = 0
    tts_first_pcm: int = 0
    speaker_first_pcm: int = 0

    task_complete: int = 0

    # Custom annotations / metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def mark(self, milestone: str, timestamp_ns: Optional[int] = None) -> None:
        """Record a milestone timestamp using the monotonic clock."""
        ts = timestamp_ns if timestamp_ns is not None and timestamp_ns > 0 else perf_counter_ns()
        if hasattr(self, milestone):
            setattr(self, milestone, ts)
        else:
            self.metadata[milestone] = ts

    @staticmethod
    def _elapsed_ms(t_start: int, t_end: int) -> float:
        if t_start > 0 and t_end > 0 and t_end >= t_start:
            return (t_end - t_start) / 1e6
        return 0.0

    # ── Component Intervals (in milliseconds) ──

    @property
    def wake_detection_ms(self) -> float:
        """Wake frame arrival -> wake detected."""
        start = self.wake_inference_started or self.wake_frame_received or self.audio_callback_received
        return self._elapsed_ms(start, self.wake_detected)

    @property
    def dashboard_visible_ms(self) -> float:
        """Wake detected -> dashboard visible / UI event sent."""
        end = self.ui_first_frame_visible or self.ui_window_show_requested or self.ui_wake_event_sent
        return self._elapsed_ms(self.wake_detected, end)

    @property
    def wake_ack_ms(self) -> float:
        """Wake detected -> ACK output started."""
        return self._elapsed_ms(self.wake_detected, self.wake_ack_output_started)

    @property
    def first_partial_stt_ms(self) -> float:
        """Speech started -> first partial text."""
        return self._elapsed_ms(self.speech_started, self.first_partial_text)

    @property
    def stable_partial_ms(self) -> float:
        """First partial -> stable partial confirmed."""
        return self._elapsed_ms(self.first_partial_text, self.first_stable_partial)

    @property
    def final_stt_ms(self) -> float:
        """Speech end / last confirmed speech frame -> final transcript."""
        start = self.last_confirmed_speech_frame or self.speech_started
        return self._elapsed_ms(start, self.final_transcript)

    @property
    def router_ms(self) -> float:
        """Router started -> router finished."""
        return self._elapsed_ms(self.router_started, self.router_finished)

    @property
    def planner_ms(self) -> float:
        """Planner started -> planner finished."""
        return self._elapsed_ms(self.planner_started, self.planner_finished)

    @property
    def tool_ms(self) -> float:
        """Tool started -> tool finished."""
        return self._elapsed_ms(self.tool_started, self.tool_finished)

    @property
    def verifier_ms(self) -> float:
        """Verification started -> verification finished."""
        return self._elapsed_ms(self.verification_started, self.verification_finished)

    @property
    def response_ms(self) -> float:
        """Verification finished -> response ready."""
        start = self.verification_finished or self.tool_finished or self.router_finished
        return self._elapsed_ms(start, self.response_ready)

    @property
    def tts_first_pcm_ms(self) -> float:
        """TTS synthesis started / response ready -> first PCM buffer."""
        start = self.tts_synthesis_started or self.tts_enqueued or self.response_ready
        return self._elapsed_ms(start, self.tts_first_pcm)

    @property
    def speaker_start_ms(self) -> float:
        """First PCM ready -> speaker output started."""
        return self._elapsed_ms(self.tts_first_pcm, self.speaker_first_pcm)

    @property
    def speech_end_to_first_action_ms(self) -> float:
        """Authoritative speech end -> first external action dispatched."""
        start = self.last_confirmed_speech_frame or self.speech_started
        end = self.first_external_action or self.tool_started
        return self._elapsed_ms(start, end)

    @property
    def speech_end_to_speech_ms(self) -> float:
        """Authoritative speech end -> first audio PCM output to speaker."""
        start = self.last_confirmed_speech_frame or self.speech_started
        end = self.speaker_first_pcm or self.tts_first_pcm
        return self._elapsed_ms(start, end)

    def waterfall_components(self) -> list[Tuple[str, float]]:
        """Returns ordered list of (component_name, duration_ms)."""
        components = [
            ("Wake detection", self.wake_detection_ms),
            ("Dashboard visible", self.dashboard_visible_ms),
            ("Wake ACK", self.wake_ack_ms),
            ("First partial STT", self.first_partial_stt_ms),
            ("Stable partial", self.stable_partial_ms),
            ("Final STT", self.final_stt_ms),
            ("Router", self.router_ms),
            ("Tool", self.tool_ms),
            ("Verifier", self.verifier_ms),
            ("Response", self.response_ms),
            ("TTS first PCM", self.tts_first_pcm_ms),
            ("Speaker start", self.speaker_start_ms),
        ]
        return components

    def format_waterfall(self) -> str:
        """Generate formatted latency trace waterfall with automatic largest-component highlight."""
        components = self.waterfall_components()
        valid_items = [(name, val) for name, val in components if val > 0.0]

        # Identify largest bottleneck component
        max_name, max_val = ("", 0.0)
        if valid_items:
            max_name, max_val = max(valid_items, key=lambda item: item[1])

        lines = [
            "=" * 50,
            "JARVIS LATENCY TRACE",
            f"Request:    {self.request_id}",
            f"Session:    {self.session_id}",
            f"Utterance:  {self.utterance_id}",
            "-" * 50,
        ]

        for name, duration in components:
            if duration <= 0.0 and name not in ("Router", "Response"):
                continue
            dur_str = f"{duration:6.1f} ms" if duration >= 1.0 else f"{duration:6.2f} ms"
            highlight = "  <-- [LARGEST BOTTLENECK]" if name == max_name and max_val > 0.0 else ""
            lines.append(f"{name:<28} {dur_str}{highlight}")

        lines.append("-" * 50)
        total_str = f"{self.speech_end_to_speech_ms:6.1f} ms"
        lines.append(f"{'TOTAL SPEECH END -> SPEECH':<28} {total_str}")
        lines.append("=" * 50)

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to structured dictionary for metrics/telemetry storage."""
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "utterance_id": self.utterance_id,
            "task_id": self.task_id,
            "wake_detection_ms": self.wake_detection_ms,
            "dashboard_visible_ms": self.dashboard_visible_ms,
            "wake_ack_ms": self.wake_ack_ms,
            "first_partial_stt_ms": self.first_partial_stt_ms,
            "stable_partial_ms": self.stable_partial_ms,
            "final_stt_ms": self.final_stt_ms,
            "router_ms": self.router_ms,
            "planner_ms": self.planner_ms,
            "tool_ms": self.tool_ms,
            "verifier_ms": self.verifier_ms,
            "response_ms": self.response_ms,
            "tts_first_pcm_ms": self.tts_first_pcm_ms,
            "speaker_start_ms": self.speaker_start_ms,
            "speech_end_to_first_action_ms": self.speech_end_to_first_action_ms,
            "speech_end_to_speech_ms": self.speech_end_to_speech_ms,
            "largest_bottleneck": max(self.waterfall_components(), key=lambda x: x[1])[0] if self.waterfall_components() else "none",
        }
