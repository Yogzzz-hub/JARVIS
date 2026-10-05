# Tanglish Stage 2.2 development report

**Recommendation: RETRAIN AGAIN.** The candidate remains offline; the original test and sealed holdout were not opened or evaluated.

## Architecture and data

The Stage 2.1 word TF-IDF binary gate is Lane 0. Scores below `T_NO_ACTION` return NO_ACTION; scores above `T_EXECUTE` produce EXECUTE_CANDIDATE; the middle goes to a word-plus-character 2–4 gram linear semantic fallback that reuses the word features. That fallback has its own no-action and candidate thresholds. A narrow full-action prohibition check overrides candidate routing while leaving object exclusions in the frame. Cases left between the thresholds require planner review or clarification. EXECUTE_CANDIDATE is a semantic label and never invokes a tool.
The fallback was trained on the existing 80,000 Stage 2 train and 16,000 repair-train rows. No new large corpus was generated. Original Stage 2 dev and the two 5,000-case adversarial development sets were partitioned by stable ID or minimal-pair family before threshold tuning; one half calibrated the thresholds and the other half supplied the results below. The fallback is a second encoder, so this is not the requested one-pass multitask or contrastive model.
Calibration rows: 9,842. Development evaluation rows: 10,158. The repair development partition has 865 calibration and 909 evaluation minimal-pair families with zero family overlap. Public corpora were not relabelled as executable commands.

## Tri-state actionability

| Threshold | Value |
|---|---:|
| T_NO_ACTION | 0.2632 |
| T_EXECUTE | 0.9357 |
| Semantic no-action | 0.4154 |
| Semantic candidate | 0.9757 |

| Metric | Fast lane | After fallback |
|---|---:|---:|
| Action trigger precision | 99.65% | 99.65% |
| Candidate command recall | 38.82% | 47.41% |
| False action rate | 0.26% | 0.32% |
| False NO_ACTION on true commands | 0.51% | 0.75% |
| Uncertain | 51.28% | 42.29% |

FastPathCoverage: 48.72%. SemanticEscalationRate: 51.28%. PlannerEscalationRate: 42.29%. Candidate action F1: 64.25%. These candidate metrics do not count uncertain requests as completed actions.
Fine SpeechAct accuracy: 73.72%. ActionConcept accuracy: 89.56%. NEGATED_COMMAND speech recognition: 62.81%. Explicit negated-command blocking: 100.00% on the synthetic development labels. The check is grammar-limited and does not establish broad negation understanding. Fine speech and action heads are carried over from Stage 2.1.
Risk-conditioned execution thresholds were not applied to semantic truth. Every candidate still needs a complete frame, capability, and downstream policy decision. The risk table below groups by ActionConcept proxy, not by an executed capability.

| Risk proxy | Rows | False action rate | False candidates |
|---|---:|---:|---:|
| DESTRUCTIVE | 342 | 0.85% | 1 |
| EXTERNAL_EFFECT | 1327 | 0.24% | 1 |
| PRIVILEGED | 318 | 0.00% | 0 |
| READ_ONLY | 1647 | 0.18% | 1 |
| REVERSIBLE | 6524 | 0.35% | 8 |

## Language and failure clusters

| Language | Rows | Trigger precision | Candidate recall | False action rate | SpeechAct accuracy | ActionConcept accuracy |
|---|---:|---:|---:|---:|---:|---:|
| english | 632 | 100.00% | 25.16% | 0.00% | 100.00% | 100.00% |
| mixed | 882 | 100.00% | 74.08% | 0.00% | 74.94% | 94.22% |
| tanglish | 8644 | 99.58% | 47.46% | 0.35% | 71.67% | 88.32% |

| Construction category | Rows | Candidate recall | Uncertain |
|---|---:|---:|---:|
| ambiguous_no_action | 255 | 0.00% | 0.00% |
| asr_noise | 264 | 5.78% | 69.70% |
| clear | 966 | 24.22% | 75.57% |
| code_switch | 517 | 74.08% | 25.92% |
| contextual | 498 | 63.05% | 36.95% |
| correction | 258 | 76.36% | 23.64% |
| natural_tanglish | 744 | 41.94% | 57.80% |
| negation | 265 | 0.00% | 0.00% |
| non_command | 237 | 0.00% | 0.00% |
| paraphrase | 471 | 99.15% | 0.85% |
| repair | 5190 | 39.88% | 44.41% |
| typo_phonetic | 493 | 46.45% | 53.55% |

