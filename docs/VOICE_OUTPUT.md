# JARVIS EDGE — Instant Voice Response Engine, Streaming Local TTS & Barge-In (Phase 7)

## 1. Overview & Mission

Phase 7 introduces the voice output counterpart to Phase 6: an instant, truthful, natural speech response engine designed around three ironclad laws:

1. **ACKNOWLEDGEMENT NEVER REQUIRES AN LLM**:
   Acknowledgements are pre-synthesized audio clips served from RAM in under 1 ms. Jarvis feels instantly responsive without waiting 500–1500 ms for an LLM to formulate filler words.
2. **SILENT EXECUTION**:
   Jarvis remains completely silent while executing actions. No intermediate step-by-step chatter ("Searching...", "Copying...", "Opening..."). At most, a single truthful progress cue ("Still working on it.") is spoken if and only if a complex task exceeds 15 seconds.
3. **TRUTHFULNESS & VERIFIED DECISIONS**:
   Jarvis speaks only verified facts from `ToolResult`, `VerificationResult`, `GraphResult`, and Phase 5 `PolicyDecision`. It never hallucinates success; `UNCERTAIN` results are clearly stated as unverified, `PARTIAL` results explain what succeeded and what failed, and `DENIED` or `CANCELLED` actions are truthfully reported.

---

## 2. High-Level Architecture

```
                    ┌─────────────────────────┐
                    │ Voice Event / Command   │
                    │   (STT / Router)        │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │     ResponseEngine      │
                    │  (Scheduling & Policy)  │
                    └───┬─────────────────┬───┘
                        │                 │
              Instant / │                 │ Verified Result
              Complex   │                 │
                        ▼                 ▼
             ┌────────────────┐  ┌──────────────────┐
             │    AckCache    │  │ResponseFormatter │
             │  (Pre-gen WAV) │  │ (Deterministic)  │
             └────────┬───────┘  └────────┬─────────┘
                      │                   │
                      │                   ▼
                      │          ┌──────────────────┐
                      │          │    TTSManager    │
                      │          │ ┌──────────────┐ │
                      │          │ │ Piper (Local)│ │
                      │          │ └──────┬───────┘ │
                      │          │        ▼         │
                      │          │ ┌──────────────┐ │
                      │          │ │SAPI Fallback │ │
                      │          │ └──────────────┘ │
                      │          └────────┬─────────┘
                      │                   │ Streaming PCM16
                      ▼                   ▼
             ┌──────────────────────────────────────┐
             │          AudioOutputQueue            │
             │   (Priority Heap, Stale/Dup Drop)    │
             └──────────────────┬───────────────────┘
                                │
                                ▼
             ┌──────────────────────────────────────┐
             │         AudioOutputManager           │
             │ (Single Owner Playback, sounddevice) │
             └──────────────────┬───────────────────┘
                                │
                                ▼
                     [ Speaker / Headphones ]
                                ▲
                                │ Interrupt / Mute Gate
             ┌──────────────────┴───────────────────┐
             │          BargeInController           │
             │ (VAD Speech Detect, Echo Protection) │
             └──────────────────┬───────────────────┘
                                │
                     [ Microphone Stream ]
```

---

## 3. Response Contract & Lifecycle

### Response Types & Priorities
The response engine enforces strict priority ordering to avoid queue starvation and audio collisions:
- **EMERGENCY / CANCEL** (Priority 1): Immediate playback interruption, cancellation notices.
- **CONFIRMATION** (Priority 2): Policy confirmation prompts requiring immediate user authorization.
- **FINAL** (Priority 3): Verified outcome of an executed task or query.
- **PROGRESS** (Priority 4): At most one cue for tasks exceeding 15 seconds.
- **ACK** (Priority 5): Initial acceptance acknowledgement.

### Lifecycle State Machine
Each request tracks a distinct lifecycle:
`NONE` $\rightarrow$ `ACK_SENT` $\rightarrow$ `FINAL_QUEUED` $\rightarrow$ `FINAL_STARTED` $\rightarrow$ `FINAL_COMPLETED`.
This state machine prevents duplicate final speech and drops obsolete ACKs automatically if the final result arrives while an ACK is queued.

---

## 4. Instant Acknowledgement Engine (`AckCache`)

