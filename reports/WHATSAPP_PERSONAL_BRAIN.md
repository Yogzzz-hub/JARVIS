# WhatsApp personal communication brain audit

The current frozen-architecture evaluation is in [WHATSAPP_PERSONAL_BRAIN_EVALUATION.md](WHATSAPP_PERSONAL_BRAIN_EVALUATION.md). It separates measured semantic failures from style proxies and leaves generated auto-reply off.

## 2026-10-05 shadow-mode update

The normal fresh Baileys companion and Python backend are running read-only. The bridge runtime check returned `READY`; the local personal contacts endpoint shows three `SUGGEST_ONLY` contacts and zero auto-reply contacts. The one-shot send exception is empty. No WhatsApp chat message was sent during this update.

The owner reviewed and approved the first contact's 35-row private batch and one additional paired row. Exactly 36 historical rows now have `VERIFIED_LEGACY_OWNER`; the other two contact batches remain unreviewed. That contact is `VERIFIED_STYLE_BUILDING`. There are 65 train examples and one newer verified holdout pair. Its one-case replay is available for owner rating in an ignored private local review sheet. One case cannot establish style quality or qualify any contact for auto-reply.

An exact recent outgoing message can now be owner-attested through a natural confirmation such as “that last message was mine.” The resolver requires one unambiguous candidate and checks JARVIS send records before assigning manual provenance. An ambiguous or unconfirmed `fromMe` message remains unverified. The review API supports APPROVE_ALL, APPROVE_SELECTED, REJECT_SELECTED and CANCEL for one contact's prepared batch.

The [shadow-mode status report](WHATSAPP_SHADOW_MODE.md) gives current counts and test results. A generic offline local probe generated eight of nine drafts; median generation was 6.2 seconds and p95 was 12.2 seconds. No fresh direct incoming message arrived for a live shadow draft during this pass, so live draft acceptance and latency remain unmeasured. Generated auto-reply is still disabled.

Later on 2026-10-05 the owner explicitly approved both remaining 35-row review sheets and one supplemental row for the first contact. The final count is **106 `VERIFIED_LEGACY_OWNER` rows**, with all three contacts in `VERIFIED_STYLE_BUILDING`, **67 train examples** and **10 newer verified holdout pairs**. Local replay generated all 10 cases: language match 40%, length match 70%, emoji and modality match 90% each. The semantic and style proxy scores are recorded in the shadow report, but ten cases and pending owner ratings cannot establish reliable quality. The read-only bridge and Python listener remain running; no generated auto-reply or general send was enabled.

The owner then identified a replay draft that reversed an incoming request for a work update. Inspection of that contact's preceding messages confirmed the contact was asking the owner for progress; the thread did not contain an owner-authored current status. The draft path and replay now block a factual answer to short update requests without owner-sourced status. This is a safe hold, not evidence that JARVIS can answer such follow-ups correctly. The old wrong-direction draft remains unrated in the private sheet. See the [current shadow report](WHATSAPP_SHADOW_MODE.md) for current metrics; earlier figures above describe the pre-correction run.

The owner clarified that, when a question lacks enough context, JARVIS may suggest a brief question in the owner's own style. The same-contact history contains one previously approved owner-authored `?` before this holdout. For an unresolved short progress request, the live draft path can now offer that verified wording as a **review-only clarification draft**; it is never counted as a factual answer and its quality report blocks autonomous sending. Unverified legacy, generated, future and other-contact text cannot supply this wording. The latest replay classified this case as a clarification opportunity rather than a successful answer. The historical wrong-direction draft remains preserved for review.

Date: 2026-10-04. This work extends the existing Baileys, Python inbox and personal reply agent. General sending and auto-reply remain disabled in the live listener. The earlier one-shot outgoing delivery still awaits confirmation on the receiving phone.

## Implemented locally

| Area | State | Evidence |
|---|---|---|
| Chat import and pair mining | Implemented, limited source evidence | Existing export/feed importer and one SQLite example store; pairs can include a preceding contact burst or an explicit reply target. Reimport is idempotent by source message ID. |
| Provenance and style drift | Verified learning path implemented | Exact-ID, owner-attested manual sends are checked against ActionLedger, Baileys/JARVIS send records and unresolved send windows before `VERIFIED_MANUAL_OWNER_SEND` is assigned. Unmatched `fromMe` rows remain unverified. Edited and unchanged approved AI drafts retain separate provenance and weights; only verified final sends enter style evidence. |
| Holdout isolation | Implemented | Reply pairs are split chronologically into train, development and holdout. Retrieval reads train only; contact and global profiles exclude later evaluation replies. |
| Global memory and privacy | Implemented | One encrypted example table, scoped by contact. General fallback contains aggregate style statistics; phrases and private text from other contacts are stripped. Historical examples are never treated as factual authority. |
| Emoji and sticker behavior | Partial | Owner-text profiles now count TEXT, TEXT_EMOJI and EMOJI_ONLY modes. A profile-derived predictor treats sensitive/urgent cases as text. The owner-only sticker index stores a hash, encrypted local media reference and scoped context embedding with cooldown. It returns candidates and never sends a sticker. No owner sticker has been indexed on this machine. |
| Conversation understanding and context | Partial | Existing bounded thread/context builder and local intelligence state; lightweight conversation-mode labels added. Full state fields such as promises and pending decisions are not independently validated. |
| Reply generation and critics | Implemented with limits | Existing compact local generation uses the configured `chat` role (`qwen3.5:4b`, then `llama3.2:latest`); a poor style score may trigger at most one revision. Semantic and same-thread factual checks remain authoritative, and copied historical facts no longer count as grounded. Model/style quality needs real holdout evidence. |
| Auto-reply | Off for generated replies | Production has `generated_auto_reply_enabled=false`. Timed direct-contact grants and group block remain as separate gates. The offline evaluation requires verified owner source rows and verified holdout; legacy-only contacts remain draft only. |
| Feedback | Implemented | SEND, EDIT, REGENERATE, NO_REPLY, BAD_STYLE and WRONG_CONTEXT are recorded. Feedback events are append-only. Candidate and final text are encrypted with edit ratio and a small style delta; only verified sent final text becomes style data. |
| Offline evaluation | Legacy bootstrap measured | Chronological replay now reports `VERIFIED_HOLDOUT` and `LEGACY_HOLDOUT` separately. Five legacy drafts were generated; verified holdout remains empty. It never sends or automatically clears auto-reply. |

