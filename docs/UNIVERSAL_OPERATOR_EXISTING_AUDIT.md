# Universal Operator — audit of what already exists

Scope: everything JARVIS EDGE uses to operate Windows, browsers, media, editors, the IDE, files, the clipboard,
screenshots and an Android phone. Read from the code on `main` (commit `ec7bf64`). Classification:

- **WORKING**: does the job, used by the live command path, has tests
- **PARTIAL**: works for some cases or only one path; gaps listed
- **BROKEN**: violates a stated requirement or does not do what it claims
- **MISSING**: no implementation
- **DUPLICATED**: two implementations of the same responsibility

## Summary

| Area | State | One-line verdict |
|---|---|---|
| Command path (CommandService → Router/JDE → ToolRegistry → Policy → Executor → Verifier → PULSE) | WORKING | Keep as is; every new primitive plugs in here |
| AppCatalog / alias / executable resolver | WORKING | Open/close/find/install apps by name, fuzzy and aliases |
| Window control (close, max, min, snap, move, other monitor, switch by title) | PARTIAL | Active window only; no `WindowRef`, no history, no fullscreen state, no "send behind" |
| Window history (previous / recent foreground windows) | MISSING | "go back to the app I was using" is Alt+Tab, not tracked |
| Windows UIA engine (`core/computer/windows`) | PARTIAL | Good strict locator + patterns; only `desktop_ui_snapshot`/`desktop_ui_click` use it; no ordinal/relative targeting, no Value/Text/Scroll/RangeValue/Selection verbs exposed |
| Unified UI target resolver (desktop + browser + Android) | MISSING | Three separate resolvers (`UIALocator`, `BrowserLocatorResolver`, Android `tap_text`) with different contracts |
| Keyboard / text input (`input_layer`, `keyboard_tools`) | WORKING | Unicode typing, combos, focus verification helper |
| Dictation | DUPLICATED + PARTIAL | `DictationController` (state machine, FocusGuard) and `DictationSessionManager` (typing, edits) both live; **words are typed only after the utterance ends** — `type_streaming_delta` exists but the voice pipeline never calls it |
| Focus guard (wrong-app typing protection) | WORKING | `FocusGuard` checks hwnd/process before typing; used by the controller path only |
| Clipboard | PARTIAL | Text read/copy/paste + "act on selection"; screenshot→clipboard; no image read, no restore, no `ClipboardResource` |
| Screenshot | PARTIAL | Full screen or active window to PNG; result not recorded as a `ScreenshotResource`, so "paste that screenshot" cannot resolve "that" |
| Browser — user's own Chrome/Edge | PARTIAL | Keyboard primitives (new/close/next tab, back, refresh, zoom, find, address bar, scroll) work on any browser; **no DOM access**, so "click the second result" is impossible there |
| Browser — JARVIS-managed Playwright browser | WORKING (isolated) | Separate profile window: semantic locators, snapshot, click/fill/check, downloads, uploads, web agent. Not the browser the owner opened with "open Chrome" → **split brain** |
| Browser downloads as `FileResource` | PARTIAL | Managed browser only; not recorded in context |
| Uploads / attachments | PARTIAL | Managed browser `input[type=file]` only; no desktop file-dialog adapter; no "attachment appeared" verification for IDE/chat apps |
| YouTube / media | PARTIAL | `play_youtube` by URL, media keys (play/pause/next/prev/mute); no seek, speed, captions, fullscreen as typed media verbs; no `MediaResource` |
| Skip-ad watcher | MISSING | — |
| Generic watchers (download done, dialog appears, IDE finished, window appears) | MISSING | Only ad-hoc polling inside individual tools |
| Screen understanding | PARTIAL | `describe_screen` goes straight to the vision model; structured text from UIA/DOM is not tried first |
| Vision grounding | BROKEN (by spec) | `screen_click` / `computer_task` click raw coordinates returned by the vision model with no candidate validation (requirement 50: never vision → click) |
| File management + FileCatalog/RAG | WORKING | Find (FTS + semantic), open, metadata, copy/move/rename, delete to Recycle Bin, duplicates, knowledge search; destructive steps confirmed |
| File context ("open the second one", "its folder") | PARTIAL | `ResultSet`, ordinal and folder follow-ups work for search results; screenshots/downloads/attachments are not resources yet |
| Typed context resources (`core/context/models.py`) | PARTIAL | Rich types exist (`ScreenshotResourceRef`, `MediaResourceRef`, `BrowserPageRef`, `DeviceResourceRef`, `TextResourceRef`, `SearchResultRef`…) but **tools never create them** (0 producers for 6 of 8 types) |
| Antigravity / IDE adapter (`ide_tools`) | BROKEN (by spec) | Blind shortcuts (`Ctrl+L`, Enter) that report SUCCESS whether or not the IDE had focus; no attach, no tab switch by name, no completion wait, no prompt verification |
| Workflows / cross-app composition | PARTIAL | Planner/DAG composes tools; multi-step router splits simple chains; resources do not flow between steps by type |
| Android — ADB/scrcpy connector | WORKING | Connect (USB/Wi-Fi), apps, keys, input text, tap by visible text (uiautomator dump), screenshot, notifications (dumpsys), toggles, push/pull files, mirroring |
| Android — thin client / accessibility / NotificationListener | MISSING | `AndroidCompanionConnector` is a stub; phone UI control is ADB-only |
| Phone semantic UI (lists, fields, checkboxes, scroll targets) | PARTIAL | Text-based tap only |
| PC ↔ phone files | WORKING | ADB push/pull + LocalSend; uncertain resend prevented by the ledger |
| Phone development (APK install/launch/logs) | MISSING | No registered parameterized ADB dev capabilities |
| System status / power | WORKING | Volume, brightness, battery, network, CPU/RAM/GPU (introspection), lock/sleep/restart/shutdown behind confirmation |
| Task / process awareness | WORKING | Phase-1 runtime introspection, scoped cancel, real step progress |
| Policy, ActionLedger, confirmation tickets, prompt-injection quarantine | WORKING | Keep; every new primitive declares a risk class |
| Voice: talk-over, live partials, early route preview | WORKING | Partials and a stable prefix are produced every 200 ms — the raw material live dictation needs |
| Capability metadata (preconditions, postconditions, counterexamples, latency) | PARTIAL | `CapabilityRegistry` has description/examples/risk; no postconditions, counterexamples or latency estimate |

