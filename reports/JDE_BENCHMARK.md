# JDE benchmark

Model `jde-20260925-223430-2c57ab` · encoder `static-glove100+hash-4096` · catalog `cat-04368ff93d`
Generated 2026-09-25 22:47 on 4 CPU threads.

Splits are never used for training, calibration, fusion weights or thresholds.

## Verdict

**JDE stays in SHADOW mode** (`[decision] stage = "shadow"`): 1 wrong consequential execution(s) across splits (target 0); route accuracy below the 98% target on at least one split. The existing router remains the only thing that routes; JDE only logs its decision next to the router's.

## Headline

| Metric | Development | Final holdout | Adversarial | Target |
|---|---|---|---|---|
| Route family accuracy | 84.6% | 88.0% | 76.0% | ≥ 98% |
| Route top-3 recall | 96.3% | 99.0% | 96.0% |  |
| Required family coverage@5 | 98.3% | 97.0% | 98.0% | ≥ 99% |
| Actionability accuracy | 93.7% | 95.0% | 84.0% | ≥ 99% |
| Needs-LLM accuracy | 90.0% | 94.0% | 90.0% | ≥ 98% |
| Needs-planner precision / recall | 58.8% / 71.4% | 83.3% / 100.0% | 0.0% / 100.0% | ≥ 97% |
| Needs-web accuracy | 95.7% | 98.0% | 96.0% |  |
| Needs-context accuracy | 98.3% | 100.0% | 100.0% |  |
| External-effect accuracy | 98.6% | 95.0% | 98.0% |  |
| Destructive accuracy | 97.4% | 95.0% | 98.0% |  |
| Ambiguity accuracy | 97.7% | 97.0% | 96.0% |  |
| Unknown / clarify detection | 100.0% | 100.0% | 100.0% | ≥ 98% |
| Route ECE / Brier | 0.033 / 0.235 | 0.085 / 0.180 | 0.138 / 0.284 |  |
| Auto-execute rate (gate) | 41.4% | 44.0% | 40.0% |  |
| Precision of auto-executed routes | 98.6% | 100.0% | 100.0% |  |
| Wrong consequential executions | 1 | 0 | 0 | 0 |

## Current router vs current router + JDE (same unseen cases, no LLM in either)

| Split | L0 decided | Current router accuracy | Router + JDE accuracy | Planner/agent calls (cur → +JDE) | LLM calls (cur → +JDE) | Wrong consequential (cur → +JDE) |
|---|---|---|---|---|---|---|
| dev | 56.3% | 58.3% | 66.9% | 36 → 15 | 104 → 110 | 12 → 7 |
| holdout | 52.0% | 48.0% | 54.0% | 25 → 15 | 39 → 32 | 6 → 5 |
| adversarial | 44.0% | 62.0% | 64.0% | 4 → 3 | 23 → 26 | 1 → 0 |

## Stage B (read_only) effect

Only requests the router cannot match (the `unknown_command` agent fallback) are eligible; JDE may send a
calibrated KNOWLEDGE question to the read-only chat model instead of the tool-using agent.

| Split | Agent fallbacks | Diverted to chat | Diverted & really a question | Diverted but really an action |
|---|---|---|---|---|
| dev | 11 | 0 | 0 | 0 |
| holdout | 3 | 0 | 0 | 0 |
| adversarial | 0 | 0 | 0 | 0 |

## Calibration (final holdout)

Route family reliability (confidence bin → mean confidence vs accuracy):

| Bin | n | Mean confidence | Accuracy |
|---|---|---|---|
| 0.1-0.2 | 1 | 0.177 | 0.000 |
| 0.2-0.3 | 1 | 0.211 | 0.000 |
| 0.3-0.4 | 2 | 0.343 | 0.500 |
| 0.4-0.5 | 5 | 0.440 | 0.600 |
| 0.5-0.6 | 8 | 0.556 | 0.875 |
| 0.6-0.7 | 2 | 0.664 | 0.500 |
| 0.7-0.8 | 7 | 0.747 | 0.571 |
| 0.8-0.9 | 17 | 0.856 | 0.882 |
| 0.9-1.0 | 57 | 0.977 | 1.000 |

