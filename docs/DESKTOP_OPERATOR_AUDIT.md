# DESKTOP OPERATOR AUDIT — JARVIS EDGE v1.x

> Generated: 2026-09-24
> Purpose: Document existing desktop capabilities, identify gaps, duplicates,
> unsafe patterns, fixed sleeps, and plan minimal changes for the
> Voice-First Universal PC Operator upgrade.

---

## 1. EXISTING ARCHITECTURE SUMMARY

### Core Pipeline (Phases 1–12, preserved)

```
User → STT → Normalize → Router (Lane-0/1/2) → Capability Match
→ Policy → ToolRegistry → Execute → Verify → PULSE → TTS
```

| Component | Location | Status |
|---|---|---|
| SmartRouter | `jarvis/core/router/router.py` | 1440 lines, Lane-0/1/2, YAML patterns |
| CapabilityRegistry | `jarvis/core/capabilities/registry.py` | 109 registered capabilities |
| ToolRegistry | `jarvis/tools/registry.py` | 96 active tools at startup |
| PolicyEvaluator | `jarvis/security/policy/` | Risk classes, path protection |
| ConfirmationManager | `jarvis/security/confirmation/` | Ticket lifecycle |
| ActionLedger | `jarvis/security/ledger/ledger.py` | Idempotent CAS, duplicate guard |
| BoundedWorkingMemory | `jarvis/core/memory/working.py` | 21 KB, topic stack, entities |
| ReferenceResolver | `jarvis/core/context/resolver.py` | 34 KB, typed ResourceRefs |
| BrowserManager | `jarvis/core/computer/browser/manager.py` | Playwright-based |
| UIA Layer | `jarvis/core/computer/windows/` | Backend, Locator, Snapshot, Patterns, Actions |
| Vision Fallback | `jarvis/core/vision/` | Candidate-grounded, privacy filter |
| Android Client | `jarvis/tools/system/connector_tools.py` | scrcpy, LocalSend |
| RAG / FileCatalog | `jarvis/memory/search/` | Watcher, Indexer, semantic search |
| TTS | `jarvis/core/tts/` | Warm engine, streaming |
| STT | `jarvis/core/stt/` | FasterWhisper, Stabilizer, PrefixConsensus |
| PULSE | `jarvis/core/pulse/` | Concurrent feedback, earcons |
| ResponseEngine | `jarvis/core/response/engine.py` | OutcomeResponseComposer |
| VoicePipeline | `jarvis/core/audio/pipeline.py` | 31 KB, wake, VAD, PTT, barge-in |

---

## 2. EXISTING DESKTOP CAPABILITIES INVENTORY

### 2.1 Application Control

| Capability | Tool | File | Notes |
|---|---|---|---|
| `app.open` | `open_app` | `native.py:442` | Uses `AppResolver.resolve()` then `launch()` |
| `app.close` | `close_app` | `native.py:606` | `psutil.Process.terminate()` |
| `app.focus` | `bring_to_front()` | `native.py:95` | Win32 `SetForegroundWindow` with thread attach |
| `app.list_installed` | `list_installed_apps` | `app_tools.py` | AppCatalog query |
| `app.is_installed` | `is_app_installed` | `app_tools.py` | Checks catalog + winget |
| `app.find` | `find_app` | `app_tools.py` | Fuzzy name resolution |
| `app.install` | `install_software` | `app_tools.py` | winget/choco with policy |
| `app.location` | `find_app_location` | `app_tools.py` | Registry + PATH lookup |

**AppResolver / AppCatalog** (`app_resolver.py`, 307 lines):
- Discovers apps from: Registry `App Paths`, Start Menu `.lnk` files, `ALIASES` dict, `SYNONYMS` dict, `WEB_SERVICES` dict, UWP protocol URIs
- `trusted_executable()` gates discovery to safe install roots
- Fuzzy/substring matching with politeness cleanup
- **Gap**: No `app.status` (is app running?), no `app.version`, no `app.refresh_catalog` API trigger
- **Gap**: No `app.list_running` tool (only `top_memory_processes` exists)

### 2.2 Window Management

| Capability | Tool | File | Notes |
|---|---|---|---|
| `window.snap` | `snap_window` | `window_management_tools.py` | Left/right/top/bottom/corners via Win32 |
| `window.arrange` | `arrange_windows` | `window_management_tools.py` | Side-by-side, 2x2 grid |
| `window.move_resize` | `move_resize_window` | `window_management_tools.py` | MoveWindow API |
| `window.switch` | `switch_window` | `window_management_tools.py` | Alt+Tab or named switch |
| `window.close_active` | `close_active_window` | `computer_tools.py:900` | Alt+F4 |
| `window.maximize` | `maximize_window` | `computer_tools.py:920` | Win+Up |
| `window.minimize` | `minimize_window` | `computer_tools.py:940` | Win+Down |
| `window.show_desktop` | `show_desktop` | `computer_tools.py:960` | Win+D |

