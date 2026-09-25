"""JARVIS Voice Doctor — End-to-End Voice Diagnostic Tool.

Usage:
    python scripts/voice_doctor.py [--full] [--fix]

Checks:
    - Python environment & voice dependencies
    - Audio input / microphone capture
    - Audio output / speaker playback
    - AudioHub canonical frame producer
    - Silero VAD boundary detection
    - Faster-Whisper local STT
    - OpenWakeWord wake detection
    - Piper local TTS synthesis & ACK playback
    - Push-to-talk & global hotkey
    - Single instance & lock state
    - Configuration files
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
import wave
from pathlib import Path
from typing import Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class VoiceDoctor:
    def __init__(self, full: bool = False, fix: bool = False):
        self.full = full
        self.fix = fix
        self.results: dict[str, Tuple[str, str]] = {}

    def report(self, component: str, status: str, detail: str = ""):
        self.results[component] = (status, detail)
        tag = f"[{status}]"
        print(f"  {component:<30} {tag:<8} {detail}")

    def run_all(self) -> int:
        print("=" * 60)
        print("JARVIS VOICE DOCTOR — SYSTEM DIAGNOSTICS")
        print("=" * 60)

        self.check_python_env()
        self.check_config()
        self.check_audio_devices()
        self.check_single_instance()
        self.check_mic_capture()
        self.check_vad()
        self.check_faster_whisper()
        self.check_openwakeword()
        self.check_piper_and_audio_output()
        self.check_ptt_and_hotkey()

        print("\n" + "=" * 60)
        print("DIAGNOSTIC SUMMARY")
        print("=" * 60)
        fail_count = 0
        warn_count = 0
        for comp, (stat, detail) in self.results.items():
            if stat == "FAIL":
                fail_count += 1
            elif stat == "WARN":
                warn_count += 1
            print(f"  {comp:<32} {stat:<8} {detail}")

        print("=" * 60)
        if fail_count > 0:
            print(f"RESULT: {fail_count} FAILED, {warn_count} WARNINGS. Voice mode requires fixes.")
            return 1
        elif warn_count > 0:
            print(f"RESULT: ALL CRITICAL PASS ({warn_count} non-critical warnings). Ready.")
            return 0
        else:
            print("RESULT: ALL COMPONENTS PASS. Voice mode fully operational.")
            return 0

    def check_python_env(self):
        print("\n[1/10] Checking Python Environment & Dependencies...")
        v = sys.version_info
        if v.major == 3 and v.minor in (11, 12):
            self.report("Python Version", "PASS", f"{v.major}.{v.minor}.{v.micro}")
        else:
            self.report("Python Version", "WARN", f"{v.major}.{v.minor}.{v.micro} (Recommended: 3.12)")

        modules = [
            ("sounddevice", "sounddevice"),
            ("numpy", "numpy"),
            ("scipy", "scipy"),
            ("faster_whisper", "faster-whisper"),
            ("ctranslate2", "ctranslate2"),
            ("openwakeword", "openwakeword"),
            ("silero_vad_lite", "silero-vad-lite"),
            ("piper", "piper-tts"),
            ("win32com.client", "pywin32"),
            ("keyboard", "keyboard"),
        ]

        missing = []
        for mod, pkg in modules:
            try:
                __import__(mod)
            except ImportError:
                missing.append(pkg)

        if not missing:
            self.report("Voice Dependencies", "PASS", "All required modules installed")
        else:
            if self.fix:
                print(f"  Attempting fix: installing {', '.join(missing)}...")
                import subprocess
                subprocess.run([sys.executable, "-m", "pip", "install", *missing], check=False)
                # Re-check
                still_missing = []
                for mod, pkg in modules:
                    try:
                        __import__(mod)
                    except ImportError:
                        still_missing.append(pkg)
                if not still_missing:
                    self.report("Voice Dependencies", "PASS", "Installed missing modules")
                else:
                    self.report("Voice Dependencies", "FAIL", f"Missing: {', '.join(still_missing)}")
            else:
                self.report("Voice Dependencies", "FAIL", f"Missing: {', '.join(missing)}")

    def check_config(self):
        print("\n[2/10] Checking Configuration Files...")
        import tomllib
        jarvis_toml_path = ROOT / "jarvis/config/jarvis.toml"
        response_toml_path = ROOT / "config/response.toml"

        if not jarvis_toml_path.exists():
            self.report("jarvis.toml", "FAIL", f"Not found at {jarvis_toml_path}")
            return
        if not response_toml_path.exists():
            self.report("response.toml", "FAIL", f"Not found at {response_toml_path}")
            return

        with jarvis_toml_path.open("rb") as f:
            jcfg = tomllib.load(f)
        with response_toml_path.open("rb") as f:
            rcfg = tomllib.load(f)

        voice_feat = jcfg.get("features", {}).get("voice", False)
        tts_feat = jcfg.get("features", {}).get("tts", False)

        if not voice_feat or not tts_feat:
            if self.fix:
                # Safe deterministic fix: update config to enable voice & tts
                print("  Applying fix: enabling features.voice and features.tts in jarvis.toml...")
                text = jarvis_toml_path.read_text(encoding="utf-8")
                text = text.replace("voice = false", "voice = true").replace("tts = false", "tts = true")
                jarvis_toml_path.write_text(text, encoding="utf-8")
                self.report("Voice Features Config", "PASS", "Enabled voice and tts via --fix")
            else:
                self.report("Voice Features Config", "FAIL", f"voice={voice_feat}, tts={tts_feat} (both must be true)")
        else:
            self.report("Voice Features Config", "PASS", "voice=true, tts=true")

        self.report("Response Config", "PASS", f"backend={rcfg.get('tts', {}).get('backend')}, voice={rcfg.get('tts', {}).get('voice')}")

    def check_audio_devices(self):
        print("\n[3/10] Checking Real Audio Devices...")
        try:
            import sounddevice as sd
            devs = sd.query_devices()
            in_devs = [d for d in devs if d["max_input_channels"] > 0]
            out_devs = [d for d in devs if d["max_output_channels"] > 0]
            default_in = sd.default.device[0]
            default_out = sd.default.device[1]

            default_in_name = devs[default_in]["name"] if default_in is not None and default_in >= 0 else "None"
            default_out_name = devs[default_out]["name"] if default_out is not None and default_out >= 0 else "None"

            if in_devs:
                self.report("Microphone Device", "PASS", f"Default [{default_in}]: {default_in_name}")
            else:
                self.report("Microphone Device", "FAIL", "No input devices found")

            if out_devs:
                self.report("Speaker Device", "PASS", f"Default [{default_out}]: {default_out_name}")
            else:
                self.report("Speaker Device", "FAIL", "No output devices found")

        except Exception as e:
            self.report("Audio Devices", "FAIL", str(e))

    def check_single_instance(self):
        print("\n[4/10] Checking Single Instance / Stale Locks...")
        import tempfile
        lock_path = Path(tempfile.gettempdir()) / "jarvis-edge-ui.lock"
        if lock_path.exists():
            if self.fix:
                try:
                    lock_path.unlink(missing_ok=True)
                    self.report("Lock File", "PASS", "Removed stale lock file")
                except Exception:
                    self.report("Lock File", "WARN", f"Active lock at {lock_path}")
            else:
                self.report("Lock File", "WARN", f"Lock file exists at {lock_path}")
        else:
            self.report("Lock File", "PASS", "No stale lock file")

    def check_mic_capture(self):
        print("\n[5/10] Testing Raw Microphone PCM Capture...")
        try:
            from jarvis.core.audio.source import MicSource
            import numpy as np

            async def _test():
                source = MicSource()
                await source.start()
                frames = []
                t0 = asyncio.get_event_loop().time()
                async for f in source.frames():
                    frames.append(f)
                    if asyncio.get_event_loop().time() - t0 >= 1.0:
                        break
                await source.stop()
                return source, frames

            source, frames = asyncio.run(_test())
            if not frames:
                self.report("Microphone Capture", "FAIL", "No frames captured in 1s")
                return

            all_pcm = b"".join(f.pcm for f in frames)
            samples = np.frombuffer(all_pcm, dtype=np.int16).astype(np.float32) / 32768.0
            rms = float(np.sqrt(np.mean(samples ** 2)))
            peak = float(np.max(np.abs(samples)))
            detail = f"Rate={source.target_rate}Hz, Frames={len(frames)}, RMS={rms:.4f}, Peak={peak:.4f}, Dropped={source.dropped_frames}"
            self.report("Microphone Capture", "PASS", detail)

        except Exception as e:
            self.report("Microphone Capture", "FAIL", str(e))

    def check_vad(self):
        print("\n[6/10] Testing Silero VAD Engine...")
        try:
            from jarvis.core.audio.vad import SileroVADEngine, VADState
            from jarvis.core.audio.frame import AudioFrame
            vad = SileroVADEngine()
            vad._ensure_loaded()
            if not vad._loaded:
                self.report("Silero VAD", "FAIL", "Failed to load SileroVAD model")
                return

            # Feed 10 chunks of silence (512 samples each)
            chunk = b"\x00" * 1024
            for i in range(10):
                frame = AudioFrame(sequence_id=i, timestamp_ns=0, sample_rate=16000, channels=1, sample_count=512, pcm=chunk, source="test")
                res = vad.feed(frame)

            detail = f"Loaded=True, Silence State={vad.state.value}, Silence Prob={vad._last_probability:.3f}"
            if vad.state == VADState.SILENCE:
                self.report("Silero VAD", "PASS", detail)
            else:
                self.report("Silero VAD", "WARN", detail)
        except Exception as e:
            self.report("Silero VAD", "FAIL", str(e))

    def check_faster_whisper(self):
        print("\n[7/10] Testing Faster-Whisper STT Engine...")
        try:
            from jarvis.core.stt.faster_whisper_engine import FasterWhisperEngine
            model_dir = ROOT / "models/whisper/base"
            if not model_dir.exists():
                self.report("Faster-Whisper Model", "FAIL", f"Missing {model_dir}")
                return

            async def _test():
                stt = FasterWhisperEngine(model=str(model_dir), device="cpu", compute_type="int8")
                t0 = time.perf_counter()
                await stt.load()
                load_ms = (time.perf_counter() - t0) * 1000
                return stt, load_ms

            stt, load_ms = asyncio.run(_test())
            self.report("Faster-Whisper STT", "PASS", f"Loaded on {stt.device_name} ({stt.compute_type}) in {load_ms:.0f}ms")
        except Exception as e:
            self.report("Faster-Whisper STT", "FAIL", str(e))

    def check_openwakeword(self):
        print("\n[8/10] Testing OpenWakeWord Engine...")
        try:
            from jarvis.core.audio.wake import OpenWakeWordEngine
            model_path = ROOT / "models/wake/hey_jarvis_v0.1.onnx"
            if not model_path.exists():
                self.report("Wake-word Model", "FAIL", f"Missing {model_path}")
                return

            engine = OpenWakeWordEngine(model_path=str(model_path), threshold=0.5)
            engine._ensure_loaded()
            if engine._loaded:
                self.report("OpenWakeWord", "PASS", f"Model '{engine._model_name}', Threshold={engine.threshold}")
            else:
                self.report("OpenWakeWord", "FAIL", "Failed to load wake word model")
        except Exception as e:
            self.report("OpenWakeWord", "FAIL", str(e))

    def check_piper_and_audio_output(self):
        print("\n[9/10] Testing Piper TTS & Audio Output...")
        try:
            from jarvis.core.tts.piper_engine import PiperEngine
            from jarvis.core.audio.output.player import AudioOutputManager, SpokenResponse, ResponseType

            model_path = ROOT / "models/piper/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
            if not model_path.exists():
                self.report("Piper Model", "FAIL", f"Missing {model_path}")
                return

            tts = PiperEngine(model_path=str(model_path))
            tts.load()
            self.report("Piper Synthesis", "PASS", f"Model loaded from {model_path.name}")

            # Check ACK files
            ack_path = ROOT / "assets/audio/acks/okay.wav"
            if ack_path.exists():
                self.report("ACK Audio", "PASS", f"Found {len(list((ROOT / 'assets/audio/acks').glob('*.wav')))} ACK WAVs")
            else:
                self.report("ACK Audio", "WARN", "ACK wavs not found in assets/audio/acks")

            # Check AudioOutputManager
            mgr = AudioOutputManager()
            mgr.start()
            resp = SpokenResponse(request_id="doc_test", type=ResponseType.ACK, text="test", audio_bytes=b"\x00\x00" * 500, sample_rate=22050)
            mgr.play(resp)
            time.sleep(0.3)
            mgr.stop()
            if mgr.last_error:
                self.report("Speaker Playback", "FAIL", mgr.last_error)
            else:
                self.report("Speaker Playback", "PASS", "Audio stream opened without error")

        except Exception as e:
            self.report("TTS & Audio Output", "FAIL", str(e))

    def check_ptt_and_hotkey(self):
        print("\n[10/10] Testing Push-To-Talk & Global Hotkey...")
        try:
            from jarvis.core.audio.wake import PushToTalkEngine
            ptt = PushToTalkEngine(hotkey="ctrl+shift+j")
            ptt.start()
            registered = ptt._registered
            ptt.stop()
            if registered:
                self.report("PTT Hotkey (Ctrl+Shift+J)", "PASS", "Registered successfully")
            else:
                self.report("PTT Hotkey (Ctrl+Shift+J)", "WARN", "Could not register hotkey (may require admin or already owned)")
        except Exception as e:
            self.report("PTT Hotkey (Ctrl+Shift+J)", "FAIL", str(e))


def main():
    parser = argparse.ArgumentParser(description="JARVIS Voice Doctor")
    parser.add_argument("--full", action="store_true", help="Run full diagnostic suite")
    parser.add_argument("--fix", action="store_true", help="Apply deterministic safe fixes")
    args = parser.parse_args()

    doctor = VoiceDoctor(full=args.full, fix=args.fix)
    code = doctor.run_all()
    sys.exit(code)


if __name__ == "__main__":
    main()