### Pre-Generated Audio Clips
Acknowledgements are pre-synthesized using the selected Piper voice (`en_US-lessac-medium`) and stored locally in `assets/audio/acks/`:
- `understood.wav` — "Understood."
- `got_it.wav` — "Got it."
- `on_it.wav` — "I'm on it."
- `okay.wav` — "Okay."
- `starting.wav` — "Starting now."
- `handle_that.wav` — "I'll handle that."
- `confirm.wav` — "Please confirm."
- `cancelled.wav` — "Cancelled."
- `stopped.wav` — "Stopped."
- `didnt_catch.wav` — "I didn't catch that."

### In-Memory Cache & Anti-Repetition
- **Zero Disk Latency**: All clips are loaded into RAM upon first use; lookup time is $< 0.001$ ms.
- **Weighted Anti-Repetition**: The last 2 used phrases are strictly excluded from subsequent selections to prevent monotonous repetition ("Got it. Got it. Got it.").

### Instant Query Bypass & Merge Window
- **Instant Answer Bypass**: Commands with near-instant execution (e.g., `get_time`, `get_volume`, `get_status`) skip the ACK step completely. Jarvis answers directly ("It's 8:35 PM.") without an annoying "Got it." preamble.
- **ACK Merge Window (150–250 ms)**: For ultra-fast actions, the ACK is scheduled with a small delay. If verification succeeds before the ACK begins playing, the ACK is dropped and only the final outcome is spoken, eliminating speech stutter.

---

## 5. Local TTS Engine (`TTSEngine`)

### Primary: Piper Neural TTS
- **Engine**: Local ONNX-based neural TTS (`piper`).
- **Default Voice**: `en_US-lessac-medium` (high naturalness, low RTF).
- **Secondary Tested Voice**: `en_US-lessac-low` (ultra-lightweight).
- **Format**: 22,050 Hz Mono PCM16.
- **Warm Keeping**: The model remains resident in memory while voice mode is enabled, avoiding expensive per-request model loading.
- **Sentence Chunking**: For multi-sentence responses, Piper synthesizes sentence-by-sentence so first-audio playback begins while later sentences are being synthesized in the background.

### Fallback Chain
If Piper encounters an error or is unavailable:
1. **Windows SAPI Fallback**: Transparently hands off synthesis to local SAPI via `pyttsx3`.
2. **Text-Only Fallback**: If audio output hardware or both TTS engines fail, the text response remains completely available in UI and logs. **Task success is never marked as failed merely because voice playback failed.**

---

## 6. Deterministic Response Formatter (`ResponseFormatter`)

Spoken responses use deterministic templates derived exclusively from verified structured data—**zero LLM hallucination**:
- **Filenames**: Ugly system names (`UNIT_4_DL_FINAL_2.pdf`) are converted into natural spoken language ("Unit 4 DL Final 2 PDF").
- **File Extensions**: `.pdf` $\rightarrow$ "PDF", `.xlsx` $\rightarrow$ "Excel file", `.pptx` $\rightarrow$ "PowerPoint".
- **File Paths**: Long filesystem paths (`C:\Users\ashok\Downloads`) are simplified to natural terms ("your Downloads folder", "Desktop").
- **Numbers & Times**: `30%` $\rightarrow$ "30 percent", `20:35` $\rightarrow$ "8:35 PM".
- **List Clamping**: Spoken lists are capped at 3 items ("I found NLP Unit 4, NLP Unit 5, and NLP Lab Manual, plus 7 more.").
- **Truthful Outcomes**:
  - `SUCCESS`: "{app} is open.", "Volume set to {percent} percent."
  - `PARTIAL`: Truthfully narrates completed vs failed steps ("I completed 3 of 4 steps...").
  - `UNCERTAIN`: "I performed the action, but I couldn't verify whether it completed." (Never falsely says "Done.").
  - `FAILED`: Concise reason ("I couldn't open Power BI because it isn't installed.").

---

## 7. Audio Output Management & Priorities (`AudioOutputManager`)

- **Single Device Owner**: Exactly one background playback thread owns the `sounddevice.OutputStream`. ACK clips, Piper streams, and SAPI never fight for hardware access.
- **Bounded Priority Queue**: Maximum 10 items. Lower-priority items are evicted during queue congestion.
- **Stale Response Purging**: Responses tagged with stale or inactive `request_id`s are dropped automatically before reaching the audio device.
- **Instrumentation**: Captures timestamps at every stage: `response_requested_ns`, `tts_start_ns`, `first_pcm_ready_ns`, `playback_started_ns`.

---

## 8. Barge-In & Full-Duplex Interruption

