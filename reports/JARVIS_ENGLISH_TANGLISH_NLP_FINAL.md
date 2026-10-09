# Unified English + Tanglish NLP — provisional development report

**Deployment decision: MORE_DEVELOPMENT_REQUIRED. CURRENT_PRODUCTION remains unchanged; shadow is OFF.**

Human audit: **DEFERRED / NOT COMPLETED**. Training quality: **PROVISIONAL**. Final production acceptance: **NOT HUMAN-VALIDATED**. These synthetic/AI-assisted measurements are not real-world production accuracy.

## Provenance and admission

738 LIKELY_APPROVE rows admitted as AI_PRECHECK_ACCEPTED for this development run only. Ten MANUAL_REVIEW rows and two LIKELY_REJECT rows were excluded and retained separately as HUMAN_REVIEW_DEFERRED. No flagged row entered any partition. Existing human history remains 10 owner REJECT decisions, 0 APPROVE, 0 FIX_LABEL; AI suggestions were not converted into human decisions.

The original 30,000-row Stage 2.5 corpus, 750-row audit queue, original annotations and frozen manifest are unchanged. Frozen verification passes. The new manifest is separate and content-addressed; its creation timestamp is recorded in created.json alongside it.

Active dataset directory: `data\nlp_provisional\74c9cca56834dbca2eaa9d74ec63d2326733e2e55ff51f12760e96e6a68d07eb`.
Manifest: `stage25_ai_provisional_manifest_4933561680de0b9c7209dbbbbdcdaf33ff5a2397b893149ce7c5d5549c7f3eaf.json`; SHA-256 `4933561680de0b9c7209dbbbbdcdaf33ff5a2397b893149ce7c5d5549c7f3eaf`.
External AI-precheck SHA-256: `29a95d7746ba6bdbec10488f194c043430c2c0eeae9db1afdd12d2f073db2447`.

The 738 preserved Tanglish/Tamil rows were combined with 1,616 separately authored provisional English, mixed and mild-ASR examples. One shared frame/action/slot schema is used. No Tanglish translation-first path exists. Raw text, case, technical identifiers, names and punctuation remain available. Normalization collapses whitespace only.

## Partitions and leakage

| Partition | Rows | Families | English | Tanglish | Tamil | Mixed | ASR |
|---|---:|---:|---:|---:|---:|---:|---:|
| DEV | 425 | 85 | 120 | 57 | 48 | 120 | 80 |
| PROVISIONAL_HOLDOUT | 202 | 60 | 45 | 53 | 29 | 45 | 30 |
| TEST | 91 | 40 | 16 | 32 | 17 | 16 | 10 |
| TRAIN | 1636 | 410 | 427 | 302 | 200 | 427 | 280 |

Family leakage: **0** for unioned construction/isolation-family components and exact normalized duplicate utterances. All authored paraphrases, code-switching variants and ASR children share a family. Hashing whole components produces uneven counts; labels were not used to balance evaluation results. This does not establish that all semantic near-duplicates outside declared families have been discovered.

TEST and PROVISIONAL_HOLDOUT were each consumed once after model/calibration freeze. Consumption markers are created before evaluation reads, and prevent reruns. No TEST/HOLDOUT tuning, retraining or phrase repairs occurred. Existing legacy TEST/sealed HOLDOUT files were not opened. The new holdout is **PROVISIONAL_HOLDOUT**, not a final production-quality evaluation.

## Model and calibration

