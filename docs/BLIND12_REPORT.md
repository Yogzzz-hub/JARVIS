# Blind-12: unseen end-to-end validation

Cases: 1100 (22 phases x 50). Locked dataset sha256 `69e4c803e5337ff399c382ae1044d73968376d19a189c78227779562a4709e2e` (see `tests/blind12/MANIFEST.json`).

## Headline (run B: command service, model unavailable, real sandbox execution where possible)

| | Exact action | Action precision | Action recall | Action F1 | Intent | Slot exact | Slot F1 | Constraints | Specificity | False-action rate | Critical wrong actions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Strict (as locked) | **32.5%** | 47.6% | 27.4% | 34.8% | 37.6% | 77.4% | 82.1% | 29.6% | 76.4% | 23.6% | **34** (C3 17, C4 17) |
| Audited (8 oracle errata removed) | **32.7%** | 47.9% | 27.6% | 35.0% | 37.6% | 77.3% | 82.0% | 29.9% | 76.3% | 23.7% | **34** (C3 17, C4 17) |

| | Value |
|---|---:|
| Reference / context resolution | 18.2% (110 cases) |
| Plan validity | 7.7% (39 cases) |
| Execution success (real postcondition checked) | 55.6% (9 executed) |
| End-to-end verified (cases with a postcondition) | 6.8% |
| Postcondition not verifiable here (dependency unavailable) | 43 cases |
| Verification accuracy (what JARVIS said vs the real result) | 66.7% (9 cases; false success 3, false failure 0) |
| Unsupported-claim rate | 1.0% |
| Clarification P / R / F1 | 14.1% / 52.8% / 22.2% |
| Tool micro P / R / F1 | 58.9% / 34.2% / 43.2% |
| Tool macro P / R / F1 | 56.9% / 34.7% / 43.1% |
| Negation / correction accuracy | 20.4% (54) / 41.2% (34) |
| Consequential negation / correction preservation (the negated or superseded consequential action never ran) | 98.9% (88) |
| Sandbox writes blocked outside the sandbox | 0 |
| Latency p50 / p95 / p99 (final response, run B) | 26 / 52 / 69 ms |
| Routing latency p50 / p95 / p99 (run A) | 11.4 / 27.8 / 44.1 ms |

## Run A (router / orchestration diagnostic, no execution)

Exact (semantic) 31.9% strict, 31.9% audited; action precision 48.3%, recall 28.2%; critical 33.

## Per phase (run B, strict)

| Phase | Exact | Intent | Act P | Act R | Act F1 | Slot F1 | Constraint | Specificity | Exec | Verify | Critical |
|------|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|
| Router / casual / typos | 42.0% | 48.0% | 64.0% | 38.1% | 47.8% | 87.5% | 37.5% | 75.0% | - | - | 1 |
| Core OS | 50.0% | 50.0% | 79.2% | 45.2% | 57.6% | 100.0% | 40.0% | 87.5% | - | - | 0 |
| Safety | 18.0% | 28.0% | 17.6% | 11.5% | 14.0% | 44.4% | 12.5% | 79.2% | 100.0% | 100.0% | 9 |
| WhatsApp | 42.0% | 50.0% | 64.0% | 38.1% | 47.8% | 83.0% | 35.7% | 62.5% | - | - | 7 |
| Multi-step planning | 10.0% | 18.0% | 20.0% | 9.5% | 12.9% | 82.4% | 25.0% | 75.0% | - | - | 0 |
| Files | 32.0% | 36.0% | 41.7% | 23.8% | 30.3% | 83.9% | 44.4% | 87.5% | 50.0% | 62.5% | 3 |
| Intelligence | 18.0% | 18.0% | 10.0% | 2.7% | 4.3% | - | 0.0% | 92.3% | - | - | 1 |
| Voice output | 38.0% | 44.0% | 52.9% | 42.9% | 47.4% | 87.0% | 37.5% | 25.0% | - | - | 0 |
| Phone | 50.0% | 52.0% | 65.5% | 45.2% | 53.5% | 95.5% | 44.4% | 87.5% | - | - | 0 |
| Google | 26.0% | 40.0% | 36.0% | 21.4% | 26.9% | 65.0% | 25.0% | 62.5% | - | - | 0 |
| Browser control | 36.0% | 38.0% | 50.0% | 35.7% | 41.7% | 94.4% | 33.3% | 62.5% | - | - | 1 |
| Vision | 48.0% | 52.0% | 62.5% | 48.8% | 54.8% | 89.7% | 83.3% | 44.4% | - | - | 2 |
| PC control | 40.0% | 44.0% | 52.0% | 31.7% | 39.4% | 77.8% | 33.3% | 77.8% | - | - | 1 |
| History / memory | 36.0% | 44.0% | 46.7% | 34.1% | 39.4% | 76.5% | 38.5% | 44.4% | - | - | 2 |
| Chat / conversation | 52.0% | 52.0% | 0.0% | - | - | - | 71.4% | 86.0% | - | - | 0 |
| Tanglish | 30.0% | 36.0% | 62.5% | 23.8% | 34.5% | 76.2% | 20.0% | 100.0% | - | - | 1 |
| Voice input / keyboard / dictation | 18.0% | 26.0% | 20.0% | 9.5% | 12.9% | 78.6% | 11.1% | 87.5% | - | - | 0 |
| Universal operator | 20.0% | 24.0% | 35.0% | 16.7% | 22.6% | 33.3% | 0.0% | 50.0% | - | - | 1 |
| Browser automation | 18.0% | 18.0% | 28.6% | 9.5% | 14.3% | 100.0% | 10.0% | 100.0% | - | - | 1 |
| Phone calls | 32.0% | 34.0% | 63.2% | 28.6% | 39.3% | 87.5% | 25.0% | 87.5% | - | - | 0 |
| Automation / watchers | 34.0% | 50.0% | 41.9% | 31.0% | 35.6% | 68.2% | 42.9% | 75.0% | - | - | 4 |
| Workflows / developer agent | 26.0% | 26.0% | 47.1% | 19.0% | 27.1% | 100.0% | 16.7% | 75.0% | - | - | 0 |

