"""JARVIS EDGE — Desktop Operator Module.

Contains the DictationController, FocusGuard, and ScreenResource management
for the Voice-First Universal PC Operator.
"""

from jarvis.core.desktop.focus_guard import FocusGuard, FocusState
from jarvis.core.desktop.dictation_controller import (
    DictationController,
    DictationState,
    DictationTarget,
)

__all__ = [
    "FocusGuard",
    "FocusState",
    "DictationController",
    "DictationState",
    "DictationTarget",
]
