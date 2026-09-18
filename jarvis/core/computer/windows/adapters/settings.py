"""Windows Settings Application Adapter."""
from __future__ import annotations

from typing import Optional
from jarvis.core.computer.models import InteractionOutcome
from jarvis.core.computer.windows.actions import WindowsActionRunner


class SettingsAdapter:
    """Specialized adapter for Windows Settings application."""

    def __init__(self, runner: Optional[WindowsActionRunner] = None) -> None:
        self.runner = runner or WindowsActionRunner()

    def show_bluetooth(self, window_id: str) -> InteractionOutcome:
        """Select Bluetooth & devices page in Windows Settings."""
        return self.runner.invoke(
            window_id=window_id,
            target_name="Bluetooth & devices",
        )
