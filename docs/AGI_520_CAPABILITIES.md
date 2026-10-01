# AGI-520: 520 capabilities on the existing JARVIS architecture

The 520-capability spec (`tests/agi/capabilities_520.md`, copied verbatim) lists commands across ten families: PC apps
and windows, browser, files and knowledge, text and live dictation, IDE, Android phone, cross-device, communication,
system and workflows, and agentic behaviour. This document records what was built, how it stays safe, and how it was
measured - including the honest first-run numbers on the frozen holdout.

No second AI brain was added. Every capability goes through the existing path:

```
STOP / CANCEL gate (control) -> L0 router (rules, operator + capability parsers) -> JDE -> context / resource refs
  -> capability retrieval -> planner only when needed -> TaskScopeManager grant -> policy / confirmation tickets
  -> registered tool -> execute -> verify -> ActionLedger -> UI / TTS -> grant revoked
```

## 1. What is new

### Task-scoped capabilities (`jarvis/core/tasks/scope.py`)

Each command gets a grant listing only the tools its route or validated plan needs. The executor refuses any other
tool while that grant is active (`ToolResult(success=False, evidence={"scope_denied": True})`), and the grant is
revoked when the command's single final response is produced.

- `CommandService.handle` opens the grant. Each routed tool is added just before it executes. A validated plan adds
  exactly its nodes' tools.
- The agent loop extends the grant with its retrieved working set, never the whole registry.
- Nested grants can only narrow the outer grant, never widen it.
- Grants travel with asyncio context, so DAG steps inherit them.
- Watch follow-ups and workflow steps are re-dispatched with an **empty** context, so each one gets its own route,
  policy check and grant. They never inherit a stale grant.
- Reading JARVIS's own state is always allowed: `task_status`, `previous_outcome`, `recent_actions`,
  `jarvis_availability` and `get_time`.

### Task control (`control.py`, `introspection.py`, `tasks/manager.py`, `executor/engine.py`)

- *"Stop everything you're doing"* cancels every task, watch, running workflow and live dictation. The microphone
  listener stays on.
- *"Pause after the current verified step"* clears the task's `run_gate`. The step in progress finishes, and the
  next step waits.
- *"Continue from where it safely stopped"* sets the gate again.
- Phrasing such as *"cancel the PC background task from my phone"* is scoped (background or foreground). Where the
  owner says it from is not part of the request.

### New primitives and tools

