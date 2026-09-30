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
import re
from typing import Any, Dict, List, Optional, Tuple, Union


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

    @property
    def value(self) -> int:
        return int(self)


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

    @property
    def value(self) -> int:
        return int(self)


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


@dataclass
class SizeConstraint:
    """Encapsulates file/resource size constraints in bytes."""
    min_bytes: Optional[int] = None
    max_bytes: Optional[int] = None
    min_inclusive: bool = True
    max_inclusive: bool = True
    label: str = ""

    def matches(self, size_bytes: int) -> bool:
        if self.min_bytes is not None:
            if self.min_inclusive and size_bytes < self.min_bytes:
                return False
            if not self.min_inclusive and size_bytes <= self.min_bytes:
                return False
        if self.max_bytes is not None:
            if self.max_inclusive and size_bytes > self.max_bytes:
                return False
            if not self.max_inclusive and size_bytes >= self.max_bytes:
                return False
        return True

    def __str__(self) -> str:
        return self.label or f"[{self.min_bytes}B, {self.max_bytes}B]"


@dataclass
class SpatialConstraint:
    """Encapsulates window or display spatial positioning (left, right, top, bottom, center)."""
    position: str
    target: Optional[str] = None

    def __str__(self) -> str:
        return f"{self.target or 'window'}:{self.position}"


SIZE_UNITS: dict[str, int] = {
    "b": 1, "byte": 1, "bytes": 1,
    "k": 1024, "kb": 1024, "kilobyte": 1024, "kilobytes": 1024,
    "m": 1024 * 1024, "mb": 1024 * 1024, "megabyte": 1024 * 1024, "megabytes": 1024 * 1024,
    "g": 1024 * 1024 * 1024, "gb": 1024 * 1024 * 1024, "gigabyte": 1024 * 1024 * 1024, "gigabytes": 1024 * 1024 * 1024,
}


def parse_size_to_bytes(num_str: str, unit_str: str) -> Optional[int]:
    """Converts a number and unit string to total bytes."""
    try:
        val = float(num_str.strip())
        mult = SIZE_UNITS.get(unit_str.lower().strip(), 1)
        return int(val * mult)
    except Exception:
        return None


def extract_size_constraint(text: str) -> Tuple[Optional[SizeConstraint], str]:
    """Extracts size constraints (e.g. 'bigger than 20 MB but smaller than 200 MB', 'over 50 MB', 'under 1 GB').

    Returns (SizeConstraint, cleaned_text).
    """
    lowered = text.casefold()

    # 1. Bounded range: 'bigger than 20 MB but smaller than 200 MB', 'between 10 MB and 50 MB', 'from 10 MB to 100 MB', 'at least 1 GB and at most 4 GB'
    m_range = re.search(
        r"\b(?:bigger\s+than|larger\s+than|greater\s+than|more\s+than|over|above|at\s+least)\s+(?P<n1>\d+(?:\.\d+)?)\s*(?P<u1>[a-zA-Z]+)\s+"
        r"(?:but\s+|and\s+)?(?:smaller\s+than|less\s+than|under|below|at\s+most)\s+(?P<n2>\d+(?:\.\d+)?)\s*(?P<u2>[a-zA-Z]+)\b",
        lowered,
    )
    if m_range:
        min_b = parse_size_to_bytes(m_range.group("n1"), m_range.group("u1"))
        max_b = parse_size_to_bytes(m_range.group("n2"), m_range.group("u2"))
        if min_b is not None and max_b is not None:
            constraint = SizeConstraint(
                min_bytes=min_b,
                max_bytes=max_b,
                min_inclusive=False,
                max_inclusive=False,
                label=f">{m_range.group('n1')}{m_range.group('u1').upper()} and <{m_range.group('n2')}{m_range.group('u2').upper()}",
            )
            start, end = m_range.span()
            cleaned = re.sub(r"\s+", " ", f"{text[:start]} {text[end:]}").strip()
            return constraint, cleaned

    m_between = re.search(
        r"\b(?:between|from)\s+(?P<n1>\d+(?:\.\d+)?)\s*(?P<u1>[a-zA-Z]+)\s+(?:and|to)\s+(?P<n2>\d+(?:\.\d+)?)\s*(?P<u2>[a-zA-Z]+)\b",
        lowered,
    )
    if m_between:
        min_b = parse_size_to_bytes(m_between.group("n1"), m_between.group("u1"))
        max_b = parse_size_to_bytes(m_between.group("n2"), m_between.group("u2"))
        if min_b is not None and max_b is not None:
            constraint = SizeConstraint(
                min_bytes=min(min_b, max_b),
                max_bytes=max(min_b, max_b),
                min_inclusive=True,
                max_inclusive=True,
                label=f"Between {m_between.group('n1')}{m_between.group('u1').upper()} and {m_between.group('n2')}{m_between.group('u2').upper()}",
            )
            start, end = m_between.span()
            cleaned = re.sub(r"\s+", " ", f"{text[:start]} {text[end:]}").strip()
            return constraint, cleaned

    # 2. Lower bound only: 'bigger than 20 MB', 'at least 10 MB', 'over 5 MB', 'above 80 MB', 'exceeding 25 MB', 'minimum 30 MB'
    m_min = re.search(
        r"\b(?P<op>at\s+least|bigger\s+than|larger\s+than|greater\s+than|more\s+than|over|above|(?<!not\s)exceeding|minimum)\s+(?P<n>\d+(?:\.\d+)?)\s*(?P<u>[a-zA-Z]+)\b",
        lowered,
    )
    if m_min:
        b_val = parse_size_to_bytes(m_min.group("n"), m_min.group("u"))
        if b_val is not None:
            inclusive = "at least" in m_min.group("op") or "minimum" in m_min.group("op")
            constraint = SizeConstraint(
                min_bytes=b_val,
                min_inclusive=inclusive,
                label=f">{'=' if inclusive else ''}{m_min.group('n')}{m_min.group('u').upper()}",
            )
            start, end = m_min.span()
            cleaned = re.sub(r"\s+", " ", f"{text[:start]} {text[end:]}").strip()
            return constraint, cleaned

    # 3. Upper bound only: 'smaller than 200 MB', 'at most 50 MB', 'under 1 GB', 'below 5 MB', 'not exceeding 50 MB', 'maximum 200 MB'
    m_max = re.search(
        r"\b(?P<op>at\s+most|smaller\s+than|less\s+than|under|below|not\s+exceeding|maximum)\s+(?P<n>\d+(?:\.\d+)?)\s*(?P<u>[a-zA-Z]+)\b",
        lowered,
    )
    if m_max:
        b_val = parse_size_to_bytes(m_max.group("n"), m_max.group("u"))
        if b_val is not None:
            inclusive = "at most" in m_max.group("op") or "maximum" in m_max.group("op") or "not exceeding" in m_max.group("op")
            constraint = SizeConstraint(
                max_bytes=b_val,
                max_inclusive=inclusive,
                label=f"<{'=' if inclusive else ''}{m_max.group('n')}{m_max.group('u').upper()}",
            )
            start, end = m_max.span()
            cleaned = re.sub(r"\s+", " ", f"{text[:start]} {text[end:]}").strip()
            return constraint, cleaned

    return None, text