Model: `intfloat/multilingual-e5-small`, revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`. LoRA query/value adapters on the last four encoder layers plus domain/action/speech/resource/safety and BIO slot heads. Trainable parameters: 122,302. Eight fixed epochs; epoch 8 selected by minimum DEV loss. GPU: RTX 3050 6 GB Laptop GPU. Training elapsed: 82.40 seconds. Peak training RSS: 1938.5 MiB; peak training VRAM: 601.2 MiB.

Selection and confidence calibration used DEV only. Temperature was selected by DEV NLL; escalation threshold by DEV semantic correctness F1; clarification threshold from DEV incorrect-confidence distribution. Execute requires joint action/domain/safety/slot correctness and at least five DEV cases with >=99% precision.

Calibration found **no safe execute threshold**. Executable recommendations are disabled (sentinel threshold 1.01). Temperature 1.0; escalation 0.170769; clarification 0.143627. References require context resolution; negations and unresolved corrections cannot authorize tools.

Model SHA-256: `77f9d185a99765b3d35fa44d7bb74779d49aed64b726b7b84ceb8e7f51677eb2`. Calibration SHA-256: `6714d3d3d834329e6333fd2d4c8afb430367be1296b19be0ac596a045e883ba7`. Frozen configuration SHA-256: `dd2c9130aeb47e1dfb1a0203012416a46521c576e2410d20efa40c9d99756aa1`.

## Separate language benchmarks

All percentages below compare against provisional labels. Slot P/R/F1 measures exact TEXT span boundaries/type, not canonical values or contextual slots. Negation/correction/reference columns are presence-classification accuracy; positive recall and unresolved extraction limitations follow below.

### DEV

| Language | N | Domain | Action | Slot P / R / F1 | Constraints | Negation | Correction | Reference | Speech act | Unknown/clarify |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| ENGLISH | 120 | 60.00% | 13.33% | 0.00% / 0.00% / 0.00% | 100.00% | 99.17% | 87.50% | 100.00% | 92.50% | N/A |
| TANGLISH | 57 | 85.96% | 70.18% | 1.91% / 3.55% / 2.48% | 98.25% | 91.23% | 100.00% | 100.00% | 73.68% | N/A |
| MIXED | 120 | 55.00% | 21.67% | 0.00% / 0.00% / 0.00% | 100.00% | 99.17% | 85.83% | 100.00% | 92.50% | N/A |
| TAMIL | 48 | 77.08% | 60.42% | 1.98% / 3.88% / 2.62% | 97.92% | 95.83% | 97.92% | 100.00% | 77.08% | 0.00% |
| ASR | 80 | 53.75% | 16.25% | 0.00% / 0.00% / 0.00% | 100.00% | 100.00% | 88.75% | 100.00% | 95.00% | N/A |
| ALL | 425 | 62.82% | 29.18% | 1.06% / 1.80% / 1.33% | 99.53% | 97.88% | 90.12% | 100.00% | 88.71% | 0.00% |

Positive recall: negation 98.68%, correction 100.00%, reference 100.00%. Recipient accuracy: 0.00%. Unknown/ambiguous cases: 3.
Executable action precision: N/A; executable action recall: 0.00%; execute recommendations: 0. No execution coverage means precision is N/A, not 100%.

### TEST

| Language | N | Domain | Action | Slot P / R / F1 | Constraints | Negation | Correction | Reference | Speech act | Unknown/clarify |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| ENGLISH | 16 | 6.25% | 6.25% | 0.00% / 0.00% / 0.00% | 100.00% | 93.75% | 100.00% | 100.00% | 81.25% | 100.00% |
| TANGLISH | 32 | 62.50% | 75.00% | 0.00% / 0.00% / 0.00% | 96.88% | 93.75% | 100.00% | 100.00% | 71.88% | 57.14% |
| MIXED | 16 | 0.00% | 6.25% | 0.00% / 0.00% / 0.00% | 100.00% | 100.00% | 100.00% | 100.00% | 93.75% | 100.00% |
| TAMIL | 17 | 88.24% | 82.35% | 0.00% / 0.00% / 0.00% | 100.00% | 100.00% | 100.00% | 100.00% | 88.24% | 100.00% |
| ASR | 10 | 0.00% | 0.00% | 0.00% / 0.00% / 0.00% | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% | N/A |
| ALL | 91 | 39.56% | 43.96% | 0.00% / 0.00% / 0.00% | 98.90% | 96.70% | 100.00% | 100.00% | 83.52% | 70.00% |

Positive recall: negation 90.00%, correction 100.00%, reference 100.00%. Recipient accuracy: 0.00%. Unknown/ambiguous cases: 10.
Executable action precision: N/A; executable action recall: 0.00%; execute recommendations: 0. No execution coverage means precision is N/A, not 100%.

### PROVISIONAL_HOLDOUT

| Language | N | Domain | Action | Slot P / R / F1 | Constraints | Negation | Correction | Reference | Speech act | Unknown/clarify |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| ENGLISH | 45 | 55.56% | 26.67% | 0.00% / 0.00% / 0.00% | 100.00% | 97.78% | 100.00% | 100.00% | 93.33% | N/A |
| TANGLISH | 53 | 77.36% | 77.36% | 0.00% / 0.00% / 0.00% | 100.00% | 90.57% | 98.11% | 100.00% | 73.58% | 100.00% |
| MIXED | 45 | 48.89% | 26.67% | 0.00% / 0.00% / 0.00% | 100.00% | 95.56% | 100.00% | 100.00% | 93.33% | N/A |
| TAMIL | 29 | 79.31% | 37.93% | 1.15% / 2.33% / 1.54% | 100.00% | 100.00% | 96.55% | 100.00% | 82.76% | 0.00% |
| ASR | 30 | 53.33% | 26.67% | 0.00% / 0.00% / 0.00% | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% | N/A |
| ALL | 202 | 62.87% | 41.58% | 0.23% / 0.39% / 0.29% | 100.00% | 96.04% | 99.01% | 100.00% | 87.62% | 50.00% |

Positive recall: negation 90.32%, correction 100.00%, reference 100.00%. Recipient accuracy: 0.00%. Unknown/ambiguous cases: 2.
Executable action precision: N/A; executable action recall: 0.00%; execute recommendations: 0. No execution coverage means precision is N/A, not 100%.

## Capability Brain retrieval

Candidate output is adapted to the existing SemanticFrame contract and CapabilityRetriever; no planner or tool runs. Retrieval uses predicted domain/action/resource/slot evidence, never gold labels. Correct-frame-only capability recall is not established: complete frame/slot/reference correctness is not available. End-to-end recall is shown without conflating it with action accuracy. Gold capability IDs exist only on a subset of authored examples; the 738 source rows have no independent capability gold. Invalid/unavailable registry targets remain misses and are listed explicitly.

| Partition | Cases | Recall@1 | Recall@3 | Recall@5 | Recall@10 |
|---|---:|---:|---:|---:|---:|
| DEV | 240 | 33.75% | 68.33% | 78.75% | 79.17% |

DEV missing registry gold IDs: `['google.drive_search']`.
| TEST | 0 | N/A | N/A | N/A | N/A |

TEST missing registry gold IDs: `[]`.
| PROVISIONAL_HOLDOUT | 80 | 40.00% | 40.00% | 40.00% | 40.00% |

PROVISIONAL_HOLDOUT missing registry gold IDs: `['google.drive_download']`.

DEV-only gold-frame oracle (240 cases): Recall@1 66.67%, @3 83.33%, @5 83.33%, @10 83.33%. This holds semantic labels correct to isolate retrieval, without tuning the candidate. Oracle @5 remains below 98%, so retrieval/registry coverage also fails independently of frame prediction.

## Safety and failures

No candidate tool execution exists. All EXECUTE recommendations were disabled because DEV calibration failed. Zero decision-level false actions/recipient/negation/correction violations therefore reflects **zero execution coverage**, not acceptance. Raw semantic errors remain safety risks.

| Partition | Raw wrong action | Raw wrong domain | Raw wrong recipient | Missed negation | Missed correction | Execute recommendations | False-action recommendations | Critical execution failures |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DEV | 301 | 158 | 25 | 1 | 0 | 0 | 0 | 0 |
| TEST | 51 | 55 | 5 | 2 | 0 | 0 | 0 | 0 |
| PROVISIONAL_HOLDOUT | 118 | 75 | 9 | 3 | 0 | 0 | 0 | 0 |

Wrong action/domain/recipient counts overlap across examples. Structured correction reconstruction and typed reference resolution are **not implemented/validated** by presence classification, and remain acceptance blockers. Failure categories and predictions are retained in offline evaluation artifacts. They are not automatically admitted to future training.

## Latency and resource use

| Partition | Total p50 ms | Total p95 ms | Startup ms | First route ms | Loaded process RAM MiB | Post-evaluation RAM MiB | VRAM MiB | CPU average % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DEV | 10.37 | 15.45 | 6800.54 | 770.29 | 1286.5 | 1629.7 | 458.4 | 89.5 |
| TEST | 17.31 | 24.40 | 12473.58 | 785.68 | 1283.9 | 1643.9 | 458.4 | 77.2 |
| PROVISIONAL_HOLDOUT | 16.10 | 23.26 | 9673.99 | 875.95 | 1284.1 | 1644.1 | 458.4 | 89.1 |

Startup includes tokenizer/model initialization in a new process; OS/disk caches were not flushed. First-route latency is reported separately and exceeds the hot-path target. RAM measures this Python process, not whole-machine idle RAM. CPU percentage is one-core-equivalent process CPU/wall time. Warm p50/p95 includes normalization, tokenization, encoder, frame construction and existing capability retrieval; no network or deep LLM is in the candidate path.

| Component (provisional holdout) | p50 ms | p95 ms |
|---|---:|---:|
| encoder_ms | 12.612 | 18.848 |
| frame_ms | 0.747 | 1.198 |
| normalization_ms | 0.002 | 0.004 |
| retrieval_ms | 1.951 | 2.976 |
| tokenization_ms | 0.554 | 0.871 |
| total_ms | 16.104 | 23.259 |

## CURRENT vs CANDIDATE

CURRENT was benchmarked on DEV before candidate training. The comparison uses **offline SmartRouter.preview**, with model/planner/network calls disabled and a partial ontology adapter. This is not full live production routing. Production slot spans and speech acts are absent from that adapter and must not be treated as validated production failures or as evidence of candidate superiority.

| Partition / language | CURRENT partial action accuracy | Candidate action accuracy | Delta percentage points | CURRENT preview p95 ms | Candidate p95 ms |
|---|---:|---:|---:|---:|---:|
| DEV / ENGLISH | 32.50% | 13.33% | -19.17 | 10.82 | 15.24 |
| DEV / TANGLISH | 5.26% | 70.18% | +64.91 | 21.96 | 16.43 |
| DEV / MIXED | 17.50% | 21.67% | +4.17 | 9.30 | 16.30 |
| DEV / TAMIL | 0.00% | 60.42% | +60.42 | 13.37 | 15.86 |
| DEV / ASR | 28.75% | 16.25% | -12.50 | 7.25 | 15.05 |
| TEST / ENGLISH | 0.00% | 6.25% | +6.25 | 12.65 | 23.83 |
| TEST / TANGLISH | 0.00% | 75.00% | +75.00 | 28.39 | 24.26 |
| TEST / MIXED | 0.00% | 6.25% | +6.25 | 14.09 | 25.47 |
| TEST / TAMIL | 0.00% | 82.35% | +82.35 | 229.86 | 175.43 |
| TEST / ASR | 0.00% | 0.00% | +0.00 | 10.49 | 19.49 |
| PROVISIONAL_HOLDOUT / ENGLISH | 33.33% | 26.67% | -6.67 | 21.08 | 23.63 |
| PROVISIONAL_HOLDOUT / TANGLISH | 1.89% | 77.36% | +75.47 | 24.98 | 24.65 |
| PROVISIONAL_HOLDOUT / MIXED | 20.00% | 26.67% | +6.67 | 15.73 | 22.57 |
| PROVISIONAL_HOLDOUT / TAMIL | 0.00% | 37.93% | +37.93 | 21.94 | 22.77 |
| PROVISIONAL_HOLDOUT / ASR | 33.33% | 26.67% | -6.67 | 12.08 | 22.27 |

Full production English regression gate is **not established**. Candidate action recall and slots fail independently, so no production or shadow recommendation is warranted regardless of preview comparisons.

## Known limitations and next development requirements

- Eight-epoch provisional training underfits action/domain generalization. Entire task families and resource/service domains are withheld; tiny evaluation slices are not representative population estimates.
- Exact-span decoding preserves tokenizer whitespace offsets, causing leading-space boundary mismatches. DEV inspection identified this and slot/type errors. No post-TEST inference repair was applied. A future repair is a schema/span change, not an exact-sentence patch.
- English coverage does not cover all 56 source action labels or 33 slot types. Synthetic question/correction/reference labels need human validation. Unknown/cancel/acknowledgement distinctions, short commands, multi-step planner composition, time/ordinal normalization and canonical slot values remain incomplete.
- ASR samples are mild authored filler/light-verb variations, not a recorded speech recognizer benchmark. Technical-Tanglish and clean/noisy degradation require richer independent cases.
- Reference presence is learned, but typed references use a generic selected-resource placeholder and are not resolved; corrections signal a required validation stage rather than reconstructing all superseded/active slots.
- Capability gold coverage is narrow; some author-assigned targets are absent from the registry. TEST has no capability-gold cases. These deficiencies prevent the Recall@5 acceptance gate.
- Seeds and family splits are repeatable, but CUDA memory-efficient attention warned of nondeterminism. Bitwise training reproducibility was not established.
- Once failed TEST/HOLDOUT examples are intentionally used for development, retire those sets and construct new unseen family-isolated evaluations. Do not retrain directly from this run’s failure artifacts.

## Decision

**MORE_DEVELOPMENT_REQUIRED / KEEP_CURRENT operationally.** No promotion; no runtime routing edit; no live shadow hook. Human validation remains deferred and mandatory before final production acceptance. The audit UI shows AI provisional status, training/evaluation aggregates and shadow OFF; evaluation answers are not exposed in normal review UI.

Verification: 41 backend/data/Stage 2.5 tests, two model-policy/calibration tests and one intercepted browser test passed (44 total). Frozen source verification and frozen model/calibration hash checks pass. Model, split and consumption evidence are preserved in the active run directory.

## STRUCTURAL_REPAIR_V2

**Decision: MORE_DEVELOPMENT_REQUIRED. CURRENT_PRODUCTION unchanged; candidate OFFLINE_DEVELOPMENT; shadow OFF.**

Human audit remains deferred: 10 owner REJECT decisions, no APPROVE/FIX_LABEL decisions. This pass does not seal a human-audited manifest or grant production acceptance. All new data and measurements remain synthetic/AI-assisted development evidence.

### Root causes and repairs

V1 coupled canonical values to brittle BIO boundaries, including tokenizer whitespace. V2 uses 33 independent typed start/end heads, separate closed-value heads for time/date/count/ordinal/number/percentage, and an optional BIO auxiliary loss. Character evidence uses original Unicode codepoints and end-exclusive spans; canonical values are evaluated independently. Technical tokens retain their original spelling.

Recipient, sender and owner reconstruction uses relation markers and action/domain evidence. Numeric time tokens and ontology verbs cannot become contacts merely because they precede a relation marker. Corrections retain superseded and active values. Bare times require context to distinguish morning/afternoon. Typed references remain unresolved and require WorkingContext; NLP never invents a resolved resource. Status queries use CHECK and cannot authorize START/RUN.

The shared action-family/action heads retain the existing 62-action ontology. A coverage audit found missing English/mixed training labels in V1. Newly authored V2 development data covers every action in English, Tanglish and mixed TRAIN. Coverage does not imply that every intent has an executable registered capability.

The capability repair is an offline registry overlay: three existing Drive tool definitions supply metadata without constructing clients or calling tools. Typed domain/action/resource contracts fix namespace/action ambiguity, including Gmail FIND/SEARCH → read/search-email capability. Production registry and router files were not changed.

### Data, coverage and isolation

Active dataset: `data/nlp_structural_v2/56a1248f87921b2c2b2866b319bb6b4f31f7eae586f14c3edd728611507f0970`. Manifest SHA-256: `eb997c7d3bef7240c41f4c7a46052f59e01031b00f9da769ecd36fc269a9120a`. Full action × domain × language × split counts: `coverage_v2.csv`; missing/thin coverage: `coverage_diagnostics.json`.

| Partition | Rows | Declared families | English | Tanglish | Tamil | Mixed | ASR |
|---|---:|---:|---:|---:|---:|---:|---:|
| DEV | 2823 | 82 | 754 | 809 | 208 | 752 | 300 |
| PROVISIONAL_HOLDOUT_V2 | 2718 | 2 | 754 | 752 | 160 | 752 | 300 |
| TEST_V2 | 2718 | 2 | 754 | 752 | 160 | 752 | 300 |
| TRAIN | 8656 | 387 | 2262 | 2558 | 680 | 2256 | 900 |

TRAIN slot-type coverage (TEXT or CONTEXT gold): ASR 12/33, ENGLISH 13/33, MIXED 13/33, TAMIL 32/33, TANGLISH 33/33. Detailed zero-filled TRAIN/DEV counts and missing types are in slot_coverage_development.json. Every type has a head; that does not supply missing positive examples. Action/domain coverage uses the declared supported pair inventory, not the full Cartesian product of every domain and action.


Declared construction-family intersections and exact normalized duplicate intersections: 0. All language and mild-ASR children stay with their parent construction. Only eligible V1 TRAIN/DEV source rows are reused; retired V1 TEST/HOLDOUT rows and their failures were not used.

The fresh authored evaluations reserve two construction families each, with new sample IDs and varied resource identifiers. Entity-value novelty is not guaranteed. This is a narrow synthetic construction benchmark, not a verified natural-language semantic-distance holdout. Shared ontology/primitive clause patterns still exist across families; a comprehensive near-paraphrase independence audit is not established. Native Tamil is limited to ten authored native-verb concepts plus existing source coverage; naturalness and labels still require human validation. These limitations block final production acceptance.

Earlier preflight datasets and interrupted experiments were retired before locked evaluation when development checks revealed role-label defects, identifier shortcuts and repeated Tamil core constructions. One exploratory run completed DEV-only fitting/calibration; its results were discarded. The final dataset uses distinct Tamil constructions across reserved families. None of these preflight candidates is selected.

### Training, selection and calibration

Encoder remains multilingual-e5-small at revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`. Selected experiment: `candidate`. Best epoch: 18; 21 epochs actually run. Selection: DEV objective .4 action + .2 domain + .4 canonical F1; patience 3; minimum improvement .0001. Training elapsed 3531.47 s; maximum observed epoch-end process RAM 2784.2 MiB; peak allocated VRAM 649.3 MiB.

