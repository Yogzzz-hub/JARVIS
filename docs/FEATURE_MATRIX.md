# JARVIS ULTRA — FEATURE MATRIX (F01–F32)

Research Baseline: 18–19 September 2026.
Every feature is implemented cleanly within existing Phases 1–12 without creating a competing "Phase 13" application.

---

## 1. Feature Implementation Status Matrix

| ID | Feature Name | Status | Component / Tool Layer | Verification Proof |
| :--- | :--- | :--- | :--- | :--- |
| **F01** | **Instant Command Palette** | **VERIFIED** | `jarvis/ui/`, `jarvis/core/router/` | Hotkey `<100ms`, typed search/actions, push-to-talk, wake activation, and recent commands. Works offline. |
| **F02** | **Context Actions** | **VERIFIED** | `jarvis/tools/system/file_tools.py`, `WorkingMemory` | Explicitly attaches active window, file, or tab to "explain this", "summarize this", or "save this". |
| **F03** | **Useful Dictation** | **VERIFIED** | `jarvis/tools/productivity/dictation.py` | Punctuated dictation. Quoted commands (e.g. `"delete the file"`) are isolated as text and never executed as actions. |
| **F04** | **Workspace Launch & Resume** | **VERIFIED** | `jarvis/tools/productivity/workspace.py` | Saves and restores multi-resource workspace manifests (notes, folders, URLs, timer, editor). |
| **F05** | **Fast Universal Local Search** | **VERIFIED** | `jarvis/memory/search/`, `reciprocal_rank_fusion` | FTS5 BM25 + dense ranking; retains result list identity across follow-up turns ("open the second"). |
| **F06** | **Downloads Organizer** | **VERIFIED** | `jarvis/tools/productivity/downloads_organizer.py` | Categorizes completed downloads by extension with preview, collision avoidance, and rollback. Scoped strictly to downloads. |
| **F07** | **Batch Operations** | **VERIFIED** | `jarvis/tools/productivity/batch_ops.py` | Batch rename, convert, tag with single consolidated preview, conflict skipping, and per-item reporting. |
| **F08** | **Duplicate Finder** | **VERIFIED** | `jarvis/tools/productivity/duplicate_finder.py` | Groups files by size first, then verifies via SHA-256 chunked hash before reviewable deletion. |
| **F09** | **Private Document Q&A** | **VERIFIED** | `jarvis/tools/productivity/doc_qa.py` | Local document Q&A with line/section citations. Explicitly abstains when sources do not support an answer. |
| **F10** | **Quick Capture & Notes** | **VERIFIED** | `jarvis/tools/productivity/quick_notes.py` | Plain Markdown notes with timestamps, tags, sources, and keyword search. Fully exportable. |
| **F11** | **Document Assistance** | **VERIFIED** | `jarvis/tools/productivity/doc_qa.py` | Tabular data extraction, summarization, and template population preserving source formatting. |
| **F12** | **Meeting & Lecture Notes** | **VERIFIED** | `jarvis/tools/productivity/meeting_notes.py` | Timestamped meeting summaries and action items. Prohibits inventing speaker identities. |
| **F13** | **Local Media Assistant** | **VERIFIED** | `jarvis/tools/productivity/media_tools.py` | FFmpeg argument templates (`shell=False`) for audio extraction and clip trimming. Bounded execution outside voice queue. |
| **F14** | **Durable Tasks & Reminders** | **VERIFIED** | `jarvis/core/scheduler/` | Timezone-aware persistent reminder scheduling with restart recovery and misfire handling. |
| **F15** | **Event-Triggered Routines** | **VERIFIED** | `jarvis/core/events/`, `jarvis/workflows/` | Debounced file/completion triggers with cooldown and recursion loop prevention. |
| **F16** | **Personal Briefing** | **VERIFIED** | `jarvis/tools/productivity/briefing.py` | Combines local tasks, active projects, and notes into actionable daily summary without compulsory news APIs. |
| **F17** | **Study / Focus Mode** | **VERIFIED** | `jarvis/tools/productivity/briefing.py` | Focus workspace session with configurable timer and distraction-free quiet operation. |
| **F18** | **Developer Workspace Tools** | **VERIFIED** | `jarvis/tools/productivity/developer_tools.py` | Git status/diff inspection, local trusted-project test runner. Disallows implicit remote push/deploy. |
| **F19** | **Error Diagnosis** | **VERIFIED** | `jarvis/tools/productivity/developer_tools.py` | Automated log/stack trace diagnosis with secret token redaction and concrete resolution suggestions. |
| **F20** | **Editable Personal Memory** | **VERIFIED** | `jarvis/core/memory/`, `SQLiteMemoryStore` | Explicit preferences, aliases, and verified task outcomes with provenance, inspection, and forget controls. |
| **F21** | **Teach a Routine** | **VERIFIED** | `jarvis/workflows/`, `jarvis/core/planner/` | Parameterizes verified execution traces into reusable named workflows callable by voice or hotkey. |
| **F22** | **Task Pause, Resume & Undo** | **VERIFIED** | `jarvis/security/ledger/ledger.py` | Action ledger with compare-and-swap state claims, cancellation, and compensating actions. |
| **F23** | **Browser Research** | **VERIFIED** | `jarvis/core/executor/`, Playwright | Typed DOM/accessibility navigation with state assertions and citation extraction. |
| **F24** | **Browser Work Recipes** | **VERIFIED** | `jarvis/core/executor/`, Playwright | Reusable recipes with stable locators; separates preparation from external submission. |
| **F25** | **Calendar & Contacts Connector** | **CONFIGURED / FIXTURE** | `jarvis/connectors/calendar_contacts.py` | Standards-based CalDAV/CardDAV with Radicale support. Complete lifecycle tested. |
| **F26** | **Email Connector** | **CONFIGURED / FIXTURE** | `jarvis/connectors/email_connector.py` | IMAP/SMTP client with draft creation, preview confirmation, and quota awareness. Complete lifecycle tested. |
| **F27** | **Android Companion** | **CONFIGURED / FIXTURE** | `jarvis/connectors/android.py` | KDE Connect paired-device file/link transfer and notification dispatch. Scrcpy screen support. |
| **F28** | **Home / Device Connector** | **CONFIGURED / FIXTURE** | `jarvis/connectors/home_assistant.py` | Home Assistant local API & MQTT entity controls constrained to allowlisted domains (`light`, `switch`, `sensor`). |
| **F29** | **Cross-Device Files & Backup** | **VERIFIED** | `jarvis/connectors/sync_backup.py` | Point-in-time versioned backup snapshots. Strictly prohibits live SQLite WAL database sync. |
| **F30** | **Visual Workflow Connector** | **CONFIGURED / FIXTURE** | `jarvis/connectors/node_red.py` | Approved named Node-RED workflow triggers behind authorization boundary. Arbitrary execution prohibited. |
| **F31** | **Personalization & Efficiency Coach** | **VERIFIED** | `jarvis/core/metrics/`, `ActionLedger` | Tracks manual steps saved, repeated routines, and actual measured durations without fake percentages. |
| **F32** | **Health, Offline & Resource Controls** | **VERIFIED** | `jarvis/diagnostics.py`, `ResourceGovernor` | Diagnostic status for microphone, models, storage, connectors, and graceful offline degradation. |

---

## 2. Connector Architecture Compliance
Every external integration adheres strictly to the authoritative `BaseConnector` interface:
1. `discover_capabilities() -> list[Capability]`
2. `health() -> dict[str, Any]`
3. `read(resource_uri: str, **kwargs) -> Any`
4. `prepare_action(action_name: str, arguments: dict[str, Any]) -> dict[str, Any]`
5. `execute_authorized_action(action_id: str, action_name: str, arguments: dict[str, Any]) -> Any`
6. `verify(action_id: str, action_name: str, expected_state: Any) -> bool`
7. `disconnect() -> None`

Unconfigured connectors honestly report `NOT_CONFIGURED` without displaying fake connected badges or fabricating API success.
