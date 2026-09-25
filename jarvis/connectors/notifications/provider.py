from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional
import urllib.request
import urllib.error

from jarvis.connectors.base import BaseConnector, Capability, ConnectorInfo, ConnectorStatus

logger = logging.getLogger("jarvis.connectors.notifications")

SECRET_PATTERNS = [
    re.compile(r"(bearer\s+)[a-zA-Z0-9_\-\.]{15,}", re.IGNORECASE),
    re.compile(r"(password[\"':\s=]+)[^\s\"']+", re.IGNORECASE),
    re.compile(r"(token[\"':\s=]+)[^\s\"']+", re.IGNORECASE),
    re.compile(r"(api[_-]?key[\"':\s=]+)[^\s\"']+", re.IGNORECASE),
    re.compile(r"(secret[\"':\s=]+)[^\s\"']+", re.IGNORECASE),
]


def redact_secrets(text: str) -> str:
    """Redact sensitive tokens, passwords, and credentials from notification bodies."""
    if not text:
        return ""
    sanitized = text
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub(r"\1[REDACTED]", sanitized)
    return sanitized


@dataclass
class NotificationRequest:
    title: str
    message: str
    priority: int = 3  # 1 (min) to 5 (urgent)
    category: str = "general"
    action_ref: Optional[str] = None


class NotificationProvider(ABC):
    @abstractmethod
    def send(self, req: NotificationRequest) -> tuple[bool, str]:
        raise NotImplementedError

    @abstractmethod
    def health(self) -> tuple[bool, str]:
        raise NotImplementedError


class NtfyProvider(NotificationProvider):
    def __init__(self, server_url: str = "https://ntfy.sh", topic: str = "jarvis_alerts_local") -> None:
        self.server_url = server_url.rstrip("/")
        self.topic = topic

    def send(self, req: NotificationRequest) -> tuple[bool, str]:
        url = f"{self.server_url}/{self.topic}"
        safe_msg = redact_secrets(req.message).encode("utf-8")
        headers = {
            "Title": req.title.encode("ascii", "ignore").decode("ascii"),
            "Priority": str(req.priority),
            "Tags": req.category,
        }
        try:
            http_req = urllib.request.Request(url, data=safe_msg, headers=headers, method="POST")
            with urllib.request.urlopen(http_req, timeout=4.0) as resp:
                if 200 <= resp.status < 300:
                    return True, f"Delivered via ntfy ({self.topic})"
                return False, f"ntfy HTTP {resp.status}"
        except Exception as e:
            return False, f"ntfy send failed: {e}"

    def health(self) -> tuple[bool, str]:
        url = f"{self.server_url}/{self.topic}/json?poll=1"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2.0):
                return True, f"ntfy server reachable at {self.server_url}"
        except Exception as e:
            return False, str(e)


class GotifyProvider(NotificationProvider):
    def __init__(self, server_url: str = "http://127.0.0.1:80", app_token: str = "") -> None:
        self.server_url = server_url.rstrip("/")
        self.app_token = app_token

    def send(self, req: NotificationRequest) -> tuple[bool, str]:
        if not self.app_token:
            return False, "Gotify app_token not configured"
        url = f"{self.server_url}/message"
        payload = {
            "title": req.title,
            "message": redact_secrets(req.message),
            "priority": req.priority,
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {"X-Gotify-Key": self.app_token, "Content-Type": "application/json"}
        try:
            http_req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(http_req, timeout=4.0) as resp:
                if 200 <= resp.status < 300:
                    return True, "Delivered via Gotify"
                return False, f"Gotify HTTP {resp.status}"
        except Exception as e:
            return False, f"Gotify send failed: {e}"

    def health(self) -> tuple[bool, str]:
        url = f"{self.server_url}/health"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2.0):
                return True, f"Gotify server reachable at {self.server_url}"
        except Exception as e:
            return False, str(e)


