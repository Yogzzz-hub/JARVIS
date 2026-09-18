"""Data models for Gmail messages, drafts, and attachments."""
from __future__ import annotations

from typing import List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field


class AttachmentMetadata(BaseModel):
    """Metadata describing an email attachment without downloading full bytes."""
    model_config = ConfigDict(extra="forbid")

    attachment_id: str
    filename: str
    mime_type: str = "application/octet-stream"
    size_bytes: int = 0


class EmailSummary(BaseModel):
    """Concise representation of an email for search results and lists."""
    model_config = ConfigDict(extra="forbid")

    message_id: str
    thread_id: str
    from_address: str
    from_name: Optional[str] = None
    subject: str = "(No Subject)"
    received_at: str = ""
    snippet: str = ""
    labels: Tuple[str, ...] = Field(default_factory=tuple)
    has_attachments: bool = False


class EmailMessage(BaseModel):
    """Complete cleaned email content."""
    model_config = ConfigDict(extra="forbid")

    message_id: str
    thread_id: str
    from_address: str
    from_name: Optional[str] = None
    to_addresses: Tuple[str, ...] = Field(default_factory=tuple)
    cc_addresses: Tuple[str, ...] = Field(default_factory=tuple)
    subject: str = "(No Subject)"
    received_at: str = ""
    body_text: str = ""
    snippet: str = ""
    labels: Tuple[str, ...] = Field(default_factory=tuple)
    attachments: Tuple[AttachmentMetadata, ...] = Field(default_factory=tuple)


class EmailDraft(BaseModel):
    """Draft message representation."""
    model_config = ConfigDict(extra="forbid")

    draft_id: str
    message_id: Optional[str] = None
    to: Tuple[str, ...] = Field(default_factory=tuple)
    cc: Tuple[str, ...] = Field(default_factory=tuple)
    bcc: Tuple[str, ...] = Field(default_factory=tuple)
    subject: str = ""
    body: str = ""
    reply_to_message_id: Optional[str] = None
