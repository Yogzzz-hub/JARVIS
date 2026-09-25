# JARVIS ULTRA — STREAMING SPEECH RECOGNITION & LOCAL AGREEMENT

## 1. Dual-Provider Streaming Architecture
Speech engines fundamentally differ in architecture. JARVIS ULTRA provides a unified `StreamingASR` protocol supporting both:
1. **Native Streaming Transducers** (e.g. sherpa-onnx Nemotron 3.5 streaming): Audio chunks stream into an ongoing internal encoder/decoder state, emitting evolving hypotheses.
2. **Whisper-Style Rolling Decoders** (e.g. Faster-Whisper int8 CTranslate2): Periodic sliding-window re-decoding with `TranscriptStabilizer` (Local Agreement) to extract stable prefixes.

```
[Canonical 16kHz PCM Stream]
             │
             ├──► [Faster-Whisper int8 Engine] (beam_size=1)
             │          │
             │          ▼
             │   [Rolling Sliding Window] (160ms - 250ms cadence)
             │          │
             │          ▼
             │   [TranscriptStabilizer: Local Agreement N=2]
             │          ├──► RAW_PARTIAL (Dispatched to UI only)
             │          └──► STABLE_PARTIAL (Safe read-only prewarm)
             │
             └──► [Endpoint Gate (VAD + Continuation)]
                        │
                        ▼ (Silence / Thought Complete)
                 [Authoritative FINAL Flush]
                        │ (Sub-millisecond commit, 0 re-decode)
                        ▼
                 [Router Dispatch]
```

---

## 2. The Three Transcript States

To maintain low latency without sacrificing safety, JARVIS ULTRA enforces three strict states:

| Transcript State | Consumer | Permitted Actions | Prohibited Actions |
| :--- | :--- | :--- | :--- |
| **RAW_PARTIAL** | UI Dashboard only | Live transcript rendering, animated waveform | Intent classification, routing, tool invocation, file mutation |
| **STABLE_PARTIAL** | Core Runtime / Router | Read-only app candidate resolution, indexed file metadata search, planner warm-up, browser context prewarm | Any mutating state change (delete, send, install, upload, click, shell) |
| **FINAL** | SmartRouter / ActionLedger | Authoritative route selection, confirmation ticket binding, tool execution dispatch | Speculative unverified execution |

---

## 3. Local Agreement Algorithm (Threshold $N=2$)

For Whisper-style decoders, successive sliding windows can oscillate on sentence tails.
The `TranscriptStabilizer`:
1. Compares word tokens across consecutive decode passes ($A$ and $B$).
2. Finds the Longest Common Prefix (LCP).
3. If words match across $N \ge 2$ consecutive intervals, they become **COMMITTED** and are marked stable.
4. Committed words are never rolled back, allowing safe read-only prewarming.

```
Pass 1: "open chrome and sea"
Pass 2: "open chrome and search"
Stable Prefix:   "open chrome and"  --> [STABLE_PARTIAL: Safe to prewarm browser]
Unstable Tail:   "search"           --> [RAW_PARTIAL: Display on UI only]
```

---

## 4. Personal Context Lexicon

A compact local lexicon (< 100 entries) is maintained from user environment metadata:
- Installed apps: `Visual Studio Code`, `Android Studio`, `Chrome`, `Notepad`
- Active projects: `RIT Gate Project`, `CLG Search`, `Deep Learning Slides`
- Technical vocabulary: `TensorFlow`, `PyTorch`, `FastAPI`, `Supabase`, `NLP`

This lexicon is used for conservative candidate repair and entity disambiguation, preventing transcription errors without polluting decoder vocabulary.
