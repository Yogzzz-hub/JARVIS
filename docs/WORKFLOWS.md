# JARVIS EDGE — Workflow Learning & Reusable Templates

## 1. Workflow Lifecycle

```
Runtime Execution
       |
       v
WorkflowLearner (Counts equivalent verified task graphs)
       |
       v  (Reaches threshold >= 3)
WorkflowCandidate Proposed
       |
       v  (Explicit user consent: "Save as 'Prepare NLP Notes'?")
User Approval (CLI / Chat UI)
       |
       v
WorkflowLibrary (Persisted in SQLite & hot-cached in RAM)
       |
       v  (Utterance match on fast-path: p95 < 0.001 ms)
Parameter Binding & Fresh DAG Reconstruction
       |
       v
Phase-4 Validator -> Phase-5 Policy Ticket Gate -> Verified Execution
```

---

## 2. Invariants & Guarantees

1. **Propose-Only Invariant**:
   `WorkflowLearner` NEVER automatically creates or executes reusable workflows. It strictly generates candidate proposals requiring explicit user approval.
2. **Consequential Action Protection**:
   Approving a workflow containing `EXTERNAL_EFFECT` (email, messaging, upload) or `DESTRUCTIVE` (deletion, kill) does NOT bypass Phase-5 security. Every execution requires fresh confirmation tickets.
3. **No Pixel / Coordinate Macros**:
   Workflows store typed logical tool operations (e.g., `copy_file`, `search_files`, `browser_click`). Raw mouse $(x, y)$ coordinates and screen pixel positions are strictly prohibited.
4. **Parameter Slot Typing**:
   Changing runtime values are parameterized into typed slots (`Path`, `String`, `FolderRef`) rather than hardcoded paths.
5. **Automatic Quarantine**:
   If an approved workflow fails 3 consecutive times, it is automatically quarantined with status `QUARANTINED` to prevent repeated broken automations.
