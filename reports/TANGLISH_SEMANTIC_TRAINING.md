# Tanglish Stage 2 semantic training report

Date: 2026-10-02. **Recommendation: RETRAIN; do not deploy these models for JARVIS actions.** The action classifier learned the synthetic ontology, but command-versus-no-action recognition is below an acceptable standard. No WhatsApp message or other external action was sent during this work.

## Data and supervision

The [Stage 1 audit](TANGLISH_DATA_AUDIT.md) and `data/tanglish/dataset_manifest.json` were frozen. TanglishSTS stayed evaluation-only; TamilTech-QA stayed quarantined. No source eligibility changed. DravidianCodeMix supplied **aggregate** safe-particle, punctuation, and script counts. The 60,986 license-eligible Aksharantar publisher-train pairs supplied source counts for the transliteration layer; they were **not** converted into action labels or sampled into this semantic classifier. Public-text sampling weight in semantic-head training was **0**; generated JARVIS frames had weight **1**. No private chats were used or uploaded.

The new corpus has **100,000** programmatically supervised examples with all 23 requested SemanticFrame fields, 59 ActionConcepts, and explicit `should_act`. Category totals were 20k clear, 15k natural Tanglish, 10k code-switch, 10k paraphrase, 10k typo/phonetic, 5k ASR-like, 10k contextual, 5k negation, 5k correction, 5k non-command, and 5k ambiguous/hard-negative. The action labels come from declared semantic programs, never from a tool name or from a classifier. At least 20% of every split has previous turns. Common polysemous verbs appear with multiple actions; for example, the train split has 637 `maathu`/CONVERT, 649 CHANGE, 637 REPLACE, 706 SWITCH, 499 SET, and 667 MOVE examples. This is class balance by generation, not proof of natural-language quality.

| Split | Rows | Contextual | No action |
|---|---:|---:|---:|
| Train | 80,000 | 20,273 | 13,325 |
| Dev | 10,000 | 2,338 | 1,669 |
| Test | 5,000 | 1,164 | 834 |
| Locked holdout | 5,000 | 1,136 | 833 |

The locked holdout was generated and sealed, but **never used to select a model or inspect failures**. The builder now refuses to overwrite it. [Leakage audit](TANGLISH_SEMANTIC_LEAKAGE.md): zero exact, normalized skeleton, and construction-family overlap across all split pairs; sampled p95 nearest-token Jaccard to train was 0.682 dev, 0.625 test, 0.633 locked. This remains a synthetic grammar corpus with no independent human annotation. Some constructions are unnatural, and structural checks cannot rule out semantic repetition. Treat the 100k count as an experiment, not a high-quality natural-language milestone.

## Models, hardware, and training

Hardware: RTX 3050 laptop GPU (6 GB), 16.89 GB system RAM. These compact baselines ran on CPU; GPU use was zero. The main model uses a shared 65,536-dimensional character 2–4 gram hashing representation and incremental linear heads for ActionConcept and speech act (`modified_huber`, `alpha=2e-5`, batch 1,000). Domain is derived from the predicted action. It is **not** a neural semantic encoder and has no learned slot head. Dev checkpoints at 10k, 25k, 50k, and 80k train rows took 62.2 seconds including dev evaluation. The 80k checkpoint was selected on dev. A weighted binary action gate (`negative_weight=5`) took another 18.6 seconds. A separate word 1–3 gram TF-IDF/logistic speech baseline took 18.2 seconds. The word model is a second encoder, so the combined prototype does not meet the desired single-encoder, one-pass design.

| Dev checkpoint | ActionConcept accuracy | Speech-act accuracy | No-action specificity | Action Recall@3 |
|---|---:|---:|---:|---:|
| 10k | 93.76% | 83.31% | 0% | 96.85% |
| 25k | 95.83% | 83.31% | 0% | 98.13% |
| 50k | 97.01% | 83.31% | 0% | 98.78% |
| 80k | 97.59% | 83.31% | 0% | 99.14% |

The speech head predicted **COMMAND for all no-action examples**. Its apparent 83% speech accuracy is just the command-class prevalence. The weighted gate threshold was selected from the dev negative-score p99. It reached 98.98% no-action specificity on dev, but only 17.13% command recall. On test it reached 100% no-action specificity and **5.38% command recall**. This is unusable despite the high action-class score.

The alternative word/phrase speech model improved test command recall, with a safety trade-off:

| Test metric | Raw character heads | Weighted gate | Word/phrase speech model |
|---|---:|---:|---:|
| ActionConcept accuracy | 95.28% | 95.28% | 95.28% shared action head |
| Domain accuracy from action | 97.38% | 97.38% | 97.38% shared action head |
| Speech-act accuracy | 83.32% | 12.42% | 81.86% |
| No-action specificity | 0% | 100% | 98.08% |
| False-action rate | 100% | 0% | **1.92%** |
| Command recall | 100% by always acting | **5.38%** | **78.61%** |
| Negation blocking | not reliable | 100% synthetic test | 100% synthetic test |
| Correction action recall | not measured | 12.8% | **55.2%** |

