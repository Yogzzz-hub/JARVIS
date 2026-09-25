"""Everyday assistant tools: open websites and time-based reminders.

Reminders persist to ``data/reminders.json`` and are fired by the runtime's reminder loop,
which speaks them, shows them in the UI and (when configured) pushes them to the phone.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic import Field

from jarvis.config import ROOT
from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition

logger = logging.getLogger("jarvis.tools.assistant")

# ============================================================================ websites


class OpenWebsiteInput(Contract):
    url: str = Field(min_length=3, max_length=2048, description="Web address or search URL to open")
    title: str = Field(default="", max_length=200, description="Optional human description of the page")


class OpenWebsiteOutput(Contract):
    url: str
    title: str
    opened: bool
    message: str


def normalize_url(url: str) -> str:
    url = url.strip().strip('"\'')
    if not re.match(r"^[a-z][a-z0-9+.-]*://", url, re.I):
        url = "https://" + url
    if not re.match(r"^https?://[^\s/$.?#].[^\s]*$", url, re.I):
        raise ValueError(f"Not a valid web address: {url}")
    return url


class OpenWebsiteTool(Tool):
    definition = ToolDefinition(
        name="open_website",
        description="Opens a website or web search results page in the user's default browser (e.g. an Amazon, Google or YouTube search URL).",
        input_model=OpenWebsiteInput,
        output_model=OpenWebsiteOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=15.0,
        tags=("web", "browser", "url", "website", "search"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def __init__(self, opener: Optional[Callable[[str], Any]] = None) -> None:
        self.opener = opener

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = OpenWebsiteInput(**arguments)
        url = normalize_url(arguments.url)
        if self.opener is not None:
            self.opener(url)
        elif sys.platform == "win32":
            os.startfile(url)  # type: ignore[attr-defined]  # default browser, no console window
        else:
            if not webbrowser.open(url):
                subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        label = arguments.title or re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
        return {"url": url, "title": arguments.title, "opened": True, "message": f"Opened {label}."}


# ============================================================================ reminders

_UNITS = {
    "second": 1, "seconds": 1, "sec": 1, "secs": 1,
    "minute": 60, "minutes": 60, "min": 60, "mins": 60,
    "hour": 3600, "hours": 3600, "hr": 3600, "hrs": 3600,
    "day": 86400, "days": 86400, "week": 604800, "weeks": 604800,
}
_WORD_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "forty five": 45, "sixty": 60,
    "couple of": 2, "few": 3,
}


def parse_reminder(text: str, now: datetime | None = None) -> tuple[str, Optional[datetime]]:
    """Split 'drink water in 10 minutes' into ('drink water', now+10m). Returns (task, due or None)."""
    now = now or datetime.now()
    body = " " + re.sub(r"\s+", " ", text.strip()) + " "
    due: Optional[datetime] = None

    def cut(match: re.Match) -> None:
        nonlocal body
        body = body[: match.start()] + " " + body[match.end():]

    m = re.search(r"\bin\s+half\s+an?\s+hour\b", body, re.I)
    if m:
        due = now + timedelta(minutes=30)
        cut(m)
    if due is None:
        num_words = "|".join(sorted((re.escape(w) for w in _WORD_NUMBERS), key=len, reverse=True))
        m = re.search(rf"\b(?:in|after)\s+(?P<n>\d+(?:\.\d+)?|{num_words})\s+(?P<u>{'|'.join(_UNITS)})\b", body, re.I)
        if m:
            raw_n = m.group("n").lower()
            n = float(raw_n) if raw_n[0].isdigit() else _WORD_NUMBERS[raw_n]
            due = now + timedelta(seconds=n * _UNITS[m.group("u").lower()])
            cut(m)
    if due is None:
        day = now
        m_day = re.search(r"\b(tomorrow|tonight|this evening|this afternoon|in the morning|tomorrow morning|tomorrow evening)\b", body, re.I)
        default_hour = None
        if m_day:
            word = m_day.group(1).lower()
            if word.startswith("tomorrow"):
                day = now + timedelta(days=1)
            default_hour = {"tonight": 20, "this evening": 18, "this afternoon": 15, "in the morning": 9,
                            "tomorrow morning": 9, "tomorrow evening": 18, "tomorrow": 9}[word]
            cut(m_day)
        m = re.search(r"\bat\s+(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ap>a\.?m\.?|p\.?m\.?)?(?=\s|$)", body, re.I)
        if m:
            hour, minute = int(m.group("h")), int(m.group("m") or 0)
            ap = (m.group("ap") or "").lower().replace(".", "")
            if ap == "pm" and hour < 12:
                hour += 12
            elif ap == "am" and hour == 12:
                hour = 0
            elif not ap and hour < 8 and default_hour is None:
                hour += 12  # "at 5" usually means 5 pm
            if 0 <= hour < 24 and 0 <= minute < 60:
                due = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if due <= now and not m_day:
                    due += timedelta(days=1)
                cut(m)
        elif default_hour is not None:
            due = day.replace(hour=default_hour, minute=0, second=0, microsecond=0)
            if due <= now:
                due += timedelta(days=1)
    task = re.sub(r"\s+", " ", body).strip(" ,.")
    task = re.sub(r"^(?:to|that|about)\s+", "", task, flags=re.I)
    return task or text.strip(), due


@dataclass
class Reminder:
    id: str
    text: str
    due: Optional[float]
    created: float = field(default_factory=time.time)
    fired: bool = False
    source: str = "local"


class ReminderService:
    def __init__(self, path: Path | None = None):
        self.path = path or (ROOT / "data" / "reminders.json")
        self._lock = threading.Lock()
        self._items: list[Reminder] = []
        self._load()

    def _load(self) -> None:
        try:
            if self.path.exists():
                self._items = [Reminder(**r) for r in json.loads(self.path.read_text(encoding="utf-8"))]
        except Exception as exc:
            logger.warning("Could not load reminders: %s", exc)
            self._items = []

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps([asdict(r) for r in self._items[-500:]], indent=1), encoding="utf-8")
            tmp.replace(self.path)
        except Exception as exc:
            logger.warning("Could not save reminders: %s", exc)

    def add(self, text: str, due: Optional[datetime], source: str = "local") -> Reminder:
        reminder = Reminder(id=f"rem_{uuid.uuid4().hex[:8]}", text=text, due=due.timestamp() if due else None, source=source)
        with self._lock:
            self._items.append(reminder)
            self._save()
        return reminder

    def pending(self) -> list[Reminder]:
        with self._lock:
            return sorted((r for r in self._items if not r.fired), key=lambda r: r.due or float("inf"))

    def pop_due(self, now: float | None = None) -> list[Reminder]:
        now = now or time.time()
        with self._lock:
            due = [r for r in self._items if not r.fired and r.due is not None and r.due <= now]
            for r in due:
                r.fired = True
            if due:
                self._save()
        return due

    def cancel(self, reminder_id: str) -> bool:
        with self._lock:
            for r in self._items:
                if r.id == reminder_id and not r.fired:
                    r.fired = True
                    self._save()
                    return True
        return False


_service: ReminderService | None = None


def get_reminder_service() -> ReminderService:
    global _service
    if _service is None:
        _service = ReminderService()
    return _service


def set_reminder_service(service: ReminderService | None) -> None:
    global _service
    _service = service


def describe_due(due: Optional[datetime], now: datetime | None = None) -> str:
    if due is None:
        return "with no time set"
    now = now or datetime.now()
    delta = (due - now).total_seconds()
    if delta <= 3660:
        mins = max(1, round(delta / 60))
        return f"in {mins} minute{'s' if mins != 1 else ''}"
    when = due.strftime("%I:%M %p").lstrip("0")
    if due.date() == now.date():
        return f"at {when}"
    if due.date() == (now + timedelta(days=1)).date():
        return f"tomorrow at {when}"
    return due.strftime("on %A %d %B at ") + when


class SetReminderInput(Contract):
    text: str = Field(min_length=1, max_length=500, description="What to remind about, including the time, e.g. 'call mom at 6 pm'")


class ReminderOutput(Contract):
    reminder_id: str
    text: str
    due_iso: str
    message: str


class SetReminderTool(Tool):
    definition = ToolDefinition(
        name="set_reminder",
        description="Sets a reminder that JARVIS will speak and show (and push to the phone) at the given time, e.g. 'drink water in 20 minutes', 'call mom at 6 pm', 'submit the report tomorrow at 10'.",
        input_model=SetReminderInput,
        output_model=ReminderOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=5.0,
        tags=("reminder", "timer", "alarm", "schedule", "productivity"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = SetReminderInput(**arguments)
        task, due = parse_reminder(arguments.text)
        if arguments.text.lower().startswith("timer:") and due is not None:
            span = arguments.text.split(":", 1)[1].strip()
            span = span[3:] if span.lower().startswith("in ") else span
            reminder = get_reminder_service().add(f"your {span} timer is done", due)
            return {"reminder_id": reminder.id, "text": reminder.text, "due_iso": due.isoformat(timespec="seconds"),
                    "message": f"Timer set for {span}."}
        reminder = get_reminder_service().add(task, due)
        when = describe_due(due)
        message = f"Okay, I'll remind you to {task} {when}." if due else f"Saved '{task}' to your reminders. Tell me a time if you want an alert."
        return {"reminder_id": reminder.id, "text": task, "due_iso": due.isoformat(timespec="minutes") if due else "", "message": message}


class ListRemindersInput(Contract):
    pass


class ListRemindersOutput(Contract):
    count: int
    reminders: list[dict]
    message: str


class ListRemindersTool(Tool):
    definition = ToolDefinition(
        name="list_reminders",
        description="Lists pending reminders and when they are due.",
        input_model=ListRemindersInput,
        output_model=ListRemindersOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=5.0,
        tags=("reminder", "schedule"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        items = get_reminder_service().pending()
        rows = [{"id": r.id, "text": r.text, "due": datetime.fromtimestamp(r.due).isoformat(timespec="minutes") if r.due else ""} for r in items]
        if not items:
            msg = "You have no pending reminders."
        else:
            parts = [f"{r.text} {describe_due(datetime.fromtimestamp(r.due) if r.due else None)}" for r in items[:3]]
            msg = f"You have {len(items)} reminder{'s' if len(items) != 1 else ''}: " + "; ".join(parts) + "."
        return {"count": len(items), "reminders": rows, "message": msg}


def create_assistant_tools() -> list[Tool]:
    return [OpenWebsiteTool(), SetReminderTool(), ListRemindersTool()]
