"""Barge-In Controller, Self-Trigger Guard & Echo Protection for JARVIS EDGE Phase 7.

Orchestrates:
1. Ultra-low-latency playback interruption (< 150 ms p95) when user speaks.
2. Differentiation between "stop talking" (audio cancel) vs "stop the task" (task cancel).
3. Self-trigger guard gating wake word while Jarvis is speaking.
4. Echo signature filter discarding transcript matching Jarvis's own output.
"""
from __future__ import annotations

import logging
import re
from time import perf_counter_ns
from typing import TYPE_CHECKING, Any, Callable, Optional, Tuple

if TYPE_CHECKING:
    from jarvis.core.audio.output.player import AudioOutputManager

logger = logging.getLogger("jarvis.audio.output.barge_in")


class BargeInController:
    """Manages audio interruption, self-trigger suppression, and control word routing."""

    def __init__(
        self,
        output_manager: AudioOutputManager,
        task_cancellation_fn: Optional[Callable[[], None]] = None,
        enabled: bool = True,
    ) -> None:
        self.output_manager = output_manager
        self.task_cancellation_fn = task_cancellation_fn
        self.enabled = enabled

        # Metrics
        self.total_barge_ins = 0
        self.total_self_triggers_prevented = 0
        self.last_barge_in_cancel_signal_ms = 0.0
        self.last_speech_to_stream_flush_ms = 0.0
        self.last_speech_to_callback_stop_ms = 0.0
        self.last_barge_in_stop_latency_ms = 0.0

    def on_user_speech_started(self, speech_start_ns: Optional[int] = None) -> bool:
        """Called immediately when VAD or wake detector detects user speech."""
        if not self.enabled:
            return False

        if self.output_manager.is_playing:
            t0 = speech_start_ns or perf_counter_ns()
            self.output_manager.cancel_current()
            t_signal = perf_counter_ns()
            self.last_barge_in_cancel_signal_ms = (t_signal - t0) / 1e6
            self.last_barge_in_stop_latency_ms = self.last_barge_in_cancel_signal_ms
            self.total_barge_ins += 1
            logger.info(
                "Barge-in signal dispatched in %.4f ms",
                self.last_barge_in_cancel_signal_ms,
            )
            return True
        return False

    def check_self_echo(self, transcript: str) -> bool:
        """Check if incoming STT transcript matches Jarvis's own recent TTS speech.

        Returns True if transcript is self-echo and should be discarded.
        """
        if not transcript:
            return False

        clean_tx = self._normalize_words(transcript)
        currently_speaking = self.output_manager.currently_spoken_text
        clean_own = self._normalize_words(currently_speaking)

        if not clean_own:
            return False

        # If transcript words are a high-overlap subset of Jarvis's own recent speech
        tx_words = clean_tx.split()
        own_words = clean_own.split()
        if not tx_words or not own_words:
            return False

        tx_set = set(tx_words)
        own_set = set(own_words)
        overlap = len(tx_set & own_set) / len(tx_set)

        if overlap >= 0.75:
            logger.warning("Self-echo detected and discarded: %r (matched %r)", transcript, currently_speaking)
            self.total_self_triggers_prevented += 1
            return True

        return False

    def handle_barge_in_words(self, transcript: str) -> Tuple[bool, str]:
        """Classify whether user speech was 'stop talking' vs 'stop task'.

        Returns (was_control_word, action_taken):
        - ("audio_only") -> stopped TTS only
        - ("task_cancel") -> stopped TTS and cancelled task
        - ("none") -> regular user query, route normally
        """
        lower = transcript.strip().lower()

        # 1. Audio-only stop
        if any(phrase in lower for phrase in ["stop talking", "be quiet", "shut up", "hush", "silence"]):
            self.output_manager.cancel_current()
            logger.info("Barge-in audio-only cancellation: %s", transcript)
            return True, "audio_only"

        # 2. Full task stop / cancel
        if lower in ["stop", "cancel", "abort", "never mind", "nevermind"]:
            self.output_manager.cancel_current()
            if self.task_cancellation_fn:
                self.task_cancellation_fn()
            logger.info("Barge-in task cancellation: %s", transcript)
            return True, "task_cancel"

        return False, "none"

    def should_suppress_wake_word(self) -> bool:
        """Returns True if wake-word detection should be gated because Jarvis is outputting audio."""
        return (self.output_manager.is_playing or
                (perf_counter_ns() - self.output_manager.last_playback_stop_ns) / 1e6 < 500)

    @staticmethod
    def _normalize_words(text: str) -> str:
        """Strip punctuation and lowercase."""
        return re.sub(r"[^\w\s]", "", text.lower()).strip()
