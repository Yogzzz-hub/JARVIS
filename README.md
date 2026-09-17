# JARVIS EDGE — Phase 1

Local Windows command service. No models, voice, planner, cloud connections or GPU computation.

Use Python 3.12 and a virtual environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e '.[test]'
python -m jarvis
```

In another activated terminal:

```powershell
python -m jarvis.cli "open notepad"
python -m jarvis.cli "time" --json
python -m pytest
python -m jarvis.scripts.bench_core
```

This workspace also includes a local Python 3.12 runtime under `.runtime` and an
already prepared `.venv`. Use `.\.venv\Scripts\python.exe` directly if activation
is restricted. The system default `python` may be a different version.

Commands: `open <indexed app>`, `volume <0-100>`, `volume`, `list <path>`,
`screenshot`, `time`, `system info`. Paths containing spaces are accepted.
Screenshots use unique PNG files under `jarvis/screenshots`.

Configure once at startup in `jarvis/config/jarvis.toml`. User aliases must be
absolute existing `.exe` paths. Restart to refresh the index. Unknown applications
produce a failure; unidentifiable shortcuts may launch but cannot report verified success.

HTTP binds to `127.0.0.1:8765`. Native work has two admission slots; overload returns
503. WebSocket commands require `version: 1`, `request_id`, `type: "command"`, and
`text`. Ping uses the same version/id fields and `type: "ping"`. Binary frames are
reserved and rejected explicitly. Browser Origin connections are rejected.

Press Ctrl+C for graceful shutdown. Cancellation cannot undo a native action that
already started; the response states that limitation. Verification checks process
existence, not whether an application window is foreground or responsive.

See [architecture](jarvis/docs/ARCHITECTURE.md), [performance](jarvis/docs/PERFORMANCE.md),
[acceptance evidence](jarvis/docs/PROGRESS.md), and [licenses](jarvis/docs/LICENSES.md).
