from __future__ import annotations

import logging
from typing import Dict, Tuple

logger = logging.getLogger("jarvis.pulse.telemetry")

# Pre-seeded empirical defaults based on real Windows 11 hardware benchmarks
DEFAULT_TOOL_DURATIONS_MS: Dict[str, float] = {
    "get_time": 5.0,
    "volume_get": 12.0,
    "volume_set": 18.0,
    "system_info": 8.0,
    "show_dashboard": 5.0,
    "wake_greeting": 5.0,
    "take_screenshot": 45.0,
    "open_app": 380.0,
    "close_app": 150.0,
    "list_directory": 30.0,
    "find_file": 70.0,
    "open_file": 220.0,
    "dictate_text": 15.0,
    "save_workspace": 80.0,
    "launch_workspace": 650.0,
    "organize_downloads": 450.0,
    "batch_rename": 500.0,
    "find_duplicates": 2200.0,
    "document_qa": 1100.0,
    "capture_note": 40.0,
    "search_notes": 80.0,
    "generate_meeting_notes": 1800.0,
    "extract_audio": 3500.0,
    "trim_media_clip": 2800.0,
    "personal_briefing": 30.0,
    "start_study_focus": 15.0,
    "git_status": 120.0,
    "run_project_tests": 4500.0,
    "diagnose_error": 80.0,
    "dag_scheduler": 3200.0,
    "planner": 3500.0,
    "control": 5.0,
    "clarification": 5.0,
    "negation_guard": 5.0,
}


class DurationPredictor:
    """Predicts execution duration using Exponential Weighted Moving Average (EWMA).
    Adapts online to the user's specific PC hardware and application responsiveness.
    """

    def __init__(self, alpha: float = 0.25) -> None:
        self.alpha = alpha
        # Key: (tool_name, target_entity) -> predicted_ms
        self._ewma_cache: Dict[Tuple[str, str], float] = {}

    def predict_duration(self, tool_name: str, entity: str = "") -> float:
        """Predicts duration in milliseconds for the given tool and optional target entity."""
        key = (tool_name.lower(), entity.lower())
        if key in self._ewma_cache:
            return self._ewma_cache[key]

        # Generic tool fallback
        tool_key = (tool_name.lower(), "")
        if tool_key in self._ewma_cache:
            return self._ewma_cache[tool_key]

        # Empirical system default
        return DEFAULT_TOOL_DURATIONS_MS.get(tool_name.lower(), 400.0)

    def record_observation(self, tool_name: str, duration_ms: float, entity: str = "") -> None:
        """Updates the EWMA duration online using observed execution latency."""
        if duration_ms <= 0:
            return

        key = (tool_name.lower(), entity.lower())
        prior = self.predict_duration(tool_name, entity)
        updated = self.alpha * duration_ms + (1.0 - self.alpha) * prior
        self._ewma_cache[key] = updated

        # Also update the generic tool entry
        if entity:
            prior_generic = self.predict_duration(tool_name)
            self._ewma_cache[(tool_name.lower(), "")] = self.alpha * duration_ms + (1.0 - self.alpha) * prior_generic
