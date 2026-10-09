# Blind-11 development progress

**Blind-11 is exposed development data.** Nothing below is an unseen result and none of it may be quoted as one. The numbers
measure how far the architecture repairs moved the same 1100 locked cases; the next unseen benchmark is Blind-12 (not yet generated).
No Blind-11 sentence was patched: every change is a typed, general mechanism with its own tests built from new constructions.

Environment: the intended local model runtime (Ollama) is **not installed and cannot be downloaded here (403)**. Run B is therefore the
command service with the deterministic router, real sandbox execution where possible, and the model **unavailable**. It is not a
full-stack result. No substitute model was installed. See "Model-off classification".

## Development metrics (run B, strict / audited, same locked cases)

| Metric | First run | After repairs (r6) |
|---|---:|---:|
| Exact action | 33.1% / 33.2% | **45.0% / 45.2%** |
| Critical wrong actions | 47 (C3 31, C4 16) | **1 strict (documented oracle erratum) / 0 audited** |
| Must-never-happen errors (C4) | 16 | **0** |
| Forbidden value used | 10 | **0** |
| Consequential negation / correction preservation | 94.1% | **100% (85/85)** |
| Negation accuracy | 26.8% | 41.5% |
| Correction accuracy | 13.6% | 63.6% |
| Reference / context resolution | 16.4% | 42.6% |
| Plan validity | 10.5% | 14.0% (needs the planner model, see below) |
| No-action specificity | 75.2% | 84.3% / 84.6% |
| False-action rate | 24.8% | 15.7% / 15.4% |
| Action precision / recall | 46.5% / 29.5% | 60.8% / 38.3% |
| Intent accuracy | 39.3% | 49.1% |
| Slot exact | 78.8% | 87.0% |
| Constraint accuracy | 24.5% | 52.7% |
| Confirmation accuracy (858 cases with a confirmation expectation) | 464 (54.1%) | 497 (57.9%) |
| Verification accuracy (said vs real result) | 100% | 100% (false success 0) |
| Run A (router only) exact | 31.5% (critical 43) | 40.9% |


Capability confusion (largest remaining): `CHAT -> CLARIFY` 21, `compound -> PLAN` 13, `compound -> CLARIFY` 11,
`browser_quick_action -> CLARIFY` 11, `clipboard_op`, `android_toggle`, `browser_click` -> CLARIFY 9 each. Almost all remaining
`-> CLARIFY` rows are the router's honest "I can't reach my local AI" fallback, not a wrong tool (see below). Primary failure causes now:
UNSUPPORTED_CAPABILITY 254 (model unavailable), TOOL_WRONG 115, INTENT_WRONG 76, POLICY_WRONG 40.

Run A still lists 4 router-level criticals. They are slot imprecision with **no execution**: two destructive requests whose file is named but
not yet bound (`delete_file` with "the march invoice"), one pronoun reply, and the "never turn off my pc without asking" erratum. In run B
the executor's scope guard resolves, binds and blocks or asks before any side effect, which is why run B has none.

## What changed (architecture, not sentences)

