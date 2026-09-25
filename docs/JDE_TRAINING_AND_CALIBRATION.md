# JDE: training and calibration

```
python scripts/setup_models.py --jde                     # optional: GloVe vectors for the glove+hash backbone
python -m jarvis.decision.train --encoder hash           # or glove+hash, minilm+hash, bge-small+hash
python -m jarvis.decision.evaluation.evaluate --model models/jde/<version> --latency 10000
python -m jarvis.decision.train --encoder glove+hash --promote   # only after the report says so
python scripts/bench_jde_backbones.py                    # compare backbones -> reports/jde_backbones.json
```

Training is CPU-only numpy and takes about 1–3 minutes. Nothing is downloaded except the optional encoder assets.

## Data

The training pool (about 9.2k examples) is built by `jarvis/decision/dataset.py` from trusted, repository-owned
sources only:

| Source | Examples | Notes |
|---|---|---|
| Synthetic generator | ~6.3k | many phrasing templates per family, context pairs (pronouns with resources), near-neighbour hard negatives (for example "open WhatsApp" is APP, not WHATSAPP), harmful or impossible requests as UNKNOWN |
| Augmentation of generated commands | ~1.6k | question frames ("how do I …" → KNOWLEDGE, non-action), negation frames (same family, `is_action = 0`), cross-family compositions (→ PLANNER with the multi-label family set) |
| Capability registry examples | ~360 | the examples each capability already declares |
| Router and planner golden files | ~300 | existing labelled routing tests |
| Generalization corpora (non-holdout) | ~650 | paraphrase, implicit, ASR variants, noisy, corrections, ambiguity, unknown; capped at 220 per family |

**Never used for training, calibration, fusion weights or thresholds:** `tests/jde/suite_dev.txt` (350),
`suite_holdout.txt` (100) and `suite_adversarial.txt` (50), and the legacy generalization holdout. `holdout_texts()`
removes any example whose normalized text appears in those suites.

**Never used at all:** webpages, WhatsApp messages, documents, the shadow log, or any other untrusted external text.
Retraining is a manual, reviewed step.

### Suite format

One case per line: `FAMILY[+FAMILY…] | flags | text | context`.

* Flags: `a` action, `l` needs LLM, `p` planner, `c` context, `w` web, `x` external effect, `d` destructive,
  `m` ambiguous, `u` unsupported; a digit gives the complexity.
* Context: `res=FileResource,…`, `topic=`, `prev=`, `task=`, `app=`, `confirm=1`, `chan=`, `na=` (families not
  configured on this machine).

## Pipeline

1. **Split:** a seeded random 85/15 split of the pool into TRAIN and VALIDATION.
2. **Features:** `[encoder(text) ; rule_features(state)]`, computed once.
3. **Heads:** trained on TRAIN with Adam, L2 and class-balanced weights. The route head is a 20-way softmax; complexity
   is 4-way; there are 9 sigmoid heads and a multi-label family head.
4. **Fusion (VALIDATION):** a grid search over the semantic-router weight `w` and similarity scale. The current
   glove+hash model uses `w = 0.15` and scale 30.
5. **Calibration (VALIDATION):**
   * route and complexity: temperature scaling (grid search on negative log-likelihood); current route T = 0.65;
   * binary heads: Platt scaling, `p = σ(a · logit + b)` per head.
6. **Thresholds (VALIDATION):** for each risk class, the lowest confidence at which the precision of auto-executed
   predictions reaches the target, with at least 10% coverage. A class with fewer than 25 validation examples uses a
   documented conservative fallback.

| Risk class | Target precision | Fitted threshold (glove+hash) | Floor | Fallback when data is thin |
|---|---|---|---|---|
| READ_ONLY | 95% | 0.955 | 0.55 | 0.70 |
| REVERSIBLE | 97% | 0.890 | 0.65 | 0.80 |
| EXTERNAL_EFFECT | 99% | 0.99 (target not reached → capped) | 0.85 | 0.92 |
| DESTRUCTIVE | 99.5% | 0.99 (target not reached → capped) | 0.93 | 0.97 |
| PRIVILEGED | 99.5% | 0.98 (no data) | 0.95 | 0.98 |

7. **Save:** `models/jde/<version>/{heads.npz, prototypes.npz, meta.json}`. `--promote` writes `models/jde/CURRENT`.

## Metrics reported (`reports/JDE_BENCHMARK.md`)

Route accuracy and top-3 recall, family coverage@5, per-head accuracy, precision, recall, ECE and Brier score, route
ECE and Brier score, a reliability table, auto-execute rate and precision, wrong (consequential) executions,
critical-pair confusions, current router vs router + JDE (accuracy, planner, LLM calls), the stage-B effect,
latency (first call, cache miss p50/p95/p99 over 10,000 requests, cache hit, throughput, RSS) and cold load time.

## Encoder backbones

| Backbone | Where it comes from | Status here |
|---|---|---|
| `hash` | built in | measured |
| `glove+hash` | GloVe 6B 100-d, GitHub release of gensim-data (one-time download of about 130 MB) | measured; CURRENT |
| `minilm+hash`, `bge-small+hash` | FastEmbed ONNX from huggingface.co | **not measured**: this build environment's network policy blocks huggingface.co. Run `pip install fastembed` and then `python scripts/bench_jde_backbones.py` on a machine that can reach it; results are added to the report automatically |

## Promotion rules

A model moves to the next stage only when the benchmark on dev, holdout **and** adversarial shows:

* zero wrong consequential executions (external or destructive routes gated EXECUTE but wrong);
* the stage's accuracy and precision targets met;
* no regression of the existing generalization benchmark.

Until then JDE runs in shadow mode.
