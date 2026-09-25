# JDE — audit of existing routing decisions

Scope: what decides *where a request goes* in JARVIS today, before the JARVIS Decision Engine (JDE)
exists. No production routing was changed while writing this audit.

## 1. Pipeline as implemented

`CommandService.handle()` → `SmartRouter.route()` → service dispatch → `ExecutionEngine` (policy,
confirmation, ledger) → `Verifier` → `ResponseEngine`/PULSE.

`SmartRouter.route()` (`jarvis/core/router/router.py`) runs these stages in order and returns at the
first one that decides:

| # | Stage | Mechanism | Decides |
|---|-------|-----------|---------|
| 1 | Control commands (stop / cancel / yes / no) | rules | CONTROL lane |
| 2 | Normalization (ASR fixes, fillers, wake word) | rules | – |
| 3a | Bulk WhatsApp reply | regex (`extended.match_bulk_reply`) | intent + slots |
| 3 | Negation / "do X instead of Y" | rules (`guards.check_negation`) | REJECT / positive override |
| 3b | Direct system actions, dashboard buttons | rules | intent |
| 3a-1..4 | Pending confirmation, "why", topic switch, pronoun/topic continuity | rules + `WorkingMemory` + `ReferenceResolver` | intent, slots, CLARIFY |
| 3b | Ordinal selection in result sets | rules | intent |
| 3b-ext | Extended domains: software, phone, transfer, screen, WhatsApp, reminders, web, open questions | regex (`extended.match_extended`) | intent + slots, or LANE_2 "question" |
| 3c | Shell / terminal commands | rules | intent |
| 4 | Question / informational guard | rules (`guards.is_informational_or_question`) | LANE_2 (chat/planner) |
| 5 | Hot route cache | exact normalized text | cached decision |
| 6 | Candidate intents | token overlap over `intents.yaml` | candidate set |
| 6a | Generic ambiguity ("open studio") | rules + app catalog | CLARIFY |
| 6b | Complexity gate | rules (`complexity.check_complexity_gate`) | LANE_2 + planner |
| 7 | Deterministic compound ("open chrome and calculator") | rules | mini-DAG subcommands |
| 7b | Pronoun / referent resolution | `ReferenceResolver` | slots |
| 8 | Exact & grammar patterns | `intents.yaml` regex | intent + slots |
| 8b | Direct app / target resolution | `AppResolver` / catalog | open_app |
| 9 | Prefiltered fuzzy match | rapidfuzz-style ratio | intent |
| 10 | Complexity gate (second pass) | rules | LANE_2 |
| 10.5 | Semantic capability retrieval + slot extraction | BM25 over `CapabilityRegistry` (`retrieval.py`) | LANE_0 intent if score ≥ 6 and slots complete |
| 11 | Lane 1 classifier | **Qwen (Ollama)**, schema-constrained to retrieved tools (`router/ollama.py`) | intent + slots, multi-step, unknown |
| 11b | Fallbacks | semantic retrieval ≥ 6 → LANE_0; ≥ 4 → LANE_2 planner; otherwise `ollama_chat` with `fallback=unknown_command` | route |

After routing, `CommandService` decides the execution path:

| Router output | Service path | Mechanism |
|---|---|---|
| LANE_0 / LANE_1 intent | tool via `ExecutionEngine` | direct |
| LANE_2 + `QUESTION_NOT_COMMAND` | grounded chat (`Assistant`: RAG + memory + web if `needs_live_data` regex) | rules |
| LANE_2 other | `AdaptivePlanner` (**planner LLM**) → DAG; invalid graph → `AgentRunner` (**planner LLM**, ReAct) | LLM |
| `ollama_chat` + `fallback=unknown_command` | `AgentRunner` | LLM |
| CLARIFY / REJECT | message only | – |

Authorization is **not** made by any of the above: `PolicyEvaluator` + `ConfirmationManager` inside
`ExecutionEngine`, plus AI-originated confirmation (`AI_CONFIRM_TOOLS`) in the service, are the final authority.

## 2. Which component makes which decision today