Full per-phase columns (tool P/R/F1, slot exact, negation, false-action rate, clarification, unsupported claims, latency, strict / audited / run A) are in `docs/BLIND12_PHASE_METRICS.csv`.

## Failure causes (run B, strict)

| Primary cause | Cases |
|---|---:|
| UNSUPPORTED_CAPABILITY | 227 |
| INTENT_WRONG | 156 |
| TOOL_WRONG | 127 |
| POLICY_WRONG | 75 |
| DEPENDENCY_UNAVAILABLE | 34 |
| SLOT_WRONG | 29 |
| ROUTER_WRONG | 26 |
| UNKNOWN | 25 |
| REFERENCE_WRONG | 25 |
| SLOT_DROPPED | 12 |
| PLANNER_WRONG | 4 |
| CORRECTION_LOST | 2 |

## Biggest capability confusions

| Expected | Got | Cases |
|---|---|---:|
| REFUSE | CLARIFY | 20 |
| browser_click | CLARIFY | 15 |
| CHAT | CLARIFY | 14 |
| browser_quick_action | CLARIFY | 12 |
| compound | PLAN | 10 |
| quick_answer | CHAT | 9 |
| android_quick_action | CLARIFY | 9 |
| CLARIFY | CHAT | 8 |
| REFUSE | PLAN | 8 |
| compound | CLARIFY | 8 |
| snap_window | CLARIFY | 8 |
| clipboard_op | CLARIFY | 8 |
| brightness_set | CLARIFY | 7 |
| read_whatsapp_messages | CHAT | 7 |
| REFUSE | CHAT | 7 |
| text_op | CLARIFY | 7 |
| search_web | CHAT | 6 |
| send_whatsapp_message | CLARIFY | 6 |
| file_op | CLARIFY | 6 |
| CONTROL:speech_control | CLARIFY | 6 |
| calendar_list_events | CHAT | 6 |
| describe_screen | CHAT | 6 |
| window_op | CLARIFY | 6 |
| android_tap_text | CLARIFY | 6 |
| android_dial | CLARIFY | 6 |

## Slot accuracy by type (run B)

| Slot type | Correct |
|---|---:|
| action / mode | 77.2% |
| application / target name | 83.3% |
| browser tab | 100.0% |
| button | 100.0% |
| component | 100.0% |
| contact | 0.0% |
| count | 30.0% |
| date / time | 100.0% |
| device | 100.0% |
| device setting | 100.0% |
| fact | 100.0% |
| file / folder | 85.7% |
| file type | 66.7% |
| filter | 100.0% |
| find | 100.0% |
| gender | 100.0% |
| group | 100.0% |
| hours | 0.0% |
| include_groups | 100.0% |
| item | 75.0% |
| key | 100.0% |
| kind | 75.0% |
| message body | 100.0% |
| message body / text | 79.2% |
| new_name | 100.0% |
| number | 72.7% |
| on | 83.3% |
| ordinal | 100.0% |
| phrase | 100.0% |
| query | 81.8% |
| recipient | 91.7% |
| replace_with | 100.0% |
| sender constraint | 60.0% |
| symbols | 0.0% |
| target | 100.0% |
| time range | 66.7% |
| unit | 100.0% |
| unread_only | 80.0% |
| what | 100.0% |
| window | 50.0% |