## Foundational defects (fix before adding behaviors)

1. **Live dictation is not live.** Partials stop at the UI. Fix: feed `stable_prefix` deltas from the voice pipeline
   into one dictation session (FocusGuard-checked) while the user is still speaking.
2. **Two dictation systems.** Keep `DictationController` (state machine + FocusGuard) as the owner; move the typing,
   formatting and edit primitives from `DictationSessionManager` behind it.
3. **Two browsers.** "Open Chrome" opens the owner's browser; semantic DOM control only works in JARVIS's isolated
   window. Fix: one *operated browser* — the owner's Chrome/Edge started with a local DevTools port (or attached when
   already running with one) and driven over CDP by the existing Playwright code; keyboard primitives stay as the
   fallback when no DevTools port is available.
4. **Resources are never produced.** Screenshots, downloads, media sessions, pages, clipboard and attachments must
   become typed resources in working memory so "that", "it", "the second one" resolve by type.
5. **Unverified success.** IDE actions and some window actions report success without checking focus or result.
6. **Ungrounded vision clicks.** Vision may propose candidates; JARVIS must validate (window, generation, UIA hit
   test) before any pointer action.

## The primitives that unlock 500+ behaviors

About 30 parameterized primitives, each a registered tool with a typed schema, risk class and verifier. User-level
behaviors in the capability catalog are compositions of these.

