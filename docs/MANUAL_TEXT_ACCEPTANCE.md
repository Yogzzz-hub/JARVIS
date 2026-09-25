# JARVIS EDGE — MANUAL TEXT ACCEPTANCE TEST MATRIX

This matrix defines the complete real-world manual acceptance test sequence for JARVIS EDGE v1.0.

> **RULE**: Testing must proceed **ONE TEST AT A TIME**, strictly in order.
> **RULE**: Voice tests (STAGE 18) are **FROZEN** until all text, deterministic, Windows, file, planner, and browser stages pass.

---

## STAGE 1 — Text Input Path & Core Connectivity
| Test ID | Phase / Module | Exact Text to Type | Expected Route | Expected Tool | Expected Real-World Result | Expected Verification | Expected Response Type | Risk Class | Status | Actual Result | Latency | Trace ID |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **T001** | Core / Gateway | `what time is it` | LANE0 (Deterministic) | `get_time` | Current system local time returned immediately | Output schema validated | Spoken + Text | READ_ONLY | **PASSED** | "It is 12:55 PM on Tuesday, September 22, 2026." | 10.9 ms | 11438887597900 |
| **T001b** | Core / Gateway | `What is today's date?` | LANE0 (Deterministic) | `get_time` | Correct live date and time returned | Output schema validated | Spoken + Text | READ_ONLY | **PASSED** | "It is 12:55 PM on Tuesday, September 22, 2026." | 11.2 ms | verified |
| **T002** | Core / Gateway | `system info` / `Show system information` | LANE0 (Deterministic) | `system_info` | CPU, RAM, OS, Battery telemetry displayed | Telemetry verified | Text / Spoken | READ_ONLY | **PASSED** | "Windows-11... running on Intel64... with 15.7 GB RAM (13.8 GB in use)." | 12.4 ms | verified |
| **T003** | Core / Gateway | `diagnostics` / `Show Jarvis status` | LANE0 (Deterministic) | `system_diagnostics` | Subsystem audit report returned | Subsystem audit verified | Text / Spoken | READ_ONLY | **PASSED** | "System diagnostics completed: 31/37 checks passed. All critical core services and models are healthy." | 14.8 ms | verified |
| **T003b** | Router / Control | `Cancel` | CONTROL | `control` | Clean cancellation of running tasks | Task state verified | Spoken / Text | READ_ONLY | **PASSED** | "No active tasks to cancel." | 0.5 ms | 11709299592100 |

---

## STAGE 2 — Deterministic / Static Commands & Media Controls
| Test ID | Phase / Module | Exact Text to Type | Expected Route | Expected Tool | Expected Real-World Result | Expected Verification | Expected Response Type | Risk Class | Status | Actual Result | Latency | Trace ID |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **T004** | Audio / Win32 | `mute` | LANE0 (Deterministic) | `volume_set` or `media_control` | System audio muted via Win32 endpoint | Endpoint volume status verified | Spoken + Event | REVERSIBLE | NOT_TESTED | - | - | - |
| **T005** | Audio / Win32 | `set volume to 50%` | LANE0 (Deterministic) | `volume_set` | Master volume set to 50% | Audio endpoint level verified | Spoken + Event | REVERSIBLE | NOT_TESTED | - | - | - |
| **T006** | System / GUI | `show desktop` | LANE0 (Deterministic) | `show_desktop` | All windows minimized; desktop exposed | Win32 keybd_event(Win+D) verified | Fast Silent / Text | REVERSIBLE | NOT_TESTED | - | - | - |
| **T007** | Multimedia | `open youtube and play believer` | LANE0 (Deterministic) | `play_youtube` | Browser opens YouTube search and confirms playback | Native URL launch verified | Spoken + Browser | REVERSIBLE | NOT_TESTED | - | - | - |
| **T008** | Realtime News | `search news in india` | LANE0 (Deterministic) | `search_news` | Live Google News RSS headlines extracted and spoken | RSS parsed & verified | Spoken + Browser | REVERSIBLE | NOT_TESTED | - | - | - |

---