DEV-only calibration: temperature 1, execute threshold 1.010000, escalate 0.777545, clarify 0.508982. Calibration requires at least 20 joint-correctness cases at >=99% observed precision; this is an empirical DEV criterion, not a statistical guarantee. Execute is an offline recommendation only.

Negation, unresolved corrections, references, context dependency and non-command speech acts cannot recommend execution. Zero coverage does not pass. A 50% eligible-command coverage floor is reported as a development usefulness check, not a tuned confidence threshold. CUDA bitwise reproducibility is not established.

Model SHA-256 `c8670d33332c68adce14ad16c966d4a3a768ebfec727124e822cf1ae18f6d065`. Calibration SHA-256 `b70d79b2015fa5c6a64ba574148dfc867df1d57536faac6b54e2c0da0c0dbb96`. Configuration SHA-256 `54f320ff53da2508672f28a9d204e03f53df9b712fe11fdad943fe4be62d55c2`. All inference/training source hashes were frozen before locked evaluation. TEST_V2 and PROVISIONAL_HOLDOUT_V2 each have a one-time consumption claim written before reading; neither influenced training, calibration or candidate selection.

### DEV ablations

| Experiment | Action | Canonical slot F1 | Exact span F1 | Recipient |
|---|---:|---:|---:|---:|
| A: V1 BIO, canonical scoring on V1 DEV | 29.18% | 19.87% | 27.24% | 8.00% |
| B: typed canonical, no BIO loss | 98.87% | 76.31% | 75.77% | 88.17% |
| C: typed canonical + BIO auxiliary | 98.76% | 76.79% | 76.28% | 88.17% |
| D: same typed model, legacy action/language coverage | 78.21% | 73.85% | 73.54% | 88.17% |
| Same selected V2 weights, BIO decoder only | 98.76% | 50.65% | 51.97% | 27.22% |

