from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from jarvis.core.pulse.earcons import EarconManager, EarconType
from jarvis.core.pulse.event_to_speech import EventToSpeechMapper
from jarvis.core.pulse.scheduler import InteractionScheduler, InteractionState
from jarvis.core.pulse.telemetry import DurationPredictor
from jarvis.core.response.models import DeliveryStatus, ResponsePriority, ResponseType, SpokenResponse

logger = logging.getLogger("jarvis.pulse.engine")


class PulseEngine:
    """PULSE: Parallel User Latency & Status Engine.
    Orchestrates the Feedback Lane strictly in parallel with the Action Lane.
    Speech never blocks execution; TTS failures never abort actions.
    """

    def __init__(
        self,
        audio_output: Optional[Any] = None,
        ack_cache: Optional[Any] = None,
        tts_manager: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        race_timer_ms: float = 250.0,
    ) -> None:
        self.audio_output = audio_output
        self.ack_cache = ack_cache
        self.tts = tts_manager
        self.event_bus = event_bus

        if self.audio_output and hasattr(self.audio_output, "start") and not getattr(self.audio_output, "_running", False):
            try:
                self.audio_output.start()
            except Exception:
                pass

        self.earcons = EarconManager(sample_rate=22050)
        self.predictor = DurationPredictor()
        self.scheduler = InteractionScheduler(race_timer_ms=race_timer_ms)

        self._active_interactions: set[str] = set()
        self._speech_tasks: set[asyncio.Task] = set()

    def predict_duration(self, tool_name: str, slots: Optional[Dict[str, Any]] = None) -> float:
        """Estimates execution duration using EWMA online learning."""
        entity = ""
        if slots:
            entity = str(slots.get("name") or slots.get("path") or slots.get("query") or "")
        return self.predictor.predict_duration(tool_name, entity)

    def play_earcon(self, earcon_type: EarconType, request_id: str = "") -> None:
        """Plays an in-memory earcon cue with sub-millisecond dispatch."""
        if not self.audio_output:
            return
        pcm = self.earcons.get_earcon(earcon_type)
        if not pcm:
            return

        duration_ms = (len(pcm) / (1 * 2 * self.earcons.sample_rate)) * 1000.0
        response = SpokenResponse(
            text=f"earcon:{earcon_type.value}",
            type=ResponseType.EARCON,
            request_id=request_id or "earcon",
            priority=ResponsePriority.EMERGENCY,
            interruptible=False,
            audio_bytes=pcm,
            sample_rate=self.earcons.sample_rate,
            duration_ms=duration_ms,
        )
        self.audio_output.play(response)
        logger.debug("Dispatched earcon %s (duration: %.1fms)", earcon_type.value, duration_ms)

    def start_interaction(
        self,
        request_id: str,
        intent: str,
        predicted_duration_ms: float,
        source: str = "voice",
        slots: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Starts the Feedback Lane in parallel with Action Lane execution."""
        self._active_interactions.add(request_id)
        # Enable talkback across all interactive channels (voice, websocket, desktop_ui, local, chat)
        is_interactive = (source in ("voice", "websocket", "desktop_ui", "local", "chat", "ui", "http", "api")) or (self.audio_output is not None and source != "test_silent")

        # Emit UI state transition: UNDERSTOOD
        if self.event_bus:
            self.event_bus.emit("ui.state", request_id, state="UNDERSTOOD")

        earcon, ack_text, use_race = self.scheduler.plan_feedback(
            request_id=request_id,
            intent=intent,
            predicted_duration_ms=predicted_duration_ms,
            is_voice=is_interactive,
            slots=slots,
        )

        # 1. Play initial earcon immediately (< 1ms)
        if earcon:
            self.play_earcon(earcon, request_id)

        # 2. Dispatch verbal micro-ACK immediately without blocking action execution
        if ack_text and is_interactive:
            if use_race:
                self.scheduler.start_race_timer(
                    request_id=request_id,
                    ack_text=ack_text,
                    on_speak_ack=self._dispatch_micro_ack,
                )
            else:
                self._dispatch_micro_ack(request_id, ack_text)

    def _dispatch_micro_ack(self, request_id: str, ack_text: str) -> None:
        """Dispatches a micro-ACK, pulling PCM directly from RAM cache or fast synthesis."""
        if not self.audio_output:
            return

        pcm = b""
        duration_ms = 350.0
        sample_rate = 22050

        # 1. Fast O(1) in-memory RAM lookup
        if self.ack_cache and hasattr(self.ack_cache, "get_phrase_bytes"):
            cached = self.ack_cache.get_phrase_bytes(ack_text)
            if cached:
                pcm, duration_ms = cached
                sample_rate = self.ack_cache.sample_rate

        # 2. Fast synthesis via TTS if available
        if not pcm and self.tts:
            try:
                pcm, _ = self.tts.synthesize(ack_text)
                sample_rate = getattr(self.tts, "sample_rate", 22050)
                duration_ms = (len(pcm) / (2 * sample_rate)) * 1000.0 if pcm else 350.0
            except Exception as ex:
                logger.debug("TTS micro-ACK synthesis error: %s", ex)

        # 3. Fallback to general pre-cached RAM ack
        if not pcm and self.ack_cache:
            phrase, pcm, duration_ms = self.ack_cache.get_ack()
            sample_rate = getattr(self.ack_cache, "sample_rate", 22050)

        response = SpokenResponse(
            text=ack_text,
            type=ResponseType.ACK,
            request_id=request_id,
            priority=ResponsePriority.ACK,
            interruptible=True,
            audio_bytes=pcm if pcm else None,
            sample_rate=sample_rate,
            duration_ms=duration_ms,
        )
        self.audio_output.play(response)
        logger.info("Dispatched micro-ACK %r for request %s", ack_text, request_id)

    def on_execution_started(self, request_id: str) -> None:
        """Notifies feedback lane that tool execution has commenced."""
        self.scheduler.mark_executing(request_id)
        if self.event_bus:
            self.event_bus.emit("ui.state", request_id, state="EXECUTING")

    def on_progress_event(self, request_id: str, event_name: str, payload: Optional[Dict[str, Any]] = None) -> None:
        """Translates verified internal execution milestones into progressive natural speech."""
        speech_text = EventToSpeechMapper.format_event(event_name, payload)
        if not speech_text or not self.audio_output:
            return

        if self.event_bus:
            self.event_bus.emit("ui.progress", request_id, message=speech_text)

        # Synthesize progress update in background without blocking execution
        async def _speak_progress():
            try:
                if self.tts:
                    pcm, backend = await asyncio.to_thread(self.tts.synthesize, speech_text)
                    if pcm:
                        resp = SpokenResponse(
                            text=speech_text,
                            type=ResponseType.PROGRESS,
                            request_id=request_id,
                            priority=ResponsePriority.PROGRESS,
                            interruptible=True,
                            audio_bytes=pcm,
                            sample_rate=self.tts.sample_rate,
                        )
                        self.audio_output.play(resp)
            except Exception as exc:
                logger.debug("Progress speech non-fatal error: %s", exc)

        task = asyncio.create_task(_speak_progress())
        self._speech_tasks.add(task)
        task.add_done_callback(self._speech_tasks.discard)

    def on_execution_finished(
        self,
        request_id: str,
        duration_ms: float,
        tool_name: str,
        entity: str = "",
    ) -> None:
        """Notifies feedback lane that tool execution completed.
        Triggers Race-to-Completion cancellation if action completed under budget!
        """
        # 1. Update EWMA telemetry
        self.predictor.record_observation(tool_name, duration_ms, entity)

        # 2. Race-to-Completion: cancel pending ACK if action finished before timer fired
        cancelled = self.scheduler.cancel_race_timer(request_id)
        if cancelled:
            logger.info("Action %s completed in %.1fms; verbal ACK cancelled via Race-to-Completion",
                        request_id, duration_ms)

        # 3. Emit UI transition: VERIFYING
        if self.event_bus:
            self.event_bus.emit("ui.state", request_id, state="VERIFYING")

    def on_verified(
        self,
        request_id: str,
        is_verified: bool,
        result_message: str,
        is_voice: bool = True,
        is_fast_silent: bool = False,
        is_waiting_confirmation: bool = False,
    ) -> None:
        """Handles post-verification feedback."""
        self.scheduler.mark_verified(request_id)

        # 1. UI state transition: DONE, WAITING_CONFIRMATION, or ERROR
        if is_waiting_confirmation:
            final_ui_state = "WAITING_CONFIRMATION"
        else:
            final_ui_state = "DONE" if is_verified else "ERROR"
        if self.event_bus:
            self.event_bus.emit("ui.state", request_id, state=final_ui_state)

        # 2. Fast action completion earcon (< 250ms) for non-voice requests
        if is_fast_silent and is_verified and not is_voice and not is_waiting_confirmation:
            self.play_earcon(EarconType.SUCCESS, request_id)
            self.scheduler.cleanup(request_id)
            self._active_interactions.discard(request_id)
            return

        # 3. Final spoken response for voice requests or confirmation talk-back
        if (is_voice or is_waiting_confirmation) and result_message and self.audio_output and self.tts:
            async def _speak_final():
                try:
                    import re
                    clean_msg = re.sub(r"[*_`#]", "", result_message)
                    clean_msg = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean_msg)
                    clean_msg = re.sub(r"https?://\S+", "", clean_msg)
                    clean_msg = re.sub(r"\s+", " ", clean_msg).strip()
                    if not clean_msg:
                        clean_msg = result_message

                    pcm, backend = await asyncio.to_thread(self.tts.synthesize, clean_msg)
                    if pcm:
                        resp = SpokenResponse(
                            text=clean_msg,
                            type=ResponseType.FINAL,
                            request_id=request_id,
                            priority=ResponsePriority.FINAL,
                            interruptible=True,
                            audio_bytes=pcm,
                            sample_rate=getattr(self.tts, "sample_rate", 22050),
                        )
                        self.audio_output.play(resp)
                except Exception as exc:
                    logger.warning("Final spoken response non-fatal error: %s", exc)
                finally:
                    self.scheduler.cleanup(request_id)
                    self._active_interactions.discard(request_id)

            task = asyncio.create_task(_speak_final())
            self._speech_tasks.add(task)
            task.add_done_callback(self._speech_tasks.discard)
        else:
            if not is_verified and not is_waiting_confirmation:
                self.play_earcon(EarconType.FAILED_UNCERTAIN, request_id)
            self.scheduler.cleanup(request_id)
            self._active_interactions.discard(request_id)
