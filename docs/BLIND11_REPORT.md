# Blind-11: unseen end-to-end validation

Cases: 1100 (22 phases x 50). Locked dataset sha256 `eacfa96ceb02e26a2a44602f737608e02ea18faa972ba709f17fab2f42216643` (see `tests/blind11/MANIFEST.json`).

## Headline (run B: command service, model unavailable, real sandbox execution where possible)

| | Exact action | Action precision | Action recall | Action F1 | Intent | Slot exact | Slot F1 | Constraints | Specificity | False-action rate | Critical wrong actions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Strict (as locked) | **33.1%** | 46.5% | 29.5% | 36.1% | 39.3% | 78.8% | 83.6% | 24.5% | 75.2% | 24.8% | **47** (C3 31, C4 16) |
| Audited (3 oracle errata removed) | **33.2%** | 46.6% | 29.6% | 36.2% | 39.3% | 78.8% | 83.6% | 24.5% | 75.2% | 24.8% | **47** (C3 31, C4 16) |

| | Value |
|---|---:|
| Reference / context resolution | 16.4% (122 cases) |
| Plan validity | 10.5% (57 cases) |
| Execution success (real postcondition checked) | 28.6% (7 executed) |
| End-to-end verified (cases with a postcondition) | 2.7% |
| Postcondition not verifiable here (dependency unavailable) | 44 cases |
| Verification accuracy (what JARVIS said vs the real result) | 100.0% (7 cases; false success 0, false failure 0) |
| Unsupported-claim rate | 0.9% |
| Clarification P / R / F1 | 12.2% / 52.8% / 19.8% |
| Tool micro P / R / F1 | 59.2% / 37.8% / 46.1% |
| Tool macro P / R / F1 | 66.9% / 42.5% / 52.0% |
| Negation / correction accuracy | 26.8% (41) / 13.6% (44) |
| Sandbox writes blocked outside the sandbox | 0 |
| Latency p50 / p95 / p99 (final response, run B) | 20 / 40 / 53 ms |
| Routing latency p50 / p95 / p99 (run A) | 9.3 / 23.2 / 31.8 ms |

## Run A (router / orchestration diagnostic, no execution)

Exact (semantic) 31.5% strict, 31.6% audited; action precision 47.2%, recall 29.4%; critical 43.

## Per phase (run B, strict)

| Phase | Exact | Intent | Act P | Act R | Act F1 | Slot F1 | Constraint | Specificity | Exec | Verify | Critical |
|------|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|
| Router / casual / typos | 46.0% | 48.0% | 71.4% | 47.6% | 57.1% | 92.3% | 33.3% | 75.0% | - | - | 1 |
| Core OS | 54.0% | 58.0% | 79.3% | 54.8% | 64.8% | 94.4% | 40.0% | 75.0% | - | - | 3 |
| Safety | 34.0% | 48.0% | 22.2% | 15.4% | 18.2% | 44.4% | 0.0% | 87.5% | - | - | 13 |
| WhatsApp | 38.0% | 54.0% | 48.3% | 33.3% | 39.4% | 82.1% | 37.5% | 87.5% | - | - | 8 |
| Multi-step planning | 10.0% | 22.0% | 10.0% | 4.8% | 6.5% | 85.7% | 14.3% | 62.5% | - | - | 1 |
| Files | 34.0% | 38.0% | 46.7% | 33.3% | 38.9% | 91.4% | 20.0% | 62.5% | 28.6% | 100.0% | 1 |
| Intelligence | 22.0% | 28.0% | 44.4% | 21.6% | 29.1% | 66.7% | 0.0% | 76.9% | - | - | 2 |
| Voice output | 28.0% | 36.0% | 34.6% | 21.4% | 26.5% | 71.4% | 0.0% | 75.0% | - | - | 0 |
| Phone | 36.0% | 38.0% | 46.9% | 35.7% | 40.5% | 92.9% | 40.0% | 50.0% | - | - | 2 |
| Google | 32.0% | 44.0% | 46.2% | 28.6% | 35.3% | 80.9% | 16.7% | 87.5% | - | - | 6 |
| Browser control | 34.0% | 40.0% | 43.8% | 33.3% | 37.8% | 86.7% | 50.0% | 75.0% | - | - | 0 |
| Vision | 46.0% | 52.0% | 64.3% | 43.9% | 52.2% | 91.4% | 25.0% | 66.7% | - | - | 2 |
| PC control | 32.0% | 36.0% | 44.4% | 29.3% | 35.3% | 75.0% | 25.0% | 66.7% | - | - | 2 |
| History / memory | 30.0% | 34.0% | 48.1% | 31.7% | 38.2% | 86.7% | 20.0% | 44.4% | - | - | 1 |
| Chat / conversation | 52.0% | 52.0% | 0.0% | - | - | - | 50.0% | 86.0% | - | - | 0 |
| Tanglish | 32.0% | 38.0% | 50.0% | 28.6% | 36.4% | 76.9% | 0.0% | 62.5% | - | - | 2 |
| Voice input / keyboard / dictation | 22.0% | 32.0% | 31.8% | 16.7% | 21.9% | 69.2% | 20.0% | 75.0% | - | - | 0 |
| Universal operator | 36.0% | 38.0% | 56.0% | 33.3% | 41.8% | 92.3% | 80.0% | 62.5% | - | - | 1 |
| Browser automation | 26.0% | 26.0% | 44.0% | 26.2% | 32.8% | 100.0% | 50.0% | 62.5% | - | - | 1 |
| Phone calls | 16.0% | 26.0% | 18.8% | 7.1% | 10.3% | 62.5% | 0.0% | 100.0% | - | - | 0 |
| Automation / watchers | 38.0% | 44.0% | 56.7% | 40.5% | 47.2% | 82.4% | 25.0% | 50.0% | - | - | 1 |
| Workflows / developer agent | 30.0% | 32.0% | 44.0% | 26.2% | 32.8% | 96.6% | 0.0% | 87.5% | - | - | 0 |

