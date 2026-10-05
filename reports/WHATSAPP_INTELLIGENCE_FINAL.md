# WhatsApp intelligence consolidation: measured local status

Observed 2026-10-05. This pass reused the registered fresh Baileys companion, the existing inbox SQLite database and its FTS/vector intelligence tables, and the existing encrypted personal-reply SQLite store. It did not send a WhatsApp message, alter auth, remove history or reviews, enable generated auto-reply, or create a per-contact database/model.

## Architecture and dashboard

| Component | Status | Evidence and limit |
|---|---|---|
| ARCHITECTURE | PARTIAL | One contact-filtered example/profile store plus the existing inbox intelligence store. Existing recent context, semantic planner, truth gate and style generator remain in the personal-reply agent. The new contact behavior and dyadic aggregates are visible but are not independently validated predictors. |
| DASHBOARD | PARTIAL | Existing Contacts page now shows an intelligence overview, Load All, per-person refresh, progress/cancel, aggregate contact detail, holdout rating dimensions and draft feedback. QML load tests pass; user interaction and visual quality have not been assessed on a live desktop. |
| LOAD ALL | PASS for local history | A persisted, restart-resumable background job imports already-local direct-chat history, classifies provenance, builds contact-scoped examples/profiles/aggregates, validates and publishes. It does not claim remote WhatsApp history is complete. |
| LOAD PERSON | PASS for local slice | One-contact refresh published independently; other contact versions remained intact. |
| ATOMIC PUBLISH | PASS in tests | Snapshots replace derived rows and advance the active version in one SQLite transaction after source-hash validation. A failed build leaves the previous index. Raw source/review rows are preserved. |
| HOT RELOAD | PASS in tests | Successful publish invalidates changed contact caches and refreshes the global fallback without restarting JARVIS. |
| HEALTH | PARTIAL | Dashboard separates local/imported history from unknown remote completeness and exposes connection, listener, index version and latest job. It is not proof of fresh end-to-end live delivery. |

Local Load All job `90a9555cbf1d4afe86e56045b7aee026` completed in approximately 3.6 s: 41 direct-contact slices, 2,083 style-source messages processed, 86 reply pairs/vectors and 26 nonempty profiles, active memory version 1. A second unchanged Load All skipped all 41 and kept version 1. A one-contact refresh built four pairs and advanced version to 2. There were no job warnings. The raw inbox retained 3,152 messages and passed `PRAGMA integrity_check`; the personal store also passed. The local inbox had 40 distinct direct chat IDs; the extra style-only contact explains 41 slices. These are local counts, not remote completeness.

## Data, memory and personalization

| Requested item | Status | Measured state |
|---|---|---|
| MESSAGES INDEXED | PASS locally | 3,152 canonical `wa_events` and 3,152 FTS rows; 2,741 existing vector rows. Style source table contains 2,083 rows after import. Counts describe different indexes and must not be added. |
| CONTACTS / REPLY PAIRS | PASS locally | 41 indexed slices; 26 nonempty style profiles; 86 reply pairs. Pair quality has limited owner verification. |
| VERIFIED OWNER EXAMPLES | PARTIAL | 106 owner-approved legacy source rows and 106 review records were preserved. There is no basis to treat all 2,083 sources as verified manual sends. |
| LEGACY OWNER EXAMPLES | PARTIAL | Existing legacy provenance remains lower weight. Two known generated/draft source rows remain excluded from style examples. Exact current legacy style-source split was not recomputed for this report. |
| GLOBAL STYLE | PARTIAL | Existing aggregate fallback without cross-contact private text. Its predictive quality is unmeasured. |
| CONTACT BEHAVIOR | PARTIAL | New local language/mode, question/emoji rate and length aggregates; no private text exposed in dashboard lists. Heuristic modes need validation. |
| OWNER-CONTACT STYLE | PARTIAL | Existing contact profiles, provenance weights and train-only example retrieval; many contacts have thin evidence. |
| DYADIC PROFILE | PARTIAL | Train-only QUESTION/TECHNICAL/CASUAL pair counts, reply-language distribution, median reply length and sample-based confidence are published per contact. They are descriptive aggregates, not a learned relationship model. |
| FTS / EMBEDDINGS | PASS locally | Existing SQLite FTS5 and vector representation; 3,152 FTS rows, 2,741 message vectors, 86 reply example vectors. |
| EPISODIC MEMORY | PARTIAL | Existing topic/thread summaries and evidence references plus recent thread context. Full relationship state, promises and decisions are not independently validated. |
| RETRIEVAL | PARTIAL | Same-contact embedding ranking now adds a bounded lexical overlap bonus while keeping the existing 0.21 cosine floor and zero-result behavior. In the small diagnostic replay, retrieval was invoked 7/10 times, returned empty 3/7, and logged zero cross-contact or future-example hits. Relevance lacks owner ratings. |
| TRUTH GATE / SEMANTIC VALIDATOR | PARTIAL | Existing answerability and same-thread factual checks remain in force; uncertain truth can cause a clarification or owner-context hold. Seven generated diagnostic drafts had six rule-based semantic passes. Human factual correctness remains unmeasured. |
| PERSONALITY RENDERER | PARTIAL | Existing local chat role and style critic, with at most one revision. Real owner-style accuracy is unmeasured. |
| MODALITY / EMOJI / STICKERS / MULTI-MESSAGE | PARTIAL | Existing modality and emoji profiles, candidate-only sticker memory and multi-message handling remain. Sticker evidence is zero; live modality and multi-message quality were not measured in this pass. |
| SHADOW DRAFT / FEEDBACK LEARNING | PARTIAL | Dashboard can request and review a personalized draft and record SEND, EDIT, REGENERATE, NO_REPLY, BAD_STYLE or WRONG_CONTEXT. Only acknowledged final owner sends are eligible as new style evidence. No owner-rated live draft was collected in this pass. |

