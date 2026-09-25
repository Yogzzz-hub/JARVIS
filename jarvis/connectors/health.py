from __future__ import annotations

from typing import Any, Dict
from jarvis.connectors.manager import ConnectorManager


def get_system_health() -> Dict[str, Any]:
    mgr = ConnectorManager.get_default()
    return mgr.get_all_statuses()