Selected source ablation: `canonical_aux`. Trainable parameters: 170427; total parameters: 117824187.

B/C/D are rescored under the same final DEV boundary policy. Training uses CUDA FP16 autocast/GradScaler; DEV and inference use FP32. Vectorized typed-head outputs and gradients were checked against separate heads. If the selected model has no BIO loss, its BIO head is untrained and that decoder comparison is diagnostic only. Literal numeric/date/time evidence is preserved beyond the closed training vocabulary. Truncated inputs and ambiguous bare times require clarification; executable recommendations require a known typed capability contract.


B/C use identical TRAIN/DEV, seed, objective and stopping rule; their loss formulation differs. D filters V2 TRAIN by V1 action/language coverage and consequently also changes row count/composition; it is a coverage ablation, not a row-matched causal study. A is historical and uses a different DEV set, so it cannot isolate decoder changes from data/model changes.

E: paired gold-frame oracle on the same 240 V1 DEV cases improves Recall@1/@3/@5/@10 from 66.67/83.33/83.33/83.33% to 100.00%/100.00%/100.00%/100.00%. New V2 DEV oracle (1156 atomic gold cases): 100.00%/100.00%/100.00%/100.00%. This validates the covered contracts, not the entire registry, live availability or composition.

### Separate language and slot benchmarks

