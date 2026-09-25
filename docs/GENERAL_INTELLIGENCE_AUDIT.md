# JARVIS EDGE v1.x: General Intelligence & Architecture Audit

## Executive Summary
This document establishes the official architectural baseline and generalization audit of the existing **JARVIS EDGE** system across Phases 1 through 12. 
In accordance with core engineering principles, **Phase 13 is NOT created**. We do not tear down or duplicate the existing hardened architecture, nor do we solve generalization by exploding regexes or hardcoding thousands of sentences.
Instead, this audit analyzes every existing subsystem and defines the exact transition from sentence-matching to **Capability-Driven Reasoning**.

---

## A. Current Architecture Discovered

JARVIS EDGE is structured as a low-latency, hybrid local AI assistant built in Python 3.11/3.12 for Windows 10/11 with a local Ollama LLM backend, Faster-Whisper STT, Piper TTS, and Win32/UIA/Playwright subsystems.

### Core Architecture Layers:
1. **Runtime & Event Infrastructure (`jarvis/core/runtime.py`, `jarvis/core/events/bus.py`)**:
   - `Runtime`: Central orchestrator initializing persistence, memory, search engine, tool registry, execution engine, verifier, router, audio pipeline, and omnichannel bridges.
   - `EventBus`: In-memory asynchronous pub/sub event bus with bounded per-subscriber queues (default 1024 capacity), queue overflow drops, and isolated async consumer tasks.
   - `PersistenceWriter`: Dedicated background thread writing SQLite WAL logs and request records with non-blocking enqueue to guarantee zero-latency spikes on the critical execution path.
   - `ProactorEventLoop`: Windows asynchronous I/O loop supporting high-throughput named pipes, sub-processes, and sockets.

2. **Perception & Speech Pipeline (`jarvis/core/audio/`, `jarvis/core/stt/`, `jarvis/core/tts/`)**:
   - `OpenWakeWordEngine`: Low-CPU streaming wake-word detection (`openwakeword`).
   - `FasterWhisperEngine`: Int8/Float16 batched local transcription via `faster-whisper`.
   - `PiperEngine`: Real-time offline neural voice synthesis (`piper-tts`).
   - `PulseEngine` (Phase 2 Speculative Acknowledgment): Parallel speculative acknowledgment playing sub-250ms phonetic acks while planner/execution runs in background.

3. **Tool & Execution Engine (`jarvis/tools/`, `jarvis/core/executor/`)**:
   - `ToolRegistry`: Immutable finalized catalog of 80 system and productivity tools with strict Pydantic `input_model` and `output_model` schemas.
   - `ExecutionEngine` (Phase 5 Hardened): Strict policy evaluation (`PolicyEvaluator`), confirmation ticket gating (`ConfirmationManager`), tamper-evident audit logging (`ActionLedger`), TOCTOU file race snapshots, and undo capabilities (`UndoManager`).
   - `MethodSelector`: Multi-lane execution cascade: `NATIVE` (Win32 API / OS calls) -> `POWERSHELL` -> `UIA` (Windows UI Automation) -> `VISION` (Screenshot + OCR/LLM).

4. **Routing & Intent Pipeline (`jarvis/core/router/`)**:
   - `SmartRouter`: Multi-lane router balancing sub-millisecond execution with local LLM flexibility.
   - `Lane 0`: Exact regex / pattern match (<0.5 ms) via `intents.yaml`.
   - `Lane 0.5`: Fuzzy match via `rapidfuzz` (>88% token set ratio).
   - `Lane 1`: Fast local Ollama LLM intent and slot extraction.
   - `Lane 2`: Adaptive Complex Planner DAG generator.

5. **Planning Subsystem (`jarvis/core/planner/`)**:
   - `AdaptivePlanner`: Dynamic task decomposition for multi-step tasks.
   - `DeterministicDecomposer`: High-confidence 2-step compound splitter.
   - `ToolRetriever`: BM25/keyword candidate tool filtering (Top-K compact schemas).
   - `GraphValidator`: Pydantic TaskGraph schema validation, cycle detection, and tool name validation.
   - `GraphOptimizer`: Safe read-only node deduplication.

