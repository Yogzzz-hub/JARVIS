"""Notepad Application Adapter translating high-level flows into verified UIA patterns."""
from __future__ import annotations

from typing import Optional
from jarvis.core.computer.models import InteractionOutcome
from jarvis.core.computer.windows.actions import WindowsActionRunner


class NotepadAdapter:
    """Specialized adapter for Microsoft Notepad."""

    def __init__(self, runner: Optional[WindowsActionRunner] = None) -> None:
        self.runner = runner or WindowsActionRunner()

    def write_text(self, window_id: str, text: str) -> InteractionOutcome:
        """Write note into Notepad's primary text editor control."""
        return self.runner.set_value(
            window_id=window_id,
            value=text,
            target_name="Text Editor",
        )
