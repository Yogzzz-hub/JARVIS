"""Safe persistent settings management for the JARVIS desktop UI."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from jarvis.config import ROOT

logger = logging.getLogger("jarvis.ui.settings")

SETTINGS_FILE = ROOT / "data" / "ui_settings.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "overlay_location": "bottom-center",
    "overlay_timeout_sec": 3.0,
    "floating_orb_enabled": False,
    "start_minimized": False,
    "close_to_tray": True,
    "low_resource_mode": False,
    "theme": "dark",
    "ptt_hotkey": "ctrl+shift+j",
    "dashboard_hotkey": "ctrl+shift+d",
    "speak_responses": True,
    "show_notifications": True,
    "ui_scale": 1.0,
    "metrics_interval_ms": 1000,
    "ui_3d": True,  # real-time 3D reactor (falls back to 2D automatically)
}


class UISettings:
    """Manages reading and updating safe UI-only settings."""

    def __init__(self, path: Path | None = None):
        self.path = path or SETTINGS_FILE
        self._settings = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> None:
        try:
            if self.path.exists():
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._settings.update(data)
        except Exception as exc:
            logger.warning("Could not read UI settings file, using defaults: %s", exc)

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2)
        except Exception as exc:
            logger.warning("Could not save UI settings: %s", exc)

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default if default is not None else DEFAULT_SETTINGS.get(key))

    def set(self, key: str, value: Any) -> None:
        self._settings[key] = value
        self.save()

    def override(self, key: str, value: Any) -> None:
        """Change a setting for this session only (not written to disk)."""
        self._settings[key] = value

    def all(self) -> dict[str, Any]:
        return dict(self._settings)