The largest unresolved cluster is genuine commands routed to UNCERTAIN. A much smaller number of commands enter NO_ACTION. The existing fine speech head still confuses corrections, meta controls, questions and statements with commands; the [Stage 2.1 matrix](TANGLISH_ACTIONABILITY_REPAIR.md) gives counts. Noisy and ASR-like categories are synthetic and have limited coverage. Prosody was unavailable.
Verb-sense accuracy was not re-estimated under this new partition; the prior [Stage 2.1 per-family results](TANGLISH_ACTIONABILITY_REPAIR.md) remain the relevant diagnostic. A new contrastive representation or weighted neural multitask loss was not trained.

## Typed frame and constraints

The offline typed frame defines all 33 requested slot names and uses ContactRefCandidate, FileRefCandidate, AppRefCandidate, BrowserTabRefCandidate, and TemporalRange values where grounded. It extracts some corrections, exclusions, ordinal, numeric, temporal, and contextual references. Unsupported or unresolved values remain empty. It has no executor access.
On 17 hand-specified development probes, **selected annotated fields only** scored precision 100.00%, recall 100.00%, F1 100.00%, and selected-field exact match 100.00%. The probes were inspected during implementation; these scores are sanity checks, not independent validation.
The earlier 5,000-row synthetic probe for six supported slots scored micro F1 98.65% and limited-slot exact match 93.96%. Many required slots have zero gold support. Full SemanticFrame exact match, general correction accuracy, constraint accuracy, and reference-resolution accuracy are **not measured**. The frame probe's per-slot counts are in the ignored local `data/tanglish/generated/stage22/frame_probe.json`.

## Capability ranking

The existing registry has 150 capabilities. Eighteen independently specified confusion cases were ranked with its lexical retriever, then with a frame-aware reranker using action, domain, resource, schema compatibility, and registry descriptions. Live availability was not checked.
| Rank metric | Existing lexical | Frame aware |
|---|---:|---:|
| Recall@1 | 83.33% | 94.44% |
| Recall@3 | 83.33% | 100.00% |
| Recall@5 | 88.89% | 100.00% |
| Recall@10 | 94.44% | 100.00% |
| MRR | 0.856 | 0.963 |
The small authored set includes file versus web search, WhatsApp versus Gmail send, file versus shortcut delete, app versus URL open, and git versus system status. The registry lacks a phone-call mute capability and separate project-status capability, so those requested confusion pairs cannot be scored against a real gold capability. This ranking score is not representative capability accuracy. No capability was invoked.

## Latency and acceptance

| Offline phase | p50 ms | p95 ms | p99 ms |
|---|---:|---:|---:|
| input | 0.01 | 0.01 | 0.01 |
| word_encoder | 1.58 | 2.17 | 3.24 |
| fast_gate | 0.63 | 0.91 | 1.41 |
| semantic_fallback | 2.68 | 3.65 | 4.42 |
| action_head | 0.00 | 20.19 | 23.70 |
| total | 5.26 | 24.65 | 29.48 |

Capability ranking averaged 7.38 ms per authored case including one-time registry/index construction; it was not timed as a warmed runtime component. English-only latency was not measured separately. The Stage 2.1 model artifact is 32.9 MB and the fallback artifact is 0.8 MB. Peak RAM and VRAM were not measured. The linear fallback runs on CPU and does not use GPU VRAM.
**Sandbox action precision, action recall/F1, ExactVerifiedActionAccuracy, and FalseSuccessRate: N/A.** Semantic candidate recall, complete slots, and general capability accuracy are below the evidence needed for a meaningful sandbox execution benchmark. No external messages, destructive tools, or live JARVIS actions were run.
The fast path covers less than the 60–80% target, and after fallback only about half of true commands become executable candidates. The substantial UNCERTAIN share is correctly withheld for planner or clarification, but no measured planner resolves it. The original test and sealed holdout remain unopened. **Final recommendation: RETRAIN AGAIN.**
