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

The desktop UI centres on a real-time 3D reactor that reacts to your voice and to what JARVIS is doing, with the
conversation streaming in beside it. In the UI: **Ctrl+Space** talk, **Ctrl+K** type, **Esc** stop talking, or click
the reactor. Answers start being spoken after the first sentence instead of after the whole reply.

## What you can say

| Area | Examples |
| --- | --- |
| **PC** | `open chrome`, `volume 40`, `brightness 70`, `take a screenshot`, `snap window left`, `lock the pc` |
| **Files** | `find my resume`, `organize my downloads`, `find duplicate files in downloads`, `move my downloads folder to desktop` |
| **Phone** | `lock my phone`, `turn up the volume on my phone`, `open spotify on my phone`, `take a screenshot of my phone`, `call 98765 43210 on my phone`, `mirror my phone`, `read my phone notifications`, `tap Allow on my phone`, `turn off bluetooth on my phone` |
| **WhatsApp** | `tell mom I'll be late`, `ask rahul if he is free tonight`, `remind dad to take his medicine on whatsapp`, `reply to rahul saying yes at 10`, `summarize my whatsapp`, `tell everyone who messaged me that I'm in a meeting, free in an hour` (personal chats only - groups are skipped), `what did rahul say about the trip` |
| **Software** | `install vlc`, `install android studio for me`, `uninstall zoom`, `update all my apps` |
| **Screen** | `what is this error on my screen`, `look at my phone screen and tell me what it says` (local vision model) |
| **Any app** | `click the Save button`, `right click the desktop`, `use my computer to turn on dark mode in Settings`, `in Excel make the first row bold` |
| **Phone ⇄ PC files** | `get the latest photo from my phone`, `copy my last 3 screenshots from my phone`, `copy resume.pdf from my phone`, `copy report.pdf to my phone` |
| **Browser tasks** | `use the browser to book...` fills forms (dropdowns, checkboxes); at a login page it pauses - sign in once in the JARVIS browser, then say `continue` |
| **Knowledge (RAG)** | `learn my documents folder`, `what do my documents say about the refund policy`, `search my notes for the wifi password` |
| **Web** | `search amazon for headphones`, `go to wikipedia.org`, `use the browser to find the price of a Pixel 9 on Flipkart` |
| **Reminders** | `remind me to drink water in 20 minutes`, `remind me to call mom at 6 pm`, `show my reminders` |
| **Ask anything** | `what's the weather in Chennai today`, `explain recursion`, `tell me a joke` (answers use your documents, the conversation and live web results) |
| **Multi-step** | `find the latest invoice and send it to my phone`, anything else in plain words (the AI agent plans it) |

Anything that sends data outside the PC (messages, uploads), deletes or installs things, or was planned by
the AI is read back to you first. Say **"yes"** / **"no"** (or reply YES / NO on WhatsApp).

**Control the laptop from your phone:** message your own WhatsApp number (the owner number in
`config/whatsapp.toml`) with any command - "take a screenshot and send it to me", "what's on my screen", "install vlc" -
and JARVIS runs it on the PC and replies there.

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

**Decision engine (JDE).** A local, offline decision layer (about 1 ms on CPU) answers typed routing questions:
route family, whether the request is an action, whether it needs an LLM, the planner, the web or context, whether it
has an external or destructive effect, and whether it is ambiguous. Answers are calibrated and gated by risk class.
It currently runs in **shadow mode**: the router above still decides, and JDE logs its own decision to
`data/jde/shadow.jsonl`. JDE never executes or authorizes anything. See [docs/JDE_ARCHITECTURE.md](docs/JDE_ARCHITECTURE.md)
and [reports/JDE_BENCHMARK.md](reports/JDE_BENCHMARK.md).

## Configuration

* `jarvis/config/jarvis.toml` – features, Ollama model roles (`[models]`), voice (`[voice]`: wake threshold, mic, Whisper model,
  `endpoint_silence_ms` = how long a pause ends your turn, `wake_ack` = `chime` / `voice` / `none`),
  decision engine stage (`[decision] stage` = `off` / `shadow` / `read_only`)
* `config/whatsapp.toml` – owner numbers, contacts, AI reply mode, default country code
* `config/response.toml` – TTS voice, barge-in
* `config/connectors.toml` – Android (ADB/scrcpy), LocalSend, browser, notifications

Restart JARVIS after config changes.
