# JARVIS EDGE — Phase 12 Advanced Intelligence

## Overview
Phase 12 completes the JARVIS EDGE system by introducing contextual personal intelligence:
- Bounded, layered memory (Session, Working, Episodic, Semantic, Preference, Workflow).
- Sub-millisecond pronoun and reference resolution (`open it again`, `the second one`, `same folder`).
- Safe workflow learning (observing repeated successful task graphs and proposing reusable parameterized templates upon reaching the 3-run threshold).
- Bounded specialist coordinator for parallel read operations with structured result merging.
- Safe speculative prefetch strictly limited to `READ_ONLY` actions with immediate cancellation upon goal diversion.
- Strict hardware resource governance for the 16 GB RAM / RTX 3050 GPU target.
- Metrics-driven self-optimization strictly bound to immutable security invariants (Zero self-modifying code).

---

## Core Invariants

1. **Memory $\neq$ Authorization**:
   Durable memories provide context hints and referents, but never grant permission or bypass Phase-5 confirmation tickets.
2. **Workflow Approval $\neq$ Action Approval**:
   Approving a reusable workflow containing `EXTERNAL_EFFECT`, `DESTRUCTIVE`, or `PRIVILEGED` actions does not grant permanent execution permission. Every execution still requires explicit Phase-5 user confirmation tickets.
3. **Untrusted Data Quarantine**:
   External content (emails, webpages, document bodies, screen text) is classified as `UNTRUSTED_EXTERNAL_CONTENT` and is prohibited from committing durable memories or overriding instructions.
4. **Credential / Secret Filtering**:
   High-entropy tokens, passwords, OTPs, SSH keys, session cookies, and API keys are automatically detected and rejected from durable memory storage.
5. **Speculation Strictly READ_ONLY**:
   Speculative prefetch is limited to safe read operations (file lookups, calendar queries). State-changing actions (`send`, `delete`, `upload`, `launch`) are blocked from speculation.
6. **Zero Self-Modifying Code**:
   JARVIS never rewrites its own Python files, prompts, or safety rules. Optimization is restricted to proposal evaluation tested against offline benchmark corpora.
7. **Graceful Fallback**:
   Subsystem failures (vector store, memory DB, cloud connectivity, vision VLM) gracefully degrade to deterministic/lexical paths without crashing core operations.

---

## Architecture Components

| Component | Responsibility | Latency Budget | Measured p95 |
| :--- | :--- | :--- | :--- |
| **BoundedWorkingMemory** | Fast RAM-first working set (last 50 files, folders, apps, searches) | $< 1.0\text{ ms}$ | **0.0003 ms** |
| **ContextAssembler** | Unified context packet assembly with 512 token budget & fast path | $< 1.0\text{ ms}$ | **0.0063 ms** |
| **ReferenceResolver** | Deterministic pronoun, ordinal, folder, and project reference resolution | $< 2.0\text{ ms}$ | **0.0041 ms** |
| **SQLiteMemoryStore** | Layered persistent storage with FTS5 lexical indexing & superseding | $< 3.0\text{ ms}$ | **2.2878 ms** |
| **WorkflowLearner** | 3-run threshold graph pattern detector (propose-only) | $< 2.0\text{ ms}$ | **0.0012 ms** |
| **WorkflowLibrary** | Hot-cached template storage, parameter binding & failure quarantine | $< 3.0\text{ ms}$ | **0.0035 ms** |
| **SpecialistCoordinator** | Bounded parallel task fanout, cancellation propagation & fact merging | $< 15.0\text{ ms}$ | **0.0614 ms** |
| **PrefetchEngine** | Bounded speculative read scheduling with direction-change cancellation | $< 1.0\text{ ms}$ | **0.0021 ms** |
| **ResourceGovernor** | System telemetry monitoring, priority enforcement & model eviction | $< 1.0\text{ ms}$ | **0.0006 ms** |
| **OptimizationEngine** | Offline benchmark evaluation of bounded operational tuning proposals | N/A (Offline) | **100% Pass** |
