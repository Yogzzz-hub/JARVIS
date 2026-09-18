# JARVIS EDGE — Phase 11: Local Vision Fallback, Screen Grounding & Verified Visual Interaction

## 1. Architectural Mission & Activation Hierarchy

Phase 11 implements a **last-resort visual understanding and screen-grounding layer** for applications and web surfaces that do not expose structured accessibility trees, DOM elements, or native programmatic interfaces.

### Automation Priority Hierarchy
```
DIRECT API
    │
    ▼
NATIVE JARVIS TOOL
    │
    ▼
APPLICATION API / CLI
    │
    ▼
BROWSER PLAYWRIGHT DOM
    │
    ▼
WINDOWS UI AUTOMATION (UIA)
    │
    ▼
CONTROLLED INPUT FALLBACK
    │
    ▼
VISION FALLBACK (PHASE 11)  <-- LAST-RESORT AUTOMATION
    │
    ▼
STOP / ASK USER
```

### Core Activation Invariant
Vision activates **strictly on-demand** only when:
1. Phase-10 structured automation explicitly emits `VISION_REQUIRED` (e.g. custom renderers, canvas games, Electron apps with broken accessibility trees).
2. The user explicitly requests read-only visual inspection (e.g., *"What is on my screen?"* or *"Where is the Export button?"*).

Vision is **never** the primary control mechanism. Continuous background screen recording, periodic screen polling, and arbitrary autonomous desktop exploration are strictly prohibited.

---

## 2. Candidate-First Grounding Architecture

### The "No-Coordinate-Guessing" Mandate
Jarvis never prompts a Vision-Language Model (VLM) to author direct screen coordinates (e.g. `click(742, 489)`). Instead, visual automation executes via a deterministic multi-stage pipeline:

```
           PHASE 10: VISION_REQUIRED
                       │
                       ▼
           Window-Scoped Capture (On-Demand)
                       │
                       ▼
           Privacy & Prompt-Injection Gate
                       │
                       ▼
           Visual Candidate Detector (SimpleRegions / OmniParser)
                       │
           Extract Candidates [C1, C2, C3, ...]
                       │
                       ▼
           Local VLM Grounder (Qwen3-VL 2B)
           Selects Candidate ID (e.g., "C2")
                       │
                       ▼
           Structured Anchor Cross-Check (UIA/DOM)
                       │
                       ▼
           Deterministic Confidence Fusion (HIGH / AMBIGUOUS / LOW)
                       │
                       ▼
           Phase-5 Policy & Confirmation Ticket
                       │
                       ▼
           Pre-Click Fresh Revalidation
                       │
                       ▼
           Physical Coordinate Calculation (Code-Derived)
                       │
                       ▼
           Verified Physical Action Dispatch
                       │
                       ▼
           Fresh Post-Action Observation & Verification
```

---

## 3. Data Contracts & Models

### VisualCandidate
Represents a discrete, potentially interactive region identified on screen:
- `candidate_id`: Session-scoped identifier (e.g. `C1`, `C2`).
- `bbox_normalized`: Normalized $[x_1, y_1, x_2, y_2]$ coordinates in $[0.0, 1.0]$.
- `bbox_pixels`: Physical pixel bounding box $[x_1, y_1, x_2, y_2]$.
- `candidate_type`: Control classification (`button`, `icon`, `input`, `menu`, `tab`).
- `detector_confidence`: Bounding box detection confidence (0.0 to 1.0).
- `visible_text`: Text extracted from region if visible.
- `icon_description`: Visual icon classification (e.g. `trash`, `download`, `settings`).
- `source`: Extraction source (`simple_regions`, `omniparser`, `synthetic`).

### VisualObservation
- `observation_id`: Unique identifier for the capture.
- `capture_region`: Bounding rectangle of the target window `{"left", "top", "width", "height"}`.
- `image_width`, `image_height`: Physical image pixel dimensions.
- `dpi_scale`: Window/monitor DPI scaling factor.
- `generation`: Incremental observation counter.
- `image_hash`: Perceptual SHA-256 state fingerprint for loop stall detection.
- `privacy_classification`: Set to `UNTRUSTED_EXTERNAL_CONTENT`.

---

## 4. Coordinate Transformations & DPI Awareness

Coordinates authoring is strictly isolated in `VisualInputController.compute_physical_click_point()`:

$$\text{screen\_x} = \text{window\_left} + \text{round}(c_x \times \text{dpi\_scale})$$
$$\text{screen\_y} = \text{window\_top} + \text{round}(c_y \times \text{dpi\_scale})$$

- **Multi-Monitor Display Awareness**: Correctly accounts for secondary monitors positioned with negative virtual coordinates (e.g. secondary monitor left at $-1920$).
- **DPI Scaling**: Integrates Windows per-monitor DPI scaling factors ($1.0\times, 1.25\times, 1.5\times$).
- **Bounding Box Validation**: Candidates with degenerate or out-of-window bounds are rejected prior to click dispatch (`INVALID_CANDIDATE_BOUNDS`).

---

## 5. Security & Privacy Invariants

