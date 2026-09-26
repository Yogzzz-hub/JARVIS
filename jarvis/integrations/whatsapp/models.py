"""Data contracts and schemas for JARVIS WhatsApp Omnichannel Integration."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class NormalizedWhatsAppMessage(BaseModel):
    """Normalized typed message representation coming from the Baileys transport boundary."""
    model_config = ConfigDict(extra="ignore")

    channel: Literal["whatsapp"] = "whatsapp"
    message_id: str = Field(min_length=1)
    chat_id: str = Field(min_length=1)
    sender_id: str = Field(min_length=1)
    sender_display_name: str = "Unknown"
    timestamp: str
    type: Literal["text", "image", "document", "audio", "voice_note"] = "text"
    text: str = ""
    media_ref: Optional[Dict[str, Any]] = None
    reply_to: Optional[Dict[str, Any]] = None
    is_from_me: bool = False
    is_group: bool = False
    chat_name: str = ""          # group subject for group chats (so the owner can name a group explicitly)
    # READY, or PENDING_DECRYPTION for a "Waiting for this message" placeholder (never replied to)
    state: str = "READY"


class WhatsAppBridgeStatus(BaseModel):
    """Current connection and pairing state of the Baileys transport bridge."""
    model_config = ConfigDict(extra="ignore")

    state: Literal[
        "DISCONNECTED",
        "PAIRING_REQUIRED",
        "CONNECTING",
        "CONNECTED",
        "DEGRADED",
        "LOGGED_OUT",
    ] = "DISCONNECTED"
    account: Optional[str] = None
    qr: Optional[str] = None
    last_message_time: Optional[str] = None
    mode: Literal["OFF", "DRAFT_ONLY", "ALLOWLIST_AUTO_REPLY"] = "DRAFT_ONLY"
    voice_reply_enabled: bool = False
    pending_approvals: int = 0


class OutboundMessageDraft(BaseModel):
    """Structured draft representing a prepared outbound WhatsApp message."""
    model_config = ConfigDict(extra="ignore")

    draft_id: str
    chat_id: str
    recipient_name: str
    text: str
    media_path: Optional[str] = None
    media_mimetype: Optional[str] = None
    requires_confirmation: bool = True
    ticket_id: Optional[str] = None
    status: Literal["PENDING", "APPROVED", "REJECTED", "SENT", "FAILED"] = "PENDING"
    created_at: float = 0.0
