# Daily use: current deployment

Use Python 3.12 (the project's declared requirement), with the existing `.venv`.
Double-click `start.bat`. The launcher validates imports/configuration and reserves
the service port before creating runtime workers. An occupied port produces a
clear error without launching another runtime. Stop the service with Ctrl+C in
its original terminal, then restart to load updated code.

From a second PowerShell terminal in this folder:

```powershell
.\.venv\Scripts\python.exe -m jarvis.cli "What time is it?"
.\.venv\Scripts\python.exe -m jarvis.cli "Please open Notepad."
.\.venv\Scripts\python.exe -m jarvis.cli "Open Notepad and Calculator."
.\.venv\Scripts\python.exe -m jarvis.cli "Turn volume to twenty five percent."
.\.venv\Scripts\python.exe -m jarvis.cli "system info"
.\.venv\Scripts\python.exe -m jarvis.cli "Hey Jarvis, cancel."
```

Cancellation signals active tasks; an OS action already started may finish.
It does not terminate the service. Unknown or disabled capabilities return an
explanation. They do not install software automatically.

## Desktop UI Interface (PySide6 + QML)

JARVIS EDGE includes a native desktop interface with three operational modes:
1. **System Tray & Floating Orb**: Resides in the Windows taskbar tray; double-click opens the dashboard.
2. **Mini Voice Overlay (`Ctrl + Shift + J`)**: Always-on-top borderless HUD for immediate queries, live audio waveforms, and transcripts.
3. **Full Dashboard (`Ctrl + Shift + D`)**: System diagnostics, hardware telemetry, activity logs, memory, and settings.

Launch independently with:
```powershell
python -m jarvis.ui
```


## Limitations you should know

- **Voice/PTT/wake word:** not activated. Ctrl+Shift+J and spoken commands are not
  connected to the running gateway. Audio hardware discovery succeeds, but this
  does not establish speech recognition or playback acceptance.
- **TTS:** Piper model files exist, but production voice output is not integrated.
- **Applications:** registered App Paths and Start Menu entries are indexed.
  Newly installed apps require a restart to refresh. An unrecognized shortcut's
  process identity can still prevent verification. Custom executable aliases
  must be explicit absolute existing `.exe` paths.
- **Files:** search components exist; initial indexing, OneDrive known-folder
  discovery and cross-command references need further deployment work.
- **Install/close apps:** not exposed as working runtime tools. WinGet being
  installed does not mean JARVIS can install packages. Do not interpret examples
  in the architecture documentation as implemented deployment commands.
- **Planner, browser, UIA, vision:** subsystem code exists, but broad natural
  language integration is disabled/incomplete. Installed dependencies alone do
  not enable these features.
- **Google:** disconnected and optional. No OAuth setup was performed.
- **Phone and login startup:** not activated. No automatic login task was created.

Policy-required operations remain blocked without an appropriate approval
ticket. A complete voice confirmation interface has not been wired into this
deployment. UAC and Windows security prompts remain user controlled.

## Setup and troubleshooting

```powershell
powershell -NoProfile -File .\setup_jarvis.ps1
powershell -NoProfile -File .\setup_jarvis.ps1 -Browser
powershell -NoProfile -File .\diagnose_jarvis.ps1
.\.venv\Scripts\python.exe -m pytest tests -q
```

The optional browser setup installs Playwright/Chromium for subsystem tests.
Diagnostics distinguish required import/configuration failures from optional
feature warnings. The setup script reuses the environment and does not replace
it or download unconfigured AI models. The previous requirements lock is a
historical snapshot; `pyproject.toml` defines the current core dependencies.

If the port is occupied, use the existing service or stop it in its own terminal.
If imports fail, run setup. If an optional feature is disabled, consult the review
report rather than simply switching its flag to `true`.
