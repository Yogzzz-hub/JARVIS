"""Gmail and Google Calendar as JARVIS actions ("any new emails", "am I free on friday afternoon",
"add dentist to my calendar for monday 10am"). They use the existing Google clients and the account connected with
``connect_google.bat`` / ``python -m jarvis.google connect``; without one they say how to connect."""
from __future__ import annotations

import asyncio
import re
from datetime import date, datetime, time, timedelta
from typing import Any, Optional

from pydantic import Field

from jarvis.tools.base import Contract, ExecutionMethod, IdempotencyClass, RiskLevel, Tool, ToolDefinition

NOT_CONNECTED = ("Google isn't connected yet. Run connect_google.bat (or \"python -m jarvis.google connect gmail\" / "
                 "\"... connect calendar\") once, then ask me again.")
_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_PARTS = {"morning": (6, 12), "afternoon": (12, 17), "evening": (17, 21), "night": (19, 24), "tonight": (17, 24)}


def _now() -> datetime:
    return datetime.now().astimezone()


def _day_of(expr: str, now: datetime) -> Optional[date]:
    today = now.date()
    if re.search(r"\bday after tomorrow\b", expr):
        return today + timedelta(days=2)
    if re.search(r"\btomorrow\b", expr):
        return today + timedelta(days=1)
    if re.search(r"\b(?:today|tonight)\b", expr):
        return today
    for i, name in enumerate(_WEEKDAYS):
        if re.search(rf"\b{name}\b", expr):
            ahead = (i - today.weekday()) % 7
            if ahead == 0 and re.search(r"\bnext\b", expr):
                ahead = 7
            return today + timedelta(days=ahead)
    return None


def time_range(expr: str, now: Optional[datetime] = None) -> tuple[datetime, datetime]:
    """'today', 'tomorrow', 'thursday evening', 'this week', 'next week', 'weekend' -> local start/end."""
    now = now or _now()
    tz = now.tzinfo
    e = (expr or "today").lower().strip()
    if "week" in e and "weekend" not in e:
        if "next" in e:
            start = now.date() + timedelta(days=(7 - now.weekday()) % 7 or 7)
            return datetime.combine(start, time(0), tz), datetime.combine(start + timedelta(days=6), time(23, 59, 59), tz)
        return now, datetime.combine(now.date() + timedelta(days=6 - now.weekday()), time(23, 59, 59), tz)
    if "weekend" in e:
        sat = now.date() + timedelta(days=(5 - now.weekday()) % 7)
        return datetime.combine(sat, time(0), tz), datetime.combine(sat + timedelta(days=1), time(23, 59, 59), tz)
    day = _day_of(e, now) or now.date()
    part = next((p for p in _PARTS if re.search(rf"\b{p}\b", e)), None)
    lo, hi = _PARTS[part] if part else (0, 24)
    start = datetime.combine(day, time(lo), tz)
    end = datetime.combine(day, time(23, 59, 59), tz) if hi == 24 else datetime.combine(day, time(hi), tz)
    return max(start, now) if day == now.date() and not part else start, end


