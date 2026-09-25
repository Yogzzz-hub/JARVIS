"""Typed Slot Pipeline Schemas and Values for JARVIS Edge.

Provides structured, typed representations for extracted slots:
- Percentage
- Ordinal
- FolderRef
- ApplicationRef
- ContactRef
- DeviceRef
- ResourceRef
- DateRange
- BooleanConstraint
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union


class Percentage(int):
    """Encapsulates a bounded percentage (0-100)."""
    def __new__(cls, value: Union[int, float, str]):
        if isinstance(value, str):
            clean = value.replace("%", "").replace("percent", "").strip()
            val = int(round(float(clean)))
        else:
            val = int(round(float(value)))
        val = max(0, min(100, val))
        return super().__new__(cls, val)


class Ordinal(int):
    """Encapsulates an ordinal index (1-based, or -1 for last)."""
    def __new__(cls, value: Union[int, str]):
        if isinstance(value, str):
            v_lower = value.lower().strip()
            word_map = {
                "first": 1, "1st": 1, "one": 1,
                "second": 2, "2nd": 2, "two": 2,
                "third": 3, "3rd": 3, "three": 3,
                "fourth": 4, "4th": 4, "four": 4,
                "fifth": 5, "5th": 5, "five": 5,
                "last": -1, "final": -1, "-1": -1,
            }
            val = word_map.get(v_lower, int(v_lower)) if v_lower in word_map or v_lower.isdigit() or v_lower == "-1" else 1
        else:
            val = int(value)
        return super().__new__(cls, val)


class ApplicationRef(str):
    """Encapsulates a normalized application reference."""
    pass


class FolderRef(str):
    """Encapsulates a normalized folder reference (e.g. Downloads, Documents)."""
    pass


class ContactRef(str):
    """Encapsulates a normalized contact/recipient reference."""
    pass


class DeviceRef(str):
    """Encapsulates a target device reference (e.g. phone, pc)."""
    pass


@dataclass
class ResourceRef:
    """Encapsulates an anaphoric or contextual resource reference."""
    referent: Optional[str] = None
    pronoun: Optional[str] = None
    referent_type: Optional[str] = None

    def __str__(self) -> str:
        return self.referent or self.pronoun or ""


@dataclass
class DateRange:
    """Encapsulates a temporal or date range constraint."""
    label: str = ""
    start: Optional[str] = None
    end: Optional[str] = None

    def __str__(self) -> str:
        return self.label


@dataclass
class BooleanConstraint:
    """Encapsulates a boolean constraint or negation."""
    key: str
    allowed: bool = True

    def __bool__(self) -> bool:
        return self.allowed