| Set / language | N | Domain | Action | Canonical P/R/F1 | Exact span P/R/F1 | Recipient | Sender | Time | Ordinal | Negation positive recall | Correction reconstruction | Reference type | Speech act | Unknown/clarify |
|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| DEV / ASR | 300 | 99.67% | 100.00% | 95.24% / 67.90% / 79.28% | 95.24% / 67.90% / 79.28% | 100.00% | N/A | N/A | N/A | 100.00% | N/A | N/A | 76.67% | N/A |
| DEV / ENGLISH | 754 | 100.00% | 100.00% | 87.23% / 72.35% / 79.10% | 87.23% / 72.35% / 79.10% | 83.33% | N/A | 100.00% | N/A | 100.00% | 94.67% | 100.00% | 98.28% | 100.00% |
| DEV / MIXED | 752 | 99.60% | 99.60% | 95.26% / 72.74% / 82.49% | 95.26% / 72.74% / 82.49% | 100.00% | N/A | 100.00% | N/A | 100.00% | 100.00% | 98.67% | 90.69% | 100.00% |
| DEV / TAMIL | 208 | 96.63% | 93.75% | 59.83% / 50.91% / 55.01% | 69.66% / 60.15% / 64.55% | 57.14% | 0.00% | 93.55% | 33.33% | 100.00% | 86.49% | 100.00% | 91.83% | 66.67% |
| DEV / TANGLISH | 809 | 99.38% | 97.65% | 84.80% / 68.83% / 75.99% | 79.20% / 64.92% / 71.35% | 90.38% | 53.85% | 95.89% | 47.37% | 98.72% | 98.04% | 88.05% | 79.60% | 100.00% |
| DEV / ALL | 2823 | 99.43% | 98.76% | 86.56% / 69.00% / 76.79% | 85.78% / 68.67% / 76.28% | 88.17% | 33.33% | 98.23% | 42.86% | 99.69% | 96.73% | 95.76% | 88.13% | 90.91% |
| TEST_V2 / ASR | 300 | 100.00% | 100.00% | 68.85% / 68.21% / 68.53% | 68.85% / 68.21% / 68.53% | 100.00% | N/A | N/A | N/A | 100.00% | N/A | N/A | 75.00% | N/A |
| TEST_V2 / ENGLISH | 754 | 100.00% | 99.87% | 90.25% / 70.54% / 79.19% | 90.25% / 70.54% / 79.19% | 100.00% | N/A | 100.00% | N/A | 100.00% | 100.00% | 99.33% | 99.60% | 100.00% |
| TEST_V2 / MIXED | 752 | 100.00% | 99.73% | 79.29% / 72.22% / 75.59% | 79.29% / 72.22% / 75.59% | 83.33% | N/A | 100.00% | N/A | 100.00% | 94.67% | 52.00% | 77.66% | 100.00% |
| TEST_V2 / TAMIL | 160 | 100.00% | 100.00% | 85.51% / 70.24% / 77.12% | 85.51% / 70.24% / 77.12% | 100.00% | N/A | 100.00% | N/A | 100.00% | 100.00% | 100.00% | 100.00% | N/A |
| TEST_V2 / TANGLISH | 752 | 100.00% | 97.07% | 74.22% / 73.64% / 73.93% | 74.22% / 73.64% / 73.93% | 83.33% | N/A | 100.00% | N/A | 100.00% | 94.00% | 50.00% | 76.46% | 100.00% |
| TEST_V2 / ALL | 2718 | 100.00% | 99.08% | 79.39% / 71.57% / 75.28% | 79.39% / 71.57% / 75.28% | 91.67% | N/A | 100.00% | N/A | 100.00% | 96.47% | 69.29% | 84.44% | 100.00% |
| PROVISIONAL_HOLDOUT_V2 / ASR | 300 | 100.00% | 99.33% | 86.85% / 67.28% / 75.83% | 86.85% / 67.28% / 75.83% | 100.00% | N/A | N/A | N/A | 100.00% | N/A | N/A | 50.00% | N/A |
| PROVISIONAL_HOLDOUT_V2 / ENGLISH | 754 | 99.73% | 100.00% | 66.75% / 71.06% / 68.84% | 66.75% / 71.06% / 68.84% | 100.00% | N/A | 100.00% | N/A | 100.00% | 100.00% | 99.33% | 99.07% | 100.00% |
| PROVISIONAL_HOLDOUT_V2 / MIXED | 752 | 100.00% | 99.47% | 86.90% / 70.28% / 77.71% | 86.90% / 70.28% / 77.71% | 94.44% | N/A | 100.00% | N/A | 100.00% | 98.67% | 41.33% | 54.52% | 100.00% |
| PROVISIONAL_HOLDOUT_V2 / TAMIL | 160 | 100.00% | 95.62% | 95.20% / 70.83% / 81.23% | 95.20% / 70.83% / 81.23% | 100.00% | N/A | 100.00% | N/A | 100.00% | 100.00% | 100.00% | 88.12% | N/A |
| PROVISIONAL_HOLDOUT_V2 / TANGLISH | 752 | 100.00% | 97.34% | 86.30% / 70.80% / 77.79% | 86.30% / 70.80% / 77.79% | 94.44% | N/A | 100.00% | N/A | 100.00% | 98.67% | 36.00% | 49.60% | 100.00% |
| PROVISIONAL_HOLDOUT_V2 / ALL | 2718 | 99.93% | 98.79% | 80.41% / 70.33% / 75.03% | 80.41% / 70.33% / 75.03% | 97.22% | N/A | 100.00% | N/A | 100.00% | 99.17% | 61.62% | 67.00% | 100.00% |

