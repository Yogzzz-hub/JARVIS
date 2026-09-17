# JARVIS EDGE — Security & Policy Specification

## Overview

Phase 5 implements a comprehensive security, policy, and trust framework that ensures JARVIS never executes dangerous actions without explicit authorization, never claims success without verified evidence, and never replays non-idempotent operations after a crash.

**Design Principle**: All security checks are deterministic, execute in microseconds, and cannot be bypassed by the LLM planner.

---

## 1. Risk Classification

Every tool declares a static `RiskLevel` in its `ToolDefinition`:

| Risk Level | Description | Confirmation Required | Auto-Execute |
|---|---|:---:|:---:|
| `READ_ONLY` | No side effects (list files, get time, read config) | No | Yes |
| `REVERSIBLE` | Can be undone (create folder, copy file) | No | Yes |
| `EXTERNAL_EFFECT` | Remote side effect (send email, webhook) | **Yes** | No |
| `DESTRUCTIVE` | Permanent data loss (delete file, format disk) | **Yes** | No |
| `PRIVILEGED` | Requires elevated permissions (install software) | **Yes** | No |

---

## 2. Idempotency Classes

Each tool declares how safe it is to retry:

| Idempotency Class | Retry Safety | Example Tools |
|---|---|---|
| `IDEMPOTENT` | Safe to retry freely | `get_time`, `list_dir`, `read_file` |
| `VERIFY_BEFORE_RETRY` | Must verify outcome before retrying | `create_folder`, `copy_file` |
| `NON_IDEMPOTENT` | **Never auto-retry** | `send_email`, `delete_file`, `send_webhook` |

---

## 3. Policy Evaluator

The `PolicyEvaluator` is a pre-compiled, deterministic engine that evaluates every action before execution. It operates in < 0.003 ms p95.

### Policy Rules (from `config/policy.toml`)

```toml
[policy]
default_action = "ALLOW"
confirmation_timeout_s = 30.0

[policy.protected_roots]
paths = [
    "C:\\Windows",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
    "C:\\ProgramData",
    "C:\\Recovery",
    "C:\\System Volume Information",
]

[policy.user_isolation]
deny_other_users = true

[policy.execution]
allow_shell_true = false
allow_powershell_generation = false
allow_uac_automation = false
```

### Policy Decision Types

| Decision | Meaning | Action |
|---|---|---|
| `ALLOW` | Action is safe to execute immediately | Proceed |
| `ALLOW_WITH_CONFIRMATION` | Action requires user approval first | Issue `ConfirmationTicket` |
| `DENY` | Action violates security policy | Block with structured error |
| `PAUSE_FOR_USER` | Action needs human interaction (UAC, auth) | Yield to user |

### Policy Reason Codes

| Reason Code | Trigger |
|---|---|
| `DEFAULT_ALLOW` | READ_ONLY risk, no policy conflict |
| `REVERSIBLE_SAFE` | REVERSIBLE risk, rollback supported |
| `CONFIRMATION_REQUIRED` | DESTRUCTIVE or EXTERNAL_EFFECT risk |
| `PROTECTED_PATH` | Target path under protected root |
| `OTHER_USER_PROFILE` | Target falls inside another user's home directory |
| `JARVIS_INTERNAL` | Target modifies Jarvis's own code, DB, or security config |
| `UAC_REQUIRED` | Operation needs Windows UAC elevation |
| `SHELL_BLOCKED` | `shell=True` execution attempted |
| `POWERSHELL_BLOCKED` | Arbitrary PowerShell generation attempted |

---

## 4. Confirmation Tickets

### Ticket Lifecycle

```
Issue → PENDING → Approve/Deny → APPROVED/DENIED → Consume → CONSUMED
                                                  → Expire → EXPIRED
```

### Cryptographic Binding

Each ticket is cryptographically bound to its action via SHA-256 fingerprint:

