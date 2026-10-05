# WhatsApp live verification

## 2026-10-04 fresh companion result and restart

The fresh Mac OS-labelled companion passed three phone-confirmed incoming direct text probes. Exact message IDs crossed Baileys raw node → `messages.upsert` in 10, 3 and 4 ms, then reached normalization, WebSocket, Python and SQLite once per ID. [The A/B record](WHATSAPP_FRESH_LATENCY_AB.md) gives IDs and timestamps. **LIVE_INCOMING_TEXT = VERIFIED for generation `a2f5bb28-c971-42ae-b83f-ee440ee6b1ca`.** This supersedes the 2026-10-03 old-session `NOT_VERIFIED` conclusion below, without changing its historical evidence.

Normal startup now pins the fresh auth. On 2026-10-04 the read-only Node bridge and Python listener were restarted against that auth, preserving 2,996 SQLite rows with `PRAGMA integrity_check=ok`. The current bridge reports registered, connected and pending notifications complete; Python records that current generation and local history availability. A complete current chat snapshot was not received, and **new-generation live incoming remains `NOT_VERIFIED`** until the requested `JARVIS RESTART CHECK 1004` is phone-confirmed and traced by exact ID. JARVIS sent no chat message during restart.

### Restart marker candidate at 07:40 UTC

The owner reported sending `JARVIS RESTART CHECK 1004`. The active fresh bridge generation `8370865b-6b4a-4ae0-af83-ce31229b839e` observed incoming direct-chat ID `AC7ECAAD4C884744B70C0CF61070F712` in the same thread as the earlier dad-chat test. Its persisted text matches the marker case-insensitively. The raw node was at **07:40:39.935 UTC** and `messages.upsert` at **07:40:39.951 UTC**, giving **16 ms** within Node. The same ID passed the upsert handler, accepted normalization, bridge callback, WebSocket `WRITE_ACCEPTED`, Python receive/schema/dispatch, and SQLite `INSERTED`; later replay was `DEDUPE_EXISTING`. SQLite contains **one row** for that ID and `PRAGMA integrity_check=ok`. The current generation reports connected and pending notifications complete. Primary-phone receipt is still awaiting explicit owner confirmation, so `event_stream_verified` remains false and **new-generation `LIVE_INCOMING_TEXT = NOT_VERIFIED`** until that confirmation is recorded. JARVIS sent nothing.

The owner subsequently gave the phone-displayed time as **1:10**. The phone's AM/PM was not stated, but the source and raw-node timestamps are 07:40 UTC = **1:10 PM IST**, so this is treated as confirmation of the requested marker on the primary phone. The acceptance record was written against the same current generation and exact stored ID with a post-probe timestamp. Inbox diagnostics now report `event_stream_verified=true`; **restart-generation `LIVE_INCOMING_TEXT = VERIFIED`**. This proves incoming text, not outgoing or complete historical coverage.

### One authorized outgoing marker, receiving-phone check pending

The fresh bridge restarted in read-only mode with a one-use exception for the same dedicated dad-chat thread and exact text `JARVIS outgoing acceptance 1004`. At approximately 07:54 UTC, request `373c72e1-af54-4fab-b217-5170c07b7127` returned Baileys `SENT` and message ID `3EB00DE5A23955CBB82465`. The bridge diagnostic matches that request and ID. ActionLedger recorded provider acknowledgement and local persistence evidence; its status remains `EXTERNALLY_ACKNOWLEDGED` pending the receiving phone. SQLite has exactly one `is_from_me=1` row with that ID, exact text and chat, and integrity `ok`. The receiving phone has not yet confirmed receipt. No reply, media, or auto-reply send was attempted.

Date: 2026-10-03. The existing registered Baileys bridge and Python service were started in **read-only mode** with the existing auth directory. The bridge reported `CONNECTED`, and Python printed `JARVIS_READ_ONLY_WHATSAPP_LISTENER_RUNNING`. The current bridge generation was observed through `/diagnostics`; the diagnostic connection did not replace Python's WebSocket consumer. No outgoing WhatsApp message was sent.

