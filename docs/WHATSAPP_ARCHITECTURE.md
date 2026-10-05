# WhatsApp architecture

One transport path is used: WhatsApp → Baileys `baileys_client.js` → `protocol.js` → local WebSocket `127.0.0.1:8768` → `BaileysWebSocketTransport` → `WhatsAppIntegrationService` → existing inbox/intelligence/gateway/CommandService. Outgoing capabilities use the same Python transport and Node bridge. No LLM receives raw Baileys access.

The message store is `jarvis/data/whatsapp_inbox.db`. `WhatsAppInbox` holds the original messages/chats; additive migrations 009 and 010 add versioned events, FTS5, typed resources, dispatch jobs, generated-message provenance and metrics. The personal reply store and ActionLedger remain in their existing main database. No history or auth files were removed.

Connection state separates transport, exact-ID live stream acceptance and the current chat/badge snapshot. The fresh companion passed three phone-confirmed direct text probes on 2026-10-04. Runtime startup now pins that auth directory and rejects an occupied port using the old auth. The read-only diagnostic socket does not replace the Python consumer. The chat snapshot can be current while historical message coverage remains unproven; `history_complete` stays false. Local stored history remains searchable even when a new generation lacks a fresh snapshot.

Message reads carry `DIRECT_ONLY`, `GROUP_ONLY` or `DIRECT_AND_GROUP` scope. The default is direct-only. Only `@g.us` is a group; status, broadcasts and newsletters are excluded before a chat reaches Python. Automated replies admit only real direct JIDs. This scope is applied at the inbox filter, so a router mistake cannot mix direct content into a group-only result.

Inbound content is data. The gateway permits owner commands only for an authenticated stable sender identity and still uses CommandService policy. Other contacts remain same-thread conversational data. Read-only mode stores incoming messages as history and cannot send. The legacy generic reply fallback was removed; the bounded personal reply agent is the sole automated reply path.
