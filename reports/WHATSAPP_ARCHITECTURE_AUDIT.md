# Existing WhatsApp architecture audit

## Actual architecture

WhatsApp -> one Baileys Node bridge -> local WebSocket on port 8768 -> one Python WhatsAppService -> existing CommandService, router, policy and ActionLedger.

Runtime injects `whatsapp_service.transport` into the existing messaging tools in `jarvis/core/runtime.py`. No Python Baileys implementation or replacement router was introduced. `/commands` reuses the same bridge action handler for the existing standalone tool fallback without taking ownership of the persistent Python receive connection.

## Outgoing call graph

| Stage | Existing implementation / evidence |
| --- | --- |
| Router intent | SmartRouter and `core/router/extended.py` select `send_whatsapp_message`. Fake command: `message Barath saying JARVIS send test`. |
| Typed tool | `SendWhatsAppMessageInput(recipient, message, confirmation_ticket, allow_group)` in `whatsapp_tools.py`. Names are resolved inside the tool. |
| Contact resolution | ContactResolver loads contact database/VCF and configuration; resolves stable PN/LID IDs and returns ambiguity for multiple matches. This does not yet implement the full requested ContactRef/ThreadRef resource model. |
| Policy | Existing EXTERNAL_EFFECT policy creates a confirmation ticket. No fake-provider call occurs before approval. Cancellation clears the pending action. |
| Ledger | ExecutionEngine prepares and starts the action, verifies its outcome and records VERIFIED or UNCERTAIN. Non-idempotent uncertain actions are protected against automatic retry. |
| Python transport | `BaileysWebSocketTransport.send_text` -> `_call` -> `_send`, correlation ID and JSON action `send_text`, payload `{to, text, quoted}`. |
| Node handler | `src/index.js` dispatches `send_text` to `baileys.sendTextMessage(to, text, quoted)`. |
| Baileys method | `src/baileys_client.js` normalizes the recipient then calls `sock.sendMessage(toJid, {text}, options)`. |
| Verifier | Both executor postconditions and CommandService verifier use `whatsapp_transport_ack_probe`: SENT, actual message ID and transport acknowledgement must agree. This proves provider submission, not recipient delivery/read status. |

Media reuses `send_media` with `{to, file_path, mimetype, caption, is_voice_note}` -> `sendMediaMessage` -> file read -> `sock.sendMessage`. Other existing actions are `connect`, `disconnect`, `get_chats`, `get_status`, `get_message`, and `ping` (response action `pong`). `get_message` returns a locally cached normalized message, not an unrestricted server history query.

## Incoming call graph

`sock.ev messages.upsert` -> BaileysClient listener -> protocol normalization -> ChatIndex and onNormalizedMessage -> index.js `incoming_message` -> persistent WebSocket -> Python transport `_handle_event` -> WhatsAppService `_on_incoming_message` -> channel gateway -> WhatsAppInbox SQLite -> existing read/summary tools -> CommandService/UI.

Read-only acceptance mode marks incoming messages as history before gateway dispatch to prevent owner commands and automatic replies. It is an explicit diagnostic flag, not a consequence of degraded inbound health. Normal outgoing policy remains independent of history/live readiness. Group automatic replies remain blocked.

## Fixes in this audit

- Removed fabricated send IDs and unsupported-transport success responses.
- Missing receipts and submitted-request timeouts now report UNCERTAIN. Node socket exceptions are marked outcome unknown; no internal resend was added.
- Transport pending requests are cleaned on timeout, send exceptions and cancellation.
- Real transport receipt verification replaces generic success verification for the send tool.
- Executor preserves uncertain outcome data; CommandService preserves UNCERTAIN rather than presenting it as FAILED.
- Added a command connection on the same bridge to preserve the standalone tool fallback without displacing Python.
- Isolated AIHarness ledger, audit and method statistics in test temporary databases; the prior defaults contended with the running app database.

Files reused: bridge index/client/protocol/chat index, Python service/inbox/contact resolver, runtime, WhatsApp tools, router, CommandService, execution engine, policy, confirmation manager and ActionLedger. Audit changes touch bridge index/client/tests, Python transport/tool/postconditions/verifier/executor/CommandService, AIHarness, evidence tests and this report.

## Acceptance limits

Local fake-provider tests cover named LID resolution, policy confirmation, cancellation with zero sends, correlated transport schema, missing receipts, one-call timeout/exception behavior, verified ledger recording and uncertain ledger recording. Existing AI integration tests cover composing a message and drafting a reply from stored conversation before confirmation.

A generalized standalone DraftResource workflow (`draft a message to Arun` -> `send the draft`), all requested conversational resources and the broad tool families are not yet complete. They must not be represented as passing merely because an existing reply preview works.

