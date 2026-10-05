# Tanglish Stage 2.1 actionability repair

**Decision: RETRAIN AGAIN. No production or sandbox executor is connected.**
The existing sealed holdout was not opened, inspected, hashed, evaluated, or changed. The original test was not opened in this stage.

## Data and method

Original train plus repair train: 96,000 rows. Original dev plus adversarial dev: 20,000 rows.
The adversarial dev material contains 5,000 action-word noncommands and 5,000 commands/corrections/meta controls. Each set was split in half for threshold calibration and reporting. All examples are synthetic declared programs; none is independent human annotation.
The repair train contains 1,450 complete ten-way minimal-pair families sharing an action, object, and verb across speech acts.
Normalized train/dev overlap: 0. Train unique: 96,000; dev unique: 20,000.
The speech taxonomy is COMMAND, QUESTION, CAPABILITY_QUERY, STATEMENT, HYPOTHETICAL, NEGATED_COMMAND, CORRECTION, CHAT, META_CONTROL, AMBIGUOUS. Execution eligibility is derived from COMMAND, CORRECTION, and META_CONTROL; corrections still require a pending frame.
Original PROHIBITION, DEFINITION, and UNCERTAIN_ASR labels were mapped to NEGATED_COMMAND, CHAT, and AMBIGUOUS for training.

| Speech act | Train count | Share | Inverse-frequency weight (descriptive only) |
|---|---:|---:|---:|
| AMBIGUOUS | 6,884 | 7.2% | 1.39 |
| CAPABILITY_QUERY | 1,564 | 1.6% | 6.14 |
| CHAT | 2,624 | 2.7% | 3.66 |
| COMMAND | 68,344 | 71.2% | 0.14 |
| CORRECTION | 1,660 | 1.7% | 5.78 |
| HYPOTHETICAL | 2,535 | 2.6% | 3.79 |
| META_CONTROL | 1,558 | 1.6% | 6.16 |
| NEGATED_COMMAND | 5,659 | 5.9% | 1.70 |
| QUESTION | 2,566 | 2.7% | 3.74 |
| STATEMENT | 2,606 | 2.7% | 3.68 |

The speech and binary gate heads used 96,000 rows and sklearn `class_weight=balanced`; the action head used all 96,000 rows. The weight column describes the resulting distribution. A one-in-eight COMMAND sampling experiment reduced speech accuracy to 73.11% and hierarchical command recall to 25.88%; it was rejected.
The common word 1–3 gram TF-IDF vector feeds both architectures. Architecture A sums executable speech-class probabilities and runs the action head only above threshold. Architecture B uses a binary hierarchical gate before the same action and slot probes. These are linear baselines, not a neural shared semantic encoder.

## Development evaluation

Thresholds were selected on 10,000 calibration rows using the highest command recall subject to ≥99% precision and <0.5% false-action rate. The other 10,000 development rows supply the table below. These are related synthetic families, so the numbers can be optimistic.

| Architecture | Threshold | Trigger precision | Command recall | False action rate | No-action specificity | Speech act accuracy | Action concept accuracy | Negation recognition | Brier | ECE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| shared_multitask | 0.9348 | 99.36% | 39.68% | 0.51% | 99.49% | 74.10% | 88.73% | 63.44% | 0.0868 | 0.0453 |
| hierarchical_gate | 0.9114 | 99.45% | 49.14% | 0.54% | 99.46% | 74.10% | 88.73% | 63.44% | 0.0742 | 0.0548 |

No-action specificity is 1 minus false-action rate. SafetyWeightedError penalizes false actions by 10, or 20 for a high-risk action concept; missed actions cost 2. The class and cost values are experimental, not production policy.

| Architecture | TP | FP | FN | TN | SafetyWeightedError/row |
|---|---:|---:|---:|---:|---:|
| shared_multitask | 2643 | 17 | 4018 | 3322 | 0.8226 |
| hierarchical_gate | 3273 | 18 | 3388 | 3321 | 0.6966 |

Full precision–recall arrays, threshold options, and confidence histograms are in the ignored local `data/tanglish/generated/stage21/evaluation.json`. Calibration here means threshold selection; probability calibration was measured with Brier/ECE but no post-hoc calibrator was fitted.

### Speech-act confusion matrix

