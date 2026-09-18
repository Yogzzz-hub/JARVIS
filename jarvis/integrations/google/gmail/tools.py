"""Native typed tools for Gmail integration."""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple
from pydantic import Field

from jarvis.integrations.google.common.content_trust import ExternalData, ExternalSourceType
from jarvis.integrations.google.gmail.client import GmailClient
from jarvis.integrations.google.gmail.models import EmailDraft, EmailMessage, EmailSummary
from jarvis.integrations.google.gmail.verifier import GmailVerifier
from jarvis.tools.base import (
    Contract,
    ExecutionMethod,
    IdempotencyClass,
    RiskLevel,
    Tool,
    ToolDefinition,
    ToolResult,
    VerificationResult,
)

# ----------------- CONTRACTS -----------------

class GmailSearchInput(Contract):
    query: str = Field(min_length=1, max_length=512, description="Gmail search query string")
    account_id: Optional[str] = None
    limit: int = Field(default=5, ge=1, le=50)


class GmailSearchOutput(Contract):
    query: str
    results: Tuple[EmailSummary, ...]
    count: int


class GmailGetMessageInput(Contract):
    message_id: str = Field(min_length=1, max_length=128)
    account_id: Optional[str] = None


class GmailGetMessageOutput(Contract):
    message: EmailMessage
    quarantined_content: str


class GmailListRecentInput(Contract):
    account_id: Optional[str] = None
    limit: int = Field(default=5, ge=1, le=50)


class GmailListRecentOutput(Contract):
    messages: Tuple[EmailSummary, ...]
    count: int


class GmailCreateDraftInput(Contract):
    to: Tuple[str, ...] = Field(min_length=1, description="Recipient email addresses")
    subject: str = Field(max_length=256)
    body: str = Field(min_length=1, description="Body text of email")
    cc: Tuple[str, ...] = Field(default_factory=tuple)
    bcc: Tuple[str, ...] = Field(default_factory=tuple)
    reply_to_message_id: Optional[str] = None
    account_id: Optional[str] = None


class GmailCreateDraftOutput(Contract):
    draft: EmailDraft
    created: bool
    summary: str


class GmailSendDraftInput(Contract):
    draft_id: str = Field(min_length=1, max_length=128)
    to_recipient: str = Field(min_length=1, description="Confirmed recipient address")
    subject: str = Field(description="Confirmed subject line")
    account_id: Optional[str] = None


class GmailSendDraftOutput(Contract):
    provider_message_id: str
    recipient: str
    subject: str
    sent: bool


# ----------------- TOOLS -----------------

class GmailSearchTool(Tool):
    definition = ToolDefinition(
        name="gmail_search",
        description="Search Gmail messages using standard query syntax (e.g. from:professor, subject:NLP).",
        input_model=GmailSearchInput,
        output_model=GmailSearchOutput,
        read_only=True,
        requires_confirmation=False,
        risk=RiskLevel.READ_ONLY,
        execution_method=ExecutionMethod.API,
        idempotency=IdempotencyClass.IDEMPOTENT,
        tags=("gmail", "email", "search", "google"),
    )

    def __init__(self, client: Any) -> None:
        self.client = client

    async def run(self, input_data: GmailSearchInput, context: Any = None) -> ToolResult:
        paginated = await self.client.search_messages(
            query=input_data.query,
            account_id=input_data.account_id,
            limit=input_data.limit,
        )
        out = GmailSearchOutput(
            query=input_data.query,
            results=paginated.items,
            count=len(paginated.items),
        )
        return ToolResult(
            success=True,
            data=out.model_dump(mode="json"),
            tool_name=self.definition.name,
        )


class GmailGetMessageTool(Tool):
    definition = ToolDefinition(
        name="gmail_get_message",
        description="Fetch cleaned text content of an email message. Content is quarantined as untrusted data.",
        input_model=GmailGetMessageInput,
        output_model=GmailGetMessageOutput,
        read_only=True,
        requires_confirmation=False,
        risk=RiskLevel.READ_ONLY,
        execution_method=ExecutionMethod.API,
        idempotency=IdempotencyClass.IDEMPOTENT,
        tags=("gmail", "email", "read", "google"),
    )

    def __init__(self, client: Any) -> None:
        self.client = client

    async def run(self, input_data: GmailGetMessageInput, context: Any = None) -> ToolResult:
        msg = await self.client.get_message(input_data.message_id, account_id=input_data.account_id)
        # Quarantine external content
        ext_data = ExternalData.create(
            source=ExternalSourceType.GMAIL,
            resource_id=msg.message_id,
            content=msg.body_text,
        )
        out = GmailGetMessageOutput(
            message=msg,
            quarantined_content=ext_data.format_for_display_or_llm(),
        )
        return ToolResult(
            success=True,
            data=out.model_dump(mode="json"),
            tool_name=self.definition.name,
        )


