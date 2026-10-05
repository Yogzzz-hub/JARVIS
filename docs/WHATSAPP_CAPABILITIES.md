# WhatsApp capabilities

As of 2026-10-04, the original read and summary tools accept typed `DIRECT_ONLY`, `GROUP_ONLY` and `DIRECT_AND_GROUP` scopes. The SQLite query applies scope before its result limit, so heavy direct traffic cannot hide older group results. Named groups must resolve to one actual `@g.us` thread. Broadcast, status and newsletter JIDs are outside all three scopes. Natural requests such as “read individual messages”, “read group messages” and “read both personal and group messages” are routed to the WhatsApp read capability with the corresponding scope. Scope remains separate from contact and group names.

The fresh companion is the configured startup transport. All outgoing capability descriptions remain subject to the runtime read-only gate and normal policy; registration or capability metadata alone does not authorize a send. Local historical messages are available for search and summary, while complete historical coverage is still unproven.

`jarvis/tools/system/whatsapp_intelligence.py` defines 41 metadata-backed operations in the existing registry, including status/sync, contact and thread resolution, message search/read/summary, typed references, drafts, media, voice, style, watchers and auto-reply policy. Existing `whatsapp_tools.py` provides original send/read/summary tools. The language model proposes a SemanticFrame and capability; policy and typed resolution remain separate from execution.

`ContactRef`, `ThreadRef`, `MessageRef`, `AttachmentRef`, `DraftResource` and `ConversationContext` are defined in the intelligence models. Search is scoped by thread and can use FTS or configured embedding retrieval. A local FTS search returned one real hit, but history incompleteness limits recall. Context resolution returned ten recent references for a real direct thread; this does not prove all natural cross-turn requests.

Sending requires an exact recipient, current draft revision, matching thread version, grounded content and the existing external-effect policy. A started draft is never blindly retried after uncertainty. Current read-only mode makes sending unavailable even to the old one-send test recipient.

Live availability varies: STT, vision, browser and transport-backed operations require their respective provider or current connection. Capability metadata describes potential operations; it does not certify live execution.