def parse_when(expr: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """'tomorrow at 4', 'monday 10am', 'friday at 3:30 pm', 'at 5' -> a local datetime (None when no time is given)."""
    now = now or _now()
    e = (expr or "").lower()
    m = re.search(r"\b(?:at\s+)?(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?\b", e)
    if not m or (not m.group(3) and not re.search(r"\bat\s+\d", e) and not m.group(2)):
        return None
    hour, minute = int(m.group(1)), int(m.group(2) or 0)
    ampm = (m.group(3) or "").replace(".", "")
    if hour > 23 or minute > 59:
        return None
    if ampm == "pm" and hour < 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    elif not ampm and 1 <= hour <= 7:
        hour += 12  # "at 4" means the afternoon
    day = _day_of(e, now) or now.date()
    when = datetime.combine(day, time(hour, minute), now.tzinfo)
    if when < now and not _day_of(e, now):
        when += timedelta(days=1)
    return when


async def _credentials(capability: Any) -> Any:
    from jarvis.integrations.google.auth.manager import get_global_auth_manager
    try:
        return await get_global_auth_manager().get_credentials(None, required_capability=capability)
    except Exception as exc:
        raise RuntimeError(NOT_CONNECTED) from exc


# ---------------------------------------------------------------- Gmail

class MailListInput(Contract):
    limit: int = Field(default=5, ge=1, le=20)
    unread_only: bool = False
    sender: str = Field(default="", max_length=120)


class GoogleResultOutput(Contract):
    message: str
    count: int = 0
    items: list[dict] = Field(default_factory=list)


class MailListTool(Tool):
    definition = ToolDefinition(
        name="gmail_list_recent", description="Read the latest emails in the Gmail inbox (optionally unread / from someone).",
        input_model=MailListInput, output_model=GoogleResultOutput, read_only=True, risk=RiskLevel.READ_ONLY,
        execution_method=ExecutionMethod.API, idempotency=IdempotencyClass.IDEMPOTENT, timeout_s=30.0,
        tags=("gmail", "email", "google"))

    def __init__(self, client: Any = None) -> None:
        self._client = client

    async def run(self, arguments: MailListInput) -> dict:
        if isinstance(arguments, dict):
            arguments = MailListInput.model_validate(arguments)
        client = self._client
        if client is None:
            from jarvis.integrations.google.auth.scopes import GoogleCapability
            from jarvis.integrations.google.gmail.client import GmailClient
            await _credentials(GoogleCapability.GMAIL_READ)
            client = GmailClient()
        query = "in:inbox" + (" is:unread" if arguments.unread_only else "") + (f" from:{arguments.sender}" if arguments.sender else "")
        page = await client.search_messages(query=query, limit=arguments.limit)
        mails = list(page.items)
        items = [{"from": m.from_name or m.from_address, "subject": m.subject, "snippet": m.snippet[:160]} for m in mails]
        if not items:
            return {"message": "No new emails." if arguments.unread_only else "Your inbox is empty.", "count": 0, "items": []}
        lines = "; ".join(f"{i['from']}: {i['subject']}" for i in items)
        kind = "unread emails" if arguments.unread_only else "latest emails"
        return {"message": f"Your {len(items)} {kind}: {lines}.", "count": len(items), "items": items}


# ---------------------------------------------------------------- Calendar

class EventsInput(Contract):
    time_window: str = Field(default="today", max_length=80)
    limit: int = Field(default=10, ge=1, le=50)


class EventCreateInput(Contract):
    summary: str = Field(min_length=1, max_length=256)
    when: str = Field(min_length=1, max_length=120, description="'tomorrow at 4', 'monday 10am'")
    duration_minutes: int = Field(default=60, ge=5, le=1440)


def _calendar_client(creds: Any) -> Any:
    from googleapiclient.discovery import build

    from jarvis.integrations.google.calendar.client import CalendarClient
    return CalendarClient(build("calendar", "v3", credentials=creds, cache_discovery=False),
                          account_id=getattr(creds, "account_id", "default"))


def _event_time(ev: Any) -> str:
    raw = getattr(ev.start, "date_time", None) or getattr(ev.start, "date", None) or ""
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone().strftime("%a %I:%M %p").replace(" 0", " ")
    except Exception:
        return str(raw)


class EventsListTool(Tool):
    definition = ToolDefinition(
        name="calendar_list_events", description="List Google Calendar events for today, tomorrow, a weekday (and part of day) or a week.",
        input_model=EventsInput, output_model=GoogleResultOutput, read_only=True, risk=RiskLevel.READ_ONLY,
        execution_method=ExecutionMethod.API, idempotency=IdempotencyClass.IDEMPOTENT, timeout_s=30.0,
        tags=("calendar", "google", "events"))

    def __init__(self, client: Any = None) -> None:
        self._client = client

    async def run(self, arguments: EventsInput) -> dict:
        if isinstance(arguments, dict):
            arguments = EventsInput.model_validate(arguments)
        client = self._client
        if client is None:
            from jarvis.integrations.google.auth.scopes import GoogleCapability
            client = _calendar_client(await _credentials(GoogleCapability.CALENDAR_READ))
        start, end = time_range(arguments.time_window)
        events, _ = await asyncio.to_thread(client.list_events, calendar_id="primary", time_min=start.isoformat(),
                                            time_max=end.isoformat(), max_results=arguments.limit)
        window = arguments.time_window or "today"
        if not events:
            return {"message": f"You're free {window} - nothing on your calendar.", "count": 0, "items": []}
        items = [{"summary": ev.summary, "start": _event_time(ev), "location": ev.location or ""} for ev in events]
        lines = "; ".join(f"{i['start']} {i['summary']}" for i in items)
        return {"message": f"{len(items)} on your calendar {window}: {lines}.", "count": len(items), "items": items}


class EventCreateTool(Tool):
    definition = ToolDefinition(
        name="calendar_create_event", description="Add an event to Google Calendar ('dentist tomorrow at 4'). Asks first.",
        input_model=EventCreateInput, output_model=GoogleResultOutput, read_only=False, requires_confirmation=True,
        risk=RiskLevel.REVERSIBLE, execution_method=ExecutionMethod.API, idempotency=IdempotencyClass.VERIFY_BEFORE_RETRY,
        timeout_s=30.0, tags=("calendar", "google", "create"))

    def __init__(self, client: Any = None) -> None:
        self._client = client

    async def run(self, arguments: EventCreateInput) -> dict:
        if isinstance(arguments, dict):
            arguments = EventCreateInput.model_validate(arguments)
        start = parse_when(arguments.when)
        if start is None:
            raise ValueError(f"What time should '{arguments.summary}' be? For example 'tomorrow at 4 pm'.")
        client = self._client
        if client is None:
            from jarvis.integrations.google.auth.scopes import GoogleCapability
            client = _calendar_client(await _credentials(GoogleCapability.CALENDAR_WRITE))
        end = start + timedelta(minutes=arguments.duration_minutes)
        ev = await asyncio.to_thread(client.create_event, summary=arguments.summary,
                                     start={"dateTime": start.isoformat()}, end={"dateTime": end.isoformat()})
        when = start.strftime("%A %I:%M %p").replace(" 0", " ")
        return {"message": f"Added '{ev.summary}' to your calendar for {when}.", "count": 1,
                "items": [{"summary": ev.summary, "start": start.isoformat()}]}


def create_google_tools() -> list[Tool]:
    return [MailListTool(), EventsListTool(), EventCreateTool()]
