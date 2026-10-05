# Tanglish language engine implementation

Date: 2026-10-02. This is a **measured partial implementation**, not production acceptance of general language understanding.

## Architecture

`GeneralLanguageUnderstandingEngine` creates one side-effect-free `LanguageFrame` for English, Tanglish and low-confidence ASR input. Its canonical projection feeds JARVIS's existing `SemanticFrame`. The frame holds speech act, semantic action, target type, recipient, channel, selector, reference, corrections, exclusions, missing context and lexical evidence. A phonetic family offers several candidate senses. Object and relation evidence select a sense, and unresolved channel, recipient, resource or verb sense stays unresolved. A schema-retrieval method uses the existing capability retriever; the existing router, policy and verifier remain the only route to execution.

CommandService retains the raw request and its language frame before legacy Tanglish rewriting. SmartRouter rejects prohibitions, routes questions/statements to the conversational lane, and asks for missing resources or channel before an action. It also prevents a Tanglish read/provide request from becoming a WhatsApp send because a contact name was guessed from a verb. No real external action was used to test this engine.

## Files

- `jarvis/core/general_language.py`: phonetic families, object-aware verb senses, speech acts, references, exclusions, correction handling, canonical-frame projection and schema candidates.
- `jarvis/core/capabilities/frame.py`: optional language evidence on the existing canonical frame.
- `jarvis/core/commands/service.py`, `jarvis/core/router/router.py`: raw-text preservation and early safety gates.
- `jarvis/tests/test_general_language.py`: minimal pairs, polysemous senses, missing-context and no-action regression cases.
- `scripts/build_tanglish_corpus.py`, `scripts/evaluate_tanglish.py`, `scripts/audit_tanglish_corpus.py`: deterministic local data generation, read-only evaluation and leakage audit.
- `jarvis/tests/fixtures/tanglish_corpus/`: compressed synthetic corpus and split manifests. No private chat text or external upload is used.

## Corpus

The generated corpus contains 105,000 examples: 84,000 train, 10,500 dev, 5,250 test and 5,250 development holdout. A further 5,000-example final locked set uses new grammar families; earlier v3–v5 sets were used during development and corpus-quality review. The final locked set has 1,338 prior-turn cases and 1,988 no-action cases. The training set has 28,620 multi-turn cases. Phonetic typo and uncertain-ASR variants are present, but each is a small minority; the corpus currently has only one automated compositional source and does **not** satisfy the requested diversity of human paraphrases, independently annotated real examples or broad ASR recordings.

The audit found **zero exact normalized and structural-skeleton overlap** between the final locked set and earlier splits. In a sampled lexical-neighbor check (500 locked versus 3,000 train), median nearest-token Jaccard was 0.375, p95 was 0.500 and none exceeded 0.8. These checks cannot detect every semantic near duplicate.

## Locked measurement

The final v6 locked set was generated after the corpus-quality review and evaluated once. No parser changes were made in response to v6 results. `reports/tanglish_locked_holdout_v6_results.json` contains counts and examples; `reports/tanglish_corpus_audit.json` contains the leakage audit.

| Metric | Locked result |
|---|---:|
| Speech-act accuracy | 87.96% |
| Semantic-action accuracy | 91.92% |
| Target-type accuracy | 92.28% |
| Recipient accuracy | 79.58% |
| Channel accuracy | 98.26% |
| Slot precision / recall / F1 | 67.56% / 87.61% / 76.29% |
| Polysemous verb-sense accuracy | 87.11% across 1,994 cases |
| Contextual target accuracy | 88.71% across 1,338 cases |
| Prohibition accuracy | 100% across 504 synthetic cases |
| Explicit exclusion accuracy | 100% across 361 synthetic cases |
| No-action specificity | 99.60% (8 false actions / 1,988 no-action examples) |
| Action-trigger precision | 96.42% |

The measured semantic-action result is below the requested 95% bar. This is a synthetic grammar benchmark, not end-to-end verified action accuracy. It does not measure capability precision/recall, policy outcome, actual reference resolution or real user language. It must not be used as evidence that an external action is safe by itself.

The corpus has no independently labeled correction set, so correction accuracy is not reported. The prohibition and exclusion scores cover generated surface patterns only. A selected-resource context is supplied to the contextual examples; this is narrower than finding a real resource across previous turns.

A 1,000-example local adapter timing sample had median 0.288 ms and p95 0.560 ms. This excludes model inference, routing, retrieval, policy and execution. The combined language, router, AI integration and WhatsApp regression run passed **414 tests** (`reports/tanglish_regression_tests.xml`). The final focused language/router run passed **103 tests**.

## Remaining work

- Add independent human annotation, broader slang, colloquial syntax, realistic ASR recordings and confusion-driven examples before treating the 100,000-row count as a training-quality milestone.
- Expand the semantic adapter to all listed verbs, morphology, corrections and implicit multi-turn requests. Current typed-context resolution handles selected resources only when they are supplied; it does not infer a missing file or person from chat history.
- Connect the semantic representation to capability retrieval and planner selection more deeply, with schema-grounded slot validation, then measure capability precision/recall and end-to-end verified action correctness.
- Reduce remaining false actions and improve the locked semantic-action score without tuning to this locked set. Future changes need a newly held-out test.
- Keep consequential permissions, secure input, confirmations and WhatsApp send policy enforced by their existing capability and policy layers.

The WhatsApp live incoming bridge issue documented in `reports/WHATSAPP_INTELLIGENCE_IMPLEMENTATION.md` is separate and remains unaccepted.

## Stage 2 update (2026-10-02)

A separate 100,000-row SemanticFrame corpus and compact local baselines are documented in [TANGLISH_SEMANTIC_TRAINING.md](TANGLISH_SEMANTIC_TRAINING.md). The test-set action classifier reached 95.28% on synthetic examples, but speech-act/action gating failed the required safety and recall balance. The trained artifacts remain offline and are not used for JARVIS execution. The locked Stage 2 holdout was not used for model selection.
