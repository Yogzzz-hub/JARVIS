# DICTATION ROUTING & STREAMING STATE FAILURE AUDIT

**Date:** 2026-10-01  
**Target:** JARVIS EDGE — Streaming Dictation State Machine, Voice Editing & Router Integration  
**Status:** Audit & Root Cause Analysis Completed  

---

## 1. Executive Summary

Real dashboard testing revealed critical bugs where voice dictation and voice editing utterances were leaking past local dictation handling directly into the global `SmartRouter` / `JDE` / `Assistant`. This resulted in:
1. Dictation start utterances ("Start typing: ...") failing with unknown action or routing to shell commands.
2. Editing commands combined with text ("New paragraph. Add authentication...") being answered by the LLM as general programming queries instead of typing.
3. Edit instructions ("Delete the last sentence", "Capitalize the previous word") routing to `delete_file` or `open_app`.
4. Text replacements ("Replace React with Next.js") failing due to missing parameter extraction.
5. Paused resumption ("Continue from where I stopped") misrouting to `send_whatsapp_message`.

---

## 2. Failure Trace Matrix

| Test Case / Utterance | State Before Turn | Raw STT / Text | Dictation Classifier | Global Router Candidates | Selected Capability | Focus Target | Actual Action Taken | Root Cause |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. "Start typing: build a responsive React dashboard..."** | `IDLE` | "Start typing: build a responsive React dashboard with a sidebar and analytics cards." | Skipped (state was `IDLE`) | `powershell_command`, `unknown`, `assistant_chat` | `None` / `unknown` | Visual Studio Code / Notepad (or none) | Error: generic router doesn't know what action to perform | Missing initial dictation trigger pattern in router; no fallback to check for focused editable control; no target query ("Where should I type?"). |
| **2. "New paragraph. Add authentication and role-based access."** | `DICTATING` | "New paragraph. Add authentication and role-based access." | Classified as text or bypassed due to non-exact regex fullmatch | `assistant_chat`, `code_generation`, `planner` | `assistant_chat` | Notepad / Editor | JARVIS answered: "How do you want to implement authentication..." | No mixed-mode parser (EDIT_COMMAND + INSERT_TEXT); non-voice channel or partial match bypass caused utterance to reach global chat. |
| **3. "Delete the last sentence."** | `DICTATING` | "Delete the last sentence." | Bypassed or not prioritized | `delete_file`, `app.open`, `file.search` | `delete_file` (slot `path="the last sentence"`) | Text control | "file/program not found" error | Dictation state had no priority in router; `delete_file` regex intercepted "delete ..." without dictation context check. |
| **4. "Replace React with Next.js."** | `EDITING` / `DICTATING` | "Replace React with Next.js." | `VOICE_EDIT` (unhandled params) | `voice_edit`, `text_edit` | `voice_edit` (missing required action) | Text control | "Please specify the required action for voice edit." | `VoiceEditInput` schema mismatch; slot parser failed to extract `target_text="React"` and `replacement_text="Next.js"`. |
| **5. "Continue from where I stopped."** | `PAUSED` | "Continue from where I stopped." | Bypassed (classifier only handled `DICTATING`) | `send_whatsapp_message`, `reply_whatsapp_message`, `web_task` | `whatsapp_action` | Text control | Attempted WhatsApp action (CRITICAL) | `control.py` / `extended.py` matched fuzzy conversational continuations into WhatsApp; `PAUSED` dictation was not given routing priority. |
| **6. "Capitalize the previous word."** | `DICTATING` | "Capitalize the previous word." | Bypassed (only exact "capitalize that" was known) | `open_app` (slot `name="Capitalize The Previous Word"`) | `open_app` | Text control | "Capitalize The Previous Word is open." | Overly rigid pattern matching in `dictation.py` coupled with aggressive `open_app` fallback in `SmartRouter`. |

---

## 3. Structural Architectural Deficiencies

### A. Two Disconnected Dictation Abstractions
The codebase possessed two completely independent dictation implementations:
1. `jarvis/core/desktop/dictation_controller.py`: Comprehensive state machine (`DictationController`) with `FocusGuard`, `DictationState`, `DictationTarget`, and diagnostics, but **never integrated** into `SmartRouter`, `VoicePipeline`, or `CommandService`.
2. `jarvis/tools/productivity/dictation.py`: Legacy singleton `DictationSessionManager` with rigid string matching and rudimentary key combos.
`CommandService._dictation` only checked `DictationSessionManager` and only if `request.source == "voice"`, completely dropping requests from other channels or tests.

### B. Routing Hierarchy Inversion
The global routing pipeline did not respect dictation context. The required routing hierarchy:
```
GLOBAL STOP / CANCEL
        ↓
PENDING CONFIRMATION
        ↓
DICTATION CONTEXT GATE (ARMED / DICTATING / EDITING / PAUSED)
        ↓
DICTATION INTERPRETER
        ↓ (only if unconsumed / explicit escape)
Normal Router / JDE
```
Instead, utterances went through global regexes, extended WhatsApp matchers, and application discovery before ever considering dictation.

### C. Lack of Mixed Command + Text Parsing
When a user says:
*"New paragraph. Add authentication and role-based access."*
The system must decompose this into:
```json
{
  "mode": "MIXED",
  "operations": [
    { "type": "NEW_PARAGRAPH" },
    { "type": "INSERT_TEXT", "text": "Add authentication and role-based access." }
  ]
}
```
Existing code performed only single fullmatch regex checks. If the whole utterance was not an exact edit phrase, it either typed everything literally or leaked to LLM.

### D. Focus Safety & Buffer Isolation
Keystroke emissions lacked structural range tracking. A `DictationBuffer` must maintain:
- `target_window_id`, `target_control_id`
- `dictation_start_position`
- `committed_text`, `recent_committed_spans`
- `pending_partial`, `undo_stack`
Mutations must be scoped strictly to the JARVIS-owned dictated range.

### E. Capability Isolation During Active Dictation
While dictation is `ARMED`, `DICTATING`, `EDITING`, or `PAUSED`, global capability retrieval must be restricted to:
- `DICTATION`
- `TEXT_EDIT`
- `CLIPBOARD`
- `GLOBAL_STOP`
All other tool families (`WHATSAPP`, `PACKAGE`, `FILE_DELETE`, `BROWSER`, `APP_OPEN`, etc.) must be strictly masked out.

---

## 4. Remediation Plan

1. **Unified DictationController & Singleton Access**:
   Make `DictationController` the single source of truth for dictation state and link it across `SmartRouter`, `CommandService`, `VoicePipeline`, and tools.
2. **Dictation Context Gate**:
   Insert `DictationContextGate` into `SmartRouter` and `CommandService` immediately after `STOP / CANCEL` and `PENDING CONFIRMATION`.
3. **Semantic Dictation Classifier & Interpreter**:
   Classify turns into `TEXT`, `EDIT_COMMAND`, `DICTATION_CONTROL`, or `GLOBAL_EMERGENCY_COMMAND`. Support `MIXED` operations (e.g. `NEW_PARAGRAPH` + `INSERT_TEXT`) and `LITERAL` mode (`"type literally <text>"`).
4. **Structural DictationBuffer & Focus Verification**:
   Verify focus target before every keystroke; pause safely if focus is lost; support relative edits (`previous word`, `last sentence`, `replace X with Y`).
5. **Capability Masking**:
   Ensure zero leakage into WhatsApp, package managers, or file operations during active dictation.