Validation: 12 focused send-evidence tests pass, including question/read requests making zero sends; eight Node tests pass. The combined send/AI integration/ledger/omnichannel run passed 46 tests and failed one existing desktop acceptance case: Notepad launched without an observable matching process before the verifier deadline. This desktop process failure does not prove WhatsApp transport failure. `git diff --check` passes.

The owned runtime was restarted with the updated code and the same copied auth, retaining explicit read-only mode. Diagnostics report transport connected, event stream unverified, history incomplete and overall DEGRADED_LIVE. The new generation does not inherit a prior generation's known failed message test.

After this restart, stored inbound records increased from 417 to 475. SQLite quick_check remains OK, duplicate IDs remain zero, and `JARVIS CHECK 1002` remains absent. Current-generation live direct count remains zero; pending-notification completion remains false. This is further historical progress, not successful live acceptance.

At the initial audit checkpoint, no real outgoing acceptance message had been sent. The subsequent authorized test is recorded below; fake-provider evidence remains separate from real acceptance.

## Authorized outgoing acceptance, 2026-10-02

The user subsequently authorized exactly one `JARVIS send test` to the saved contact Naveen. ContactResolver returned one unambiguous PN contact. Both transport and Node retained read-only mode with a one-use exception for only that resolved recipient and exact text; regression coverage verifies mismatched recipient/text and second attempts are blocked. The exception has now been removed from the runtime.

CommandService preview selected `send_whatsapp_message` and created an EXTERNAL_EFFECT confirmation ticket for the exact text. The approved execution returned SENT with Baileys message ID `3EB0F9388263DE847D2D64`. Node diagnostics recorded `send_text`, its correlation request ID and the same message ID. The durable ledger contains exactly one matching send action, `act_b9f86f885de5`, under request `wa_naveen_send_once2_20261002`, in VERIFIED state with `whatsapp_transport_ack_probe` evidence. This verifies CommandService -> resolved contact -> policy -> Python WebSocket -> Node -> Baileys -> actual returned metadata -> verifier -> durable ledger. No second WhatsApp message was submitted. Recipient delivery/read status is not established by this receipt.

During acceptance, the initial `confirm tkt_...` command fell through to desktop dialog handling and pressed Enter; it did not call the WhatsApp send tool. The corrected `confirm ticket tkt_...` command executed the send after a fresh exact-text preview. Explicit short ticket confirmation is now recognized deterministically and covered by a regression test. The formatter's inaccurate SENT wording (`delivered`) was corrected to `sent`.

Post-send `summarize my whatsapp` used the real available inbox and returned PARTIAL_SUCCESS / PARTIAL_SYNC with the incomplete-history warning and actual stored message previews. Complete live/history acceptance remains pending.

Latest validation: 29 focused send/read-only/AI integration Python tests and nine Node tests pass. New offline preview telemetry showed 10,118 pending items and no completion event. A single explicit diagnostic batch request capped at 1,000 items is being tested through the same Baileys socket. It does not send chat content, modify dependency sources, force the buffer, or replace auth.

The bounded batch probe returned additional raw group and direct LID traffic (211 group nodes and 366 LID nodes in the observed generation). Stored inbound messages reached 640. The exposed buffer subsequently released, but pending-notification completion remains false, no offline completion event arrived, and current live direct count remains zero. The previous phone-delivered marker remains absent. Therefore larger batches demonstrate further backlog retrieval but do not prove complete sync or repair the live path.

One final incoming acceptance request is pending for `JARVIS INCOMING CHECK 1003`; baseline is 640 stored records in generation `dbb67999-a394-49b4-9d11-c2be0a61b5f8`. Automatic replies remain blocked. No fresh pairing or auth replacement was initiated.

The authorized outgoing receipt is also present in the real inbox with `is_from_me=1` and text exactly `JARVIS send test`. SQLite quick_check is OK and duplicate IDs are zero. A 35-second observation before any user confirmation found no new incoming marker; count reached 641. This is waiting for the requested human test, not a confirmed failed test.

Incoming live acceptance remains failed on the copied existing session: the phone received `JARVIS CHECK 1002`, but the actual inbox did not. Historical records grew to 417 and remain preserved; integrity was OK with zero duplicate IDs. History remains incomplete. The previous root-cause report documents 6.7.24 queue failure, rc14 queue improvement and ongoing decryption/NACK/pending-notification failures. Production uses exactly pinned 7.0.0-rc14; it is a release candidate.

The original production auth, backups, chat state and inbox remain preserved. A fresh pairing control has not been authorized or initiated. No permanent forced event-buffer flush is installed. `summarize my whatsapp` can return available stored messages with an incomplete-history warning; complete live acceptance is still unpassed.
