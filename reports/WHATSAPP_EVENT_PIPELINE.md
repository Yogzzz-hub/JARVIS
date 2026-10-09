# WhatsApp event pipeline

## Boundaries inspected

| Boundary | Input / output | State, buffering and failure condition |
| --- | --- | --- |
| WebSocket / Baileys | Encrypted nodes → decoded message nodes | TLS uses system CA. OPEN proves transport only. Offline preview starts delivery of queued nodes. |
| Receive handler | PN/LID/group nodes → message objects, receipts | 6.7.24 uses a serial offline queue. Direct LIDs are accepted. A stuck receive task prevents subsequent offline nodes from processing. |
| Event buffer | `ev.emit` → consolidated `ev.process` map and named listeners | 6.7.24 starts buffering before OPEN; missing offline completion leaves it held. rc14 has revised queue processing, acknowledgements and bounded event buffering. Internal closure-triggered flushes do not necessarily call a wrapped public `ev.flush`; `ev.isBuffering()` is the authoritative exposed state. |
| Bridge message handler | Named upserts → normalized records | Accepts notify/append; old append records are history. Unsupported message types are omitted; decryption placeholders remain placeholders. PN and LID are direct; groups, broadcast and newsletters are scoped separately. |
| ChatIndex | Chat events and normalized messages → snapshots/deltas | Deltas now include generation, counts and event timestamps. A full history-completion event is required for complete history. |
| Bridge WebSocket | Normalized records → Python | `/diagnostics` cannot replace the backend. A second backend connection is rejected. Pending messages are bounded to 500. |
| Python transport | JSON → validated message model | Creates handler tasks; transport and history readiness are separate. Status refresh uses the existing backend connection. |
| Read-only service | Validated messages → history storage path | Prevents incoming owner commands, announcements and replies. Transport and bridge both block chat sends in acceptance mode. |
| Inbox / SQLite | Message ID → durable record | Actual default store: `jarvis/data/whatsapp_inbox.db`. The root `data/whatsapp_inbox.db` is unused. IDs provide deduplication; partial badge state falls back to stored inbound messages. |
| Tools / CommandService | Inbox queries → partial/complete response | Unknown counts must remain unknown. Partial history can show stored messages. Live acceptance requires matching a real new message through this boundary. |

## Evidence limits

Raw upsert event counts, consolidated listener message counts and SQLite rows count different things. Replayed IDs, owner messages, unsupported protocol records and decryption placeholders explain some differences; none alone proves the requested live message arrived.

No copied-auth probe includes JARVIS, the bridge WebSocket or ChatIndex. Probes suppress libsignal console output because that dependency can print session objects. Only aggregate counters and timestamps are retained in current probe output.
