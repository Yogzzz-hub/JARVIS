# Tanglish Stage 2.3 development report

**Recommendation: RETRAIN AGAIN.** The Stage 2.3 neural candidate failed the development acceptance gate and remains offline. The original Stage 2 TEST and sealed HOLDOUT were not opened. No capability, sandbox action, external message, or production route was invoked.

## Design and reproducibility

The candidate uses a frozen [multilingual MiniLM encoder](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) (Apache-2.0) through FastEmbed/ONNX, followed by one trainable 384→256→128 shared projection (143,711 parameters; 0.557 MB checkpoint). One encoder pass feeds actionability, SpeechAct, ActionConcept, domain, negation, correction, context-presence, seven slot-presence heads, and a retrieval embedding. The ONNX model file is 224.2 MB. The cached Qdrant ONNX snapshot is `faf4aa4225822f3bc6376869cb1164e8e3feedd0`; the ONNX blob SHA-256 is `634d0f66c29dc934c8fa72b8a4fe91dd4d420a22f1d82a241058d4316e659a99`. The trainable head is a local probe, not a fine-tuned base transformer.

Three pretrained encoders were compared on 800 train neighbors, 250 development queries, and 200 weak hard-pair checks. English MiniLM scored action Recall@1 53.6%; BGE-small-en-v1.5 47.6%; multilingual MiniLM 39.6%. The multilingual model was selected to cover the requested language mix, but the small probe did not predict downstream success. The hard-pair positive is mainly a polite rewrite and is too easy for a strong contrastive claim. Encoder details and raw results are in ignored `data/tanglish/generated/stage23/encoder_benchmark.json`.

Training used 3,500 sampled Stage 2 train rows and 5,000 Stage 2.1 repair-train rows. The sampled SpeechAct distribution was COMMAND 3,442; NEGATED_COMMAND 732; AMBIGUOUS 725; QUESTION 561; HYPOTHETICAL 533; STATEMENT 516; CHAT 509; CORRECTION 509; CAPABILITY_QUERY 489; META_CONTROL 484. It included 7,238 Tanglish, 833 mixed, and 429 English-labelled rows. There were 402 same-family contrastive triplets with a spelling/politeness positive and a question, capability query, statement, or prohibition negative. Positive generation was narrow; it did not supply independent ASR or broad code-switch equivalents. The synthetic source labels expose 10 SpeechAct classes, so INFORMATION_REQUEST, STATUS_QUERY, CONFIRMATION, and ACKNOWLEDGEMENT remain unsupervised.

The frozen embeddings cover 8,500 train, 9,842 calibration, and 10,158 evaluation rows. Calibration and evaluation use the same stable-ID/minimal-pair-family partition as Stage 2.2. Thresholds and checkpoints were chosen on calibration only. Training ran 20 epochs; train loss fell from 8.56 to 2.74 and calibration loss from 7.51 to 4.97. The final gap and poor evaluation metrics indicate weak generalization despite decreasing loss. Stage 2.1's word gate remains Lane 0. Its uncertain cases pass to the neural model; all other uncertain cases remain UNCERTAIN. The Stage 2.2 explicit full-action prohibition guard still overrides candidate decisions. These candidates never execute tools. The older TF-IDF/character fallback remains a baseline and was not replaced in production.

## Actionability on the identical development evaluation partition

| Metric | Stage 2.1 gate at its saved threshold | Stage 2.2 fast gate | Stage 2.2 final | Stage 2.3 fast + neural |
|---|---:|---:|---:|---:|
| Action trigger precision | 99.52% | 99.65% | 99.65% | **99.66%** |
| Executable command recall | 49.15% | 38.82% | **47.41%** | 39.07% |
| False action rate | 0.46% | 0.26% | 0.32% | 0.26% |
| Uncertain | 0% (binary gate) | 51.28% | 42.29% | 44.63% |
| Candidate action F1 | N/A | N/A | 64.25% | 56.14% |

The Stage 2.1 figure applies its saved binary threshold, so its zero UNCERTAIN rate means every rejected command becomes NO_ACTION. The tri-state systems preserve many of those commands for review.

The Stage 2.3 neural fallback added only 17 true candidate commands beyond Lane 0 on 10,158 evaluation rows. Its standalone threshold, calibrated to the same safety target, selected 70 of 6,680 executable commands. Stage 2.3 had 2,610 true candidates, nine false candidates, 4,070 executable commands withheld or missed, and 49 true commands incorrectly returned NO_ACTION. FastPathCoverage is 48.72%; SemanticEscalationRate is 51.28%; PlannerEscalationRate is 44.63%. The neural high-confidence threshold was about 0.999987, a sign of poor calibration/separation. The candidate is below the 90% minimum recall gate and the 15% uncertainty aspiration.

Semantic COMMAND speech recognition was 93.87% on true COMMAND rows, while **executable command recall was 39.07%**. These are different metrics. NEGATED_COMMAND recognition was 29.17%, although all gold negated commands were blocked from EXECUTE_CANDIDATE by the gate. Blocking does not establish understanding of negation. No semantic frame exact match or verified execution was scored.

| Development label metric | Stage 2.2 | Stage 2.3 neural |
|---|---:|---:|
| SpeechAct accuracy | 73.72% | **63.16%** |
| ActionConcept accuracy | 89.56% | **33.09%** |
| Domain accuracy | Not reported | 65.88% |
| Negation binary accuracy | Not reported | 93.02% (imbalanced) |
| Correction binary accuracy | Not reported | 90.78% (imbalanced) |