The bridge received queued/history upserts and the existing SQLite inbox count rose while the listener ran. At the latest metadata-only check, the bridge counted 257 `messages.upsert` events and 2,787 stored messages, but **zero live direct messages**. `received_pending_notifications` remained false and there was no current history-complete event. The bridge reported 85 LID, 51 group and 10 broadcast negative acknowledgements with code 500; message bodies and full identities were not logged. The inbox reported `DEGRADED_LIVE` and `PARTIAL_SYNC`. Queue/history delivery is not a controlled live acceptance.

The pinned Baileys package enables automatic per-contact session recreation by default, but this bridge had it disabled unless `JARVIS_WHATSAPP_SESSION_RECOVERY=1`. After recording repeated `Bad MAC` decrypt failures, the existing auth was copied to an ignored local backup (1,462 files, 1,101,354 bytes), without clearing or relinking the active auth. The same read-only bridge was restarted once with that recovery flag. It connected, processed 47 queued upserts and reported 13 code-500 negative acknowledgements at the first poll, but still zero live direct messages. This is a diagnostic control, not a verified repair. The code's default remains unchanged pending evidence.

A phone-confirmed new direct message from a second account has been requested while the read-only listener is running. Acceptance requires matching its exact persisted incoming message ID, with a timestamp after probe start, to the current generation. Aggregate `messages.upsert` counts alone no longer set `EVENT_STREAM_VERIFIED`. Until that match is made, live incoming is **NOT_VERIFIED**. Outgoing reply, attachment, voice, granted auto-reply, owner remote command and uncertain-send recovery remain externally unverified.

## 2026-10-03 exact-ID boundary trace

Temporary opt-in metadata-only traces now cover Baileys raw message nodes and `messages.upsert`, handler entry, normalizer accept/reject reason, bridge callback, WebSocket write/queue result, Python schema/dispatch and SQLite insert/dedupe. They contain IDs, JIDs, timestamps, message types and generation, but no message bodies. The trace files are ignored local data under `integrations/data/` and `jarvis/data/`. Old socket upsert listeners are detached on reconnect; the new listener checks its socket generation before acting. Read-only mode blocks all sends.

In the first traced generation, 66 raw upsert records reached the Baileys emitter and 65 reached the handler by the inspection instant; their **sets of message IDs matched**, so the one-record count difference was a timing snapshot. The normalizer recorded 11 accepted bodies, 11 pending decryption placeholders, 29 unsupported protocol messages and 14 empty-body rejections. All 11 accepted IDs appeared in the bridge callback, WebSocket dispatch, Python receive/schema and SQLite trace. SQLite recorded one insert and one later dedupe/upsert for each ID; unique message identity remained intact. These were queued/older messages, **not** the controlled new direct message.

The controlled message sent before this instrumentation has no known exact ID in the new trace, so its missing boundary cannot be reconstructed honestly. At 2026-10-03 15:41 UTC the traced read-only listener was connected in generation `3acfd386-3f2a-4435-9c9e-5e81ac2665eb`. This generation had 63 raw message nodes, 88 upsert messages, 88 handler entries, 25 accepted normalizations and 25 accepted WebSocket writes; these are backlog/other traffic, not proof of the controlled message. The bridge reported zero live direct messages. A new unique marker `JARVIS TRACE 1003` has been requested; at 15:41 UTC it had zero SQLite rows, and phone receipt of that marker had not yet been confirmed. Final acceptance remains **NOT_VERIFIED** pending one new phone-confirmed direct message and its exact-ID trace.

Transport regression tests: Node `npm test` passed 17/17 after the listener-generation guard and raw-node trace changes. Python WhatsApp-focused tests passed 358 with 3 skipped. The raw-node trace tap only writes metadata from Baileys node attributes. No JARVIS action or WhatsApp send was executed during these diagnostics.