6. **Context & Memory (`jarvis/memory/`, `jarvis/core/context/`, `jarvis/core/memory/`)**:
   - `WorkingMemory`: In-memory tracking of recent entities (files, folders, apps, URLs, contacts, search results).
   - `ReferenceResolver`: Deterministic resolver for conversational pronouns ("it", "that file"), ordinals ("the first one"), and folder continuity.
   - `SearchEngine` & `FileIndexer`: SQLite FTS5 full-text indexing, MIME extraction, and USN journal file watcher.
   - `SQLiteMemoryStore`: Persistent episodic facts and preferences with privacy tagging.

7. **Omnichannel & Connected Systems (`jarvis/integrations/`, `jarvis/connectors/`)**:
   - `WhatsAppIntegrationService`: Local WebSocket client connecting to Baileys Node.js bridge with draft-first security.
   - `AndroidConnector`: ADB and scrcpy phone control and screen mirroring.
   - `GoogleConnectors`: Gmail, Calendar, Drive read-only & drafted integrations.

---

## B. Existing Capability Count

JARVIS currently possesses **80 distinct registered tools**, categorized across **12 functional domains**:

| Domain / Category | Tool Count | Primary Responsibilities |
| :--- | :---: | :--- |
| **SYSTEM** | 10 | Clock, system diagnostics, audio devices, microphone/STT/wake health, voice selection, dashboard |
| **APP** | 7 | Launch, close, check installation, get location, list installed apps, refresh catalog, install software |
| **WINDOWS** | 14 | Window minimize/maximize/close, desktop toggle, volume/mute control, screenshots, UIA click/snapshot, media playback |
| **BROWSER** | 6 | Managed Playwright navigation, page snapshots (DOM accessibility tree), clicking, typing, URL opening, YouTube |
| **FILE** | 12 | Directory listing, FTS5 search, open, create folder, rename, move, copy, recycle-bin delete, metadata, batch rename, download organizer, duplicate finder |
| **RAG / KNOWLEDGE**| 12 | Document QA, note capture, note search, Memos inbox/recent, daily/morning briefings, meeting notes, RSS news, web search, Ollama chat |
| **PHONE** | 9 | Android status, scrcpy mirror open/close, Home/Back navigation, phone app launch, LocalSend file/text push, push notifications (ntfy/Gotify) |
| **WHATSAPP** | 4 | Send message (draft/policy gated), read unread messages, summarize urgent messages, bridge actions |
| **GOOGLE** | 4 | Gmail search, Calendar list/create, Drive search (read-only / draft mode) |
| **TERMINAL** | 1 | Guarded administrator PowerShell execution with policy checks and argument validation |
| **WORKFLOW** | 1 | Workspace save/launch, focus session timer, developer unit test runner, git status, audio extraction, clip trimming |
| **TOTAL** | **80** | **100% of all executable system interactions** |

---

## C. Existing Tools Inventory

All 80 tools implement `jarvis.tools.base.Tool` with formal input/output schemas:

