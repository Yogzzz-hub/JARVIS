# JARVIS EDGE — Resource Governor & Speculative Prefetch

## 1. Hardware Budget (16 GB RAM / RTX 3050 GPU)

JARVIS EDGE is designed to run efficiently on resource-constrained personal hardware:
- **Idle Core RAM**: $< 350\text{ MB}$ (Measured: $\sim 245\text{ MB}$).
- **Idle VRAM**: $0.0\text{ MB}$ (Models loaded strictly on-demand).
- **Interactive Priority**: Real-time voice capture, STT, and deterministic commands always take precedence over background jobs.

---

## 2. Priority Hierarchy

The `ResourceGovernor` maintains strict execution priorities:

```
[Level 1] EMERGENCY_STOP / CANCEL
[Level 2] VOICE_CAPTURE (Real-time microphone stream)
[Level 3] STREAMING_STT (Silero VAD / Whisper)
[Level 4] DETERMINISTIC_COMMAND (Sub-millisecond tool execution)
[Level 5] ROUTER_LANE_0 / LANE_1 (Intent classification)
[Level 6] ACTIVE_PLANNER (Qwen 4B reasoning)
[Level 7] UI_INTERACTION / BROWSER (Playwright / UIA)
[Level 8] LOCAL_VISION (VLM fallback on-demand)
[Level 9] BACKGROUND_EMBEDDINGS & INDEXING
[Level 10] OPTIMIZATION & WORKFLOW LEARNING
```

When interactive tasks (Levels 1–7) begin, background maintenance jobs (Levels 9–10) are instantly paused to eliminate CPU/disk contention.

---

## 3. Dynamic Model Eviction Under Memory Pressure

- **Pressure Thresholds**: Evaluates system RAM (default 85%) and GPU VRAM (default 3,200 MB).
- **Eviction Order**: Idle Vision and Planner models are evicted first.
- **Immunity**: Active STT and audio pipelines are never evicted.
- **Latency Impact**: Governor evaluation decision takes $p95 = 0.0006\text{ ms}$ ($< 1.0\text{ ms}$ budget).

---

## 4. Safe Speculative Prefetch

The `PrefetchEngine` anticipates likely user requests during interaction:
- **Strict Read-Only Enforcement**: State-changing operations (`send`, `delete`, `move`, `upload`, `launch`) are blocked from speculation.
- **Bounded Concurrency**: Maximum 2 concurrent speculative read tasks.
- **Direction-Change Cancellation**: If user intent diverges from the speculative task, running prefetches are aborted immediately with zero side-effects.