Rows are truth, columns are prediction; class order:
`AMBIGUOUS, CAPABILITY_QUERY, CHAT, COMMAND, CORRECTION, HYPOTHETICAL, META_CONTROL, NEGATED_COMMAND, QUESTION, STATEMENT`

```text
AMBIGUOUS              378     0     0   285     0     0     1    37     0     0
CAPABILITY_QUERY         0   171     0     0     0     0     0     0   183     0
CHAT                   119     0   198    99     0     0     3     9     0     0
COMMAND                 44     0     3  4984     8     0     4     0     0     0
CORRECTION             148     0     0   279   456     0     1     0     0     0
HYPOTHETICAL             0     0     0    34     0   324     0    40     0     0
META_CONTROL             0     0     0   498     0     0   235     1     0     0
NEGATED_COMMAND         31     0     1   175    16     0     0   387     0     0
QUESTION                 5     0     2   173     0     0     2    34   213     0
STATEMENT                5     0     1   346     0     0     3     0     0    64
```

## Verb sense and contextual probes

| Surface family | Rows | ActionConcept accuracy |
|---|---:|---:|
| maathu | 505 | 72.87% |
| kudu | 522 | 75.86% |
| eduthu | 248 | 77.02% |
| podu | 613 | 79.12% |
| paaru | 280 | 80.36% |
| sollu | 83 | 91.57% |
| pannu | 3235 | 85.84% |
| anupu | 244 | 83.61% |

Synthetic context-reference target accuracy: 100.00%. Synthetic correction-recipient accuracy: 100.00%. These probes do not measure general reference or correction accuracy.

## Typed slots and remaining gaps

The offline slot probe extracts explicit target, recipient, ordinal, file type, application, and destination relations. It leaves absent values unresolved; it does not authorize any action. Its synthetic label support is sparse and partly inconsistent, so the following is diagnostic only.

| Slot | Gold positives | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| target | 5000 | 100.00% | 94.84% | 97.35% |
| recipient | 2332 | 100.00% | 100.00% | 100.00% |
| sender | 0 | N/A | N/A | N/A |
| application | 426 | 100.00% | 95.31% | 97.60% |
| file | 0 | N/A | N/A | N/A |
| folder | 0 | N/A | N/A | N/A |
| file_type | 467 | 100.00% | 94.86% | 97.36% |
| message_content | 0 | N/A | N/A | N/A |
| query | 0 | N/A | N/A | N/A |
| date | 0 | N/A | N/A | N/A |
| time | 0 | N/A | N/A | N/A |
| time_range | 0 | N/A | N/A | N/A |
| number | 0 | N/A | N/A | N/A |
| quantity | 0 | N/A | N/A | N/A |
| ordinal | 2691 | 100.00% | 100.00% | 100.00% |
| source | 0 | N/A | N/A | N/A |
| destination | 415 | 100.00% | 100.00% | 100.00% |
| device | 0 | N/A | N/A | N/A |
| browser_tab | 0 | N/A | N/A | N/A |
| attachment | 0 | N/A | N/A | N/A |
| include_constraint | 0 | N/A | N/A | N/A |
| exclude_constraint | 0 | N/A | N/A | N/A |

Observed-slot micro precision/recall/F1: 100.00% / 97.33% / 98.65%. Exact match across supported slots: 93.96% on 5,000 development rows.
Unlabelled requested slots, include/exclude constraints, correction application, temporal constraints, and typed reference resolution have no valid accuracy estimate. Whole SemanticFrame exact match is likewise unmeasured.
Capability Recall@1/3/5, MRR, selection confusion pairs, sandbox execution, verified action accuracy, and false-success rate are unmeasured because the semantic frame fails the gate. No test or sealed holdout evaluation was performed.

## Runtime and recommendation

Offline semantic inference p50/p95/p99: 2.92/14.59/17.32 ms per request on this machine. Training plus development evaluation took 33.9 seconds. The model uses CPU; GPU VRAM use for this benchmark is zero. The local candidate pickle is 32.9 MB. Peak RAM was not measured.
The dominant failures are speech-act confusions around corrections, meta controls, questions and ambiguous wording, followed by missing typed slots. The targets of ≥99% trigger precision, <0.5% false actions, ≥95% command recall, ≥95% speech accuracy, ≥99% negation recognition, and ≥99% no-action specificity are **not jointly met**. Further work needs independently reviewed labels, better correction/context supervision, and a trained slot decoder before any test or sealed holdout run.
