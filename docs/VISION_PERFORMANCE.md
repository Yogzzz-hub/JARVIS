# JARVIS EDGE v1.0 — VISION FALLBACK & SCREEN CAPTURE PERFORMANCE

## 1. Vision Architecture Overview

Vision in JARVIS EDGE v1.0 serves strictly as a safe, candidate-first fallback when deterministic accessibility trees (UIA, DOM) are unavailable or uninformative.

```
[Screen Capture Request] (On-Demand only, never continuous background polling)
         │
         ▼
[Multi-Tier Robust Capture Fallback]
         ├── Tier 1: PIL ImageGrab (Fastest on interactive desktop, 4.27 ms)
         ├── Tier 2: mss direct memory grab (Fallback for multiple displays)
         └── Tier 3: Synthetic / Headless DC frame (Headless CI / disconnected session safety)
         │
         ▼
[Perceptual Hashing & Privacy Filter] (0.087 ms)
         ├── SHA-256 slice / dHash fingerprint
         ├── VisualCache Lookup (0.0024 ms hit)
         └── Privacy Gate: Redact untrusted / confidential credentials
         │
         ▼
[Candidate Extraction: SimpleRegionsParser] (0.21 ms)
         ├── Deterministic edge & contour detection
         ├── Normalized BoundingBox calculation [0.0, 1.0]
         └── Zero-Raw-Coordinates Enforcement
         │
         ▼
[Visual Grounding Engine: VisionGrounder] (0.005 ms)
         ├── Candidate matching via semantic label & spatial context
         └── Bounded Zoom-Crop Pass (Max 2 passes strictly enforced)
```

---

## 2. Key Vision Invariants & Optimizations

### A. Zero Disk I/O In-Memory Capture
Legacy screen automation writes screenshots to disk (`temp.png`), reads them back, and runs vision models. JARVIS captures directly into in-memory byte buffers:
- In-memory 1080p capture latency: **4.27 ms** (p50 on real hardware).
- Perceptual hashing latency: **0.087 ms**.
- Total memory footprint: ephemeral numpy buffer reused across frames.

### B. Multi-Tier Headless Resiliency
In Windows background sessions, services, or disconnected RDP sessions, `ImageGrab.grab()` raises `OSError: screen grab failed (BitBlt failed)`.
JARVIS implements automatic 3-tier fallback in `jarvis/core/vision/capture.py`:
1. `ImageGrab.grab(all_screens=True)`
2. `mss.mss().grab(...)`
3. Zero-crash synthetic headless 1080p canvas with warning logs.
This guarantees CI and background daemon runners never crash due to desktop context unavailability.

### C. Zero-Raw-Coordinates Safety Invariant
Under NO circumstances does JARVIS accept or generate raw $(x, y)$ coordinate clicks from an LLM.
All interactions require:
1. Candidate extraction generating a `VisualCandidate` with ID, normalized bounds, and label.
2. Grounder mapping intent to a specific `VisualCandidate.candidate_id`.
3. Input controller clicking the verified geometric center of that candidate only after confidence verification.

### D. Ephemeral VisualCache (15-Second TTL)
Visual candidate extraction and grounding decisions are cached in memory keyed by perceptual image hash:
- Cache hit retrieval latency: **0.0024 ms**.
- Automatic TTL invalidation after 15 seconds prevents operating on stale screen states.

---

## 3. Real Hardware Benchmark Summary (RTX 3050 / Intel Core i5)

Extracted directly from `scripts/bench_capture_latency.py` and `scripts/bench_vision_latency.py`:

| Operation | Measured p50 Latency | Measured p95 Latency | Safety & Efficiency Invariant |
| :--- | :--- | :--- | :--- |
| **1080p In-Memory Capture** | **4.27 ms** | **17.81 ms** | Zero disk write |
| **Perceptual Hash Computation**| **0.087 ms** | **0.155 ms** | In-memory SHA-256 slice |
| **Candidate Detection (16 objs)**| **0.21 ms** | **0.69 ms** | Deterministic SimpleRegions |
| **Candidate Grounding Decision**| **0.005 ms** | **0.016 ms** | Zero raw coordinates |
| **VisualCache Hit Retrieval** | **0.0024 ms** | **0.0050 ms** | 15s TTL invalidation |
