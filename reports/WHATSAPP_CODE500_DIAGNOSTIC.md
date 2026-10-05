# WhatsApp code-500 diagnostic

Date: 2026-10-01. No WhatsApp messages were sent, no account unlink/relink was performed, and production authentication files were not deleted. Sequential probes used separate copies of the backed-up auth directory.

## Version comparison

Installed `@whiskeysockets/baileys`: **6.7.24**. The socket passed no explicit version, so Baileys used its bundled `[2, 3000, 1043857760]`. Baileys' default browser is Ubuntu/Chrome `22.04.4`.

| Source | Version | `isLatest` | Result |
| --- | --- | --- | --- |
| Bundled/default | `2.3000.1043857760` | n/a | Opened with system CA. |
| `fetchLatestBaileysVersion()` | `2.3000.1043857760` | true | Same as bundled; this reports Baileys' version source. |
| `fetchLatestWaWebVersion()` | `2.3000.1048995966` | true | Opened with system CA. |

Both fetch functions initially returned certificate-verification errors under default Node trust. With `node --use-system-ca`, both fetched successfully. Their `isLatest=true` values refer to different version sources and do not mean the numbers agree. The version difference did not cause the connection failure: both versions opened with the system CA store.

## Minimal probe matrix

The minimal probe contains no JARVIS WebSocket, ChatIndex, Python service, auto-reply, or `sendMessage`. It used auth copies from `integrations/data/whatsapp_auth_backup_20261001-231423`. The normal bridge was stopped before each probe.

| Probe | OPEN | Code | History | Chats | Time to open/close |
| --- | --- | --- | ---: | ---: | --- |
| Default config, default Node CA | No | 500 | 0 | 0 | Closed in 343 ms. |
| Default version, **system CA** | Yes | none | 0 | 0 | Open in 2,300 ms. |
| Latest WA Web version, system CA | Yes | none | 0 | 0 | Open in 2,386 ms. |
| Baileys version fetch | Equivalent to bundled/default | — | — | — | Returned the same version, so a separate identical probe adds no evidence. |
| Cacheable key store, bundled version, system CA | Yes | none | 0 | 0 | Open in 2,786 ms. |

The system-CA minimal probes recorded two `creds.update` events each; both writes succeeded to their **copied** auth stores. Some old message decryptions emitted `Bad MAC` warnings after connection opened. These warnings did not close the socket; they may limit recovery of specific old bodies and were not treated as proof that the whole auth store is corrupt.

The temporary copied probe directories remain under `integrations/data/wa_probe_*`. Automatic approval review rejected the recursive cleanup command as blocked by policy. They contain copies of auth material; the original session and timestamped recovery backup remain intact.

## Auth structure and backup

Timestamped recovery copy: `integrations/data/whatsapp_auth_backup_20261001-231423`; 1,299 original files, 714,187 bytes. `.sha256-manifest` records a hash for each original file. No credential values or filenames from the key store were printed in the user-facing result.

`creds.json` parses and has `registered`, `me`, `noiseKey`, `signedIdentityKey`, `signedPreKey`, and `registrationId`. All 1,299 auth JSON files parsed; invalid JSON files = **0**, zero-byte files = **0**. Key-store category counts: pre-key 813, session 221, sender-key 256, app-state-sync-key 3, app-state-sync-version 3, sender-key-memory 0. The auth and key-store structure is present. The standard `auth: state` and `makeCacheableSignalKeyStore` variants both opened with system CA.

Only one owned JARVIS bridge used the auth and port 8768 during normal operation. Other Node processes were unrelated applications and were left alone.

## Socket config and exact code-500 cause

Baileys 6.7.24 effective defaults: Ubuntu/Chrome browser; version `2.3000.1043857760`; `fireInitQueries=true`; `markOnlineOnConnect=true`; `connectTimeoutMs=20000`; `keepAliveIntervalMs=30000`; WebSocket URL `wss://web.whatsapp.com/ws/chat`. JARVIS sets `syncFullHistory=false`, accepts bootstrap/recent/push-name/on-demand history types, provides `getMessage`, and uses Baileys' default retry cache (no custom `msgRetryCounterCache`).

Without the system CA store, the minimal socket reported: **`WebSocket Error (unable to verify the first certificate; if the root CA is installed locally, try running Node.js with --use-system-ca)`**. Baileys wrapped this TLS failure in a Boom 500 response (`Internal Server Error`). This is the identifiable source of code 500; it was not a demonstrated WhatsApp session rejection. `start.bat` and the bridge's `npm start` script now launch Node with `--use-system-ca`.

## Production bridge after the fix

The normal bridge was started as `node --use-system-ca integrations/whatsapp/bridge/src/index.js`, PID **30876**, using the original registered auth directory. It reached `CONNECTED` and remained connected through the observation window. The current sync generation was visible. Disconnect code was null.

History events = **0**; `chats.upsert` = **0**; `chats.update` = **0**; `messages.upsert` = **0**; current-session chats = **0**; `synced=false`. Baileys did not invoke the history filter during the observation window, indicating no history notification arrived. This is a separate blocker for unread acceptance. The old cache already had zero chats and three history attempts; reopening an already-linked session did not backfill it during this test. The Python JARVIS service was not running, and no real `summarize my whatsapp` result was possible.

## Relink decision and next safe action

Relinking is **not required to fix code 500**. The existing session opens with the system CA store. It may be required to obtain an initial history snapshot, but this is unproven; Baileys 6.7.24 did not send one on this reconnect. Keep the auth backup and production session intact. The next safe action is to check the phone's linked-device state and observe whether a current-session history or live chat event arrives. If a fresh link is considered to recover history, use a separate auth folder and obtain the owner's explicit approval before pairing. Until then, JARVIS must remain `PARTIAL_SYNC` and cannot claim zero unread messages.