## STAGE 2.1 — Negation Safety Tests (Before Consequential Execution)
| Test ID | Phase / Module | Exact Text to Type | Expected Route | Expected Tool | Expected Real-World Result | Expected Verification | Expected Response Type | Risk Class | Status | Actual Result | Latency | Trace ID |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **T009** | Router / Negation | `don't open notepad` | CANCEL / NO-OP | `None` | **Zero actions executed**. Notepad must NOT open. | Negation verified | Spoken / Text | READ_ONLY | NOT_TESTED | - | - | - |
| **T010** | Router / Negation | `do not close chrome` | CANCEL / NO-OP | `None` | **Zero actions executed**. Chrome stays open. | Negation verified | Spoken / Text | READ_ONLY | NOT_TESTED | - | - | - |

---

## STAGE 3 — Real Windows Application Control
| Test ID | Phase / Module | Exact Text to Type | Expected Route | Expected Tool | Expected Real-World Result | Expected Verification | Expected Response Type | Risk Class | Status | Actual Result | Latency | Trace ID |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **T011** | Windows / AppCatalog | `open notepad` | LANE0 | `open_app` | Actual Windows Notepad window appears | Process & Window handle verified | Spoken + Window | REVERSIBLE | **PASSED** | "Notepad is open." | 683.4 ms | verified |
| **T012** | Windows / AppCatalog | `open calculator` / `Launch Calculator` | LANE0 | `open_app` | Actual Windows Calculator window appears | Process & Window handle verified | Spoken + Window | REVERSIBLE | **PASSED** | "Calculator is open." | 116.0 ms | verified |
| **T012b** | Windows / AppCatalog | `Can you open Microsoft Edge for me?` | LANE0 | `open_app` | Actual Microsoft Edge window opens | Process & Window handle verified | Spoken + Window | REVERSIBLE | **PASSED** | "Edge is open." | 27.3 ms | verified |
| **T013** | Windows / MicroWin32 | `maximize window` | LANE0 | `maximize_window` | Active window maximizes to fullscreen | ShowWindow(3) verified | Fast Silent / Text | REVERSIBLE | NOT_TESTED | - | - | - |
| **T014** | Windows / MicroWin32 | `minimize window` | LANE0 | `minimize_window` | Active window minimizes to taskbar | ShowWindow(6) verified | Fast Silent / Text | REVERSIBLE | NOT_TESTED | - | - | - |
| **T015** | Windows / AppCatalog | `close notepad` | LANE0 | `close_app` | Running Notepad process/window terminates | Process termination verified | Spoken + Window | REVERSIBLE | NOT_TESTED | - | - | - |
| **T016** | Windows / AppCatalog | `open ABCXYZFakeApplication123` | CLARIFY / UNKNOWN | `None` | Reports unknown app; does NOT hallucinate | AppResolver rejected | Spoken / Text | READ_ONLY | NOT_TESTED | - | - | - |

---

## STAGE 4 — Filesystem & Sandbox Tests (`JARVIS_TEST_SANDBOX`)
| Test ID | Phase / Module | Exact Text to Type | Expected Route | Expected Tool | Expected Real-World Result | Expected Verification | Expected Response Type | Risk Class | Status | Actual Result | Latency | Trace ID |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **T017** | Filesystem / Search | `find file alpha.txt` | LANE0 | `find_file` | Locates `alpha.txt` in test sandbox | ResourceRef generated | Text + Path | READ_ONLY | NOT_TESTED | - | - | - |
| **T018** | Filesystem / Directory | `list desktop` | LANE0 | `list_directory` | Lists directory contents with item count | Filesystem directory verified | Text | READ_ONLY | NOT_TESTED | - | - | - |
| **T019** | Filesystem / Write | `create a folder called DemoFolder in sandbox` | LANE1/2 | `create_folder` | New directory created on disk | Path existence verified | Text | REVERSIBLE | NOT_TESTED | - | - | - |
| **T020** | Filesystem / Destructive | `delete disposable-test.txt` | LANE1/2 + POLICY | `delete_file` | Triggers Phase-5 security confirmation ticket | Policy ticket generated | CONFIRMATION | DESTRUCTIVE | NOT_TESTED | - | - | - |

---

