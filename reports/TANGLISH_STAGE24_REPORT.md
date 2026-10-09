# Tanglish Stage 2.4 development report

**Recommendation: RETRAIN AGAIN, starting with the data.** The required tiny-overfit check passed under full E5-small fine-tuning, but the existing synthetic corpus failed the training-data quality gate. No general Stage 2.4 candidate was trained or calibrated. The original Stage 2 TEST and sealed HOLDOUT remain unopened; no production route, sandbox tool, WhatsApp message, or external action was used.

## Architecture and model selection

Lane 0, the existing fast word/structural gate, was preserved. The Stage 2.3 frozen encoder and shared classification/retrieval projection remain a rejected baseline. The Stage 2.4 prototype uses a trainable transformer with separate pooled classification heads and token-level BIO slot tags. Capability retrieval keeps the existing lexical candidate generator and a **separate pretrained embedding**, with structured reranking of their candidate union. Neither classifier logits nor its trained projection are used as capability embeddings.

The experiment used [multilingual E5-small](https://huggingface.co/intfloat/multilingual-e5-small) under its MIT license, pinned at revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`. Its `model.safetensors` is 470,641,600 bytes with SHA-256 `1a55775f53449dac10a2bcbc312469fac40b96d53198c407081a831f81c98477`. The complete local file manifest is ignored under `models/tanglish_stage24/encoders/multilingual-e5-small/`. The prototype has **117,670,315 parameters** when fully trainable. A 13-family semantic ontology covers all 62 existing ActionConcepts; it preserves fine distinctions such as SEND/FORWARD and CHECK/VERIFY under coarse families rather than collapsing them to tool IDs. The SpeechAct hierarchy distinguishes action-oriented, non-action, and uncertain before the fine label.

Three compact multilingual representations were compared on **25 authored semantic positive/hard-negative pairs** and a separate, noisy synthetic 500-train/200-development ActionConcept nearest-neighbor probe:

| Base representation | Pair positive above hard negative | Action Recall@1 | Cross-language pair success |
|---|---:|---:|---:|
| Multilingual MiniLM | 44% | 33.0% | 1/10 |
| Multilingual E5-small | 40% | 31.0% | 0/10 |
| Potion multilingual static embeddings | 44% | 29.5% | 0/10 |

These small authored pairs are a diagnostic, **not independent generalization evidence**. The action probe inherits synthetic labels. Raw pretrained embeddings do not handle the English/Romanized-Tamil equivalents well; E5-small was chosen as a compact trainable architecture probe, not as an accepted language model. Potion's static token representation is not an equivalent transformer fine-tuning target. Raw measurements are in ignored `data/tanglish/generated/stage24/encoder_benchmark.json`.

## Data quality gate

The [data-quality audit](TANGLISH_STAGE24_DATA_QUALITY.md) read 80,000 Stage 2 train, 10,000 Stage 2 development, 16,000 repair-train, and 10,000 repair-development rows; it did **not** read TEST or HOLDOUT. A stratified 355-row train sample was reviewed. Among 9,875 Stage 2 rows labelled English, **7,424 contain clear Tanglish markers**. All 4,000 Stage 2 train rows in the correction category carry the fine label COMMAND, while the repair corpus uses CORRECTION. Reviewed ASR rows included corruptions that removed or changed the actionable meaning; reviewed action/object pairs and corrections also contained malformed cases. The sample has zero normalized exact train/development overlap, but that does not establish near-duplicate or semantic-family isolation.

These are upstream label and meaning-preservation failures. The existing 96,000 train rows were **not** silently relabelled or fine-tuned as trustworthy Stage 2.4 supervision. The Stage 2 `asr_noise` category is quarantined until each corruption is linked to a clean source and checked for semantic equivalence. English labels require token-level review; the correction policy and object affordances require validated processed copies. No 20,000-pair contrastive set, balanced 10,000-row English set, full 33-slot span corpus, or independent contextual/constraint set was accepted for training.

## Mandatory tiny-overfit test

The authored diagnostic has 48 **TRAIN-only** utterances, eight ActionConcepts, six SpeechActs, and explicit active character spans for eight slot types where present. It includes questions, capability queries, statements, prohibitions, and corrections. The BIO head tags active spans; superseded mentions are outside tags. This set is too small and too constructed for a development accuracy claim.

The tiny check used supervised heads only. **No contrastive fine-tuning, compact WorkingContext encoding, all-33-slot decoder, or general-data training was run** after the data gate failed.

| Strategy | Trainable parameters | Device | SpeechAct train fit | ActionConcept train fit | Slot-positive train F1 | Exact slot sequences |
|---|---:|---|---:|---:|---:|---:|
| Frozen encoder, trained heads | 16,555 | CPU | 89.6% | 100% | 61.4% | 54.2% |
| Final two transformer layers | 3,565,483 | CPU | 100% | 100% | 74.5% | 62.5% |
| Rank-8 query/value LoRA, final four layers | 65,707 | RTX 3050 | 91.7% | 97.9% | 71.9% | 50.0% |
| Full encoder | 117,670,315 | RTX 3050 | **100%** | **100%** | **100%** | **100%** |

The full model reached the tiny fit criterion at epoch 25 in 44.4 seconds, with 2.27 GB peak VRAM and about 1.59 GB process RSS. Its coarse SpeechAct, ActionFamily, execution eligibility, and negation training labels also fit 100%. The frozen, final-layer, and LoRA runs did not fit slot spans near perfectly under these settings. Full fine-tuning is **possible on this hardware for a tiny batch**; this is not evidence that full fine-tuning will generalize or fit a larger corpus. The raw per-epoch diagnostics are in ignored `data/tanglish/generated/stage24/tiny_overfit_*.json`. A slot-loss imbalance was identified in an initial frozen run and corrected before the reported comparison.

## Capability retrieval

The offline prototype unions top-20 lexical and top-20 pretrained E5 candidates, then reranks using oracle ActionConcept/domain/resource fields, required slots, and explicit family exclusions. Live availability remains unknown; risk remains metadata rather than semantic truth. On the **18 previously authored oracle-frame confusion cases**, lexical Recall@1 was 83.33%; hybrid Recall@1 was **94.44%**, Recall@3/5/10 were 100%, and MRR was 0.963. One top-1 miss was web search versus website opening. The result is comparable to the Stage 2.2 frame-aware reranker and far too small to justify acceptance. The required **1,500–3,000 independent, naturally worded capability queries do not exist yet**; registry-derived paraphrases remain excluded from independent accuracy claims. The 150-capability registry was not invoked. Detailed ranks are in ignored `data/tanglish/generated/stage24/capability_hybrid_18.json`.

## Runtime

The figures below are **base encoder forward timing**, not an end-to-end trained Stage 2.4 route. Each uses 60 sampled development inputs with five warmups, batch size one. Tokenization, slot decoding, retrieval, planning, and policy are outside the timed forward phase.

| Base encoder | p50 / p95 / p99 warm forward | Cold load | Peak process RSS | Peak VRAM |
|---|---:|---:|---:|---:|
| Multilingual MiniLM CPU | 24.22 / 39.75 / 43.16 ms | 1.26 s | 1.34 GB | N/A |
| Potion multilingual CPU | 0.36 / 0.80 / 1.58 ms | 2.42 s | 1.78 GB | N/A |
| E5-small CPU | 33.75 / 65.40 / 92.18 ms | 6.79 s | 1.29 GB | N/A |
| E5-small RTX 3050 | 16.46 / 18.22 / 22.07 ms | 2.68 s | 1.58 GB | 459 MB |

The measured E5 forward pass fits the requested semantic-lane budget, but an end-to-end p95 was **not measured**. The existing Lane 0 was unchanged. Raw timings are in ignored `data/tanglish/generated/stage24/latency_dev.json`.

## Development acceptance and comparison

| Metric | Stage 2.2 final | Stage 2.3 rejected | Stage 2.4 |
|---|---:|---:|---:|
| Action trigger precision | 99.65% | 99.66% | N/A: no general candidate |
| Executable command recall | 47.41% | 39.07% | N/A |
| False action rate | 0.32% | 0.26% | N/A |
| UNCERTAIN | 42.29% | 44.63% | N/A |
| Fine SpeechAct accuracy | 73.72% | 63.16% | N/A |
| Fine ActionConcept accuracy | 89.56% | 33.09% | N/A |
| Slot F1 | Limited six-slot Stage 2.2 probe | Seven-field presence 65.67% | N/A beyond tiny train fit |
| Independent capability Recall@5 | N/A | N/A | N/A; 18 oracle cases only |

Stage 2.4 **train/calibration/development gaps, balanced English/Tanglish/mixed/ASR/contextual metrics, verb-sense accuracy, negated-command understanding, correction-value accuracy, slot span and typed-value development F1, slot value exact match, SemanticFrame exact match, reference resolution, ECE, Brier score, calibration curves, and end-to-end verified action accuracy are N/A**. Computing those from the 48-row training sanity check or from the known flawed corpus would be misleading. No Stage 2.4 thresholds were calibrated, because representation training was not frozen on a validated general corpus.

**Next gate:** repair and validate the processed training labels and meaning-preserving pairs, build independent balanced development strata and full typed slot/value annotations, then fine-tune and evaluate a general model. Preserve the lexical retriever and separate pretrained capability embedding during that work. Until those gates pass, **do not open TEST or HOLDOUT and do not connect Stage 2.4 to production.**
