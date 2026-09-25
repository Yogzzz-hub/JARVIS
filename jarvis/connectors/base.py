from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ConnectorStatus(StrEnum):
    DISABLED = "DISABLED"
    UNAVAILABLE = "UNAVAILABLE"
    CONNECTING = "CONNECTING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"

    # Aliases for backwards compatibility
    NOT_CONFIGURED = "DISABLED"
    CONFIGURED = "READY"
    CONNECTED = "READY"
    DISCONNECTED = "UNAVAILABLE"


@dataclass(frozen=True)
class Capability:
    name: str
    description: str
    risk_level: str = "READ_ONLY"
    requires_network: bool = False


@dataclass(frozen=True)
class ConnectorInfo:
    connector_id: str
    name: str
    version: str
    transport: str
    network_requirement: str
    permission_scope: str


class BaseConnector(ABC):
    """Authoritative connector interface specified by JARVIS v1.x architecture:
    - name, status, capabilities
    - connect(), disconnect(), health_check()
    - execute(), verify()
    - timeout, retry_policy, security_metadata
    """

    def __init__(
        self,
        info: ConnectorInfo,
        timeout: float = 10.0,
        retry_policy: dict[str, Any] | None = None,
        security_metadata: dict[str, Any] | None = None,
    ) -> None:
        self.info = info
        self._status = ConnectorStatus.UNAVAILABLE
        self._error_message: str | None = None
        self.timeout = timeout
        self.retry_policy = retry_policy or {"max_retries": 2, "backoff_factor": 1.5}
        self.security_metadata = security_metadata or {
            "network": info.network_requirement,
            "trust_level": "EXTERNAL_UNTRUSTED",
            "scope": info.permission_scope,
        }

    @property
    def name(self) -> str:
        return self.info.name

    @property
    def status(self) -> ConnectorStatus:
        return self._status

    @status.setter
    def status(self, val: ConnectorStatus) -> None:
        self._status = val

    def is_ready(self) -> bool:
        """Returns True if the connector is ready or degraded (operational)."""
        return self._status in (ConnectorStatus.READY, ConnectorStatus.DEGRADED)

    @property
    def capabilities(self) -> list[Capability]:

        return self.discover_capabilities()

    async def connect(self) -> bool:
        """Asynchronously connect or initialize connector resources."""
        return True

    def health_check(self) -> dict[str, Any]:
        """Runs health check and updates internal status."""
        h = self.health()
        return h

    def execute(self, action_name: str, arguments: dict[str, Any] | None = None, action_id: str = "act_direct", **kwargs: Any) -> Any:
        """Direct execution interface supporting dictionary or keyword arguments."""
        args = dict(arguments or {})
        args.update(kwargs)
        return self.execute_authorized_action(action_id, action_name, args)


    @abstractmethod
    def discover_capabilities(self) -> list[Capability]:
        """Discovers capabilities exposed by the target system."""
        raise NotImplementedError

    @abstractmethod
    def health(self) -> dict[str, Any]:
        """Returns truthful health status, connection metrics, and errors."""
        raise NotImplementedError

    @abstractmethod
    def read(self, resource_uri: str, **kwargs: Any) -> Any:
        """Reads permitted resource without mutation."""
        raise NotImplementedError

    @abstractmethod
    def prepare_action(self, action_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Validates arguments, creates action preview, and returns ticket."""
        raise NotImplementedError

    @abstractmethod
    def execute_authorized_action(self, action_id: str, action_name: str, arguments: dict[str, Any]) -> Any:
        """Executes an action under verified user authority."""
        raise NotImplementedError

    @abstractmethod
    def verify(self, action_id: str, action_name: str, expected_state: Any) -> bool:
        """Verifies independent observable outcome against target system."""
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        """Gracefully disconnects and cleans up resources."""
        raise NotImplementedError

