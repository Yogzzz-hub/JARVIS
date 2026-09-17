"""Voice pipeline — orchestrates the full voice input flow for JARVIS EDGE.

AudioHub → WakeWord → VAD → STT → Stabilizer → EndpointDetector → Router

Voice creates NO separate execution path. Final transcript feeds
the existing CommandService → SmartRouter → Planner → Policy → ExecutionEngine.
"""
from __future__ import annotations

import asyncio
import logging
from time import perf_counter_ns
from typing import Any

from jarvis.core.audio.frame import AudioFrame, CANONICAL_SAMPLE_RATE
from jarvis.core.audio.hub import AudioHub, AudioConsumer
from jarvis.core.audio.ring_buffer import RingBuffer
from jarvis.core.audio.session import VoiceSession, VoiceState
from jarvis.core.audio.vad import SileroVADEngine, VADState, EndpointDetector
from jarvis.core.audio.wake import OpenWakeWordEngine, PushToTalkEngine, WakeDetection
from jarvis.core.audio.early_router import EarlyRoutePreview
from jarvis.core.stt.base import TranscriptFinal, TranscriptPartial
from jarvis.core.stt.stabilizer import TranscriptStabilizer

logger = logging.getLogger("jarvis.voice.pipeline")


class VoicePipeline:
    """Orchestrates the complete voice input pipeline.

    ARCHITECTURE RULE: Audio capture NEVER waits for STT.
    Audio callback → bounded queue → AudioHub → consumers.
    STT runs in a separate worker, never in audio callback.
    """

    def __init__(
        self,
        hub: AudioHub | None = None,
        wake_engine: OpenWakeWordEngine | None = None,
        ptt_engine: PushToTalkEngine | None = None,
        vad_engine: SileroVADEngine | None = None,
        stt_engine: Any = None,  # STTEngine protocol
        endpoint_detector: EndpointDetector | None = None,
        early_router: EarlyRoutePreview | None = None,
        command_service: Any = None,
        event_bus: Any = None,
        barge_in_controller: Any = None,
        response_engine: Any = None,
        wake_enabled: bool = True,
        ptt_enabled: bool = True,
        voice_enabled: bool = True,
        preroll_ms: int = 500,
        partial_interval_ms: int = 400,
    ):
        self.hub = hub
        self.wake_engine = wake_engine or OpenWakeWordEngine()
        self.ptt_engine = ptt_engine or PushToTalkEngine()
        self.vad = vad_engine or SileroVADEngine()
        self.stt = stt_engine
        self.endpoint = endpoint_detector or EndpointDetector()
        self.early_router = early_router or EarlyRoutePreview()
        self.command_service = command_service
        self.event_bus = event_bus
        self.barge_in = barge_in_controller
        self.response_engine = response_engine
        self.wake_enabled = wake_enabled
        self.ptt_enabled = ptt_enabled
        self.voice_enabled = voice_enabled
        self.preroll_ms = preroll_ms
        self.partial_interval_ms = partial_interval_ms

        self._running = False
        self._session: VoiceSession | None = None
        self._wake_consumer: AudioConsumer | None = None
        self._vad_consumer: AudioConsumer | None = None
        self._task: asyncio.Task | None = None
        self._stabilizer: TranscriptStabilizer | None = None
        self._last_partial_ns: int = 0

        # Metrics
        self.total_sessions = 0
        self.total_wake_triggers = 0
        self.total_ptt_triggers = 0
        self.false_wake_triggers = 0

    async def start(self) -> None:
        """Start the voice pipeline."""
        if not self.voice_enabled:
            logger.info("Voice pipeline disabled by configuration")
            return

        if self.hub is None:
            from jarvis.core.audio.source import MicSource
            self.hub = AudioHub(source=MicSource())

        # Register consumers
        self._wake_consumer = self.hub.register("wake_word", queue_size=50)
        self._vad_consumer = self.hub.register("vad", queue_size=100)

        try:
            await self.hub.start()
        except Exception as exc:
            logger.error("Audio hub start failed (no microphone?): %s", exc)
            if self._session:
                self._session.transition(VoiceState.AUDIO_UNAVAILABLE)
            self._emit("voice.error", error=str(exc))
            return

        if self.ptt_enabled:
            self.ptt_engine.start()

        self._running = True
        self._task = asyncio.create_task(self._main_loop())
        logger.info("Voice pipeline started")

    async def _main_loop(self) -> None:
        """Main voice pipeline loop."""
        try:
            while self._running:
                # Phase 1: Wait for wake word or push-to-talk
                triggered = await self._wait_for_trigger()
                if not triggered or not self._running:
                    continue

                # Phase 2: Active listening + STT session
                await self._handle_speech_session()

        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Voice pipeline error")

    async def _wait_for_trigger(self) -> bool:
        """Wait for wake word detection or push-to-talk.

        Returns True when triggered, False if pipeline is stopping.
        """
        while self._running:
            # Check active follow-up listening window (e.g. after asking confirmation)
            if self.response_engine and getattr(self.response_engine, "active_followup_window", False):
                logger.info("Active follow-up window triggered without wake word")
                return True

            # Check push-to-talk
            if self.ptt_enabled and self.ptt_engine.check():
                self.total_ptt_triggers += 1
                logger.info("Push-to-talk triggered")
                self._emit("voice.wake_detected", source="ptt")
                return True

            # Process wake word audio (suppressed if Jarvis is speaking)
            if self.wake_enabled and self._wake_consumer:
                if self.barge_in and self.barge_in.should_suppress_wake_word():
                    await asyncio.sleep(0.02)
                    continue
                try:
                    frame = await asyncio.wait_for(
                        self._wake_consumer.queue.get(), timeout=0.1
                    )
                    detection = self.wake_engine.feed(frame)
                    if detection and detection.detected:
                        self.total_wake_triggers += 1
                        logger.info("Wake word detected: score=%.3f", detection.score)
                        self._emit("voice.wake_detected", source="wake_word", score=detection.score)
                        return True
                except asyncio.TimeoutError:
                    continue
            else:
                await asyncio.sleep(0.05)

        return False

    async def _handle_speech_session(self) -> None:
        """Handle a complete speech session from wake to final transcript."""
        session = VoiceSession(source="mic")
        session.wake_timestamp_ns = perf_counter_ns()
        session.transition(VoiceState.WAKE_DETECTED)
        session.transition(VoiceState.LISTENING)
        self._session = session
        self.total_sessions += 1
        self._stabilizer = TranscriptStabilizer(session_id=session.session_id)

        # Predictive model load — start STT load immediately on wake
        stt_load_task = None
        if self.stt and not self.stt.is_loaded:
            stt_load_task = asyncio.create_task(self.stt.load())

        # Start STT session
        if self.stt:
            if stt_load_task:
                await stt_load_task
            await self.stt.start_session(session.session_id)
            session.stt_model = self.stt.model_name

        # Feed pre-roll audio from ring buffer
        if self.hub and self.preroll_ms > 0:
            preroll = self.hub.ring.read_last_ms(self.preroll_ms)
            if preroll and self.stt:
                await self.stt.feed_audio(preroll)

        self.vad.reset()
        self._emit("voice.speech_started", session_id=session.session_id)

        # Main speech processing loop
        speech_ended = False
        while self._running and not speech_ended:
            if not self._vad_consumer:
                break

            try:
                frame = await asyncio.wait_for(
                    self._vad_consumer.queue.get(), timeout=0.5
                )
            except asyncio.TimeoutError:
                continue

            session.audio_frames += 1

            # Feed to VAD
            vad_result = self.vad.feed(frame)

            # Feed to STT
            if self.stt and self.stt.is_loaded:
                await self.stt.feed_audio(frame.pcm)

            # Track speech start
            if vad_result.state == VADState.SPEECH and session.speech_start_ns == 0:
                session.speech_start_ns = perf_counter_ns()
                session.transition(VoiceState.SPEECH_ACTIVE)
                if self.barge_in:
                    self.barge_in.on_user_speech_started(session.speech_start_ns)

            # Get partials at configured interval
            now = perf_counter_ns()
            if (
                self.stt
                and self.stt.is_loaded
                and session.speech_start_ns > 0
                and (now - self._last_partial_ns) / 1e6 >= self.partial_interval_ms
            ):
                partial = await self.stt.get_partial()
                if partial and partial.text:
                    self._last_partial_ns = now
                    session.partial_count += 1
                    if session.first_partial_ns == 0:
                        session.first_partial_ns = now

                    self._emit("voice.partial", text=partial.text, session_id=session.session_id)

                    # Update stabilizer
                    stable = self._stabilizer.update(partial)
                    if stable and stable.text:
                        session.stable_prefix = stable.text
                        if session.first_stable_ns == 0:
                            session.first_stable_ns = now
                        session.revision_count = stable.revision_count
                        self._emit("voice.stable_prefix", text=stable.text, session_id=session.session_id)

            # Check endpoint
            if vad_result.state in (VADState.SILENCE, VADState.TRAILING_SILENCE):
                if session.speech_start_ns > 0:  # Only after speech started
                    should_end, reason = self.endpoint.should_finalize(
                        vad_state=vad_result.state,
                        silence_ms=self.vad.silence_duration_ms,
                        utterance_ms=self.vad.speech_duration_ms,
                        stable_text=self._stabilizer.stable_prefix if self._stabilizer else "",
                        router_complete=False,
                    )
                    if should_end:
                        session.speech_end_ns = perf_counter_ns()
                        session.endpoint_reason = reason
                        speech_ended = True
                        self._emit("voice.speech_ended", reason=reason, session_id=session.session_id)

        # Finalize transcript
        session.transition(VoiceState.FINALIZING)
        final = None
        if self.stt and self.stt.is_loaded:
            final = await self.stt.finalize()

        if final and final.text:
            session.final_text = final.text
            session.final_transcript_ns = perf_counter_ns()

            # Strip wake phrase from transcript
            clean_text = self._strip_wake_phrase(final.text)
            if clean_text:
                self._emit("voice.final", text=clean_text, session_id=session.session_id)

                # Route through existing Phase 1-5 pipeline
                await self._route_final(clean_text, session)
            else:
                logger.debug("Empty transcript after wake phrase removal")
        else:
            logger.debug("No final transcript produced")

        # Cleanup session
        session.transition(VoiceState.IDLE)
        self._session = None
        self.wake_engine.reset()
        self.vad.reset()
        if self._stabilizer:
            self._stabilizer.reset()

    async def _route_final(self, text: str, session: VoiceSession) -> None:
        """Route final transcript through existing CommandService.

        Voice uses the EXACT SAME path as text commands:
        CommandService → SmartRouter → Planner → Policy → ExecutionEngine.
        No separate unsafe voice execution path.
        """
        # 1. Echo / Self-Trigger Protection
        if self.barge_in and self.barge_in.check_self_echo(text):
            logger.info("Discarded self-echo: %r", text)
            return

        # 2. Barge-In Control Words ("stop talking" vs "stop task")
        if self.barge_in:
            handled, action = self.barge_in.handle_barge_in_words(text)
            if handled:
                logger.info("Handled barge-in control word: %r (action=%s)", text, action)
                return

        # 3. Close active follow-up window once input is received
        if self.response_engine and getattr(self.response_engine, "active_followup_window", False):
            self.response_engine.close_followup_window()

        if not self.command_service:
            logger.warning("No CommandService configured — transcript not routed: %s", text)
            return

        try:
            from jarvis.core.commands.contracts import CommandRequest
            request = CommandRequest(text=text, source="voice")
            result = await self.command_service.handle(request)
            session.route_complete_ns = perf_counter_ns()
            if hasattr(result, "first_action_ns"):
                session.first_action_ns = result.first_action_ns

            logger.info(
                "Voice command routed: text=%r, speech_end_to_intent=%.1fms",
                text, session.speech_end_to_intent_ms,
            )
        except Exception as exc:
            logger.error("Voice command routing failed: %s", exc)
            session.transition(VoiceState.ERROR)

    @staticmethod
    def _strip_wake_phrase(text: str) -> str:
        """Remove wake phrase from transcript beginning."""
        lower = text.lower().strip()
        wake_phrases = [
            "hey jarvis", "hey jarvis,", "hey jarvis.",
            "hey jarvis ", "jarvis", "jarvis,", "jarvis.",
        ]
        for phrase in wake_phrases:
            if lower.startswith(phrase):
                result = text[len(phrase):].strip().lstrip(",. ")
                return result
        return text

    def _emit(self, event: str, **data) -> None:
        """Emit voice event to EventBus if available."""
        if self.event_bus:
            session_id = data.get("session_id", "")
            if not session_id and self._session:
                session_id = self._session.session_id
            try:
                self.event_bus.emit(event, session_id, **data)
            except Exception:
                pass

    async def stop(self) -> None:
        """Stop the voice pipeline. Microphone closes."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self.ptt_engine:
            self.ptt_engine.stop()
        if self.hub:
            await self.hub.stop()
        if self.stt:
            await self.stt.cancel()
        logger.info("Voice pipeline stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_session(self) -> VoiceSession | None:
        return self._session

    @property
    def metrics(self) -> dict:
        return {
            "running": self._running,
            "voice_enabled": self.voice_enabled,
            "wake_enabled": self.wake_enabled,
            "ptt_enabled": self.ptt_enabled,
            "total_sessions": self.total_sessions,
            "total_wake_triggers": self.total_wake_triggers,
            "total_ptt_triggers": self.total_ptt_triggers,
            "hub_metrics": self.hub.metrics if self.hub else {},
        }