| Invariant | Implementation Mechanism | Violation Action |
|---|---|---|
| **Zero Screen Recording** | `ScreenCaptureProvider` runs solely on explicit task demand | Blocked |
| **Ephemeral RAM Only** | Screenshot bytes reside only in volatile RAM; deleted post-step | 0 disk writes |
| **Zero Persistent Logging** | Raw screenshots omitted from logs unless explicit `--save-debug` flag | 0 image leaks |
| **Password / Secret Redaction** | Known password boxes redacted with black fill before VLM inference | 0 vision of secrets |
| **Password / Auth Screen** | Password fields or auth dialogs trigger `AUTH_REQUIRED` / `PAUSE_FOR_USER` | Zero password typing |
| **CAPTCHA Challenges** | Challenge elements or text triggers `PAUSE_FOR_USER` | Zero solving or bypass |
| **UAC / Secure Desktop** | Elevation prompts trigger `UAC_REQUIRED` / `PAUSE_FOR_USER` | Zero UAC automation |
| **Visual Prompt Injection** | Screen text scanned for adversarial patterns; tagged `UNTRUSTED_EXTERNAL_CONTENT` | Zero command authority |
| **Consequential Actions** | Send, Delete, Submit, Upload require Phase-5 `ConfirmationTicket` + `ActionLedger` | Zero unconfirmed actions |
| **Stale Screen Movement** | Target window movement between capture and click triggers `STALE_VISUAL_OBSERVATION` | Zero misplaced clicks |
| **Ambiguous Icons** | Duplicate identical icons without context return `TargetConfidence.AMBIGUOUS` | Zero blind clicks |
| **Uncertain Side-Effects** | Network or UI timeouts marked `UNCERTAIN`; blind retries prohibited | Zero duplicate writes |

---

## 6. Model Lifecycle & VRAM Resource Management

- **Cold Startup**: The local vision model (`Qwen3-VL-2B-Instruct Q4_K_M`) is kept **COLD** during normal Jarvis operation ($0.0\text{ MB VRAM}$ idle).
- **On-Demand Loading**: Loaded into memory only when `VISION_REQUIRED` is triggered or when read-only visual inspection is requested.
- **VRAM Prioritization**: If GPU memory pressure occurs on 4 GB graphics cards, idle planner models are evicted. Active speech input (Whisper) is **never** evicted.
- **Auto-Unload**: Unloaded after inactivity to preserve system resources for core routing and file search.
- **Hardware Profile**: Fully verified on 16 GB RAM and NVIDIA RTX 3050 (4–6 GB VRAM).

---

## 7. Diagnostics & CLI Tools

### Visual Debug Inspector
```powershell
python -m jarvis.vision_debug
python -m jarvis.vision_debug --ground "Open Settings"
python -m jarvis.vision_debug --window <HWND> --save-debug <DIR>
```

### Vision System Report
```powershell
python -m jarvis.report vision
```

### CLI Execution Diagnostics
```powershell
python -m jarvis.cli "Open Settings" --dry-run-vision
python -m jarvis.cli "Open Settings" --explain-vision
```

---

## 8. Verification & Demonstration Suite (`scripts/demo_phase11.py`)

All 15 required acceptance demonstrations pass with 100% success rate:
- **Demo 1**: Inaccessible UI $\rightarrow$ `VISION_REQUIRED` $\rightarrow$ candidate $C_1$ grounded $\rightarrow$ clicked $\rightarrow$ verified.
- **Demo 2**: Dynamic button relocation $\rightarrow$ fresh capture derives updated coordinates.
- **Demo 3**: Duplicate delete icons without context $\rightarrow$ `AMBIGUOUS` $\rightarrow$ zero clicks.
- **Demo 4**: Relational grounding $\rightarrow$ "download next to report.pdf" resolves correct row.
- **Demo 5**: Visual Send button $\rightarrow$ Phase-5 policy confirmation enforced.
- **Demo 6**: Visual prompt injection $\rightarrow$ quarantined as data $\rightarrow$ zero actions.
- **Demo 7**: Login password screen $\rightarrow$ `AUTH_REQUIRED` $\rightarrow$ zero scraping.
- **Demo 8**: CAPTCHA screen $\rightarrow$ `PAUSE_FOR_USER` $\rightarrow$ zero bypass.
- **Demo 9**: Window movement $\rightarrow$ `STALE_VISUAL_OBSERVATION` $\rightarrow$ prevents misplaced clicks.
- **Demo 10**: UI generation increment $\rightarrow$ candidate cache purged.
- **Demo 11**: VLM unavailable $\rightarrow$ `VISION_UNAVAILABLE` $\rightarrow$ core system stable.
- **Demo 12**: OmniParser unavailable $\rightarrow$ graceful fallback to region detector.
- **Demo 13**: Malformed model candidate ID $\rightarrow$ validator rejects $\rightarrow$ zero clicks.
- **Demo 14**: Screen pixels unchanged after click $\rightarrow$ postcondition verification `FAILED`.
- **Demo 15**: Read-only "Where is Export?" $\rightarrow$ returns coordinates without clicking.
