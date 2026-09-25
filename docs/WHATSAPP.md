# WhatsApp Omnichannel Integration in JARVIS EDGE v1.0

## 1. Overview
The WhatsApp integration brings WhatsApp as a first-class I/O channel into the **existing** JARVIS EDGE architecture alongside Desktop UI, Android, voice, and text. 

> [!IMPORTANT]
> **Transport-Only Baileys Bridge**:
> Baileys is an unofficial WhatsApp Web multi-device library and is treated as **replaceable transport infrastructure**.
> Node.js does **NOT** run any AI models, does **NOT** call Ollama, does **NOT** manage AI memory, and does **NOT** make autonomous system decisions. All intelligence lives strictly inside the Python Jarvis backend.

---

## 2. Target Architecture Flow

```
WhatsApp Mobile / Web Client
           │
           ▼
Baileys Transport Bridge (Node.js)
  - Raw event ingestion
  - Media stream buffering (temp directory)
  - Normalization to typed Jarvis envelope
           │  (Local WebSocket ws://127.0.0.1:8768)
           ▼
WhatsAppChannelGateway (Python)
  - Idempotency deduplication (message_id sliding cache)
  - Trust Boundary: Untrusted external data boundary tagging
  - Owner identification and pairing verification
  - Media pipeline dispatch (Faster-Whisper STT, Qwen3-VL VLM, KnowledgeEngine chunking)
           │
           ▼
CommandService
  - Dispatches to SmartRouter (Lane 0 deterministic / Lane 1 LLM / Lane 2 Planner)
  - ToolRegistry & ExecutionEngine
  - Verifier & Phase 5 PolicyEngine
  - PULSE Feedback Lane & ActionLedger
           │
           ▼
WhatsAppChannelGateway
           │
           ▼
Baileys Transport Bridge -> WhatsApp
```

---

## 3. Normalized Message Schema
At the transport boundary, raw Baileys objects are converted into typed Jarvis objects:
```json
{
  "channel": "whatsapp",
  "message_id": "3EB0...128",
  "chat_id": "1234567890@s.whatsapp.net",
  "sender_id": "1234567890@s.whatsapp.net",
  "sender_display_name": "Alex",
  "timestamp": "2026-09-21T12:00:00Z",
  "type": "text",
  "text": "What time is it?",
  "media_ref": null,
  "reply_to": null
}
```

Supported Message Types:
- `TEXT`
- `IMAGE`
- `DOCUMENT`
- `AUDIO`
- `VOICE_NOTE`

---

## 4. Reconnection & Lifecycle Management
The Node.js Baileys adapter implements bounded exponential backoff (1.5s to 30s) across six defined states:
- `DISCONNECTED`
- `PAIRING_REQUIRED`
- `CONNECTING`
- `CONNECTED`
- `DEGRADED`
- `LOGGED_OUT`

---

## 5. Diagnostics & Doctor
Run the WhatsApp diagnostic doctor at any time:
```powershell
python -m jarvis.integrations.whatsapp.doctor
```
Checks:
- Baileys bridge installation and node_modules
- Local bridge connection
- Pairing state and credentials (secrets redacted)
- Owner identity configuration
- CommandService omnichannel readiness
- Existing Ollama models
- KnowledgeService and scoped FTS5
- Faster-Whisper STT & Piper TTS
- Qwen3-VL Multimodal Vision Provider
- Phase 5 Policy & ActionLedger
