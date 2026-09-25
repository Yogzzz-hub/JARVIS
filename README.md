# JARVIS EDGE v1.0

Your personal, local-first AI assistant for Windows: voice ("Hey Jarvis"), PC control, Android phone
control, WhatsApp, browser automation, a private knowledge base (RAG) and a local LLM (Ollama) that
thinks through anything the fast deterministic commands don't cover.

## Setup (one time)

```powershell
powershell -NoProfile -File .\setup_jarvis.ps1          # core + voice + Windows automation + models
powershell -NoProfile -File .\setup_jarvis.ps1 -Browser # also install the automated browser (Playwright)
```

Setup installs the voice extras (wake word, speech recognition, VAD, TTS, push-to-talk hotkey), downloads
the Whisper speech model and Piper voice (they are too large for git), and pulls the Ollama models named in
`jarvis/config/jarvis.toml`. Install [Ollama](https://ollama.com/download) first for the AI features.

Check everything at any time:

```powershell
powershell -NoProfile -File .\diagnose_jarvis.ps1
python scripts\setup_models.py --check
```

## Start

Double-click **`start.bat`** (starts Ollama, the WhatsApp bridge, the backend and the desktop UI), then say
**"Hey Jarvis"** or press **Ctrl+Shift+J** (push-to-talk). Typed commands work too:

```powershell
python -m jarvis.cli "open notepad"
python -m jarvis.cli "ask rahul if he is free tonight on whatsapp"
```

## What you can say

| Area | Examples |
| --- | --- |
| **PC** | `open chrome`, `volume 40`, `brightness 70`, `take a screenshot`, `snap window left`, `lock the pc` |
| **Files** | `find my resume`, `organize my downloads`, `find duplicate files in downloads`, `move my downloads folder to desktop` |
| **Phone** | `lock my phone`, `turn up the volume on my phone`, `open spotify on my phone`, `take a screenshot of my phone`, `call 98765 43210 on my phone`, `mirror my phone` |
| **WhatsApp** | `tell mom I'll be late`, `ask rahul if he is free tonight`, `remind dad to take his medicine on whatsapp`, `reply to rahul saying yes at 10`, `summarize my whatsapp` |
| **Knowledge (RAG)** | `learn my documents folder`, `what do my documents say about the refund policy`, `search my notes for the wifi password` |
| **Web** | `search amazon for headphones`, `go to wikipedia.org`, `use the browser to find the price of a Pixel 9 on Flipkart` |
| **Reminders** | `remind me to drink water in 20 minutes`, `remind me to call mom at 6 pm`, `show my reminders` |
| **Ask anything** | `what's the weather in Chennai today`, `explain recursion`, `tell me a joke` (answers use your documents, the conversation and live web results) |
| **Multi-step** | `find the latest invoice and send it to my phone`, anything else in plain words (the AI agent plans it) |

Anything that sends data outside the PC (messages, uploads), deletes or installs things, or was planned by
the AI is read back to you first. Say **"yes"** / **"no"** (or reply YES / NO on WhatsApp).

## How it fits together

```
voice / UI / CLI / WhatsApp
        │
        ▼
 SmartRouter ── deterministic fast paths (<1 ms) ── phone / messaging / knowledge / web / reminders
        │                                            PC, files, apps, windows ...
        ├─ LLM classifier (fast model, schema-constrained to real tools)
        ├─ Grounded chat  (RAG + conversation history + live web)       ─┐
        ├─ DAG planner    (planner model, validated TaskGraph)           ├─ one Ollama client
        └─ Tool agent     (step-by-step, confirmation on risky steps)   ─┘
        │
        ▼
 ExecutionEngine: policy · confirmation tickets · ledger · verification → talkback (TTS) / reply
```

See [docs/AI_INTEGRATION.md](docs/AI_INTEGRATION.md) for the architecture, model configuration and
troubleshooting (wake word, Ollama, WhatsApp, browser, phone).

## Configuration

* `jarvis/config/jarvis.toml` – features, Ollama model roles (`[models]`), voice (`[voice]`: wake threshold, mic, Whisper model)
* `config/whatsapp.toml` – owner numbers, contacts, AI reply mode, default country code
* `config/response.toml` – TTS voice, barge-in
* `config/connectors.toml` – Android (ADB/scrcpy), LocalSend, browser, notifications

Restart JARVIS after config changes.