At 2026-10-03 17:14 UTC (22:44 IST), the previous tool-session processes had ended, so the same read-only Node and Python listeners were restarted as hidden background processes against the existing auth and inbox. The bridge was `CONNECTED` in generation `e61d82de-6df3-46cf-8879-c87ababc5f24`. In this generation, 87 emitted upsert records matched 87 handler entries; 32 accepted normalizations reached WebSocket dispatch and 32 reached Python receive/schema/dispatch. Some IDs recur in the queued backlog, so these are event counts, not unique new messages. SQLite `PRAGMA integrity_check` returned `ok`. The unique marker `JARVIS TRACE 1003` still had zero inbox rows and no phone confirmation. Live incoming remains **NOT_VERIFIED**.

## 2026-10-03 phone-confirmed marker check

The owner confirmed that `JARVIS TRACE 1003` was visible on the primary phone. Read-only inspection at 17:20 UTC (22:50 IST) found zero exact or whitespace-trimmed matches in `whatsapp_messages`; `PRAGMA integrity_check` was `ok`. The bridge remained `CONNECTED` in generation `e61d82de-6df3-46cf-8879-c87ababc5f24` (opened 17:13:23 UTC), with the same 87 upserts and zero live direct messages. Its last raw Baileys message node was at 17:13:23 UTC, and its last upsert handler event was at 17:13:49 UTC. Both are before the phone-confirmed marker report and the 17:14 UTC probe check. No raw message node or upsert has been observed since. The last Python trace event was also at 17:13:49 UTC. Existing queued/backlog IDs are excluded from this acceptance check.

| Required field | Observed value for the controlled marker |
|---|---|
| phone_received | true (owner report) |
| baileys_raw_seen | false after the probe start |
| baileys_upsert_seen | false after the probe start |
| handler_seen | false |
| normalizer_result | NOT_SEEN |
| normalizer_reason | No matching post-probe Baileys event reached the normalizer |
| websocket_seen | false |
| python_seen | false |
| sqlite_match_count | 0 |
| message_id | UNKNOWN: the phone-visible message ID was not supplied and the bridge emitted no post-probe raw ID |
| chat_jid | UNKNOWN for this message |
| timestamp | UNKNOWN for this message; confirmation was received by 17:20 UTC |
| current_generation | `e61d82de-6df3-46cf-8879-c87ababc5f24` |

**First observed missing boundary: primary phone → Baileys raw message node.** Because the exact phone-side message ID and send timestamp are unavailable, this identifies the first *observable* missing boundary in the current trace, not proof that a particular raw node ID was rejected. No downstream filter or normalization rejection can be assigned to this marker. `LIVE_INCOMING_TEXT = NOT_VERIFIED`. No code was changed for this check, and JARVIS sent nothing.

## 2026-10-04 sync recovery, acceptance pending

The owner identified **Google Chrome (Ubuntu)** as the Baileys companion in the phone's Linked devices list; it showed **Active** at 08:58 IST. A separate Windows entry last active the prior evening is not Baileys. Two phone-visible `JARVIS RUN A 1004` messages at 08:55 and 08:57 IST eventually reached SQLite as two distinct incoming message IDs. A recovery-enabled generation first saw one of these as an encrypted/pending body. A later read-only generation submitted one bounded offline-batch control request, received offline completion, and changed `receivedPendingNotifications` from `false` to `true`. It then accepted and forwarded both delayed IDs through the WebSocket and Python inbox; SQLite inserted one row per ID and deduped later replay of the first ID. [The session-health report](WHATSAPP_BAILEYS_SESSION_HEALTH.md) records the IDs and boundary timestamps.