On test, ambiguous-verb ActionConcept accuracy was **89.18%** across 1,460 cases. Action-class Recall@1/3/5 was **95.28% / 97.36% / 98.04%**, MRR **0.966**. These are retrieval over the 59 synthetic action labels, **not** capability-schema Recall@K. The word/phrase gate's test speech accuracy was 84.0% English, 99.6% mixed, and 79.2% Tanglish, but its category scores varied sharply: 43.2% ASR, 63.4% contextual, 55.2% correction, and 74.1% natural Tanglish. Test-set model selection was not performed.

## Pretrained encoder baseline

For 1,200 sampled train examples as a neighbor index and 300 sampled dev queries, untrained ActionConcept nearest-neighbor Recall@1/3/5 was:

| Encoder | Recall@1 | Recall@3 | Recall@5 | Bulk embedding ms/row |
|---|---:|---:|---:|---:|
| Current JDE `hash-4096` encoder | 66.0% | 80.3% | 86.0% | 0.44 |
| [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) | 65.3% | 76.7% | 81.7% | 17.66 |
| [BGE-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5) | 54.7% | 71.3% | 78.7% | 40.21 |

The current language adapter scored 15.54% ActionConcept accuracy and 98.62% no-action specificity on dev, but its action vocabulary is narrower than the 59-class corpus, so that number is only a directional comparison. The [Morgan Tanglish model](https://huggingface.co/vishnu-n/Morgan-Tanglish-v7) was inspected but not benchmarked: its publisher artifact is a 470 MB safetensors model, and this environment has no compatible Transformers/PyTorch runtime installed. FastEmbed-managed MiniLM and BGE cache revisions were checked against Hub model cards; their cache contents are not revision-pinned, so these are exploratory baselines. Neither pretrained retrieval result validates speech act or slots.

## Latency and missing acceptance metrics

The two-encoder action-plus-word-speech prototype took p50 **43.86 ms**, p95 **55.80 ms**, p99 **63.58 ms** per request over 300 test rows on CPU. This includes text preparation, both encoders, action head, speech head, and gate. It excludes capability retrieval, policy, planning, external execution, and verification. Pure English routing was not separately timed end to end.

The prototype does **not** emit or validate target/recipient/source/destination/content/query/temporal/ordinal slots at inference. Therefore slot precision/recall/F1/exact match, constraint accuracy, correction-slot accuracy, reference-resolution accuracy, exact SemanticFrame accuracy, capability Recall@K, and verified end-to-end action accuracy are **not measured**. No claim is made for those metrics. A human-reviewed corpus and a typed slot decoder are required before those numbers can be meaningful. The model was not connected to JARVIS's executor or external capabilities because it fails no-action precision and command recall gates.

## Error clusters and decision

- Character speech head collapses to COMMAND under class imbalance, yielding a 100% false-action rate on test no-action cases.
- Conservative weighted gate removes those false actions but rejects nearly every real command, particularly English and mixed requests.
- Word/phrase gate improves recall but permits 1.92% false actions and handles only 55.2% of correction commands on the synthetic test.
- ASR-like and contextual commands remain weak; artificial syntax variation makes these estimates unreliable for real user speech.
- No trained slot decoder or capability grounding exists, so a correct action concept cannot safely become an executable JARVIS plan.

**Decision: RETRAIN and keep the model offline.** Next work should start with independently reviewed semantic frames and a compact shared encoder with supervised speech act, action, and typed slot heads. Keep the current locked holdout sealed; use dev for training decisions and create a new unseen holdout if it is ever inspected. Scale to 300k only after no-action precision, slot correctness, and end-to-end verified behavior improve on unseen data.

Reproduce from the acquisition environment plus `scripts/requirements_tanglish_stage2.txt`: run the Stage-2 builder once in a clean generated directory, then the leakage audit, training scripts, raw-test evaluator, encoder benchmark, latency measurement, and artifact sealer. Machine-readable build, leakage, training, test, latency, benchmark, and SHA256 records are under `data/tanglish/manifests/`. The corpus, model weights, and encoder caches are Git-ignored; scripts and this report are reviewable.

## Stage 2.1 continuation

The [Stage 2.1 repair report](TANGLISH_ACTIONABILITY_REPAIR.md) compares two shared-representation actionability architectures, adds 10,000 adversarial development examples, and measures a limited typed-slot probe. The outcome remains **RETRAIN AGAIN**. The existing sealed holdout and original test were not used in Stage 2.1.
