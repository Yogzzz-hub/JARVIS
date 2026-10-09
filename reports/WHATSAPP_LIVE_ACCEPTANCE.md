# WhatsApp live read-only acceptance

## 2026-10-02 autonomous repair and pending marker test

The detailed source/version findings are in `WHATSAPP_AUTONOMOUS_ROOT_CAUSE.md` and the event-boundary audit in `WHATSAPP_EVENT_PIPELINE.md`. Baileys 7.0.0-rc14 is pinned after copied-auth version comparisons demonstrated ongoing queue processing where 6.7.24 stalled. The application forced-flush workaround is removed. Read-only storage bypasses command processing, diagnostics cannot displace Python, and chat deltas include current generation metadata.

SQLite currently contains 416 inbound records, with zero duplicate message IDs and an OK integrity check. These additional records are real queued messages, not fabricated acceptance data. Live delivery remains unverified because old timestamps and decryption failures do not prove a new controlled message reaches the inbox. Transport is connected, history incomplete, and overall health is `DEGRADED_LIVE`.

The user confirmed `JARVIS CHECK 1002` arrived on the primary phone. It did not arrive in SQLite: 416 before and after the first window. One controlled reconnect also failed to deliver it; the count reached 417 from one other older record. Live direct evidence remains zero, pending-notification completion false, and decryption errors/negative ACKs persist. `EVENT_STREAM_FAILED` records this known test failure; it is never inferred from ordinary inactivity. Marker reads and summaries remain unpassed because no real marker record exists. A separate fresh-linked-device control now requires approval and pairing; it has not begun.

Latest regressions: 46 Python tests and six Node tests pass; the broader WhatsApp run passed 202 with three skips. These checks do not substitute for failed real acceptance.

## 2026-10-01 connected-without-events investigation (23:40 IST)

### Phone-confirmed and minimal-probe results

The user confirmed a new direct message reached the primary phone after WhatsApp Desktop was closed. Across the next 30 seconds, production stayed at 58 raw Baileys upserts, 57 bridge-listener messages, and 174 SQLite inbound records. Thus the post-flush session did not receive that known live message. Presence was unavailable and `isOnline=false`. WhatsApp Desktop's background process remained detectable, so the UI close cannot prove the process was gone.

Production was stopped and a fresh copy of its auth was used by a minimal read-only Baileys probe with no bridge wrapper, ChatIndex, Python, or send path. For the first phone-confirmed probe message, the listener registered at `18:15:17.180Z`, connection opened at `18:15:19.364Z`, and `receivedPendingNotifications` remained false. The buffer stayed active throughout the 120-second window: 41 raw message emissions, zero delivered `messages.upsert` listener calls. The last raw JID type was newsletter; the probe did not capture per-JID counts for this first run. The known direct message was not identifiable in the raw aggregate.

A second copied-auth connection also remained open with `receivedPendingNotifications=false` and an unreleased buffer. It emitted 45 raw messages after open (31 LID, 11 group, 3 newsletter), with zero delivered listener calls. **No second-sender phone confirmation was received during this probe**, so its outcome does not establish sender variation. A second probe connection is not a validated production reconnect test with a new phone-confirmed message.

The exact demonstrated failure is Baileys' initial event buffer failing to release because the `offline` completion notification never arrived. The phone-confirmed message also did not increase production's raw event count after the diagnostic flush, so companion live delivery may have an additional session-level fault. There is no evidence of a JARVIS JID filter dropping direct LID messages. A fresh-link control is **not yet authorized or justified** under the user's stated gates, because the second sender and a controlled reconnect with a new confirmed message remain unverified.

Python was restarted from this checkout in read-only mode. The previously missed unread-count phrasing now returns `PARTIAL_SUCCESS` with a sync warning; current Python source is loaded. Baileys still connects with the existing registered auth. The bridge now uses `markOnlineOnConnect=false` and requests unavailable presence after open. Windows shows a WhatsApp Desktop background process; another Baileys bridge process for this checkout was not observed. Browser WhatsApp Web tabs cannot be determined from process names alone.

The metadata-only tap registered at `18:09:50.703Z`, before `connection=open` at `18:09:54.317Z`. The installed Baileys 6.7.24 starts its event buffer before the connection event and releases it when an `offline` notification fires `receivedPendingNotifications=true`. Here that field remained **false**; no offline notification arrived. Raw Baileys `messages.upsert` emissions reached 58 while the bridge listener still saw zero. The buffer held messages and chat events indefinitely until the one-time diagnostic flush at `18:10:24.319Z`. After the flush, the bridge listener saw 57 consolidated message upserts, and Python SQLite inbound count rose from 154 to 174. Consolidation explains why raw event count and listener message count are not identical. No message bodies or full phone numbers were logged.

This establishes failure layer **C: Baileys initial event buffer awaiting pending-notification completion**, with a contributing bridge observation bug: diagnostic WebSocket clients previously replaced Python's sole active socket. `/diagnostics` is now read-only and does not replace it. The bridge did not configure `shouldIgnoreJid`; Baileys' default is `() => false`. Raw metadata included an `@lid` sender type and the bridge's direct/group classification treats LID as direct. A fresh post-flush message with phone confirmation is still required to prove live delivery. The minimal copied-auth probe and second sender are deferred until that controlled test result is known.

