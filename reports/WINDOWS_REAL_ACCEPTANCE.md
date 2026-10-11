# Windows acceptance — local owner machine

Status: **MORE_DEVELOPMENT_REQUIRED**. The owner explicitly chose “Continue automated work; I’ll test voice later.” Voice ratings and natural owner commands are therefore deferred, not marked passed.

Actual environment: Windows 11 build 26200, approximately 16 GiB RAM, NVIDIA GeForce RTX 3050 6GB Laptop GPU (6,144 MiB), driver 577.05. Existing `.venv-stage24` reported PyTorch 2.11.0+cu128 with CUDA available. This does not mean every production model uses CUDA. Available system memory during this run was approximately 1 GiB; unrelated applications were left running.

The existing `start.ps1` launcher was used. Initial startup logged `JARVIS_READY`, 44,022 ms startup, approximately 1,068 MiB RSS, 234 tools and database readiness. Concurrent full tests later caused a database lock; the acceptance-owned backend was stopped before further regression runs. The interrupted collector was recorded as failed, not successful. Final sequential acceptance results follow below.

WhatsApp was launched through the existing bridge implementation using the existing fresh auth directory with READ_ONLY=1 and empty one-shot send variables. The bridge test suite passed 24 tests. Session/inbox readiness is reported from actual diagnostics; stored data or auth-file presence alone cannot establish READY. No messages were sent.

Google account metadata is not fresh OAuth authorization. The collector does not refresh tokens; missing fresh credentials means AUTH_MISSING/NOT_TESTED. Phone, MCP and new autonomous code agents require separate readiness evidence. No device/auth status is inferred from a mock.

No candidate promoted. No synthetic utterance counted among the required 50 natural owner commands. No owner listening rating, accuracy, long-term leak verdict or GPU residency was fabricated.

Local review pages, when the backend is running: `http://127.0.0.1:8765/dashboard/acceptance/page` and the existing `/dashboard/voice-benchmark/page`.

## Completed combined-runtime automated window

Observed on 2026-10-11 using the normal `python -m jarvis` backend entry point, reusing the UI already started by `start.ps1` to avoid a duplicate window. Startup logged **20,162.5 ms**, **1,069.5 MiB RSS**, **237 tools**, database ready and the Proactor event loop. `/health` reported ready and zero dropped events/persistence/metrics/logs at collection. Both `/dashboard/acceptance/page` and `/dashboard/voice-benchmark/page` returned HTTP 200.

| Check | Observed result |
|---|---|
| Time queries | 8/8 SUCCESS; cold 2209.6 ms, warm median 32.7 ms, warm p95 1538.9 ms |
| Knowledge/context queries | 6/6 runtime SUCCESS; 3441.5?5000.4 ms; factual/context quality not independently owner-rated |
| Backend resource samples | idle peak RSS 1129.9 MiB; deterministic-window peak 1132.1 MiB; no long-term leak inference |
| WhatsApp | DEGRADED_LIVE, PARTIAL_SYNC; authenticated/transport connected, history incomplete, event stream not verified, snapshot not current |
| WhatsApp bridge write guard | Bridge launched with read-only environment flag; diagnostic endpoint does not report it independently; no send attempted |
| Google | AUTH_MISSING, zero configured accounts; no OAuth refresh |
| Phone / external MCP | PHONE_NOT_READY / MCP_NOT_TESTED; no pairing or foreign execution |
| Optional cloud brain | Actual `/api/brain/status`: ollama mode, SDK absent, built-in writes false; no cloud call |
| Voice | Runtime enabled/running, TTS enabled, hotkey registered, no reported voice error; no intelligibility/listening verdict |

Operational trace aggregate contained 19 records, **0 REAL_SHADOW**, **0 owner-reviewed**, **0 VERIFIED_REAL**; accuracy is UNREVIEWED. These automated commands are SYNTHETIC and do not satisfy 50 natural owner commands.

Ollama directly reported three resident local models: `llama3.2:latest` (2,334,591,548 bytes VRAM, context 4096), `nomic-embed-text:latest` (323,150,151 bytes, context 2048), and `qwen3:1.7b` (1,482,476,747 bytes, context 4096). Installed inventory is retained privately; no downloads were requested. Total GPU use was approximately 4,685 MiB of 6,144 MiB after the window. System memory use was 88.2%; unrelated apps were left running. These measurements do not establish memory fitness for simultaneous additional large models.

Final acceptance remains **MORE_DEVELOPMENT_REQUIRED**: variable latency, broad-suite failures, incomplete WhatsApp readiness, missing integration credentials/pairing, owner voice/natural-command review and universal-browser capabilities remain open. No candidate was promoted or message sent. The normal backend and existing UI remain running for owner review.
