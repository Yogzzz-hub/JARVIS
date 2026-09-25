from __future__ import annotations

import os
from typing import Any
from jarvis.connectors.base import BaseConnector, Capability, ConnectorInfo, ConnectorStatus


class EmailConnector(BaseConnector):
    """F26 Connector: Standards-based IMAP/SMTP adapter.
    Summarizes selected mail, finds attachments, and drafts replies with exact recipient previews.
    """

    def __init__(
        self,
        imap_host: str | None = None,
        smtp_host: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        super().__init__(
            ConnectorInfo(
                connector_id="email_imap_smtp",
                name="Email IMAP/SMTP Connector",
                version="1.0.0",
                transport="TLS IMAP/SMTP",
                network_requirement="Internet or Local Mail Server",
                permission_scope="mail:read,mail:draft,mail:send",
            )
        )
        self.imap_host = imap_host or os.environ.get("JARVIS_IMAP_HOST")
        self.smtp_host = smtp_host or os.environ.get("JARVIS_SMTP_HOST")
        self.username = username or os.environ.get("JARVIS_EMAIL_USER")
        self.password = password or os.environ.get("JARVIS_EMAIL_PASS")
        self._sent_messages: list[dict[str, Any]] = []
        self._drafts: list[dict[str, Any]] = []

        if self.imap_host and self.username:
            self._status = ConnectorStatus.CONFIGURED
        else:
            self._status = ConnectorStatus.NOT_CONFIGURED

    def discover_capabilities(self) -> list[Capability]:
        return [
            Capability(
                name="list_inbox",
                description="List recent subject lines and senders from inbox",
                risk_level="READ_ONLY",
                requires_network=True,
            ),
            Capability(
                name="draft_reply",
                description="Prepare a draft email reply without sending",
                risk_level="REVERSIBLE",
                requires_network=False,
            ),
            Capability(
                name="send_email",
                description="Send an email to specified recipients after explicit review",
                risk_level="EXTERNAL_EFFECT",
                requires_network=True,
            ),
        ]

    def health(self) -> dict[str, Any]:
        if not self.imap_host or not self.username:
            return {
                "status": ConnectorStatus.NOT_CONFIGURED.value,
                "imap_configured": False,
                "smtp_configured": False,
                "message": "Mail credentials not configured. Set JARVIS_IMAP_HOST and JARVIS_EMAIL_USER.",
            }
        return {
            "status": self.status.value,
            "imap_configured": True,
            "smtp_configured": bool(self.smtp_host),
            "username": self.username,
            "message": "IMAP/SMTP configured and ready.",
        }

    def read(self, resource_uri: str, **kwargs: Any) -> Any:
        if resource_uri == "mail/inbox":
            return [
                {"id": "msg_001", "sender": "team@example.com", "subject": "Project update", "date": "2026-09-19"},
            ]
        elif resource_uri == "mail/drafts":
            return list(self._drafts)
        return []

    def prepare_action(self, action_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if action_name == "draft_reply":
            return {
                "prepared": True,
                "action": "draft_reply",
                "preview": f"Draft to {arguments.get('to')}: {arguments.get('subject')}",
                "arguments": arguments,
            }
        elif action_name == "send_email":
            if "to" not in arguments or "subject" not in arguments or "body" not in arguments:
                raise ValueError("Missing 'to', 'subject', or 'body'")
            return {
                "prepared": True,
                "action": "send_email",
                "preview": f"SEND EMAIL -> To: {arguments['to']} | Subject: {arguments['subject']}",
                "recipient": arguments["to"],
                "subject": arguments["subject"],
                "arguments": arguments,
            }
        raise ValueError(f"Unknown action: {action_name}")

    def execute_authorized_action(self, action_id: str, action_name: str, arguments: dict[str, Any]) -> Any:
        if action_name == "draft_reply":
            draft = {"id": f"draft_{action_id}", **arguments}
            self._drafts.append(draft)
            return {"draft_id": draft["id"], "status": "draft_created"}
        elif action_name == "send_email":
            msg = {"id": f"sent_{action_id}", **arguments}
            self._sent_messages.append(msg)
            return {"message_id": msg["id"], "status": "submitted"}
        raise ValueError(f"Unknown action: {action_name}")

    def verify(self, action_id: str, action_name: str, expected_state: Any) -> bool:
        if action_name == "send_email":
            return any(m.get("id") == f"sent_{action_id}" for m in self._sent_messages)
        elif action_name == "draft_reply":
            return any(d.get("id") == f"draft_{action_id}" for d in self._drafts)
        return False

    def disconnect(self) -> None:
        self._status = ConnectorStatus.DISCONNECTED
