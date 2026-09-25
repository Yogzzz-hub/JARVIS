# JARVIS ULTRA — SINGLE-OWNER AUDIOHUB ARCHITECTURE

## 1. Single-Owner Audio Philosophy
On Windows, opening duplicate capture streams across multiple threads or subsystems causes driver device contention, audio buffer starvation, sample-rate mismatches, and severe UI stalls.
In JARVIS ULTRA, exactly **one** physical microphone owner exists: `AudioHub`.

```
[Windows Realtek Microphone Array] (Hardware Native: 48,000 Hz PCM)
                  │
                  ▼ (Non-blocking physical callback)
          [AudioHub Core]
                  │
                  ▼ (Streaming Single Resampler)
      [Canonical Stream: 16,000 Hz Mono Signed PCM16]
                  │
       ┌──────────┼──────────────────────┬──────────────────────┐
       ▼          ▼                      ▼                      ▼
 [Lock-Free Ring] [openWakeWord]    [Silero VAD]       [Faster-Whisper STT]
 (800ms Pre-Roll) (80ms frames)     (32ms frames)      (Sliding Window)
```

---

## 2. AudioHub Invariants

### A. Non-Blocking Hardware Callback
Under NO circumstances may any of the following occur inside the physical audio callback:
- Speech recognition inference
- Acoustic wake inference
- File or database writes
- Network calls or socket sends
- String formatting or logging
- Memory reallocations

The audio callback simply copies incoming byte chunks into a high-speed lock-free ring buffer and updates an atomic monotonic sequence counter.

### B. Single Canonical Resampling Pass
- Hardware native rate is automatically queried via Windows WASAPI (`sounddevice.query_devices`). On the current host, the rate is 48,000 Hz.
- Rather than running three independent resamplers for Wake, VAD, and STT, `AudioHub` executes a single, highly optimized streaming resampler (`scipy.signal.resample_poly` or linear polyphase) producing standard 16,000 Hz 16-bit mono PCM.
- All downstream consumers receive references to identical `AudioFrame` structures.

### C. Pre-Roll Ring Buffer (800ms Depth)
When a user says *"Hey Jarvis, open Chrome"*, acoustic wake detection requires ~100–300 ms of the wake phrase. Without a pre-roll buffer, the verb *"open"* would be lost.
`AudioHub` continuously maintains an 800ms circular ring buffer in RAM. When `wake_detected` fires, the preceding 800ms of audio is prepended to the speech session, guaranteeing 100% preservation of verb prefixes.

### D. Audio Backpressure & Queue Boundaries
- Bounded dropping queues prevent unbounded memory growth if downstream inference experiences transient thread stalls.
- Level meter events (`LatestValueQueue`) sample RMS energy for UI orb visualization without introducing locks into the speech pipeline.
