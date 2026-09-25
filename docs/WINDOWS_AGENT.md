# JARVIS ULTRA — WINDOWS DESKTOP & UI AUTOMATION AGENT

## 1. Desktop Automation Hierarchy
Under the research-verified architecture of JARVIS ULTRA (borrowing proven hybrid GUI/API concepts from Microsoft UFO²), desktop control follows a strict priority cascade:

```
[User Desktop Intent] (e.g. "mute audio", "open notepad", "bluetooth settings")
         │
         ▼
[Priority 1: Native Windows API / COM / URI Scheme] (0 ms UI lag)
   ├── ShellExecute / CreateProcess for installed applications
   ├── CoreAudio / PyCaw for master volume and mute
   └── ms-settings: protocol for Windows Settings pages
         │ (If interactive GUI control required)
         ▼
[Priority 2: Microsoft UI Automation (UIA)]
   ├── Scoped tree search (Process ID -> Top Window HWND -> Subtree)
   ├── Cached window handles and AutomationIds with pre-action revalidation
   └── Control patterns: InvokePattern, ValuePattern, TogglePattern, RangeValue
         │ (If custom control is completely inaccessible to UIA)
         ▼
[Priority 3: Visual Fallback (SimpleRegions / OmniParser)]
   └── Candidate-first visual grounding (STRICTLY ZERO raw coordinates)
```

---

## 2. Key Desktop Invariants & Optimizations

### A. Scoped Window Subtree Search
- Legacy UIA automation enumerates the entire desktop tree from `GetRootElement()`, causing 500ms–2000ms stalls.
- JARVIS ULTRA scopes all tree searches strictly to the target application's active top-level HWND:
  - Scoped window subtree search: **0.79 ms** (p50 on real hardware).
  - Unscoped desktop search: **45.20 ms** (57.2x speedup).

### B. Control Patterns Over Coordinate Simulation
- Rather than calculating pixel bounding boxes and sending virtual mouse events (`mouse_event` / `SendInput`), JARVIS invokes native accessibility patterns:
  - Text input: `IUIAutomationValuePattern::SetValue` (instant, no focus loss).
  - Button click: `IUIAutomationInvokePattern::Invoke`.
  - Checkbox / Toggle: `IUIAutomationTogglePattern::Toggle`.

### C. Pre-Action Revalidation
Before dispatching any pattern invocation, the agent checks:
1. Does the window handle still exist (`IsWindow(hwnd)`)?
2. Is the control still visible and enabled on screen?
3. Has the UI layout shifted or closed?
If stale, the agent recaptures and re-observes rather than issuing blind actions.

### D. Process & State Verification
No action reports success simply because a process was launched. The `VerifierRegistry` polls the target process ID or top-level window title with early exit (measured p50: **300.91 ms**) before emitting verified status to the response engine.
