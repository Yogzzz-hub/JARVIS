# JARVIS ULTRA — ACTIONLEDGER & DURABLE STATE MACHINE

## 1. ActionLedger Architecture
External desktop and network actions have irreversible real-world side effects. To guarantee reliability, prevent duplicate execution, and provide complete auditability, all consequential operations in JARVIS ULTRA are tracked via a durable, append-only SQLite ledger (`ActionLedger`).

```
           [Task Node / Command Request]
                         │
                         ▼
                    [PREPARED] ────(Fingerprint & Idempotency Key Generated)
                         │
                         ▼
                    [AUTHORISED] ──(Policy & Confirmation Verified)
                         │
                         ▼
                     [STARTED]
                    /    │    \
                   /     │     \
                  ▼      ▼      ▼
              [VERIFIED] [FAILED] [UNCERTAIN]
                  │
                  ▼
             [COMMITTED]
```

---

## 2. State Machine Transitions

| State | Description | Transition Trigger | Permitted Next States |
| :--- | :--- | :--- | :--- |
| **`PREPARED`** | Action synthesized with typed arguments, target, and risk level. | Action creation | `AUTHORISED`, `CANCELLED` |
| **`AUTHORISED`** | Policy validation passed; confirmation ticket verified if required. | Policy sign-off | `STARTED`, `CANCELLED` |
| **`STARTED`** | External invocation dispatched to native API, UIA, or Playwright. | Tool dispatch | `VERIFIED`, `FAILED`, `UNCERTAIN` |
| **`VERIFIED`** | Typed verifier confirmed target state change (process alive, DOM updated, file present). | Verifier evidence | `COMMITTED` |
| **`COMMITTED`** | Final status recorded; evidence logged to durable storage. | Post-verification commit | Terminal State |
| **`FAILED`** | Action failed with explicit error or verifier postcondition unmet. | Explicit error | Terminal State |
| **`UNCERTAIN`** | Invocation timed out or external status unknown. | Network / IPC timeout | **TERMINAL STATE (NO AUTO-RETRY)** |
| **`CANCELLED`** | User revoked command or barge-in cancelled pipeline. | User / System cancel | Terminal State |

---

## 3. The Strict UNCERTAIN State Law

When an external side-effecting action (sending an email, creating a remote resource, submitting a web form) encounters a socket timeout or network disconnection:
1. The state is recorded as **`UNCERTAIN`**.
2. **AUTOMATIC BLIND RETRY IS STRICTLY FORBIDDEN**. Retrying an unconfirmed external action can send duplicate emails, double-bill orders, or corrupt remote state.
3. The response engine reports the uncertainty honestly to the user ("The request timed out before confirmation; please verify in your browser before re-sending.").
