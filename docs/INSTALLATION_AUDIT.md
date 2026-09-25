# Installation audit

2026-09-18. Reused `.venv`, Python 3.12.14, matching the repository's
`>=3.12,<3.13` requirement. System `py` reports Python 3.14.4 and was not used to
run the application. Existing environment and source/configuration checkpoint
were preserved before edits.

| Component | Action and purpose | Source |
| --- | --- | --- |
| JARVIS 1.0.0 | Installed editable from this workspace after correcting core dependency declarations | Local project |
| Playwright 1.63.0, Pillow 12.3.0 | Added for existing browser and vision tests | pip package index |
| Chromium | Ran Playwright's managed browser installer; completed successfully | Playwright installer |
| sounddevice 0.5.6 | Added for audio device discovery | pip package index |
| uiautomation 2.0.29, pywin32 312 | Added for existing Windows backend imports | pip package index |
| tzdata 2026.4, google-api-python-client 2.200.0 | Added for existing calendar and Drive fake-provider tests; no OAuth performed | pip package index |
| PyYAML 6.0.3, RapidFuzz 3.14.6, lxml 6.1.1 | Reinstalled same versions using compatible cp312 Windows wheels after pip check failures | pip package index |
| Git, WinGet, Ollama, nvidia-smi | Already on PATH; no reinstall | Existing machine installations |
| Faster-Whisper, openWakeWord, Piper runtime | Still missing/unintegrated; no production voice acceptance claimed | Not installed in this pass |

Transitive dependencies installed by pip are captured in
`.runtime/review/installed-packages.json`. No system software, Windows login
task, OAuth connection or AI model download was performed. FFmpeg was not on
PATH; no current activated capability required installing it.

Final core imports and `pip check` pass. Optional feature limitations are recorded
in `REVIEW_AND_RATING.md`. The historical `requirements-lock.txt` was preserved;
use the updated `pyproject.toml` and setup script for the current dependency set.
