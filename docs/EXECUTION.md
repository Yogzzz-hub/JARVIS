# JARVIS EDGE — Execution Engine Specification

## Overview

The Phase 5 Execution Engine transitions JARVIS from generating and scheduling valid task graphs into **executing real actions safely**, exactly when authorized, verifying post-execution evidence, recovering from crashes, preventing duplicate non-idempotent side-effects, and never claiming success without verified evidence.

**Core Principle**: FAST DOES NOT MEAN UNSAFE. Every safety check executes in microseconds to low milliseconds, never skipping validation for performance.

---

## 1. Execution Pipeline

Every tool invocation follows this exact sequence:

```
Node → ToolDefinition → Policy → Ticket → Preconditions → Fingerprint
  → DuplicateGuard → MethodSelector → Ledger(PREPARED)
  → Execute → Ledger(STARTED) → Verify → Ledger(Final)
  → Audit → Receipt
```

### Step-by-Step

| Step | Component | Latency | Description |
|---:|---|---:|---|
| 0 | Kill Switch Check | < 0.001 ms | `ExecutionSupervisor.is_stopped()` — global emergency halt |
| 1 | Policy Evaluation | 0.003 ms p95 | `PolicyEvaluator.evaluate_node()` — risk classification, protected path guard, UAC detection |
| 2 | Action Fingerprint | 0.15 ms p95 | SHA-256 hash of `(tool, canonical_args, graph_id, node_id)` |
| 3 | Confirmation Ticket | 0.18 ms p95 | `ConfirmationManager.consume_ticket()` — cryptographic binding, expiration, tamper detection |
| 4 | Preconditions | 0.0002 ms p95 | `check_preconditions()` — deterministic zero-LLM pre-execution checks |
| 5 | Duplicate Guard | 0.43 ms p95 | `ActionLedger.check_duplicate()` — fingerprint lookup in memory + SQLite |
| 6 | Method Selection | 0.0002 ms p95 | `MethodSelector.select_variant()` — scored variant ranking with circuit breaker |
| 7 | Ledger PREPARED | 2.0 ms (durable) | Write-ahead record before any side effect |
| 8 | Tool Execution | Variable | Actual OS/filesystem/application operation |
| 9 | Ledger STARTED | 2.0 ms (durable) | Transition to STARTED before verification |
| 10 | Post-Verification | 0.12 ms p50 | `verify_postconditions()` — cheapest verifier cascade |
| 11 | Ledger Final | 0.4 ms (memory) | Record VERIFIED / FAILED / UNCERTAIN outcome |
| 12 | Audit Log | 0.1 ms | Append-only structured log with credential redaction |

---

## 2. Method Selection & Circuit Breaker

### MethodSelector

The `MethodSelector` ranks available execution variants for each tool using a scoring formula:

```
score = (success_rate × confidence × (10 / priority)) / (latency_cost × quarantine_penalty)
```

Where:
- `success_rate` = EWMA of verified successes / total attempts
- `confidence` = static variant confidence from `ToolVariant`
- `priority` = variant priority (lower = preferred)
- `latency_cost` = `log1p(max(ewma_latency_ms, 1.0))`
- `quarantine_penalty` = 10.0 if quarantined, 1.0 otherwise

### MethodStatsTracker

Tracks per-capability, per-method statistics:
- Total attempts, successes, verified successes, failures, uncertain outcomes
- EWMA latency with α = 0.1
- Consecutive failure counter → automatic quarantine after 5 consecutive failures

### CircuitBreaker

Each method has an independent circuit breaker:
- **CLOSED** → normal operation
- **OPEN** → 5+ consecutive failures → blocks execution for `recovery_timeout_s` (default: 30s)
- **HALF_OPEN** → after recovery timeout, allows one probe execution

### Quarantine

Methods quarantined after sustained failures:
- Default duration: 60 seconds
- Selector routes traffic to next-best variant
- Quarantine expires automatically

---

## 3. Verification Strategies

### Verifier Implementations

| Verifier | Checks | Use Cases |
|---|---|---|
| `FileExistsVerifier` | File exists at expected path | `create_file`, `copy_file`, `move_file` |
| `FileAbsentVerifier` | File no longer exists | `delete_file`, `remove_file` |
| `FileSizeVerifier` | File size within expected range | `download_file`, `create_file` |
| `FileHashVerifier` | SHA-256 hash matches expected | Critical file operations |
| `FolderContainsVerifier` | Folder contains expected entries | `create_folder`, `extract_archive` |
| `ProcessRunningVerifier` | Process with expected name is running | `open_app`, `start_service` |

