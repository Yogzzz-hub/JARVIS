# Blind-11: unseen end-to-end validation

Cases: 1100 (22 phases x 50). Locked dataset sha256 `eacfa96ceb02e26a2a44602f737608e02ea18faa972ba709f17fab2f42216643` (see `tests/blind11/MANIFEST.json`).

## Headline (run B: command service, model unavailable, real sandbox execution where possible)

| | Exact action | Action precision | Action recall | Action F1 | Intent | Slot exact | Slot F1 | Constraints | Specificity | False-action rate | Critical wrong actions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Strict (as locked) | **45.0%** | 60.8% | 38.3% | 47.0% | 49.1% | 87.0% | 91.6% | 52.7% | 84.3% | 15.7% | **1** (C3 1, C4 0) |
| Audited (4 oracle errata removed) | **45.2%** | 61.0% | 38.5% | 47.2% | 49.2% | 87.0% | 91.6% | 52.7% | 84.6% | 15.4% | **0** (C3 0, C4 0) |

| | Value |
|---|---:|
| Reference / context resolution | 42.6% (122 cases) |
| Plan validity | 14.0% (57 cases) |
| Execution success (real postcondition checked) | 85.7% (14 executed) |
| End-to-end verified (cases with a postcondition) | 16.4% |
| Postcondition not verifiable here (dependency unavailable) | 45 cases |
| Verification accuracy (what JARVIS said vs the real result) | 100.0% (14 cases; false success 0, false failure 0) |
| Unsupported-claim rate | 0.7% |
| Clarification P / R / F1 | 14.0% / 53.9% / 22.2% |
| Tool micro P / R / F1 | 69.3% / 44.0% / 53.8% |
| Tool macro P / R / F1 | 75.2% / 47.7% / 58.4% |
| Negation / correction accuracy | 41.5% (41) / 63.6% (44) |
| Consequential negation / correction preservation (the negated or superseded consequential action never ran) | 100.0% (85) |
| Sandbox writes blocked outside the sandbox | 0 |
| Latency p50 / p95 / p99 (final response, run B) | 15 / 31 / 40 ms |
| Routing latency p50 / p95 / p99 (run A) | 7.0 / 19.2 / 25.5 ms |

## Run A (router / orchestration diagnostic, no execution)

Exact (semantic) 40.9% strict, 41.1% audited; action precision 58.7%, recall 35.0%; critical 4.

## Per phase (run B, strict)

| Phase | Exact | Intent | Act P | Act R | Act F1 | Slot F1 | Constraint | Specificity | Exec | Verify | Critical |
|------|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|
| Router / casual / typos | 56.0% | 56.0% | 88.5% | 54.8% | 67.6% | 100.0% | 66.7% | 87.5% | - | - | 0 |
| Core OS | 68.0% | 70.0% | 90.3% | 66.7% | 76.7% | 100.0% | 80.0% | 87.5% | - | - | 1 |
| Safety | 78.0% | 80.0% | 89.5% | 65.4% | 75.6% | 93.8% | 80.0% | 95.8% | 100.0% | 100.0% | 0 |
| WhatsApp | 60.0% | 68.0% | 74.2% | 54.8% | 63.0% | 90.3% | 50.0% | 87.5% | - | - | 0 |
| Multi-step planning | 20.0% | 32.0% | 19.0% | 9.5% | 12.7% | 90.9% | 14.3% | 87.5% | - | - | 0 |
| Files | 46.0% | 48.0% | 60.7% | 40.5% | 48.6% | 97.8% | 40.0% | 75.0% | 75.0% | 100.0% | 0 |
| Intelligence | 30.0% | 36.0% | 53.3% | 21.6% | 30.8% | 73.7% | 0.0% | 92.3% | - | - | 0 |
| Voice output | 34.0% | 42.0% | 44.4% | 28.6% | 34.8% | 80.0% | 60.0% | 75.0% | - | - | 0 |
| Phone | 46.0% | 48.0% | 60.0% | 42.9% | 50.0% | 94.7% | 40.0% | 75.0% | - | - | 0 |
| Google | 52.0% | 54.0% | 74.1% | 47.6% | 58.0% | 98.2% | 50.0% | 87.5% | - | - | 0 |
| Browser control | 46.0% | 52.0% | 56.2% | 42.9% | 48.6% | 89.5% | 75.0% | 75.0% | - | - | 0 |
| Vision | 56.0% | 58.0% | 74.1% | 48.8% | 58.8% | 94.4% | 75.0% | 88.9% | - | - | 0 |
| PC control | 42.0% | 44.0% | 57.1% | 39.0% | 46.4% | 88.9% | 25.0% | 66.7% | - | - | 0 |
| History / memory | 40.0% | 44.0% | 59.3% | 39.0% | 47.1% | 88.2% | 40.0% | 55.6% | - | - | 0 |
| Chat / conversation | 54.0% | 54.0% | 0.0% | - | - | - | 75.0% | 88.0% | - | - | 0 |
| Tanglish | 48.0% | 50.0% | 72.0% | 42.9% | 53.7% | 100.0% | 60.0% | 87.5% | - | - | 0 |
| Voice input / keyboard / dictation | 30.0% | 38.0% | 41.7% | 23.8% | 30.3% | 74.1% | 80.0% | 75.0% | - | - | 0 |
| Universal operator | 40.0% | 42.0% | 60.9% | 33.3% | 43.1% | 91.7% | 80.0% | 87.5% | - | - | 0 |
| Browser automation | 36.0% | 36.0% | 54.5% | 28.6% | 37.5% | 100.0% | 50.0% | 87.5% | - | - | 0 |
| Phone calls | 26.0% | 38.0% | 31.6% | 14.3% | 19.7% | 72.0% | 60.0% | 100.0% | - | - | 0 |
| Automation / watchers | 42.0% | 48.0% | 57.1% | 38.1% | 45.7% | 81.2% | 25.0% | 62.5% | - | - | 0 |
| Workflows / developer agent | 40.0% | 42.0% | 52.0% | 31.0% | 38.8% | 96.8% | 50.0% | 87.5% | - | - | 0 |

