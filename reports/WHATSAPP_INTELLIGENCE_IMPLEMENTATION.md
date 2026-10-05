# WhatsApp intelligence implementation and acceptance evidence

Date: 2026-10-02. **Production acceptance remains open.** The implementation extends the existing architecture, but live incoming acceptance and the requested routing accuracy target have not passed. No additional real outgoing message was sent during this implementation.

## Architecture

```text
Baileys rc14 → existing Node bridge → existing WebSocket transport
  → persist original inbox message + scoped event
  → durable dispatch (two workers, serial per thread)
  → existing gateway / authenticated CommandService

Scoped event → background thread intelligence → existing model/embed cascade
Owner command → existing SmartRouter / planner → registered capabilities
  → existing policy, confirmation, ActionLedger and receipt verifier
```

There is one active bridge, one transport, and one authoritative inbox. Python does not call Baileys directly. Conversation intelligence uses the existing inbox database. The existing main database continues to hold the ActionLedger and personal style profiles. No replacement bot or routing service was introduced.

## Files changed

Primary new files:

- `jarvis/integrations/whatsapp/intelligence/{models,language,store,engine}.py`
- `jarvis/tools/system/whatsapp_intelligence.py`
- `jarvis/core/commands/provenance.py`
- `jarvis/db/migrations/whatsapp_inbox/009_whatsapp_intelligence.sql`
- `jarvis/db/migrations/whatsapp_inbox/010_whatsapp_dispatch.sql`
- `jarvis/tests/test_whatsapp_intelligence.py`
- `jarvis/tests/test_whatsapp_intelligence_capabilities.py`
- `integrations/whatsapp/bridge/test/intelligence_boundary.test.js`
- `jarvis/tests/fixtures/whatsapp_semantic_holdout*.json`
- `scripts/evaluate_whatsapp_semantics.py`

Existing integration points changed:

- WhatsApp inbox, transport/service, gateway, AI composer, media pipeline, personal-reply agent and policy.
- Runtime wiring, WorkingContext/WorkingMemory, existing SmartRouter/classifier, capability metadata and registry.
- Existing receipt verifier and postconditions; managed browser page-reading capability.
- Node message normalization, media bounds, on-demand media retrieval and cache persistence.
- Persistence writer migration backups and migration ownership; test harness isolation.

The working tree also contains earlier transport, unread reconciliation, send-evidence and diagnostic changes from this session. This report does not attribute every pre-existing dirty change to the intelligence implementation.

## Database changes

Inbox migration 009 adds scoped raw events, FTS5, thread versions, typed resources, generated-message attribution, processing jobs, vectors, language lexicon, watcher matches and metrics. Migration 010 adds durable incoming dispatch jobs. Raw inbox rows are preserved.

SQLite backups were confirmed present:

- `jarvis/data/whatsapp_inbox.before_intelligence_009.db`
- `jarvis/data/whatsapp_inbox.before_intelligence_010.db`

The migration files are scoped under `migrations/whatsapp_inbox`. Top-level 009/010 files are main-database compatibility markers. A fresh main database is tested to reach version 10 without creating `wa_events`. The first local startup, before this separation was corrected, created empty intelligence tables in the main database. They contain zero event/dispatch rows, have no consumers, and were retained to avoid an unnecessary destructive schema cleanup.

Future main-database migrations also take a SQLite backup before applying pending migrations. `PRAGMA quick_check` returned `ok` for the actual inbox and main database.

## Context engine

`ConversationContext` combines the actual current MessageRef, recent messages, quoted reply chain, historical results, extractive checkpoint, active topics, open items, attachments/links and a contact style profile. References retain thread identity, direction, timestamp, authorship and source.

Context is bounded to 12,000 characters. Selected older attachment/link evidence can be included explicitly without crossing threads. Current incoming bursts use actual stored message IDs; no synthetic “current-burst” message is used as factual evidence.

## Thread memory

Frames and resources are durable beside the inbox. Observed questions, requests, explicit commitments and source-anchored dates retain message IDs. Reconnect replay is deduplicated. Message edits invalidate vectors and supersede obsolete items; attachment/link extraction is tied to the source revision.

Checkpoint summaries are extractive, retain up to 40 excerpts/message IDs, and report their actual retained time span. They are bounded checkpoints, not a claim that every historical message has been summarized. Open-item filtering happens before limiting results, avoiding a false empty result caused by recent resolved items.

## RAG design

Every retrieval starts with an explicit thread filter. Recent rows and quoted chains are combined with same-thread FTS and optional dense retrieval. Dense search considers at most 2,000 rows, rejects invalid vectors, and filters by the actual embedding model. Edited events invalidate their vectors. Optional embedding failures do not replay completed side effects.

Actual persisted embeddings were observed using `nomic-embed-text:latest`. Keyword/raw history remains available when embedding or models are unavailable. External document/page content remains untrusted data.

