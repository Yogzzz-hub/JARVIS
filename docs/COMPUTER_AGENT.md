# JARVIS EDGE — Structured Computer Agent Specification
## Windows UI Automation, Accessibility Control Trees & Verified Interaction

## 1. Overview & Fundamental Principle

The Computer Agent enables **JARVIS EDGE** to observe and interact with Microsoft Windows desktop applications through official accessibility control trees without requiring proprietary APIs for every application.

### Fundamental Invariant
> **NEVER AUTOMATE BY SCREEN COORDINATES WHEN STRUCTURED INFORMATION EXISTS.**

Pixel-based clicking (`click(x, y)`) is brittle, layout-dependent, and prone to catastrophic misclicks. All normal Phase-10 desktop interactions occur strictly through structured UI Automation patterns (`InvokePattern`, `ValuePattern`, `TogglePattern`, `SelectionPattern`). If an application provides no accessibility tree or structured metadata, the engine halts and returns a first-class `VISION_REQUIRED` error (deferring to Phase 11).

---

## 2. Automation Priority Hierarchy

JARVIS follows this strict decision cascade when resolving user requests:

1. **Official / Service API** (e.g. Gmail, Calendar, Drive via Phase 9)
2. **Native Jarvis Tool** (e.g. `open_app`, `get_volume`, `find_files`)
3. **Application-Specific API / IPC**
4. **Application CLI Command** (e.g. `git`, `code --goto`, `winget`)
5. **Browser Playwright Semantic DOM**
6. **Windows UI Automation (UIA)**
7. **Registered Keyboard Shortcut** (e.g. `Ctrl+S`, `Alt+F4`)
8. **Controlled Input Simulation** (strictly with focus & target verification)
9. **Vision Fallback** (*Phase 11 — Local Candidate-First Vision via `VisionManager`*)
10. **Absolute Screen Coordinates** (*Zero coordinate guessing permitted*)

UI automation is never used when a clean API or CLI tool is available.

---

## 3. Architecture & Components

```
                 USER REQUEST
                       │
                       ▼
                ROUTER / PLANNER
                       │
                       ▼
                CAPABILITY SELECTOR
                       │
        ┌──────────────┼───────────────┐
        │              │               │
        ▼              ▼               ▼
   Native/API      Browser DOM      Windows UIA
        │              │               │
        └──────────────┼───────────────┘
                       │
                       ▼
             INTERACTION CONTROLLER
                       │
                       ▼
                  OBSERVATION
                       │
                       ▼
              TARGET RESOLUTION (Strict / Unique)
                       │
                       ▼
                 POLICY CHECK (Phase 5)
                       │
                       ▼
                    ACTION (Structured Pattern)
                       │
                       ▼
                  VERIFICATION
                       │
                 success?
                  /     \
                yes      no
                 │        │
                 ▼        ▼
               DONE   bounded retry/
                      VISION_REQUIRED
```

### Key Modules in `jarvis/core/computer/windows/`:
- **`backend.py` (`WindowsUIABackend`)**: Direct adapter using Microsoft UI Automation and `pywin32`.
- **`windows.py` (`WindowManager`)**: Window discovery (`ui_list_windows`) with PID, title, and foreground tracking.
- **`snapshot.py` (`UIASnapshotBuilder`)**: Captures bounded Control View snapshots (depth $\le 8$, elements $\le 500$, pruning decorative noise).
- **`locator.py` (`UIALocator`)**: Resolves targets with confidence ranking (`HIGH`, `MEDIUM`, `LOW`, `AMBIGUOUS`).
- **`patterns.py` (`UIAPatterns`)**: Direct pattern invocation wrappers.
- **`actions.py` (`WindowsActionRunner`)**: High-level typed action execution.
- **`mock_backend.py` (`MockWindowsUIABackend`)**: In-memory synthetic desktop harness for 100% reliable CI testing.

---

## 4. Target Resolution & Ambiguity Protection

### Target Resolution Priority:
1. `automation_id` + `control_type` + `name`
2. `automation_id` alone
3. `control_type` / `role` + `name` (exact match)
4. `name` (exact match)
5. `ancestor_path` + `name`
6. Substring match
7. Structured fuzzy match

### Ambiguity Rule:
If more than one element matches the locator criteria, the resolution returns `TargetConfidence.AMBIGUOUS`. The engine **never** clicks the first element arbitrarily. Ambiguous targets halt execution or ask for clarification.

---

## 5. Security & Safety Invariants

1. **Zero Pixel Coordinate Clicking**: Prohibited in all Phase 10 production and test execution paths.
2. **Password & Credential Guard**: Controls marked as password, PIN, or OTP trigger `PAUSE_FOR_USER`. Jarvis refuses to read, extract, or log credentials.
3. **UAC / Secure Desktop Guard**: Prompts from User Account Control automatically trigger `PAUSE_FOR_USER`. Secure desktop automation is strictly blocked.
4. **No Terminal Shell Backdoors**: The computer agent cannot send free-form arbitrary shell commands into `cmd.exe` or PowerShell to bypass system safety policies.
5. **Consequential Action Ledger**: Destructive operations (e.g. deleting files, closing unsaved documents) require Phase-5 confirmation tickets and record entries into `ActionLedger`.

---

## 6. Hand-off to Phase 11 Local Vision Fallback (`VisionManager`)

When Phase 10 structured interaction encounters an inaccessible control, custom drawn canvas, remote desktop surface, or non-standard desktop toolkit lacking accessibility trees, it emits `status: VISION_REQUIRED`.

### Hand-off Protocol:
1. **Trigger Condition**: UI automation yields no candidate elements or `element_not_found`, but user intent targets that window.
2. **Handoff Invocation**: Control transfers to `jarvis.core.vision.manager.VisionManager` with:
   - Target window identifier (`window_id` / title / PID)
   - Desired user goal (e.g. `"click export button"`, `"where is the submit button?"`)
   - Bounded execution step budget (default $\le 8$ steps)
3. **Candidate-First Invariant**: The vision subsystem never asks local models to author raw $(x, y)$ coordinates. An integrated candidate detector (`SimpleRegionsParser` / `OmniParserAdapter`) identifies bounding boxes and assigns ephemeral candidate IDs ($C_1, C_2, \dots$).
4. **Structured Re-Discovery Priority**: On every visual observation step, `VisualTargetResolver` cross-checks with Windows UIA and browser DOM. If a structured accessibility element has become available (e.g., after a canvas menu opens an OS popup), the structured target is preferred over visual approximation.
5. **Postcondition Verification**: Every visual action is verified by image differencing (`VisualVerifier`) and state re-capture. If the screen is unchanged or the window moved unexpectedly, execution fails truthfully (`SCREEN_UNCHANGED` / `STALE_VISUAL_OBSERVATION`).