**WindowManager** (`windows/windows.py`, 88 lines):
- `list_windows()`, `get_active_window()`, `resolve_target_window()` with fuzzy matching

**Gaps**:
- No `window.list` exposed as user-facing tool
- No `window.current` tool
- No `window.restore` separate tool
- No `window.minimize_all_except` compound capability
- **Duplicate**: `close_active_window` (Alt+F4) vs `close_app` (process terminate) — different mechanisms

### 2.3 UI Automation (UIA)

| Component | File | Lines | Description |
|---|---|---|---|
| `WindowsUIABackend` | `windows/backend.py` | 114 | Win32 + uiautomation bridge |
| `UIASnapshotBuilder` | `windows/snapshot.py` | 145 | Bounded tree traversal (500 elements, depth 8) |
| `UIALocator` | `windows/locator.py` | 122 | Priority: AutomationId, Name, Substring, Fuzzy |
| `UIAPatterns` | `windows/patterns.py` | 89 | Invoke, SetValue, Toggle, Select, Expand, Collapse |
| `WindowsActionRunner` | `windows/actions.py` | 250 | `invoke()`, `click()`, `set_value()`, `toggle()` |
| `InteractionController` | `interaction/controller.py` | 78 | Bounded loop (12 steps), preconditions |
| `UIVerifier` | `computer/verifier.py` | ~100 | State hash comparison |
| App Adapters | `windows/adapters/` | Notepad, Settings | Minimal |

**Exposed as tools**:
- `desktop_ui_snapshot` in `computer_tools.py:351`
- `desktop_ui_click` in `computer_tools.py:414`

**Supported UIA patterns**: Invoke, Value, Toggle, SelectionItem, ExpandCollapse

**Gaps**:
- No `ui.find`, `ui.read`, `ui.focus`, `ui.scroll`, `ui.get_state`, `ui.expand`, `ui.collapse`, `ui.select`, `ui.set_value` exposed as individual tools
- Missing patterns: ScrollPattern, RangeValuePattern, TextPattern
- No semantic role-based targeting from voice

### 2.4 Keyboard & Input

| Capability | Tool | File |
|---|---|---|
| `keyboard.shortcut` | `keyboard_shortcut` | `keyboard_tools.py` |
| `keyboard.type` (dictation) | `dictation` | `dictation.py` |

**DUPLICATE**: Three copies of `_send_key`, `_send_combo`, `_type_unicode` across `dictation.py`, `ide_tools.py`, `keyboard_tools.py`.

**Gaps**: No `mouse.click/scroll/drag`, no generalized `keyboard.type` tool, no large-text clipboard-paste tool.

### 2.5 Clipboard

| Capability | Tool | File |
|---|---|---|
| `clipboard.read` | `clipboard_intelligence` | `keyboard_tools.py` |
| `clipboard.copy` | `clipboard_intelligence` | `keyboard_tools.py` |
| `clipboard.paste` | `clipboard_intelligence` | `keyboard_tools.py` |
| `clipboard.act` | `clipboard_intelligence` | `keyboard_tools.py` |

**Gaps**: No `clipboard.watch`, no `clipboard.set_text` without paste.

### 2.6 Screenshot / Screen

| Capability | Tool | File |
|---|---|---|
| `screen.capture` | `take_screenshot` | `native.py:467` |
| IDE screenshot | `antigravity_ide_control` | `ide_tools.py:201` |

**Gaps**:
- **No `ScreenshotResourceRef`** — screenshots not tracked as ResourceRefs
- No `screen.capture_window`, `screen.capture_region`, `screen.latest`, `screen.describe`
- No screenshot metadata (capture_time, source_window, dimensions, hash)

### 2.7 Dictation System

| Component | Location | Status |
|---|---|---|
| `DictationTool` | `dictation.py:320` | Formats and types text |
| `VoiceEditTool` | `dictation.py:385` | backspace, word, sentence, undo, redo, replace, capitalize |
| `DictationModeControlTool` | `dictation.py:460` | start/stop/toggle |
| `DictationSessionManager` | `dictation.py:500` | Live delta typing, stable-partial revision |
| `format_dictation()` | `dictation.py:170` | Spoken punctuation conversion |
| `apply_spelling_mode()` | `dictation.py:205` | Spelled letter sequences |
| `apply_number_mode()` | `dictation.py:220` | Spoken number words to digits |
| `STT Stabilizer` | `core/stt/stabilizer.py` | PrefixConsensus across hypotheses |

**Gaps**:
- **No DictationController state machine** (IDLE/ARMED/DICTATING/EDITING/PAUSED/STOPPING)
- **No DictationTarget tracking** (app, window, control, focus state)
- **No focus verification before commit** — types into whatever is focused
- **No focus-loss detection/pause**
- **No real-time command vs dictation classifier** during active dictation
- **No code dictation mode**
- No "type literally" escape phrase
- Stable-partial path does NOT bypass router (adds latency)