## Evaluation and tuning

The existing chronological train/development/holdout split and retrieval isolation were retained. Ten previously opened diagnostic holdout cases across three hashed contacts were replayed after Load All; this is **not** an untouched final holdout. Seven yielded drafts, one asked for clarification, one held for missing owner context, and one chose no reply. Rule-based semantic checks passed 6/7 generated drafts. Language label matched 3/7 and length band 5/7. These proxies do not establish semantic, dyadic or style quality. The local replay logged zero cross-contact and zero future-example retrieval hits. No owner ratings were available, so safe parameter auto-tuning and auto-reply promotion were withheld. The 0.21 retrieval floor was kept.

| Evaluation dimension | Status |
|---|---|
| TRAIN / DEV | PARTIAL: chronological isolation exists, but current aggregate counts were not recomputed. |
| HOLDOUT | INSUFFICIENT_EVIDENCE: 10 previously opened diagnostic cases, no untouched final acceptance set. |
| SEMANTIC | PARTIAL: 6/7 rule pass; no owner semantic ratings. |
| TRUTH/STATE | INSUFFICIENT_EVIDENCE: no independent real-world factual labels. |
| DYADIC / STYLE | INSUFFICIENT_EVIDENCE: zero owner-rated replay or live drafts. |
| LANGUAGE / LENGTH | PARTIAL: proxy matches 3/7 and 5/7 respectively. |
| EMOJI / MODALITY | INSUFFICIENT_EVIDENCE: seven drafts are too few and no owner ratings. |
| RETRIEVAL RELEVANCE / WRONG MEMORY | INSUFFICIENT_EVIDENCE: four nonempty retrieved results, no owner relevance judgments. |
| CROSS-CONTACT LEAKAGE | PASS on this diagnostic replay: 0/7 retrieval paths; broader live privacy acceptance remains pending. |
| DRAFT ACCEPTANCE / EDIT RATE / AVERAGE EDIT RATIO | INSUFFICIENT_EVIDENCE: no reviewed live drafts. |

A nine-prompt, three-contact local benchmark produced five drafts. Total p50/p95 was 4,429.9/5,750.5 ms; generation 4,265.4/5,551.9 ms; classification 0.5/5.9 ms; retrieval 0.5/40.6 ms. Recent-context p50/p95 was 14.1/21.6 ms, planning 172.8/186.8 ms and validation/revision 0.5/21.3 ms. Phase timings are per call; their percentiles need not add to total percentiles. The earlier baseline used different prompts, so no before/after speedup is claimed. No extra model call or LoRA was added.

## Verification and production boundary

The first broad Python run found one outdated pause/resume assertion: it expected automatic sending despite the offline-evaluation gate. That assertion was corrected to verify grant expiry retention and the gate. The final broad rerun passed **255/255** (two dependency deprecation warnings). Node bridge tests passed **24/24**. Dashboard QML tests passed **4/4** within the Python run. `git diff --check` found no whitespace errors.

**AUTO-REPLY STATUS: OFF.** `generated_auto_reply_enabled=false`, with zero currently active grants; no chat sends or automatic replies were activated. The restarted read-only Python listener returned health `ready` and reported memory version 2, 41 indexed contacts and the latest job `COMPLETE`; the existing read-only Node bridge stayed running. The fresh Baileys auth, exact-once inbox, ActionLedger and existing outgoing evidence were untouched. This pass did not re-accept live reply, attachment, voice or remote owner-command paths.

Top failure modes are limited verified reply evidence, no owner-rated draft/holdout quality, thin per-contact pairs, weak language agreement on seven drafts, uncertain remote history completeness, and model generation dominating latency. There is no evidence to tune thresholds or promote any contact to generated auto-reply. Final production acceptance is **PARTIAL**, with autonomous reply quality **INSUFFICIENT_EVIDENCE**.
