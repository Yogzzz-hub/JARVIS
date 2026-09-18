"""Data models for Google Calendar integration."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import re
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field


class EventDateTime(BaseModel):
    """Encapsulates start/end time supporting both timed and all-day events."""
    date: Optional[str] = Field(default=None, description="YYYY-MM-DD for all-day events")
    date_time: Optional[str] = Field(default=None, description="RFC3339 timestamp for timed events")
    time_zone: Optional[str] = Field(default=None, description="IANA timezone name")

    @property
    def is_all_day(self) -> bool:
        return self.date is not None and self.date_time is None

    def display_str(self) -> str:
        if self.is_all_day:
            return f"{self.date} (All day)"
        if self.date_time:
            # Short clean display
            return self.date_time.replace("T", " ").split("+")[0].split("Z")[0]
        return "Unknown"


class Attendee(BaseModel):
    """Calendar event attendee."""
    email: str
    display_name: Optional[str] = None
    response_status: Optional[str] = None  # needsAction, declined, tentative, accepted


class CalendarEvent(BaseModel):
    """Normalized Google Calendar event model."""
    event_id: str
    calendar_id: str = "primary"
    summary: str
    description: Optional[str] = None
    start: EventDateTime
    end: EventDateTime
    location: Optional[str] = None
    attendees: Tuple[Attendee, ...] = Field(default_factory=tuple)
    html_link: Optional[str] = None
    status: str = "confirmed"

    def summary_confirmation(self) -> str:
        attendees_str = ""
        if self.attendees:
            emails = [a.email for a in self.attendees]
            attendees_str = f" with {', '.join(emails)}"
        return f"'{self.summary}' on {self.start.display_str()} to {self.end.display_str()}{attendees_str}"


class EventDiff(BaseModel):
    """Deterministic diff between original and updated event."""
    summary_changed: bool = False
    old_summary: Optional[str] = None
    new_summary: Optional[str] = None
    time_changed: bool = False
    old_start: Optional[str] = None
    new_start: Optional[str] = None
    old_end: Optional[str] = None
    new_end: Optional[str] = None
    attendees_added: Tuple[str, ...] = Field(default_factory=tuple)
    attendees_removed: Tuple[str, ...] = Field(default_factory=tuple)
    confirmation_text: str = ""


def compute_event_diff(original: CalendarEvent, updates: Dict[str, Any]) -> EventDiff:
    """Computes a precise human-readable diff for calendar event updates."""
    diff = EventDiff()
    changes: List[str] = []

    if "summary" in updates and updates["summary"] != original.summary:
        diff.summary_changed = True
        diff.old_summary = original.summary
        diff.new_summary = updates["summary"]
        changes.append(f"title from '{original.summary}' to '{updates['summary']}'")

    if "start" in updates:
        diff.time_changed = True
        diff.old_start = original.start.display_str()
        diff.new_start = updates["start"] if isinstance(updates["start"], str) else str(updates["start"])
        changes.append(f"start from {diff.old_start} to {diff.new_start}")

    if "end" in updates:
        diff.time_changed = True
        diff.old_end = original.end.display_str()
        diff.new_end = updates["end"] if isinstance(updates["end"], str) else str(updates["end"])
        changes.append(f"end to {diff.new_end}")

    if "attendees" in updates:
        orig_emails = {a.email.lower() for a in original.attendees}
        new_emails = {e.lower() if isinstance(e, str) else e.get("email", "").lower() for e in updates["attendees"]}
        added = tuple(sorted(list(new_emails - orig_emails)))
        removed = tuple(sorted(list(orig_emails - new_emails)))
        if added:
            diff.attendees_added = added
            changes.append(f"add attendees: {', '.join(added)}")
        if removed:
            diff.attendees_removed = removed
            changes.append(f"remove attendees: {', '.join(removed)}")

    if not changes:
        diff.confirmation_text = f"Update '{original.summary}' (no major fields changed)"
    else:
        diff.confirmation_text = f"Update '{original.summary}': {'; '.join(changes)}"

    return diff


def parse_natural_time_range(
    expression: str,
    base_tz_name: str = "UTC",
    reference_dt: Optional[datetime] = None,
) -> Tuple[datetime, datetime]:
    """
    Deterministic natural date / time expression parser.
    Parses 'today', 'tomorrow', 'next week', 'next monday', etc.
    Avoids LLM hallucination for standard calendar ranges.
    """
    try:
        tz = ZoneInfo(base_tz_name)
    except Exception:
        tz = ZoneInfo("UTC")

    now = reference_dt if reference_dt else datetime.now(tz)
    expr = expression.strip().lower()

    if expr in ("today", ""):
        start = datetime.combine(now.date(), time(0, 0, 0), tzinfo=tz)
        end = datetime.combine(now.date(), time(23, 59, 59), tzinfo=tz)
        return start, end

    if expr == "tomorrow":
        t_date = now.date() + timedelta(days=1)
        start = datetime.combine(t_date, time(0, 0, 0), tzinfo=tz)
        end = datetime.combine(t_date, time(23, 59, 59), tzinfo=tz)
        return start, end

    if expr in ("this week", "next 7 days"):
        start = datetime.combine(now.date(), time(0, 0, 0), tzinfo=tz)
        end = datetime.combine(now.date() + timedelta(days=7), time(23, 59, 59), tzinfo=tz)
        return start, end

    if expr == "next week":
        days_until_next_mon = (7 - now.weekday()) % 7 or 7
        next_mon = now.date() + timedelta(days=days_until_next_mon)
        start = datetime.combine(next_mon, time(0, 0, 0), tzinfo=tz)
        end = datetime.combine(next_mon + timedelta(days=6), time(23, 59, 59), tzinfo=tz)
        return start, end

    # Fallback to next 24 hours
    start = now
    end = now + timedelta(days=1)
    return start, end
