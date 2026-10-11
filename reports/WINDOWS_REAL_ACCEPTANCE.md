# Windows acceptance — local owner machine

Status: **MORE_DEVELOPMENT_REQUIRED**. The owner explicitly chose “Continue automated work; I’ll test voice later.” Voice ratings and natural owner commands are therefore deferred, not marked passed.

Actual environment: Windows 11 build 26200, approximately 16 GiB RAM, NVIDIA GeForce RTX 3050 6GB Laptop GPU (6,144 MiB), driver 577.05. Existing `.venv-stage24` reported PyTorch 2.11.0+cu128 with CUDA available. This does not mean every production model uses CUDA. Available system memory during this run was approximately 1 GiB; unrelated applications were left running.

The existing `start.ps1` launcher was used. Initial startup logged `JARVIS_READY`, 44,022 ms startup, approximately 1,068 MiB RSS, 234 tools and database readiness. Concurrent full tests later caused a database lock; the acceptance-owned backend was stopped before further regression runs. The interrupted collector was recorded as failed, not successful. Final sequential acceptance results follow below.

WhatsApp was launched through the existing bridge implementation using the existing fresh auth directory with READ_ONLY=1 and empty one-shot send variables. The bridge test suite passed 24 tests. Session/inbox readiness is reported from actual diagnostics; stored data or auth-file presence alone cannot establish READY. No messages were sent.

Google account metadata is not fresh OAuth authorization. The collector does not refresh tokens; missing fresh credentials means AUTH_MISSING/NOT_TESTED. Phone, MCP and new autonomous code agents require separate readiness evidence. No device/auth status is inferred from a mock.

No candidate promoted. No synthetic utterance counted among the required 50 natural owner commands. No owner listening rating, accuracy, long-term leak verdict or GPU residency was fabricated.

Local review pages, when the backend is running: `http://127.0.0.1:8765/dashboard/acceptance/page` and the existing `/dashboard/voice-benchmark/page`.
