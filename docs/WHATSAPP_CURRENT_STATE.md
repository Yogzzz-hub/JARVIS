# WhatsApp current state

## 2026-10-04 restart and one-shot acceptance

The phone-confirmed `JARVIS RESTART CHECK 1004` reached the fresh bridge in the restarted generation at 07:40:39 UTC. Raw node to `messages.upsert` took 16 ms; the exact ID passed normalization, WebSocket and Python, and SQLite holds one incoming row. **Restart-generation LIVE_INCOMING_TEXT = VERIFIED.**

One authorized outgoing marker, `JARVIS outgoing acceptance 1004`, was sent to the same dedicated dad-chat thread using a read-only bridge with a one-use exact-match exception. Baileys returned message ID `3EB00DE5A23955CBB82465`; ActionLedger recorded the acknowledgement, and SQLite holds one matching outgoing row. Receiving-phone confirmation is pending, so delivery acceptance remains **PARTIAL**. General sending and auto-reply remain disabled. The detailed trace is in [the final acceptance tracker](WHATSAPP_FINAL_ACCEPTANCE.md).

## 2026-10-04 fresh companion update

The fresh, Mac OS-labelled Baileys companion is now the configured runtime auth in `config/whatsapp.toml`, the bridge default, and `start.bat`. Startup checks the auth path, registration, connection and notification completion; an occupied port using the archived auth fails closed. The current fresh bridge passes that read-only check. Startup defaults to read-only unless the operator explicitly sets `JARVIS_WHATSAPP_READ_ONLY=0`. The old auth, its backup and SQLite history remain intact.

Three phone-confirmed fresh direct messages crossed raw node → `messages.upsert` in 10, 3 and 4 ms, then reached the normalizer, WebSocket, Python and SQLite once per ID. [The exact-ID A/B report](WHATSAPP_FRESH_LATENCY_AB.md) has the evidence. **LIVE_INCOMING_TEXT = VERIFIED** for that generation. This does not establish outgoing, media, auto-reply or reboot acceptance.

Direct, group and combined reads now use explicit scopes. Broadcast, status and newsletter JIDs cannot enter these scopes or the auto-reply path. `READY` in the inbox means the live stream and current chat/badge snapshot are available; it does **not** prove every historical message was fetched. Diagnostics now report local history availability and chat snapshot currency separately, with `history_complete=false` until a full-message-history proof exists.

The table below is the earlier 2026-10-03 audit snapshot; its live and auth rows were superseded by this update.
Faster-Whisper and PyAV now import locally; the old table's voice dependency label is also superseded, while live voice acceptance remains pending.

Audit date: 2026-10-03. Labels describe observed behavior, not the presence of a function. **The subsystem is not complete.** The live acceptance result is in [WHATSAPP_LIVE_VERIFICATION.md](WHATSAPP_LIVE_VERIFICATION.md).

| Feature | State | Evidence / limit |
| --- | --- | --- |
| Single Baileys transport | WORKING | Existing `integrations/whatsapp/bridge/src` connected with registered auth in read-only mode. |
| Auth preservation | WORKING | Existing auth directory retained; no relink or reset. Unregistered sessions no longer request pairing for a baked-in phone number. |
| WebSocket transport | WORKING | Existing `127.0.0.1:8768` bridge and Python consumer connected in this run. |
| Protocol normalization | PARTIAL | `protocol.js` normalizes messages and media; edits/revokes are not externally accepted. |
| Live incoming text | NOT_VERIFIED | A controlled, phone-confirmed message must match one new stored ID in this generation. Prior controlled tests failed. |
| Incoming media / voice | NOT_VERIFIED | Parser, download and processing paths exist; no current external acceptance. |
| History sync completeness | PARTIAL | Current generation has no verified complete snapshot; status remains `PARTIAL_SYNC`. |
| Persistent inbox and dedupe | WORKING | Existing SQLite has 2,767 distinct messages at audit time; integrity check `ok`. Duplicate-ID prevention has local tests. |
| FTS and scoped search | WORKING | Existing FTS5 store returned a real same-thread hit; complete-history search cannot be claimed. |
| Actual-message summaries | PARTIAL | Local summary used available stored messages and reported `PARTIAL_SYNC`; full history coverage is unverified. |
| Contact resolution | PARTIAL | Stable JID and ambiguity handling exist; real ambiguous-contact acceptance is pending. |
| Typed context / references | PARTIAL | Same-thread context built ten recent refs from the real store; cross-turn external acceptance is pending. |
| Drafting and grounding | PARTIAL | Durable drafts, revisions, evidence checks and cancellation have local tests; live reply acceptance is pending. |
| Outgoing text | PARTIAL | One previously authorized message was sent in an earlier session; no new send was authorized in this request. Current read-only mode blocks all sends. |
| Media / attachments | PARTIAL | Bounded on-demand download and file checks pass local tests; external media round trip is pending. |
| Voice transcription | DEPENDENCY_UNAVAILABLE | Requires available STT and a real downloaded voice note. No current live acceptance. |
| Personal style | PARTIAL | Contact-specific profiles and user-authored provenance checks exist; current account style quality not independently accepted. |
| Auto-reply grants | PARTIAL | Time-limited, direct-chat policy and expiry have local tests; no real auto-reply acceptance. Default is off. |
| Group auto-reply block | WORKING | Structural group gate and local tests; no autonomous group send was performed. |
| Owner remote commands | NOT_VERIFIED | Stable owner identity check routes to CommandService when enabled; current listener is read-only and has no command service. |
| ActionLedger / uncertain send | PARTIAL | Consequential send and uncertain-state code paths have local tests; external timeout reconciliation is unverified. |
| Notifications / watchers | PARTIAL | Durable notification and attachment watchers exist; deferred general workflow DAGs are not implemented. |
| Live full acceptance | NOT_VERIFIED | Requires controlled incoming, reply, attachment, voice, auto-reply and uncertain-send evidence. |

The last recorded failure was a phone-confirmed direct message absent from SQLite while the bridge showed connection. The active read-only listener is for diagnosis only. A connected transport and aggregate upsert counts do not establish that the known message arrived.
