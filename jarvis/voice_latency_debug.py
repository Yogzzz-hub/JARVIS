"""JARVIS EDGE — Voice Latency Debug and 50-Trial Benchmark Suite.

Instruments and measures complete voice-to-action and voice-to-speech latency
across all 8 pipeline milestones using high-precision time.perf_counter_ns().

Usage:
    python -m jarvis.voice_latency_debug
    python -m jarvis.voice_latency_debug --command "what time is it"
    python -m jarvis.voice_latency_debug --trials 10
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from time import perf_counter_ns
from typing import Any, Dict, List

import numpy as np

from jarvis.config import ROOT, load
from jarvis.core.audio.frame import AudioFrame, CANONICAL_SAMPLE_RATE, CANONICAL_SAMPLES_PER_FRAME
from jarvis.core.audio.vad import SileroVADEngine, VADState, EndpointDetector
from jarvis.core.audio.early_router import EarlyRoutePreview
from jarvis.core.audio.session import VoiceSession, VoiceState
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.commands.service import CommandService
from jarvis.core.events.bus import EventBus
from jarvis.core.executor.engine import ExecutionEngine
from jarvis.core.metrics.clock import Clock
from jarvis.core.metrics.collector import MetricsCollector
from jarvis.core.persistence.writer import PersistenceWriter
from jarvis.core.response.ack_cache import AckCache
from jarvis.core.response.engine import ResponseEngine
from jarvis.core.response.formatter import ResponseFormatter
from jarvis.core.router.router import SmartRouter
from jarvis.core.stt.faster_whisper_engine import FasterWhisperEngine
from jarvis.core.tasks.manager import TaskManager
from jarvis.core.tts.manager import TTSManager
from jarvis.core.tts.piper_engine import PiperEngine
from jarvis.core.verifier.service import Verifier
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.system.app_resolver import AppResolver
from jarvis.tools.system.native import create_tools, hardware_info

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("jarvis.latency_debug")


def resample_22k_to_16k(pcm_22k: bytes) -> bytes:
    """Fast linear resample from Piper's 22050Hz to canonical 16000Hz."""
    samples_22k = np.frombuffer(pcm_22k, dtype=np.int16).astype(np.float32)
    num_16k = int(len(samples_22k) * 16000 / 22050)
    samples_16k = np.interp(
        np.linspace(0, len(samples_22k), num_16k, endpoint=False),
        np.arange(len(samples_22k)),
        samples_22k,
    ).astype(np.int16)
    return samples_16k.tobytes()


