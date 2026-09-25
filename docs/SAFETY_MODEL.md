# JARVIS ULTRA — TEN NON-NEGOTIABLE SAFETY LAWS

## 1. Safety Primacy
In JARVIS ULTRA, **low latency never overrides authority or safety**. Shaving 50 milliseconds from an execution loop is meaningless if an agent acts on an incorrect target, runs untrusted shell code, or leaks sensitive credentials.

---

## 2. The Ten Non-Negotiable Safety Laws

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       THE TEN SAFETY LAWS OF JARVIS                         │
├────┬────────────────────────────────────────────────────────────────────────┤
│ 1  │ LOW LATENCY NEVER OVERRIDES AUTHORITY.                                 │
│ 2  │ NO ARBITRARY MODEL-GENERATED SHELL / POWERSHELL / CMD EXECUTION.       │
│ 3  │ NO ARBITRARY MODEL-GENERATED JAVASCRIPT / BROWSER RUN CODE.            │
│ 4  │ NO MODEL-GENERATED RAW $(X, Y)$ COORDINATE CLICKS.                     │
│ 5  │ NO UAC BYPASS — USER ALONE HANDLES PRIVILEGED ELEVATION.               │
│ 6  │ NO AUTOMATION OR SCRAPING OF PASSWORDS, PINS, OR OTPS.                 │
│ 7  │ NO CAPTCHA CHALLENGE AUTOMATION OR BYPASS — PAUSE FOR HUMAN USER.      │
│ 8  │ NO UNCONFIRMED INSTALL, DELETE, SEND, OR PURCHASE WHEN POLICY GUARDS. │
│ 9  │ NO UNVERIFIED "DONE" CLAIMS WITHOUT TYPED VERIFIER EVIDENCE.           │
│ 10 │ STABLE PARTIALS MAY PREVIEW/PREWARM; FINAL TRANSCRIPT AUTHORISES.      │
└────┴────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Implementation Verification Mechanisms

### Law 2 & 3: Elimination of Unrestricted Code Execution
- LLM outputs are restricted to Pydantic-validated JSON TaskGraphs.
- All system capabilities are registered typed functions (e.g. `open_app`, `set_volume`, `copy_file`).
- Shell tool wrappers (`run_shell`, `powershell_exec`, `browser_run_code`) do NOT exist in the LLM tool registry.

### Law 4: Candidate-First Visual Targeting
- Physical click dispatches require a named `VisualCandidate` with normalized bounding bounds.
- Clicks target the verified geometric center of that candidate only after confidence verification.

### Law 5, 6 & 7: Human Security Boundaries
- When a UAC dialog, password input field, or reCAPTCHA appears, the agent enters `PAUSE_FOR_USER` state.
- Automated typing into password fields is blocked at the input controller layer.

### Law 8: Cryptographic Confirmation Tickets
- Consequential mutations (deleting files, moving directories, sending emails, executing package installations) generate a unique confirmation ticket bound to the target and parameters.
- If parameters change, the previous ticket becomes immediately invalid.

### Law 9: Typed Postcondition Verification
- Success is never declared simply because a tool returned code 0.
- A typed verifier explicitly inspects external evidence (process table, window HWND, DOM state, file hash) before reporting completion.
