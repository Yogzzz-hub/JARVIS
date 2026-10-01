# Universal Operator - Architecture

How JARVIS operates the PC, the browser, the IDE and the phone: **a small set of typed, verifiable primitives**
reached through the existing pipeline. There is no second brain, no new phase, no per-sentence handler.

```
voice / text
   |  (voice: partial -> stable prefix -> LiveDictation, when dictation is on)
   v
CommandService ── SmartRouter (existing) ── operator semantic parser (verb family x object family, typed slots)
   |                                        └─ compound: every step parsed -> step list; mixed -> planner
   v
schema validation (Contract) -> policy / approval gate -> registered tool -> primitive -> verifier -> ActionLedger
                                                                                │
                                         Desktop (Win32 | Fake) · UI adapters (UIA | DOM | uiautomator | Fake)
                                         Browser backends (DevTools | keyboard | Fake) · ADB (argv-only | Fake)
```

## 1. Layers

| Layer | Module | Responsibility |
|---|---|---|
| Platform | `jarvis/core/operator/platform.py` | The only code that touches the OS: windows, foreground, state, rects, monitors, **named** chords (fixed key table), typing, clipboard (text/image/files), capture, focused-field read. `Win32Desktop` (ctypes) and `FakeDesktop` (in-memory windows + text buffer with caret/selection/undo). `wait_until` waits on observed state, never a fixed sleep. |
| References | `refs.py`, `resources.py` | Typed resources: `WindowRef`, `ControlRef`, `ClipboardResource`, `DownloadResource`, `BrowserTabRef`, `LinkRef`, plus the existing `ScreenshotResourceRef` / `MediaResourceRef`. `OperatorResources` resolves "that screenshot", "the download", "it" **by type, then recency**, mirrors into working memory, and asks when the named type was never produced. |
| Primitives | `windows.py` `ui.py` `text.py` `dictate.py` `clip.py` `screen.py` `deliver.py` `browser.py` `media.py` `watch.py` `ide.py` `device.py` | ~30 operations, each returning an `OperatorOutcome(ok, message, resource, evidence, needs, candidates)`. `needs` is `clarify` (ambiguous), `approve` (consequential), `user` (login/CAPTCHA/locked phone/secret field), `target_lost`, `vision` (no structure). |
| Tools | `jarvis/tools/system/operator_tools.py` | 11 registered tools (`window_op`, `ui_op`, `text_op`, `clipboard_op`, `screen_op`, `deliver_op`, `browser_op`, `video_op`, `watch_op`, `ide_op`, `phone_op`) with strict input contracts. A failed primitive raises (the executor records a failure); `needs=approve` raises `ApprovalNeeded`, which `CommandService` turns into the normal confirmation flow re-running **the same prepared call** with `approved=True`. |
| Routing | `jarvis/core/router/operator_intents.py` | Verb family x object family -> one capability + slots, typo repair against the operator vocabulary, mode awareness, compound splitting. Runs after control, follow-ups, meta-policy, dictation and the **negation guard**, before frame routing. Also reachable from `match_extended`, so clause splitting elsewhere sees operator steps. |

## 2. Primitive families

* **window** - `resolve` (previous / current / family "my editor" / app / title words / ordinal "second chrome") with a
  foreground **history** that excludes JARVIS's own windows; `focus`, `set_state` (max/min/restore/fullscreen),
  `arrange` (halves, quarters, centre, side-by-side, stack, quadrants, next/previous monitor), `close`. Ties without
  history ask; every effect is read back (foreground hwnd, `IsIconic/IsZoomed`, rect within 16 px).
* **ui** - one `UIResolver` for every surface. `UITarget.parse("the second Send button")` -> role/name/ordinal/near.
  Scores: exact > prefix/suffix > word > substring > fuzzy, role bonus/penalty, visibility/enabled; ties are
  questions. Adapters: `UIAWindowAdapter` (existing UIA snapshot + patterns: Invoke/Toggle/Select/Expand/Value),
  `WebUIAdapter` (fixed DOM script assigns `data-jarvis-id`), `AndroidUIAdapter` (uiautomator XML), `FakeUIAdapter`.
  Refuses password/OTP/PIN/CVV fields, pauses for CAPTCHA, asks before Pay/Delete account/Submit order.
* **text** - `insert` (focus re-checked first), `press` (named chord table only), `edit` (delete/select/copy/cut N
  chars/words/lines/sentences/paragraphs, replace X with Y nearest-before-caret or all, case changes, undo/redo),
  verified by reading the field when the platform can.
* **dictate** - see section 4.
* **clip / screen / deliver** - copy waits for the clipboard to change (probe marker), screenshots become resources,
  delivery pastes text/image/files (CF_HDROP) into a verified-foreground window or a resolved control, then looks
  for the effect (field value, attachment chip). Sending is a separate step that needs approval and is only
  reported when the composer empties.
* **browser** - one model, three backends: DevTools (a Chromium started with a debugging port and a dedicated
  persistent profile, e.g. from a shortcut; tabs via `/json/*`, page work via **named scripts only**), keyboard (owner's ordinary window;
  title is the only page signal), fake. Tabs, navigation, results as `LinkRef` ordinals, find, read (untrusted).
* **media** - the page's main `<video>` (state read back after every op), else system media keys (reported as
  unverified). Seek/time parsing (`1:30`, `2 minutes`), rate, volume, captions, full screen, skip a skippable ad.