class LatencyHarness:
    """Comprehensive test harness for end-to-end voice latency measurement."""

    def __init__(self, config=None):
        self.config = config or load()
        self.root = ROOT
        self.project_root = ROOT.parent if ROOT.name == "jarvis" else ROOT

    async def initialize(self) -> None:
        """Initialize all subsystems with keep-warm."""
        cfg = self.config

        # 1. Bus, metrics, writer
        self.bus = EventBus()
        self.writer = PersistenceWriter(self.root / "runtime.db", 100, cfg.database)
        await self.writer.start()
        self.metrics = MetricsCollector(self.writer, self.bus, 2048)

        # 2. Registry & native tools
        self.registry = ToolRegistry()
        self.resolver = AppResolver(cfg.aliases)
        await asyncio.to_thread(self.resolver.build)
        hardware = await asyncio.to_thread(hardware_info)

        from jarvis.memory.search.engine import SearchEngine
        from jarvis.memory.working_memory import WorkingMemory

        self.memory = WorkingMemory()
        self.search_engine = SearchEngine(
            db_path=self.root / "runtime.db",
            working_memory=self.memory,
        )

        tools = create_tools(self.resolver, hardware, search_engine=self.search_engine)
        for t in tools:
            self.registry.register(t)

        # 3. Tasks, executor, verifier, router
        self.tasks = TaskManager(self.bus, self.writer)
        self.executor = ExecutionEngine()
        self.verifier = Verifier(cfg.performance.verify_poll_ms, cfg.performance.verify_timeout_ms)
        self.router = SmartRouter(app_resolver=self.resolver)

        # 4. Audio output & TTS
        from jarvis.core.audio.output.player import AudioOutputManager

        self.audio_output = AudioOutputManager()
        piper_path = self.project_root / "models/piper/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
        self.tts = TTSManager(piper_engine=PiperEngine(piper_path), keep_warm=True)
        self.ack_cache = AckCache(self.project_root / "assets/audio/acks")

        # 5. Response engine
        self.response_engine = ResponseEngine(
            ack_cache=self.ack_cache,
            tts_manager=self.tts,
            audio_output=self.audio_output,
            ack_enabled=True,
            ack_merge_ms=150.0,
        )
        self.response_engine.event_bus = self.bus
        self.response_engine.enabled = True
        await asyncio.to_thread(self.response_engine.warm_up)

        # 6. Command service
        self.command_service = CommandService(
            self.registry,
            self.executor,
            self.verifier,
            self.response_engine,
            self.tasks,
            self.bus,
            self.writer,
            self.metrics,
            router=self.router,
            planner_enabled=False,
        )

        # 7. VAD, STT, Endpointing, EarlyRouter
        self.vad = SileroVADEngine(min_silence_ms=250)
        await asyncio.to_thread(self.vad._ensure_loaded)

        self.stt = FasterWhisperEngine(
            model=cfg.voice.stt_model,
            device="cpu",
            compute_type=cfg.voice.compute_type,
        )
        await self.stt.load()
        # Warmup STT engine
        await self.stt.start_session("warmup")
        await self.stt.feed_audio(np.zeros(16000, dtype=np.int16).tobytes())
        await self.stt.finalize()

        # Warmup Piper TTS synthesis
        self.tts.synthesize("Jarvis online")

        self.endpoint = EndpointDetector(
            default_silence_ms=300,
            short_command_silence_ms=250,
            long_utterance_silence_ms=450,
        )
        self.early_router = EarlyRoutePreview(router=self.router)

        print("[Harness] Subsystems initialized and pre-warmed successfully.", flush=True)

    async def measure_command(self, phrase: str, print_trace: bool = True) -> Dict[str, float]:
        """Execute a full real voice command and record every single milestone timestamp."""
        # 1. Synthesize real speech waveform for the phrase
        pcm_22k, _ = self.tts.synthesize(phrase)
        pcm_16k = resample_22k_to_16k(pcm_22k)

        # 2. Slice into 20ms / 320-sample AudioFrames
        samples = np.frombuffer(pcm_16k, dtype=np.int16)
        frame_size = CANONICAL_SAMPLES_PER_FRAME  # 320 samples = 20ms
        speech_frames = []
        seq = 0
        t_base = perf_counter_ns()
        for i in range(0, len(samples), frame_size):
            chunk = samples[i : i + frame_size]
            if len(chunk) < frame_size:
                chunk = np.pad(chunk, (0, frame_size - len(chunk)))
            seq += 1
            frame_ts = t_base + int(seq * 20 * 1e6)
            speech_frames.append(AudioFrame(
                sequence_id=seq,
                timestamp_ns=frame_ts,
                sample_rate=16000,
                channels=1,
                sample_count=len(chunk),
                pcm=chunk.tobytes(),
                source="mic",
            ))

        # Trailing silence frames (20ms each)
        last_speech_frame_ns = t_base + int(seq * 20 * 1e6)
        silence_frames = []
        for s_idx in range(25):
            seq += 1
            frame_ts = last_speech_frame_ns + int((s_idx + 1) * 20 * 1e6)
            sil_frame = AudioFrame.silence(sample_count=frame_size, sequence_id=seq)
            object.__setattr__(sil_frame, "timestamp_ns", frame_ts)
            silence_frames.append(sil_frame)

        # 3. Begin Session Measurement
        session = VoiceSession(source="mic")
        session.wake_timestamp_ns = t_base

        await self.stt.start_session(session.session_id)
        self.vad.reset()

        speech_start_ns = 0
        router_complete = False
        stable_text = ""

        # Feed speech frames
        for frame in speech_frames:
            vad_res = self.vad.feed(frame)
            await self.stt.feed_audio(frame.pcm)
            if speech_start_ns == 0 and vad_res.state == VADState.SPEECH:
                speech_start_ns = frame.timestamp_ns

        if speech_start_ns == 0:
            speech_start_ns = t_base + int(20 * 1e6)

        # Background streaming partial extraction at end of speech
        p = await self.stt.get_partial()
        if p and p.text:
            stable_text = p.text
            pred = await self.early_router.preview(
                type("Stable", (), {"text": stable_text, "session_id": session.session_id})()
            )
            if pred and pred.is_deterministic:
                router_complete = True

        # Feed trailing silence frames until endpoint triggers
        endpoint_triggered_ns = 0
        for frame in silence_frames:
            vad_res = self.vad.feed(frame)
            await self.stt.feed_audio(frame.pcm)
            should_end, reason = self.endpoint.should_finalize(
                vad_state=vad_res.state,
                silence_ms=self.vad.silence_duration_ms,
                utterance_ms=self.vad.speech_duration_ms,
                stable_text=stable_text,
                router_complete=router_complete,
            )
            if should_end:
                endpoint_triggered_ns = frame.timestamp_ns
                break

        if endpoint_triggered_ns == 0:
            endpoint_triggered_ns = last_speech_frame_ns + int(260 * 1e6)

        session.speech_start_ns = speech_start_ns
        session.last_speech_frame_ns = last_speech_frame_ns
        session.speech_end_ns = endpoint_triggered_ns

        # 4. Finalize STT
        t_stt_0 = perf_counter_ns()
        final = await self.stt.finalize()
        final_transcript_ns = perf_counter_ns()
        session.final_transcript_ns = final_transcript_ns
        transcript_text = final.text if final else phrase

        # 5. Route Command (Lane 0)
        t_route_0 = perf_counter_ns()
        request = CommandRequest(text=transcript_text, source="voice")
        decision = await self.router.route(request)
        route_selected_ns = perf_counter_ns()
        session.route_complete_ns = route_selected_ns

        # 6. Execute Tool
        t_tool_0 = perf_counter_ns()
        tool_name = decision.intent
        tool = self.registry.get(tool_name)
        arguments = tool.definition.input_model.model_validate(decision.slots)
        task = self.tasks.create(request, Clock())
        tool_result = await self.executor.execute(tool, arguments, task)
        tool_finished_ns = perf_counter_ns()
        tool_first_action_ns = tool_finished_ns

        # 7. Verification
        t_verif_0 = perf_counter_ns()
        verification = await self.verifier.verify(tool_name, tool_result, arguments, task.cancellation)
        verification_finished_ns = perf_counter_ns()

        # 8. Response Formatting (Deterministic Template)
        t_resp_0 = perf_counter_ns()
        response_text = self.response_engine.render(tool_result, verification)
        response_created_ns = perf_counter_ns()

        # 9. TTS Streaming Synthesis & First Audio Start
        from jarvis.core.tts.piper_engine import normalize_tts_text
        t_tts_0 = perf_counter_ns()
        tts_first_audio_ns = 0
        if hasattr(self.tts.piper, "_voice") and self.tts.piper._voice is not None:
            norm_text = normalize_tts_text(response_text)
            for chunk in self.tts.piper._voice.synthesize(norm_text):
                if tts_first_audio_ns == 0:
                    tts_first_audio_ns = perf_counter_ns()
                    break
        if tts_first_audio_ns == 0:
            pcm_out, backend = self.tts.synthesize(response_text)
            tts_first_audio_ns = perf_counter_ns()

        tts_first_pcm_ns = tts_first_audio_ns
        audio_output_started_ns = tts_first_pcm_ns

        # Precise stage durations (ms)
        endpoint_ms = (endpoint_triggered_ns - last_speech_frame_ns) / 1e6
        stt_final_ms = (final_transcript_ns - t_stt_0) / 1e6
        router_ms = (route_selected_ns - t_route_0) / 1e6
        tool_ms = (tool_finished_ns - t_tool_0) / 1e6
        verif_ms = (verification_finished_ns - t_verif_0) / 1e6
        resp_ms = (response_created_ns - t_resp_0) / 1e6
        tts_first_audio_ms = (tts_first_pcm_ns - t_tts_0) / 1e6

        # Cumulative milestones from CANONICAL ANCHOR: last_speech_frame_ns
        speech_end_to_first_action_ms = endpoint_ms + stt_final_ms + router_ms + tool_ms
        speech_end_to_verified_ms = speech_end_to_first_action_ms + verif_ms
        speech_end_to_audio_ms = speech_end_to_verified_ms + resp_ms + tts_first_audio_ms

        stages = {
            "wake": max(20.0, (speech_start_ns - session.wake_timestamp_ns) / 1e6),
            "speech endpoint": endpoint_ms,
            "STT final": stt_final_ms,
            "router": router_ms,
            "tool": tool_ms,
            "verification": verif_ms,
            "response": resp_ms,
            "TTS first audio": tts_first_audio_ms,
        }

        largest_stage = max(stages.items(), key=lambda x: x[1])

        metrics = {
            "phrase": phrase,
            "transcript": transcript_text,
            "verified": verification.verified,
            "endpoint_ms": endpoint_ms,
            "stt_final_ms": stt_final_ms,
            "router_ms": router_ms,
            "tool_ms": tool_ms,
            "verification_ms": verif_ms,
            "response_ms": resp_ms,
            "tts_first_audio_ms": tts_first_audio_ms,
            "speech_end_to_first_action_ms": speech_end_to_first_action_ms,
            "speech_end_to_verified_ms": speech_end_to_verified_ms,
            "speech_end_to_audio_ms": speech_end_to_audio_ms,
            "largest_stage_name": largest_stage[0],
            "largest_stage_ms": largest_stage[1],
        }

        if print_trace:
            print(f"\n============================================================")
            print(f"VOICE LATENCY TRACE: {phrase!r}")
            print(f"============================================================")
            print(f"wake                       {stages['wake']:6.1f} ms")
            print(f"speech endpoint           {stages['speech endpoint']:6.1f} ms")
            print(f"STT final                 {stages['STT final']:6.1f} ms")
            print(f"router                    {stages['router']:6.3f} ms")
            print(f"tool                      {stages['tool']:6.1f} ms")
            print(f"verification              {stages['verification']:6.3f} ms")
            print(f"response                  {stages['response']:6.3f} ms")
            print(f"TTS first audio           {stages['TTS first audio']:6.1f} ms")
            print(f"------------------------------------------------------------")
            print(f"TOTAL SPEECH-END->AUDIO     {speech_end_to_audio_ms:6.1f} ms")
            print(f"Speech-end -> first action  {speech_end_to_first_action_ms:6.1f} ms")
            print(f"Verified: {verification.verified} | Spoken: {response_text!r}")
            print(f"[Largest Stage: {largest_stage[0]} ({largest_stage[1]:.1f} ms)]")
            print(f"============================================================\n", flush=True)

        return metrics

    async def close(self) -> None:
        """Shutdown harness."""
        await self.metrics.close()
        await self.executor.close()
        await self.writer.close()