Full-duplex operation permits the microphone to remain active while the speaker is outputting sound.
- **Interruption Latency**: When user speech is detected by VAD (`on_user_speech_started`), playback is cancelled immediately ($< 150$ ms p95, measured $< 0.1$ ms in synthetic tests).
- **Control Word Distinction**:
  - `"stop talking"` / `"be quiet"`: Halts current TTS output only; active background task continues unaffected.
  - `"stop"` / `"cancel"`: Halts speech AND requests Phase 5 cancellation of the active task.

---

## 9. Echo Suppression & Self-Trigger Prevention

Local speaker audio entering the open microphone is mitigated via multi-layer protection:
1. **Output-State Gating**: While Jarvis audio is actively playing, wake-word detection is temporarily gated/suppressed.
2. **Echo Signature Matching**: Jarvis compares incoming STT partial transcripts against its own active playback text buffer. If similarity $> 80\%$, the audio is classified as self-echo and discarded.

---

## 10. Spoken Confirmation & Follow-Up Window

- **Deterministic Confirmation Grammar**:
  - Affirmative: `yes`, `yeah`, `yep`, `confirm`, `go ahead`, `do it`.
  - Negative: `no`, `nope`, `cancel`, `stop`, `don't`.
- **Security Invariance**: Spoken confirmations **cannot bypass Phase 5 policy**. A "yes" is valid only if an active unexpired confirmation ticket exists with a matching action fingerprint.
- **Follow-Up Window (5–10s)**: After Jarvis asks a clarification or confirmation question, an active listening window is opened, allowing the user to reply without repeating the wake word ("Hey Jarvis").

---

## 11. Measured Benchmarks & Performance

All benchmarks run on local hardware (Intel i7 / RTX 4060 Laptop):

| Metric | Phase 7 Target | Measured Result | Status |
|---|---|---|---|
| **Cached ACK RAM Lookup** | $< 1.0$ ms p95 | **0.001 ms** | PASS (Exceeds) |
| **Barge-In Cancel Signal (`barge_in_cancel_signal_ms`)** | $< 5.0$ ms p95 | **0.003 ms** | PASS (Exceeds) |
| **Speech $\rightarrow$ Audio Stream Flush (`stream_flush_ms`)** | $< 50.0$ ms p95 | **23.5 ms** | PASS |
| **Speech $\rightarrow$ Output Callback Stop (`callback_stop_ms`)** | $< 150.0$ ms p95 | **29.0 ms** | PASS |
| **Piper Warm First Chunk** | $< 200.0$ ms p95 | **107.7 ms** | PASS |
| **Piper Synthesis RTF** | $< 0.50$ | **0.111** (9x real-time) | PASS |
| **Verified $\rightarrow$ Final Audio** | $< 300.0$ ms p95 | **141.1 ms** | PASS |
| **Speech-End to Action** | Baseline $\pm 10\%$ | **404.6 ms** (no regression) | PASS |
| **Piper Memory Footprint** | $< 150$ MB RAM | **+99.5 MB RAM** | PASS |
| **GPU / VRAM Impact** | 0 MB VRAM (CPU TTS) | **0 MB VRAM** | PASS |

---

## 12. Privacy & Security Safeguards

- **100% Local & Free**: Zero cloud TTS APIs (no ElevenLabs, Azure, Google Cloud, or OpenAI TTS).
- **Ephemeral Dynamic Speech**: Dynamic user text audio is never saved permanently to disk; it is held in RAM buffers and deleted immediately after playback. Only generic ACK clips are stored in `assets/audio/acks/`.
- **No Authorization Elevation**: The TTS and response layer merely format decisions; they possess zero authority to execute tools, grant tickets, or bypass security rules.

---

## 13. CLI Commands & Verification

### Response Engine Report
```powershell
python -m jarvis.report response
```
Displays total responses, ACK %, final-only %, cache latencies, TTS backend, first-audio latency, barge-in latencies, echo count, and memory footprint.

### Extended Voice Report
```powershell
python -m jarvis.report voice
```
Includes Phase 6 STT metrics alongside Phase 7 `speech_end_to_ack`, `verified_to_final`, and full interaction latency.

### Audio Devices Inspector
```powershell
python -m jarvis.audio_devices
```
Inspects all active Windows audio input (microphones) and output (speakers/headphones) devices with host APIs.

### Complete 10-Scenario Demo Suite
```powershell
python scripts/demo_phase7.py
```
Runs all 10 required Phase 7 demonstration scenarios end-to-end.
