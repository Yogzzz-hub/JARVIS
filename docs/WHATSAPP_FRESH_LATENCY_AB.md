# WhatsApp raw-to-upsert latency A/B — 2026-10-04

**Result: OLD_SESSION_DEGRADED (operational A/B classification).** The fresh companion delivered three phone-confirmed direct texts from Baileys raw node to `messages.upsert` in 3–10 ms. The old companion took 148.107 s and 444.111 s for two controlled texts. The old session's exact internal delay mechanism remains unproven. This A/B isolates the companion/auth state from the shared pinned Baileys version, Node runtime, bridge code, machine and downstream inbox; differences in accumulated backlog and sync state remain possible contributors.

## Isolation and readiness

- The old bridge was disconnected before its process was stopped. No other Baileys bridge remained. The old `integrations/data/whatsapp_auth`, its existing backup, SQLite inbox, message history and trace files were preserved.
- `integrations/data/whatsapp_auth_fresh_latency_test` was created empty; no old Signal keys, prekeys, app-state keys, LID mappings or device-list files were copied. The owner linked it through WhatsApp's normal phone-number pairing flow. The pairing code is omitted from this report.
- The fresh bridge used the same Node `v24.15.0`, pinned `@whiskeysockets/baileys@7.0.0-rc14`, `JARVIS_WHATSAPP_SESSION_RECOVERY=1`, and bounded offline-batch setting of 200 as the old recovery-enabled run. It remained `JARVIS_WHATSAPP_READ_ONLY=1`; Python also remained read only. No JARVIS chat message was sent.
- At test time, fresh generation `a2f5bb28-c971-42ae-b83f-ee440ee6b1ca` was `CONNECTED`, credentials registered, `receivedPendingNotifications=true`, offline completion count 1, and event buffer inactive. Exactly one Baileys bridge used the fresh auth directory.

## Exact-ID controlled results

The owner confirmed each marker appeared on the primary phone. Phone time has minute precision. The raw and upsert times below are from the **same Node process** and support millisecond latency comparison; all times are IST on 2026-10-04.

| Marker | Phone | Message ID | Raw node | `messages.upsert` | Raw → upsert | SQLite rows |
|---|---:|---|---:|---:|---:|---:|
| 01 | 10:07 | `AC3259D189BABB5E073B3C1BA98A4FA8` | 10:07:18.117 | 10:07:18.127 | **10 ms** | 1 |
| 02 | 10:08 | `AC7EBC16EDDF86F9B4410703D5FE9C11` | 10:08:50.450 | 10:08:50.453 | **3 ms** | 1 |
| 03 | 10:09 | `AC42C737922A5C060C6DAA22D46A9CC5` | 10:09:26.730 | 10:09:26.734 | **4 ms** | 1 |

All three were incoming direct-chat text messages in the fresh generation. For each ID, the normalizer accepted, the WebSocket recorded `WRITE_ACCEPTED` with one Python client, Python received and schema-accepted, and SQLite inserted one row. The later service pass recorded `DEDUPE_EXISTING` for the same ID; `PRAGMA integrity_check = ok`. Marker 01's phone/stored capitalization was `Jarvis fresh latency 01`; markers 02 and 03 matched the requested uppercase text. No aggregate backlog count was used as acceptance evidence.

Within Node, upsert → WebSocket write trace was 1, 2 and 2 ms. The Python receive and SQLite timestamps are recorded in the ignored local trace, but their clocks have roughly millisecond-to-tens-of-milliseconds resolution/offset relative to Node: for some probes a Python timestamp precedes the Node upsert timestamp. Consequently **phone → raw, WebSocket → Python and raw → SQLite millisecond intervals are not reliable from these wall clocks**. Python receive → SQLite was logged within approximately 0–16 ms, with the 0 ms value limited by clock resolution. This does not affect the same-process raw → upsert result or the exact-ID insert proof.

For the three fresh probes, raw → upsert **min 3 ms, median 4 ms, max 10 ms**. The nearest-rank p95 of this three-sample diagnostic is 10 ms, but three cases do not estimate population p95. The two old-session controls measured 148.107 s and 444.111 s. The fresh session met the <2 s target for all three; the old session did not.

An external read-only process sampler recorded Node CPU and memory. In four-second windows centered on the fresh probes, CPU time increased approximately 0.110 s, 0.015 s and 0.016 s; working set was approximately 162–331 MB, 164 MB and 164–165 MB. The first window included a transient working-set peak of unknown cause. These coarse samples do not measure event-loop delay, GC pauses or auth key-store operation latency, and are not evidence for an old-session bottleneck.

## Current state and recommendation

The fresh read-only bridge remains connected using the isolated fresh auth directory, and a single read-only Python listener is connected. After refreshing Python's status connection without changing code, inbox diagnostics report `connector_state=READY`, `event_stream_verified=true`, `history_sync_state=READY`, and `overall_state=READY` for the fresh generation. **LIVE_INCOMING_TEXT = VERIFIED** and **PROMPT_INCOMING_DELIVERY = VERIFIED for this three-message diagnostic run**. Auto-reply remains disabled by read-only mode; no outgoing or attachment acceptance was performed.

The A/B supports replacing the old runtime auth with this fresh linked companion for future starts, while retaining the old auth and backup as archives and keeping SQLite/history separate. Do not merge Signal files or unlink the old Ubuntu device during this diagnostic. **Update on 2026-10-04:** the ordinary startup defaults and bridge fallback now point to the fresh auth directory, and startup rejects a port occupied by the archived auth. A reboot acceptance test has not yet been performed. No Baileys package/runtime upgrade is justified by these results.
