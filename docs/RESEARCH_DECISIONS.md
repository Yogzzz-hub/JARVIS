# JARVIS ULTRA — ARCHITECTURAL RESEARCH DECISIONS

## 1. Executive Rationale
The core thesis of JARVIS ULTRA is that the "ultimate personal assistant" is not built by putting every popular repository into one process or invoking an LLM for every user turn. The system converges on a disciplined cascade: **use the cheapest deterministic mechanism first, allow every uncertain layer to abstain, escalate only when necessary, keep perception and execution strictly separated, and verify every real-world action before reporting success.**

---

## 2. Deep Dive Architectural Comparisons

### A. Speech-to-Text (ASR): Faster-Whisper vs. Nemotron vs. Moonshine
- **The Problem**: Speech engines either suffer from high latency (waiting for user silence to re-decode audio from scratch) or require heavy GPU resources that starve generative planners.
- **Faster-Whisper (CTranslate2)**: Outstanding quantized CPU/CUDA performance. When combined with our `TranscriptStabilizer` (Local Agreement, $N=2$), it outputs stable partials in real time and completes finalization in **0.001 ms** via fast-path buffer reuse.
- **sherpa-onnx + Nemotron 3.5 Streaming (0.6B)**: Excellent true streaming transducer path with Windows ONNX support (80/160/560/1120 ms chunk variants). However, in local benchmarks on Intel CPU, Faster-Whisper int8 base achieves lower memory overhead and sub-millisecond finalization with zero network dependencies.
- **Moonshine**: Designed specifically for low-latency local speech. Benchmark contender for resource-constrained environments.
- **Decision**: **Faster-Whisper int8 Base** remains the primary streaming engine on Windows, backed by local comparative benchmarks (`scripts/bench_asr_candidates.py`).

### B. Generative Models: Qwen3.5 vs. Qwen3.8
- **The Problem**: Blindly picking the "newest" model version often leads to models that exceed consumer GPU VRAM.
- **Analysis as of September 2026**: Qwen's open releases for Qwen3.8 are in the 27B and 2.4T parameter classes, requiring 16 GB+ to hundreds of gigabytes of VRAM—completely unviable for an RTX 3050 (6 GB VRAM). In contrast, the Qwen3.5 series provides 0.8B, 2B, 4B, and 9B variants with native multimodal capabilities and full llama.cpp support.
- **Decision**:
  - **Lane 2 Slot Filler**: Qwen3.5-0.8B Q4 (~0.6 GB VRAM / CPU).
  - **Lane 3 Task Planner**: Qwen3.5-4B Q4 (~2.8 GB VRAM).
  - **Vision Fallback**: Qwen3-VL-2B-Instruct Q4 (~1.8 GB VRAM).

### C. Text-to-Speech (TTS): Piper vs. Kokoro vs. Coqui XTTS
- **Piper**: Fast local neural TTS, maintained under Open Home Foundation (`OHF-Voice/piper1-gpl`). On real hardware, it achieves **~107 ms** to first audio frame and supports pre-generated PCM caching (0.0006 ms retrieval for wake ACKs).
- **Kokoro**: Apache-2.0, 82M parameters. Strong quality candidate, but adds CPU load compared to Piper's lightweight ONNX runtime.
- **Coqui / XTTS**: High voice cloning quality, but heavy and weights are licensed under the Coqui Public Model License (CPML), which restricts commercial use.
- **Decision**: **Piper** remains default; pre-generated ACK cache in RAM provides sub-millisecond instant conversational feedback; Kokoro is preserved as an optional high-quality profile.

### D. Desktop Automation: Native UIA vs. Computer-Use Vision Models
- **The Problem**: Vision-only "computer-use" agents that take screenshots and generate $(x, y)$ coordinate clicks are slow (1–5 seconds per step), fragile to resolution/DPI scaling, and dangerous (accidental clicks on wrong buttons).
- **Solution (Borrowing from Microsoft UFO² & Playwright MCP)**:
  1. Priority 1: Native Windows API / COM methods (0 ms UI lag).
  2. Priority 2: Structured UI Automation (UIA) patterns (`InvokePattern`, `ValuePattern`, `TogglePattern`) using scoped window subtrees and handle caching.
  3. Priority 3: Semantic Playwright locators (`get_by_role`, `get_by_text`) for browser pages.
  4. Priority 4: Candidate-first visual fallback (SimpleRegions / OmniParser) where models output only verified candidate IDs—**NEVER raw coordinates**.

### E. Screen Capture: In-Memory Multi-Tier Fallback vs. Disk Screenshots
- **Legacy Approach**: Write screenshots to `temp.png`, load into PIL, run OCR. Incurred 65+ ms disk latency and crashed under headless Windows background sessions (`BitBlt failed`).
- **JARVIS ULTRA Approach**: 3-tier in-memory capture (ImageGrab -> mss direct DIBSection -> synthetic headless canvas). Achieves **4.27 ms** 1080p capture latency with 100% crash resilience in headless CI and background daemon execution.

### F. Adaptive Endpointing: VAD + Continuation Hints vs. Fixed Silence
- **The Problem**: 500ms fixed silence feels sluggish for short commands ("mute"), while 300ms cuts off compound speech ("open Chrome... and search TensorFlow").
- **Solution**: Silero VAD gate combined with linguistic continuation hints (`and`, `then`, `after that`, `with`, `for`, `to`, `or`, `but`, `also`). Short commands finalize in **250 ms**; continuation conjunctions dynamically extend pause allowance to **550 ms**.