```python
fingerprint = SHA-256({
    "tool": "delete_file",
    "args": {"path": "c:\\users\\ashok\\desktop\\report.txt"},
    "graph_id": "g1",
    "node_id": "n1",
})
```

### Tamper Detection

When a ticket is consumed, the engine recomputes the fingerprint from the actual execution arguments. If the fingerprint doesn't match (indicating argument tampering between approval and execution), the action is **immediately blocked** with zero invocations.

### Human-Readable Summaries

The `generate_human_summary()` function creates natural language descriptions:
- `delete_file` → "Permanently delete 'report.txt'"
- `create_folder` → "Create folder 'projects'"
- `send_email` → "Send email to 'user@example.com' with subject 'Report'"

For multi-step graphs, `generate_graph_summary()` combines all consequential actions:
- "Jarvis wants to permanently delete 'report.txt'; then send email to 'boss@company.com'. Do you want to continue?"

---

## 5. Path Security

### Canonicalization

All file paths undergo strict canonicalization before policy evaluation:

1. Expand environment variables (`%USERPROFILE%` → `C:\Users\ashok`)
2. Expand user home shorthand (`~` → `C:\Users\ashok`)
3. Resolve all relative segments (`..`, `.`)
4. Resolve symlinks and NTFS junctions
5. Normalize separators and case

### Traversal Defense

Paths like `C:\Users\ashok\Desktop\..\..\Windows\System32\cmd.exe` are canonicalized to `C:\Windows\System32\cmd.exe` and **denied** under the `PROTECTED_PATH` guard.

### TOCTOU Protection

The `toctou_snapshot()` captures file metadata (size, mtime, inode) before execution, and `toctou_verify()` checks that the file hasn't been modified between policy evaluation and execution.

---

## 6. Action Ledger

### Dual-Path Persistence

The `ActionLedger` uses a dual-path architecture:

| Path | Latency | Scope |
|---|---:|---|
| **Memory Cache** | 0.26 ms p50 | All actions (fast lookup, duplicate guard) |
| **SQLite WAL Write** | 1.77 ms p50 | Critical actions only (EXTERNAL_EFFECT, DESTRUCTIVE, PRIVILEGED) |

### Ledger States

```
PREPARED → STARTED → VERIFIED | FAILED | UNCERTAIN
                   → COMMITTED (EXTERNAL_EFFECT confirmed)
                   → CANCELLED (pre-start abort)
```

### Duplicate Guard

Before executing any action, the ledger checks if an identical fingerprint already exists:

| Prior State | Current Risk | Decision |
|---|---|---|
| VERIFIED / COMMITTED | Any | **Block** (already done) |
| STARTED / UNCERTAIN | Non-Idempotent | **Block** (unsafe to retry) |
| VERIFIED / COMMITTED | READ_ONLY (different request) | **Allow** (safe repeat) |

---

## 7. Audit Logging

### Append-Only Logger

The `AuditLogger` writes structured JSONL entries for every execution:

```json
{
  "timestamp": "2026-09-17T15:00:01Z",
  "request_id": "req_abc123",
  "graph_id": "g1",
  "node_id": "n1",
  "tool": "delete_file",
  "method": "NATIVE",
  "risk": "DESTRUCTIVE",
  "decision": "ALLOW_WITH_CONFIRMATION",
  "confirmation_ticket_id": "tkt_def456",
  "action_fingerprint": "sha256:...",
  "result_status": "VERIFIED",
  "verification_summary": "FileAbsentVerifier confirmed deletion",
  "duration_ms": 4.32
}
```

### Credential Redaction

All log entries are automatically scrubbed of sensitive patterns:
- `password: [REDACTED]`
- `Bearer [REDACTED]`
- `token: [REDACTED]`
- `api_key: [REDACTED]`
- `secret: [REDACTED]`

---

## 8. Golden Security Dataset

The file `tests/data/policy_golden.jsonl` contains **260 comprehensive security scenarios** covering:

