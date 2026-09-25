from __future__ import annotations

import logging
from pathlib import Path
import time
import tomllib
from typing import Any, Dict, Optional

from jarvis.config import ROOT
from jarvis.connectors.base import BaseConnector, ConnectorStatus
from jarvis.connectors.android.scrcpy import AndroidScrcpyConnector
from jarvis.connectors.localsend.client import LocalSendConnector
from jarvis.connectors.browser.playwright_connector import PlaywrightConnector
from jarvis.connectors.rss.freshrss import FreshRSSConnector
from jarvis.connectors.notifications.provider import NotificationConnector
from jarvis.connectors.memos.client import MemosConnector
from jarvis.connectors.node_red import NodeRedConnector

logger = logging.getLogger("jarvis.connectors.manager")


class ConnectorManager:
    """Central orchestrator for all JARVIS EDGE v1.x local connectors.
    Provides lazy-loading, cached health checks, event forwarding, and safe degradation.
    """

    _instance: Optional[ConnectorManager] = None

    @classmethod
    def get_default(cls) -> ConnectorManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, config_path: Optional[Path] = None, event_bus: Optional[Any] = None) -> None:
        self.config_path = config_path or (ROOT.parent / "config" / "connectors.toml")
        self.event_bus = event_bus
        self.config: dict[str, Any] = {}
        self._load_config()

        self._connectors: dict[str, BaseConnector] = {}
        self._health_cache: dict[str, dict[str, Any]] = {}
        self._health_cache_time: dict[str, float] = {}
        self._health_ttl_s = 30.0

        self._init_connectors()

    def _load_config(self) -> None:
        if self.config_path.exists():
            try:
                with open(self.config_path, "rb") as f:
                    self.config = tomllib.load(f)
            except Exception as e:
                logger.warning("Failed to parse config/connectors.toml: %s", e)

    def _init_connectors(self) -> None:
        cfg = self.config.get("connectors", {})

        # 1. Android / scrcpy
        android_cfg = cfg.get("android", {})
        self._connectors["android"] = AndroidScrcpyConnector(
            device_id=android_cfg.get("device_id") or None,
            scrcpy_path=android_cfg.get("scrcpy_path") or None,
            adb_path=android_cfg.get("adb_path") or None,
            max_size=android_cfg.get("max_size", 1024),
            max_fps=android_cfg.get("max_fps", 30),
            stay_awake=android_cfg.get("stay_awake", True),
            enabled=android_cfg.get("enabled", True),
        )

        # 2. LocalSend
        ls_cfg = cfg.get("localsend", {})
        self._connectors["localsend"] = LocalSendConnector(
            base_url=ls_cfg.get("base_url", "http://127.0.0.1:53317"),
            port=ls_cfg.get("port", 53317),
            enabled=ls_cfg.get("enabled", True),
            event_callback=self._on_connector_event,
        )

        # 3. Playwright Browser
        b_cfg = cfg.get("browser", {})
        self._connectors["browser"] = PlaywrightConnector(
            headless=b_cfg.get("headless", True),
            enabled=b_cfg.get("enabled", True),
            event_callback=self._on_connector_event,
        )

        # 4. FreshRSS
        rss_cfg = cfg.get("freshrss", {})
        self._connectors["freshrss"] = FreshRSSConnector(
            base_url=rss_cfg.get("base_url", ""),
            username=rss_cfg.get("username", ""),
            api_password=rss_cfg.get("api_password", ""),
            enabled=rss_cfg.get("enabled", False),
        )

        # 5. Push Notifications
        notif_cfg = cfg.get("notifications", {})
        self._connectors["notifications"] = NotificationConnector(
            provider_name=notif_cfg.get("provider", "ntfy"),
            ntfy_url=notif_cfg.get("ntfy_url", "https://ntfy.sh"),
            ntfy_topic=notif_cfg.get("ntfy_topic", "jarvis_alerts_local"),
            gotify_url=notif_cfg.get("gotify_url", "http://127.0.0.1:80"),
            gotify_token=notif_cfg.get("gotify_token", ""),
            enabled=notif_cfg.get("enabled", True),
        )

        # 6. Memos
        memos_cfg = cfg.get("memos", {})
        self._connectors["memos"] = MemosConnector(
            base_url=memos_cfg.get("base_url", ""),
            access_token=memos_cfg.get("access_token", ""),
            enabled=memos_cfg.get("enabled", True),
        )

        # 7. Node-RED
        nr_cfg = cfg.get("nodered", {})
        self._connectors["nodered"] = NodeRedConnector(
            node_red_url=nr_cfg.get("base_url"),
            api_key=nr_cfg.get("api_key"),
            enabled=nr_cfg.get("enabled", False),
            event_bus=self.event_bus,
        )

    def _on_connector_event(self, event_name: str, data: dict[str, Any]) -> None:
        if self.event_bus:
            try:
                self.event_bus.emit(f"connector.{event_name.lower()}", "", **data)
            except Exception as e:
                logger.warning(f"Error publishing connector event {event_name}: {e}")

    def get_connector(self, name: str) -> Optional[BaseConnector]:
        name_clean = name.lower().strip()
        if name_clean in ("rss", "freshrss"):
            return self._connectors.get("freshrss")
        if name_clean in ("notification", "notifications"):
            return self._connectors.get("notifications")
        if name_clean in ("nodered", "node_red"):
            return self._connectors.get("nodered")
        return self._connectors.get(name_clean)


    def get_status(self, name: str, force_refresh: bool = False) -> dict[str, Any]:
        """Returns health status with 30s TTL caching to avoid latency spikes."""
        now = time.time()
        name = name.lower()
        conn = self._connectors.get(name)
        if not conn:
            return {"status": ConnectorStatus.UNAVAILABLE.value, "message": f"Connector '{name}' not found."}

        if not force_refresh and name in self._health_cache:
            if (now - self._health_cache_time.get(name, 0.0)) < self._health_ttl_s:
                return self._health_cache[name]

        res = conn.health()
        self._health_cache[name] = res
        self._health_cache_time[name] = now
        return res

    def get_all_statuses(self, force_refresh: bool = False) -> dict[str, dict[str, Any]]:
        statuses = {}
        for name in self._connectors:
            statuses[name] = self.get_status(name, force_refresh=force_refresh)
        return statuses

    def execute(self, connector_name: str, action_name: str, arguments: dict[str, Any]) -> Any:
        conn = self.get_connector(connector_name)
        if not conn:
            raise KeyError(f"Connector '{connector_name}' is not registered.")
        return conn.execute(action_name, arguments)


def get_connector_manager() -> ConnectorManager:
    return ConnectorManager.get_default()