| Tool | New actions |
|---|---|
| `window_op` | resize, move to the other side, next monitor, list, active, find a minimised/buried window, info, save/restore a named layout (`jarvis/db/window_layouts.json`, metadata only) |
| `ui_op` | select an option, set a slider, expand/collapse, menu path, modal check, explain why a control is disabled, focus / next field, clear, copy a field, remove an attachment chip (never deletes a file) |
| `text_op` | caret moves, word count, find, append/prepend, clear, save, save as (dialog verified, replace prompts go to the owner), paste as plain text, named templates (`jarvis/db/text_templates.json`) |
| `browser_op` | duplicate tab, stop loading, url/title, copy url, jump to/read a heading, site search, official docs, login/CAPTCHA detection, open a link by name, upload via the page's file input (never submits), download |
| `file_op` (new) | type/size/age filters, reveal in Explorer, open folder, copy path, duplicate, open with an app, open newest, find a moved file again, verify a move/delete, restore from the Recycle Bin |
| `ide_op` | file tabs, focus panels (editor, AI prompt, terminal, problems, explorer, source control), cancel generation, read/copy the response, definition/references, F2 rename (undoable), format, save/save all, list/remove attachments, docs for a symbol, read/copy the current error, open a recent project, symbol/text search |
| `phone_op` | recents, previous app, settings pages, media volume %, media state, current app, relaunch, installed?, UI tree, read the screen, find/focus/clear a control, swipe, filtered notifications, open/dismiss a notification, RAM/storage/online, pull today's/latest screenshots, open a PC page on the phone and the phone's page on the PC (Chrome's own debugging socket), screen recording, app logs, heads-up notification, did a file really arrive |
| `watch_op` | `when`: conditional watches - control enabled/appears, window opened/closed, file/PDF appears, download done, phone online, battery thresholds (PC or phone), page changed, IDE done, task/build done or failed (fail-only ends silently on success), CAPTCHA solved; optional phone notification; the owner's own follow-up (`then`) is re-dispatched through CommandService |
| `system_op` (new) | measured CPU/RAM/GPU/disk/network/uptime/battery, local Ollama models (list, loaded, unload, warm), audio devices (switching opens Sound settings - there is no supported API, and it says so), capability audit of the active and recent grants |
| `workflow_op` (new) | owner-authored workflows (`jarvis/db/workflows.json`): create (from given steps or the last successful commands), preview (dry run), run, clone, enable/disable, schedule (`weekdays 08:30`, `every 30 minutes`, "every morning except weekends"), cancel schedule, one-run folder override |

### Workflow and watch execution

- Steps run one at a time. A run stops at the first step that ends FAILED, CANCELLED, UNCERTAIN or waiting for the
  owner. Nothing is retried blindly.
- Every step is the owner's own command text, routed and policy-checked as if said fresh. A workflow can never do
  something the owner could not have asked for directly.
- A conditional watch never runs its action early. On timeout, nothing runs.

## 2. Router: the capability layer (`jarvis/core/router/capability_intents.py`)

A second operator layer, tried before the first one. It uses the same rule: the **object family** picks the
capability and the **verb family** picks the action. References ("this", "that", "its", "the current") are left for
the tool to resolve against the screen or resource memory. No sentence is special-cased.

Families are tried in this order:

1. conditions and watches, so "when X, open it" never opens anything now;
2. branch and parallel requests, which go to the planner;
3. device references, which are asked about;
4. messages, workflows, system state, phone, IDE, files, browser, text, controls and windows.

Generic fixes found while doing this:

- **Operator parser casing.** The parser received mixed-case text, and its patterns are lower case. Any capitalised
  word ("Press Continue.") silently fell through to other routes. The parser now lower-cases its input and keeps the
  owner's casing for typed text.
- **Typo repair and inflections.** Repair no longer turns an inflection into another word ("deleted" → "delete",
  "paragraph" → "paragraphs").
- **Standing rules.** Conditional policies are kept as rules: *"pause if I leave this editor"*, *"use vision only if
  UIA can't find it"*, *"hold replies about payments"*. A condition JARVIS can observe, with an action verb, is a
  watch instead: *"continue the transfer when my phone reconnects"*.
- **Read-only actions.** Questions may route to operator actions that only look (`is_read_action`). Actions that
  change something still need an imperative.
- **Introspection.** The phone's RAM is the phone's state, not this PC's. *"What exactly failed?"* is a question about
  the previous outcome.
- **Pre-normalisation.** Em-dashes become commas ("Use Chrome—actually Edge"). A trailing *"on my PC"* is dropped for
  imperative commands.
- **Deliberate planner decisions.** A branch or parallel request that was sent to the planner on purpose is not
  re-parsed by the "remark, command" rule.

## 3. Safety

| Guard | Where |
|---|---|
| A consequential tool needs a verb of its own family in the request ("shrink this window" never closes it; "minimse the window" is asked about) | `targets.missing_consequential_verb` |
| A pronoun is not a message ("send that to Arun" → *what should I send?*) | `router._check_recipient` |
| A described device or "do this on my phone" with nothing named → a question | `capability_intents._device_refs` |
| "rename/move/delete this *symbol/line/…*" (not a file) → a question | `targets.check_target` (FILE_CHANGE_INTENTS) |
| A verb is never part of an app name ("stop test app" never closes an app called "stop test"); punctuation is not an app | `targets.check_target` (APP_INTENTS) |
| Copied text is not a file to push | `targets.check_target` → `localsend_text` |
| A file or page reference is not an app to open on the phone | `targets.check_target` (`android_open_app`) |
| Phone checks pass only validated, fixed paths to `adb shell`; names never reach a shell | `DeviceOperator.has_file` / `notify` |
| Installs, uninstalls and clearing app data on the phone need approval; unknown dev ops are refused | `DeviceOperator.dev` |
| Consequential buttons (submit, confirm, send, pay, delete, install, …) need approval when clicked | `computer_use` / `ui.UIOperator.invoke` |
| IDE palette commands that remove, reset or run text are refused | `IDEOperator.command` |
| Content (pages, notifications, IDE output, window titles, logs) is returned as `untrusted` data | evidence flags |
| No lock-screen, PIN, OTP, UAC or CAPTCHA bypass: the phone must be unlocked by the owner, and CAPTCHAs are handed to the owner | `DeviceOperator._gate`, browser `login_state`, standing rule `captcha` |

## 4. Measurement

`python -m tests.agi.runner [--split dev|holdout|all] [--fails] [--json out.json]` routes every row through the real
router with **no AI model**, so the numbers measure deterministic understanding only.

- **Expectations.** `tests/agi/expectations.txt` holds the acceptable outcome tokens for every row. It was frozen
  (`FROZEN.sha256`) in its own commit **before any router work**.
- **Dev split.** The spec's own example for each row, plus generated surface forms: polite, wake word, hesitant,
  typo, and so on.
- **Holdout split.** One paraphrase per row, written and frozen with the expectations, plus generated holdout forms.
  It was not looked at while building the parsers.
- **Negation.** "don't <example>" must never run a tool. From this round, questions are skipped: "don't what's my
  battery?" is not a command.
- **Critical.** A failed row routed to a consequential tool in an executing lane.

| Measure | Before | First run on the frozen holdout | After the safety fixes below |
|---|---|---|---|
| dev canonical (spec examples) | 280/520 (53.8%) | 502/520 (96.5%) | 500/520 (96.2%) |
| dev, all surface forms | 52.4% | 91.4% | 91.0% |
| **holdout paraphrases** | 239/520 (46.0%) | **375/520 (72.1%)** | 379/520 (72.9%) |
| holdout, all forms | 44.5% | 68.8% | 69.6% |
| critical wrong consequential (all splits) | 181 | 29 | **0** |
| negated example executed | 15 of 460 | 2 of 408 | 2 of 408 |
| routing p50 / p95 (ms, no model) | 20.9 / 36.5 | 18.6 / 34.0 | 18.3 / 32.5 |

The first holdout run surfaced **29 critical routes**, from five distinct requests:

- "shrink this window a bit" and "minimse the window" went to `close_window`;
- "open the settings page for this app" went to phone settings while on the PC;
- "put the copied text onto my phone" went to `android_push_file`;
- "get the text I copied on my phone" went to `localsend_text` with the whole command as the message.

These were fixed with the generic guards in section 3, not with sentence rules. After that, the holdout is **no
longer blind**: the right-hand column is reported for safety tracking only. The first-run column is the
generalisation number.

The two remaining negation cases:

- "don't The app updated; find the new executable." is malformed. It routes to a read-only application rescan.
- "don't keep replies concise for this session" is itself a valid reply-style policy.

Neither changes anything on the PC or phone.

### Remaining differences, by design

- **"Open Wi-Fi / Bluetooth / display settings" without "phone".** These open the PC's settings. The spec lists them
  under Android, but on a PC with no phone mentioned the PC is the honest default.
- **Phone-surface wording with no phone named or in front** ("focus the message box", "tap Continue", "clear this
  textbox", "what controls are visible?"). These act on the PC window in front. With a phone session in front, the
  same words go to the phone.
- **"How much storage is free?"** reports the PC disk. "...on my phone" reports the phone.
- **"Unload the vision model when you're done"** is kept as a standing rule, applied after the current task, instead
  of unloading now.
- **"What's this error?"** with no IDE in front reads the screen (`describe_screen`). In the IDE it reads the
  Problems panel.

### Regression checks (same machine, no model)

- **Operator suite (`tests.operator.runner`).** Identical failure list to before (0 new). Negated actions executed: 0.
- **Phase suites.** dev 88 → 84 failures, blind 27 → 23, blind-2…6 unchanged or better.
- **Generalisation file.** 39 → 43 failures. All four are "Click the Submit button."-style requests that now route
  to `screen_click` (approval-gated) instead of a clarification. Before, only the capitalised spelling clarified,
  because of the casing bug; the lower-case spelling already clicked.
- **pytest.** No new failures; only the failures already present on `main`.
- **`jarvis/tests/test_agi_capabilities.py`.** 49 tests: scope grants (nesting, asyncio, executor gate),
  pause/resume, conditional watches (no early action, silent end, timeout), workflows (order, stop on failure,
  preview, override, reference, schedule), file and phone primitives (no shell injection), system status, router
  routes and safety questions.

## 5. Not verified on real hardware

Everything above was exercised against the in-memory desktop, browser and phone fakes and the real router. These
still need a real Windows PC and a real Android phone before they can be called done:

- UIA patterns: selection, range and expand/collapse.
- Save-as dialogs.
- Chrome's DevTools file upload.
- `cmd notification post`, and Chrome remote debugging on the phone.
- `screenrecord`.

The real-machine checklist is `reports/UNIVERSAL_OPERATOR_REAL_ACCEPTANCE.md`.
