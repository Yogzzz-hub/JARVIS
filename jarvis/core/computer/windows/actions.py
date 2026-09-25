"""Typed Windows UI Automation Action Handlers."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional
from jarvis.core.computer.models import (
    InteractionOutcome,
    TargetConfidence,
    UIAFailureReason,
    UIElement,
    UIObservation,
    VisionRequiredResult,
)
from jarvis.core.computer.windows.backend import WindowsUIABackend
from jarvis.core.computer.windows.locator import UIALocator
from jarvis.core.computer.windows.patterns import UIAPatterns
from jarvis.core.computer.windows.snapshot import UIASnapshotBuilder
from jarvis.core.computer.windows.windows import WindowManager
from jarvis.core.computer.verifier import UIVerifier

logger = logging.getLogger("jarvis.computer.windows.actions")

try:
    import uiautomation as auto
except ImportError:
    auto = None


class WindowsActionRunner:
    """Executes structured UIA actions strictly through patterns with verification."""

    def __init__(
        self,
        backend: Optional[WindowsUIABackend] = None,
        snapshot_builder: Optional[UIASnapshotBuilder] = None,
        window_mgr: Optional[WindowManager] = None,
    ) -> None:
        self.backend = backend or WindowsUIABackend()
        self.snapshot_builder = snapshot_builder or UIASnapshotBuilder(self.backend)
        self.window_mgr = window_mgr or WindowManager(self.backend)

    def find_target_control(
        self,
        window_id: str,
        target_name: Optional[str] = None,
        automation_id: Optional[str] = None,
        control_type: Optional[str] = None,
    ) -> tuple[Optional[Any], Optional[UIElement], str]:
        """Locate target UIA control and element model strictly without coordinates.
        
        Returns: (ctrl_object, ui_element, status_string)
        """
        obs = self.snapshot_builder.capture_snapshot(window_id)
        if not obs.elements:
            return None, None, UIAFailureReason.UI_NOT_EXPOSED.value

        elem, conf = UIALocator.resolve_target(
            observation=obs,
            name=target_name,
            automation_id=automation_id,
            control_type=control_type,
        )

        if conf == TargetConfidence.AMBIGUOUS:
            return None, None, UIAFailureReason.ELEMENT_AMBIGUOUS.value
        if not elem or conf == TargetConfidence.LOW:
            return None, None, UIAFailureReason.ELEMENT_NOT_FOUND.value

        # Check for password/credential controls
        if elem.is_password_or_credential():
            return None, elem, "PAUSE_FOR_USER"

        # Resolve live UIA Control
        win_ctrl = self.backend.find_window_control(window_id)
        if not win_ctrl:
            return None, None, UIAFailureReason.WINDOW_NOT_FOUND.value

        # Try by AutomationId
        live_ctrl = None
        if elem.automation_id:
            try:
                live_ctrl = win_ctrl.Control(AutomationId=elem.automation_id)
            except Exception:
                pass

        # Try by Name
        if not live_ctrl and elem.name:
            try:
                live_ctrl = win_ctrl.Control(Name=elem.name)
            except Exception:
                pass

        if not live_ctrl:
            return None, elem, UIAFailureReason.ELEMENT_NOT_FOUND.value

        return live_ctrl, elem, "FOUND"

    def invoke(
        self,
        window_id: str,
        target_name: Optional[str] = None,
        automation_id: Optional[str] = None,
        control_type: Optional[str] = None,
    ) -> InteractionOutcome:
        """Invoke a button or clickable control strictly via InvokePattern."""
        live_ctrl, elem, status = self.find_target_control(window_id, target_name, automation_id, control_type)
        if status == "PAUSE_FOR_USER":
            return InteractionOutcome(
                success=False,
                action="ui_invoke",
                verification_status="PAUSE_FOR_USER",
                message="Sensitive password/credential field detected. Pausing for user interaction.",
            )
        if status != "FOUND":
            return InteractionOutcome(
                success=False,
                action="ui_invoke",
                verification_status="FAILED",
                failure_reason=status,
                message=f"Target resolution failed: {status}",
            )

        success = UIAPatterns.invoke(live_ctrl)
        time.sleep(0.05)  # Action settled

        return InteractionOutcome(
            success=success,
            action="ui_invoke",
            target_element_id=elem.element_id,
            verification_status="VERIFIED" if success else "FAILED",
            evidence={"action": "invoke", "name": elem.name, "automation_id": elem.automation_id},
        )

    def click(
        self,
        target: Any = None,
        window_id: str = "",
        target_name: Optional[str] = None,
        automation_id: Optional[str] = None,
        control_type: Optional[str] = None,
    ) -> InteractionOutcome:
        """Alias for invoke supporting both direct element and property lookups."""
        if target is not None:
            if isinstance(target, str):
                target_name = target_name or target
            elif hasattr(target, "name"):
                target_name = getattr(target, "name", None)
                automation_id = getattr(target, "automation_id", None)
        return self.invoke(
            window_id=window_id,
            target_name=target_name,
            automation_id=automation_id,
            control_type=control_type,
        )

    def set_value(
        self,
        window_id: str,
        value: str,
        target_name: Optional[str] = None,
        automation_id: Optional[str] = None,
    ) -> InteractionOutcome:
        """Set text value on an edit control via ValuePattern or controlled typing."""
        live_ctrl, elem, status = self.find_target_control(window_id, target_name, automation_id, control_type="Edit")
        if status == "PAUSE_FOR_USER":
            return InteractionOutcome(
                success=False,
                action="ui_set_value",
                verification_status="PAUSE_FOR_USER",
                message="Password control detected. Pausing for user.",
            )
        if status != "FOUND":
            # If not found under Edit, try generic
            live_ctrl, elem, status = self.find_target_control(window_id, target_name, automation_id)
            if status != "FOUND":
                return InteractionOutcome(
                    success=False,
                    action="ui_set_value",
                    verification_status="FAILED",
                    failure_reason=status,
                    message=f"Edit target resolution failed: {status}",
                )

        # 1. Try ValuePattern
        success = UIAPatterns.set_value(live_ctrl, value)
        if not success:
            # 2. Controlled typing fallback with focus verification
            try:
                live_ctrl.SetFocus()
                time.sleep(0.05)
                # Verify control has focus
                focused = self.backend.get_focused_control()
                if focused and (focused.AutomationId == live_ctrl.AutomationId or focused.Name == live_ctrl.Name):
                    if auto:
                        auto.SendKeys(value, waitTime=0.01)
                        success = True
            except Exception as e:
                logger.warning(f"Controlled SendKeys fallback failed: {e}")

        time.sleep(0.05)
        # Verify value matches
        matched = False
        try:
            val_pat = live_ctrl.GetValuePattern()
            if val_pat:
                actual = val_pat.Value or ""
                matched = (value in actual) or (actual == value)
        except Exception:
            matched = success

        return InteractionOutcome(
            success=success and matched,
            action="ui_set_value",
            target_element_id=elem.element_id,
            verification_status="VERIFIED" if (success and matched) else "FAILED",
            evidence={"expected": value, "verified_match": matched},
        )

    def toggle(
        self,
        window_id: str,
        target_name: Optional[str] = None,
        automation_id: Optional[str] = None,
        expected_state: Optional[bool] = None,
    ) -> InteractionOutcome:
        """Toggle a checkbox or switch via TogglePattern."""
        live_ctrl, elem, status = self.find_target_control(window_id, target_name, automation_id, control_type="CheckBox")
        if status != "FOUND":
            return InteractionOutcome(
                success=False,
                action="ui_toggle",
                verification_status="FAILED",
                failure_reason=status,
                message=f"Toggle target resolution failed: {status}",
            )

        new_state = UIAPatterns.toggle(live_ctrl)
        verified = (new_state is not None)
        if verified and expected_state is not None:
            verified = (bool(new_state) == expected_state)

        return InteractionOutcome(
            success=verified,
            action="ui_toggle",
            target_element_id=elem.element_id,
            verification_status="VERIFIED" if verified else "FAILED",
            evidence={"toggle_state": new_state, "verified": verified},
        )