| Head | Accuracy | Precision | Recall | ECE | Brier |
|---|---|---|---|---|---|
| is_action | 95.0% | 100.0% | 94.3% | 0.060 | 0.041 |
| needs_llm | 94.0% | 93.8% | 88.2% | 0.060 | 0.060 |
| needs_planner | 99.0% | 83.3% | 100.0% | 0.053 | 0.010 |
| needs_context | 100.0% | 100.0% | 100.0% | 0.009 | 0.001 |
| needs_web | 98.0% | 100.0% | 71.4% | 0.015 | 0.016 |
| external_effect | 95.0% | 75.0% | 66.7% | 0.043 | 0.045 |
| destructive | 95.0% | 0.0% | 0.0% | 0.040 | 0.041 |
| ambiguous | 97.0% | 60.0% | 75.0% | 0.035 | 0.013 |
| supported | 96.0% | 100.0% | 95.9% | 0.035 | 0.031 |

## Critical confusions (holdout + adversarial + dev)

| True → predicted | count |
|---|---|
| KNOWLEDGE ↔ APP | 0 |
| KNOWLEDGE ↔ WHATSAPP | 4 |
| KNOWLEDGE ↔ PACKAGE | 0 |
| RAG ↔ WEB | 0 |
| BROWSER ↔ DESKTOP | 0 |
| PHONE ↔ TRANSFER | 2 |
| PLANNER ↔ WHATSAPP | 2 |
| CLARIFY ↔ WHATSAPP | 7 |
| CLARIFY ↔ TRANSFER | 0 |
| KNOWLEDGE ↔ WEB | 2 |
| FILE ↔ RAG | 2 |

## Latency (routing only, no execution)

* first call (model already loaded): 1.29 ms
* cache miss p50 / p95 / p99: 1.13 / 1.51 / 2.23 ms over 10000 requests
* cache hit p50: 0.024 ms · throughput 840 decisions/s · process max RSS 182 MB
* engine load (cold start): 1070 ms

## Encoder backbones

| Encoder | Holdout route acc | Adversarial route acc | Dev route acc | Miss p50 ms |
|---|---|---|---|---|
| hash | 86.0% | 84.0% | 86.6% | 1.03 |
| glove+hash | 88.0% | 76.0% | 84.6% | 1.10 |

Not measured here: minilm+hash, bge-small+hash (FastEmbed models download from huggingface.co, which this build environment could not reach). Run `pip install fastembed` and then `python scripts/bench_jde_backbones.py` on a machine that can.

## Remaining errors (holdout)

| Text | Expected | Predicted | Confidence |
|---|---|---|---|
| shutdown spotify app pls | APP | SYSTEM | 0.709 |
| screen is too bright, lower it | SYSTEM | DESKTOP | 0.859 |
| turn off my computer in a minute | SYSTEM | UNKNOWN | 0.177 |
| where'd i put the birthday photos | FILE | KNOWLEDGE | 0.211 |
| from my chats, when is priya's wedding | RAG | UNKNOWN | 0.373 |
| write me a short birthday wish for a friend | KNOWLEDGE | WHATSAPP | 0.823 |
| design a study plan for learning deep learning in 3 months | KNOWLEDGE | RAG | 0.439 |
| mail my manager that I'm working from home today | GOOGLE | UNKNOWN | 0.552 |
| nudge me in half an hour to take the clothes out | REMINDER | UNKNOWN | 0.425 |
| get rid of the steam app | PACKAGE | APP | 0.729 |
| bring all my apps up to date | PACKAGE | SYSTEM | 0.793 |
| tell him yes | CLARIFY | WHATSAPP | 0.648 |

## Wrong auto-executions (all splits)

* [dev] "which day is it today" expected SYSTEM, gated EXECUTE as WEB (0.974)
* [dev] "open yesterday's screenshot" expected FILE, gated EXECUTE as SYSTEM (0.992)
