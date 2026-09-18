"""Focused Window Snapshot Generation and Control View Reduction."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional
from jarvis.core.computer.models import UIBackend, UIElement, UIObservation
from jarvis.core.computer.windows.backend import WindowsUIABackend

logger = logging.getLogger("jarvis.computer.windows.snapshot")

try:
    import uiautomation as auto
except ImportError:
    auto = None


class UIASnapshotBuilder:
    """Extracts bounded structured Control View snapshots from UIA trees."""

    def __init__(self, backend: Optional[WindowsUIABackend] = None) -> None:
        self.backend = backend or WindowsUIABackend()

    def capture_snapshot(
        self,
        window_id: str,
        max_elements: int = 500,
        max_depth: int = 8,
    ) -> UIObservation:
        """Capture a bounded control view snapshot of the specified window."""
        window_ctrl = self.backend.find_window_control(window_id)
        if not window_ctrl:
            return UIObservation(
                observation_id=f"snap_err_{int(time.time()*1000)}",
                backend=UIBackend.WINDOWS_UIA,
                application="Unknown",
                window_title="Unknown",
                elements=[],
                is_untrusted=True,
                quarantine_notes=["Window control could not be accessed."],
            )

        app_title = window_ctrl.Name or "Window"
        elements: List[UIElement] = []
        element_counter = 1

        def traverse(ctrl: Any, depth: int, ancestor_path: str):
            nonlocal element_counter
            if depth > max_depth or len(elements) >= max_elements:
                return

            try:
                name = (ctrl.Name or "").strip()
                auto_id = ctrl.AutomationId or ""
                control_type = ctrl.ControlTypeName or "Control"
                role = control_type

                # Prune useless decorative containers
                is_container = control_type in ("PaneControl", "GroupControl", "CustomControl")
                has_meaningful_id = bool(name or auto_id)

                # Determine value if supported
                value_summary = ""
                editable = False
                try:
                    val_pattern = ctrl.GetValuePattern()
                    if val_pattern:
                        value_summary = val_pattern.Value or ""
                        editable = not val_pattern.IsReadOnly
                except Exception:
                    pass

                # Check toggle state
                checked = None
                try:
                    toggle_pattern = ctrl.GetTogglePattern()
                    if toggle_pattern:
                        checked = (toggle_pattern.ToggleState == 1)
                except Exception:
                    pass

                # Check supported actions
                actions = []
                try:
                    if ctrl.GetInvokePattern():
                        actions.append("invoke")
                except Exception:
                    pass
                try:
                    if ctrl.GetValuePattern():
                        actions.append("set_value")
                except Exception:
                    pass
                try:
                    if ctrl.GetTogglePattern():
                        actions.append("toggle")
                except Exception:
                    pass
                try:
                    if ctrl.GetSelectionItemPattern():
                        actions.append("select")
                except Exception:
                    pass

                if control_type != "WindowControl" and (has_meaningful_id or actions or editable or value_summary):
                    elem_id = f"uia:w{window_id}:e{element_counter}"
                    element_counter += 1
                    ui_elem = UIElement(
                        element_id=elem_id,
                        role=role,
                        name=name,
                        control_type=control_type,
                        automation_id=auto_id,
                        value_summary=value_summary,
                        enabled=getattr(ctrl, "IsEnabled", True),
                        visible=not getattr(ctrl, "IsOffscreen", False),
                        editable=editable,
                        checked=checked,
                        ancestor_path=ancestor_path,
                        actions_supported=actions,
                    )
                    elements.append(ui_elem)

                # Recurse children
                next_path = f"{ancestor_path}/{name or control_type}"
                for child in ctrl.GetChildren():
                    traverse(child, depth + 1, next_path)

            except Exception as e:
                logger.debug(f"Error reading node: {e}")

        # Start traversal from top-level window
        traverse(window_ctrl, depth=1, ancestor_path=app_title)

        obs = UIObservation(
            observation_id=f"snap_{window_id}_{int(time.time()*1000)}",
            backend=UIBackend.WINDOWS_UIA,
            application=app_title,
            window_title=app_title,
            elements=elements,
            is_untrusted=True,
        )
        obs.compute_state_hash()
        return obs
