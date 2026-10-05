# WhatsApp test report

## 2026-10-04 update

The fresh companion passed three phone-confirmed exact-ID incoming text tests; see [the A/B report](WHATSAPP_FRESH_LATENCY_AB.md). A read-only bridge/Python restart then passed a fourth phone-confirmed marker at **16 ms** raw → upsert with one exact-ID SQLite row; see [live verification](WHATSAPP_LIVE_VERIFICATION.md). These are incoming acceptance, not live outgoing or media acceptance. The promoted startup auth passes the read-only runtime verifier. Node bridge tests passed **24/24** after scope/channel, startup, health refresh and one-use outgoing guard checks. Focused Python inbox, unread, scope and read-only acceptance tests passed **49/49**. The broader WhatsApp/router/policy Python selection passed **420 tests, 3 skipped** after replacing the coalescing test's fixed wait with a bounded completion wait. `git diff --check` passed. No WhatsApp chat message was sent during this update.

Direct-only, group-only and combined reads have local tests. Channel JIDs are rejected by the Node normalizer and omitted from inbox read scopes. These tests do not prove complete historical recall, externally delivered attachments, voice transcription or outgoing idempotency.

Date: 2026-10-03. After the gateway and read-only send changes, the full WhatsApp Python selection passed **357 tests, 3 skipped** and the Node bridge suite passed **15/15**. Focused reruns passed **200/200** and **29/29** for the modified reply and send-evidence paths. The later exact-ID/time live-health check passed its **2/2** focused tests and Python compilation. `git diff --check` passed. These are local tests, not live message acceptance.

Read-only SQLite checks on the existing inbox: integrity `ok`, 2,767 unique stored messages at audit time, 2,767 versioned events, and no duplicate message IDs. A real stored direct thread yielded ten recent typed context references. FTS5 held 13 `project` matches globally and returned one match in a scoped thread. The inbox summary reported ten people and `PARTIAL_SYNC`; content was not printed into test logs.

Forty warmed calls over a real stored thread measured context retrieval at **14.19 ms p50 / 17.42 ms p95**, scoped FTS at **0.69 / 0.88 ms**, and the available-data inbox summary at **14.63 / 17.18 ms**. These are local store operations; they exclude model generation, media processing, network and end-to-end command routing.

Live message, attachment, voice, reply, auto-reply, owner remote command and uncertain-send reconciliation must be accepted separately with external evidence. Model, media and end-to-end command latency are not available from this run.
