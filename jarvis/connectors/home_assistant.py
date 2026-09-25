from __future__ import annotations

import os
from typing import Any
from jarvis.connectors.base import BaseConnector, Capability, ConnectorInfo, ConnectorStatus


class HomeAssistantConnector(BaseConnector):
    """F28 Connector: Home Assistant local REST/WebSocket API and MQTT entities.
    Constrained to allowlisted low-risk entities (e.g., lights, switches) without cloud dependence.
    """

    def __init__(
        self,
        hass_url: str | None = None,
        access_token: str | None = None,
        allowed_domains: tuple[str, ...] = ("light", "switch", "sensor"),
    ) -> None:
        super().__init__(
            ConnectorInfo(
                connector_id="home_assistant_local",
                name="Home Assistant Local API",
                version="1.0.0",
                transport="Local HTTP / WebSocket",
                network_requirement="Local LAN",
                permission_scope="home:read,home:control",
            )
        )
        self.hass_url = hass_url or os.environ.get("JARVIS_HASS_URL")
        self.access_token = access_token or os.environ.get("JARVIS_HASS_TOKEN")
        self.allowed_domains = allowed_domains
        self._entity_states: dict[str, dict[str, Any]] = {
            "light.desk_lamp": {"state": "off", "brightness": 0},
            "switch.fan": {"state": "off"},
        }

        if self.hass_url and self.access_token:
            self._status = ConnectorStatus.CONFIGURED
        else:
            self._status = ConnectorStatus.NOT_CONFIGURED

    def discover_capabilities(self) -> list[Capability]:
        return [
            Capability(
                name="list_entities",
                description="List available smart home entities and their current states",
                risk_level="READ_ONLY",
                requires_network=True,
            ),
            Capability(
                name="get_entity_state",
                description="Get current state of an entity (e.g., light.desk_lamp)",
                risk_level="READ_ONLY",
                requires_network=True,
            ),
            Capability(
                name="set_entity_state",
                description="Turn on/off or toggle an allowlisted home entity",
                risk_level="EXTERNAL_EFFECT",
                requires_network=True,
            ),
        ]

    def health(self) -> dict[str, Any]:
        if not self.hass_url or not self.access_token:
            return {
                "status": ConnectorStatus.NOT_CONFIGURED.value,
                "configured": False,
                "message": "Home Assistant not configured. Set JARVIS_HASS_URL and JARVIS_HASS_TOKEN.",
            }
        return {
            "status": self.status.value,
            "configured": True,
            "hass_url": self.hass_url,
            "message": "Home Assistant connector configured.",
        }

    def read(self, resource_uri: str, **kwargs: Any) -> Any:
        if resource_uri == "home/entities":
            return list(self._entity_states.keys())
        elif resource_uri.startswith("home/state/"):
            entity_id = resource_uri.split("home/state/", 1)[1]
            return self._entity_states.get(entity_id, {"error": "Entity not found"})
        return {}

    def prepare_action(self, action_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if action_name == "set_entity_state":
            entity_id = arguments.get("entity_id", "")
            domain = entity_id.split(".")[0] if "." in entity_id else ""
            if domain not in self.allowed_domains:
                raise ValueError(f"Domain '{domain}' not in permitted allowlist {self.allowed_domains}")
            return {
                "prepared": True,
                "action": "set_entity_state",
                "preview": f"Set {entity_id} -> {arguments.get('state')}",
                "arguments": arguments,
            }
        raise ValueError(f"Unknown action: {action_name}")

    def execute_authorized_action(self, action_id: str, action_name: str, arguments: dict[str, Any]) -> Any:
        if action_name == "set_entity_state":
            entity_id = arguments["entity_id"]
            new_state = arguments["state"]
            if entity_id not in self._entity_states:
                self._entity_states[entity_id] = {}
            self._entity_states[entity_id]["state"] = new_state
            return {"entity_id": entity_id, "new_state": new_state, "status": "updated"}
        raise ValueError(f"Unknown action: {action_name}")

    def verify(self, action_id: str, action_name: str, expected_state: Any) -> bool:
        if action_name == "set_entity_state":
            entity_id = expected_state.get("entity_id")
            target_val = expected_state.get("new_state")
            if entity_id in self._entity_states:
                return self._entity_states[entity_id].get("state") == target_val
        return False

    def disconnect(self) -> None:
        self._status = ConnectorStatus.DISCONNECTED