This demonstrates backlog recovery, **not live post-completion delivery**. The distinct phone-confirmed `JARVIS RUN B 1004` marker still had zero SQLite rows at the check. A new `JARVIS LIVE 1004` message was requested after offline completion; its receipt on the main phone and exact-ID trace remain pending. `LIVE_INCOMING_TEXT = NOT_VERIFIED`; JARVIS remains read-only and sent no chat message.

## 2026-10-04 post-completion live candidate

The owner confirmed `JARVIS LIVE 1004` was visible on the primary phone at **09:13 IST** and identified the same-chat raw node at 09:13:24 IST as candidate ID `AC657A1013A35C1194C31EFEF0262EAA`. In generation `baa22f51-9acb-42e7-814e-463efd4ef649`, Baileys' `CB:message` tap recorded that ID at 03:43:25.143 UTC with node type `text`, direct `@lid` chat and node timestamp 03:43:24 UTC. It matched the direct chat of the earlier Run A messages. At 03:47:26.808 UTC, a `messages.update` event with the same ID had **no message body** (`NO_MESSAGE_BODY`).

No `messages.upsert`, bridge handler, normalization, WebSocket dispatch, Python receive or SQLite insert for this ID appears in the metadata traces. The exact marker text had zero SQLite rows; `PRAGMA integrity_check` returned `ok`. No per-ID `baileys_decrypt_error` entry (`PRE_KEY`, `SESSION_RECORD`, `BAD_MAC` or other) was recorded, and no per-ID retry result was recorded. The bridge later reported `buffer_active = false` and a released buffer, but the ID still had not advanced. Its precise Baileys internal reason is **unresolved**: the current metadata does not distinguish an internal queue stall, handler skip, ACK/status failure or an unlogged exception for this ID. The observed first missing boundary for this candidate is **raw Baileys node → `messages.upsert`**. This candidate is tied to the phone message by chat and second-level time; a phone-side message ID was not available for independent identity confirmation.

`LIVE_INCOMING_TEXT = NOT_VERIFIED`. No new WhatsApp send, relink, auth wipe or downstream code change was performed while tracing this candidate.

### 09:20 IST delayed completion of the same candidate

The provisional raw→upsert failure above **resolved in the original generation before any diagnostic package restart**. At 03:50:49.254 UTC (09:20:49 IST), Baileys emitted a `notify` `messages.upsert` for **the same ID** `AC657A1013A35C1194C31EFEF0262EAA` with the original 03:43:24 UTC message timestamp. The bridge handler saw it at 03:50:49.257, normalization accepted it at 03:50:49.258, and the existing WebSocket accepted the write at 03:50:49.277. Python received and schema-accepted it, then SQLite inserted one direct incoming text row at 03:50:49.287. Python's later service pass recorded `DEDUPE_EXISTING`; the exact ID and `JARVIS LIVE 1004` text each have **one** SQLite row. `PRAGMA integrity_check = ok`. No outgoing WhatsApp message was sent.

Phone receipt, raw node, upsert, normalizer, WebSocket, Python and one SQLite row are therefore proven for this post-start ID in generation `baa22f51-9acb-42e7-814e-463efd4ef649`. The raw→upsert delay was about **7 minutes 24 seconds**; raw→SQLite about **7 minutes 24 seconds**. This corrects the earlier snapshot-based conclusion that the ID was permanently stuck. The cause of the delay is still unproven, and that latency is unsuitable for prompt automation. The bridge has since restarted into a new generation, so its *current-generation* live acceptance remains pending a fresh post-start test before a runtime `LIVE_INCOMING_TEXT = VERIFIED` designation is set.

A temporary ID-scoped metadata diagnostic was staged inside the pinned Baileys package and tested, but the candidate had already completed before the instrumented restart and did not replay into that diagnostic generation. The package files were restored byte-for-byte from ignored local backups; the helper was removed. Node tests passed 18/18 after restoration. The current read-only bridge is connected in generation `a941e625-59d7-47ea-84d1-b784273536fb`, with offline notification completion observed. A fresh `JARVIS LIVE FIX 1004` message has been requested to measure the current generation's delivery and latency. No fresh QR companion was created.