## Local data audit

The new [legacy provenance audit](WHATSAPP_LEGACY_PROVENANCE_AUDIT.md) classified **646** historical `fromMe` rows: **486** lower-confidence legacy owner candidates, **158** unknown and **2** known JARVIS sends. It rebuilt **76** reply pairs across **30** direct contacts, with **26 low-confidence profiles**, **3 draft-ready contacts**, **5 legacy holdout pairs**, **0 verified holdout pairs** and **0 indexed stickers**. There are still **0 verified owner source rows**. The previous zero-profile audit was the state before this recovery; these new profiles are provisional draft evidence, not verified human authorship. No private chat content was uploaded.

An exported chat may include forwarded or externally generated outgoing text. Export `fromMe` lines are now provisional `LEGACY_OWNER_LIKELY` evidence. Optional compact same-contact batch review can approve rows as `VERIFIED_LEGACY_OWNER` or reject them while retaining the original classification. Legacy review never clears the auto-reply gate. The stronger evidence path is an exact-ID verified manual send or a final owner edit after a verified send.

## Acceptance limits

No authoritative per-contact style accuracy, sticker choice, reply-needed accuracy, semantic appropriateness, unsafe auto-send rate, generation latency or live auto-reply result can be stated with zero verified holdout pairs. The local model produced five legacy-holdout drafts in two contacts, but that sample is too small for approval and some language/length proxies failed. Sticker media selection and actual sticker sending have not passed a live test. Voice, attachment and reply-to-message live acceptance are tracked separately in [the WhatsApp final tracker](../docs/WHATSAPP_FINAL_ACCEPTANCE.md).

A 100-call CPU-only fast-path probe (lightweight understanding, cached profile lookup and empty example retrieval) measured p50 **0.93 ms**, p95 **2.03 ms**, p99 **10.33 ms**. It excludes model generation and populated-index retrieval, so it is not an end-to-end reply latency result.

Production generated auto-reply remains off. Three existing draft-ready contacts are set to `SUGGEST_ONLY`. The read-only listener can create reviewable personalized drafts for new unanswered incoming text, and an on-demand `draft-latest` API uses the same store, profile, context and critics. The bridge/listener was not running at this audit, so natural live draft creation awaits a read-only restart. There are still zero verified owner rows and zero verified holdout cases. [The flywheel report](WHATSAPP_VERIFIED_STYLE_FLYWHEEL.md) lists per-contact maturity and evidence counts without message bodies.

Verification: the focused provenance and personal-reply suites passed **83/83** after updating older fixtures that treated exported `fromMe` as proven authorship. Two subsequent focused tests passed for append-only feedback and an inbox-backed reviewable draft (**85 focused tests passing in total**). Node bridge suite passed **24/24**. No live auto-reply or sticker send was performed.

## Requested status checklist

| Check | Status |
|---|---|
| CHAT IMPORT | Implemented for explicit exports and conservatively classified local direct-chat history. |
| PAIR MINING | Implemented for contact bursts and explicit reply targets. |
| GLOBAL MEMORY | One encrypted SQLite example store. |
| CONTACT STYLE PROFILES | 26 provisional low-confidence profiles; zero verified local profiles; derived maturity states added. |
| GENERAL USER STYLE | Implemented as aggregate fallback without cross-contact text. |
| EMOJI MODEL | Weighted legacy text frequencies, placement and combinations; limited local evidence. |
| STICKER MEMORY | Owner-only scoped index implemented; zero stickers indexed. |
| CONVERSATION STATE | Bounded recent thread and same-thread semantic context; broader state fields remain unvalidated. |
| EXAMPLE RETRIEVAL | Contact-scoped, train-only and time-filtered. |
| FACT/STYLE SEPARATION | Historical example facts excluded from factual grounding. |
| REPLY GENERATOR | Local configured 4B chat role; real style quality unmeasured. |
| STYLE CRITIC | Existing score plus at most one bounded revision. |
| SEMANTIC CRITIC | Relevance, same-thread evidence and sensitive-topic checks; independent real validation pending. |
| FEEDBACK LEARNING | Verified final edited text and lower-weight unchanged owner-approved AI output retain distinct provenance. |
| STYLE DRIFT PROTECTION | Generated, draft-only and unattributed messages excluded. |
| AUTO-REPLY DECISION | Generated auto-reply explicitly disabled; timed grants, profile and offline-evaluation gates remain. |
| DIRECT-ONLY AUTO REPLY | Structurally restricted to direct JIDs. |
| SENSITIVE GATE | Local gate; live negative acceptance pending. |
| CROSS-CONTACT PRIVACY | Scoped examples and statistical-only global fallback. |
| OFFLINE EVALUATION | Five legacy holdout drafts replayed; zero verified holdout examples locally. |
| LATENCY | CPU-only preprocessing p50 0.93 ms, p95 2.03 ms; generation unmeasured. |
| PYTHON TESTS | 83 focused suite tests plus 2 new focused regression tests passed. |
| NODE TESTS | 24 passed. |
