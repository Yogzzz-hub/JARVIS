import numpy as np
from jarvis.core.audio.wake import OpenWakeWordEngine
from jarvis.core.audio.frame import AudioFrame
from jarvis.core.tts.piper_engine import PiperEngine
from jarvis.core.audio.source import MicSource

def test_wake():
    engine = OpenWakeWordEngine(model_path="models/wake/hey_jarvis_v0.1.onnx", threshold=0.5)
    engine._ensure_loaded()
    print(f"OWW Loaded: {engine._loaded} | Model: {engine._model_name} | Threshold: {engine.threshold}")

    tts = PiperEngine(model_path="models/piper/en/en_US/lessac/medium/en_US-lessac-medium.onnx")
    tts.load()

    def feed_audio(pcm_16k):
        # Feed in 1280-sample chunks (80ms at 16kHz = 2560 bytes)
        chunk_size = 2560
        max_score = 0.0
        detected = False
        engine.reset()
        for i in range(0, len(pcm_16k), chunk_size):
            chunk = pcm_16k[i : i + chunk_size]
            if len(chunk) < chunk_size:
                chunk = chunk + b"\x00" * (chunk_size - len(chunk))
            frame = AudioFrame(
                sequence_id=1,
                timestamp_ns=0,
                sample_rate=16000,
                channels=1,
                sample_count=len(chunk) // 2,
                pcm=chunk,
                source="test",
            )
            res = engine.feed(frame)
            if res:
                if res.score > max_score:
                    max_score = res.score
                if res.detected:
                    detected = True
        return detected, max_score

    # 1. Silence test (1.5 seconds silence)
    silence_pcm = b"\x00" * (16000 * 2 * 2)
    sil_det, sil_score = feed_audio(silence_pcm)
    print(f"Test Silence: Detected={sil_det}, Max Score={sil_score:.4f}")

    # 2. Normal conversation test
    norm_pcm_22 = tts.synthesize("How is the weather outside today? I want to go for a quick walk.")
    norm_pcm_16 = MicSource._resample_pcm16(norm_pcm_22, 22050, 16000)
    norm_det, norm_score = feed_audio(norm_pcm_16)
    print(f"Test Normal Speech ('weather...'): Detected={norm_det}, Max Score={norm_score:.4f}")

    # 3. Hey Jarvis test
    wake_pcm_22 = tts.synthesize("Hey Jarvis")
    wake_pcm_16 = MicSource._resample_pcm16(wake_pcm_22, 22050, 16000)
    wake_det, wake_score = feed_audio(wake_pcm_16)
    print(f"Test 'Hey Jarvis': Detected={wake_det}, Max Score={wake_score:.4f}")

    # 4. Hey Jarvis, open Chrome test
    wake_cmd_pcm_22 = tts.synthesize("Hey Jarvis, open Chrome")
    wake_cmd_pcm_16 = MicSource._resample_pcm16(wake_cmd_pcm_22, 22050, 16000)
    wake_cmd_det, wake_cmd_score = feed_audio(wake_cmd_pcm_16)
    print(f"Test 'Hey Jarvis, open Chrome': Detected={wake_cmd_det}, Max Score={wake_cmd_score:.4f}")

if __name__ == "__main__":
    test_wake()
