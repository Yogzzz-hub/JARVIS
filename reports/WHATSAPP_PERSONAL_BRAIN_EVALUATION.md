# WhatsApp personal brain: frozen architecture evaluation

Observed 2026-10-05 IST. This is a read-only evaluation of the existing personal reply path. No reply was sent, no profile or model was added, and generated auto-reply remains off. Contact identifiers below are SHA-256 prefixes. Private message bodies remain in the encrypted local store and ignored review sheets.

## Evidence and scope

| Contact hash | Verified train pairs | Verified holdout pairs | Remaining legacy pairs for owner review | Contact messages |
|---|---:|---:|---:|---:|
| `e35117b2` | 2 | 1 | 2 | 226 |
| `003c7eaf` | 10 | 3 | 4 | 184 |
| `adbd8753` | 18 | 6 | 4 | 107 |
| **Total** | **30** | **10** | **10** | **517** |

There are 106 owner-approved `VERIFIED_LEGACY_OWNER` text rows across these contacts, but only 30 older verified reply pairs and 10 newer verified holdout pairs. Approval records retain exact contact and message IDs, timestamp, and original provenance. Ten additional paired owner messages remain unverified; private same-contact sheets are `jarvis/data/whatsapp_style_reviews/{hash}.next_pairs.md`. No new rows were approved during this audit.

The importer reconstructs up to three consecutive preceding contact messages or an explicit reply target, within a six-hour gap. It combines consecutive owner lines into one response. `wa_pr_examples` stores encrypted context and reply, contact, timestamp, split and provenance. It does **not** store thread ID, prior owner turns, conversation mode, language mix, emoji or modality metadata as separate example fields. Replay reconstructs recent prior lines from `wa_pr_sources`; therefore the full requested conversation-to-reply unit is only partially represented.

The split is chronological for all three contacts: the newest verified train timestamp precedes the earliest verified holdout timestamp. The inspected holdout replay retrieved no future example and no example from another contact. Exact owner-response overlap across train and holdout is zero. One holdout context is the common one-character acknowledgement `k`, also present in train; that case offers little evidence of generalization. No owner holdout response was supplied to generation. These checks cover the ten local cases, not a larger locked evaluation set.

## Current path versus requested evaluation

| Component | Current evidence |
|---|---|
| Contact behavior profile | Contact messages exist, but no separate persisted contact-behavior profile is used by the personal reply path. A read-only sample found median contact message lengths of 3, 3 and 4 words; this is descriptive, not a validated profile. |
| Owner-contact style | Existing `ContactStyleProfile` uses owner evidence and contact-scoped statistics. |
| Dyadic conditional profile | No separately measured or persisted conditional owner-response profile. Pair retrieval gives limited implicit conditioning. |
| Conversation and truth state | Recent same-contact lines and optional intelligence context are passed to generation. The special short-update hold uses owner-sourced status; there is no measured general truth/personal-state classifier across the requested categories. |
| Episodic memory | The existing contact-scoped example index is consulted for every profiled draft, including simple requests. This is not yet optional by measured need. |
| What versus how | Current quality `relevance` largely uses the model's self-reported confidence; `style_match` uses surface statistics. They are not independent semantic and style judgments. |
| Modality | Current predictor covers TEXT, TEXT_EMOJI, EMOJI_ONLY and STICKER_ONLY. There is no tested NO_REPLY, TEXT_STICKER or MULTI_MESSAGE prediction. Sticker evidence is zero. |
| Candidate count | One model candidate is usual; at most one bounded style revision was observed in code. No multi-candidate search was added. |

## Holdout and owner feedback

The latest ten-case verified replay produced **nine answer candidates** and **one review-only clarification opportunity**. The clarification was drawn from a previously owner-approved message in the same contact and predating the holdout. It is not scored as a factual answer. The existing proxy reported language match **2/9**, length match **6/9**, emoji presence **9/9**, and observed text modality **9/9** for answer candidates. The separate modality predictor selected TEXT for all ten cases and all ten actual owner responses were TEXT; this homogeneous set cannot test sticker, emoji-only, no-reply or segmentation decisions.

The proxy semantic score was 9/9, but it is **invalid as evidence of semantic appropriateness**: the owner identified one earlier wrong-direction draft that the proxy had accepted. That case is preserved in its private sheet and remains unrated in the formal five-level review field. The other side-by-side owner ratings are pending. Actual semantic appropriateness, dyadic match, reply-needed accuracy, style acceptance and edit rate are therefore **not measured**. No live shadow draft has yet been reviewed or sent.

| Contact hash | Answer candidates / holdout | Language match | Length match | Emoji match | Text modality match | Owner-rated semantic, dyadic and draft acceptance | Live generation p50/p95 |
|---|---:|---:|---:|---:|---:|---|---|
| `e35117b2` | 0/1; one clarification opportunity | N/A | N/A | N/A | N/A | Pending | N/A |
| `003c7eaf` | 3/3 | 1/3 | 1/3 | 3/3 | 3/3 | Pending | N/A |
| `adbd8753` | 6/6 | 1/6 | 5/6 | 6/6 | 6/6 | Pending | N/A |