## Style engine

The existing personal-reply profile and example index are reused. Runtime read-only mode can read stored profiles without enabling automatic replies. Genuine owner text is separated from generated echoes using request hashes and actual outgoing message IDs. Unknown historical outgoing authorship does not automatically train a profile.

Legacy composer style samples now come from the same contact's genuine owner events. Global samples and generated output are excluded. Style examples cannot authorize an availability claim, payment, promise or other factual assertion.

## Tanglish engine

Normalization is linguistic vocabulary/variant handling, not tool triggers. Raw text is preserved. The existing semantic classifier receives a vocabulary gloss alongside raw wording and typed conversation resources. Negation/correction and relative dates are retained separately. Lexicon observations require confirmation or three consistent observations before use; conflicting meanings are rejected.

Dates use the existing TemporalResolver and source timestamp with Asia/Kolkata anchoring. An old relative date cannot be repeated as a current plan without current supporting evidence.

## Reference resolution

Typed contact, thread, message, attachment, link, topic, item and draft identities are stored. Ordered WhatsApp results participate in existing WorkingMemory. Ordinals resolve within the selected typed result set and thread. Ambiguity requires clarification; no implicit first selection is made for multiple candidates.

WhatsApp resource ordinals cannot be reinterpreted by the generic app-opening follow-up path. Historical MessageRefs resolve by exact scoped ID rather than being restricted to the most recent 100 messages.

## Topic tracker

Topics currently use bounded lexical overlap, entities and temporal proximity, with source message IDs. They are useful observed clusters, not a measured semantic topic-resolution model. Independent evaluation of long-running topic continuity remains outstanding.

## Draft engine

Drafts persist recipient, content, revision, exclusions, grounding references, attachment IDs, thread version and validation. Editing keeps the DraftRef and recipient. Recipient changes require a new draft. Cancellation makes zero transport calls.

Sending requires the current revision, current conversation version, verified direct recipient, available attachment evidence and a passing grounding guard. A transactional submission claim prevents concurrent sends. Interrupted submissions recover as uncertain and are never automatically resent. Explicit negative owner constraints block submission before claiming the draft.

Model-extracted arguments are not owner evidence. Authenticated command text is propagated through a ContextVar; literal candidate text is owner evidence only when actually present in that request. Generated drafts can receive one bounded repair through the existing model, then must pass the same deterministic guard. Failed repair remains held.

## Auto-reply engine

The existing personal-reply agent, timed grants, coalescing, owner-takeover checks, quality gates and ledger path remain in use. Persistent pauses retain original grant expiration; resume cannot create or extend a grant. Groups remain blocked automatically. Grant validity and stop generation are checked again after drafting and before sending.

A saved allowlist alone does not enable automatic sending. Unsupported fallback promises and invented “owner is busy” statements were removed. Read-only acceptance mode disables automatic replies and all outgoing test exceptions are removed.

## Hallucination guard

The deterministic guard checks thread isolation, factual clause support, first-person owner evidence, exclusions, claim quotations/provenance and source-day relative dates. Swapped roles, invented numbers, dropped negations and recombined facts are held.

The guard is deliberately conservative: factual paraphrases without verified entailment require review. Downloaded document text/transcripts and fetched page excerpts can provide scoped evidence. Image-model descriptions are treated as interpretations and do not independently license factual claims. This is not a complete semantic entailment evaluator.

## Orchestration

Forty-one new metadata-backed tools are registered in the existing ToolRegistry and CapabilityRegistry. Requested aliases such as `whatsapp.message.reply_context` and `whatsapp.message.action_items` resolve to their registered implementations. Schemas, risk, confirmation, availability and verification metadata are discoverable.

Existing planner/DAG scheduling remains the cross-application path. Document/STT/vision providers and the managed browser are reused. Attachment saving is an exclusive file creation with SHA-256 verification. On-demand media download is thread-scoped, streamed and limited to 25 MB; cache capacity is bounded.

Persistent watchers currently support notification and explicit attachment saving. Saving runs registered download/save capabilities through the existing executor under an owner-created capability scope. Watchers ignore historical/own messages and claim each match once. Arbitrary deferred multi-application watcher DAGs are not implemented.

## Policy and safety

- Exactly one real outgoing message was authorized and previously sent. No additional message was sent here.
- Current Python and Node services both remain read-only. The one-send exception is removed.
- Actual submission receipts are distinguished from delivery/read acknowledgement.
- Owner identity matching is exact, with phone normalization; suffix coincidence does not establish ownership.
- Non-owner knowledge access is limited to that thread and cannot execute PC tools.
- Existing consequential confirmation, ActionLedger and verifier paths are reused.
- Negative owner constraints, stale drafts, ambiguity and uncertain submissions prevent automatic sending.
- Files are not overwritten; original auth and user history are preserved.

