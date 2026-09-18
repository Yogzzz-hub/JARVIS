"""Windows UI Automation Subsystem."""
from jarvis.core.computer.windows.backend import WindowsUIABackend
from jarvis.core.computer.windows.windows import WindowManager
from jarvis.core.computer.windows.snapshot import UIASnapshotBuilder
from jarvis.core.computer.windows.locator import UIALocator
from jarvis.core.computer.windows.patterns import UIAPatterns
from jarvis.core.computer.windows.actions import WindowsActionRunner
from jarvis.core.computer.windows.mock_backend import MockWindowsUIABackend, MockUIAControl

__all__ = [
    "WindowsUIABackend",
    "WindowManager",
    "UIASnapshotBuilder",
    "UIALocator",
    "UIAPatterns",
    "WindowsActionRunner",
    "MockWindowsUIABackend",
    "MockUIAControl",
]