1. `android_back` (REVERSIBLE): Win32/ADB Back keyevent on Android phone.
2. `android_close_control` (REVERSIBLE): Closes active scrcpy screen mirroring window.
3. `android_home` (REVERSIBLE): Win32/ADB Home keyevent on Android phone.
4. `android_open_app` (REVERSIBLE): Launches package on Android device via monkey/intent.
5. `android_open_control` (REVERSIBLE): Spawns scrcpy low-latency desktop mirror.
6. `android_status` (READ_ONLY): Queries ADB devices, battery level, and scrcpy status.
7. `batch_rename` (REVERSIBLE): Previewed regex/pattern file rename with conflict avoidance.
8. `browser_click` (REVERSIBLE): Clicks DOM accessibility element via Playwright.
9. `browser_navigate` (REVERSIBLE): Navigates managed browser to validated web URL.
10. `browser_open_url` (REVERSIBLE): Launches or connects to Playwright page.
11. `browser_snapshot` (READ_ONLY): Extracts accessibility tree and interactive elements.
12. `browser_type` (REVERSIBLE): Fills text into active web form input.
13. `capture_note` (REVERSIBLE): Saves markdown note with timestamp.
14. `check_app_installed` (READ_ONLY): Queries AppCatalog for software existence.
15. `close_app` (REVERSIBLE): Closes running application by process name or window handle.
16. `close_window` (REVERSIBLE): Closes foreground window in under 200us via Win32.
17. `connected_devices` (READ_ONLY): Enumerates audio endpoints and primary monitors.
18. `copy_file` (REVERSIBLE): Copies local file with TOCTOU check.
19. `create_folder` (REVERSIBLE): Creates directory hierarchy.
20. `delete_file` (REVERSIBLE): Safely moves file to Windows Recycle Bin (`send2trash`).
21. `desktop_ui_click` (REVERSIBLE): Windows UI Automation element click.
22. `desktop_ui_snapshot` (READ_ONLY): Captures accessibility hierarchy of focused window.
23. `diagnose_error` (READ_ONLY): Redacts tokens and diagnoses stack trace.
24. `dictate_text` (REVERSIBLE): Formats spoken text and inputs via keyboard automation.
25. `document_qa` (READ_ONLY): Answers document questions with section citations.
26. `extract_audio` (REVERSIBLE): Extracts MP3/WAV from video file via FFmpeg.
27. `find_duplicates` (READ_ONLY): Detects duplicate files using size + SHA-256.
28. `find_file` (READ_ONLY): Cascaded FTS5 + semantic local search.
29. `generate_meeting_notes` (REVERSIBLE): Extracts summary and action items from transcripts.
30. `get_app_location` (READ_ONLY): Retrieves installation path from AppCatalog.
31. `get_time` (READ_ONLY): Returns local ISO timestamp.
32. `git_status` (READ_ONLY): Checks modified files in developer repository.
33. `install_software` (REVERSIBLE): Installs package via winget and refreshes AppCatalog.
34. `launch_workspace` (REVERSIBLE): Restores apps, folders, and tabs from manifest.
35. `list_directory` (READ_ONLY): Lists contents of a directory.
36. `list_installed_applications` (READ_ONLY): Returns all cataloged applications.
37. `localsend_file` (REVERSIBLE): Sends local file to phone via LocalSend protocol.
38. `localsend_text` (REVERSIBLE): Sends clipboard or text to phone via LocalSend.
39. `maximize_window` (REVERSIBLE): Win32 `ShowWindow(SW_MAXIMIZE)`.
40. `media_control` (REVERSIBLE): Multimedia keyboard event (Play/Pause/Next/Prev/Mute).
41. `memos_create` (REVERSIBLE): Stores note in local Memos inbox.
42. `memos_recent` (READ_ONLY): Fetches recent notes from Memos.
43. `microphone_status` (READ_ONLY): Verifies audio input device health.
44. `minimize_window` (REVERSIBLE): Win32 `ShowWindow(SW_MINIMIZE)`.
45. `morning_briefing` (READ_ONLY): Aggregates RSS, weather, Memos, and health.
46. `move_file` (REVERSIBLE): Relocates file/directory with TOCTOU check.
47. `notification_send` (REVERSIBLE): Dispatches push notification via ntfy/Gotify.
48. `ollama_chat` (READ_ONLY): Queries local LLM for general knowledge/reasoning.
49. `open_app` (REVERSIBLE): Resolves executable via AppCatalog and launches process.
50. `open_file` (REVERSIBLE): Opens validated file with default OS shell handler.
51. `organize_downloads` (REVERSIBLE): Sorts downloaded files into categorized folders.
52. `personal_briefing` (READ_ONLY): Synthesizes daily task summary.
53. `play_youtube` (REVERSIBLE): Launches YouTube video or search in browser.
54. `powershell_command` (REVERSIBLE): Runs validated PowerShell command with audit.
55. `read_file_metadata` (READ_ONLY): Retrieves size, mtime, and MIME type.
56. `read_whatsapp_messages` (READ_ONLY): Reads incoming messages from Baileys transport.
57. `refresh_applications` (READ_ONLY): Scans registry, shortcuts, UWP, and PATH.
58. `rename_file` (REVERSIBLE): Renames file with conflict safety.
59. `rss_latest` (READ_ONLY): Fetches RSS headlines.
60. `run_project_tests` (REVERSIBLE): Runs pytest in approved project root.
61. `save_workspace` (REVERSIBLE): Serializes open apps and tabs into manifest.
62. `search_news` (READ_ONLY): Fetches live Indian/global headlines.
63. `search_notes` (READ_ONLY): Full-text search across local markdown notes.
64. `search_web` (READ_ONLY): Queries live web search API with citations.
65. `send_whatsapp_message` (EXTERNAL_EFFECT): Dispatches WhatsApp message (policy gated).
66. `set_voice` (REVERSIBLE): Switches Piper TTS voice (male/female).
67. `show_dashboard` (REVERSIBLE): Displays JARVIS monitoring dashboard.
68. `show_desktop` (REVERSIBLE): Win32 `Win+D` hardware event.
69. `speech_recognition_status` (READ_ONLY): STT engine status.
70. `start_study_focus` (REVERSIBLE): Activates focus mode and timer.
71. `summarize_whatsapp_messages` (READ_ONLY): Summarizes urgent messages.
72. `system_diagnostics` (READ_ONLY): Runs comprehensive subsystem diagnostic check.
73. `system_info` (READ_ONLY): Returns CPU, RAM, OS, and uptime stats.
74. `take_screenshot` (REVERSIBLE): Captures monitor frame to PNG via `mss`.
75. `trim_media_clip` (REVERSIBLE): Cuts media clip using FFmpeg.
76. `volume_get` (READ_ONLY): Returns master audio volume percent via PyCaw.
77. `volume_set` (REVERSIBLE): Sets master volume percent via PyCaw.
78. `wake_greeting` (REVERSIBLE): Plays randomized natural morning/evening greeting.
79. `wake_word_status` (READ_ONLY): Returns openWakeWord engine state.
80. `whatsapp_action` (REVERSIBLE): Controls WhatsApp transport (pair/connect/disconnect).

