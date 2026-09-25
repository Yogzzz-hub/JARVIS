import asyncio
import time
from jarvis.core.stt.faster_whisper_engine import FasterWhisperEngine
from jarvis.core.tts.piper_engine import PiperEngine
from jarvis.core.audio.source import MicSource

async def main():
    print("Loading Piper TTS to generate test audio...")
    tts = PiperEngine(model_path="models/piper/en/en_US/lessac/medium/en_US-lessac-medium.onnx")
    tts.load()

    print("Loading Faster-Whisper STT model...")
    stt = FasterWhisperEngine(model="models/whisper/base", device="cpu", compute_type="int8")
    t0 = time.perf_counter()
    await stt.load()
    load_time = time.perf_counter() - t0
    print(f"STT Loaded in {load_time:.2f}s | Model: {stt.model_name} | Device: {stt.device_name} | Compute: {stt.compute_type}")

    test_phrases = [
        "open notepad",
        "open microsoft edge",
        "what time is it",
        "open calculator",
    ]

    for phrase in test_phrases:
        pcm_22k = tts.synthesize(phrase)
        pcm_16k = MicSource._resample_pcm16(pcm_22k, 22050, 16000)

        await stt.start_session("session_" + phrase.replace(" ", "_"))
        await stt.feed_audio(pcm_16k, sample_rate=16000)

        t_start = time.perf_counter()
        final = await stt.finalize()
        latency_ms = (time.perf_counter() - t_start) * 1000.0

        print(f"Input: '{phrase}' -> Recognized: '{final.text}' | Latency: {latency_ms:.1f}ms | Device: {stt.device_name}")

if __name__ == "__main__":
    asyncio.run(main())
