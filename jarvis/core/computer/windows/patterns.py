"""UI Automation Pattern Wrappers."""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("jarvis.computer.windows.patterns")

try:
    import uiautomation as auto
except ImportError:
    auto = None


class UIAPatterns:
    """Executes Microsoft UI Automation control patterns."""

    @staticmethod
    def invoke(ctrl: Any) -> bool:
        """Invoke a button or clickable control."""
        try:
            pattern = ctrl.GetInvokePattern()
            if pattern:
                pattern.Invoke()
                return True
        except Exception as e:
            logger.warning(f"InvokePattern failed: {e}")
        return False

    @staticmethod
    def set_value(ctrl: Any, value: str) -> bool:
        """Set text value via ValuePattern."""
        try:
            pattern = ctrl.GetValuePattern()
            if pattern:
                pattern.SetValue(value)
                return True
        except Exception as e:
            logger.warning(f"ValuePattern failed: {e}")
        return False

    @staticmethod
    def toggle(ctrl: Any) -> Optional[int]:
        """Toggle a checkbox and return new toggle state."""
        try:
            pattern = ctrl.GetTogglePattern()
            if pattern:
                pattern.Toggle()
                return pattern.ToggleState
        except Exception as e:
            logger.warning(f"TogglePattern failed: {e}")
        return None

    @staticmethod
    def select(ctrl: Any) -> bool:
        """Select an item via SelectionItemPattern."""
        try:
            pattern = ctrl.GetSelectionItemPattern()
            if pattern:
                pattern.Select()
                return True
        except Exception as e:
            logger.warning(f"SelectionItemPattern failed: {e}")
        return False

    @staticmethod
    def expand(ctrl: Any) -> bool:
        """Expand a dropdown or tree node via ExpandCollapsePattern."""
        try:
            pattern = ctrl.GetExpandCollapsePattern()
            if pattern:
                pattern.Expand()
                return True
        except Exception as e:
            logger.warning(f"ExpandCollapsePattern.Expand failed: {e}")
        return False

    @staticmethod
    def collapse(ctrl: Any) -> bool:
        """Collapse a dropdown or tree node via ExpandCollapsePattern."""
        try:
            pattern = ctrl.GetExpandCollapsePattern()
            if pattern:
                pattern.Collapse()
                return True
        except Exception as e:
            logger.warning(f"ExpandCollapsePattern.Collapse failed: {e}")
        return False
