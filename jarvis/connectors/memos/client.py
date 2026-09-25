from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional
import urllib.request
import urllib.error

from jarvis.connectors.base import BaseConnector, Capability, ConnectorInfo, ConnectorStatus
from jarvis.connectors.notifications.provider import redact_secrets

logger = logging.getLogger("jarvis.connectors.memos")


@dataclass
class MemoItem:
    id: str
    content: str
    created_at: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)
    pinned: bool = False
    is_untrusted: bool = True  # Untrusted user data when read back

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MemosConnector(BaseConnector):
    """Integrates self-hosted Memos for human-readable notes and quick inboxes.
    Strictly separated from JARVIS internal working memory (WorkingMemory).
    Treats all memo content read back as UNTRUSTED data.
    """

    def __init__(
        self,
        base_url: str = "",
        access_token: str = "",
        enabled: bool = False,
    ) -> None:
        super().__init__(
            ConnectorInfo(
                connector_id="memos_notes",
                name="Memos Human Notebook",
                version="1.0.0",
                transport="REST API",
                network_requirement="Localhost / LAN",
                permission_scope="memos:read,memos:write",
            )
        )
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.enabled = enabled

        # Local fallback store for offline/standalone resilience
        self._local_notes: list[MemoItem] = []

        if not self.enabled:
            self._status = ConnectorStatus.DISABLED
        elif not self.base_url:
            self._status = ConnectorStatus.READY  # Standalone local note mode
        else:
            self._status = ConnectorStatus.READY

    def discover_capabilities(self) -> list[Capability]:
        if not self.enabled:
            return []
        return [
            Capability(
                name="memos.status",
                description="Check Memos server health or local notes store",
                risk_level="READ_ONLY",
                requires_network=bool(self.base_url),
            ),
            Capability(
                name="memos.create",
                description="Create a human-readable note, reminder, or quick memo",
                risk_level="EXTERNAL_EFFECT",
                requires_network=bool(self.base_url),
            ),
            Capability(
                name="memos.search",
                description="Search human notes by keyword",
                risk_level="READ_ONLY",
                requires_network=bool(self.base_url),
            ),
            Capability(
                name="memos.recent",
                description="Get recent human notes (e.g. for morning briefing)",
                risk_level="READ_ONLY",
                requires_network=bool(self.base_url),
            ),
            Capability(
                name="memos.get",
                description="Retrieve a single note by ID",
                risk_level="READ_ONLY",
                requires_network=bool(self.base_url),
            ),
        ]

    def health(self) -> dict[str, Any]:
        if not self.enabled:
            return {"status": ConnectorStatus.DISABLED.value, "message": "Memos connector disabled in config."}
        if not self.base_url:
            return {
                "status": ConnectorStatus.READY.value,
                "mode": "standalone_local",
                "notes_count": len(self._local_notes),
                "message": "Memos operating in local standalone note store mode.",
            }

        url = f"{self.base_url}/ping"
        try:
            req = urllib.request.Request(url)
            if self.access_token:
                req.add_header("Authorization", f"Bearer {self.access_token}")
            with urllib.request.urlopen(req, timeout=2.0):
                self._status = ConnectorStatus.READY
                return {
                    "status": ConnectorStatus.READY.value,
                    "endpoint": self.base_url,
                    "message": "Memos service reachable.",
                }
        except Exception as e:
            self._status = ConnectorStatus.DEGRADED
            return {
                "status": ConnectorStatus.DEGRADED.value,
                "endpoint": self.base_url,
                "message": f"Memos service unreachable at {self.base_url}: {e}. Falling back to local store.",
            }

    def read(self, resource_uri: str, **kwargs: Any) -> Any:
        if resource_uri == "recent":
            return [m.to_dict() for m in self._local_notes[-10:]]
        return []

    def prepare_action(self, action_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if action_name == "memos.create":
            content = arguments.get("content", "")
            return {"prepared": True, "action": action_name, "preview": f"Save note: '{content[:60]}'"}
        return {"prepared": True, "action": action_name, "preview": f"Execute {action_name}"}

    def execute_authorized_action(self, action_id: str, action_name: str, arguments: dict[str, Any]) -> Any:
        t0 = time.perf_counter()
        action = action_name.removeprefix("memos.")

        if action == "status":
            return {"status": "SUCCESS", "data": self.health()}

        if action == "create":
            raw_content = arguments.get("content", "").strip()
            if not raw_content:
                raise ValueError("memos.create requires non-empty 'content'")
            # Redact any accidental tokens or passwords
            safe_content = redact_secrets(raw_content)
            tags = arguments.get("tags", [])

            memo = MemoItem(
                id=f"memo_{int(time.time()*1000)}",
                content=safe_content,
                created_at=time.time(),
                tags=tags if isinstance(tags, list) else [],
            )
            self._local_notes.append(memo)

            # If remote base_url configured, try sync
            remote_synced = False
            if self.base_url and self.enabled:
                try:
                    payload = {"content": safe_content, "visibility": "PRIVATE"}
                    data = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(f"{self.base_url}/memos", data=data, method="POST")
                    req.add_header("Content-Type", "application/json")
                    if self.access_token:
                        req.add_header("Authorization", f"Bearer {self.access_token}")
                    with urllib.request.urlopen(req, timeout=3.0) as resp:
                        if 200 <= resp.status < 300:
                            remote_synced = True
                except Exception as e:
                    logger.debug("Remote Memos sync skipped: %s", e)

            dur = (time.perf_counter() - t0) * 1000
            return {
                "status": "SUCCESS",
                "success": True,
                "message": f"Saved note: '{safe_content[:80]}'",
                "memo_id": memo.id,
                "memo": memo.to_dict(),
                "remote_synced": remote_synced,
                "duration_ms": dur,
            }

        if action == "recent":
            limit = int(arguments.get("limit", 5))
            recent = [m.to_dict() for m in reversed(self._local_notes[-limit:])]
            dur = (time.perf_counter() - t0) * 1000
            return {"status": "SUCCESS", "success": True, "count": len(recent), "notes": recent, "duration_ms": dur}

        if action == "search":
            query = arguments.get("query", "").strip().casefold()
            matched = [m.to_dict() for m in self._local_notes if query in m.content.casefold()]
            dur = (time.perf_counter() - t0) * 1000
            return {"status": "SUCCESS", "success": True, "query": query, "count": len(matched), "notes": matched, "duration_ms": dur}


        if action == "get":

            mid = arguments.get("id", "")
            found = next((m.to_dict() for m in self._local_notes if m.id == mid), None)
            if not found:
                raise KeyError(f"Memo '{mid}' not found")
            return {"status": "SUCCESS", "memo": found}

        raise NotImplementedError(f"Action '{action_name}' not implemented")

    def verify(self, action_id: str, action_name: str, expected_state: Any) -> bool:
        return True

    def disconnect(self) -> None:
        self._status = ConnectorStatus.UNAVAILABLE
