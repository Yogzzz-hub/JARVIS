# JARVIS EDGE v1.0

Your personal local AI command assistant for Windows. Fully offline, privacy-first.

**Deployment status:** the deterministic desktop core is operational. Voice,
wake word, TTS, AI planning, browser/vision integration and package installation
are not activated in this runtime. Feature flags currently accept only `false`;
changing them to `true` is not sufficient to enable these subsystems.
See [review and rating](docs/REVIEW_AND_RATING.md) and [daily use](docs/DAILY_USE.md).

Setup: `powershell -NoProfile -File .\setup_jarvis.ps1`

Diagnostics: `powershell -NoProfile -File .\diagnose_jarvis.ps1`

## Quick Start

### Option 1 — Double-click
Run **`start.bat`** (or `start.ps1` in PowerShell).

### Option 2 — Terminal
```powershell
.\.venv\Scripts\Activate.ps1
python -m jarvis
```

JARVIS starts on `http://127.0.0.1:8765`. You'll see `JARVIS_READY` when it's live.

## Send Commands

Open a **second terminal** (keep the server running):

```powershell
.\.venv\Scripts\Activate.ps1
python -m jarvis.cli "open notepad"
python -m jarvis.cli "what time is it"
python -m jarvis.cli "take a screenshot"
python -m jarvis.cli "volume 50"
python -m jarvis.cli "system info" --json
```

## Available Commands

| Category     | Examples                                        |
| ------------ | ----------------------------------------------- |
| **Apps**      | `open chrome`, `open notepad`, `open calc`      |
| **Volume**    | `volume 75`, `volume` (read current)            |
| **Files**     | `list Desktop`, `find my resume`                |
| **System**    | `time`, `system info`, `screenshot`             |
| **Planning**  | `open chrome and notepad` (multi-step DAG)      |

## Configuration

Edit `jarvis/config/jarvis.toml` to configure:

- **Server**: host, port, backends
- **Features**: deployment status flags; optional subsystem activation requires runtime integration
- **Search**: file indexing roots and limits
- **Aliases**: custom app aliases (absolute `.exe` paths)

Restart JARVIS after config changes.

## Architecture

- **Core Engine** — sub-50ms command processing
- **Smart Router** — deterministic + AI routing lanes
- **File Intelligence** — full-text search across Desktop/Documents/Downloads
- **Planner** — multi-step DAG execution with parallel branches
- **Policy Engine** — risk-based approval with verification
- **Voice I/O** — streaming STT + local TTS (when enabled)
- **Computer Agent** — GUI automation via UIA + vision fallback
- **Browser Agent** — structured web interaction
- **Memory System** — layered contextual memory
- **Workflow Learning** — reusable approved patterns

See [docs/](docs/) for detailed architecture documentation.