class NotificationConnector(BaseConnector):
    """Notification abstraction supporting ntfy and Gotify.
    Includes sliding-window deduplication to avoid repeat notification spam.
    """

    def __init__(
        self,
        provider_name: str = "ntfy",
        ntfy_url: str = "https://ntfy.sh",
        ntfy_topic: str = "jarvis_alerts_local",
        gotify_url: str = "http://127.0.0.1:80",
        gotify_token: str = "",
        enabled: bool = True,
        dedup_window_s: float = 60.0,
    ) -> None:
        super().__init__(
            ConnectorInfo(
                connector_id="notification_dispatch",
                name="Push Notification Dispatcher",
                version="1.0.0",
                transport="REST Webhook",
                network_requirement="Local LAN or HTTPS Webhook",
                permission_scope="notification:send",
            )
        )
        self.enabled = enabled
        self.provider_name = provider_name
        self.dedup_window_s = dedup_window_s

        if provider_name.lower() == "gotify":
            self.provider: NotificationProvider = GotifyProvider(gotify_url, gotify_token)
        else:
            self.provider = NtfyProvider(ntfy_url, ntfy_topic)

        self._sent_notifications: list[dict[str, Any]] = []
        self._dedup_cache: dict[str, float] = {}

        if not self.enabled:
            self._status = ConnectorStatus.DISABLED
        else:
            self._status = ConnectorStatus.READY

    def discover_capabilities(self) -> list[Capability]:
        if not self.enabled:
            return []
        return [
            Capability(
                name="notification.status",
                description="Check push notification provider health and topic reachability",
                risk_level="READ_ONLY",
                requires_network=True,
            ),
            Capability(
                name="notification.send",
                description="Send a push notification to user's phone upon task/download completion",
                risk_level="EXTERNAL_EFFECT",
                requires_network=True,
            ),
        ]

    def health(self) -> dict[str, Any]:
        if not self.enabled:
            return {"status": ConnectorStatus.DISABLED.value, "message": "Notification connector disabled in config."}
        ok, msg = self.provider.health()
        self._status = ConnectorStatus.READY if ok else ConnectorStatus.DEGRADED
        return {
            "status": self._status.value,
            "provider": self.provider_name,
            "message": msg,
        }

    def read(self, resource_uri: str, **kwargs: Any) -> Any:
        if resource_uri == "history":
            return list(self._sent_notifications)
        return []

    def prepare_action(self, action_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if action_name == "notification.send":
            title = arguments.get("title", "Jarvis Alert")
            msg = arguments.get("message", "")
            return {"prepared": True, "action": action_name, "preview": f"Push '{title}': '{msg[:60]}' to phone"}
        elif action_name == "notification.status":
            return {"prepared": True, "action": action_name, "preview": "Check notification provider status"}
        raise ValueError(f"Unknown action: {action_name}")

    def execute_authorized_action(self, action_id: str, action_name: str, arguments: dict[str, Any]) -> Any:
        t0 = time.perf_counter()

        action = action_name.removeprefix("notification.").removeprefix("notifications.")

        if action == "status":
            h = self.health()
            dur = (time.perf_counter() - t0) * 1000
            return {"status": "SUCCESS", "success": True, "data": h, "duration_ms": dur}

        if action == "send":
            title = arguments.get("title", "JARVIS Notification")
            raw_msg = arguments.get("message", "").strip()
            priority = int(arguments.get("priority", 3))
            category = arguments.get("category", "general")

            # Deduplication check
            dedup_key = hashlib.sha256(f"{title}:{raw_msg}".encode("utf-8")).hexdigest()
            now = time.time()
            if dedup_key in self._dedup_cache and (now - self._dedup_cache[dedup_key]) < self.dedup_window_s:
                dur = (time.perf_counter() - t0) * 1000
                return {
                    "status": "DEDUPLICATED",
                    "success": True,
                    "message": "Duplicate notification skipped within rate limit window.",
                    "duration_ms": dur,
                }

            req = NotificationRequest(title=title, message=raw_msg, priority=priority, category=category)
            ok, msg = self.provider.send(req)

            self._dedup_cache[dedup_key] = now
            record = {
                "id": f"notif_{action_id}",
                "title": title,
                "message": redact_secrets(raw_msg),
                "timestamp": now,
                "provider": self.provider_name,
                "status": "SENT" if ok else "FAILED",
            }
            self._sent_notifications.append(record)

            dur = (time.perf_counter() - t0) * 1000
            return {
                "status": "SUCCESS" if ok else "FAILED",
                "success": ok,
                "message": f"Notification '{title}' dispatched: {msg}",
                "duration_ms": dur,
                "notification_id": record["id"],
                "action_ledger_status": "COMMITTED" if ok else "FAILED",
            }


        raise NotImplementedError(f"Action '{action_name}' not implemented")

    def verify(self, action_id: str, action_name: str, expected_state: Any) -> bool:
        return any(n.get("id") == f"notif_{action_id}" and n.get("status") == "SENT" for n in self._sent_notifications)

    def disconnect(self) -> None:
        self._dedup_cache.clear()
        self._status = ConnectorStatus.UNAVAILABLE
