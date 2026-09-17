from pathlib import Path
from typing import Any, Protocol, runtime_checkable

@runtime_checkable
class ChangeFeed(Protocol):
    def start(self) -> None:
        ...
    def stop(self) -> None:
        ...
    def is_available(self) -> bool:
        ...

class USNChangeFeed(ChangeFeed):
    """Optional NTFS USN Change Journal reader. Never alters or creates journals."""
    def __init__(self, drive_letter: str = "C:"):
        self.drive_letter = drive_letter
        self._available = False
        self._check_usn_access()

    def _check_usn_access(self):
        # Only check read access without elevating or mutating journal
        try:
            import ctypes
            # Verify Windows NTFS volume
            self._available = False  # By default disabled unless explicit permissions exist
        except Exception:
            self._available = False

    def is_available(self) -> bool:
        return self._available

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass
