from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
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
        self._ack_pcm: "OrderedDict[str, tuple[bytes, int]]" = OrderedDict()  # recent micro-ACK audio
        self._streams: dict[str, "SpeechStream"] = {}  # requests whose answer is spoken while it is generated

    # Sources whose feedback must never be spoken on the PC (remote or background channels).
    SILENT_SOURCES = frozenset({"whatsapp", "test_silent", "benchmark", "test"})

    @staticmethod
    def split_for_speech(text: str, max_chars: int = 220) -> list[str]:
        """Sentence-sized chunks so the first words play while the rest is still being synthesized."""
        import re
        sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", text or "") if x.strip()]
        chunks: list[str] = []
        for sentence in sentences:
            while len(sentence) > max_chars:
                cut = sentence.rfind(", ", 0, max_chars)
                cut = cut + 1 if cut > max_chars // 3 else sentence.rfind(" ", 0, max_chars)
                cut = cut if cut > 0 else max_chars
                chunks.append(sentence[:cut].strip())
                sentence = sentence[cut:].strip()
            if chunks and len(chunks[-1]) + len(sentence) < 90:
                chunks[-1] = f"{chunks[-1]} {sentence}"
            elif sentence:
                chunks.append(sentence)
        return chunks or ([text.strip()] if text and text.strip() else [])

    def open_speech_stream(self, request_id: str) -> Optional["SpeechStream"]:
        """Speak an answer while the model is still writing it (first sentence plays immediately)."""
        if not (self.audio_output and self.tts):
            return None
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return None
        stream = SpeechStream(self, request_id)
        self._streams[request_id] = stream
        return stream

    def close_speech_stream(self, request_id: str) -> None:
        stream = self._streams.pop(request_id, None)
        if stream is not None:
            stream.close()

    async def _speak_chunk(self, request_id: str, chunk: str, index: int) -> None:
        if getattr(self.tts, "blocking", False):
            pcm, _backend = await asyncio.to_thread(self.tts.synthesize, chunk)
        else:
            pcm, _backend = self.tts.synthesize(chunk)
        if not pcm:
            return
        self.audio_output.play(SpokenResponse(
            text=chunk,
            type=ResponseType.FINAL,
            request_id=request_id,
            priority=ResponsePriority.FINAL,
            interruptible=True,
            audio_bytes=pcm,
            sample_rate=getattr(self.tts, "sample_rate", 22050),
            is_chunk=index > 0,
            chunk_index=index,
        ))

    def _synth_blocks_loop(self) -> bool:
        if not getattr(self.tts, "blocking", False):
            return False
        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            return False

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
        # Talk back on local interactive channels; remote channels (WhatsApp) stay silent on the PC.
        is_interactive = source not in self.SILENT_SOURCES and (
            source in ("voice", "websocket", "desktop_ui", "local", "chat", "ui", "http", "api", "cli")
            or self.audio_output is not None
        )

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

        if not pcm and ack_text in self._ack_pcm:
            pcm, sample_rate = self._ack_pcm[ack_text]
            self._ack_pcm.move_to_end(ack_text)
            duration_ms = (len(pcm) / (2 * sample_rate)) * 1000.0

        # 2. Synthesis via TTS: off the event loop for real (blocking) engines.
        if not pcm and self.tts and self._synth_blocks_loop():
            task = asyncio.get_running_loop().create_task(self._synthesize_ack_async(request_id, ack_text))
            self._speech_tasks.add(task)
            task.add_done_callback(self._speech_tasks.discard)
            return
        if not pcm and self.tts:
            try:
                pcm, _ = self.tts.synthesize(ack_text)
                sample_rate = getattr(self.tts, "sample_rate", 22050)
                duration_ms = (len(pcm) / (2 * sample_rate)) * 1000.0 if pcm else 350.0
                self._remember_ack(ack_text, pcm, sample_rate)
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

    def _remember_ack(self, text: str, pcm: bytes, sample_rate: int) -> None:
        if pcm:
            self._ack_pcm[text] = (pcm, sample_rate)
            while len(self._ack_pcm) > 64:
                self._ack_pcm.popitem(last=False)

    async def _synthesize_ack_async(self, request_id: str, ack_text: str) -> None:
        try:
            pcm, _ = await asyncio.to_thread(self.tts.synthesize, ack_text)
        except Exception as ex:
            logger.debug("TTS micro-ACK synthesis error: %s", ex)
            pcm = b""
        from jarvis.core.pulse.scheduler import InteractionState
        state = self.scheduler._states.get(request_id)
        if state in (InteractionState.VERIFIED, InteractionState.FINAL_RESPONSE, InteractionState.ACK_CANCELLED):
            return  # the result is already being announced; a late "On it" would be noise
        sample_rate = getattr(self.tts, "sample_rate", 22050)
        if pcm:
            self._remember_ack(ack_text, pcm, sample_rate)
        elif self.ack_cache:
            _, pcm, _ = self.ack_cache.get_ack()
            sample_rate = getattr(self.ack_cache, "sample_rate", 22050)
        if not pcm or not self.audio_output:
            return
        self.audio_output.play(SpokenResponse(
            text=ack_text, type=ResponseType.ACK, request_id=request_id, priority=ResponsePriority.ACK,
            interruptible=True, audio_bytes=pcm, sample_rate=sample_rate,
            duration_ms=(len(pcm) / (2 * sample_rate)) * 1000.0,
        ))

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

        # 3. The answer was already spoken sentence by sentence while it was generated.
        stream = self._streams.pop(request_id, None)
        if stream is not None:
            stream.close()
            if stream.spoke and not is_waiting_confirmation:
                def _done(_task, rid=request_id):
                    self.scheduler.cleanup(rid)
                    self._active_interactions.discard(rid)
                if stream.task is not None:
                    stream.task.add_done_callback(_done)
                else:
                    _done(None)
                return

        # 4. Final spoken response for voice requests or confirmation talk-back
        if (is_voice or is_waiting_confirmation) and result_message and self.audio_output and self.tts:
            async def _speak_final():
                try:
                    from time import perf_counter_ns
                    from jarvis.core.llm.assistant import to_speakable
                    clean_msg = to_speakable(result_message, max_chars=900) or result_message
                    started_ns = perf_counter_ns()
                    for index, chunk in enumerate(self.split_for_speech(clean_msg)):
                        # Stop if the user interrupted (barge-in / "stop talking") after we started.
                        if getattr(self.audio_output, "_cancel_ns", 0) > started_ns:
                            break
                        if getattr(self.tts, "blocking", False):
                            pcm, backend = await asyncio.to_thread(self.tts.synthesize, chunk)
                        else:
                            pcm, backend = self.tts.synthesize(chunk)
                        if not pcm:
                            continue
                        self.audio_output.play(SpokenResponse(
                            text=chunk,
                            type=ResponseType.FINAL,
                            request_id=request_id,
                            priority=ResponsePriority.FINAL,
                            interruptible=True,
                            audio_bytes=pcm,
                            sample_rate=getattr(self.tts, "sample_rate", 22050),
                            is_chunk=index > 0,
                            chunk_index=index,
                        ))
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


