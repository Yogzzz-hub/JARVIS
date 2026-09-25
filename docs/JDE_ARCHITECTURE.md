# JARVIS Decision Engine (JDE): architecture

JDE is a local, offline, CPU-first **System-One** decision layer. It sits between the deterministic router (L0) and the
LLMs. It answers typed routing questions in about 1 ms, calibrates its answers, and abstains when unsure. It never
executes and never authorizes anything.

```
request ─► L0 deterministic router (unchanged, always first)
             │ decided? ─► existing path (policy → confirmation → execute → verify)
             ▼ not decided
           JDE (shadow today): one encoding ─► all heads in one pass ─► calibration ─► fusion ─► gate
             │ EXECUTE (by risk class) → family → shortlisted tools → policy/confirmation (unchanged)
             │ FALLBACK / ABSTAIN      → existing router / Qwen Lane 1 / planner, exactly as before
             │ CLARIFY / UNSUPPORTED   → ask / refuse
             ▼ rare
           Qwen arbitrator / planner (only for PLANNER-class or low-confidence cases)
```

## Components (`jarvis/decision/`)

| Module | Role |
|---|---|
| `schemas.py` | Typed questions and answers: `ChoiceAnswer` (route family, model class), `ScoreAnswer` (complexity), `ProbabilityAnswer` (9 binary heads); `DecisionState` (compact context vector); `DecisionResult` with `Gate` and versions |
| `encoder.py` | `DecisionEncoder` protocol. `HashingEncoder` (crc32 word/bigram/char n-grams, 4096-d, always available); `FastEmbedEncoder` (all-MiniLM-L6-v2 / BGE-small via ONNX); `ConcatEncoder` (dense + lexical) |
| `static_vectors.py` | GloVe 100-d (downloaded once from a GitHub release) as a torch-free semantic backbone; SIF-style weighted mean |
| `features.py` | General rule and context signals (question form, negation, "draft only", multi-clause, deictic references, resource types, previous route, pending confirmation). **No sentence is hardcoded.** |
| `classifier.py` | numpy linear heads: softmax (route, complexity), sigmoid (binary), multi-label (families). Adam, L2, class balancing |
| `catalog.py` | Route catalog built from the live `CapabilityRegistry`: family → tools, risk, prototypes. Versioned by content hash |
| `semantic_router.py` | Prototype similarity per family (0.6 · max + 0.4 · mean), a second opinion that is independent of the classifier |
| `calibration.py` | Temperature scaling, Platt scaling, ECE, Brier score, reliability tables |
| `thresholds.py` | Risk-class gates fitted on validation data to a target precision per class |
| `cache.py` | LRU decision cache keyed by normalized text + context signature + all versions |
| `engine.py` | `LocalJDE` (load/save/decide), `HostedJevAdapter` (stub, disabled by `JDE_LOCAL_ONLY`), `get_engine()` (never raises) |
| `runtime.py` | Shadow logging and stage handling; the only code the service calls |
| `dataset.py`, `train.py`, `evaluation/evaluate.py` | Data, training, benchmark |

## One encoding, many heads

`X = [encoder(text) ; rule_features(state)]` is computed once. Every head reads the same `X`:

* `route_family`: 20-way softmax, fused with the semantic router: `log p = log p_clf + w · log p_sem`, then temperature
* `families`: multi-label (which families a compound request needs; drives the planner tool shortlist)
* `complexity`: 0–3 (single step … open-ended)
* `is_action`, `needs_llm`, `needs_planner`, `needs_context`, `needs_web`, `external_effect`, `destructive`,
  `ambiguous`, `supported`: sigmoid heads with Platt calibration
* `model_class`: derived (NONE / TINY / SMALL / PLANNER / VISION), so an LLM is loaded only when needed

## Gate logic (in order)

1. UNKNOWN route or `p(supported) < 0.35` → UNSUPPORTED
2. an action family but `p(is_action) < 0.5` → FALLBACK (questions about an action are not the action)
3. incoherent heads (for example `external_effect` high on a family that cannot have external effects) → CLARIFY
4. high-risk family where the classifier and the semantic router disagree → CLARIFY
5. CLARIFY route, or `p(ambiguous) ≥ threshold` → CLARIFY
6. top-2 margin below `disagreement_margin` → CLARIFY (high risk) or FALLBACK
7. confidence ≥ the risk-class threshold → EXECUTE
8. otherwise CLARIFY (high risk), FALLBACK (≥ `fallback_min`), or ABSTAIN

## Rollout stages

| Stage | Setting | Effect | Status |
|---|---|---|---|
| Shadow | `[decision] stage = "shadow"` (default) | Router acts; JDE decides on a background thread and appends `{router, jde, agree}` to `data/jde/shadow.jsonl` (rotated at 20 MB) | **active** |
| B: read-only | `stage = "read_only"` | Also: a request with no router match that JDE gates EXECUTE as KNOWLEDGE goes to read-only chat instead of the tool-using agent | implemented, off by default; the benchmark shows no measurable gain yet |
| C: reversible | – | JDE picks reversible families when L0 does not match | not implemented; needs zero wrong consequential executions on every split |
| D: consequential | – | JDE shortlists tools for external and destructive families | not implemented |

`JARVIS_JDE_STAGE=off|shadow|read_only` overrides the config. Under pytest the stage defaults to `off`.

## Safety invariants

* JDE confidence is never used as authorization. Every tool call still goes through `PolicyEvaluator`,
  `ConfirmationManager` and the AI-confirmation step in the service.
* JDE chooses a family, never a tool name. Families map only to tools in the registry, so JDE cannot invent a tool,
  and the planner is shown only the shortlisted families' tools.
* The existing router stays first and remains the fallback. Any exception in JDE is swallowed: `get_engine()`
  returns `None`, and the runtime logs at debug level.
* The shadow log is never used for automatic training. Webpages, WhatsApp messages, documents and other untrusted
  external text are never training data and never routing authority.
* `JDE_LOCAL_ONLY=true` (the default) makes `HostedJevAdapter` refuse to construct, so no data leaves the machine.
* Hidden holdout suites are never used for training, calibration, fusion weights or thresholds.

## Versioning and cache

Each model directory `models/jde/jde-<timestamp>-<hash>/` holds `heads.npz`, `prototypes.npz` and `meta.json`. The
metadata records `decision_model_version`, `encoder_version`, `route_catalog_version` and `threshold_version`.
`models/jde/CURRENT` names the promoted model. If the CURRENT model's encoder assets are missing on a machine (for
example GloVe was never downloaded), `get_engine()` falls back to the newest model that loads. The hash model always
loads. Cache keys include every version, so a retrain or a catalog change can never serve a stale decision.

## Mini-DAG fast path

JDE's `families` head gives compound requests their family set. Deterministic compounds ("open chrome and
calculator") are already split by the router's rule-based compound step (L0). JDE only marks remaining multi-family
requests as PLANNER and shortlists the planner's tools. The planner, not JDE, builds the DAG, and each step is
policy-gated.