## STAGE 5 — Ollama & Lane 1 Routing
| Test ID | Phase / Module | Exact Text to Type | Expected Route | Expected Tool | Expected Real-World Result | Expected Verification | Expected Response Type | Risk Class | Status | Actual Result | Latency | Trace ID |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **T021** | Ollama / Lane 1 | `could you bring up the calculator for me` | LANE1 (Ollama) | `open_app` | Maps paraphrased request to `open_app(calculator)` | Calculator window verified | Spoken + Window | REVERSIBLE | NOT_TESTED | - | - | - |

---

## STAGE 6 — Complex Multi-Step Planner (Lane 2 DAG)
| Test ID | Phase / Module | Exact Text to Type | Expected Route | Expected Tool | Expected Real-World Result | Expected Verification | Expected Response Type | Risk Class | Status | Actual Result | Latency | Trace ID |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **T022** | Planner / Lane 2 | `open calculator and notepad` | LANE0 (Compound) | Compound [open_app, open_app] | Both Calculator and Notepad appear | Both windows verified | Spoken + Windows | REVERSIBLE | NOT_TESTED | - | - | - |

---

## STAGE 7 — Policy, ActionLedger & Verification
| Test ID | Phase / Module | Exact Text to Type | Expected Route | Expected Tool | Expected Real-World Result | Expected Verification | Expected Response Type | Risk Class | Status | Actual Result | Latency | Trace ID |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **T023** | Policy / Confirmation | `cancel` | LANE0 (CONTROL) | Control Cancel | Rejects pending destructive action; 0 file changes | ActionLedger CANCELLED verified | Spoken + State | READ_ONLY | NOT_TESTED | - | - | - |

---

## STAGE 8 — Browser (Playwright Semantic Actions)
| Test ID | Phase / Module | Exact Text to Type | Expected Route | Expected Tool | Expected Real-World Result | Expected Verification | Expected Response Type | Risk Class | Status | Actual Result | Latency | Trace ID |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **T024** | Browser / Playwright | `open example.com in browser` | LANE1/2 | `browser_open_url` | Navigates to example.com via Playwright | Page title / URL verified | Text | REVERSIBLE | NOT_TESTED | - | - | - |

---

## STAGE 9 — Windows UI Automation (UIA)
| Test ID | Phase / Module | Exact Text to Type | Expected Route | Expected Tool | Expected Real-World Result | Expected Verification | Expected Response Type | Risk Class | Status | Actual Result | Latency | Trace ID |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **T025** | UIA / Inspection | `inspect active window UI tree` | LANE1/2 | `desktop_ui_snapshot` | Returns structural control tree of foreground window | UI elements verified | Text | READ_ONLY | NOT_TESTED | - | - | - |

---

## STAGE 10 — Screen / Vision Fallback
| Test ID | Phase / Module | Exact Text to Type | Expected Route | Expected Tool | Expected Real-World Result | Expected Verification | Expected Response Type | Risk Class | Status | Actual Result | Latency | Trace ID |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **T026** | Vision / Fallback | `take a screenshot` | LANE0 | `take_screenshot` | Captures display to disk and registers reference | Image file existence verified | Text + Image | REVERSIBLE | NOT_TESTED | - | - | - |

---

## STAGE 11 — Memory & Pronoun Reference Resolution
| Test ID | Phase / Module | Exact Text to Type | Expected Route | Expected Tool | Expected Real-World Result | Expected Verification | Expected Response Type | Risk Class | Status | Actual Result | Latency | Trace ID |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **T027** | Working Memory | `close it` | LANE0 / Context | `close_app` | Resolves "it" to most recently manipulated application | Process termination verified | Spoken + Window | REVERSIBLE | NOT_TESTED | - | - | - |

---

## STAGE 18 — Voice Commands (FROZEN UNTIL STAGES 1-17 PASS)
| Test ID | Phase / Module | Spoken Phrase | Expected Route | Expected Tool | Expected Real-World Result | Expected Verification | Expected Response Type | Risk Class | Status | Actual Result | Latency | Trace ID |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **V001** | Voice / PTT | `"What time is it?"` | LANE0 | `get_time` | Speech recognized accurately; time spoken aloud | STT match + Time verified | Spoken | READ_ONLY | **FROZEN** | - | - | - |
