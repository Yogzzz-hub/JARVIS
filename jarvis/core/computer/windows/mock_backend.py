"""Mock / Synthetic Windows UIA Backend for Headless Testing and CI Benchmarks."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from jarvis.core.computer.models import UIBackend, UIElement, UIObservation


class MockUIAControl:
    """Synthetic UIA control for reproducible tests."""

    def __init__(
        self,
        name: str = "",
        automation_id: str = "",
        control_type: str = "Control",
        value: str = "",
        checked: Optional[bool] = None,
        is_password: bool = False,
        children: Optional[List[MockUIAControl]] = None,
    ) -> None:
        self.Name = name
        self.AutomationId = automation_id
        self.ControlTypeName = control_type
        self.Value = value
        self.ToggleState = 1 if checked else 0
        self.is_password = is_password
        self.children = children or []
        self.invoked = False

    def GetChildren(self) -> List[MockUIAControl]:
        return self.children

    def Control(self, Name: Optional[str] = None, AutomationId: Optional[str] = None) -> Optional[MockUIAControl]:
        """Find a child control matching Name or AutomationId recursively."""
        for child in self.children:
            if AutomationId and child.AutomationId == AutomationId:
                return child
            if Name and child.Name.lower() == Name.lower():
                return child
            res = child.Control(Name=Name, AutomationId=AutomationId)
            if res:
                return res
        return None

    def GetInvokePattern(self) -> Optional[MockUIAControl]:
        return self if "Button" in self.ControlTypeName or "Item" in self.ControlTypeName else None

    def Invoke(self) -> None:
        self.invoked = True

    def GetValuePattern(self) -> Optional[MockUIAControl]:
        return self if "Edit" in self.ControlTypeName or "Document" in self.ControlTypeName else None

    def SetValue(self, val: str) -> None:
        self.Value = val

    def GetTogglePattern(self) -> Optional[MockUIAControl]:
        return self if "Check" in self.ControlTypeName else None

    def Toggle(self) -> None:
        self.ToggleState = 1 if self.ToggleState == 0 else 0


class MockWindowsUIABackend:
    """In-memory mock backend simulating Windows UIA desktop state."""

    def __init__(self) -> None:
        self.windows: Dict[str, Dict[str, Any]] = {
            "1001": {
                "window_id": "1001",
                "hwnd": 1001,
                "process_id": 401,
                "window_title": "Untitled - Notepad",
                "class_name": "Notepad",
                "foreground": True,
                "enabled": True,
                "root_control": MockUIAControl(
                    name="Untitled - Notepad",
                    control_type="WindowControl",
                    children=[
                        MockUIAControl(name="Text Editor", automation_id="15", control_type="EditControl"),
                        MockUIAControl(name="File", automation_id="FileMenu", control_type="MenuItemControl"),
                        MockUIAControl(name="Save", automation_id="SaveButton", control_type="ButtonControl"),
                    ],
                ),
            },
            "1002": {
                "window_id": "1002",
                "hwnd": 1002,
                "process_id": 402,
                "window_title": "Settings",
                "class_name": "ApplicationFrameWindow",
                "foreground": False,
                "enabled": True,
                "root_control": MockUIAControl(
                    name="Settings",
                    control_type="WindowControl",
                    children=[
                        MockUIAControl(name="Bluetooth & devices", automation_id="BluetoothNav", control_type="ListItemControl"),
                        MockUIAControl(name="Bluetooth toggle", automation_id="BluetoothSwitch", control_type="CheckBoxControl", checked=True),
                    ],
                ),
            },
            "1003": {
                "window_id": "1003",
                "hwnd": 1003,
                "process_id": 403,
                "window_title": "Ambiguous App",
                "class_name": "TestApp",
                "foreground": False,
                "enabled": True,
                "root_control": MockUIAControl(
                    name="Ambiguous App",
                    control_type="WindowControl",
                    children=[
                        MockUIAControl(name="Delete", automation_id="btn_del_1", control_type="ButtonControl"),
                        MockUIAControl(name="Delete", automation_id="btn_del_2", control_type="ButtonControl"),
                    ],
                ),
            },
            "1004": {
                "window_id": "1004",
                "hwnd": 1004,
                "process_id": 404,
                "window_title": "Canvas Game (No UIA)",
                "class_name": "GameWindow",
                "foreground": False,
                "enabled": True,
                "root_control": MockUIAControl(
                    name="Canvas Game",
                    control_type="WindowControl",
                    children=[],  # No children / no accessibility tree
                ),
            },
        }

    def list_windows(self) -> List[Dict[str, Any]]:
        return list(self.windows.values())

    def find_window_control(self, window_id: str) -> Optional[Any]:
        win = self.windows.get(str(window_id))
        return win["root_control"] if win else None

    def get_focused_control(self) -> Optional[Any]:
        return self.windows["1001"]["root_control"].children[0]
