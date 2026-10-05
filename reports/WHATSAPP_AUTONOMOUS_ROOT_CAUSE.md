# Autonomous WhatsApp repair

## Source and runtime audit

The working tree contained earlier WhatsApp modifications and unrelated changes. `reports/whatsapp_safety_baseline.patch` records the initial tracked diff; no changes were reset. Recent WhatsApp history and staged state were inspected. Installed 6.7.24 `messages-recv.js` was compared byte-for-byte with the published npm tarball and matched.

The configured socket uses system CA, unavailable presence, recent history, default initialization queries, default own-event emission, the multi-file key store, 20-second connect timeout and 30-second keepalive. The application does not set an ignore-JID filter. Auth JSON parses when read as UTF-8; an initial Windows default-encoding check misreported the Unicode chat index. The actual inbox resides beneath `jarvis/data`, not root `data`.

## Upstream evidence

[Issue 2810](https://github.com/WhiskeySockets/Baileys/issues/2810) describes the same 6.7.24 initial buffer deadlock and truthy `offline="0"` handling. [PR 2779](https://github.com/WhiskeySockets/Baileys/pull/2779) describes a status-message acknowledgement stall; this is a hypothesis, not a confirmed cause in this account. [Official releases](https://github.com/WhiskeySockets/Baileys/releases) describe offline batching, mutex and app-state changes in the v7 release candidates.

The 6.7.24 probe received 62 raw message nodes but only emitted 25 buffered message objects, then stopped progressing. It never received offline completion. Direct LID nodes were present, and 22 nodes carried `offline="0"`. No custom JID filter was responsible. A manual flush previously released old records without restoring delivery and has been removed from the bridge.

An additional source-level reproduction isolates a 6.7.24 queue defect: after the first handler rejects, subsequent queued and newly enqueued nodes are never handled because `isProcessing` remains true. The reproduction returned `handled=[]` after a failed node followed by two valid nodes. rc14's per-node error catch allows both valid nodes to complete, covered by `offline_queue.test.js`. This proves the defect; the earlier silent runtime did not capture the specific node exception, so it is not evidence identifying which account record originally triggered the stall.

Correction to the initial acknowledgement hypothesis: normal direct messages use delivery receipts, so the absence of a final generic ACK alone is not proof of a protocol bug. rc14 changes newsletter acknowledgement and error handling as well as buffering and offline queues. The version comparison establishes aggregate improvement; it does not isolate every upstream change's contribution.

An isolated rc14 probe using a fresh auth copy emitted 189 message objects and delivered 130 to listeners in 60 seconds. A separate 180-second probe emitted 675 and delivered 586, continuing through the backlog without a bridge workaround. This objectively supports testing rc14, but does not yet establish complete offline drain or fresh live acceptance. Version 7.0.0-rc14 is pinned exactly in package.json and the lockfile; it is a release candidate, not a claimed newer stable release. No dependency source was patched.

## Application defects corrected

- Diagnostic connections previously stole the single backend socket. Read-only diagnostics now use a separate path, and additional backend connections are rejected.
- ChatIndex deltas omitted generation and event metadata. Deltas now preserve it.
- Read-only mode disabled replies but could still reach owner command processing. Incoming records now take the storage-only path; a regression test demonstrates this.
- Dashboard metadata could remain stale. It now refreshes through Python's current transport.
- Health requires current-session live direct-event evidence separately from transport and history readiness.

## Current experiment

The full bridge is running rc14 against `integrations/data/wa_candidate_recovery`, copied from the earlier candidate. The original auth has not been replaced. Both Python and bridge use read-only mode. Built-in session recreation was tested with the recent-message retry manager on this copy; cached outbound message lookup is disabled so this test cannot resend cached chats. It still reports cryptographic SessionError/PreKeyError failures and negative ACKs for LID traffic, and pending-notification completion remains false.

The upgrade allowed over 990 raw upserts and grew the actual SQLite inbound store from 187 to 416. It therefore repairs queue progress materially but has not established reliable current live delivery. Several restarts continued advancing through older timestamps before stalling again. This is not a completed foundation or evidence that fresh pairing is already required.

The user confirmed `JARVIS CHECK 1002` reached the primary phone. The current-code acceptance check found no marker after 35 seconds; SQLite stayed at 416. One controlled reconnect using the same copied session also failed to deliver the marker during the next observation window. An unrelated older inbound record raised the count to 417. Pending notifications stayed false, the buffer was released, live direct evidence remained zero, and negative ACK/decryption errors continued. CommandService marker and summary acceptance remain unpassed because no real marker record exists.

## Boundary reached

`FRESH_LINK_REQUIRED_FOR_CONTROL_TEST`: transport, listeners, wrapper routing, storage and read commands have been inspected; original auth parses and is preserved; old/new library versions and built-in copied-session recovery were tested; a new primary-phone-confirmed message still failed after a controlled reconnect. The next discriminating control is a separately paired linked device in `integrations/data/whatsapp_auth_fresh_test`. Pairing has not been initiated and requires explicit approval and phone interaction. This distinguishes old companion/session state from a remaining library/server issue; it does not assume relinking is already the repair.

No broader intelligence feature batch has begun, and the foundation is not marked fixed. No production auth was removed or replaced and no JARVIS chat message was sent. Known phone-delivered test failure is recorded only for its matching sync generation; ordinary inactivity never triggers `EVENT_STREAM_FAILED`.

Temporary auth copies and isolated dependencies remain under `integrations/data`; they contain private session data and are excluded from version control. Earlier probe logs were sanitized to retain only the JSON event records; dependency-emitted console objects were removed from those logs. Current probes suppress such output. No auth directory cleanup bypasses the prior automatic deletion rejection.

Validation so far: 136 focused WhatsApp/routing/follow-up tests passed; the broader WhatsApp selection passed 202 tests with three skips. After adding current-generation health and chat-delta coverage, 36 focused Python tests and five Node bridge tests passed. Real read commands returned partial results with stored messages and history warnings. SQLite quick-check is OK and duplicate message ID count is zero.

Latest focused validation: 46 Python tests and six Node tests pass. The audit also found direct `@lid` recipients being mistaken for groups in the existing send tool; the group guard now recognizes both direct PN and LID JIDs, with a fake-transport regression test. No real WhatsApp send was used to test this fix.

## Subsequent authorized send and incoming diagnostics

On 2026-10-02 the user explicitly authorized exactly one `JARVIS send test` to Naveen. That test passed the existing CommandService, resolved-contact, policy, Python WebSocket, Node/Baileys receipt and durable VERIFIED ledger boundaries. The receipt ID is `3EB0F9388263DE847D2D64`. No second chat message was submitted; all sends are blocked again. See `WHATSAPP_ARCHITECTURE_AUDIT.md` for the trace and acceptance limits.

New metadata-only preview telemetry exposed a backlog of over 10,000 items. One bounded `offline_batch` control request for 1,000 items through the same copied-auth socket caused additional raw direct LID traffic and grew the durable inbox to 640 records. The event buffer released without forced flushing, but completion stayed absent and no current live direct event was proven. This is a useful backlog diagnostic, not evidence that a fresh link is already necessary or that live reception is repaired. The upstream [initial buffer issue](https://github.com/WhiskeySockets/Baileys/issues/2810) remains relevant as a reported similar failure, not proof of this account's server state.

The original production auth and inbox remain preserved. A final incoming marker has been requested once. No fresh pairing was initiated, and ordinary silence before the user's confirmation is not recorded as a failed acceptance test.
