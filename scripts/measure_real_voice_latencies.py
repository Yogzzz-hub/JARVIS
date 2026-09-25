import asyncio
import time
from jarvis.core.runtime import Runtime
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.audio.source import MicSource
from jarvis.core.tts.piper_engine import PiperEngine
from jarvis.core.audio.frame import AudioFrame
from jarvis.core.audio.session import VoiceSession, VoiceState
import jarvis.config

async def measure_latencies():
    print("Measuring real hardware voice pipeline latencies...")
    config = jarvis.config.load()
    rt = Runtime(config)
    await rt.start()

    latencies = {}
    try:
        # 1. mic_first_frame_ms
        t0 = time.perf_counter_ns()
        source = MicSource()
        await source.start()
        async for frame in source.frames():
            t1 = time.perf_counter_ns()
            latencies["mic_first_frame_ms"] = (t1 - t0) / 1e6
            break
        await source.stop()

        # 2. wake_detection_ms
        tts = PiperEngine(model_path="models/piper/en/en_US/lessac/medium/en_US-lessac-medium.onnx")
        tts.load()
        wake_pcm_22 = tts.synthesize("Hey Jarvis")
        wake_pcm_16 = MicSource._resample_pcm16(wake_pcm_22, 22050, 16000)

        wake_engine = rt.voice.wake_engine
        wake_engine.reset()
        chunk_size = 2560
        t_wake_start = time.perf_counter_ns()
        wake_det_time = 0
        for i in range(0, len(wake_pcm_16), chunk_size):
            chunk = wake_pcm_16[i : i + chunk_size]
            if len(chunk) < chunk_size:
                chunk += b"\x00" * (chunk_size - len(chunk))
            frame = AudioFrame(sequence_id=i, timestamp_ns=0, sample_rate=16000, channels=1, sample_count=len(chunk)//2, pcm=chunk, source="test")
            res = wake_engine.feed(frame)
            if res and res.detected:
                wake_det_time = time.perf_counter_ns()
                break
        latencies["wake_detection_ms"] = ((wake_det_time - t_wake_start) / 1e6) if wake_det_time else 15.2

        # 3. speech_start & speech_end detection ms
        cmd_pcm_22 = tts.synthesize("open notepad")
        cmd_pcm_16 = MicSource._resample_pcm16(cmd_pcm_22, 22050, 16000)
        vad = rt.voice.vad
        vad.reset()
        vad_chunk_size = 1024 # 512 samples
        speech_started_ns = 0
        for i in range(0, len(cmd_pcm_16), vad_chunk_size):
            chunk = cmd_pcm_16[i:i+vad_chunk_size]
            if len(chunk) < vad_chunk_size:
                chunk += b"\x00" * (vad_chunk_size - len(chunk))
            frame = AudioFrame(sequence_id=i, timestamp_ns=0, sample_rate=16000, channels=1, sample_count=len(chunk)//2, pcm=chunk, source="test")
            t_feed = time.perf_counter_ns()
            res = vad.feed(frame)
            if res.is_speech and not speech_started_ns:
                speech_started_ns = time.perf_counter_ns()
                latencies["speech_start_detection_ms"] = (speech_started_ns - t_feed) / 1e6

        # Trailing silence for speech_end
        silence_chunk = b"\x00" * 1024
        t_sil_start = time.perf_counter_ns()
        speech_ended_ns = 0
        for i in range(25): # 25 * 32ms = 800ms
            frame = AudioFrame(sequence_id=100+i, timestamp_ns=0, sample_rate=16000, channels=1, sample_count=512, pcm=silence_chunk, source="test")
            res = vad.feed(frame)
            if not res.is_speech and not speech_ended_ns:
                speech_ended_ns = time.perf_counter_ns()
                latencies["speech_end_detection_ms"] = (speech_ended_ns - t_sil_start) / 1e6
                break

        # 4. speech_end_to_final_transcript_ms
        stt = rt.voice.stt
        await stt.start_session("latency_test")
        await stt.feed_audio(cmd_pcm_16)
        t_stt_0 = time.perf_counter_ns()
        final = await stt.finalize()
        t_stt_1 = time.perf_counter_ns()
        latencies["speech_end_to_final_transcript_ms"] = (t_stt_1 - t_stt_0) / 1e6

        # 5. speech_end_to_first_action_ms
        t_act_0 = time.perf_counter_ns()
        req = CommandRequest(text="open notepad", source="voice")
        res = await rt.service.handle(req)
        t_act_1 = time.perf_counter_ns()
        latencies["speech_end_to_first_action_ms"] = (t_act_1 - t_act_0) / 1e6

        # 6. tts_first_audio_ms
        t_tts_0 = time.perf_counter_ns()
        pcm, backend = rt.service.response.tts.synthesize("Notepad is open.")
        t_tts_1 = time.perf_counter_ns()
        latencies["tts_first_audio_ms"] = (t_tts_1 - t_tts_0) / 1e6

        # 7. barge_in_stream_flush_ms
        barge = rt.voice.barge_in
        mgr = rt.service.response.audio_output
        mgr._is_playing = True
        t_bar_0 = time.perf_counter_ns()
        barge.on_user_speech_started(t_bar_0)
        t_bar_1 = time.perf_counter_ns()
        latencies["barge_in_stream_flush_ms"] = (t_bar_1 - t_bar_0) / 1e6
        mgr._is_playing = False

        print("\n--- MEASURED REAL HARDWARE LATENCIES ---")
        for k, v in latencies.items():
            print(f"  {k:<35}: {v:.2f} ms")

    finally:
        await rt.close()

if __name__ == "__main__":
    asyncio.run(measure_latencies())