### Verification Cascade

Postconditions execute cheapest verifier first:
1. Existence check (< 0.1 ms)
2. Size check (< 0.2 ms)
3. Hash check (< 5 ms for typical files)
4. Process check (< 10 ms)

### VerificationResult States

| Status | Meaning | Retry Safe? |
|---|---|---|
| `VERIFIED` | Post-check confirmed success with evidence | N/A |
| `FAILED` | Post-check proved failure | Depends on idempotency |
| `UNCERTAIN` | Side effect may have occurred but cannot confirm | **Never auto-retry** |

---

## 4. Retry Engine

The `RetryEngine` computes retry decisions based on:
- **Idempotency class**: `IDEMPOTENT` (safe to retry), `VERIFY_BEFORE_RETRY` (check first), `NON_IDEMPOTENT` (never auto-retry)
- **Failure classification**: timeout, permission, not found, network, UAC, auth
- **Retry budget**: Maximum attempts before escalation

### Retry Decision Matrix

| Idempotency | Failure Type | Decision |
|---|---|---|
| IDEMPOTENT | Transient/Timeout | RETRY_SAME_METHOD |
| IDEMPOTENT | Permanent | TRY_NEXT_METHOD |
| VERIFY_BEFORE_RETRY | Any | VERIFY_AGAIN first |
| NON_IDEMPOTENT | UNCERTAIN | DO_NOT_RETRY |
| NON_IDEMPOTENT | FAILED | ASK_USER |

---

## 5. Crash Recovery

### StartupReconciler

On startup, the `StartupReconciler` scans the action ledger for unresolved entries:

| Pre-Crash State | Recovery Action | Post-Recovery State |
|---|---|---|
| **PREPARED** | Never started → safe to cancel | CANCELLED |
| **STARTED** (local verifiable tool) | Attempt verification | VERIFIED or UNCERTAIN |
| **STARTED** (external/non-idempotent) | Cannot verify remotely | UNCERTAIN |
| **UNCERTAIN** | Already flagged | Remains UNCERTAIN |

**Critical invariant**: The reconciler **never blindly re-executes** a state-changing action. It only checks if the outcome can be verified locally.

---

## 6. Undo & Receipts

### ActionReceipt

Every successful execution that supports rollback generates an `ActionReceipt`:

```python
ActionReceipt(
    action_id="act_abc123",
    tool="create_folder",
    args={"path": "C:\\Users\\ashok\\Desktop\\demo_folder"},
    undo_tool="delete_folder",
    undo_args={"path": "C:\\Users\\ashok\\Desktop\\demo_folder"},
    created_at=1726598400.0,
    expires_at=1726684800.0,
)
```

### UndoManager

Maintains a bounded stack of recent receipts:
- Maximum depth: configurable (default: 100)
- Auto-expires after TTL (default: 24 hours)
- Only tools with `rollback_supported=True` generate receipts

---

## 7. File Manifest

| File | Purpose |
|---|---|
| `jarvis/core/executor/engine.py` | Full execution pipeline (12-step sequence) |
| `jarvis/core/executor/selector.py` | MethodSelector, MethodStatsTracker, CircuitBreaker, FailureClassifier, RetryEngine |
| `jarvis/security/verifiers/strategies.py` | FileExistsVerifier, FileAbsentVerifier, FileSizeVerifier, FileHashVerifier, FolderContainsVerifier, ProcessRunningVerifier |
| `jarvis/security/preconditions.py` | Deterministic pre-execution validation |
| `jarvis/security/postconditions.py` | Postcondition verification cascade |
| `jarvis/security/recovery.py` | StartupReconciler crash recovery |
| `jarvis/security/undo.py` | UndoManager and ActionReceipt |
| `jarvis/security/supervisor.py` | ExecutionSupervisor global kill switch |
| `jarvis/security/ledger/ledger.py` | ActionLedger (dual-path: memory + SQLite WAL) |
| `jarvis/security/ledger/models.py` | LedgerState, LedgerEntry |
| `scripts/bench_execution.py` | Phase 5 deterministic micro-benchmark |
| `scripts/demo_phase5.py` | 10 required demonstration scenarios |
