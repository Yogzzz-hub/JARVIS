# JARVIS EDGE v1.0 — Desktop UI Documentation

## Overview

JARVIS EDGE v1.0 Desktop UI is an advanced, ultra-lightweight, hardware-accelerated desktop interface built using **PySide6** and **Qt Quick / QML**. It interfaces with the authoritative local JARVIS backend over high-throughput WebSocket (`ws://127.0.0.1:8765/ws`) and REST endpoints (`http://127.0.0.1:8765`), maintaining strict separation between presentation and business logic.

---

## Key Features

1. **Three Dynamic UI Modes:**
   - **Full Dashboard:** High-fidelity management cockpit with pages for Home, Activity DAG, System Telemetry, Safe Memory, Workflows, Devices, Integrations, Settings, and Diagnostics.
   - **Mini Voice Overlay:** Always-on-top, borderless floating HUD centered above the taskbar. Displays live partial/final transcription, audio amplitude waveform, and auto-dismisses 3 seconds after execution completes.
   - **System Tray & Floating Orb:** Persistent `QSystemTrayIcon` with contextual quick actions (Talk, Dashboard, Cancel Task, Settings, Restart UI) and optional 48px draggable floating orb.

2. **Strict Security & Zero Direct AI Bypass:**
   - The UI never directly touches Ollama, the filesystem, or Google APIs.
   - All actions route strictly through backend router policies.
   - Phase-5 confirmation tickets require explicit user approval/rejection.
   - Automatic credential redaction masks API keys, secrets, and auth tokens.

3. **Performance Optimization:**
   - Pure QML Quick Items; zero Electron or Chromium overhead.
   - Bounded 1Hz telemetry sampling.
   - Low Resource UI Mode for laptops or power-sensitive workflows.

---

## Launching

### Quick Start
Double-click `start.bat` or run:
```powershell
.\start.ps1
```

### UI Independent Launch
If the JARVIS backend is already running:
```powershell
python -m jarvis.ui
```

---

## Keyboard Shortcuts

- **`Ctrl + Shift + J`**: Push-To-Talk (PTT) / Activate Mini Voice Overlay.
- **`Ctrl + Shift + D`**: Open Full Dashboard.
- **`Esc`**: Dismiss voice overlay or modal dialogues.
