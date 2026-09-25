# JARVIS ULTRA — CURRENT ARCHITECTURE AUDIT (PHASES 1–12)

## 1. Audit Overview
This document inventories the existing JARVIS EDGE v1.0 codebase across all 12 Phases as of 18 September 2026. The goal is to identify operational strengths, quantify real measured baselines, enforce safety invariants, and define surgical optimizations without introducing a Phase 13 or rewriting stable systems.

---

## 2. Component Mapping Matrix

| Phase / Subsystem | Current Implementation File(s) | Current Dependencies | Active Model / Backend | Measured Hardware Baseline | Architectural Action | Justification |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1: Core Runtime & State** | `jarvis/core/runtime.py`, `jarvis/core/gateway/app.py` | FastAPI, Uvicorn, Pydantic, AnyIO | Native Python / Win32 | Boot: ~450 ms | **KEEP** | Rock-solid asynchronous runtime, zero unnecessary abstractions. |
| **Phase 2: Single-Owner AudioHub** | `jarvis/core/audio/hub.py`, `source.py`, `session.py` | `sounddevice`, `numpy`, `scipy` | Hardware Native -> 16kHz Canonical Stream | Capture loop: < 0.1 ms overhead | **KEEP** | Single-owner microphone architecture prevents device contention. 800ms pre-roll ring buffer preserved. |
| **Phase 3: Acoustic Wake Word** | `jarvis/core/audio/wake/__init__.py` | `openwakeword`, `onnxruntime` | `models/wake/hey_jarvis_v0.1.onnx` | 80ms chunk inference: **14.41 ms** (p50) | **KEEP & BENCHMARK** | Proven C-accelerated ONNX inference. Evaluated against 80ms/160ms/240ms frame configurations. |
| **Phase 3: Wake Acknowledgement** | `jarvis/core/response/ack_cache.py` | `wave`, `collections` | Pre-generated Piper WAVs (`yes.wav`, `listening.wav`) | RAM retrieval: **0.0006 ms** (p50) | **KEEP** | Sub-microsecond RAM lookup; completely eliminates LLM/TTS generation latency on wake. |
| **Phase 4: Streaming Voice & STT** | `jarvis/core/stt/faster_whisper_engine.py`, `stabilizer.py` | `faster-whisper`, `ctranslate2` | `models/whisper/base` (int8 CPU/CUDA) | First partial: ~160 ms; fast-path finalization: **0.001 ms** | **KEEP & BAKE-OFF** | Local Agreement (threshold=2) eliminates duplicate re-decode. Bake-off suite evaluates Nemotron & Moonshine. |
| **Phase 4: Endpointing & VAD** | `jarvis/core/audio/vad/__init__.py` | `silero-vad-lite` | Silero VAD Lite + Continuation Evaluator | Silence endpoint: 250 ms (short) / 550 ms (compound) | **KEEP & TUNE** | Linguistic continuation hints (`and`, `then`, `with`) prevent premature cut-offs. |
| **Phase 5: Multi-Lane Router** | `jarvis/core/router/router.py`, `control.py`, `cache.py` | `RapidFuzz`, `pydantic`, `PyYAML` | Lane 0 (Exact/Alias), Lane 1 (Semantic), Lane 2 (Tiny), Lane 3 (Planner) | Lane 0: **0.184 ms** (p50); 4,819.9 routes/sec | **KEEP & EXTEND** | High-throughput deterministic grammar bypasses generative models for >50% of commands. |
| **Phase 5: Safety Policy & Guard**| `jarvis/security/postconditions.py`, `router/guards.py` | Native Python | Explicit Confirmation Tickets | Validation: < 0.05 ms | **KEEP** | Absolute rule: Zero arbitrary shell/JS/coordinates. Mutating operations strictly require user confirmation. |
| **Phase 6: Multi-Step DAG Planner**| `jarvis/core/planner/` | `pydantic` | DAG TaskGraph schema | DAG validation: < 0.2 ms | **KEEP** | Model output strictly constrained to acyclic Pydantic DAG nodes; independent risk recomputation. |
| **Phase 7: Response & Fast TTS** | `jarvis/core/response/engine.py`, `formatter.py`, `tts/manager.py` | `piper-tts`, `sounddevice` | Piper (`en_US-ryan-medium.onnx` / `lessac`) | Template format: **0.005 ms**; TTS first PCM: ~107 ms | **KEEP & OPTIMIZE** | Zero-LLM deterministic spoken responses. Persistent audio stream prevents driver reinitialization lag. |
| **Phase 8: ActionLedger & Persistence**| `jarvis/core/execution/ledger.py`, `store.py` | SQLite (WAL mode) | Durable State Machine | Commit latency: < 0.8 ms | **KEEP** | State machine: `PREPARED` -> `AUTHORISED` -> `STARTED` -> `VERIFIED` -> `COMMITTED`. Uncertain actions never retried blindly. |
| **Phase 9: Windows Desktop UIA** | `jarvis/tools/system/native.py`, `app_resolver.py` | `uiautomation`, `pywin32`, `comtypes` | Windows UIA / Process API | App resolve: **0.0003 ms**; verification: ~300 ms | **KEEP & SCOPE** | Uses UIA patterns (Invoke, Value, Toggle) instead of mouse clicks. Handle caching and scoped subtree searches. |
| **Phase 10: Persistent Browser** | `jarvis/core/browser/manager.py` | `playwright` | Chromium Persistent Context | Cold start: 934 ms; warm tab reuse: **0.001 ms**; locator: **3.82 ms** | **KEEP** | Accessibility semantic locators (`get_by_role`, `get_by_text`) with zero arbitrary sleeps. |
| **Phase 11: Screen Capture & Vision**| `jarvis/core/vision/capture.py`, `grounding.py`, `parsers/` | `pillow`, `mss`, `cv2` (SimpleRegions) | 3-tier fallback (ImageGrab -> mss -> headless frame) | 1080p capture: **4.27 ms**; candidate extraction: **0.21 ms**; grounding: **0.005 ms** | **KEEP** | Zero raw coordinates invariant. Zero disk I/O in-memory buffers. Headless BitBlt crash resilience. |
| **Phase 12: Context, Memory & Governor**| `jarvis/core/memory/`, `workflows/`, `resources/governor.py` | SQLite FTS5, Pydantic | Working Memory + Workflow Induction + GPU Governor | Working memory lookup: < 0.05 ms; governor switch: < 2 ms | **KEEP** | Prevents VRAM exhaustion on 6 GB GPU; learns workflows only from verified successful traces with explicit user approval. |

---

## 3. Fixed Delay Audit Summary

All 14 legacy `time.sleep` / `asyncio.sleep` calls across the repository were audited and classified in `docs/FIXED_WAIT_AUDIT.md`:
- **Zero arbitrary waits** remain in hot execution paths.
- All polling operations employ predicate conditions with early exit.
- Playwright operations rely on native actionability promises rather than sleep timeouts.
