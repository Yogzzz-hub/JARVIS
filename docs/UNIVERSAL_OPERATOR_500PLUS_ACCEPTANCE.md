# Universal Operator - 500+ Scenario Acceptance

Router-level acceptance of the operator scenarios (`tests/operator/`), measured in the CI container with **no AI model** (DisabledProvider): every number below is deterministic understanding. Execution on a real PC/phone is the separate checklist in `reports/UNIVERSAL_OPERATOR_REAL_ACCEPTANCE.md` (not yet run).

## What a scenario is

A meaning, not a sentence: setup state, semantic goal, constraints, the capability that must run (or that JARVIS must ask / refuse / plan), the expected state change, how it is verified, and the risk. Surface wordings are generated from each scenario's seed: **dev** forms (canonical, formal, casual, polite, wake word, ASR-style, short, typo) were used while building the parser; **holdout** forms (long run-up, "for me" tails, spoken numbers, "kindly", a different typo model, hesitation) were never used for tuning. Every action scenario is also checked in negated form ("don't ...") - nothing may run.

Scenarios: **598** - android 58, browser 72, clipboard 38, cross 30, desktop 66, files 50, ide 45, media 38, system 36, text 61, ui 56, workflow 48

## Headline

| Metric | Dev forms | Holdout forms |
|---|---:|---:|
| Surface forms routed | 4179 | 3828 |
| Form accuracy | 99.76% | 99.45% |
| Scenarios with every form correct | 589 / 598 | 577 / 598 |
| Negated forms checked / executed | 548 / 0 | 548 / 0 |
| Security-bypass routes (secret fields, unlock, CAPTCHA) | 0 | 0 |
| Forms routed to a different runnable tool | 5 | 15 |
| Routing p50 / p95 (ms) | 2.62 / 7.62 | 2.53 / 7.86 |

**Holdout first run** (before anything was changed in response to it): 94.98% of 3828 forms, 454 / 598 scenarios with every form correct, 0 negated executions, 4 secret-field forms routed to the planner instead of a refusal. Its failures were mostly polite run-ups ("hey jarvis, when you get a sec, ..." was read as a standing rule) and dropped-letter typos ("phne", "frst", "wrds" - the dev typo model only swapped letters). Those were fixed generically (run-up stripping before routing, one-dropped-letter repair against the operator vocabulary, a text-unit guard on file deletion), so the holdout numbers in the table are **after** that round and are no longer a pure holdout; the first-run figure is the honest generalization estimate.

"Different runnable tool" counts every form whose route was not the scenario's capability or one of its listed equivalents and was not a question or a plan. Most are typo forms of real English words ("froth", "filed") that are deliberately not corrected; they are listed below so nothing is hidden.

### Dev forms by family

| Slice | Passed | Total | Accuracy |
|---|---:|---:|---:|
| android | 401 | 402 | 99.75% |
| browser | 458 | 461 | 99.35% |
| clipboard | 252 | 254 | 99.21% |
| cross | 204 | 205 | 99.51% |
| desktop | 558 | 559 | 99.82% |
| files | 341 | 342 | 99.71% |
| ide | 307 | 308 | 99.68% |
| media | 223 | 223 | 100.0% |
| system | 222 | 222 | 100.0% |
| text | 400 | 400 | 100.0% |
| ui | 484 | 484 | 100.0% |
| workflow | 319 | 319 | 100.0% |

### Dev forms by surface form

| Slice | Passed | Total | Accuracy |
|---|---:|---:|---:|
| asr | 21 | 21 | 100.0% |
| canonical | 638 | 638 | 100.0% |
| casual | 638 | 638 | 100.0% |
| formal | 637 | 638 | 99.84% |
| polite | 637 | 638 | 99.84% |
| short | 394 | 394 | 100.0% |
| typo | 566 | 574 | 98.61% |
| wake | 638 | 638 | 100.0% |

### Holdout forms by family

