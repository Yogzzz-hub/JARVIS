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
from jarvis.core.metrics.latency_trace import LatencyTrace
from jarvis.core.stt.base import TranscriptFinal, TranscriptPartial
from jarvis.core.stt.stabilizer import TranscriptStabilizer

logger = logging.getLogger("jarvis.voice.pipeline")

SILENCE_HALLUCINATIONS = frozenset({
    "", "you", "you.", "thank you", "thank you.", "thanks", "thanks.",
    "up on that.", "up on that", "bye", "bye.", "the", "a", "so",
    "i", "um", "uh", "yeah", "yes", "oh", "ok", "okay",
    "thanks for watching", "thanks for watching.",
    "thank you for watching", "thank you for watching.",
    "please subscribe", "subscribe", "subtitles",
})

WAKE_ACTIVATION_PHRASES = frozenset({
    "listen", "listen to me",
    "hey jarvis", "jarvis",
})


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
        preroll_ms: int = 800,
        partial_interval_ms: int = 200,
    ):
        self.hub = hub
        self.wake_engine = wake_engine or OpenWakeWordEngine()
        self.ptt_engine = ptt_engine or PushToTalkEngine()
        self.vad = vad_engine or SileroVADEngine()
        self.stt = stt_engine
        self.endpoint = endpoint_detector or EndpointDetector()
        self.early_router = early_router or EarlyRoutePreview()
        self.command_service = command_service
        if self.command_service and hasattr(self.command_service, "router") and self.early_router:
            if getattr(self.early_router, "_router", None) is None:
                self.early_router._router = getattr(self.command_service, "router", None)
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
        self.last_error = ""
        self.last_result = None
        self.last_timeline = {}
        self._release = False
        self._loop = None
        self._command_tasks = set()

    @property
    def is_running(self) -> bool:
        return self._running

    def request_ptt(self):
        if not self._running or not self.ptt_enabled:
            raise RuntimeError(self.last_error or "Voice input is unavailable")
        if self.response_engine:
            self.response_engine.stop_speaking()
        if self._session is not None:
            self._release = True
        self.ptt_engine._triggered = True

    def release_ptt(self):
        self._release = True

    async def start(self) -> None:
        """Start the voice pipeline."""
        if not self.voice_enabled:
            logger.info("Voice pipeline disabled by configuration")
            return

        if self._running:
            return
        self._loop = asyncio.get_running_loop()
        await asyncio.to_thread(self.vad._ensure_loaded)
        if not self.vad._loaded:
            raise RuntimeError("Silero VAD could not load")
        if self.stt:
            await self.stt.load()
        if self.wake_enabled:
            await asyncio.to_thread(self.wake_engine._ensure_loaded)
            if not self.wake_engine._loaded:
                self.wake_enabled = False
                self._emit("voice.error", error="Wake model unavailable; PTT remains available")

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
            self.last_error = str(exc)
            return

        if self.ptt_enabled:
            self.ptt_engine.start(callback=lambda: self._loop.call_soon_threadsafe(self.request_ptt))

        self._running = True
        self._task = asyncio.create_task(self._main_loop())
        logger.info("Voice pipeline started")

    async def _main_loop(self) -> None:
        """Main voice pipeline loop."""
        try:
            while self._running:
                # Phase 1: Wait for wake word, push-to-talk, or follow-up speech
                trigger = await self._wait_for_trigger()
                if not trigger or not self._running:
                    continue
                trigger_source, initial_frame = trigger

                # Phase 2: Active listening + STT session
                try:
                    await self._handle_speech_session(trigger_source=trigger_source, initial_frame=initial_frame)
                except Exception as exc:
                    self.last_error = str(exc)
                    logger.exception("Voice session failed")
                    self._emit("voice.error", error=str(exc))
                finally:
                    self._session = None
                    self.wake_engine.reset()
                    self.vad.reset()
                    self._drain(self._wake_consumer)

        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Voice pipeline error")

    async def _wait_for_trigger(self) -> tuple[str, AudioFrame | None] | None:
        """Wait for wake word detection, push-to-talk, or follow-up speech.

        Returns (source, initial_frame) when triggered, None if pipeline is stopping.
        """
        while self._running:
            # Check active follow-up listening window (e.g. after asking confirmation or completed task)
            if self.response_engine and getattr(self.response_engine, "active_followup_window", False):
                if self.ptt_enabled and self.ptt_engine.check():
                    self.total_ptt_triggers += 1
                    self.response_engine.close_followup_window()
                    self._emit("voice.wake_detected", source="ptt")
                    return ("ptt", None)

                if self._vad_consumer:
                    try:
                        frame = await asyncio.wait_for(self._vad_consumer.queue.get(), timeout=0.08)
                        vad_res = self.vad.feed(frame)
                        if vad_res.state == VADState.SPEECH:
                            logger.info("Speech detected during active conversation follow-up window")
                            self.response_engine.close_followup_window()
                            return ("followup", frame)
                    except asyncio.TimeoutError:
                        pass
                    continue

            # Check push-to-talk
            if self.ptt_enabled and self.ptt_engine.check():
                self.total_ptt_triggers += 1
                logger.info("Push-to-talk triggered")
                self._emit("voice.wake_detected", source="ptt")
                return ("ptt", None)

            # Process wake word audio (suppressed if Jarvis is speaking)
            if self.wake_enabled and self._wake_consumer:
                if self.barge_in and self.barge_in.should_suppress_wake_word():
                    self._drain(self._wake_consumer)
                    self.wake_engine.reset()
                    await asyncio.sleep(0.02)
                    continue
                try:
                    frame = await asyncio.wait_for(
                        self._wake_consumer.queue.get(), timeout=0.1
                    )
                    detection = await asyncio.to_thread(self.wake_engine.feed, frame)
                    if detection and detection.detected:
                        self.total_wake_triggers += 1
                        logger.info("Wake word detected: score=%.3f", detection.score)
                        self._emit("voice.wake_detected", source="wake_word", score=detection.score)
                        return ("wake_word", None)
                except asyncio.TimeoutError:
                    continue
            else:
                await asyncio.sleep(0.05)

        return None

    async def _handle_speech_session(
        self,
        trigger_source: str = "wake_word",
        initial_frame: AudioFrame | None = None,
    ) -> None:
        """Handle a complete speech session from wake to final transcript."""
        session = VoiceSession(source="mic")
        session.wake_timestamp_ns = perf_counter_ns()
        trace = LatencyTrace(session_id=session.session_id)
        trace.mark("wake_detected", session.wake_timestamp_ns)
        trace.mark("ui_wake_event_sent", perf_counter_ns())
        session.trace = trace

        session.transition(VoiceState.WAKE_DETECTED)

        # Concurrently dispatch cached wake ACK ("Yes?" or "I'm listening.")
        # Only dispatch wake ACK for wake_word or ptt, NEVER during conversational follow-up!
        if trigger_source in ("wake_word", "ptt") and self.response_engine and hasattr(self.response_engine, "play_wake_ack"):
            session.transition(VoiceState.WAKE_ACK)
            trace.mark("wake_ack_requested", perf_counter_ns())
            ack_res = self.response_engine.play_wake_ack(session.session_id)
            if ack_res:
                trace.mark("wake_ack_output_started", perf_counter_ns())

        session.transition(VoiceState.LISTENING)
        self._session = session
        self.total_sessions += 1
        self._stabilizer = TranscriptStabilizer(session_id=session.session_id)
        self._release = False
        self._last_partial_ns = 0
        if trigger_source != "followup":
            self._drain(self._vad_consumer)
        self._emit("voice.listening", session_id=session.session_id)

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

        # Feed pre-roll audio from ring buffer for all triggers so speech onset isn't chopped
        if self.hub and self.preroll_ms > 0:
            preroll = self.hub.ring.read_last_ms(self.preroll_ms)
            if preroll and self.stt:
                await self.stt.feed_audio(preroll)
        elif initial_frame and self.stt:
            await self.stt.feed_audio(initial_frame.pcm)

        if initial_frame:
            session.speech_start_ns = initial_frame.timestamp_ns or perf_counter_ns()
            session.transition(VoiceState.SPEECH_ACTIVE)
            self._emit("voice.speech_started", session_id=session.session_id)

        self.vad.reset()

        # Concurrency & early routing state
        router_complete = False
        partial_task: asyncio.Task | None = None

        async def _run_partial() -> None:
            nonlocal router_complete
            try:
                p = await self.stt.get_partial()
                if p and p.text:
                    now_p = perf_counter_ns()
                    session.partial_count += 1
                    if session.first_partial_ns == 0:
                        session.first_partial_ns = now_p
                        if trace:
                            trace.mark("first_partial_text", now_p)

                    self._emit("voice.partial", text=p.text, session_id=session.session_id)

                    # Update stabilizer
                    stable = self._stabilizer.update(p)
                    if stable and stable.text:
                        session.stable_prefix = stable.text
                        if session.first_stable_ns == 0:
                            session.first_stable_ns = now_p
                            if trace:
                                trace.mark("first_stable_partial", now_p)
                        session.revision_count = stable.revision_count
                        self._emit("voice.stable_prefix", text=stable.text, session_id=session.session_id)

                        # Check early route preview for deterministic intent
                        if self.early_router:
                            pred = await self.early_router.preview(stable)
                            if pred and pred.is_deterministic and pred.is_complete:
                                router_complete = True
            except Exception as exc:
                logger.debug("Background partial failed: %s", exc)

        # Main speech processing loop
        listening_start_ns = perf_counter_ns()
        speech_ended = False
        while self._running and not speech_ended:
            now_loop_ns = perf_counter_ns()

            # Check if assistant audio output is currently active (playing "Yes?" ACK or speech)
            is_speaking = bool(
                self.response_engine
                and getattr(self.response_engine, "audio_output", None)
                and self.response_engine.audio_output.is_playing
            )
            if is_speaking:
                # Keep updating listening_start_ns so pause timeout begins AFTER assistant finishes "Yes?"
                listening_start_ns = now_loop_ns

            elapsed_listening = (now_loop_ns - listening_start_ns) / 1e9

            if session.speech_start_ns > 0:
                speech_elapsed = (now_loop_ns - session.speech_start_ns) / 1e9
                if speech_elapsed > 10.0:
                    session.endpoint_reason = "max_utterance_timeout"
                    session.speech_end_ns = now_loop_ns
                    speech_ended = True
                    self._emit("voice.speech_ended", reason=session.endpoint_reason)
                    break
            else:
                if elapsed_listening > 6.0:  # Allow 6.0s pause window for user to speak after ACK completes
                    session.endpoint_reason = "wake_pause_timeout"
                    session.speech_end_ns = now_loop_ns
                    self._emit("voice.speech_ended", reason=session.endpoint_reason)
                    break

            if elapsed_listening > 60 or self._release:
                session.endpoint_reason = "ptt_release" if self._release else "timeout"
                session.speech_end_ns = now_loop_ns
                self._emit("voice.speech_ended", reason=session.endpoint_reason)
                break
            if not self._vad_consumer:
                break

            try:
                frame = await asyncio.wait_for(
                    self._vad_consumer.queue.get(), timeout=0.2
                )
            except asyncio.TimeoutError:
                continue

            session.audio_frames += 1

            # Feed to VAD
            vad_result = self.vad.feed(frame)

            # Feed to STT
            if self.stt and self.stt.is_loaded:
                await self.stt.feed_audio(frame.pcm)

            # Track speech start and update canonical last_speech_frame_ns
            if vad_result.state == VADState.SPEECH:
                session.last_speech_frame_ns = perf_counter_ns()
                if trace:
                    trace.mark("last_confirmed_speech_frame", session.last_speech_frame_ns)
                if session.speech_start_ns == 0:
                    session.speech_start_ns = session.last_speech_frame_ns
                    if trace:
                        trace.mark("speech_started", session.speech_start_ns)
                    session.transition(VoiceState.SPEECH_ACTIVE)
                    self._emit("voice.speech_started", session_id=session.session_id)
                    logger.info("speech_started %s", session.session_id)
                    if self.barge_in:
                        self.barge_in.on_user_speech_started(session.speech_start_ns)

            # Trigger non-blocking partial background task
            now = perf_counter_ns()
            if (
                self.stt
                and self.stt.is_loaded
                and session.speech_start_ns > 0
                and (partial_task is None or partial_task.done())
                and (now - self._last_partial_ns) / 1e6 >= self.partial_interval_ms
            ):
                self._last_partial_ns = now
                partial_task = asyncio.create_task(_run_partial())

            # Check endpoint
            if vad_result.state in (VADState.SILENCE, VADState.TRAILING_SILENCE):
                if session.speech_start_ns > 0:  # Only after speech started
                    should_end, reason = self.endpoint.should_finalize(
                        vad_state=vad_result.state,
                        silence_ms=self.vad.silence_duration_ms,
                        utterance_ms=self.vad.speech_duration_ms,
                        stable_text=self._stabilizer.stable_prefix if self._stabilizer else "",
                        router_complete=router_complete,
                    )
                    if should_end:
                        session.speech_end_ns = perf_counter_ns()
                        if session.last_speech_frame_ns == 0:
                            session.last_speech_frame_ns = session.speech_start_ns
                        session.endpoint_reason = reason
                        speech_ended = True
                        self._emit("voice.speech_ended", reason=reason, session_id=session.session_id)
                        logger.info("speech_ended %s (%s)", session.session_id, reason)

        # Allow running partial task a brief moment to finish
        if partial_task and not partial_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(partial_task), timeout=0.08)
            except (asyncio.TimeoutError, Exception):
                pass

        # Finalize transcript
        session.transition(VoiceState.FINALIZING)
        self._emit("voice.state", state="transcribing", session_id=session.session_id)
        final = None
        if self.stt and self.stt.is_loaded and (session.speech_start_ns or session.audio_frames > 15):
            final = await self.stt.finalize()

        if final and final.text:
            session.final_text = final.text
            session.final_transcript_ns = perf_counter_ns()
            if trace:
                trace.mark("final_transcript", session.final_transcript_ns)

            # Strip wake phrase from transcript
            clean_text = self._strip_wake_phrase(final.text)
            clean_norm = clean_text.lower().strip().rstrip(".!,?")
            if (
                clean_text
                and clean_norm not in SILENCE_HALLUCINATIONS
                and clean_norm not in WAKE_ACTIVATION_PHRASES
                and len(clean_text.strip()) >= 2
            ):
                self._emit("voice.final", text=clean_text, session_id=session.session_id)

                # Route through existing Phase 1-5 pipeline
                task = asyncio.create_task(self._route_final(clean_text, session))
                self._command_tasks.add(task)
                task.add_done_callback(self._command_tasks.discard)
            else:
                logger.info("Wake-only or conversation activation detected: %r (clean_norm=%r)", final.text, clean_norm)
                self._emit("voice.final", text="Hey Jarvis", session_id=session.session_id)
                # Open active follow-up window (e.g. 10s)
                if self.response_engine and hasattr(self.response_engine, "open_followup_window"):
                    self.response_engine.open_followup_window(session.session_id, duration_seconds=10.0)
        else:
            logger.info("No final transcript produced; holding follow-up window")
            self._emit("voice.final", text="Hey Jarvis", session_id=session.session_id)
            if self.response_engine and hasattr(self.response_engine, "open_followup_window"):
                self.response_engine.open_followup_window(session.session_id, duration_seconds=10.0)
            self._emit("voice.idle", reason="No speech recognized")

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

        trace = getattr(session, "trace", None)
        if trace:
            trace.mark("router_started")

        try:
            from jarvis.core.commands.contracts import CommandRequest
            req_kwargs = {"text": text, "source": "voice"}
            if trace and getattr(trace, "request_id", None):
                req_kwargs["request_id"] = trace.request_id
            request = CommandRequest(**req_kwargs)
            result = await self.command_service.handle(request)
            self.last_result = result.model_dump(mode="json")
            session.route_complete_ns = perf_counter_ns()
            if trace:
                trace.mark("router_finished", session.route_complete_ns)
                trace.mark("task_complete", perf_counter_ns())
            if hasattr(result, "first_action_ns"):
                session.first_action_ns = result.first_action_ns
                if trace and result.first_action_ns:
                    trace.mark("first_external_action", result.first_action_ns)
                    trace.mark("tool_started", result.first_action_ns)
            task = self.command_service.tasks.get(result.request_id)
            if task:
                session.first_action_ns = task.timestamps.get("tool_started_ns", 0)
                if trace:
                    if task.timestamps.get("tool_started_ns", 0):
                        trace.mark("tool_started", task.timestamps["tool_started_ns"])
                    if task.timestamps.get("tool_returned_ns", 0):
                        trace.mark("tool_finished", task.timestamps["tool_returned_ns"])
                    if task.timestamps.get("verification_started_ns", 0):
                        trace.mark("verification_started", task.timestamps["verification_started_ns"])
                    if task.timestamps.get("verification_finished_ns", 0):
                        trace.mark("verification_finished", task.timestamps["verification_finished_ns"])
                    if task.timestamps.get("response_ready_ns", 0):
                        trace.mark("response_ready", task.timestamps["response_ready_ns"])

            # Record audio output timestamp if available
            if self.response_engine and hasattr(self.response_engine, "audio_output"):
                player = getattr(self.response_engine, "audio_output", None)
                if player and getattr(player, "last_playback_start_ns", 0) > 0:
                    session.first_audio_ns = player.last_playback_start_ns
                    if trace:
                        trace.mark("speaker_first_pcm", session.first_audio_ns)

            # Open active follow-up window (e.g. 10s) so user can speak next command without wake word
            if self.response_engine and hasattr(self.response_engine, "open_followup_window"):
                self.response_engine.open_followup_window(session.session_id, duration_seconds=10.0)

            # Print Latency Trace waterfall if trace exists
            if trace:
                logger.info("\n%s", trace.format_waterfall())

            self.last_timeline = session.timeline()
            self._emit("voice.metrics", **self.last_timeline)

            # Log regression warning if simple command exceeds 1500 ms
            total_speech_end_to_response_ms = session.speech_end_to_first_audio_ms or session.speech_end_to_committed_action_ms
            if total_speech_end_to_response_ms > 1500.0:
                logger.warning(
                    "VOICE_LATENCY_REGRESSION: speech_end_to_response=%.1fms (threshold=1500ms). Breakdown: "
                    "endpoint=%.1fms, STT_final=%.1fms, route=%.1fms, tool=%.1fms, first_action=%.1fms",
                    total_speech_end_to_response_ms,
                    session.speech_end_to_endpoint_ms,
                    session.speech_end_to_final_transcript_ms,
                    session.route_ms,
                    session.tool_duration_ms,
                    session.speech_end_to_committed_action_ms,
                )

            logger.info(
                "Voice command routed: text=%r, speech_end_to_intent=%.1fms",
                text, session.speech_end_to_intent_ms,
            )
        except Exception as exc:
            logger.error("Voice command routing failed: %s", exc)
            session.transition(VoiceState.ERROR)
            self._emit("voice.error", error=str(exc))

    @staticmethod
    def _drain(consumer):
        if consumer:
            while not consumer.queue.empty():
                consumer.queue.get_nowait()

    @staticmethod
    def _strip_wake_phrase(text: str) -> str:
        """Remove wake phrase from transcript beginning."""
        lower = text.lower().strip()
        wake_phrases = [
            "hey jarvis", "hey jarvis,", "hey jarvis.",
            "hey jarvis ", "jarvis", "jarvis,", "jarvis.",
            "ok jarvis", "ok jarvis,", "ok jarvis.", "okay jarvis",
            "hello jarvis", "hi jarvis",
        ]
        for phrase in wake_phrases:
            if lower.startswith(phrase):
                result = text[len(phrase):].strip().lstrip(",. ")
                return result

        # Also strip leading conversational wake acks if followed by a command
        # (e.g. "Yes, open Chrome" -> "open Chrome")
        tokens = text.split()
        if len(tokens) > 1 and tokens[0].lower().rstrip(",.!?") in ("yes", "yeah", "yep", "sure", "ok", "okay"):
            return text.split(None, 1)[1].strip().lstrip(",. ")

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
            await self.stt.unload()
        await asyncio.gather(*tuple(self._command_tasks), return_exceptions=True)
        self.wake_engine.close()
        self.vad.close()
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
