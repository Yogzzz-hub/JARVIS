"""Automation Priority and Capability Selection for JARVIS EDGE."""
from __future__ import annotations

from enum import IntEnum
from typing import List, Optional


class AutomationPriority(IntEnum):
    """Execution priority for interactive automation methods."""
    OFFICIAL_API = 1
    NATIVE_JARVIS_TOOL = 2
    APP_SPECIFIC_API = 3
    APP_CLI = 4
    BROWSER_PLAYWRIGHT = 5
    WINDOWS_UIA = 6
    REGISTERED_SHORTCUT = 7
    CONTROLLED_INPUT = 8
    VISION_PHASE11 = 9
    ABSOLUTE_COORDINATES = 10  # Strictly prohibited in Phase 10


def select_best_automation_method(
    has_api: bool = False,
    has_native_tool: bool = False,
    has_cli: bool = False,
    is_web: bool = False,
    has_uia: bool = False,
    has_shortcut: bool = False,
    has_controlled_input: bool = False,
) -> AutomationPriority:
    """Select the highest-priority structured interaction method according to Section 1."""
    if has_api:
        return AutomationPriority.OFFICIAL_API
    if has_native_tool:
        return AutomationPriority.NATIVE_JARVIS_TOOL
    if has_cli:
        return AutomationPriority.APP_CLI
    if is_web:
        return AutomationPriority.BROWSER_PLAYWRIGHT
    if has_uia:
        return AutomationPriority.WINDOWS_UIA
    if has_shortcut:
        return AutomationPriority.REGISTERED_SHORTCUT
    if has_controlled_input:
        return AutomationPriority.CONTROLLED_INPUT
    return AutomationPriority.VISION_PHASE11
