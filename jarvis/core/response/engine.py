"""Response Engine & Scheduler for JARVIS EDGE Phase 7.

Orchestrates:
1. Instant zero-LLM ACKs via AckCache.
2. Direct final-only responses for instant queries (e.g. time, volume) skipping ACK.
3. Fast-action ACK merge window (cancelling obsolete ACK if execution finishes before ACK starts).
4. Silent execution (0 narration during tools/planning).
5. Spoken confirmation integration with Phase 5 tickets.
6. Verified factual templating via ResponseFormatter.
7. Streaming TTS output via TTSManager.
"""
from __future__ import annotations

import asyncio
import logging
from time import perf_counter_ns
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Protocol

if TYPE_CHECKING:
    from jarvis.core.audio.output.player import AudioOutputManager
from jarvis.core.response.ack_cache import AckCache
from jarvis.core.response.formatter import ResponseFormatter
from jarvis.core.response.models import (
    DeliveryStatus,
    ResponsePriority,
    ResponseType,
    SpokenResponse,
)
from jarvis.core.response.progress import ProgressTracker
from jarvis.core.tts.manager import TTSManager

logger = logging.getLogger("jarvis.response.engine")

INSTANT_INTENTS = {
    "get_time",
    "volume_get",
    "system_info",
    "list_directory",
    "set_voice",
    "show_dashboard",
    "wake_greeting",
}


class ResponseSink(Protocol):
    async def deliver(self, text: str) -> None: ...