---

## D. Existing Router Behavior

`SmartRouter` (`jarvis/core/router/router.py`) handles incoming utterances through four lanes:

- **Lane 0 (Deterministic Pattern / Exact Grammar, <0.5 ms)**:
  Direct lookup using `intents.yaml` patterns (e.g. `^time$`, `^volume\s+(\d+)$`, `^open\s+(.+)$`).
- **Lane 0.5 (Fuzzy / Alias Matching, <2 ms)**:
  Extracts query tokens, evaluates against canonical aliases and `rapidfuzz.token_set_ratio`.
- **Lane 1 (Semantic Intent + Slot Extraction via Ollama, ~150-400 ms)**:
  Prompts local LLM (`llama3.2` or `qwen2.5`) to output JSON `{intent, slots, confidence}`.
- **Lane 2 (Adaptive Complex Planner, ~400-1200 ms)**:
  Triggers `AdaptivePlanner` to construct multi-node TaskGraphs.

### Current Router Strengths:
- Sub-millisecond latency on exact commands.
- Guaranteed zero LLM hallucinations on Lane 0.
- Fast, deterministic slot parsing for standard verbs.

### Current Router Weaknesses:
- Rigid lexical dependency: variations like *"could you please see what files are in downloads"* fail Lane 0 patterns and fall back to Lane 1.
- No semantic capability retrieval: Lane 1 generates an intent name from general LLM training without grounding against candidate capabilities.
- Lack of explicit Negation & Correction precedence: "Don't open Spotify, open Chrome" risks activating the first verb encountered.

---

## E. Existing Planner Behavior

`AdaptivePlanner` (`jarvis/core/planner/adaptive_planner.py`) operates as a deterministic cascade:
1. `PlanTemplateCache`: Reuses verified TaskGraphs for recurring goals.
2. `DeterministicDecomposer`: Splices 2-clause sentences (e.g. *"open Chrome and play music"*) into sequential or parallel sub-commands.
3. `ToolRetriever`: Uses BM25 keyword matching over raw tool descriptions to supply Top-12 tool schemas to the planner model.
4. `GraphValidator`: Validates Pydantic schema, acyclic topology (DAG), argument typing, and value bindings (`$node_id.output.key`).
5. `GraphOptimizer`: Deduplicates idempotent and read-only nodes.

### Current Planner Weaknesses:
- Decomposer relies on fixed conjunctions (`and`, `then`, `also`).
- Tool retriever scores raw description text rather than semantic capability keywords, preconditions, or risk tiers.
- Does not reason over dynamic capability availability (e.g., whether Android phone or WhatsApp bridge is actually connected before generating nodes).

---

## F. Existing Context / Memory Behavior

- **WorkingMemory (`jarvis/memory/working_memory.py`, `jarvis/core/memory/working.py`)**:
  Maintains bounded ring buffers of recent entities:
  - `last_app`: name of last launched/closed app.
  - `last_file`: path of last opened/searched/copied file.
  - `last_folder`: last referenced directory.
  - `last_search_results`: list of file paths from recent search.
  - `last_url`: last visited web domain.