| # | Primitive | Signature (typed) | Notes |
|---|---|---|---|
| 1 | `window.target` | `(app?, title?, ordinal?, history: current\|previous\|recent[n]) → WindowRef` | Needs window-history tracker |
| 2 | `window.set_state` | `(WindowRef, MAXIMIZED\|MINIMIZED\|RESTORED\|FULLSCREEN\|NORMAL)` | Fullscreen via app-appropriate key, verified by rect |
| 3 | `window.arrange` | `(WindowRef, snap left/right/top/bottom/quadrant, monitor next/prev, move/resize, z-order front/back)` | Merges snap / move / switch tools |
| 4 | `window.focus` | `(WindowRef)` | Verified foreground |
| 5 | `app.open / app.close` | existing | Return `ApplicationRef` + `WindowRef` |
| 6 | `ui.find` | `(scope: WindowRef\|Page\|Device, role?, name?, ordinal?, near?, state?) → ControlRef[]` | **UITargetResolver** with adapters |
| 7 | `ui.invoke` | `(ControlRef)` | Invoke / click / select / toggle by pattern |
| 8 | `ui.set_value` | `(ControlRef, value)` | Value pattern / fill / Android set text |
| 9 | `ui.read` | `(ControlRef\|scope) → text` | Text pattern / DOM text / accessibility text |
| 10 | `ui.scroll` | `(scope, direction, amount\|to: top\|bottom\|ControlRef)` | |
| 11 | `text.insert` | `(EditableControlRef?, text, literal)` | Focus-verified; default = current focus |
| 12 | `text.edit` | `(op: delete/select/move/case/replace, unit: char/word/sentence/line/paragraph/all, n, find?, replace?)` | One primitive for every dictation edit |
| 13 | `key.chord` | `(registered chord name)` | Registry of named chords only; no free-form keys from a model |
| 14 | `dictation.session` | `(start(target) / pause / resume / stop)` + live delta feed | Owns live typing |
| 15 | `clipboard.get / set` | `(text\|image\|file list) ↔ ClipboardResource` | Save + restore around pastes |
| 16 | `screen.capture` | `(display\|window\|region\|WindowRef) → ScreenshotResource` | Recorded in context |
| 17 | `screen.read` | `(scope) → structured text` | UIA/DOM first, vision only for pixels |
| 18 | `resource.deliver` | `(Resource, to: ControlRef\|app\|chat\|device, mode: paste\|attach\|upload\|send)` | Paste, attach, upload, phone transfer — one verb, adapters decide |
| 19 | `browser.attach` | `(browser?) → BrowserRef` | DevTools attach to the owner's browser, keyboard fallback |
| 20 | `browser.navigate` | `(url\|search query\|back\|forward\|reload\|home\|stop)` | |
| 21 | `browser.tab` | `(op: new/close/switch/next/prev/find/reopen/duplicate, ordinal?, title?)` | |
| 22 | `browser.page` | `(op: find_text/zoom/fullscreen/scroll/print/save)` | |
| 23 | `browser.results` | `(page) → ResultSet<LinkRef>` | Search results / video results become a result set → "open the third one" |
| 24 | `media.control` | `(MediaResource, op: play/pause/seek/speed/captions/fullscreen/mute/volume/next/prev)` | DOM media element first, media keys fallback |
| 25 | `watch` | `(condition: control appears/enabled, download done, window appears, file created, generation done, device connected; scope; timeout) → event` | Skip-ad = `watch(control "Skip" visible+enabled in MediaResource page) → ui.invoke` |
| 26 | `file.*` | existing find/open/copy/move/rename/delete/reveal | Return `FileResource`/`ResultSet` |
| 27 | `ide.*` | `(open project/file/tab, focus pane, prompt set/send/cancel/wait, read problems/terminal)` on top of 6–18 | Verified, no blind Enter |
| 28 | `device.ui.*` | `ui.find/invoke/set_value/scroll` via the Android adapter | ADB uiautomator now; accessibility client later |
| 29 | `device.app / device.key / device.media / device.notification` | existing ADB actions, typed | |
| 30 | `device.dev.*` | `(install/uninstall/launch/stop/clear-data/logs) for an allow-listed package` | Parameterized ADB, confirmation for data loss |

Context types produced by these primitives: `WindowRef`, `ControlRef`, `EditableControlRef`, `BrowserTabRef`,
`ScreenshotResource`, `ClipboardResource`, `MediaResource`, `DownloadResource`, `FileResource`, `DeviceResource`,
`ProjectResource` — all as `BaseResourceRef` subclasses in the existing `core/context/models.py`.

## Order of work

1. Window history + `window.target/set_state/arrange/focus` (1–5)
2. `UITargetResolver` + `ui.*` (6–10) over the existing UIA locator and Playwright resolver
3. `text.insert/text.edit/key.chord` (11–13)
4. Live dictation: one `DictationController`, live deltas from the pipeline (14)
5. Clipboard + screenshot resources (15–16), `screen.read` structured-first (17)
6. `resource.deliver` (18)
7. Browser attach over DevTools + tab/page/results primitives (19–23)
8. Media + watchers + skip-ad (24–25)
9. Files and result sets as resources (26)
10. IDE adapter rebuilt on 6–18 (27)
11. Android typed UI + dev capabilities (28–30)
12. Vision demoted to a candidate proposer behind validation
13. Capability catalog (600+ behaviors as compositions), acceptance matrix, benchmark, real-device acceptance