class ResponseEngine:
    """Core response coordinator and scheduler."""

    def __init__(
        self,
        ack_cache: Optional[AckCache] = None,
        tts_manager: Optional[TTSManager] = None,
        audio_output: Optional[Any] = None,
        progress_tracker: Optional[ProgressTracker] = None,
        ack_enabled: bool = True,
        ack_merge_ms: float = 150.0,
        instant_threshold_ms: float = 300.0,
        long_task_seconds: float = 15.0,
    ) -> None:
        self.ack_cache = ack_cache or AckCache()
        self.tts = tts_manager or TTSManager()
        if audio_output is None:
            from jarvis.core.audio.output.player import AudioOutputManager
            audio_output = AudioOutputManager()
        self.audio_output = audio_output
        self.progress = progress_tracker or ProgressTracker(progress_threshold_seconds=long_task_seconds)

        self.ack_enabled = ack_enabled
        self.ack_merge_ms = ack_merge_ms
        self.instant_threshold_ms = instant_threshold_ms

        # Active tracking per request
        self._pending_ack_tasks: Dict[str, asyncio.Task] = {}
        self._active_requests: set[str] = set()
        self._spoken_responses: Dict[str, SpokenResponse] = {}

        # Follow-up listening window state
        self.active_followup_window: bool = False
        self.followup_target_request_id: Optional[str] = None
        self._followup_timer: Optional[asyncio.Task] = None

        # Telemetry
        self.total_responses = 0
        self.total_acks_sent = 0
        self.total_final_only = 0
        self.total_acks_cancelled_merge = 0
        self.enabled = False
        # "chime" (default), "voice" (rotating short phrases) or "none" when the wake word is heard.
        self.wake_ack_mode = "chime"
        self._wake_chime: Optional[bytes] = None
        self._speech_tasks = set()
        self._speech_lock = asyncio.Lock()
        self._speech_generation = 0
        self.event_bus = None

    def schedule_final(self, request_id, text):
        self.cancel_pending_ack(request_id)
        self.progress.cancel(request_id)
        generation = self._speech_generation

        async def deliver():
            try:
                async with self._speech_lock:
                    if generation != self._speech_generation:
                        return

                    clean_text = text.strip()
                    if not clean_text:
                        return

                    # 1. Zero-latency path: Check generic phrase cache
                    cached_pcm = getattr(self.tts, "_generic_phrase_cache", {}).get(clean_text)
                    if cached_pcm:
                        resp = SpokenResponse(
                            text=clean_text,
                            type=ResponseType.FINAL,
                            request_id=request_id,
                            priority=ResponsePriority.FINAL,
                            audio_bytes=cached_pcm,
                            sample_rate=self.tts.sample_rate,
                            source="cache",
                        )
                        resp.tts_start_ns = perf_counter_ns()
                        resp.first_pcm_ready_ns = perf_counter_ns()
                        if not self.audio_output.play(resp):
                            raise RuntimeError("Audio output queue rejected cached final response")
                        return

                    # 2. Streaming sentence synthesis
                    chunk_idx = 0
                    stream_failed = False
                    tts_start = perf_counter_ns()
                    try:
                        pending_chunk = None
                        pending_backend = "piper"
                        async for chunk, backend in self.tts.stream(clean_text):
                            if generation != self._speech_generation:
                                return
                            if pending_chunk is not None:
                                resp = SpokenResponse(
                                    text=clean_text if chunk_idx == 0 else f"chunk_{chunk_idx}",
                                    type=ResponseType.FINAL,
                                    request_id=request_id,
                                    priority=ResponsePriority.FINAL,
                                    audio_bytes=pending_chunk.pcm,
                                    sample_rate=pending_chunk.sample_rate or self.tts.sample_rate,
                                    source=pending_backend,
                                    is_chunk=True,
                                    chunk_index=chunk_idx,
                                    is_last_chunk=False,
                                )
                                resp.tts_start_ns = tts_start
                                resp.first_pcm_ready_ns = perf_counter_ns()
                                self.audio_output.play(resp)
                                chunk_idx += 1
                            pending_chunk = chunk
                            pending_backend = backend

                        if pending_chunk is not None:
                            resp = SpokenResponse(
                                text=clean_text if chunk_idx == 0 else f"chunk_{chunk_idx}",
                                type=ResponseType.FINAL,
                                request_id=request_id,
                                priority=ResponsePriority.FINAL,
                                audio_bytes=pending_chunk.pcm,
                                sample_rate=pending_chunk.sample_rate or self.tts.sample_rate,
                                source=pending_backend,
                                is_chunk=(chunk_idx > 0),
                                chunk_index=chunk_idx,
                                is_last_chunk=True,
                            )
                            resp.tts_start_ns = tts_start
                            resp.first_pcm_ready_ns = perf_counter_ns()
                            if not self.audio_output.play(resp):
                                raise RuntimeError("Audio output queue rejected final chunk")
                            return
                    except Exception as st_err:
                        logger.warning("TTS streaming failed (%s); falling back to direct synthesize", st_err)
                        stream_failed = True

                    if chunk_idx == 0 or stream_failed:
                        response = SpokenResponse(
                            text=clean_text,
                            type=ResponseType.FINAL,
                            request_id=request_id,
                            priority=ResponsePriority.FINAL,
                        )
                        response.tts_start_ns = tts_start
                        pcm, backend = await asyncio.to_thread(self.tts.synthesize, clean_text)
                        if generation != self._speech_generation:
                            return
                        if not pcm:
                            raise RuntimeError("TTS produced no audio (" + backend + ")")
                        response.audio_bytes = pcm
                        response.sample_rate = self.tts.sample_rate
                        response.source = backend
                        response.first_pcm_ready_ns = perf_counter_ns()
                        if not self.audio_output.play(response):
                            raise RuntimeError("Audio output queue rejected final response")
            except Exception as exc:
                logger.exception("Spoken response failed")
                if self.event_bus:
                    self.event_bus.emit("tts.error", request_id, error=str(exc))
            finally:
                self._active_requests.discard(request_id)

        task = asyncio.create_task(deliver())
        self._speech_tasks.add(task)
        task.add_done_callback(self._speech_tasks.discard)

    def stop_speaking(self) -> None:
        """Immediately stop all speech: playing audio, queued audio and responses still being synthesized."""
        # Bumping the generation makes in-flight synthesis tasks drop their audio instead of playing it.
        self._speech_generation += 1
        for task in self._pending_ack_tasks.values():
            task.cancel()
        self._pending_ack_tasks.clear()
        output = getattr(self, "audio_output", None)
        if output is not None:
            if hasattr(output, "cancel_all"):
                output.cancel_all()
            else:
                if hasattr(output, "queue"):
                    output.queue.clear()
                if hasattr(output, "cancel_current"):
                    output.cancel_current()
        logger.info("Speech output stopped via stop_speaking")

    async def close(self):
        self.stop_speaking()
        self.close_followup_window()
        await asyncio.gather(*tuple(self._speech_tasks), return_exceptions=True)
        await asyncio.to_thread(self.audio_output.stop)
        self.tts.unload()

    def warm_up(self) -> None:
        """Pre-warm TTS and ACK cache."""
        self.ack_cache.load_cache()
        self.tts.warm_up()
        if getattr(self, "wake_ack_mode", "chime") == "voice":
            from jarvis.core.response.ack_cache import WAKE_VOICE_ACKS
            for phrase in WAKE_VOICE_ACKS:
                if not self.ack_cache.is_cached(phrase):
                    try:
                        pcm, _backend = self.tts.synthesize(phrase)
                        if pcm and getattr(self.tts, "sample_rate", self.ack_cache.sample_rate) == self.ack_cache.sample_rate:
                            self.ack_cache.add_phrase(phrase, pcm)
                    except Exception as exc:
                        logger.debug("Wake phrase %r not synthesized: %s", phrase, exc)
        self.audio_output.start()

    def render(self, result, verification) -> str:
        """Backwards-compatible render method for Phase 1 contracts."""
        if not result.success or not verification or not verification.verified:
            return result.error or (verification.error if verification else "Verification unavailable")
        return ResponseFormatter.format_verified_tool(result.tool_name, result.data)

    async def schedule_ack_or_skip(
        self,
        request_id: str,
        intent: Optional[str],
        is_complex: bool = False,
        is_voice: bool = True,
    ) -> None:
        """Determine whether to emit an immediate ACK or wait/skip for instant query."""
        self._active_requests.add(request_id)
        self.audio_output.queue.register_active_request(request_id)

        if not is_voice or not self.ack_enabled:
            return

        # Instant answer-only queries SKIP ACK
        if intent in INSTANT_INTENTS and not is_complex:
            logger.debug("Request %s matches instant intent %s; skipping ACK", request_id, intent)
            self.total_final_only += 1
            return

        # If complex or planner-bound: immediate ACK without delay
        if is_complex:
            self._dispatch_ack(request_id)
            return

        # For normal actions: schedule ACK with merge window
        # If action verifies before merge window expires, ACK will be cancelled!
        async def _delayed_ack():
            try:
                await asyncio.sleep(self.ack_merge_ms / 1000.0)
                if request_id in self._active_requests:
                    self._dispatch_ack(request_id)
            except asyncio.CancelledError:
                pass

        self._pending_ack_tasks[request_id] = asyncio.create_task(_delayed_ack())

    def _dispatch_ack(self, request_id: str) -> None:
        """Dispatch a cached ACK clip to the audio output queue."""
        phrase, pcm, duration_ms = self.ack_cache.get_ack()
        response = SpokenResponse(
            text=phrase,
            type=ResponseType.ACK,
            request_id=request_id,
            priority=ResponsePriority.ACK,
            interruptible=True,
            audio_bytes=pcm,
            sample_rate=self.ack_cache.sample_rate,
            duration_ms=duration_ms,
        )
        enqueued = self.audio_output.play(response)
        if enqueued:
            self.total_acks_sent += 1
            logger.info("Dispatched ACK %r for request %s", phrase, request_id)

    def play_wake_ack(self, session_id: str = "") -> Optional[SpokenResponse]:
        """Ultra-low-latency dispatch of cached wake ACK ('Yes?' or 'I'm listening.').

        Zero LLM, zero synthesis on hot path. Target p50 < 100ms.
        """
        mode = getattr(self, "wake_ack_mode", "chime")
        if mode == "none":
            return None
        if mode == "chime":
            if self._wake_chime is None:
                from jarvis.core.pulse.earcons import wake_chime_pcm
                self._wake_chime = wake_chime_pcm(self.ack_cache.sample_rate)
            phrase, pcm, duration_ms = "(chime)", self._wake_chime, 240.0
        else:
            phrase, pcm, duration_ms = self.ack_cache.get_wake_ack()
        if not pcm:
            return None
        response = SpokenResponse(
            text=phrase,
            type=ResponseType.ACK,
            request_id=session_id or f"wake_{perf_counter_ns()}",
            priority=ResponsePriority.ACK,
            interruptible=True,
            audio_bytes=pcm,
            sample_rate=self.ack_cache.sample_rate,
            duration_ms=duration_ms,
        )
        response.first_pcm_ready_ns = perf_counter_ns()
        if self.audio_output.play(response):
            self.total_acks_sent += 1
            logger.info("Dispatched instant wake ACK %r (session %s)", phrase, session_id)
            return response
        return None

    def cancel_pending_ack(self, request_id: str) -> bool:
        """Cancel a pending ACK task (used when fast action completes within merge window)."""
        task = self._pending_ack_tasks.pop(request_id, None)
        if task and not task.done():
            task.cancel()
            self.total_acks_cancelled_merge += 1
            self.total_final_only += 1
            logger.info("Cancelled pending ACK for request %s (fast execution merge)", request_id)
            return True
        return False

    def handle_final_result(
        self,
        request_id: str,
        tool_result: Any,
        verification: Any,
        is_voice: bool = True,
    ) -> SpokenResponse:
        """Format verified outcome and stream/play final speech output."""
        # Fast action completion: cancel any pending scheduled ACK
        self.cancel_pending_ack(request_id)

        # Stop long task progress tracking
        self.progress.cancel(request_id)

        # Format deterministic speakable message
        if tool_result and getattr(tool_result, "tool_name", "") == "dag_scheduler":
            # Plan/Graph outcome
            text = ResponseFormatter.format_graph_result(tool_result.data)
        elif tool_result and getattr(tool_result, "success", False) and verification and getattr(verification, "verified", False):
            text = ResponseFormatter.format_verified_tool(tool_result.tool_name, tool_result.data)
        elif tool_result and not getattr(tool_result, "success", False):
            text = ResponseFormatter.sanitize_error(getattr(tool_result, "error", "") or "Task failed")
        elif verification and not getattr(verification, "verified", False):
            if getattr(verification, "status", None) == "uncertain":
                text = "I performed the action, but I couldn't verify whether it completed."
            else:
                text = ResponseFormatter.sanitize_error(getattr(verification, "error", "") or "Verification failed")
        else:
            text = "Task completed."

        response = SpokenResponse(
            text=text,
            type=ResponseType.FINAL,
            request_id=request_id,
            priority=ResponsePriority.FINAL,
            interruptible=True,
            source="verified_engine",
            verified_status="verified" if (verification and getattr(verification, "verified", False)) else "failed",
        )

        if is_voice:
            response.tts_start_ns = perf_counter_ns()
            # Synthesize final response audio via TTSManager
            pcm, backend = self.tts.synthesize(text)
            response.first_pcm_ready_ns = perf_counter_ns()
            response.audio_bytes = pcm
            response.source = backend
            self.audio_output.play(response)

        self._active_requests.discard(request_id)
        self.total_responses += 1
        return response

    def handle_confirmation_prompt(
        self,
        request_id: str,
        prompt_text: str,
        is_voice: bool = True,
    ) -> SpokenResponse:
        """Speak confirmation question and open active follow-up window."""
        self.cancel_pending_ack(request_id)

        response = SpokenResponse(
            text=prompt_text,
            type=ResponseType.CONFIRMATION,
            request_id=request_id,
            priority=ResponsePriority.CONFIRMATION,
            interruptible=False,  # Confirmations are high priority
        )

        if is_voice:
            response.tts_start_ns = perf_counter_ns()
            pcm, backend = self.tts.synthesize(prompt_text)
            response.audio_bytes = pcm
            response.source = backend
            self.audio_output.play(response)

        # Open follow-up window for 10 seconds
        self.open_followup_window(request_id, duration_seconds=10.0)
        return response

    def open_followup_window(self, request_id: str, duration_seconds: float = 10.0) -> None:
        """Open short conversational follow-up window without requiring wake phrase."""
        self.active_followup_window = True
        self.followup_target_request_id = request_id

        if self._followup_timer and not self._followup_timer.done():
            self._followup_timer.cancel()

        async def _close_after():
            # The window counts silence *after* JARVIS finishes talking, so a long spoken answer
            # does not use up the time the user has to reply.
            try:
                remaining = duration_seconds
                step = 0.1
                while remaining > 0:
                    await asyncio.sleep(step)
                    if self._output_busy():
                        remaining = duration_seconds
                    else:
                        remaining -= step
                self.close_followup_window()
            except asyncio.CancelledError:
                pass

        self._followup_timer = asyncio.create_task(_close_after())
        logger.info("Opened voice follow-up window for %.1fs (request %s)", duration_seconds, request_id)

    def _output_busy(self) -> bool:
        output = getattr(self, "audio_output", None)
        if output is None:
            return False
        if getattr(output, "is_playing", False):
            return True
        try:
            return len(output.queue) > 0
        except Exception:
            return False

    def close_followup_window(self) -> None:
        """Close active follow-up window."""
        self.active_followup_window = False
        self.followup_target_request_id = None
        if self._followup_timer and not self._followup_timer.done():
            self._followup_timer.cancel()
        logger.info("Closed voice follow-up window")

    def handle_cancellation(self, request_id: str, is_voice: bool = True) -> SpokenResponse:
        """Handle task cancellation."""
        self.cancel_pending_ack(request_id)
        self.progress.cancel(request_id)
        self.audio_output.cancel_request(request_id)

        pcm, _ = self.ack_cache.get_phrase_bytes("Stopped.") or (b"", 0.0)
        response = SpokenResponse(
            text="Stopped.",
            type=ResponseType.CANCELLED,
            request_id=request_id,
            priority=ResponsePriority.EMERGENCY,
            interruptible=False,
            audio_bytes=pcm,
        )

        if is_voice and pcm:
            self.audio_output.play(response)

        self._active_requests.discard(request_id)
        return response