- **ReferenceResolver (`jarvis/core/context/resolver.py`)**:
  Deterministic resolution of conversational anaphora:
  - Pronouns (*"it"*, *"that"*, *"them"*).
  - Ordinals (*"the first one"*, *"the second result"*, *"the last file"*).
  - Spatial continuity (*"same folder"*, *"that directory"*).
- **SQLiteMemoryStore (`jarvis/core/memory/store.py`)**:
  Stores long-term user facts and preferences with explicit privacy classifications.

### Current Context Weaknesses:
- The router does not resolve referents *before* intent classification; e.g., *"open it"* is routed as `open_app(name="it")` instead of `open_file(path=last_file)`.
- Working memory context is not passed into capability retrieval scoring.

---

## G. Existing Recovery Mechanisms

The execution subsystem features a multi-tiered resilience stack:
1. `MethodSelector` & `ExecutionMethod`:
   Cascade: `NATIVE` (Win32/Python) -> `POWERSHELL` -> `UIA` -> `VISION`.
2. `FailureClassifier`:
   Standardized error taxonomy: `NOT_FOUND`, `PERMISSION_DENIED`, `TIMEOUT`, `AUTH_REQUIRED`, `RESOURCE_BUSY`, `INVALID_ARGUMENT`, `VERIFICATION_FAILED`.
3. `MethodStatsTracker`:
   Tracks per-capability method success rates, EWMA latency, and quarantine state.
4. `CircuitBreaker`:
   Trips after 5 consecutive failures, backing off for 30 seconds to prevent resource exhaustion.
5. `UndoManager`:
   Reverses file moves, copies, and folder creations.

### Current Recovery Weaknesses:
- When an application is not installed (`APP_NOT_FOUND`), recovery stops instead of querying `PackageCatalog` to recommend verified installation.
- Talk-back on failure does not always explain *why* an action failed in grounded natural language.

---

## H. Existing Capability Metadata

Current metadata is restricted to `ToolDefinition`:
- `name`: str
- `description`: str
- `input_model`: type[BaseModel]
- `output_model`: type[BaseModel]
- `risk`: RiskLevel
- `idempotent`: IdempotencyClass
- `read_only`: bool
- `requires_confirmation`: bool

### Missing Metadata Needed for General Intelligence:
- `category`: CapabilityCategory
- `keywords`: list[str] (semantic anchors)
- `examples`: list[str] (positive natural language examples)
- `counterexamples`: list[str] (phrases that sound similar but belong elsewhere)
- `required_slots`: list[str]
- `optional_slots`: list[str]
- `preconditions`: list[str]
- `verifier`: str
- `recovery_methods`: list[str]
- `availability_check`: callable / str
- `cost_tier`: CostTier

---

## I. Current Hardcoded Command / Regex Dependence

1. `intents.yaml`: 54 intents with ~300 hardcoded regex patterns.
2. `router.py`: Hardcoded regexes for shell commands, system diagnostics, WhatsApp commands, and volume changes.
3. `complexity.py`: Hardcoded string patterns to identify compound clauses (`open X and play Y`).
4. `matcher.py`: Strict regex boundary matching that rejects natural phrasing variations.

---

## J. Current Generalization Weaknesses

1. **Phrasing Sensitivity**: Minor phrasing changes fail fast matching and fall back to ungrounded LLM inference.
2. **Missing Slot Guessing**: Tendency for LLMs to invent default paths or parameters when unspecified.
3. **Pronoun Blindness**: Inability to differentiate *"open it"* (file vs. app) without contextual binding.
4. **Negation Vulnerability**: Risk of executing actions when instructions contain negative constraints (*"do not delete"*).
5. **Correction Lateness**: Conversational corrections (*"no, the other one"*) treated as disconnected requests.

---

## K. Current Duplicate Systems

1. **Working Memory**: `jarvis/memory/working_memory.py` vs. `jarvis/core/memory/working.py`.
2. **App Resolution**: `jarvis/tools/system/app_resolver.py` vs. `jarvis/core/catalog/app_catalog.py`.
3. **Search Caches**: Independent hot caches in memory search, planner, and router.

---

## L. Existing Features That Must Be Reused