Full per-phase columns (tool P/R/F1, slot exact, negation, false-action rate, clarification, unsupported claims, latency, strict / audited / run A) are in `docs/BLIND11_PHASE_METRICS.csv`.

## Failure causes (run B, strict)

| Primary cause | Cases |
|---|---:|
| UNSUPPORTED_CAPABILITY | 254 |
| TOOL_WRONG | 115 |
| INTENT_WRONG | 76 |
| POLICY_WRONG | 40 |
| DEPENDENCY_UNAVAILABLE | 34 |
| ROUTER_WRONG | 17 |
| SLOT_WRONG | 17 |
| SLOT_DROPPED | 17 |
| REFERENCE_WRONG | 14 |
| UNKNOWN | 12 |
| PLANNER_WRONG | 9 |

## Biggest capability confusions

| Expected | Got | Cases |
|---|---|---:|
| CHAT | CLARIFY | 21 |
| compound | PLAN | 13 |
| compound | CLARIFY | 11 |
| browser_quick_action | CLARIFY | 11 |
| clipboard_op | CLARIFY | 9 |
| android_toggle | CLARIFY | 9 |
| browser_click | CLARIFY | 9 |
| gmail_list_recent | CLARIFY | 8 |
| brightness_set | CLARIFY | 7 |
| compound | compound | 7 |
| CLARIFY | CHAT | 7 |
| CONTROL:speech_control | CLARIFY | 7 |
| text_op | CLARIFY | 7 |
| ide_op | CLARIFY | 7 |
| android_tap_text | CLARIFY | 7 |
| read_whatsapp_messages | CLARIFY | 6 |
| computer_task | CLARIFY | 6 |
| snap_window | CLARIFY | 6 |
| set_reminder | CLARIFY | 6 |
| search_news | CLARIFY | 5 |
| quick_answer | CHAT | 5 |
| REFUSE | CLARIFY | 5 |
| document_qa | CLARIFY | 5 |
| describe_screen | CLARIFY | 5 |
| android_tap_text | phone_op | 5 |

## Slot accuracy by type (run B)

| Slot type | Correct |
|---|---:|
| URL | 80.0% |
| action / mode | 83.6% |
| application / target name | 95.1% |
| browser tab | 100.0% |
| button | 100.0% |
| command | 100.0% |
| condition | 100.0% |
| contact | 100.0% |
| count | 71.4% |
| count_only | 100.0% |
| date / time | 100.0% |
| device | 100.0% |
| device setting | 100.0% |
| double | 100.0% |
| dry_run | 0.0% |
| everyone | 100.0% |
| fact | 100.0% |
| file / folder | 93.9% |
| file type | 50.0% |
| filter | 25.0% |
| gender | 100.0% |
| item | 100.0% |
| key | 100.0% |
| kind | 100.0% |
| message body | 100.0% |
| message body / text | 88.9% |
| new_name | 100.0% |
| number | 92.3% |
| on | 100.0% |
| option | 100.0% |
| ordinal | 100.0% |
| phrase | 50.0% |
| query | 93.8% |
| recipient | 100.0% |
| sender constraint | 100.0% |
| settings page | 100.0% |
| target | 66.7% |
| time range | 100.0% |
| unit | 100.0% |
| unread_only | 50.0% |
| window | 100.0% |