class GmailListRecentTool(Tool):
    definition = ToolDefinition(
        name="gmail_list_recent",
        description="List the latest N email messages from the inbox.",
        input_model=GmailListRecentInput,
        output_model=GmailListRecentOutput,
        read_only=True,
        requires_confirmation=False,
        risk=RiskLevel.READ_ONLY,
        execution_method=ExecutionMethod.API,
        idempotency=IdempotencyClass.IDEMPOTENT,
        tags=("gmail", "email", "list", "google"),
    )

    def __init__(self, client: Any) -> None:
        self.client = client

    async def run(self, input_data: GmailListRecentInput, context: Any = None) -> ToolResult:
        paginated = await self.client.search_messages(
            query="in:inbox",
            account_id=input_data.account_id,
            limit=input_data.limit,
        )
        out = GmailListRecentOutput(
            messages=paginated.items,
            count=len(paginated.items),
        )
        return ToolResult(
            success=True,
            data=out.model_dump(mode="json"),
            tool_name=self.definition.name,
        )


class GmailCreateDraftTool(Tool):
    definition = ToolDefinition(
        name="gmail_create_draft",
        description="Create an email draft in Gmail without sending it.",
        input_model=GmailCreateDraftInput,
        output_model=GmailCreateDraftOutput,
        read_only=False,
        requires_confirmation=False,
        risk=RiskLevel.REVERSIBLE,
        execution_method=ExecutionMethod.API,
        idempotency=IdempotencyClass.VERIFY_BEFORE_RETRY,
        tags=("gmail", "email", "draft", "google"),
    )

    def __init__(self, client: Any) -> None:
        self.client = client

    async def run(self, input_data: GmailCreateDraftInput, context: Any = None) -> ToolResult:
        draft = await self.client.create_draft(
            to=list(input_data.to),
            subject=input_data.subject,
            body=input_data.body,
            cc=list(input_data.cc),
            bcc=list(input_data.bcc),
            reply_to_message_id=input_data.reply_to_message_id,
            account_id=input_data.account_id,
        )
        out = GmailCreateDraftOutput(
            draft=draft,
            created=True,
            summary=f"Draft created for {', '.join(draft.to)} with subject '{draft.subject}'",
        )
        return ToolResult(
            success=True,
            data=out.model_dump(mode="json"),
            tool_name=self.definition.name,
        )


class GmailSendDraftTool(Tool):
    definition = ToolDefinition(
        name="gmail_send_draft",
        description="Send an existing Gmail draft to recipients. Requires user policy confirmation.",
        input_model=GmailSendDraftInput,
        output_model=GmailSendDraftOutput,
        read_only=False,
        requires_confirmation=True,
        risk=RiskLevel.EXTERNAL_EFFECT,
        execution_method=ExecutionMethod.API,
        idempotency=IdempotencyClass.NON_IDEMPOTENT,
        tags=("gmail", "email", "send", "google"),
    )

    def __init__(self, client: Any) -> None:
        self.client = client
        self.verifier = GmailVerifier(client)

    def human_confirmation_prompt(self, input_data: GmailSendDraftInput) -> str:
        return f"Send this email to {input_data.to_recipient} with subject '{input_data.subject}'?"

    async def run(self, input_data: GmailSendDraftInput, context: Any = None) -> ToolResult:

        provider_msg_id = await self.client.send_draft(
            draft_id=input_data.draft_id,
            account_id=input_data.account_id,
        )
        out = GmailSendDraftOutput(
            provider_message_id=provider_msg_id,
            recipient=input_data.to_recipient,
            subject=input_data.subject,
            sent=True,
        )
        return ToolResult(
            success=True,
            data=out.model_dump(mode="json"),
            tool_name=self.definition.name,
        )
