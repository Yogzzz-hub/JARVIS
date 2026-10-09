"""Offline Stage 2.5 short-reply policy. No tool or production router access.

A confirmation decision identifies a pending ticket; it does not approve or
execute it. A future executor must atomically revalidate that exact ticket.
"""
from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass


ACK_WORDS = frozenset({"yes", "yeah", "ok", "okay", "seri", "sari", "ama", "aama", "ஆம்", "ஆமாம்", "சரி", "ஓகே"})
NEGATIVE_WORDS = frozenset({"no", "nope", "illa", "illai", "இல்லை", "வேண்டாம்", "venam", "vendam"})
MAX_PENDING_AGE_SECONDS = 90


@dataclass(frozen=True)
class PendingInteraction:
    kind: str  # CONFIRMATION or CLARIFICATION
    reference_id: str
    created_at: float
    channel: str
    owner_id: str
    action_fingerprint: str = ""
    consumed: bool = False


@dataclass(frozen=True)
class ConversationDecision:
    speech_act: str
    resolution: str
    reference_id: str | None = None
    action_fingerprint: str | None = None
    should_execute: bool = False


def _short_reply(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold().strip()
    return re.sub(r"[\s.,!?।…]+", " ", normalized).strip()


def resolve_short_reply(
    text: str,
    *,
    pending_confirmation: PendingInteraction | None = None,
    pending_clarification: PendingInteraction | None = None,
    channel: str,
    owner_id: str,
    now: float | None = None,
) -> ConversationDecision | None:
    """Resolve only short acknowledgements/denials; return None otherwise.

    Pending clarification has priority if both are present. The caller must
    provide authenticated channel and owner identity, not values from text.
    """
    reply = _short_reply(text)
    if reply not in ACK_WORDS | NEGATIVE_WORDS:
        return None
    current = time.time() if now is None else now

    def valid(item: PendingInteraction | None, kind: str) -> bool:
        return bool(
            item and item.kind == kind and item.reference_id and
            item.channel == channel and item.owner_id == owner_id and
            not item.consumed and 0 <= current - item.created_at <= MAX_PENDING_AGE_SECONDS
        )

    if valid(pending_clarification, "CLARIFICATION"):
        return ConversationDecision("ACKNOWLEDGEMENT", "CLARIFICATION_RESPONSE", pending_clarification.reference_id)
    if valid(pending_confirmation, "CONFIRMATION"):
        if reply in NEGATIVE_WORDS:
            return ConversationDecision("NEGATED_COMMAND", "REJECT_PENDING", pending_confirmation.reference_id)
        if pending_confirmation.action_fingerprint:
            return ConversationDecision("CONFIRMATION", "CONFIRM_PENDING", pending_confirmation.reference_id, pending_confirmation.action_fingerprint)
    return ConversationDecision("ACKNOWLEDGEMENT", "NO_ACTION")


def resolve_from_working_context(
    text: str, working_context: object, *, channel: str, owner_id: str, now: float | None = None
) -> ConversationDecision | None:
    """Read pending state without trusting legacy, unbound ticket records.

    Existing WorkingContext records lack authenticated owner/channel bindings;
    they therefore cannot grant confirmation through this offline policy.
    """
    confirmation = getattr(working_context, "pending_confirmation", None)
    clarification = getattr(working_context, "pending_clarification", None)
    return resolve_short_reply(
        text,
        pending_confirmation=confirmation if isinstance(confirmation, PendingInteraction) else None,
        pending_clarification=clarification if isinstance(clarification, PendingInteraction) else None,
        channel=channel,
        owner_id=owner_id,
        now=now,
    )