1. **`AppCatalog` & `PackageCatalog`**: Multi-source registry/shortcut scanner, O(1) in-memory hot path, trusted roots validation.
2. **`ToolRegistry`**: 80 hardened tools with Pydantic contracts and risk tiers.
3. **`ExecutionEngine`**: Policy evaluator, confirmation tickets, action ledger, TOCTOU snapshots, supervisor kill switch.
4. **`ReferenceResolver`**: Pronoun, ordinal, and directory reference resolution.
5. **`SearchEngine`**: FTS5 full-text indexing, SQLite WAL database, MIME extractor.
6. **`MethodStatsTracker`**: Latency and success tracking across execution methods.
7. **`PulseEngine`**: Speculative low-latency audio acknowledgments.

---

## M. Proposed Minimal Architecture Changes

To achieve general intelligence without architectural bloat or regressions:

1. **Formalize Capability Brain (`jarvis/core/capabilities/`)**:
   - `models.py`: `CapabilityDefinition`, `CapabilityCategory`, `CostTier`.
   - `registry.py`: `CapabilityRegistry` unifying all 80 tools into rich capability definitions with semantic metadata.
   - `retrieval.py`: Fast hybrid `CapabilityRetriever` (BM25 + semantic keyword ranking) returning Top-K candidates in <2 ms.
   - `verifier_map.py`: Explicit mapping of capabilities to deterministic verifiers.

2. **Enhance `SmartRouter` with Capability Grounding**:
   - Maintain Lane 0 exact regex match (<0.5 ms) for zero regression.
   - Insert Lane 0.75 Capability Retrieval: score input against `CapabilityRegistry`.
   - Implement strict Negation & Correction filters.
   - Ground Lane 1 and Lane 2 in retrieved capabilities, guaranteeing 0% tool hallucination.

3. **Pre-Route Context & Reference Binding**:
   - Query `ReferenceResolver` *before* slot assignment so pronouns and ordinals resolve into real entities.

4. **Closed-Loop Verification & Adaptive Recovery**:
   - On execution failure, feed structured `FailureClassification` into recovery alternatives (e.g. app missing -> offer winget package install).

---

## N. Benchmark & Holdout Plan

We evaluate generalization across **10 distinct dimensions**:

| Dim | Name | Target Behavior |
| :---: | :--- | :--- |
| **A** | **Canonical** | Exact commands must hit Lane 0 and pass (<1 ms). |
| **B** | **Paraphrase** | Unseen natural language phrasings must map to correct capability. |
| **C** | **Implicit** | Indirect requests (*"it's too loud"*) must trigger correct action (*`volume_down`*). |
| **D** | **Noisy / Speech** | Speech typos and phonetic slips (*"ope notpad"*) must resolve correctly. |
| **E** | **Compositional** | Multi-action sentences (*"open Chrome and search for Python docs"*) form valid DAGs. |
| **F** | **Contextual** | Pronouns and ordinals (*"find report"* -> *"open it"*) resolve to referents. |
| **G** | **Correction** | Immediate corrections (*"no, open VLC instead"*) override previous intent. |
| **H** | **Negation** | Negative constraints (*"don't delete that file"*) are strictly honored. |
| **I** | **Ambiguity** | Missing critical info (*"send email"*) prompts for clarification, never guesses. |
| **J** | **Unknown** | Out-of-domain requests (*"bake a pizza"*) politely decline without hallucinating tools. |

### Evaluation Standards:
- **Correct Capability Accuracy**: >= 95%
- **Wrong Consequential Execution**: Strictly 0.0%
- **Tool Hallucination Rate**: Strictly 0.0%
- **Fast-Path Latency**: < 1.0 ms
- **Semantic Retrieval Latency**: < 5.0 ms

---

## O. Safety Invariants

1. **Strict Hierarchy of Risk**:
   - `READ_ONLY`: Autonomous, immediate execution.
   - `REVERSIBLE`: Executed with action ledger recording and undo tracking.
   - `DESTRUCTIVE` / `EXTERNAL_EFFECT`: Strictly blocked until cryptographic confirmation ticket is approved.
2. **Zero Arbitrary Code Generation**:
   - LLMs are prohibited from emitting arbitrary shell, CMD, or Python strings.
3. **Deterministic TOCTOU Protection**:
   - All filesystem modifications snapshot path states before and after execution.
4. **Global Supervisor Kill-Switch**:
   - `global_supervisor.is_stopped()` halts all current and queued executions immediately.
5. **No Blind Hallucination of Missing Information**:
   - Required slots must be explicitly supplied, contextually resolved with HIGH confidence, or prompted to the user.