| Priority | Mechanism | Where |
|---|---|---|
| P1/P4 | Risk-class policy applied on every lane (payment, secrets, credentials, third-party devices, drive wipe, scam UI, CAPTCHA, exfiltration, content authority, exams, hoax calls, mass contact, destructive dev ops ...); questions about a risky topic are answered; relayed speech is separated from JARVIS's own actions; a statement about a secret stores no secret; writing tools refuse secrets themselves | `core/semantics/policy.py`, `quick_notes`, `connector_tools` |
| P2 | Typed path references (FILE / FOLDER / ITEM / ROOT) with parent, resolver with exclusions and ambiguity | `core/semantics/resources.py`, `router/slots.py` |
| P3 | Domain checks before tool choice: payment vs message, device-mode names vs windows / clock, modifier-aware capability anchors, duration adjuncts are not clock questions | `router._mode_domain`, `capabilities/retrieval.py` |
| P5 | Destructive scope guard: resolve -> type -> scope/parent -> affected count -> policy -> only then confirmation; bound arguments are what the ticket confirms; rename never overwrites or drops the type | `security/destructive.py`, `executor/engine.py` |
| P6 | Separate decision states (clarification / confirmation / authorization / blocked / ready) and `POLICY_BLOCKED` | `router/models.py` |
| P7/P8 | One constraint representation: corrections with typed alignment and supersession, exclusions, prohibitions (target-scoped), contrasts, trailing and Tanglish prohibitions, cancellation; addresses, restatements, mode names and "no + plural" are not corrections or prohibitions | `core/semantics/constraints.py`, `router.route` |
| P9 | Typed reference resolution by type and active turn: person pronouns, on/off flip, repeat/intensify, sibling swap, refinement, typed pronoun for reversible verbs only, introspection, forget, extend, settings page, device continuity, Tanglish demonstratives; a reference expression is never an entity name | `context/carryover.py`, `semantics/references.py`, `router._reference_slots` |
| P10 | Semantic plan validation on every planner validation point: negated action, excluded target, rejected value, policy, unrequested destructive/outward step, unsafe literal destructive target | `planner/semantic_validator.py` |

## Why plan validity and reference accuracy are still low

* **Plan validity 14.0%**: 57 cases need the planner model to build a graph. With the model unavailable they cannot pass whatever the
  validator does. The validator is now the gate for planner output (P10, 8 tests); its effect can only be measured with the real model.
* **Reference 42.6%**: roughly half of the remaining misses are follow-ups the router deliberately hands to the model (open-ended
  "what about ..." questions, content questions about an opened document).

## Model-off classification (run B, r6)

330 of 1100 cases fell through to the unavailable model (377 before). None counts as a success.

| Class | Cases | Meaning |
|---|---:|---|
| ROUTER_WRONG | 201 | Explicit requests the deterministic router should handle itself: the repair backlog |
| ROUTER_CORRECT_ESCALATION_MODEL_UNAVAILABLE | 80 | Indirect / ambiguous requests; escalating is intended |
| MODEL_REQUIRED_UNAVAILABLE | 49 | Conversation, planning, composing, vision, document Q&A |

Per-case list: `docs/blind11_dev/BLIND11_MODEL_OFF.md`. Full report, failures, confusion matrix and CSVs: `docs/blind11_dev/`.
Raw results: `tests/blind11/results/dev_r6_run_a.json`, `dev_r6_run_b.json`.

## Regression gate (this phase, no new critical regressions)

| Suite | Baseline | Now |
|---|---:|---:|
| Phase-500 (dev + holdout failures) | 106 | 106, identical set |
| Blind-7 / 8 / 9 failures | 208 / 284 / 137 | 208 / 284 / 137, identical sets |
| Phase suite + Blind-2..6 + generalisation | 40 / 4 / 3 / 0 / 0 / 41 | 25 / 4 / 3 / 0 / 0 / 35 (no new) |
| Context (66 turns) | 98.5% | 98.5% |
| Context-2 dev follow-ups | 98.9% | 98.9% |
| Operator | 401/402, 461/461 | 401/402, 461/461 |
| AGI-520 dev / holdout | 499 / 380 | 499 / 382 |
| pytest known failures | 21 | 21 environmental (+ intermittent timing flakes under machine load) |

## Blocked / next

* **DEPENDENCY_UNAVAILABLE: Ollama** (and its models). A full-stack run needs it; nothing here substitutes for it.
* Remaining router backlog is the 201 ROUTER_WRONG rows: mostly wording coverage for existing tools (speech control, clipboard, browser quick
  actions, text ops, brightness, phone toggles, window snapping), to be repaired as vocabulary/schema generalisations.
* **Blind-12** (new constructions, Run A router diagnostic and Run B full stack, Run B marked DEPENDENCY_UNAVAILABLE while the model is absent)
  is generated only after the candidate is frozen.
