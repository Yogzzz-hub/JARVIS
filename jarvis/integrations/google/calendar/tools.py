"""Native typed tools for Google Calendar integration."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo
from pydantic import Field

from jarvis.integrations.google.auth.scopes import GoogleCapability, ScopeGuard
from jarvis.integrations.google.calendar.client import CalendarClient
from jarvis.integrations.google.calendar.models import (
    CalendarEvent,
    EventDateTime,
    EventDiff,
    compute_event_diff,
    parse_natural_time_range,
)
from jarvis.integrations.google.calendar.verifier import CalendarVerifier
from jarvis.tools.base import (
    Contract,
    ExecutionMethod,
    IdempotencyClass,
    RiskLevel,
    Tool,
    ToolDefinition,
    ToolResult,
    VerificationResult,
)

logger = logging.getLogger("jarvis.integrations.google.calendar.tools")


# ----------------- CONTRACTS -----------------

class CalendarListEventsInput(Contract):
    time_window: str = Field(default="today", description="Natural time expression: 'today', 'tomorrow', 'next week'")
    calendar_id: str = Field(default="primary", description="Calendar identifier")
    account_id: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=50)


class CalendarListEventsOutput(Contract):
    events: Tuple[CalendarEvent, ...]
    time_window: str
    count: int


class CalendarFindEventsInput(Contract):
    query: str = Field(min_length=1, max_length=256, description="Search term for event summary/description")
    calendar_id: str = Field(default="primary")
    account_id: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=50)


class CalendarFindEventsOutput(Contract):
    events: Tuple[CalendarEvent, ...]
    query: str
    count: int


class CalendarGetEventInput(Contract):
    event_id: str = Field(min_length=1, max_length=128)
    calendar_id: str = Field(default="primary")
    account_id: Optional[str] = None


class CalendarGetEventOutput(Contract):
    event: Optional[CalendarEvent] = None
    found: bool


class CalendarCreateEventInput(Contract):
    summary: str = Field(min_length=1, max_length=256, description="Event title")
    start_time: str = Field(description="ISO timestamp or date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)")
    end_time: Optional[str] = Field(default=None, description="Optional ISO timestamp or date")
    duration_minutes: int = Field(default=60, ge=5, le=1440, description="Default duration in minutes if end_time omitted")
    description: Optional[str] = None
    location: Optional[str] = None
    attendees: Tuple[str, ...] = Field(default_factory=tuple, description="Emails of attendees to invite")
    is_all_day: bool = False
    calendar_id: str = Field(default="primary")
    account_id: Optional[str] = None


class CalendarCreateEventOutput(Contract):
    created: bool
    event: Optional[CalendarEvent] = None
    confirmation_summary: str


class CalendarUpdateEventInput(Contract):
    event_id: str = Field(min_length=1, max_length=128)
    summary: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    description: Optional[str] = None
    attendees: Optional[Tuple[str, ...]] = None
    calendar_id: str = Field(default="primary")
    account_id: Optional[str] = None


class CalendarUpdateEventOutput(Contract):
    updated: bool
    event: Optional[CalendarEvent] = None
    diff_summary: str


class CalendarDeleteEventInput(Contract):
    event_id: str = Field(min_length=1, max_length=128)
    calendar_id: str = Field(default="primary")
    account_id: Optional[str] = None


class CalendarDeleteEventOutput(Contract):
    deleted: bool
    event_id: str


# ----------------- TOOLS -----------------

class CalendarListEventsTool(Tool):
    definition = ToolDefinition(
        name="calendar_list_events",
        description="List upcoming calendar events for a specific time window (e.g. 'today', 'tomorrow', 'next week').",
        input_model=CalendarListEventsInput,
        output_model=CalendarListEventsOutput,
        read_only=True,
        requires_confirmation=False,
        risk=RiskLevel.READ_ONLY,
        execution_method=ExecutionMethod.API,
        idempotency=IdempotencyClass.IDEMPOTENT,
        tags=("calendar", "google", "events", "list"),
    )

    def __init__(self, client: Optional[CalendarClient] = None) -> None:
        self._client = client

    def run(self, input_data: Any) -> ToolResult:
        if isinstance(input_data, dict):
            input_data = CalendarListEventsInput.model_validate(input_data)
        return self.execute(input_data)

    def execute(self, validated_input: CalendarListEventsInput) -> ToolResult:
        ScopeGuard.assert_capability(self._client.account_id if self._client else "default", GoogleCapability.CALENDAR_READ)
        if not self._client:
            return ToolResult(success=False, error="CalendarClient is not configured.", tool_name=self.definition.name)

        start_dt, end_dt = parse_natural_time_range(validated_input.time_window)
        events, _ = self._client.list_events(
            calendar_id=validated_input.calendar_id,
            time_min=start_dt.isoformat(),
            time_max=end_dt.isoformat(),
            max_results=validated_input.limit,
        )

        out = CalendarListEventsOutput(
            events=tuple(events),
            time_window=validated_input.time_window,
            count=len(events),
        )
        return ToolResult(success=True, data=out.model_dump(mode="json"), tool_name=self.definition.name)


class CalendarFindEventsTool(Tool):
    definition = ToolDefinition(
        name="calendar_find_events",
        description="Find calendar events by keyword search in title or description.",
        input_model=CalendarFindEventsInput,
        output_model=CalendarFindEventsOutput,
        read_only=True,
        requires_confirmation=False,
        risk=RiskLevel.READ_ONLY,
        execution_method=ExecutionMethod.API,
        idempotency=IdempotencyClass.IDEMPOTENT,
        tags=("calendar", "google", "events", "search"),
    )

    def __init__(self, client: Optional[CalendarClient] = None) -> None:
        self._client = client

    def run(self, input_data: Any) -> ToolResult:
        if isinstance(input_data, dict):
            input_data = CalendarFindEventsInput.model_validate(input_data)
        return self.execute(input_data)

    def execute(self, validated_input: CalendarFindEventsInput) -> ToolResult:
        ScopeGuard.assert_capability(self._client.account_id if self._client else "default", GoogleCapability.CALENDAR_READ)
        if not self._client:
            return ToolResult(success=False, error="CalendarClient is not configured.", tool_name=self.definition.name)

        events = self._client.find_events(
            query=validated_input.query,
            calendar_id=validated_input.calendar_id,
            limit=validated_input.limit,
        )

        out = CalendarFindEventsOutput(
            events=tuple(events),
            query=validated_input.query,
            count=len(events),
        )
        return ToolResult(success=True, data=out.model_dump(mode="json"), tool_name=self.definition.name)


class CalendarGetEventTool(Tool):
    definition = ToolDefinition(
        name="calendar_get_event",
        description="Retrieve full details for a specific calendar event by ID.",
        input_model=CalendarGetEventInput,
        output_model=CalendarGetEventOutput,
        read_only=True,
        requires_confirmation=False,
        risk=RiskLevel.READ_ONLY,
        execution_method=ExecutionMethod.API,
        idempotency=IdempotencyClass.IDEMPOTENT,
        tags=("calendar", "google", "event", "get"),
    )

    def __init__(self, client: Optional[CalendarClient] = None) -> None:
        self._client = client

    def run(self, input_data: Any) -> ToolResult:
        if isinstance(input_data, dict):
            input_data = CalendarGetEventInput.model_validate(input_data)
        return self.execute(input_data)

    def execute(self, validated_input: CalendarGetEventInput) -> ToolResult:
        ScopeGuard.assert_capability(self._client.account_id if self._client else "default", GoogleCapability.CALENDAR_READ)
        if not self._client:
            return ToolResult(success=False, error="CalendarClient is not configured.", tool_name=self.definition.name)

        event = self._client.get_event(validated_input.event_id, calendar_id=validated_input.calendar_id)
        out = CalendarGetEventOutput(event=event, found=event is not None)
        return ToolResult(success=True, data=out.model_dump(mode="json"), tool_name=self.definition.name)


class CalendarCreateEventTool(Tool):
    definition = ToolDefinition(
        name="calendar_create_event",
        description="Schedule a new event on Google Calendar. Requires Phase 5 policy confirmation.",
        input_model=CalendarCreateEventInput,
        output_model=CalendarCreateEventOutput,
        read_only=False,
        requires_confirmation=True,
        risk=RiskLevel.EXTERNAL_EFFECT,
        execution_method=ExecutionMethod.API,
        idempotency=IdempotencyClass.VERIFY_BEFORE_RETRY,
        tags=("calendar", "google", "create", "schedule"),
    )

    def __init__(self, client: Optional[CalendarClient] = None) -> None:
        self._client = client

    def human_confirmation_prompt(self, validated_input: CalendarCreateEventInput) -> str:
        attendees_text = ""
        if validated_input.attendees:
            attendees_text = f" with {', '.join(validated_input.attendees)}"
        return f"Create '{validated_input.summary}' starting {validated_input.start_time}{attendees_text}?"

    def run(self, input_data: Any) -> ToolResult:
        if isinstance(input_data, dict):
            input_data = CalendarCreateEventInput.model_validate(input_data)
        return self.execute(input_data)

    def execute(self, validated_input: CalendarCreateEventInput) -> ToolResult:
        ScopeGuard.assert_capability(self._client.account_id if self._client else "default", GoogleCapability.CALENDAR_WRITE)
        if not self._client:
            return ToolResult(success=False, error="CalendarClient is not configured.", tool_name=self.definition.name)

        # Compute start and end structures
        if validated_input.is_all_day:
            start_dict = {"date": validated_input.start_time.split("T")[0]}
            end_dict = {"date": validated_input.end_time.split("T")[0] if validated_input.end_time else start_dict["date"]}
        else:
            start_str = validated_input.start_time
            if "T" not in start_str:
                start_str = f"{start_str}T09:00:00Z"
            if validated_input.end_time:
                end_str = validated_input.end_time
            else:
                try:
                    dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    end_str = (dt + timedelta(minutes=validated_input.duration_minutes)).isoformat()
                except Exception:
                    end_str = start_str
            start_dict = {"dateTime": start_str}
            end_dict = {"dateTime": end_str}

        # Guard against accidental duplicates
        duplicate = self._client.check_duplicate(
            calendar_id=validated_input.calendar_id,
            summary=validated_input.summary,
            start_str=validated_input.start_time,
            end_str=end_dict.get("dateTime", end_dict.get("date", "")),
        )
        if duplicate:
            out = CalendarCreateEventOutput(
                created=False,
                event=duplicate,
                confirmation_summary=f"Event already exists: '{duplicate.summary}' on {duplicate.start.display_str()}",
            )
            return ToolResult(
                success=True,
                data=out.model_dump(mode="json"),
                evidence={"duplicate_detected": True, "event_id": duplicate.event_id},
                tool_name=self.definition.name,
            )

        event = self._client.create_event(
            summary=validated_input.summary,
            start=start_dict,
            end=end_dict,
            calendar_id=validated_input.calendar_id,
            description=validated_input.description,
            location=validated_input.location,
            attendees=list(validated_input.attendees),
        )

        # Verification step
        ver = CalendarVerifier.verify_create(
            client=self._client,
            calendar_id=validated_input.calendar_id,
            event_id=event.event_id,
            expected_summary=validated_input.summary,
        )

        out = CalendarCreateEventOutput(
            created=ver.verified,
            event=event,
            confirmation_summary=f"Created {event.summary_confirmation()}",
        )
        return ToolResult(
            success=ver.verified,
            data=out.model_dump(mode="json"),
            error=ver.error if not ver.verified else None,
            evidence=ver.evidence if ver.evidence else {},
            tool_name=self.definition.name,
        )


class CalendarUpdateEventTool(Tool):
    definition = ToolDefinition(
        name="calendar_update_event",
        description="Update fields of an existing calendar event. Requires Phase 5 policy confirmation.",
        input_model=CalendarUpdateEventInput,
        output_model=CalendarUpdateEventOutput,
        read_only=False,
        requires_confirmation=True,
        risk=RiskLevel.EXTERNAL_EFFECT,
        execution_method=ExecutionMethod.API,
        idempotency=IdempotencyClass.VERIFY_BEFORE_RETRY,
        tags=("calendar", "google", "update", "modify"),
    )

    def __init__(self, client: Optional[CalendarClient] = None) -> None:
        self._client = client

    def human_confirmation_prompt(self, validated_input: CalendarUpdateEventInput) -> str:
        if not self._client:
            return f"Update event {validated_input.event_id}?"
        existing = self._client.get_event(validated_input.event_id, calendar_id=validated_input.calendar_id)
        if not existing:
            return f"Update event {validated_input.event_id}?"
        updates: Dict[str, Any] = {}
        if validated_input.summary:
            updates["summary"] = validated_input.summary
        if validated_input.start_time:
            updates["start"] = validated_input.start_time
        if validated_input.end_time:
            updates["end"] = validated_input.end_time
        if validated_input.attendees is not None:
            updates["attendees"] = list(validated_input.attendees)
        diff = compute_event_diff(existing, updates)
        return diff.confirmation_text

    def run(self, input_data: Any) -> ToolResult:
        if isinstance(input_data, dict):
            input_data = CalendarUpdateEventInput.model_validate(input_data)
        return self.execute(input_data)

    def execute(self, validated_input: CalendarUpdateEventInput) -> ToolResult:
        ScopeGuard.assert_capability(self._client.account_id if self._client else "default", GoogleCapability.CALENDAR_WRITE)
        if not self._client:
            return ToolResult(success=False, error="CalendarClient is not configured.", tool_name=self.definition.name)

        existing = self._client.get_event(validated_input.event_id, calendar_id=validated_input.calendar_id)
        if not existing:
            return ToolResult(success=False, error=f"Event {validated_input.event_id} not found.", tool_name=self.definition.name)

        updates: Dict[str, Any] = {}
        if validated_input.summary:
            updates["summary"] = validated_input.summary
        if validated_input.description is not None:
            updates["description"] = validated_input.description
        if validated_input.start_time:
            if "T" in validated_input.start_time:
                updates["start"] = {"dateTime": validated_input.start_time}
            else:
                updates["start"] = {"date": validated_input.start_time}
        if validated_input.end_time:
            if "T" in validated_input.end_time:
                updates["end"] = {"dateTime": validated_input.end_time}
            else:
                updates["end"] = {"date": validated_input.end_time}
        if validated_input.attendees is not None:
            updates["attendees"] = [{"email": a.strip()} for a in validated_input.attendees if a.strip()]

        diff = compute_event_diff(existing, updates)
        updated_event = self._client.update_event(
            event_id=validated_input.event_id,
            updates=updates,
            calendar_id=validated_input.calendar_id,
        )

        ver = CalendarVerifier.verify_update(
            client=self._client,
            calendar_id=validated_input.calendar_id,
            event_id=validated_input.event_id,
            diff=diff,
        )

        out = CalendarUpdateEventOutput(
            updated=ver.verified,
            event=updated_event,
            diff_summary=diff.confirmation_text,
        )
        return ToolResult(
            success=ver.verified,
            data=out.model_dump(mode="json"),
            error=ver.error if not ver.verified else None,
            evidence=ver.evidence if ver.evidence else {},
            tool_name=self.definition.name,
        )


class CalendarDeleteEventTool(Tool):
    definition = ToolDefinition(
        name="calendar_delete_event",
        description="Delete a calendar event. Requires Phase 5 policy confirmation.",
        input_model=CalendarDeleteEventInput,
        output_model=CalendarDeleteEventOutput,
        read_only=False,
        requires_confirmation=True,
        risk=RiskLevel.DESTRUCTIVE,
        execution_method=ExecutionMethod.API,
        idempotency=IdempotencyClass.VERIFY_BEFORE_RETRY,
        tags=("calendar", "google", "delete"),
    )

    def __init__(self, client: Optional[CalendarClient] = None) -> None:
        self._client = client

    def human_confirmation_prompt(self, validated_input: CalendarDeleteEventInput) -> str:
        if self._client:
            existing = self._client.get_event(validated_input.event_id, calendar_id=validated_input.calendar_id)
            if existing:
                return f"Delete calendar event '{existing.summary}' on {existing.start.display_str()}?"
        return f"Delete calendar event {validated_input.event_id}?"

    def run(self, input_data: Any) -> ToolResult:
        if isinstance(input_data, dict):
            input_data = CalendarDeleteEventInput.model_validate(input_data)
        return self.execute(input_data)

    def execute(self, validated_input: CalendarDeleteEventInput) -> ToolResult:
        ScopeGuard.assert_capability(self._client.account_id if self._client else "default", GoogleCapability.CALENDAR_WRITE)
        if not self._client:
            return ToolResult(success=False, error="CalendarClient is not configured.", tool_name=self.definition.name)

        deleted = self._client.delete_event(validated_input.event_id, calendar_id=validated_input.calendar_id)
        ver = CalendarVerifier.verify_delete(
            client=self._client,
            calendar_id=validated_input.calendar_id,
            event_id=validated_input.event_id,
        )

        out = CalendarDeleteEventOutput(
            deleted=ver.verified,
            event_id=validated_input.event_id,
        )
        return ToolResult(
            success=ver.verified,
            data=out.model_dump(mode="json"),
            error=ver.error if not ver.verified else None,
            evidence=ver.evidence if ver.evidence else {},
            tool_name=self.definition.name,
        )
