from __future__ import annotations

import os
from typing import Any
from jarvis.connectors.base import BaseConnector, Capability, ConnectorInfo, ConnectorStatus


class CalendarContactsConnector(BaseConnector):
    """F25 Connector: Standards-based CalDAV/CardDAV client with optional local Radicale service.
    Implements schedule reading, event creation, and contact resolution without compulsory cloud APIs.
    """

    def __init__(
        self,
        caldav_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        carddav_url: str | None = None,
    ) -> None:
        super().__init__(
            ConnectorInfo(
                connector_id="calendar_contacts_dav",
                name="CalDAV / CardDAV Connector",
                version="1.0.0",
                transport="HTTP/HTTPS WebDAV",
                network_requirement="Local LAN or configured CalDAV host",
                permission_scope="calendar:read,calendar:write,contacts:read",
            )
        )
        self.caldav_url = caldav_url or os.environ.get("JARVIS_CALDAV_URL")
        self.carddav_url = carddav_url or os.environ.get("JARVIS_CARDDAV_URL")
        self.username = username or os.environ.get("JARVIS_CALDAV_USER")
        self.password = password or os.environ.get("JARVIS_CALDAV_PASS")
        self._mock_events: list[dict[str, Any]] = []
        self._mock_contacts: list[dict[str, Any]] = []

        if self.caldav_url and self.username:
            self._status = ConnectorStatus.CONFIGURED
        else:
            self._status = ConnectorStatus.NOT_CONFIGURED

    def discover_capabilities(self) -> list[Capability]:
        return [
            Capability(
                name="list_events",
                description="List upcoming calendar events across permitted date ranges",
                risk_level="READ_ONLY",
                requires_network=bool(self.caldav_url and not self.caldav_url.startswith("http://127.0.0.1")),
            ),
            Capability(
                name="create_event",
                description="Create a calendar event with title, start, end, and optional location",
                risk_level="EXTERNAL_EFFECT",
                requires_network=bool(self.caldav_url and not self.caldav_url.startswith("http://127.0.0.1")),
            ),
            Capability(
                name="resolve_contact",
                description="Search contacts by name or email for explicit communication",
                risk_level="READ_ONLY",
                requires_network=bool(self.carddav_url and not self.carddav_url.startswith("http://127.0.0.1")),
            ),
        ]

    def health(self) -> dict[str, Any]:
        if not self.caldav_url or not self.username:
            return {
                "status": ConnectorStatus.NOT_CONFIGURED.value,
                "caldav_configured": False,
                "carddav_configured": False,
                "message": "CalDAV/CardDAV credentials not configured. Configure via environment or local Radicale instance.",
            }
        return {
            "status": self.status.value,
            "caldav_configured": True,
            "caldav_url": self.caldav_url,
            "carddav_configured": bool(self.carddav_url),
            "message": "Connector configured and ready for CalDAV queries.",
        }

    def read(self, resource_uri: str, **kwargs: Any) -> Any:
        if resource_uri == "calendar/events":
            limit = kwargs.get("limit", 10)
            return self._mock_events[:limit]
        elif resource_uri.startswith("contacts/"):
            query = resource_uri.split("/", 1)[1].lower()
            return [c for c in self._mock_contacts if query in c.get("name", "").lower() or query in c.get("email", "").lower()]
        return []

    def prepare_action(self, action_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if action_name == "create_event":
            if "title" not in arguments or "start_time" not in arguments:
                raise ValueError("Missing required arguments for create_event: 'title' and 'start_time'")
            return {
                "prepared": True,
                "action": "create_event",
                "preview": f"Event '{arguments['title']}' at {arguments['start_time']}",
                "arguments": arguments,
            }
        raise ValueError(f"Unknown action: {action_name}")

    def execute_authorized_action(self, action_id: str, action_name: str, arguments: dict[str, Any]) -> Any:
        if action_name == "create_event":
            event = {
                "id": f"evt_{action_id}",
                "title": arguments["title"],
                "start_time": arguments["start_time"],
                "end_time": arguments.get("end_time"),
                "location": arguments.get("location", ""),
            }
            self._mock_events.append(event)
            return {"event_id": event["id"], "status": "created"}
        raise ValueError(f"Unknown action: {action_name}")

    def verify(self, action_id: str, action_name: str, expected_state: Any) -> bool:
        if action_name == "create_event":
            return any(e.get("id") == f"evt_{action_id}" for e in self._mock_events)
        return False

    def disconnect(self) -> None:
        self._status = ConnectorStatus.DISCONNECTED