The full 10-class SpeechAct confusion matrix and per-risk proxy counts are in ignored `data/tanglish/generated/stage23/neural_dev.json`. Important failures include corrections mapped to COMMAND, capability queries mapped to HYPOTHETICAL, and negated commands mapped to COMMAND. The binary negation/correction accuracies are dominated by their negative classes. Train SpeechAct accuracy was 94.91% versus 63.16% on evaluation, a large generalization gap. Train ActionConcept accuracy was only 42.84% and evaluation was 33.09%, showing that the action head also failed to fit the sampled ontology well. Verb-sense accuracy was **not measured**; the action head's 33.09% accuracy makes any derived sense score untrustworthy. Two false candidates occurred in the high-risk ActionConcept proxy stratum; that proxy is not a capability risk assessment.

## Language and construction failures

| Slice | Stage 2.2 candidate recall | Stage 2.3 candidate recall | Stage 2.3 uncertain |
|---|---:|---:|---:|
| English-labelled | 25.16% | **14.40%** | 85.28% |
| Tanglish-labelled | 47.46% | **40.81%** | 43.94% |
| Mixed-labelled | 74.08% | **50.68%** | 43.54% |
| ASR-like category | 5.78% | **4.62%** | 76.89% |
| Clear category | 24.22% | **13.87%** | 85.82% |
| Contextual category | 63.05% | 63.65% | 36.35% |

| Labelled slice | Stage 2.3 SpeechAct accuracy | Stage 2.3 ActionConcept accuracy |
|---|---:|---:|
| English | 97.00% | 60.60% |
| Tanglish | 60.04% | 30.98% |
| Mixed | 69.50% | 34.01% |
| ASR-like category | 60.23% | 39.77% |
| Contextual category | 100.00% | 48.39% |

These labels are synthetic and the slices are not independently balanced. Language-specific slot F1, frame exact match, and latency were not measured. The English-labelled slice has 632 commands and **zero** no-action rows, so its 100% observed trigger precision has no English safety denominator. See the [English/clear audit](STAGE23_ENGLISH_RECALL_AUDIT.md). The ASR/noisy data are synthetic. These results show a broad representation/calibration failure; no phrase-specific patches were added. The largest ActionConcept confusions include SEND→FORWARD (75), CHECK→VERIFY (67), CAPTURE→COPY (36), and PROVIDE→ANSWER (35). The detailed train/calibration/evaluation gap and per-slice counts are in ignored `data/tanglish/generated/stage23/generalization_gap.json`.

## Slot and reference evidence

The head predicts presence for seven supervised fields on 5,190 synthetic repair-development rows: target, recipient, ordinal, file_type, application, source, destination. Presence micro precision was **79.50%**, recall **55.94%**, F1 **65.67%**, and seven-field presence exact match **23.45%**. File type and destination recall were 0%; recipient recall was 22.66%. Presence does not score mention spans, values, entity types, constraints, or runtime resolution. The full 33-slot schema, typed candidates, SemanticFrame exact match, correction-value accuracy, reference-resolution accuracy, and slot-value exact match are **N/A**. Stage 2.2's hand-inspected 17-case typed-frame probe remains a sanity check, not independent validation. The seven-field diagnostic is in ignored `data/tanglish/generated/stage23/slot_presence_dev.json`.

## Capability retrieval

The registry contains 150 capabilities across 13 families. A 1,050-case development probe covers every capability and family, with gold IDs inherited from real registry examples. The query variants paraphrase those examples, which are also indexed by the lexical retriever. **This is an optimistic, non-independent coverage probe, not a valid acceptance benchmark.** All gold IDs exist in the registry; absent conceptual capabilities are not scored.

| Retrieval on registry-derived queries | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR |
|---|---:|---:|---:|---:|---:|
| Existing lexical retriever | 94.67% | 99.05% | 99.05% | 99.24% | 0.968 |
| Pretrained multilingual embedding | 79.81% | 92.29% | 94.95% | 98.57% | 0.867 |
| Stage 2.3 shared projection | **24.19%** | 42.38% | **49.71%** | 63.81% | 0.371 |

The separate 18 authored confusion cases retain a 94.44% frame-aware Recall@1, but are far too small. The learned projection badly damages retrieval. The requested independent 1,000-case capability benchmark and ≥98% independent Recall@5 are unmet. Per-family confusion and full ranks are in ignored `data/tanglish/generated/stage23/capability_dev.json`. Availability, risk metadata at retrieval time, and execution were not tested.

## Runtime and acceptance

On 120 sampled development inputs, CPU batch-one latency was: Lane 0 p50/p95/p99 **1.67/3.82/4.46 ms**; escalated neural phase **24.59/41.61/51.77 ms**; sampled total **25.90/43.87/54.05 ms**. Cold encoder load was 1.23 s. Process RSS peaked at about 1.20 GB in this sample; training was observed near 1.6 GB. GPU and VRAM were not used or measured. These are offline timings, not a production latency guarantee. Raw timing is in ignored `data/tanglish/generated/stage23/latency_dev.json`.

Action precision and false action rate meet the numerical development thresholds, but executable recall, speech acts, action concepts, slot coverage, and retrieval do not. Constraints, typed references, full slots, and end-to-end planning are not meaningfully measured. Sandbox Action Precision/Recall/F1, Execution Success, Verification Accuracy, ExactVerifiedActionAccuracy, and FalseSuccessRate are **N/A**. The model remains unconnected. **Do not open TEST or sealed HOLDOUT. Retrain again with stronger multilingual fine-tuning, more diverse train-only semantic equivalents and hard negatives, complete slot/span supervision, and an independent capability set before reconsidering the gate.**