| Decision (JDE question) | Made today by | Quality / cost notes |
|---|---|---|
| Is this a known command? | rules (stages 1–9) | fast (<1 ms p50), high precision, brittle to paraphrase |
| Route family (WhatsApp / browser / phone / file / …) | regex in `extended.py` + `intents.yaml`; else BM25; else **Qwen** | paraphrases fall through to Qwen (1–20 s cold, 150–600 ms warm) |
| Knowledge question vs action (actionability) | `OPEN_QUESTION` regex + `is_informational_or_question` | good on "what is X", weak on implicit phrasing ("too loud in here") |
| Needs fresh web info | `LIVE_DATA_PATTERN` regex (assistant) | keyword based, misses "who won yesterday's match" style variants without keywords |
| Needs RAG | always attempted when KB non-empty (assistant) | no routing decision; costs a retrieval per chat |
| Needs planner | complexity gate rules + Qwen `is_multi_step` | rules over-trigger on long single-intent sentences |
| Needs context | `ReferenceResolver` (pronouns) | good, rule based |
| Ambiguity / clarify | disambiguation rules, Qwen `missing_slots`, low BM25 | inconsistent across paths |
| Unknown / unsupported | `unsupported.py` rules; Qwen `unknown` | – |
| External effect / destructive (risk) | tool `RiskLevel` **after** tool choice | not available before a tool is chosen |
| Model class (none / small / planner / vision) | implicit in the lane | no explicit gating; LANE_2 always wakes the planner model |
| Capability shortlist for planner/agent | BM25 top-k (`select_tools`) + `CORE_TOOLS` | adequate |

Measured baseline (generalization torture corpus, 17 datasets, 1 658 cases, deterministic router,
no model): **96.68 %** (`tests/generalization/benchmark_runner.py`, see `reports/`).

## 3. Datasets available for JDE

| Source | Size | Labels useful for JDE | Gaps |
|---|---|---|---|
| `tests/generalization/*.jsonl` | 1 658 | expected_behavior (EXECUTE / CLARIFY / UNKNOWN / REJECT / CONFIRM / SAFE_*), expected_intent, expected capability ids | 70 % open_app / volume / diagnostics; almost no knowledge, web, RAG, WhatsApp, browser, phone |
| `tests/generalization_holdout/holdout_unseen.jsonl` | 320 | as above | **reserved** – never used for JDE training |
| `tests/data/router_golden.jsonl`, `router_adversarial.jsonl` | 428 | expected lane + intent | command-heavy |
| `tests/data/planner_golden.jsonl` | 206 | required tools, clarification, capability gap | planner only |
| `tests/data/policy_golden.jsonl` | 260 | tool + risk + decision | risk labels (per tool) |
| `CapabilityRegistry` | ~150 capabilities | description, examples, counterexamples, category, risk, target tool | examples only (2–5 each) |
| `jarvis/tests/test_extended_routing.py` etc. | ~150 | intent per phrase | – |

Conclusion: the existing corpora cannot train route-family / needs-web / needs-RAG / actionability heads on
their own. JDE needs a new labelled suite (families balanced, near-neighbour hard negatives), plus
label derivation from the capability registry and the existing corpora.

## 4. What moves into JDE (and what does not)

Moves into JDE (bounded, typed, no generation):

* route family (multi-label top-K) and primary family, including KNOWLEDGE / WEB / RAG / CLARIFY / UNKNOWN,
* actionability (`is_action`), needs_llm, needs_planner, needs_context, needs_web,
* external_effect, destructive (advisory risk *before* a tool is chosen),
* ambiguity / abstention, complexity score, model class.

Consumers:

* the Lane 1 Qwen classifier becomes an **arbitrator**, called only when JDE is uncertain or its heads disagree
  on a non-consequential request,
* the service uses `needs_planner` / `needs_llm` / `needs_web` to pick chat vs mini-DAG vs planner vs agent,
* the assistant uses `needs_web` instead of (or in addition to) the keyword regex.

Stays where it is:

* L0 deterministic stages 1–9 (they are faster and already correct; JDE never runs when they decide),
* slot/entity extraction and reference resolution (JDE only predicts coarse types),
* the planner (JDE says *whether* to plan, never *what* steps),
* `PolicyEvaluator` / `ConfirmationManager` / ledger / verifier (JDE risk is advisory only),
* tool execution (JDE never executes).

## 5. Integration points (for shadow mode)

* `SmartRouter.route()` returns → the service already has the decision and the `WorkingMemory` context:
  JDE runs there in **shadow** (off the critical path, logged to `data/jde/shadow.jsonl`).
* Promotion stage B (read-only) hooks the two points where today an LLM is woken for a routing decision that
  JDE can make: the `unknown_command` fallback (agent) and LANE_2 "question" dispatch (chat vs planner).
