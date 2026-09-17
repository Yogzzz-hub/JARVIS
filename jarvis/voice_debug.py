"""Live voice debugging tool for JARVIS EDGE.

Displays real-time audio levels, wake score, VAD state, STT hypotheses,
queue depths, dropped frames, and latencies.
"""
from __future__ import annotations

import argparse
import asyncio
import math
import sys
import time
from pathlib import Path

import numpy as np

from jarvis.core.audio.frame import CANONICAL_SAMPLE_RATE, AudioFrame
from jarvis.core.audio.hub import AudioHub
from jarvis.core.audio.source import MicSource
from jarvis.core.audio.vad import SileroVADEngine, VADState
from jarvis.core.audio.wake import OpenWakeWordEngine


def compute_rms_peak(pcm_data: bytes) -> tuple[float, float, int]:
    """Calculate RMS (dBFS), peak (dBFS), and raw peak amplitude."""
    if not pcm_data:
        return -100.0, -100.0, 0
    samples = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32)
    if len(samples) == 0:
        return -100.0, -100.0, 0
    peak_val = int(np.max(np.abs(samples)))
    rms_val = float(np.sqrt(np.mean(samples**2)))
    peak_db = 20 * math.log10(max(peak_val, 1) / 32767.0)
    rms_db = 20 * math.log10(max(rms_val, 1.0) / 32767.0)
    return rms_db, peak_db, peak_val


def render_meter(db_val: float, width: int = 20) -> str:
    """ASCII volume meter from -60 dB to 0 dB."""
    clamped = max(-60.0, min(0.0, db_val))
    norm = (clamped + 60.0) / 60.0  # 0.0 to 1.0
    num_chars = int(norm * width)
    bar = "█" * num_chars + "░" * (width - num_chars)
    return f"[{bar}] {db_val:5.1f} dBFS"


async def run_voice_debug(
    duration: float = 10.0,
    record_debug: bool = False,
    output_wav: str = "debug_audio.wav",
) -> None:
    print("=" * 65)
    print("            JARVIS EDGE -- LIVE VOICE DEBUGGER")
    print("=" * 65)
    print("Initializing microphone and audio hub...")

    mic = MicSource(sample_rate=CANONICAL_SAMPLE_RATE)
    hub = AudioHub(source=mic)
    consumer_vad = hub.register("debug_vad", queue_size=100)
    consumer_wake = hub.register("debug_wake", queue_size=50)

    wake_engine = OpenWakeWordEngine()
    vad_engine = SileroVADEngine()

    try:
        await hub.start()
    except Exception as exc:
        print(f"Error starting audio capture: {exc}")
        print("Subsystem state: AUDIO_UNAVAILABLE")
        return

    recorded_frames: list[bytes] = []
    print(f"Capture active: 16 kHz mono PCM16 | Hub queue capacity: 100")
    print("Speak into microphone. Press Ctrl+C to exit.\n")
    print(f"{'Time':<8} {'RMS Level':<27} {'Peak':<6} {'Wake':<7} {'VAD':<15} {'Dropped':<7}")
    print("-" * 75)

    start_time = time.monotonic()
    last_print = start_time

    try:
        while True:
            now = time.monotonic()
            if duration > 0 and (now - start_time) >= duration:
                break

            # Read VAD queue
            try:
                frame = await asyncio.wait_for(consumer_vad.queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue

            if record_debug:
                recorded_frames.append(frame.pcm)

            rms_db, peak_db, peak_raw = compute_rms_peak(frame.pcm)
            vad_res = vad_engine.feed(frame)

            # Check wake queue
            wake_score = 0.0
            wake_detected = False
            if not consumer_wake.queue.empty():
                try:
                    w_frame = consumer_wake.queue.get_nowait()
                    w_det = wake_engine.feed(w_frame)
                    if w_det:
                        wake_score = w_det.score
                        wake_detected = w_det.detected
                except asyncio.QueueEmpty:
                    pass

            if now - last_print >= 0.1:
                meter = render_meter(rms_db, width=15)
                vad_label = vad_res.state.name
                if vad_res.is_speech:
                    vad_label += f" ({vad_res.probability:.2f})"
                wake_label = f"{wake_score:.2f}"
                if wake_detected:
                    wake_label += " [WAKE!]"

                elapsed = f"{now - start_time:5.1f}s"
                dropped = hub.dropped_frames
                sys.stdout.write(
                    f"\r{elapsed:<8} {meter:<27} {peak_raw:<6} {wake_label:<7} {vad_label:<15} {dropped:<7}"
                )
                sys.stdout.flush()
                last_print = now

    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        print("\nStopping audio capture...")
        await hub.stop()

        if record_debug and recorded_frames:
            import wave
            out_path = Path(output_wav)
            with wave.open(str(out_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(CANONICAL_SAMPLE_RATE)
                wf.writeframes(b"".join(recorded_frames))
            print(f"Debug audio recorded to: {out_path.resolve()} ({len(recorded_frames)} frames)")

    print(f"Debug session completed. Total dropped frames: {hub.dropped_frames}")


def main() -> None:
    parser = argparse.ArgumentParser(description="JARVIS Voice Debugger")
    parser.add_argument("--duration", type=float, default=5.0, help="Debug run duration in seconds (default: 5.0, 0 for infinite)")
    parser.add_argument("--record-debug", action="store_true", help="Explicitly record debug audio to WAV file")
    parser.add_argument("--output", default="debug_audio.wav", help="Debug WAV file path (default: debug_audio.wav)")
    args = parser.parse_args()

    asyncio.run(run_voice_debug(duration=args.duration, record_debug=args.record_debug, output_wav=args.output))


if __name__ == "__main__":
    main()