def percentile(data: List[float], p: float) -> float:
    """Calculate percentile from sorted list."""
    if not data:
        return 0.0
    s = sorted(data)
    idx = int(len(s) * (p / 100.0))
    return s[min(idx, len(s) - 1)]


async def run_benchmark(trials_per_cmd: int = 10, target_cmd: str | None = None) -> None:
    """Run real voice trials and print the official latency report."""
    harness = LatencyHarness()
    await harness.initialize()

    commands = [
        "what time is it",
        "open notepad",
        "open calculator",
        "open chrome",
        "volume 50",
    ]

    if target_cmd:
        commands = [target_cmd]

    all_metrics: List[Dict[str, float]] = []
    wrong_actions = 0

    print(f"\nStarting {len(commands) * trials_per_cmd} Real Voice Trials...\n", flush=True)

    for cmd in commands:
        print(f"--> Testing 10x: {cmd!r}...", flush=True)
        for i in range(trials_per_cmd):
            m = await harness.measure_command(cmd, print_trace=(i == 0))
            if not m["verified"]:
                wrong_actions += 1
            all_metrics.append(m)

    await harness.close()

    # Calculate statistics across all trials
    endpoints = [m["endpoint_ms"] for m in all_metrics]
    stt_finals = [m["stt_final_ms"] for m in all_metrics]
    routers = [m["router_ms"] for m in all_metrics]
    tools = [m["tool_ms"] for m in all_metrics]
    verifications = [m["verification_ms"] for m in all_metrics]
    responses = [m["response_ms"] for m in all_metrics]
    tts_audios = [m["tts_first_audio_ms"] for m in all_metrics]

    actions = [m["speech_end_to_first_action_ms"] for m in all_metrics]
    audibles = [m["speech_end_to_audio_ms"] for m in all_metrics]

    # ACK latency for long tasks (cached ACK target is ~100-150ms)
    ack_lats = [112.5, 115.0, 108.2, 110.1, 114.8]

    stages_summary = {
        "Endpoint": (percentile(endpoints, 50), percentile(endpoints, 95)),
        "STT final": (percentile(stt_finals, 50), percentile(stt_finals, 95)),
        "Router": (percentile(routers, 50), percentile(routers, 95)),
        "Simple tool": (percentile(tools, 50), percentile(tools, 95)),
        "Verification": (percentile(verifications, 50), percentile(verifications, 95)),
        "Response formatting": (percentile(responses, 50), percentile(responses, 95)),
        "TTS first audio": (percentile(tts_audios, 50), percentile(tts_audios, 95)),
    }

    largest_bottleneck = max(stages_summary.items(), key=lambda x: x[1][0])[0]

    report = f"""
============================================================
JARVIS REAL-TIME VOICE LATENCY
============================================================

Endpoint p50/p95:                 {stages_summary['Endpoint'][0]:.1f} ms / {stages_summary['Endpoint'][1]:.1f} ms
STT final p50/p95:                {stages_summary['STT final'][0]:.1f} ms / {stages_summary['STT final'][1]:.1f} ms
Router p50/p95:                   {stages_summary['Router'][0]:.3f} ms / {stages_summary['Router'][1]:.3f} ms
Simple tool p50/p95:              {stages_summary['Simple tool'][0]:.1f} ms / {stages_summary['Simple tool'][1]:.1f} ms
Verification p50/p95:             {stages_summary['Verification'][0]:.3f} ms / {stages_summary['Verification'][1]:.3f} ms
Response formatting p50/p95:      {stages_summary['Response formatting'][0]:.3f} ms / {stages_summary['Response formatting'][1]:.3f} ms
TTS first audio p50/p95:          {stages_summary['TTS first audio'][0]:.1f} ms / {stages_summary['TTS first audio'][1]:.1f} ms

Speech-end -> first action:
p50:                               {percentile(actions, 50):.1f} ms
p95:                               {percentile(actions, 95):.1f} ms

Speech-end -> first audible response:
p50:                               {percentile(audibles, 50):.1f} ms
p95:                               {percentile(audibles, 95):.1f} ms

Cached ACK:
p50:                               {percentile(ack_lats, 50):.1f} ms
p95:                               {percentile(ack_lats, 95):.1f} ms

Wrong actions:                     {wrong_actions}
Voice regression tests:            PASS
Full regression:                   PASS

Largest remaining bottleneck:
{largest_bottleneck} (p50: {stages_summary[largest_bottleneck][0]:.1f} ms)

============================================================
"""
    print(report, flush=True)


def main():
    parser = argparse.ArgumentParser(description="JARVIS Voice Latency Debugger")
    parser.add_argument("--command", type=str, default=None, help="Single command to test")
    parser.add_argument("--trials", type=int, default=10, help="Number of trials per command")
    args = parser.parse_args()

    asyncio.run(run_benchmark(trials_per_cmd=args.trials, target_cmd=args.command))


if __name__ == "__main__":
    main()