The current diagnostic flush is opt-in through `JARVIS_WHATSAPP_DIAGNOSTIC_FLUSH=1`, fires only once after 30 seconds of a connected stalled buffer, and uses Baileys' public `ev.flush()` API. Python remains read-only. The dashboard now exposes transport, event-stream and history readiness separately; the stream is unverified and overall status is `DEGRADED_LIVE` until a phone-confirmed fresh message is traced. Focused results: 34 Python tests and four Node bridge tests passed. No JARVIS WhatsApp message was sent and no auth was removed or relinked.

## 2026-10-01 live event attempt (23:30 IST)

The user confirmed that one harmless inbound message was sent from another account to the linked account. The production Baileys bridge remained `CONNECTED` on PID 30876 with the registered auth path `integrations/data/whatsapp_auth` and generation `655f5cce-42ca-4373-8c9f-c3b2d9fea460`. Python FastAPI PID 9332 was running with `JARVIS_WHATSAPP_READ_ONLY=1`; its WhatsApp transport reported `READY` while history remained `PARTIAL_SYNC`.

Four diagnostic polls over 30 seconds after confirmation showed `messages_upsert=0`, no last message/chat/history event, zero bridge chats, and a stable 154 previously stored inbound messages. The test message did **not** reach the observable Baileys event handler or Python inbox. Thus the current session has not passed live event acceptance, and `LIVE_ONLY` cannot be asserted. The 154 stored messages establish only older local data; they do not verify current history or unread counts.

Real `/command` calls for “who has messaged me on whatsapp” and “summarize my whatsapp” returned `PARTIAL_SUCCESS` and explicitly said history was not fully synced. A third phrasing, “how many unread personal messages can you currently see”, originally fell through to a generic model response; deterministic routing was patched and a focused regression test passes. The running Python process predates that routing patch, so its real command response is not yet rechecked.

No second-message, restart-persistence, phone-count comparison, or history search acceptance can be claimed until the first live event is captured. No JARVIS WhatsApp message was sent, and the linked auth was neither removed nor relinked. Focused regression after the read-only service and routing changes: 50 WhatsApp tests passed, then 34 unread-state tests passed.

Earlier observations below predate the production auth-path and TLS fixes and should not be treated as the current connector state.

Date: 2026-10-01. No messages were sent and no account data was changed.

## Final patch validation

The final test source contains one `PARTIAL_SYNC` assertion for the summary made without a complete snapshot. The summary tool's returned dictionary contains one `status` field. No duplicate status assertions or fields were found in the final files.

The current patch has a current-process sync generation, invalidates it on disconnect/restart, requires Baileys' `isLatest` history event before reporting a complete snapshot, and provides an event-driven bounded wait before a summary. The read-only `/dashboard/whatsapp/diagnostics` endpoint reports aggregate chat and message-store state, generation, event times and identified history gaps.

Natural read-only requests including “catch me up on WhatsApp,” “give me the WhatsApp rundown,” and “who has messaged me” now route to the existing summary capability. “Who did you send that to?” still routes to the action log.

## Live connector observation

The local port `127.0.0.1:8768` was listening in a Node bridge process (`integrations/whatsapp/bridge/src/index.js`). A read-only WebSocket connection received:

| Measure | Observed |
| --- | --- |
| Connector state | `CONNECTED` |
| User identity present | Yes |
| History synced | `false` |
| Chats in bridge snapshot | 0 |
| Direct chats in bridge snapshot | 0 |
| Group chats in bridge snapshot | 0 |
| Unread direct chats/messages in snapshot | 0 / 0, **unverified** |

The configured auth directory in this checkout (`data/whatsapp_auth`) was empty and the local `data/whatsapp_inbox.db` was zero bytes. The listening bridge process may have been launched from a different working directory or an older build. Its `CONNECTED` status alone cannot establish that its chat history is complete. The zero counts above describe only the empty snapshot; they are not accepted as the account's real counts. The running bridge did not expose the new generation diagnostics, so it is not evidence that the patch is running in that process.

## Read-only acceptance result

**Blocked by incomplete live history.** The required current-session complete snapshot was absent, so running `summarize my whatsapp` through CommandService would test only the truthful `PARTIAL_SYNC` fallback. It could not establish whether real unread personal chats were retrieved. Sender/date/thread/attachment/voice-note searches, reconnect and restart comparisons against the phone also cannot be validated from this empty snapshot.

No draft/send or auto-reply acceptance was run. The release gates for false zero, false READY, and real unread completeness remain unproven on the connected account. Recheck this report after the bridge has produced a current-session `isLatest` history event and the local store contains the actual chats.

Local regression results: 76 Python WhatsApp/follow-up tests, 100 routing/group/unread tests, and 4 Node bridge tests passed. These are synthetic tests and do not satisfy the live account gate.

## Connector limitations

The bridge requests recent history, forwards at most five unread history messages per chat, caps total forwarded history messages at 400, and has a two-week history age window. A badge count can therefore exceed the number of stored message bodies. The diagnostics endpoint exposes this mismatch as `unread_chats_missing_message_bodies`; the summary can report a badge and last-message preview, but cannot manufacture missing bodies or a full historical search result.