* **watch** - one daemon thread, scoped/time-limited/cancelable watches: skip ads (only the player's own visible Skip
  button, this video only, ends when the tab changes), download finished (new non-partial file), IDE agent done.
* **ide** - Antigravity / VS Code / Cursor / Windsurf on top of window + ui + text + deliver: prompt (read back),
  send (box empties or Stop appears), attach (chip appears), accept/reject via the IDE's own buttons, Quick Open
  (title verified), palette commands (destructive ones refused), status, read reply (untrusted).
* **device** - ADB as argv lists from a fixed operation table: authorized devices only (optional serial allow-list),
  lock screen respected (only media/volume/wake/lock keys work locked), taps from the UI tree, typed text escaped,
  push verified with `ls`, allow-listed developer ops (logcat bounded, packages, battery, storage, info, open_url
  http(s) only; install/uninstall/clear data need approval).

## 3. Safety rules as code

| Rule | Where it is enforced |
|---|---|
| AI -> structured capability -> schema -> policy -> registered tool -> execution -> verification | `operator_intents` produces only tool names + typed slots; `Contract` (strict, extra=forbid) validates; `CommandService` policy/approval; `ExecutionEngine` + ledger |
| Never LLM -> arbitrary PowerShell/CMD/ADB/JS/coordinates | chords parsed against `VK_CODES`; page scripts are constants in `SCRIPTS` with JSON-encoded args; ADB argv from `KEYS`/`APPS`/`DEV_OPS`; UI acts on resolved controls |
| Vision last, candidate-first, no direct vision->click | `screen_click` runs `_structured_click` (operator UI resolver) first; a vision point is clicked only if `validate_point` finds the UI element under it matches the request and is not sensitive/consequential |
| Never bypass UAC / password / PIN / OTP / CAPTCHA / phone lock / login | `SENSITIVE` field refusal (UI, web, phone), CAPTCHA -> `needs=user`, `DeviceOperator._gate` lock check, router `_SECRET` clarify |
| Untrusted content | page text, notifications, IDE replies, clipboard returned with `evidence.untrusted`; never parsed as commands |
| Negated actions never run | negation guard precedes the operator parser; 0 executions across all scenarios' negated forms |
| Wrong action worse than clarification | resolver ties, unknown resources, missing windows, nested scopes ("option in the dropdown"), references ("the same control") all ask or plan |
| Skip-ad only via visible Skip control | `SCRIPTS["skip_ad"]` clicks only a visible element whose text says Skip; no network blocking; watch is scoped to one video URL and time-limited |
| One command id -> one final response; no fake progress | tools return what was observed; unverifiable effects say "(I can't see inside that app to confirm it.)" |

## 4. Live dictation

```
STT partial (200 ms) -> TranscriptStabilizer.stable_prefix -> LiveDictation.feed(stable)
      held:   utterance starts like a command ("delete…", "new paragraph…", "type literally…", "jarvis…")
      held:   trailing word that may become a spoken token ("question" -> "question mark", "stop" -> "stop typing")
      typed:  only words beyond what was already typed, formatted by DictationController (punctuation words, modes)
final transcript -> LiveDictation.finish(final)
      command utterance -> not consumed -> CommandService -> DictationController.execute_turn (edit/control/literal)
      dictated text     -> reconcile: erase exactly the revised words, type the rest, apply a trailing
                           "stop/pause typing" -> consumed (the command path never types it again)
```

States come from the existing `DictationController` (IDLE / ARMED / DICTATING / EDITING / PAUSED / STOPPING; "target
lost" = PAUSED with reason, words kept in its pending buffer for "continue"). Focus is checked before **every**
insertion against the controller's target window. No model call per word.

## 5. Mode awareness

The tracker's current window family (`browser`, `media`, `editor`, `ide`, `files`, `chat`) settles only implicit
objects: "go back" in a browser is page-back, "make it full screen" is the video only while one is in front,
"open the second one" needs a list in front. Explicit objects always win.

## 6. Compound commands

`_compound` splits at clause boundaries followed by a step verb (never inside typed text, never across
corrections like "no wait", never across message words). If every step parses to a LANE_0 capability the result is
a deterministic step list (no model); if an operator step is mixed with one that needs thinking, the planner gets
the request with the operator tools in its catalog. "find the wifi icon and click it" stays one located action.

## 7. What changed in existing code (reuse, not rebuild)

* `pc_quick_action` screenshot/copy/paste-to-app actions now run on clip/screen/deliver (resolved + verified
  window, observed clipboard, honest result) - same routing contract.
* `screen_click` resolves structurally first; vision proposals are validated before any click.
* Voice pipeline calls `LiveDictation` at each stable prefix and at the final transcript.
* Runtime starts the foreground-history poll (Windows) and wires watch announcements to the response engine.
* Router: operator parser step, typo vocabulary for operator words, device-noun typo repair, `check for updates`,
  `search for X` (nothing local) -> web, `open my resume` -> planner (a file, not an app).

## 8. Tests and evidence

* `jarvis/tests/test_operator_primitives.py` - observable effects on the fake desktop/browser/phone.
* `jarvis/tests/test_operator_routing.py` - scenario slice, negation, secrets, former misroutes, route -> tool ->
  effect end to end.
* `tests/operator/` - 598 semantic scenarios, surface generator, runner (dev + holdout).
* `reports/UNIVERSAL_OPERATOR_BENCHMARK.md`, `reports/UNIVERSAL_OPERATOR_REAL_ACCEPTANCE.md` (manual, real machine).
