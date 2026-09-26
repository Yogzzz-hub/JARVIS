"""Placeholder / undecrypted-message detection.

WhatsApp shows "Waiting for this message. This may take a while." (and similar) when a message
could not be decrypted yet. Such events are NEVER content: no reply, no read/replied marking.
"""
from __future__ import annotations

import re
from typing import Any

PLACEHOLDER_TEXT = re.compile(
    r"^\s*(?:waiting for this message\.?(?:\s*this may take a while\.?)?|"
    r"this message couldn'?t (?:load|be decrypted)|message (?:not available|unavailable)|"
    r"\[?(?:ciphertext|encrypted message|decryption (?:pending|failed))\]?|"
    r"<pending decryption>|null)\s*$", re.I)

PENDING_STATES = {"PENDING_DECRYPTION", "CIPHERTEXT", "SYNC_PENDING", "UNDECRYPTED", "ENCRYPTED"}


def is_placeholder(message: Any) -> bool:
    """True when the event has no real decrypted body yet (must wait for the update event)."""
    state = str(getattr(message, "state", "") or "").upper()
    if state in PENDING_STATES:
        return True
    mtype = getattr(message, "type", "text")
    text = (getattr(message, "text", "") or "").strip()
    if mtype == "text" and not text:
        return True
    return bool(text and PLACEHOLDER_TEXT.match(text))


def is_group_chat(chat_id: str) -> bool:
    """Structural group gate: groups, broadcast lists, status and channels are never direct chats."""
    cid = (chat_id or "").lower()
    return (cid.endswith("@g.us") or cid.endswith("@broadcast") or cid.endswith("@newsletter")
            or cid.startswith("status@") or cid.endswith("@temp") or not cid)
