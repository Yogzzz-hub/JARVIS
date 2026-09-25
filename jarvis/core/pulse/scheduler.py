from __future__ import annotations

import asyncio
import logging
from enum import StrEnum
from typing import Callable, Dict, Optional, Tuple

from jarvis.core.pulse.earcons import EarconType
from jarvis.core.pulse.event_to_speech import EventToSpeechMapper

logger = logging.getLogger("jarvis.pulse.scheduler")


class InteractionState(StrEnum):
    RECEIVED = "RECEIVED"
    DISPATCHED = "DISPATCHED"
    ACK_PENDING = "ACK_PENDING"
    ACK_SPOKEN = "ACK_SPOKEN"
    ACK_CANCELLED = "ACK_CANCELLED"
    EXECUTING = "EXECUTING"
    PROGRESS = "PROGRESS"
    VERIFIED = "VERIFIED"
    FINAL_RESPONSE = "FINAL_RESPONSE"
    CANCELLED = "CANCELLED"


class InteractionScheduler:
    """Manages the lifecycle of feedback for an active command.
    Enforces Adaptive Feedback Budgeting and Race-to-Completion.
    """

    def __init__(
        self,
        fast_threshold_ms: float = 250.0,
        medium_threshold_ms: float = 1200.0,
        long_threshold_ms: float = 4000.0,
        race_timer_ms: float = 250.0,
    ) -> None:
        self.fast_threshold_ms = fast_threshold_ms
        self.medium_threshold_ms = medium_threshold_ms
        self.long_threshold_ms = long_threshold_ms
        self.race_timer_ms = race_timer_ms

        self._states: Dict[str, InteractionState] = {}
        self._ack_timers: Dict[str, asyncio.Task] = {}
        self._predicted_durations: Dict[str, float] = {}

    def get_state(self, request_id: str) -> InteractionState:
        return self._states.get(request_id, InteractionState.RECEIVED)

    def plan_feedback(
        self,
        request_id: str,
        intent: str,
        predicted_duration_ms: float,
        is_voice: bool = True,
        slots: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[EarconType], Optional[str], bool]:
        """Determines initial feedback budget based on predicted execution latency.
        Returns: (initial_earcon, initial_ack_text, requires_race_timer)
        """
        self._states[request_id] = InteractionState.DISPATCHED
        self._predicted_durations[request_id] = predicted_duration_ms

        if not is_voice:
            return None, None, False

        # Instant answer queries (e.g. get_time, volume_get) skip pre-action ACK so answer is immediate
        if intent.lower() in ("get_time", "volume_get", "wake_greeting", "show_dashboard"):
            return EarconType.COMMAND_ACCEPTED, None, False

        ack_text = EventToSpeechMapper.get_contextual_ack(intent, slots)

        # Deliver immediate verbal announcement without race delay for slots or explicit action categories:
        immediate_intents = {
            "read_whatsapp_messages", "read_whatsapp", "summarize_whatsapp_messages", "unread_whatsapp_messages",
            "send_whatsapp_message", "send_whatsapp", "send_email", "gmail_send", "read_emails", "unread_emails",
            "volume_mute", "volume_unmute", "take_screenshot", "quick_notes", "create_note", "meeting_notes",
            "git_status", "git_commit", "run_project_tests", "web_search", "browse_url", "browser_navigate",
            "ollama_chat", "ask_question", "general_question", "workspace", "briefing",
            "planner", "dag_scheduler",
        }
        if slots or intent.lower() in immediate_intents:
            return EarconType.COMMAND_ACCEPTED, ack_text, False

        # 1. Very fast action (< 250ms predicted) without slots -> Earcon only
        if predicted_duration_ms < self.fast_threshold_ms:
            return EarconType.COMMAND_ACCEPTED, None, False

        # 2. Medium action (250ms - 1.2s predicted) -> Short micro-ACK with Race-to-Completion timer
        if predicted_duration_ms < self.medium_threshold_ms:
            return EarconType.COMMAND_ACCEPTED, ack_text, True

        # 3. Longer action (1.2s+) -> Contextual ACK with immediate delivery
        return None, ack_text, False

    def start_race_timer(
        self,
        request_id: str,
        ack_text: str,
        on_speak_ack: Callable[[str, str], None],
    ) -> None:
        """Starts the Race-to-Completion timer. If action finishes before timer, ACK is cancelled."""
        self._states[request_id] = InteractionState.ACK_PENDING

        async def _timer_worker():
            try:
                await asyncio.sleep(self.race_timer_ms / 1000.0)
                if self._states.get(request_id) == InteractionState.ACK_PENDING:
                    self._states[request_id] = InteractionState.ACK_SPOKEN
                    on_speak_ack(request_id, ack_text)
            except asyncio.CancelledError:
                pass
            finally:
                self._ack_timers.pop(request_id, None)

        self._ack_timers[request_id] = asyncio.create_task(_timer_worker())

    def cancel_race_timer(self, request_id: str) -> bool:
        """Cancels pending ACK when the action wins the race to completion."""
        timer = self._ack_timers.pop(request_id, None)
        if timer and not timer.done():
            timer.cancel()
            self._states[request_id] = InteractionState.ACK_CANCELLED
            logger.info("Race-to-Completion won by action for %s; verbal ACK cancelled", request_id)
            return True
        return False

    def mark_executing(self, request_id: str) -> None:
        if self._states.get(request_id) not in (InteractionState.CANCELLED, InteractionState.VERIFIED):
            self._states[request_id] = InteractionState.EXECUTING

    def mark_verified(self, request_id: str) -> None:
        self.cancel_race_timer(request_id)
        self._states[request_id] = InteractionState.VERIFIED

    def mark_finalized(self, request_id: str) -> None:
        self.cancel_race_timer(request_id)
        self._states[request_id] = InteractionState.FINAL_RESPONSE
        self._predicted_durations.pop(request_id, None)

    def cleanup(self, request_id: str) -> None:
        self.cancel_race_timer(request_id)
        self._states.pop(request_id, None)
        self._predicted_durations.pop(request_id, None)