N/A means no eligible gold cases. Presence accuracy is not substituted for reconstruction or positive recall. Exact-span scores remain sensitive to tokenizer subword/particle boundaries. Canonical scores count typed values, including incorrect/extraneous values. Sender/ordinal and all 33 types are not exhaustively represented in fresh evaluation; focused diagnostics do not substitute for benchmark coverage.

| Set | Recipient gold | Sender gold | Time gold | Ordinal gold | Negation gold | Correction gold | Reference gold | Unknown gold | Eligible commands |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| DEV | 169 | 21 | 453 | 28 | 644 | 490 | 495 | 11 | 1154 |
| TEST_V2 | 144 | 0 | 442 | 0 | 632 | 482 | 482 | 8 | 1114 |
| PROVISIONAL_HOLDOUT_V2 | 144 | 0 | 442 | 0 | 632 | 482 | 482 | 8 | 1114 |

### Capability, safety and executable recommendations

| Set | Capability cases | R@1 | R@3 | R@5 | R@10 | Execute precision | Eligible-command coverage | Critical wrong recommendations | Missed negation | Raw wrong action | Raw wrong domain |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| DEV | 1156 | 98.70% | 99.31% | 99.39% | 99.65% | N/A | 0.00% | 0 | 2 | 35 | 16 |
| TEST_V2 | 1156 | 98.53% | 99.65% | 99.91% | 100.00% | N/A | 0.00% | 0 | 0 | 25 | 0 |
| PROVISIONAL_HOLDOUT_V2 | 1156 | 98.70% | 99.83% | 99.91% | 99.91% | N/A | 0.00% | 0 | 0 | 33 | 2 |

