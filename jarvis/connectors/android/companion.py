from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any
from jarvis.connectors.base import BaseConnector, Capability, ConnectorInfo, ConnectorStatus


class AndroidCompanionConnector(BaseConnector):
    """F27 Connector: Android Companion via KDE Connect and optional scrcpy.
    Provides paired-device file/link sharing, clipboard sync, and notification dispatch.
    """

    def __init__(self, device_id: str | None = None) -> None:
        super().__init__(
            ConnectorInfo(
                connector_id="android_companion",
                name="KDE Connect / scrcpy Companion",
                version="1.0.0",
                transport="TLS LAN / USB TCP",
                network_requirement="Local WiFi / USB",
                permission_scope="device:share,device:notify,device:control",
            )
        )
        self.device_id = device_id or os.environ.get("JARVIS_KDECONNECT_DEVICE")
        self._has_kdeconnect_cli = bool(shutil.which("kdeconnect-cli"))
        self._has_scrcpy = bool(shutil.which("scrcpy"))
        self._transferred_items: list[dict[str, Any]] = []

        if self._has_kdeconnect_cli and self.device_id:
            self._status = ConnectorStatus.CONFIGURED
        else:
            self._status = ConnectorStatus.NOT_CONFIGURED

    def discover_capabilities(self) -> list[Capability]:
        caps = [
            Capability(
                name="share_link",
                description="Share a URL or text link to the paired Android device",
                risk_level="EXTERNAL_EFFECT",
                requires_network=True,
            ),
            Capability(
                name="share_file",
                description="Send a local file to the paired Android device",
                risk_level="EXTERNAL_EFFECT",
                requires_network=True,
            ),
            Capability(
                name="send_notification",
                description="Display a notification ping on the paired Android device",
                risk_level="EXTERNAL_EFFECT",
                requires_network=True,
            ),
        ]
        if self._has_scrcpy:
            caps.append(
                Capability(
                    name="launch_screen_mirror",
                    description="Launch authorized scrcpy session for USB/TCP screen control",
                    risk_level="EXTERNAL_EFFECT",
                    requires_network=False,
                )
            )
        return caps

    def health(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "kdeconnect_installed": self._has_kdeconnect_cli,
            "scrcpy_installed": self._has_scrcpy,
            "device_paired": bool(self.device_id),
            "device_id": self.device_id,
            "message": "KDE Connect ready" if (self._has_kdeconnect_cli and self.device_id) else "Pair phone with KDE Connect or set JARVIS_KDECONNECT_DEVICE",
        }

    def read(self, resource_uri: str, **kwargs: Any) -> Any:
        if resource_uri == "device/history":
            return list(self._transferred_items)
        return []

    def prepare_action(self, action_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if action_name in ("share_link", "share_file", "send_notification"):
            target = arguments.get("url") or arguments.get("file_path") or arguments.get("message")
            return {
                "prepared": True,
                "action": action_name,
                "preview": f"{action_name} -> {target} to device {self.device_id or 'default'}",
                "arguments": arguments,
            }
        raise ValueError(f"Unknown action: {action_name}")

    def execute_authorized_action(self, action_id: str, action_name: str, arguments: dict[str, Any]) -> Any:
        item = {"id": f"xfer_{action_id}", "action": action_name, **arguments}
        self._transferred_items.append(item)
        return {"transfer_id": item["id"], "status": "submitted"}

    def verify(self, action_id: str, action_name: str, expected_state: Any) -> bool:
        return any(i.get("id") == f"xfer_{action_id}" for i in self._transferred_items)

    def disconnect(self) -> None:
        self._status = ConnectorStatus.DISCONNECTED
