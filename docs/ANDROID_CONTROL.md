# Android Control via scrcpy & ADB

## Architecture & Boundaries
- **scrcpy** provides an optional phone viewing and interaction surface.
- It does **NOT** replace the JARVIS Android Companion client (which handles voice STT/TTS, wake words, and UI).
- scrcpy is launched strictly **on-demand** to conserve CPU and GPU resources.

## Strict Security Invariant: No Arbitrary ADB Shell
The LLM is **never** granted arbitrary ADB or shell access. All operations are strictly validated typed actions:
- `android.status`: Query battery, screen, device model, and connection state.
- `android.open_control`: Launch scrcpy window with bounded resolution and framerate.
- `android.close_control`: Gracefully terminate scrcpy mirroring process.
- `android.home`: Simulate Home keyevent (`KEYCODE_HOME = 3`).
- `android.back`: Simulate Back keyevent (`KEYCODE_BACK = 4`).
- `android.open_app`: Launch an app by allowlisted package name or verified alias (e.g. `Spotify`, `Camera`, `Settings`).

Sensitive actions (purchases, OTP, credential prompts, account modifications) are never bypassed and remain under user control.
