# JARVIS EDGE — Version 1.0 Final Architecture Specification

## 1. Unified Request Lifecycle

Every user request across voice, text, and mobile thin client traverses this verified deterministic pipeline:

```
                            USER INPUT
                  (Voice / Text CLI / Android Phone)
                                 │
                                 ▼
                         CONTEXT ASSEMBLER
     ┌───────────────────────────┼───────────────────────────┐
     │                           │                           │
Working Memory               Reference               Active Project &
(RAM 50 items)                Resolver                     Mode
     │                           │                           │
     └───────────────────────────┼───────────────────────────┘
                                 │
                                 ▼
                           SMART ROUTER
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
     Lane 0                   Lane 1                   Lane 2
  Deterministic            Small Model                Complex
  Regex / Fast             (Qwen 0.5B)               Multi-Step
        │                        │                        │
        └────────────────────────┼────────────────────────┘
                                 │
                                 ▼
                         WORKFLOW MATCHER
                                 │
                    ┌────────────┴────────────┐
                    │                         │
            Approved Template?             No Match
                    │                         │
                    ▼                         ▼
            Template Fast-Path         Adaptive Planner
            (Param Binding)            (DAG Generation)
                    │                         │
                    └────────────┬────────────┘
                                 ▼
                         TASK GRAPH (DAG)
                                 │
                                 ▼
                           POLICY ENGINE
           (ActionLedger, TOCTOU Check, Protected Paths,
             Confirmation Tickets for External Effects)
                                 │
                                 ▼
                      EXECUTION & SPECIALISTS
       ┌─────────────────────────┼─────────────────────────┐
       │                         │                         │
  Native Tools              Browser / UIA             Google APIs
(Files, Apps, OS)        (Playwright, Windows)    (Gmail, Drive, Cal)
       │                         │                         │
       └─────────────────────────┼─────────────────────────┘
                                 │ (Vision Fallback if needed)
                                 ▼
                        VERIFICATION ENGINE
                (Postcondition checks, Fingerprints)
                                 │
                                 ▼
                        MEMORY COMMIT GATE
          (Secret filter, Untrusted external data quarantine,
            Provenance tracking, Episode compaction)
                                 │
                                 ▼
                          RESPONSE ENGINE
              (Concise spoken audio / Text UI telemetry)
```

---

## 2. Model Lifecycle & Hardware Footprint

Target Hardware: Windows 11 PC, 16 GB RAM, RTX 3050 (4 GB VRAM).

| Role | Backend | Idle State | Load Trigger | Eviction Trigger |
| :--- | :--- | :--- | :--- | :--- |
| **STT Engine** | Silero VAD + Whisper | Resident RAM (~120 MB) | Hot | Never evicted (Interactive priority) |
| **Router (Lane 1)** | Small Qwen 0.5B Q4 | Cold / On-demand | Ambiguous single-step command | 60s idle timeout |
| **Planner (Lane 2)**| Qwen 4B Q4 | Cold (0 MB VRAM) | Multi-step DAG goal | 120s idle or RAM pressure |
| **Vision (Phase 11)**| OmniParser / VLM | Cold (0 MB VRAM) | `VISION_REQUIRED` trigger | Immediately after grounding |
| **Embeddings** | Lightweight CPU ONNX | Cold / Background | RAG search / Periodic indexing | Pauses during voice/interaction |

---

## 3. Trust & Security Boundaries

### Memory vs. Authorization
- Durable memories provide context hints (e.g. `preferred_browser = Edge`), but **never authorize actions**.
- Workflows save reusable task templates, but **never bypass Phase-5 policies**. State-changing actions (`send_email`, `delete_file`, `upload_file`) always pause for user confirmation tickets.

### Data Quarantine Boundary
- Content from email bodies, downloaded web pages, screen OCR, and files is labeled `UNTRUSTED_EXTERNAL_CONTENT`.
- Data cannot create durable user memories or alter system security configuration.

### Immutable Safety Policy
The `OptimizationEngine` and `AdaptiveRouter` can only tune bounded operational parameters (cache sizes, fuzzy thresholds). They are strictly prohibited from altering:
- Protected file paths (`System32`, `Program Files`).
- Destructive and external-effect confirmation rules.
- Authentication and credential scrapers.

---

## 4. Subsystem Degradation Matrix

| Failure Mode | Subsystem Affected | Graceful Degradation Behavior |
| :--- | :--- | :--- |
| `sqlite-vec` extension missing | Semantic Memory Search | Fallback to FTS5 lexical search & structured exact lookups. Core functions 100% operational. |
| Memory DB lock / error | Durable Memory | Working memory in RAM continues to resolve recent pronouns and active files. |
| Ollama / Local LLM down | Lane 1 & 2 Routing | Lane 0 regex and approved workflows continue to execute on fast path. |
| Vision VLM unavailable | Phase 11 Grounding | Falls back to Windows UIA accessible controls and keyboard navigation. |
| Internet disconnected | Connected Services | Local file tools, desktop automation, and voice continue locally. |
| Phone thin client disconnected | Remote Gateway | Local PC brain continues operating with zero data loss. |