| Set | Raw wrong recipient | Missed correction | Wrong-recipient EXECUTE | Negation EXECUTE violation | Correction EXECUTE violation | Ambiguity EXECUTE violation | False-positive negation | Negation overall accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DEV | 35 | 8 | 0 | 0 | 0 | 0 | 352 | 87.46% |
| TEST_V2 | 101 | 17 | 0 | 0 | 0 | 0 | 488 | 82.05% |
| PROVISIONAL_HOLDOUT_V2 | 10 | 4 | 0 | 0 | 0 | 0 | 1362 | 49.89% |

No tools were executed. Critical counts are wrong offline EXECUTE recommendations scored against measured canonical/action/domain/speech/safety correctness, not claims about real tool incidents or complete frame correctness. Complete constraints, reference typing and resource correctness are not included in this joint calibration criterion. A safe abstention policy cannot compensate for poor recall, low coverage or raw semantic failures. Constraint extraction, cross-domain multi-step composition and contextual reference resolution remain unvalidated; no promotion/rollback or shadow hook was introduced.

### Latency and resources

| Set | Warm p50 ms | Warm p95 ms | First route ms | Startup ms | Loaded RAM MiB | Post RAM MiB | Allocated VRAM MiB | CPU % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DEV | 115.94 | 156.80 | 1377.67 | 27488.77 | 1297.91 | 1689.39 | 482.50 | 29.57 |
| TEST_V2 | 106.10 | 169.97 | 1562.81 | 26468.03 | 1297.83 | 1687.76 | 482.50 | 31.82 |
| PROVISIONAL_HOLDOUT_V2 | 16.31 | 23.47 | 233.75 | 5892.97 | 1296.41 | 1687.55 | 482.50 | 91.94 |

Warm latency excludes the first route and includes tokenization, encoder, canonical/frame construction and offline capability retrieval. Startup measures model/tokenizer initialization in a fresh process after framework imports, without forced cache eviction; full process-launch latency is not measured. RAM is this Python process; VRAM is allocated tensor memory, not whole-GPU utilization; CPU is one-core-equivalent process CPU/wall time. No network or deep LLM participates.

Measured latency varies substantially between the three processes. DEV and TEST_V2 exceed the preferred 150 ms warm p95 target, while the provisional holdout is below it. Other machine activity was not controlled; the cause is not established. No evaluation was rerun to obtain a faster number. The all-measured-runs latency check fails.

### CURRENT versus CANDIDATE and decision

CURRENT production was preview-benchmarked on fresh DEV before training with network/model/planner execution disabled. The adapter is partial and cannot establish a full English regression gate. V2 comparisons use production_baseline_independent_DEV.json, derived solely from recorded intent/slots; SEARCH remains SEARCH without consulting expected labels. The original helper used gold-aware SEARCH/FIND conversion, so its immutable recording is preserved but that conversion is excluded from this comparison. Production paths, registry, planner and tools remain unchanged.

