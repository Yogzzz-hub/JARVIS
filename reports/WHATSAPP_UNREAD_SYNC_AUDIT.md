# WhatsApp unread sync audit

## Scope and evidence

The reported command is `summarize my whatsapp`, which routes to `summarize_whatsapp_messages` and reads `WhatsAppInbox.summarize_inbox()`. The local `data/whatsapp_inbox.db` in this checkout is zero bytes and `data/whatsapp_auth` contains no account state. No live connector, message store, or phone state was available for inspection. Therefore the exact state of the user's account at the time of the reported failure cannot be reconstructed from this checkout.

## Trace of the failure path

| Stage | Existing behavior and failure mode |
| --- | --- |
| Connector | The Python transport receives bridge status and `chat_state` events. Previously the inbox did not persist connection state, so a read could trust old sync metadata after disconnect. |
| Bridge chat store | `ChatIndex` persisted `synced=true` and unread badges in `chat_index.json`. On restart it loaded that flag as if the current connection had completed a history sync. |
| History | `BaileysClient.start()` requested history only while `ChatIndex.synced` was false. A cached true value therefore suppressed the fresh history request. After three failed attempts, it also stopped requesting history on later starts. |
| Chat enumeration | `snapshot()` returned cached chats as `full: true`; the Python inbox stored their badges and its own `chats_synced=1` flag. A stale zero badge could be treated as definitive. |
| Inbound store | `whatsapp_messages` persists received messages, but messages missed before the bridge had a complete history are absent. A cached zero badge could hide a newer locally stored unread message. |
| Scope | The summary selects direct chats by default. Group chats are counted separately. This filter is not the cause of zero direct unread results when direct chats are missing or stale. |
| Summary input | `unread_chats()` preferred badges when `chats_synced=1`, then passed an empty list to `summarize_inbox()`. |
| Final outcome | `summarize_inbox()` produced `No unread messages in your personal chats.` and the tool returned `SUCCESS`, even though the bridge's unread state might have been incomplete or cached. |

This establishes a concrete code path for a false zero. The unavailable live store prevents proving which of the cached badge, absent history, or connection timing conditions occurred in the user's run.

## Repair

The bridge now loads saved badges as provisional and retries history synchronization for each process session. A disconnect invalidates full-sync confidence. Python persists the bridge's connector state, clears full-sync confidence on disconnect or partial snapshots, and merges newer locally stored unread messages over a stale zero badge while sync is incomplete. Summary and unread-count results return `PARTIAL_SYNC` when no complete current snapshot exists; they no longer assert zero unread. A verified `READY` snapshot retains the existing per-chat summary behavior.

## Verification and remaining acceptance

Focused tests cover multiple direct chats with group filtering, bridge badge persistence, stale zero badges, restart/disconnect invalidation, partial-sync zero reporting, duplicate/history behavior, and routing. These run without a WhatsApp account. Real acceptance still requires linking the user's authorized account and checking phone unread badges against the dashboard and `summarize my whatsapp` after sync and reconnect. The 220-capability expansion, dashboard additions, and 500-scenario holdout in the attached master prompt remain separate work and are not claimed complete here.