Full per-phase columns (tool P/R/F1, slot exact, negation, false-action rate, clarification, unsupported claims, latency, strict / audited / run A) are in `docs/BLIND11_PHASE_METRICS.csv`.

## Failure causes (run B, strict)

| Primary cause | Cases |
|---|---:|
| UNSUPPORTED_CAPABILITY | 260 |
| TOOL_WRONG | 134 |
| POLICY_WRONG | 92 |
| INTENT_WRONG | 78 |
| DEPENDENCY_UNAVAILABLE | 40 |
| REFERENCE_WRONG | 31 |
| SLOT_WRONG | 28 |
| ROUTER_WRONG | 24 |
| UNKNOWN | 16 |
| SLOT_DROPPED | 15 |
| CORRECTION_LOST | 9 |
| PLANNER_WRONG | 9 |

## Biggest capability confusions

| Expected | Got | Cases |
|---|---|---:|
| REFUSE | CLARIFY | 33 |
| CHAT | CLARIFY | 23 |
| compound | PLAN | 13 |
| brightness_set | CLARIFY | 10 |
| compound | CLARIFY | 10 |
| android_toggle | CLARIFY | 10 |
| browser_quick_action | CLARIFY | 10 |
| clipboard_op | CLARIFY | 9 |
| browser_click | CLARIFY | 9 |
| gmail_list_recent | CLARIFY | 8 |
| compound | compound | 7 |
| CLARIFY | CHAT | 7 |
| CONTROL:speech_control | CLARIFY | 7 |
| text_op | CLARIFY | 7 |
| ide_op | CLARIFY | 7 |
| android_tap_text | CLARIFY | 7 |
| volume_set | CLARIFY | 6 |
| read_whatsapp_messages | CLARIFY | 6 |
| describe_screen | CLARIFY | 6 |
| computer_task | CLARIFY | 6 |
| snap_window | CLARIFY | 6 |
| set_reminder | CLARIFY | 6 |
| android_dial | CLARIFY | 6 |
| search_news | CLARIFY | 5 |
| quick_answer | CHAT | 5 |

## Slot accuracy by type (run B)

| Slot type | Correct |
|---|---:|
| URL | 75.0% |
| action / mode | 81.7% |
| application / target name | 83.3% |
| browser tab | 100.0% |
| button | 100.0% |
| command | 100.0% |
| condition | 100.0% |
| contact | 100.0% |
| count | 55.6% |
| count_only | 100.0% |
| date / time | 85.7% |
| device | 100.0% |
| device setting | 100.0% |
| double | 100.0% |
| dry_run | 0.0% |
| fact | 100.0% |
| file / folder | 73.1% |
| file type | 50.0% |
| filter | 33.3% |
| gender | 100.0% |
| item | 100.0% |
| key | 100.0% |
| kind | 100.0% |
| message body | 100.0% |
| message body / text | 91.7% |
| new_name | 100.0% |
| number | 82.4% |
| on | 100.0% |
| option | 100.0% |
| ordinal | 100.0% |
| phrase | 50.0% |
| query | 92.9% |
| recipient | 76.9% |
| sender constraint | 100.0% |
| settings page | 100.0% |
| symbols | 0.0% |
| target | 68.4% |
| time range | 100.0% |
| unit | 100.0% |
| unread_only | 0.0% |
| window | 100.0% |