| Provisional holdout gate | Pass |
|---|---|
| action | YES |
| canonical_slot_f1 | NO |
| recipient | YES |
| negation_positive_recall | YES |
| correction_reconstruction | YES |
| reference_typing | NO |
| capability_oracle_at5 | YES |
| end_to_end_capability_at5 | YES |
| zero_critical_recommendations | YES |
| execute_precision | NO |
| useful_execute_coverage | NO |
| warm_p95 | YES |
| human_validation | NO |
| all_measured_warm_p95_within_150_ms | NO |

**MORE_DEVELOPMENT_REQUIRED.** No shadow recommendation or promotion. Human validation, richer independent evaluation families, full production English regression, complete constraints/references/correction coverage and critical semantic safety acceptance remain required. Evaluation failures are recorded only; they are not automatically admitted to training. Once intentionally used for development, these V2 evaluation sets must be retired and replaced.

| DEV language | CURRENT partial action | Candidate action | Delta pp |
|---|---:|---:|---:|
| ASR | 2.67% | 100.00% | +97.33 |
| ENGLISH | 1.72% | 100.00% | +98.28 |
| MIXED | 1.86% | 99.60% | +97.74 |
| TAMIL | 0.00% | 93.75% | +93.75 |
| TANGLISH | 1.61% | 97.65% | +96.04 |

Paired before/after on the same historical V1 DEV: action 29.18% -> 89.65%, canonical slot F1 19.87% -> 45.85%, recipient 8.00% -> 44.00%. This development comparison was not used for model selection.

Focused known development probes: 13/21 cases passed every stated check. These probes are neither training examples nor acceptance evidence. Detailed predicted frames and failed checks are retained in diagnostics_DEVELOPMENT.json.

Top V2 DEV action confusions: [{"count": 3, "gold": "SEND", "predicted": "READ"}, {"count": 3, "gold": "DELETE", "predicted": "CHECK"}, {"count": 2, "gold": "PROVIDE", "predicted": "ANSWER"}, {"count": 2, "gold": "SEND", "predicted": "REPLY"}, {"count": 2, "gold": "COPY", "predicted": "MOVE"}, {"count": 2, "gold": "LIST", "predicted": "SHOW"}, {"count": 1, "gold": "CHECK", "predicted": "CLOSE"}, {"count": 1, "gold": "DELETE", "predicted": "SAVE"}, {"count": 1, "gold": "SHOW", "predicted": "CHECK"}, {"count": 1, "gold": "SHOW", "predicted": "LIST"}, {"count": 1, "gold": "READ", "predicted": "REPLY"}, {"count": 1, "gold": "WRITE", "predicted": "CHECK"}].

Top V2 DEV domain confusions: [{"count": 6, "gold": "FILES", "predicted": "GENERAL"}, {"count": 3, "gold": "GENERAL", "predicted": "FILES"}, {"count": 2, "gold": "CALENDAR", "predicted": "GENERAL"}, {"count": 1, "gold": "FILES", "predicted": "IDE"}, {"count": 1, "gold": "GENERAL", "predicted": "PC"}, {"count": 1, "gold": "GENERAL", "predicted": "BROWSER"}, {"count": 1, "gold": "BROWSER", "predicted": "FILES"}, {"count": 1, "gold": "CONTROL", "predicted": "GENERAL"}].

Top V2 DEV speech-act confusions: [{"count": 291, "gold": "COMMAND", "predicted": "NEGATED_COMMAND"}, {"count": 14, "gold": "COMMAND", "predicted": "STATUS_QUERY"}, {"count": 9, "gold": "CORRECTION", "predicted": "NEGATED_COMMAND"}, {"count": 6, "gold": "COMMAND", "predicted": "CORRECTION"}, {"count": 3, "gold": "CAPABILITY_QUERY", "predicted": "STATUS_QUERY"}, {"count": 2, "gold": "STATUS_QUERY", "predicted": "CAPABILITY_QUERY"}, {"count": 2, "gold": "NEGATED_COMMAND", "predicted": "COMMAND"}, {"count": 1, "gold": "STATUS_QUERY", "predicted": "NEGATED_COMMAND"}, {"count": 1, "gold": "ACKNOWLEDGEMENT", "predicted": "COMMAND"}, {"count": 1, "gold": "QUESTION", "predicted": "HYPOTHETICAL"}, {"count": 1, "gold": "STATEMENT", "predicted": "COMMAND"}, {"count": 1, "gold": "STATEMENT", "predicted": "CORRECTION"}].

Remaining structural gaps: legacy broad domains coexist with explicit service domains; full namespace reconciliation is not established. Canonical scoring includes gold contextual slots although NLP leaves references unresolved. Source/contact distinctions, negation scope, domain/action corrections, short and hypothetical requests and tool-required argument completeness remain incompletely validated. EXECUTE is only an offline semantic recommendation, not proof of tool readiness. Raw negation misses remain semantic safety failures even when abstention suppresses execution. High positive negation recall coexists with many false-positive negations, which suppress valid requests; it is not evidence that negation understanding passes overall.

Verification: 65 unique tests passed, including slot/schema/Unicode/relation/coverage/ASR-family/status-query/offline-registry/policy/consumption and dependency/software drift refusal. Frozen source and owner audit histories remain byte-identical. Detailed verification evidence is stored separately in verification.json.
