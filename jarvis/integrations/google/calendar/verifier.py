"""Verification and reconciliation logic for Google Calendar mutations."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from jarvis.integrations.google.calendar.client import CalendarClient
from jarvis.integrations.google.calendar.models import CalendarEvent, EventDiff
from jarvis.tools.base import VerificationResult

logger = logging.getLogger("jarvis.integrations.google.calendar.verifier")


class CalendarVerifier:
    """Verifies calendar mutations against provider state."""

    @staticmethod
    def verify_create(
        client: CalendarClient,
        calendar_id: str,
        event_id: str,
        expected_summary: str,
    ) -> VerificationResult:
        """Verify that newly created event exists at provider with matching summary."""
        try:
            event = client.get_event(event_id, calendar_id=calendar_id)
            if not event:
                return VerificationResult(
                    verified=False,
                    evidence={"event_id": event_id, "calendar_id": calendar_id},
                    error=f"Event {event_id} was not found on calendar {calendar_id} after creation.",
                )

            if event.summary.strip().lower() != expected_summary.strip().lower():
                return VerificationResult(
                    verified=False,
                    evidence={"event_id": event_id, "provider_summary": event.summary},
                    error=f"Event summary mismatch: expected '{expected_summary}', got '{event.summary}'",
                )

            return VerificationResult(
                verified=True,
                evidence={
                    "event_id": event.event_id,
                    "calendar_id": event.calendar_id,
                    "summary": event.summary,
                    "start": event.start.display_str(),
                    "end": event.end.display_str(),
                    "status": event.status,
                },
                error=None,
            )
        except Exception as e:
            return VerificationResult(
                verified=False,
                evidence={"event_id": event_id},
                error=f"Verification failed with exception: {e}",
            )

    @staticmethod
    def verify_update(
        client: CalendarClient,
        calendar_id: str,
        event_id: str,
        diff: EventDiff,
    ) -> VerificationResult:
        """Verify that event was updated at provider with expected changes."""
        try:
            event = client.get_event(event_id, calendar_id=calendar_id)
            if not event:
                return VerificationResult(
                    verified=False,
                    evidence={"event_id": event_id},
                    error=f"Event {event_id} not found after update.",
                )

            if diff.summary_changed and diff.new_summary:
                if event.summary.strip().lower() != diff.new_summary.strip().lower():
                    return VerificationResult(
                        verified=False,
                        evidence={"event_id": event_id, "current_summary": event.summary},
                        error="Updated summary did not match expected value.",
                    )

            return VerificationResult(
                verified=True,
                evidence={
                    "event_id": event.event_id,
                    "updated_summary": event.summary,
                    "updated_start": event.start.display_str(),
                    "status": event.status,
                },
                error=None,
            )
        except Exception as e:
            return VerificationResult(
                verified=False,
                evidence={"event_id": event_id},
                error=f"Update verification error: {e}",
            )

    @staticmethod
    def verify_delete(
        client: CalendarClient,
        calendar_id: str,
        event_id: str,
    ) -> VerificationResult:
        """Verify that event has been removed or marked cancelled at provider."""
        try:
            event = client.get_event(event_id, calendar_id=calendar_id)
            if event is None or event.status == "cancelled":
                return VerificationResult(
                    verified=True,
                    evidence={"event_id": event_id, "deleted": True},
                    error=None,
                )

            return VerificationResult(
                verified=False,
                evidence={"event_id": event_id, "status": event.status},
                error=f"Event {event_id} still active after delete operation.",
            )
        except Exception as e:
            return VerificationResult(
                verified=False,
                evidence={"event_id": event_id},
                error=f"Delete verification error: {e}",
            )
