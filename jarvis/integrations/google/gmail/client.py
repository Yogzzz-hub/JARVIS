"""Google Gmail API client wrapper."""
from __future__ import annotations

import base64
import email
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jarvis.integrations.google.auth.manager import GoogleAuthManager
from jarvis.integrations.google.auth.scopes import GoogleCapability
from jarvis.integrations.google.common.errors import normalize_google_error
from jarvis.integrations.google.common.executor import GoogleIntegrationExecutor
from jarvis.integrations.google.common.pagination import PaginatedResult
from jarvis.integrations.google.common.quota import QuotaManager
from jarvis.integrations.google.common.retry import execute_with_retry
from jarvis.integrations.google.gmail.models import (
    AttachmentMetadata,
    EmailDraft,
    EmailMessage,
    EmailSummary,
)


class GmailClient:
    """Production client for interacting with Google Gmail API v1."""

    def __init__(
        self,
        auth_manager: Optional[GoogleAuthManager] = None,
        executor: Optional[GoogleIntegrationExecutor] = None,
        quota_manager: Optional[QuotaManager] = None,
        service: Optional[Any] = None,
        account_id: str = "default",
    ) -> None:
        self.auth_manager = auth_manager
        self.executor = executor or GoogleIntegrationExecutor()
        self.quota_manager = quota_manager or QuotaManager()
        self._mock_service = service
        self.account_id = account_id
        self._service_cache: Dict[str, Any] = {}

    async def _get_service(self, account_id: Optional[str], capability: GoogleCapability) -> Any:
        if self._mock_service is not None:
            return self._mock_service
        if self.auth_manager is None:
            from jarvis.integrations.google.auth.manager import get_global_auth_manager
            self.auth_manager = get_global_auth_manager()
        creds = await self.auth_manager.get_credentials(account_id, required_capability=capability)
        acc_id = getattr(creds, "account_id", account_id or "default")
        if acc_id not in self._service_cache:
            from googleapiclient.discovery import build
            self._service_cache[acc_id] = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return self._service_cache[acc_id]


    async def search_messages(
        self,
        query: str,
        account_id: Optional[str] = None,
        limit: int = 10,
        page_token: Optional[str] = None,
    ) -> PaginatedResult[EmailSummary]:
        """Search messages matching Gmail search syntax."""
        await self.quota_manager.acquire("gmail")
        service = await self._get_service(account_id, GoogleCapability.GMAIL_READ)

        def _do_search():
            try:
                res = (
                    service.users()
                    .messages()
                    .list(userId="me", q=query, maxResults=limit, pageToken=page_token)
                    .execute()
                )
                msg_refs = res.get("messages", [])
                summaries: List[EmailSummary] = []
                for m in msg_refs:
                    msg_data = (
                        service.users()
                        .messages()
                        .get(userId="me", id=m["id"], format="metadata", metadataHeaders=["From", "Subject", "Date"])
                        .execute()
                    )
                    headers = {h["name"].lower(): h["value"] for h in msg_data.get("payload", {}).get("headers", [])}
                    from_val = headers.get("from", "Unknown")
                    subject_val = headers.get("subject", "(No Subject)")
                    date_val = headers.get("date", "")
                    summaries.append(
                        EmailSummary(
                            message_id=m["id"],
                            thread_id=m["threadId"],
                            from_address=from_val,
                            subject=subject_val,
                            received_at=date_val,
                            snippet=msg_data.get("snippet", ""),
                            labels=tuple(msg_data.get("labelIds", ())),
                        )
                    )
                return PaginatedResult(
                    items=tuple(summaries),
                    next_page_token=res.get("nextPageToken"),
                    total_estimate=res.get("resultSizeEstimate"),
                )
            except Exception as exc:
                raise normalize_google_error(exc, service="gmail")

        return await execute_with_retry(
            lambda: self.executor.run(_do_search),
            service="gmail",
            is_write=False,
        )

    async def get_message(self, message_id: str, account_id: Optional[str] = None) -> EmailMessage:
        """Fetch full cleaned plain text content of a message."""
        await self.quota_manager.acquire("gmail")
        service = await self._get_service(account_id, GoogleCapability.GMAIL_READ)

        def _do_get():
            try:
                res = service.users().messages().get(userId="me", id=message_id, format="full").execute()
                payload = res.get("payload", {})
                headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

                from_val = headers.get("from", "Unknown")
                to_val = tuple(x.strip() for x in headers.get("to", "").split(",") if x.strip())
                cc_val = tuple(x.strip() for x in headers.get("cc", "").split(",") if x.strip())
                subject_val = headers.get("subject", "(No Subject)")
                date_val = headers.get("date", "")

                body_text = ""
                attachments: List[AttachmentMetadata] = []

                # Recursive part extractor
                def extract_parts(part):
                    nonlocal body_text
                    mime = part.get("mimeType", "")
                    body = part.get("body", {})
                    data = body.get("data")
                    filename = part.get("filename")

                    if filename and body.get("attachmentId"):
                        attachments.append(
                            AttachmentMetadata(
                                attachment_id=body["attachmentId"],
                                filename=filename,
                                mime_type=mime,
                                size_bytes=body.get("size", 0),
                            )
                        )
                    elif mime == "text/plain" and data:
                        decoded = base64.urlsafe_b64decode(data.encode("ASCII")).decode("utf-8", errors="replace")
                        body_text += decoded + "\n"
                    elif "parts" in part:
                        for subpart in part["parts"]:
                            extract_parts(subpart)

                extract_parts(payload)
                if not body_text:
                    body_text = res.get("snippet", "")

                return EmailMessage(
                    message_id=message_id,
                    thread_id=res.get("threadId", ""),
                    from_address=from_val,
                    to_addresses=to_val,
                    cc_addresses=cc_val,
                    subject=subject_val,
                    received_at=date_val,
                    body_text=body_text.strip(),
                    snippet=res.get("snippet", ""),
                    labels=tuple(res.get("labelIds", ())),
                    attachments=tuple(attachments),
                )
            except Exception as exc:
                raise normalize_google_error(exc, service="gmail")

        return await execute_with_retry(
            lambda: self.executor.run(_do_get),
            service="gmail",
            is_write=False,
        )

    async def create_draft(
        self,
        to: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to_message_id: Optional[str] = None,
        account_id: Optional[str] = None,
    ) -> EmailDraft:
        """Create a new draft in Gmail."""
        await self.quota_manager.acquire("gmail")
        service = await self._get_service(account_id, GoogleCapability.GMAIL_COMPOSE)

        def _do_create():
            try:
                mime_msg = MIMEText(body)
                mime_msg["to"] = ", ".join(to)
                if cc:
                    mime_msg["cc"] = ", ".join(cc)
                if bcc:
                    mime_msg["bcc"] = ", ".join(bcc)
                mime_msg["subject"] = subject
                raw_encoded = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("ascii")

                draft_body = {"message": {"raw": raw_encoded}}
                res = service.users().drafts().create(userId="me", body=draft_body).execute()

                return EmailDraft(
                    draft_id=res["id"],
                    message_id=res.get("message", {}).get("id"),
                    to=tuple(to),
                    cc=tuple(cc or ()),
                    bcc=tuple(bcc or ()),
                    subject=subject,
                    body=body,
                    reply_to_message_id=reply_to_message_id,
                )
            except Exception as exc:
                raise normalize_google_error(exc, service="gmail")

        return await execute_with_retry(
            lambda: self.executor.run(_do_create),
            service="gmail",
            is_write=True,
        )

    async def send_draft(self, draft_id: str, account_id: Optional[str] = None) -> str:
        """Send an existing draft."""
        await self.quota_manager.acquire("gmail")
        service = await self._get_service(account_id, GoogleCapability.GMAIL_SEND)

        def _do_send():
            try:
                res = service.users().drafts().send(userId="me", body={"id": draft_id}).execute()
                return res["id"]  # provider message ID
            except Exception as exc:
                raise normalize_google_error(exc, service="gmail")

        return await execute_with_retry(
            lambda: self.executor.run(_do_send),
            service="gmail",
            is_write=True,
        )

    async def verify_message_exists(self, message_id: str, account_id: Optional[str] = None) -> bool:
        """Check if message exists on Gmail provider."""
        service = await self._get_service(account_id, GoogleCapability.GMAIL_READ)

        def _check():
            try:
                service.users().messages().get(userId="me", id=message_id, format="minimal").execute()
                return True
            except Exception:
                return False

        return await self.executor.run(_check)
