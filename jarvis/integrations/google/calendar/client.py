"""Client for Google Calendar API operations."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from jarvis.integrations.google.calendar.models import (
    Attendee,
    CalendarEvent,
    EventDateTime,
)
from jarvis.integrations.google.common.cache import get_connector_cache
from jarvis.integrations.google.common.errors import (
    GoogleErrorCode,
    GoogleProviderError,
    normalize_google_error,
)
from jarvis.integrations.google.common.retry import execute_with_retry

logger = logging.getLogger("jarvis.integrations.google.calendar.client")


class CalendarClient:
    """Wrapper around Google Calendar API v3."""

    def __init__(self, service: Any, account_id: str = "default") -> None:
        self.service = service
        self.account_id = account_id
        self._cache = get_connector_cache()

    def _normalize_event(self, raw: Dict[str, Any], calendar_id: str = "primary") -> CalendarEvent:
        """Parse raw Google Calendar API JSON event into typed CalendarEvent."""
        raw_start = raw.get("start", {})
        start = EventDateTime(
            date=raw_start.get("date"),
            date_time=raw_start.get("dateTime"),
            time_zone=raw_start.get("timeZone"),
        )
        raw_end = raw.get("end", {})
        end = EventDateTime(
            date=raw_end.get("date"),
            date_time=raw_end.get("dateTime"),
            time_zone=raw_end.get("timeZone"),
        )
        raw_attendees = raw.get("attendees", [])
        attendees = tuple(
            Attendee(
                email=att.get("email", ""),
                display_name=att.get("displayName"),
                response_status=att.get("responseStatus"),
            )
            for att in raw_attendees
            if att.get("email")
        )

        return CalendarEvent(
            event_id=raw.get("id", ""),
            calendar_id=calendar_id,
            summary=raw.get("summary", "(No title)"),
            description=raw.get("description"),
            start=start,
            end=end,
            location=raw.get("location"),
            attendees=attendees,
            html_link=raw.get("htmlLink"),
            status=raw.get("status", "confirmed"),
        )

    def list_events(
        self,
        calendar_id: str = "primary",
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 10,
        page_token: Optional[str] = None,
        single_events: bool = True,
    ) -> Tuple[List[CalendarEvent], Optional[str]]:
        """List upcoming events within an optional time window."""
        cache_key = f"cal:list:{self.account_id}:{calendar_id}:{time_min}:{time_max}:{max_results}:{page_token}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        def _call() -> Dict[str, Any]:
            req = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=min(max_results, 50),
                pageToken=page_token,
                singleEvents=single_events,
                orderBy="startTime" if single_events else None,
            )
            return req.execute()

        try:
            res = execute_with_retry(_call, operation_name="calendar_list_events", is_write=False)
        except Exception as e:
            raise normalize_google_error(e, "calendar_list_events") from e

        items = res.get("items", [])
        events = [self._normalize_event(item, calendar_id) for item in items]
        next_page = res.get("nextPageToken")
        result = (events, next_page)
        self._cache.set(cache_key, result, ttl_seconds=60)
        return result

    def find_events(
        self,
        query: str,
        calendar_id: str = "primary",
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        limit: int = 10,
    ) -> List[CalendarEvent]:
        """Free-text search across calendar events."""
        def _call() -> Dict[str, Any]:
            req = self.service.events().list(
                calendarId=calendar_id,
                q=query,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=min(limit, 25),
                singleEvents=True,
                orderBy="startTime",
            )
            return req.execute()

        try:
            res = execute_with_retry(_call, operation_name="calendar_find_events", is_write=False)
        except Exception as e:
            raise normalize_google_error(e, "calendar_find_events") from e

        items = res.get("items", [])
        return [self._normalize_event(item, calendar_id) for item in items]

    def get_event(self, event_id: str, calendar_id: str = "primary") -> Optional[CalendarEvent]:
        """Fetch a single event by ID."""
        cache_key = f"cal:event:{self.account_id}:{calendar_id}:{event_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        def _call() -> Dict[str, Any]:
            req = self.service.events().get(calendarId=calendar_id, eventId=event_id)
            return req.execute()

        try:
            res = execute_with_retry(_call, operation_name="calendar_get_event", is_write=False)
        except GoogleProviderError as gpe:
            if gpe.code == GoogleErrorCode.NOT_FOUND:
                return None
            raise
        except Exception as e:
            err = normalize_google_error(e, "calendar_get_event")
            if err.code == GoogleErrorCode.NOT_FOUND:
                return None
            raise err from e

        event = self._normalize_event(res, calendar_id)
        self._cache.set(cache_key, event, ttl_seconds=120)
        return event

    def check_duplicate(
        self,
        summary: str,
        start_str: str,
        end_str: str,
        calendar_id: str = "primary",
    ) -> Optional[CalendarEvent]:
        """Check if an identical event already exists to prevent duplication."""
        # Find events around this summary
        existing = self.find_events(query=summary, calendar_id=calendar_id, limit=5)
        for ev in existing:
            if ev.summary.strip().lower() == summary.strip().lower():
                ev_start = ev.start.date if ev.start.is_all_day else ev.start.date_time
                if ev_start and (start_str in ev_start or ev_start in start_str):
                    return ev
        return None

    def create_event(
        self,
        summary: str,
        start: Dict[str, str],
        end: Dict[str, str],
        calendar_id: str = "primary",
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[str]] = None,
    ) -> CalendarEvent:
        """Create a new calendar event. External write operation."""
        body: Dict[str, Any] = {
            "summary": summary,
            "start": start,
            "end": end,
        }
        if description:
            body["description"] = description
        if location:
            body["location"] = location
        if attendees:
            body["attendees"] = [{"email": a.strip()} for a in attendees if a.strip()]

        def _call() -> Dict[str, Any]:
            req = self.service.events().insert(calendarId=calendar_id, body=body)
            return req.execute()

        try:
            res = execute_with_retry(_call, operation_name="calendar_create_event", is_write=True)
        except Exception as e:
            raise normalize_google_error(e, "calendar_create_event") from e

        # Invalidate event list caches
        self._cache.invalidate_prefix(f"cal:list:{self.account_id}:{calendar_id}")
        return self._normalize_event(res, calendar_id)

    def update_event(
        self,
        event_id: str,
        updates: Dict[str, Any],
        calendar_id: str = "primary",
    ) -> CalendarEvent:
        """Update existing event. External write operation."""
        def _call() -> Dict[str, Any]:
            req = self.service.events().patch(calendarId=calendar_id, eventId=event_id, body=updates)
            return req.execute()

        try:
            res = execute_with_retry(_call, operation_name="calendar_update_event", is_write=True)
        except Exception as e:
            raise normalize_google_error(e, "calendar_update_event") from e

        self._cache.invalidate(f"cal:event:{self.account_id}:{calendar_id}:{event_id}")
        self._cache.invalidate_prefix(f"cal:list:{self.account_id}:{calendar_id}")
        return self._normalize_event(res, calendar_id)

    def delete_event(self, event_id: str, calendar_id: str = "primary") -> bool:
        """Delete an event. Destructive external write operation."""
        def _call() -> None:
            req = self.service.events().delete(calendarId=calendar_id, eventId=event_id)
            req.execute()

        try:
            execute_with_retry(_call, operation_name="calendar_delete_event", is_write=True)
        except Exception as e:
            raise normalize_google_error(e, "calendar_delete_event") from e

        self._cache.invalidate(f"cal:event:{self.account_id}:{calendar_id}:{event_id}")
        self._cache.invalidate_prefix(f"cal:list:{self.account_id}:{calendar_id}")
        return True
