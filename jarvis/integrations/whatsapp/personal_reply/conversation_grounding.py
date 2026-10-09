"""Conservative same-thread grounding for factual follow-up drafts.

This is a draft safety check, not a command router. It never supplies facts or
authorizes an outgoing message. A short request for a progress update needs an
owner-sourced status before a personal reply can be drafted confidently.
"""
from __future__ import annotations

import re

from jarvis.integrations.whatsapp.personal_reply.models import Authorship, ChatLine, Direction


_UPDATE_REQUEST = re.compile(
    r"\b(?:updates?|status|progress|any news|what happened|enna aachu|enna achu)\b", re.I)
_OWNER_STATUS = re.compile(
    r"\b(?:done|completed?|finished|working on|in progress|started|fixed|ready|"
    r"mudich|pannitu|panren|aagiduchu|agiduchu)\b", re.I)


def missing_owner_status(current: str, thread: list[tuple[bool, str]]) -> bool:
    """Hold a short progress request when the recent thread has no owner status.

    Longer messages can contain their own answerable context. This deliberately
    errs toward owner review and never infers completion from a contact's words.
    """
    words = re.findall(r"\w+", current or "")
    if len(words) > 8 or not _UPDATE_REQUEST.search(current or ""):
        return False
    return not any(mine and _OWNER_STATUS.search(text or "") for mine, text in thread)


_CLARIFICATION = re.compile(
    r"(?:\?+|(?:purila|puriyala|enadhu|ennadhu|enna|what|huh)\s*[?.!]?)", re.I)
_TRUSTED_OWNER = {
    Authorship.USER_TYPED, Authorship.VERIFIED_MANUAL_OWNER_SEND,
    Authorship.USER_EDITED_AI_DRAFT, Authorship.VERIFIED_LEGACY_OWNER,
}


def owner_clarification(rows: list[ChatLine], before: float) -> str | None:
    """Return a short *review-only* clarification actually used with this contact.

    The timestamp cutoff keeps a replay from learning its held-out owner reply.
    Unknown, generated, and merely likely legacy messages cannot seed a draft.
    """
    candidates = [row for row in rows if row.direction == Direction.USER
                  and row.provenance in _TRUSTED_OWNER and row.timestamp < before
                  and _CLARIFICATION.fullmatch((row.text or "").strip())]
    if not candidates:
        return None
    # A clear phrase is easier to understand than a bare question mark. Within
    # each kind, use the owner's most recent verified wording for this contact.
    best = max(candidates, key=lambda row: (row.text.strip() != "?", row.timestamp))
    return best.text.strip()