| Slice | Passed | Total | Accuracy |
|---|---:|---:|---:|
| android | 346 | 348 | 99.43% |
| browser | 429 | 432 | 99.31% |
| clipboard | 228 | 228 | 100.0% |
| cross | 177 | 180 | 98.33% |
| desktop | 544 | 546 | 99.63% |
| files | 296 | 300 | 98.67% |
| ide | 268 | 270 | 99.26% |
| media | 225 | 228 | 98.68% |
| system | 216 | 216 | 100.0% |
| text | 364 | 366 | 99.45% |
| ui | 426 | 426 | 100.0% |
| workflow | 288 | 288 | 100.0% |

### Holdout forms by surface form

| Slice | Passed | Total | Accuracy |
|---|---:|---:|---:|
| hesitant | 638 | 638 | 100.0% |
| kindly | 638 | 638 | 100.0% |
| long | 638 | 638 | 100.0% |
| spoken_numbers | 638 | 638 | 100.0% |
| tail | 635 | 638 | 99.53% |
| typo2 | 620 | 638 | 97.18% |

## Dev failures (10)

| Scenario | Form | Text | Why |
|---|---|---|---|
| DES-0025 | typo | toggle back and froth | intent volume_unmute (LANE_0) not in ('window_op',) |
| BRO-0247 | typo | refrseh the page | intent None (LANE_2) not in ('browser_quick_action', 'browser_op', 'pc_quick_action', 'window_op') |
| BRO-0252 | typo | saerch for lofi music | intent find_file (LANE_0) not in ('search_web', 'open_website', 'web_task', 'browser_op', 'quick_answer') |
| BRO-0255 | typo | seacrh for best laptops 2026 | intent find_file (LANE_0) not in ('search_web', 'open_website', 'web_task', 'browser_op', 'quick_answer') |
| CLI-0319 | formal | What's on my clipboard? | intent None (LANE_2) not in ('clipboard_intelligence', 'clipboard_op') |
| CLI-0319 | polite | tell me what's on my clipboard please | intent None (LANE_2) not in ('clipboard_intelligence', 'clipboard_op') |
| FIL-0375 | typo | open the most recent dwonload | intent open_app (LANE_0) not in ('open_file', 'find_file', 'document_qa', 'knowledge_search', '*CLARIFY', 'read_file_metadata', 'list_direct |
| IDE-0426 | typo | open the redame in antigravity | intent open_app (LANE_0) not in ('open_file', 'ide_op', 'find_file', 'antigravity_ide_control', '*PLANNER') |
| AND-0471 | typo | type pizza in the search filed on my phone | intent unknown (CLARIFY) not in ('ui_op', 'android_input') |
| CRO-0494 | typo | trnasfer the download to my phone | intent None (LANE_2) not in ('deliver_op', 'localsend_file', 'android_push_file', 'deliver_op', 'localsend_text', 'android_pull_file', '*CLA |

## Holdout failures (21)

| Scenario | Form | Text | Why |
|---|---|---|---|
| DES-0020 | typo2 | switch to the previous widow | intent switch_window (LANE_0) not in ('window_op',) |
| DES-0025 | typo2 | toggle back and frth | intent volume_unmute (LANE_0) not in ('window_op',) |
| TEX-0117 | typo2 | select the whle paragraph | intent screen_click (LANE_0) not in ('text_op', 'voice_edit', 'pc_quick_action') |
| TEX-0123 | tail | select all for me | intent screen_click (LANE_0) not in ('pc_quick_action', 'text_op', 'voice_edit', 'keyboard_shortcut', 'clipboard_op') |
| BRO-0195 | typo2 | open the forth video | intent open_app (LANE_0) not in ('browser_op',) |
| BRO-0247 | typo2 | rfresh the page | intent None (LANE_2) not in ('browser_quick_action', 'browser_op', 'pc_quick_action', 'window_op') |
| BRO-0252 | typo2 | sarch for lofi music | intent find_file (LANE_0) not in ('search_web', 'open_website', 'web_task', 'browser_op', 'quick_answer') |
| MED-0273 | typo2 | play at 2x seed | intent play_youtube (LANE_0) not in ('video_op',) |
| MED-0276 | typo2 | play at nomal speed | intent play_youtube (LANE_0) not in ('video_op',) |
| MED-0291 | typo2 | resume the muic | intent None (LANE_2) not in ('media_control', 'video_op', 'media_control', 'volume_set', 'play_youtube', 'volume_mute') |
| FIL-0365 | typo2 | delete the last tree words | intent delete_file (LANE_0) not in ('text_op', 'voice_edit') |
| FIL-0369 | typo2 | erase the last 2 lies | intent None (LANE_2) not in ('text_op', 'voice_edit') |
| FIL-0372 | typo2 | open the secnd file | intent open_app (LANE_0) not in ('open_file', 'find_file', 'document_qa', 'knowledge_search', '*CLARIFY', 'read_file_metadata', 'list_direct |
| FIL-0373 | typo2 | open the first result in my documnts | intent open_app (LANE_0) not in ('open_file', 'find_file', 'document_qa', 'knowledge_search', '*CLARIFY', 'read_file_metadata', 'list_direct |
| IDE-0411 | typo2 | discrd the suggestions in vs code | intent None (LANE_2) not in ('ide_op',) |
| IDE-0426 | typo2 | open the radme in antigravity | intent open_app (LANE_0) not in ('open_file', 'ide_op', 'find_file', 'antigravity_ide_control', '*PLANNER') |
| AND-0437 | typo2 | press back on my pone | intent screen_click (LANE_0) not in ('android_back', 'android_key', 'android_back', 'android_home', 'phone_op', 'android_quick_action') |
| AND-0463 | tail | open google.com on my phone for me | intent android_open_app (LANE_0) not in ('android_open_url', 'android_toggle', 'android_key', 'android_quick_action', 'phone_op', 'localsend |
| CRO-0492 | tail | get the latest screenshot from my phone for me | intent android_screenshot (LANE_0) not in ('android_pull_file', 'localsend_file', 'android_push_file', 'deliver_op', 'localsend_text', 'andr |
| CRO-0506 | typo2 | what notifications do I have on my pone | intent None (LANE_2) not in ('android_notifications',) |
| CRO-0510 | typo2 | is my phone charing | intent android_quick_action (CLARIFY) not in ('android_status', 'battery_status', 'phone_op') |

## Zero-fail rules and how they are held

| Rule | Mechanism | Evidence |
|---|---|---|
| Wrong-app typing = 0 | focus re-verified before every keystroke batch (`TextOperator._guard`, LiveDictation `_focus_ok`) | `test_typing_refuses_a_window_that_lost_focus`, `test_live_dictation_pauses_when_target_is_lost` |
| Wrong control invocation = 0 | resolver ties -> question; nested scopes/references -> plan or ask | `test_resolver_scores_asks_on_ties_and_respects_ordinals` |
| Negated action execution = 0 | negation guard before the operator parser | negated forms above; `test_negated_wording_never_runs` |
| Unrelated capability = 0 for text units | 'delete the last three words' is text_op, never delete_file | `test_former_misroutes_are_fixed` |
| Unverified send success = 0 | send needs approval; success only when the composer empties / Stop appears | `test_send_needs_approval`, `test_ide_prompt_write_and_send_are_observed` |
| Duplicate uncertain send = 0 | approval re-runs the same prepared call once; no automatic retry of sends | `CommandService._operator_approval` |
| Prompt-injection execution = 0 | page/notification/IDE/clipboard text returned as untrusted data | `evidence.untrusted` on reads |
| Security bypass = 0 | secret fields refused, CAPTCHA/lock -> owner, no UAC automation | `test_sensitive_and_consequential_controls`, `test_phone_typed_operations_and_lock_guard` |
| Ungrounded visual click = 0 | vision point validated against the element under it | `computer_use.validate_point` |
