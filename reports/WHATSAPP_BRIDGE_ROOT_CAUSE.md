# WhatsApp bridge live root-cause trace

> Historical snapshot. The code-500 cause was subsequently traced to Node's TLS trust store and fixed with `--use-system-ca`. See [WHATSAPP_CODE500_DIAGNOSTIC.md](WHATSAPP_CODE500_DIAGNOSTIC.md) for current status.

Date: 2026-10-01. Read-only inspection; no WhatsApp messages were sent, no credential contents were printed, and no account relink was attempted. The inspection read only the boolean `registered` value from the credentials JSON.

## Running bridge identity

| Field | Observed |
| --- | --- |
| PID | 2624 |
| Process start | 2026-10-01T17:36:07Z |
| Node executable | `C:\Program Files\nodejs\node.exe` |
| Working directory | `C:\Users\ashok\OneDrive\Desktop\New folder (2)` |
| Script/source | `integrations\whatsapp\bridge\src\index.js` / `baileys_client.js` / `chat_index.js` |
| Package root | `integrations\whatsapp\bridge` |
| Package metadata | `integrations\whatsapp\bridge\package.json` |
| Bridge version / commit | `1.0.0` / `c9aab945830dac311170695f80dda6db81029333` |
| Baileys version | `6.7.24` |
| Auth directory | `integrations\data\whatsapp_auth` (exists; 1,299 entries; loaded `registered=true`) |
| Chat index | `integrations\data\whatsapp_auth\chat_index.json` |
| Bridge retry message cache | `integrations\data\whatsapp_auth\message_cache.json` |
| Python inbox SQLite | `data\whatsapp_inbox.db` (zero bytes in this checkout) |
| Python transport endpoint | `ws://127.0.0.1:8768` |

The original `config/whatsapp.toml` pointed at `data/whatsapp_auth`, but `baileys_client.js` resolved its relative default from `bridge/src`, which placed the actual registered session in `integrations/data/whatsapp_auth`. The config now names the existing session's path. Auth files were not moved or deleted.

The original bridge PID 13316 was started at 2026-10-01 21:03 local time, before the patched source was loaded. Only that confirmed JARVIS Node process was stopped. The new bridge's runtime identity proves it uses this checkout and exposes the patched generation diagnostics.

## Installed Baileys and history configuration

Baileys 6.7.24 exposes `messaging-history.set`, `chats.upsert`, `chats.update`, and `messages.upsert`; its event type does not expose `messaging-history.status`. It has `isLatest` and `progress` on `messaging-history.set`. The bridge uses `syncFullHistory=false`, Baileys' default Ubuntu/Chrome browser identity, `fireInitQueries=true`, and `markOnlineOnConnect=true`. The explicit history filter accepts bootstrap (0), recent (3), push-name (4), and on-demand (6), and excludes full history (2). No full-history request was enabled.

## Live pipeline counts

| Stage | Chat count | Message count | Evidence |
| --- | ---: | ---: | --- |
| Baileys history events | 0 events | 0 | Transport closes before a history notification or `messaging-history.set`. |
| ChatIndex, current generation | 0 | 0 | Runtime snapshot reports zero chats and zero `messages.upsert`. |
| Bridge WebSocket payload | 0 | 0 | Read-only `chat_state` snapshot reports zero chats. |
| Python WhatsAppService | Not running | Not running | No JARVIS Python/uvicorn process was present. |
| Python SQLite inbox | 0 verified | 0 verified | `data/whatsapp_inbox.db` is zero bytes. |
| Summary tool / CommandService / UI | Not reached | Not reached | Cannot run a real-message acceptance without current history and a Python service. |

The bridge cached `chat_index.json` already had zero chats, `synced=false`, and three old history attempts. On patched restart, the bridge resets in-memory attempts and creates a new sync generation. The current generation changes on reconnect; no READY evidence has been observed.

## Exact live blocker

The patched process loads the existing auth files with `registered=true`, then Baileys disconnects with numeric code **500 (`badSession` in the installed Baileys 6.7.24 enum)**. Baileys also uses 500 as a fallback for some unspecified stream errors, so this code alone does not prove the credentials are corrupt. Runtime state is `DISCONNECTED`, history events received = 0, history filter invocation = none, current-generation chats = 0. This blocks the pipeline before chat indexing, Python storage, or summarization. A status of `CONNECTED` from the old process did not prove history; after the controlled restart, even the transport connection does not remain open.

No relink was performed. Code 401 now preserves auth files and reports authentication required rather than deleting the directory. Code 500 remains a connection failure. The registered auth files and cached chat state remain on disk; the empty Python inbox contains no messages to lose. The owner must inspect the phone's linked-device status and decide whether to repair or relink this session if the existing credentials cannot establish a connection. If relinking is chosen, back up the existing auth directory first; a new link may restore future/recent history but should not be assumed to recover every old message body.

## Acceptance status

`LIVE_BRIDGE_IS_PATCHED=true`; `AUTH_PATH_IDENTIFIED=true`; `CURRENT_SYNC_GENERATION_VISIBLE=true`; `NO_MESSAGES_SENT_DURING_ACCEPTANCE=true`. Real direct-chat count, real message visibility, `summarize my whatsapp`, restart recovery, reconnect recovery, and false-zero release gates remain **unverified**. The live sync state is `DISCONNECTED` after `badSession` 500.
