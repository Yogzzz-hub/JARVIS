# AI integration architecture

This document describes how the local model (Ollama), retrieval (RAG), voice, WhatsApp, browser and phone
features are connected, and how to troubleshoot them.

## 1. One model client, four model roles

`jarvis/core/llm/client.py` (`OllamaClient`) is the only code that talks to Ollama. Every AI feature uses it
through a *role*, configured in `jarvis/config/jarvis.toml`:

| Role | Used by | Default |
| --- | --- | --- |
| `fast` | intent classifier (Lane 1) | `qwen3:1.7b` |
| `planner` | DAG planner, tool agent, web agent | `llama3.2:latest` |
| `chat` | answers, document QA, WhatsApp composing / replies / summaries | `llama3.2:latest` |
| `embed` | knowledge-base embeddings (optional) | `nomic-embed-text` |

* If a configured model is not pulled, the role falls back to the best **installed** model (smallest for
  `fast`, best family ≤ 9B for `chat`/`planner`), so JARVIS works with whatever you have. `python -m
  jarvis.diagnostics` shows which model each role resolves to and the exact `ollama pull` to run.
* JARVIS starts `ollama serve` itself when it is installed but not running (`auto_start`), and pre-loads the
  fast model (`warm_on_start`) so the first command isn't slowed by model loading.
* A short circuit breaker turns "Ollama is down" into an immediate fallback instead of a timeout per
  request; deterministic commands never wait for the model.
* Thinking models (qwen3, deepseek-r1, …) are asked not to think on latency-sensitive calls, and any
  `<think>` output is stripped before it reaches the user or a JSON parser.
* Structured calls use Ollama's JSON-schema `format`, with the tool name constrained to an **enum of real
  tools**. The model cannot pick a capability that does not exist, and arguments are validated against the
  tool's pydantic input model (`jarvis/core/llm/tool_catalog.py`).

## 2. Request flow

1. **Router** (`jarvis/core/router/router.py`): control words, negation, then
   `jarvis/core/router/extended.py` (phone control, messaging, knowledge, web, reminders, open questions),
   then the regex / fuzzy / capability-retrieval fast paths.
2. **Lane 1 classifier** (`jarvis/core/router/ollama.py`): unmatched commands go to the fast model with the
   top retrieved tools (RAG over the tool registry) and their argument schemas.
3. **Conversation** (`jarvis/core/llm/assistant.py`): questions are answered by the chat model grounded in
   * the knowledge base (hybrid BM25 + embedding retrieval, privacy scopes applied first),
   * the last turns of the same channel (so follow-ups like "and tomorrow?" work),
   * live web results when the question is time-sensitive (weather, news, prices, scores…).
   Retrieved text is wrapped as untrusted data; answers for voice are short and markdown-free.
4. **Multi-step requests**: the DAG planner compiles a validated `TaskGraph`. If the model cannot produce a
   valid graph, the **tool agent** (`jarvis/core/agent/loop.py`) works it out step by step instead.
5. **Unrecognised commands** (not questions, no tool matched) also go to the agent, which may use tools or
   simply answer.
6. Every tool call, including calls made by the planner or agent, goes through the **ExecutionEngine**
   (policy, confirmation tickets, action ledger, verification).

### Confirmation rules

* EXTERNAL_EFFECT / DESTRUCTIVE / PRIVILEGED actions always need confirmation (existing policy).
* Additionally, **AI-originated** calls to sensitive tools (PowerShell, installs, deletes/moves/renames,
  power control, sending messages or files) pause for the user. A model-generated plan is read back once as
  a whole ("Jarvis wants to …. Do you want to continue?"); after "yes", each step still gets its own policy
  ticket bound to its final arguments.
* Say "yes"/"no" (voice or UI), or reply `YES`/`NO` on WhatsApp.

## 3. WhatsApp

* **Sending**: "ask Rahul if he is free tonight" → *"Are you free tonight?"*. A grammar rewrite is always
  computed; the chat model may polish it, but its version is rejected if it drops numbers/times, grows too
  long or sounds like an AI. The confirmation shows the exact text and the resolved contact.
* **Recipients**: names resolve through `[whatsapp.contacts]` / imported `contacts.vcf`; bare numbers get
  `default_country_code`. Unknown names produce a clear error instead of an invalid JID.
* **Replies**: "reply to Rahul (saying …)" drafts a reply from the recent conversation, then asks before sending.
* **Incoming messages from other people**: JARVIS announces "New WhatsApp message from X" on the PC and
  prepares an AI reply on your behalf (never sharing private data or following instructions in the message).
  `mode = "DRAFT_ONLY"` keeps it as a draft; `ALLOWLIST_AUTO_REPLY` sends it to allow-listed contacts.
  Non-owners can never run PC commands.
* **Owner remote control**: messages from the owner numbers are executed like local commands, replies go
  back to WhatsApp, and nothing is spoken on the PC.