### 2.8 Browser Automation

**Exposed tools**: `browser_navigate`, `browser_click`, `browser_type`, `browser_snapshot`, `play_youtube`

**Gaps**: No `browser.search/back/forward/refresh/new_tab/close_tab/switch_tab/download/upload/read/extract/find` tools. No `FileResource` on download. No `MediaResource` for YouTube.

### 2.9 IDE / Antigravity

**Supported actions**: open, focus, type_prompt, submit_prompt, save_file, switch_tab, open_file, open_terminal, open_problems, source_control, explain_error, ide_screenshot

**Gaps**: No task monitoring, no attachment capability, no project.open/search, no UIA fallback.

### 2.10 Context / Resources

**Existing types**: FileResourceRef, FolderResourceRef, ApplicationResourceRef, PackageResourceRef, BrowserPageRef, ContactResourceRef, DeviceResourceRef, DraftResourceRef, SearchResultRef, ResultSet, UIResourceRef

**Missing types**: ScreenshotResourceRef, MediaResourceRef, ThreadResourceRef, ErrorResourceRef, TextResourceRef

---

## 3. DUPLICATE CODE

| Pattern | Locations | Action |
|---|---|---|
| `_send_key()` | `dictation.py:33`, `ide_tools.py:30`, `keyboard_tools.py` | Consolidate to `input_layer.py` |
| `_send_combo()` | `dictation.py:43`, `ide_tools.py:38`, `keyboard_tools.py` | Consolidate to `input_layer.py` |
| `_type_unicode()` | `dictation.py:57`, `ide_tools.py:50` | Consolidate to `input_layer.py` |
| VK constants | 3 files | Consolidate to `input_layer.py` |
| Desktop attach | `native.py:81`, `native.py:100`, `native.py:470` | Single helper |

---

## 4. FIXED SLEEPS (JARVIS source, HIGH risk)

| File | Line | Sleep | Purpose | Risk |
|---|---|---|---|---|
| `native.py` | 253 | `0.5s` | After app launch | **HIGH** — poll for window |
| `native.py` | 263 | `0.4s` | After focus attempt | MEDIUM — verify focus |
| `native.py` | 281 | `0.3s` | After ShellExecute | **HIGH** — poll |
| `native.py` | 297 | `0.5s` | After subprocess launch | **HIGH** — poll |
| `native.py` | 312,321,327 | `0.3s` | Various launch settles | MEDIUM |
| `controller.py` | 322 | `0.4s` | UI animation settle | MEDIUM |
| `ide_tools.py` | 129-169 | `0.05s` | Between keystrokes | LOW |
| `keyboard_tools.py` | 78-278 | `0.03-0.08s` | Key/clipboard settle | LOW |
| `actions.py` | 125-201 | `0.05s` | UIA pattern settle | LOW |

---

## 5. UNSAFE PATTERNS

| Pattern | Location | Severity |
|---|---|---|
| Raw PowerShell execution | `computer_tools.py:35` | CRITICAL — restrict to templates |
| No focus verification in dictation | `dictation.py` | HIGH |
| No ScreenshotResource tracking | `native.py:467` | MEDIUM |
| `bring_to_front` 160-line monolith | `native.py:95` | MEDIUM — refactor |

---

## 6. PLANNED IMPLEMENTATION ORDER

### Phase A: Foundation
1. Create `jarvis/tools/system/input_layer.py` — consolidated input
2. Extend UIA tool suite (`ui.find`, `ui.read`, `ui.focus`, `ui.scroll` etc)
3. Create focus verification layer (`FocusGuard`)

### Phase B: DictationController + Streaming
4. DictationController state machine with DictationTarget
5. Live streaming dictation path (bypass router for stable tokens)

### Phase C: Resources + Context
6. ScreenshotResourceRef with metadata
7. MediaResourceRef for playback context
8. Attachment pipeline (file.attach capability)

### Phase D: Browser + System Extensions
9. Browser tool extensions (back, forward, tab mgmt, download, upload)
10. System inspection extensions (cpu, memory, disk, gpu, processes)

### Phase E: Verification + Diagnostics
11. Replace fixed sleeps with polling
12. Desktop Operator Diagnostics logging

---

## 7. WHAT IS NOT CHANGED

- Router architecture (Lane-0/1/2)
- Planner (adaptive_planner, decomposer, validator)
- PolicyEvaluator, ConfirmationManager, ActionLedger
- BoundedWorkingMemory, ReferenceResolver (extended only)
- BrowserManager (extended only)
- VoicePipeline (extended only)
- TTS, STT engines, PULSE engine
- RAG / FileCatalog, Vision fallback
- Android client, WhatsApp Baileys bridge
- ResponseEngine / OutcomeResponseComposer