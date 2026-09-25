from __future__ import annotations

import logging
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Optional

from jarvis.connectors.base import BaseConnector, Capability, ConnectorInfo, ConnectorStatus

logger = logging.getLogger("jarvis.connectors.nodered")

APPROVED_EVENT_TYPES = frozenset({
    "download_completed",
    "rss_updated",
    "scheduled_morning_event",
    "task_complete",
    "motion_detected",
    "sensor_reading",
})


@dataclass
class ExternalEvent:
    source: str
    event_type: str
    event_id: str
    timestamp: float = field(default_factory=time.time)
    payload: dict[str, Any] = field(default_factory=dict)
    is_untrusted: bool = True  # External event payloads are strictly data, never instructions

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NodeRedConnector(BaseConnector):
    """Integrates Node-RED as an OPTIONAL event bridge.
    Never acts as an independent authority or reasoning engine.
    Applies strict event allowlisting, rate limits, and replay protection.
    """

    def __init__(
        self,
        node_red_url: Optional[str] = None,
        api_key: Optional[str] = None,
        enabled: bool = False,
        event_bus: Optional[Any] = None,
    ) -> None:
        super().__init__(
            ConnectorInfo(
                connector_id="node_red_visual",
                name="Node-RED Event Bridge",
                version="1.0.0",
                transport="Local HTTP Webhooks",
                network_requirement="Localhost / LAN",
                permission_scope="workflow:read,workflow:trigger,event:bridge",
            )
        )
        self.node_red_url = node_red_url or os.environ.get("JARVIS_NODERED_URL", "http://127.0.0.1:1880")
        self.api_key = api_key or os.environ.get("JARVIS_NODERED_KEY")
        self.enabled = enabled
        self.event_bus = event_bus

        self._approved_workflows: set[str] = {
            "notify_study_complete",
            "sync_reading_notes",
            "backup_daily_journal",
        }
        self._triggered_executions: list[dict[str, Any]] = []

        # Replay protection & Rate limiting
        self._processed_event_ids: dict[str, float] = {}
        self._rate_limits: list[float] = []

        if not self.enabled:
            self._status = ConnectorStatus.DISABLED
        else:
            self._status = ConnectorStatus.READY

    def discover_capabilities(self) -> list[Capability]:
        if not self.enabled:
            return []
        return [
            Capability(
                name="nodered.status",
                description="Check Node-RED bridge status and approved flows",
                risk_level="READ_ONLY",
                requires_network=True,
            ),
            Capability(
                name="nodered.list_workflows",
                description="List approved named Node-RED workflows callable by JARVIS",
                risk_level="READ_ONLY",
                requires_network=True,
            ),
            Capability(
                name="nodered.trigger_workflow",
                description="Trigger an approved named Node-RED flow with structured payload",
                risk_level="EXTERNAL_EFFECT",
                requires_network=True,
            ),
        ]

    def health(self) -> dict[str, Any]:
        if not self.enabled:
            return {"status": ConnectorStatus.DISABLED.value, "message": "Node-RED connector disabled in config."}
        return {
            "status": ConnectorStatus.READY.value,
            "node_red_url": self.node_red_url,
            "approved_workflows_count": len(self._approved_workflows),
            "processed_events_count": len(self._processed_event_ids),
            "message": "Node-RED event bridge ready for authorized named flows.",
        }

    def receive_external_event(self, event: ExternalEvent) -> tuple[bool, str]:
        """Ingests an external event through schema validation, allowlist, rate-limiting, and replay protection."""
        now = time.time()

        # 1. Replay protection
        if event.event_id in self._processed_event_ids:
            return False, f"Replay detected: event '{event.event_id}' already processed"
        self._processed_event_ids[event.event_id] = now

        # Prune old event IDs (> 1 hour)
        cutoff = now - 3600.0
        self._processed_event_ids = {k: v for k, v in self._processed_event_ids.items() if v > cutoff}

        # 2. Rate limiting (max 10 events per minute)
        self._rate_limits = [t for t in self._rate_limits if (now - t) < 60.0]
        if len(self._rate_limits) >= 10:
            return False, "Rate limit exceeded: maximum 10 events per minute allowed from Node-RED"
        self._rate_limits.append(now)

        # 3. Allowlist validation
        norm_type = event.event_type.replace(".", "_")
        if norm_type not in APPROVED_EVENT_TYPES:
            logger.warning(f"Rejected unapproved Node-RED event type: {event.event_type}")
            return False, f"Unauthorized event type: '{event.event_type}' not in allowlist"


        # 4. Forward to Jarvis EventBus as safe data
        logger.info(f"Node-RED bridge accepted event: {event.event_type} ({event.event_id})")
        if self.event_bus:
            try:
                self.event_bus.emit(
                    f"external.{event.event_type}",
                    "",
                    source=event.source,
                    event_id=event.event_id,
                    payload=event.payload,
                )
            except Exception as e:
                logger.warning(f"Error publishing external event to bus: {e}")

        return True, f"Event '{event.event_id}' accepted"

    handle_event = receive_external_event


    def read(self, resource_uri: str, **kwargs: Any) -> Any:
        if resource_uri == "workflows/approved":
            return list(self._approved_workflows)
        elif resource_uri == "workflows/history":
            return list(self._triggered_executions)
        return []

    def prepare_action(self, action_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if action_name in ("nodered.trigger_workflow", "trigger_named_workflow"):
            wf_name = arguments.get("workflow_name", "")
            if wf_name not in self._approved_workflows:
                raise ValueError(
                    f"Workflow '{wf_name}' is not an approved named workflow in JARVIS. "
                    "Arbitrary flow execution is prohibited."
                )
            return {
                "prepared": True,
                "action": action_name,
                "preview": f"Trigger approved workflow: {wf_name}",
                "workflow_name": wf_name,
                "arguments": arguments,
            }
        return {"prepared": True, "action": action_name, "preview": f"Execute {action_name}"}

    def execute_authorized_action(self, action_id: str, action_name: str, arguments: dict[str, Any]) -> Any:
        t0 = time.perf_counter()

        if action_name == "nodered.status":
            return {"status": "SUCCESS", "data": self.health()}

        if action_name in ("nodered.list_workflows", "list_named_workflows"):
            return {"status": "SUCCESS", "workflows": list(self._approved_workflows)}

        if action_name in ("nodered.trigger_workflow", "trigger_named_workflow"):
            wf_name = arguments.get("workflow_name", "")
            if wf_name not in self._approved_workflows:
                raise ValueError(f"Workflow '{wf_name}' not approved")

            record = {
                "execution_id": f"nr_{action_id}",
                "workflow_name": wf_name,
                "payload": arguments.get("payload", {}),
                "status": "dispatched",
            }
            self._triggered_executions.append(record)
            dur = (time.perf_counter() - t0) * 1000
            return {
                "status": "SUCCESS",
                "message": f"Triggered Node-RED flow '{wf_name}'",
                "execution_id": record["execution_id"],
                "duration_ms": dur,
            }

        raise NotImplementedError(f"Action '{action_name}' not implemented")

    def verify(self, action_id: str, action_name: str, expected_state: Any) -> bool:
        return any(e.get("execution_id") == f"nr_{action_id}" for e in self._triggered_executions)

    def disconnect(self) -> None:
        self._status = ConnectorStatus.UNAVAILABLE