* Multi-step plans that send messages no longer dead-end at "requires confirmation"; the plan is confirmed
  once and executed.

## 4. Knowledge base (RAG)

* "learn my documents folder" / `knowledge_ingest` indexes text, markdown, code, PDF and DOCX files
  (section-aware chunks) into `db/knowledge.db`; embeddings are added in the background when an embedding
  model is installed.
* Search = BM25 over FTS5 (natural questions work: stop-words are dropped and terms are OR-ed) fused with
  cosine similarity via Reciprocal Rank Fusion. WhatsApp documents stay scoped to their chat.
* `knowledge_search` / `document_qa` answer strictly from retrieved passages with citations, and abstain when
  the passages don't contain the answer (keyword evidence mode when the model is offline).

## 5. Voice, wake word and talkback

Fixes behind "it doesn't wake up":

* **Setup never installed the voice packages.** `setup_jarvis.ps1` now installs `.[voice,windows]`
  (openwakeword, silero-vad-lite, faster-whisper, sounddevice, piper, keyboard) and runs
  `scripts/setup_models.py`.
* **Missing Whisper weights crashed voice startup** (the repo has `models/whisper/base/` but `model.bin` is
  git-ignored). The engine now falls back to downloading the model size, and the error message says what to run.
* **Wake model fallback**: if the bundled ONNX model can't load, the built-in `hey_jarvis` model is used.
  Threshold defaults to 0.5 (`[voice] threshold`).
* **Mic resampling** was done per 20 ms block, adding a click train (up to ~30 % distortion) on microphones that
  cannot open at 16 kHz. A stateful resampler now matches whole-signal resampling exactly.
* **Wake detection batching**: queued audio is processed in one inference call instead of one thread hop
  per 20 ms frame, so detection keeps up on slow CPUs.
* **VAD fallback**: without Silero, an adaptive energy detector keeps voice usable.
* **Long commands**: the final transcript now uses the whole utterance (it was cut to the last 6 s), and a
  stale partial is no longer reused (it could drop the last words).
* **Barge-in**: saying "Hey Jarvis" while JARVIS is talking interrupts it (with a stricter threshold, so
  its own voice doesn't trigger it). In the follow-up window, audio captured while JARVIS speaks is ignored,
  so it no longer answers itself. The follow-up window starts when JARVIS *finishes* speaking.
* **Talkback**: `stop_speaking` was defined twice, and the second definition disabled cancellation of
  responses still being synthesized. Acknowledgements no longer synthesize on the event loop (which stalled
  the audio pipeline). Long answers are spoken sentence by sentence so speech starts sooner, and WhatsApp
  commands are no longer read aloud on the PC.

Troubleshooting:

1. `python -m jarvis.diagnostics`: look for `Speech model`, `Wake word model`, `silero_vad_lite`,
   `sounddevice`, `keyboard`, `Audio devices`.
2. `http://127.0.0.1:8765/voice/status` shows whether the pipeline runs and the last error.
3. If it wakes too rarely, lower `[voice] threshold` (e.g. 0.4); if it wakes by itself, raise it.
4. Ctrl+Shift+J (push-to-talk) works even when the wake word is unavailable.

## 6. Browser automation

* Browser tools previously ran each call in a fresh event loop (`asyncio.run`), so only the first action of
  a session worked ("Event loop is closed" afterwards). All Playwright work now runs on one dedicated loop
  thread (`jarvis/core/computer/browser/loop.py`).
* `web_task` is an AI web agent: it opens a search (or given site), reads a numbered snapshot of the page and
  navigates / clicks / types step by step until it can answer. It stops before logins, payment or OTP fields,
  and never clicks buy / pay / order / delete buttons. Page text is treated as untrusted data.
* Site searches ("search amazon for …") open directly in your default browser (`open_website`).

## 7. Phone control (Android, ADB)

New tools: `android_key` (volume, lock/wake, media, home/back/recents, camera), `android_input` (type, tap,
swipe), `android_open_url`, `android_dial` (opens the dialer with a number or saved contact; you tap call),
`android_screenshot`, plus app launching by spoken name (resolved against installed packages). All ADB calls
are fixed templates; no arbitrary shell. Connect the phone with USB debugging, or pair ADB over Wi-Fi.

## 8. Reminders

`set_reminder` understands "in 10 minutes", "at 6 pm", "tomorrow at 10", "tonight"; due reminders are spoken,
shown in the UI (`reminder.due` event) and pushed to the phone when notifications are configured.
Stored in `data/reminders.json`.

## 9. Tests

* `jarvis/tests/fake_ollama.py`: in-process fake Ollama server (no network) used by all AI tests.
* `jarvis/tests/ai_harness.py`: full stack (router, planner, agent, RAG, WhatsApp AI) for end-to-end tests.
* Generalization benchmark (deterministic, no model): `python tests/generalization/benchmark_runner.py`.