| Category | Count | Examples |
|---|---:|---|
| READ_ONLY safe operations | 40 | list_dir, get_time, read_file |
| REVERSIBLE operations | 30 | create_folder, copy_file, move_file |
| DESTRUCTIVE operations | 30 | delete_file, format_drive |
| EXTERNAL_EFFECT operations | 25 | send_email, webhook, API calls |
| Protected path violations | 30 | C:\Windows, C:\Program Files, other user profiles |
| Path traversal attacks | 25 | `..\..\Windows`, symlink traversal |
| UAC/privilege escalation | 20 | install_software, modify_registry |
| Shell injection attempts | 20 | `shell=True`, PowerShell commands |
| Argument tampering | 20 | Modified args after ticket approval |
| Duplicate suppression | 20 | Repeated non-idempotent operations |

All 260 scenarios pass with 100% accuracy in `jarvis/tests/test_policy_security.py`.

---

## 9. CLI Integration

### `--dry-run-policy`

Simulates the complete policy evaluation pipeline without executing any actions:

```
$ python -m jarvis.cli "time" --dry-run-policy
============================================================
JARVIS EDGE -- Phase 5 Dry-Run Policy & Verification Report
============================================================
Goal:               time
Nodes Planned:      1
------------------------------------------------------------
Node ID:            n1
  Tool:             get_time
  Risk:             READ_ONLY
  Policy Decision:  ALLOW
  Reason Code:      DEFAULT_ALLOW
  Confirmation Req: False
  Selected Method:  NATIVE
  Expected Verif:   BasicVerifier
------------------------------------------------------------
Policy Dry-Run complete. ZERO actions executed.
============================================================
```

### `--explain-execution`

Shows detailed execution diagnostics for each node:

```
$ python -m jarvis.cli "time" --explain-execution
============================================================
JARVIS EDGE -- Phase 5 Explain Execution Diagnostics
============================================================
Command:                time
Planning Latency:       2345.80 ms

[Node n1: get_time]
  policy_ms:            0.040 ms
  precondition_ms:      0.007 ms
  method_selection_ms:  0.002 ms
  execution_ms:         0.000 ms (simulated)
  verification_ms:      0.085 ms (estimated)
  ledger_ms:            0.040 ms (cached)
  retry_count:          0
  method:               NATIVE
  status:               ALLOWED (DEFAULT_ALLOW)

============================================================
```

---

## 10. File Manifest

| File | Purpose |
|---|---|
| `jarvis/security/policy/evaluator.py` | Pre-compiled deterministic policy evaluator |
| `jarvis/security/policy/models.py` | PolicyDecision, PolicyDecisionType, PolicyReasonCode |
| `jarvis/security/paths.py` | Path canonicalization, traversal defense, TOCTOU protection |
| `jarvis/security/confirmation/manager.py` | ConfirmationManager (ticket lifecycle, tamper detection) |
| `jarvis/security/confirmation/models.py` | ConfirmationTicket, compute_action_fingerprint |
| `jarvis/security/audit/logger.py` | Append-only AuditLogger with credential redaction |
| `jarvis/security/ledger/ledger.py` | ActionLedger (dual-path: memory + SQLite) |
| `jarvis/security/ledger/models.py` | LedgerState, LedgerEntry |
| `jarvis/db/migrations/005_security_ledger.sql` | Database schema for action_ledger, method_stats, audit_log |
| `config/policy.toml` | Policy configuration (protected roots, confirmation timeout, restrictions) |
| `tests/data/policy_golden.jsonl` | 260 golden security test scenarios |
| `jarvis/tests/test_policy_security.py` | 6 tests covering full 260-scenario evaluation |
| `jarvis/tests/test_action_ledger.py` | 5 tests covering ledger operations |
| `jarvis/tests/test_verifiers.py` | 5 tests covering verification strategies |
| `scripts/generate_policy_golden.py` | Generator for policy golden dataset |