## Performance

Actual stored-context benchmark: 32 samples across eight direct threads, median **19.43 ms**, p95 **27.79 ms**, largest serialized context **6,324 characters**, and all checked MessageRefs remained in the requested thread. This benchmark excludes model generation, voice, browser and cold-start costs.

Actual fast-model classification used `qwen3:1.7b`: first-run holdout medians were approximately **1.92 s** and **1.91 s**. A cold case took approximately **11.09 s**. These are local measurements, not production latency guarantees.

Incoming content is persisted before heavier work. Two dispatch workers serialize each thread, while receipt handling remains available. Background batches and retries are bounded. Optional embedding is separated from one-time effects. The actual background queue drained to zero pending jobs after backfill.

## Test counts

The full WhatsApp Python suite passed **307/307 tests**; results are in `reports/whatsapp_brain_tests.xml`. The suite includes 100 adversarial factual-claim cases, language variants, thread isolation, source-date anchoring, stale drafts, concurrent submission, cancellation, dispatcher recovery, placeholder-to-decrypted dispatch, typed ordinals, pause/resume expiry, migration ownership/backups and bounded repair. An older burst-style test now requires clarification instead of copying an unsupported historical location claim; generic “read/summarize my chats” commands retain inbox-wide routing.

The Node bridge suite passed **15 tests**, including scoped on-demand media, streaming limits, view-once refusal, required transport IDs and uncertain-send behavior. Python compilation, Node syntax checks and `git diff --check` passed. These local tests do not substitute for real incoming or media acceptance.

## Measured accuracy

| Evaluation | Intent accuracy | English | Tanglish |
|---|---:|---:|---:|
| First untouched set A, before routing changes | 18/24 = 75% | 8/12 | 10/12 |
| Separate untouched set B, after general routing changes | 21/24 = 87.5% | 12/12 | 9/12 |
| Set B after it became development data | 21/24 = 87.5% | 11/12 | 10/12 |

These are small actual-model primary-intent pilots. They do not establish representative production accuracy, context accuracy, slot accuracy or model-based reference-resolution accuracy. After a set was inspected, subsequent measurements on it were labeled development results. First-run results remain preserved. **The requested >95% targets have not been demonstrated.**

## Failed test clusters

The earlier factual-promise tests depended on copying style examples into new commitments. Fixtures were corrected to use clarification replies for transport tests; unrelated promises are now explicitly expected to be held. The legacy status-as-contact bug was reproduced through the real CommandService and fixed through generic registered-capability label resolution; the runtime command now succeeds as `whatsapp_status`.

Actual-model misses remain around attachment search versus general thread search, Tanglish ordinal selection versus listing, and draft preview/edit distinctions. These require broader representative evaluation. Passing deterministic tests is not presented as a solution to those misses.

## Real WhatsApp acceptance

Outgoing evidence remains:

- Contact: **Naveen**.
- Exact text: **JARVIS send test**.
- Actual Baileys message ID: `3EB0F9388263DE847D2D64`.
- ActionLedger action: `act_b9f86f885de5`, status `VERIFIED` using the transport-ack probe.
- Correlated Node request and actual inbox echo match the receipt.

This proves submission, not delivery/read acknowledgement. It was not repeated.

Incoming acceptance remains **not passed**. After the owned read-only services were restarted with the current code, transport is connected but reports `DEGRADED_LIVE`, partial history, zero verified live direct messages and session decryption errors. The requested `JARVIS INCOMING CHECK 1003` marker is absent from both actual inbox tables. The intelligence store has 820 events and zero pending jobs. Stored historical events and successful outgoing submission do not prove live receiving.

The original auth was not deleted/replaced. The same previously selected recovery copy remains the sole active bridge auth directory. No fresh pairing or auth reset was performed. The already pending real incoming test request was not repeated.

## Known limitations and remaining acceptance

- Real incoming reception/decryption is unresolved; later user-only device/pairing action may be required if local session recovery cannot deliver the pending test.
- Broad >95% English/Tanglish/context/reference targets remain unproved and some measured intent sets failed them.
- Grounding holds unsupported factual paraphrases; it does not implement general semantic entailment.
- Topics/open-item resolution and summaries are conservative bounded observations/extracts.
- Arbitrary conditional multi-application watcher workflows are not implemented; notification/save are supported.
- Only one attachment per draft submission is supported. Automatic group replies remain unsupported.
- Media must still be available in the bounded bridge cache for on-demand download. Real media/STT/vision/browser flows have not all been accepted against this linked account.
- Dense retrieval has a bounded scan; full raw/keyword history remains separate. History completeness is never inferred from successful connection or an empty query result.
- Current deployment intentionally blocks all outgoing messages; auto-reply availability reports that restriction.

This report is an implementation/verification record, not a declaration that the entire production acceptance prompt is complete.