Per-contact BAD_STYLE and WRONG_CONTEXT feedback counts are zero because no live draft was reviewed. Zero is not an accuracy result. Reply-needed accuracy, retrieval accuracy and cross-contact leakage as an end-to-end user outcome remain unmeasured; the structural retrieval isolation check is reported below.

## Controlled truth and personal-state probes

Six isolated, unsent questions were tested without current thread facts: location, whether the owner ate, availability, tomorrow's attendance, backend repair status, and meeting time. All six require personal state, an owner decision, or verified external/conversation evidence before a factual answer. The current model returned six nonresponsive short strings; none established the requested fact. **The quality gate passed all six.** This is a measured semantic and confidence-gate failure, not proof of six invented factual assertions. Truth/state-gate accuracy cannot be calculated from these probes because the current path does not emit the requested `STYLE_ONLY / CONVERSATION_KNOWN / JARVIS_KNOWN / PERSONAL_STATE_REQUIRED / OWNER_DECISION_REQUIRED / SENSITIVE` labels.

## Retrieval and latency

On the ten verified holdout inputs, contact-scoped retrieval returned prior examples in **10/10** cases, with **0 cross-contact** and **0 future-timestamp** results in the inspected output. One top result had similarity **0.056** despite three examples being supplied; it was topically unrelated to the update request. Several other top hits were broad conversation or word overlaps. There are no independent gold episode-relevance labels, so retrieval precision and wrong-memory rate are **not established**. The `min_k=3` behavior explains why weak examples can reach the prompt. The simple one-character acknowledgement also retrieved examples, although no episodic memory was needed.

A six-prompt offline draft probe, using a mature contact profile and no WhatsApp transport, produced six drafts. Retrieval ran in **6/6** cases; five used one model call and one used the instant path. No prompt used multiple model calls. These are small, warm-runtime measurements:

| Phase | p50 | p95 |
|---|---:|---:|
| Other work (profile, context, critics; residual estimate) | 5.1 ms | 36.0 ms |
| Retrieval | 0.4 ms | 5.1 ms |
| Model generation | 1,146.2 ms | 1,888.0 ms |
| Total draft | 1,151.9 ms | 1,929.1 ms |

This excludes incoming WebSocket/SQLite receipt, live contact bursts and owner review. No end-to-end live draft latency can be claimed.

## Failure matrix and next evidence

| Primary failure | Evidence | Responsible area | Measured impact | Minimum general change to evaluate later |
|---|---|---|---|---|
| `SEMANTIC_WRONG` | One owner-identified reversed update request; six nonresponsive controlled state probes | Conversation interpretation and local generation | At least seven inspected failures across different probe types; not a population rate | Better role/question interpretation and independent answer validation, benchmarked on untouched cases |
| `CONFIDENCE_GATE_WRONG` | All six nonresponsive probe replies passed the quality gate | Quality/confidence gate | 6/6 controlled failures not blocked | Calibrate against owner-rated negatives; stop treating model self-confidence as semantic truth |
| `MEMORY_RETRIEVAL_WRONG` | Weak unrelated top hit at similarity 0.056; retrieval on every simple probe | Contact example retrieval | 1 confirmed poor top hit; 6/6 simple prompts retrieved | Measure relevance and make retrieval conditional on actual memory need |
| `LANGUAGE_STYLE_WRONG` | Only 2/9 candidate language labels matched actual owner replies | Renderer/model and style measurement | 7/9 proxy mismatches; owner rating pending | Use reviewed outcomes to separate detector error from generation error |
| `TRUTH_STATE_MISSING` | Six probes needed facts or decisions that were unavailable | Truth/personal-state gate | No false-fact count; all six nonresponsive outputs were allowed | Add independently labeled state-gate evaluation before implementation changes |

There is not enough verified owner-rated holdout or live feedback for an A–F architecture decision. The strongest present finding is that semantic correctness is unmeasured by the existing proxy and the gate accepted clear nonanswers. Do not fine-tune or enable generated auto-reply on this evidence. After the owner reviews the remaining ten paired rows and several live drafts, repeat the same chronological, contact-scoped evaluation and then decide whether the minimum fix is data, retrieval, truth/state handling, model capacity or a small architecture change.

## Runtime and validation

At inspection, the fresh Baileys bridge and Python backend were running, HTTP health returned 200, three contacts had `SUGGEST_ONLY`, and no contact had active auto-reply. There were zero live shadow draft feedback events. `PRAGMA integrity_check` returned `ok`. The previously focused personal-reply tests passed 79/79; this audit changed no reply-path code and sent no WhatsApp message.