class SpeechStream:
    """Ordered sentence queue for one request: synthesizes and plays each sentence as it arrives."""

    def __init__(self, engine: PulseEngine, request_id: str):
        from time import perf_counter_ns
        self.engine = engine
        self.request_id = request_id
        self.started_ns = perf_counter_ns()
        self.queue: asyncio.Queue = asyncio.Queue()
        self.spoke = False
        self.closed = False
        self.task: Optional[asyncio.Task] = asyncio.create_task(self._worker())
        engine._speech_tasks.add(self.task)
        self.task.add_done_callback(engine._speech_tasks.discard)

    def push(self, sentence: str) -> None:
        from jarvis.core.llm.assistant import to_speakable
        text = to_speakable(sentence)
        if self.closed or not text or not any(ch.isalnum() for ch in text):
            return
        if not self.spoke:
            self.spoke = True
            # The real answer is about to play: a pending "one moment" acknowledgement would only delay it.
            try:
                self.engine.scheduler.cancel_race_timer(self.request_id)
            except Exception:
                pass
        self.queue.put_nowait(text)

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self.queue.put_nowait(None)

    async def _worker(self) -> None:
        index = 0
        audio = self.engine.audio_output
        while True:
            chunk = await self.queue.get()
            if chunk is None:
                break
            if getattr(audio, "_cancel_ns", 0) > self.started_ns:
                continue  # barge-in / "stop talking": drop the rest of this answer
            try:
                await self.engine._speak_chunk(self.request_id, chunk, index)
                index += 1
            except Exception as exc:
                logger.warning("Streamed speech chunk failed (non-fatal): %s", exc)