At 04:10 UTC (09:40 IST), process inspection found one bridge and one Python read-only listener. The bridge was `CONNECTED` in the same generation with `received_pending_notifications = true`; the SQLite inbox had zero rows for `JARVIS LIVE FIX 1004` and passed `PRAGMA integrity_check`. Phone receipt of this new marker has not been confirmed, so this zero count is not a failed delivery result. The current-generation acceptance test remains pending.

## 2026-10-04 current-generation fresh marker

The owner sent `JARVIS LIVE FIX 1004` from the second account and confirmed that it appeared on the primary phone at **09:50 IST** (phone display has minute resolution). The exact text has one incoming SQLite row, ID `ACFB752CBDDFEAA850856852570A0DF2`, in the same direct chat. Its original message timestamp is 04:20:16 UTC. All observations below belong to connected, read-only generation `a941e625-59d7-47ea-84d1-b784273536fb`, which opened at 04:02:51.710 UTC and had completed offline notifications.

| Boundary | UTC time | Result |
|---|---|---|
| Primary phone | 09:50 IST (04:20 UTC; minute precision) | Received, per owner |
| Baileys `CB:message` raw node | 04:20:16.473 | Same ID, direct chat, text node |
| Baileys `messages.upsert` | 04:22:44.580 | Same ID, `notify`, incoming conversation |
| Handler and normalizer | 04:22:44.581–04:22:44.582 | Accepted |
| WebSocket write | 04:22:44.582 | `WRITE_ACCEPTED`, one connected client |
| Python receive and schema | 04:22:44.584 | Received and accepted |
| SQLite | 04:22:44.594 | `INSERTED`; later same-ID write `DEDUPE_EXISTING` |

Raw node → upsert was **148.107 seconds**. Upsert → SQLite was **0.014 seconds**, and raw node → SQLite was **148.121 seconds**. The SQLite row count is one for the ID and one for the exact marker text; `PRAGMA integrity_check = ok`. The inbox recorded exact-ID phone-confirmed acceptance for this current generation and now reports `event_stream_verified = true`. Therefore **`LIVE_INCOMING_TEXT = VERIFIED` for eventual delivery**, while **prompt live delivery is DEGRADED**. This second long raw→upsert delay reproduces the latency problem; its internal Baileys cause is still unresolved. No JARVIS chat message was sent, no companion was relinked, and the bridge and Python listener remain read only.

## 2026-10-04 isolated fresh companion latency A/B

The owner linked a separate empty auth directory through the normal WhatsApp phone-number pairing flow. The old companion auth, backup, inbox and traces were preserved; the old bridge was stopped before the fresh read-only bridge started. After fresh-session registration, offline notification completion and an inactive event buffer, three owner-confirmed direct messages reached the same fresh bridge generation with exact-ID raw→upsert latencies of **10 ms, 3 ms and 4 ms**. All three continued through normalization, WebSocket, Python and exactly one SQLite row per ID. The [full A/B evidence and limitations](WHATSAPP_FRESH_LATENCY_AB.md) records the IDs, phone times, timestamps, process samples and comparison.

Fresh-session inbox diagnostics now show `connector_state=READY`, `event_stream_verified=true`, `history_sync_state=READY`, and `overall_state=READY`. **LIVE_INCOMING_TEXT = VERIFIED; PROMPT_INCOMING_DELIVERY = VERIFIED for the three-message fresh-session run.** This supports an operational `OLD_SESSION_DEGRADED` classification relative to the old 148–444-second results, although the old session's internal delay mechanism remains unknown. The current manually started bridge uses fresh isolated auth; ordinary startup still defaults to old auth until separately migrated. The fresh bridge and Python listener remain read only. No outgoing WhatsApp message was sent by JARVIS, and the old Ubuntu device was not unlinked.
Section one notes...
