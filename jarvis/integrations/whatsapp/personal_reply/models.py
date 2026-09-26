"""Contracts for the WhatsApp personal reply agent (contact-specific style + timed auto-reply)."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Optional


class ReplyMode(StrEnum):
    OFF = "OFF"
    SUGGEST_ONLY = "SUGGEST_ONLY"          # draft shown in the UI, never sent
    ASK_BEFORE_SEND = "ASK_BEFORE_SEND"    # draft sent only after the owner approves it
    AUTO_REPLY_UNTIL = "AUTO_REPLY_UNTIL"  # sent automatically while a time-boxed grant is active


class GrantScope(StrEnum):
    CONTACT = "CONTACT"
    CONTACTS = "CONTACTS"
    ALL_DIRECT_CONTACTS = "ALL_DIRECT_CONTACTS"  # never includes groups


class Direction(StrEnum):
    USER = "USER"        # written by the account owner
    CONTACT = "CONTACT"  # written by the other person


class ExampleSource(StrEnum):
    IMPORT = "IMPORT"            # owner-authored message from an imported chat
    LIVE_USER = "LIVE_USER"      # owner typed it themselves on WhatsApp
    USER_EDITED = "USER_EDITED"  # owner edited an AI suggestion before sending
    APPROVED = "APPROVED"        # owner explicitly approved an AI draft as a good example
    # Autonomous AI replies are deliberately NOT a source: training on them causes style drift.


class Outcome(StrEnum):
    IGNORED_GROUP = "IGNORED_GROUP"
    IGNORED_OWN = "IGNORED_OWN"
    PENDING_DECRYPTION = "PENDING_DECRYPTION"
    DUPLICATE = "DUPLICATE"
    QUEUED = "QUEUED"                    # waiting for the coalescing window
    NOT_ENABLED = "NOT_ENABLED"          # no mode / grant for this contact
    EXPIRED = "EXPIRED"
    SUGGESTED = "SUGGESTED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    NEEDS_USER_REVIEW = "NEEDS_USER_REVIEW"
    SENT = "SENT"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    UNCERTAIN = "UNCERTAIN"
    AMBIGUOUS_CONTACT = "AMBIGUOUS_CONTACT"
    OWNER_REPLIED = "OWNER_REPLIED"      # owner answered manually before JARVIS did


@dataclass
class ChatLine:
    """One message from an imported or live conversation."""
    timestamp: float
    sender: str
    direction: Direction
    text: str
    message_id: str = ""
    reply_to: str = ""
    origin: str = ""   # import id, or "live" for messages seen live through the connector


@dataclass
class ReplyExample:
    """What the contact said (context) and how the OWNER answered (reply)."""
    contact_id: str
    context: str
    reply: str
    timestamp: float
    source: ExampleSource = ExampleSource.IMPORT
    split: str = "TRAIN"   # TRAIN / DEV / HOLDOUT
    example_id: int = 0


@dataclass
class ContactStyleProfile:
    contact_id: str
    display_name: str = ""
    preferred_language: str = "ENGLISH"     # ENGLISH / TANGLISH / MIXED
    english_ratio: float = 1.0              # share of the owner's messages that are plain English
    tanglish_ratio: float = 0.0             # share that contain Tanglish (TANGLISH or MIXED)
    avg_message_length: float = 0.0         # words
    median_message_length: float = 0.0
    emoji_frequency: float = 0.0            # emojis per message
    common_emojis: list[str] = field(default_factory=list)
    punctuation_style: str = "minimal"      # none / minimal / standard / expressive
    capitalization_style: str = "lowercase" # lowercase / sentence / mixed
    greeting_patterns: list[str] = field(default_factory=list)
    closing_patterns: list[str] = field(default_factory=list)
    common_words: list[str] = field(default_factory=list)
    common_tanglish_phrases: list[str] = field(default_factory=list)
    formality: str = "CASUAL"               # VERY_CASUAL / CASUAL / NEUTRAL / PROFESSIONAL
    humor_level: str = "LOW"                # LOW / MEDIUM / HIGH
    directness: str = "MEDIUM"
    typical_reply_length: str = "1 sentence"
    question_style: str = "rare"
    acknowledgement_style: list[str] = field(default_factory=list)
    response_patterns: list[str] = field(default_factory=list)
    example_message_ids: list[str] = field(default_factory=list)
    messages_analyzed: int = 0
    confidence: float = 0.0
    profile_version: int = 0
    updated_at: float = field(default_factory=time.time)
    preferences: dict[str, Any] = field(default_factory=dict)  # explicit owner feedback ("more English", "shorter")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContactStyleProfile":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    # Effective values after explicit owner feedback ------------------------------------------------
    def effective_tanglish_ratio(self) -> float:
        shift = float(self.preferences.get("tanglish_shift", 0.0))
        return max(0.0, min(1.0, self.tanglish_ratio + shift))

    def effective_length_words(self) -> float:
        factor = float(self.preferences.get("length_factor", 1.0))
        return max(1.0, self.median_message_length * factor)

    def effective_formality(self) -> str:
        order = ["VERY_CASUAL", "CASUAL", "NEUTRAL", "PROFESSIONAL"]
        idx = order.index(self.formality) if self.formality in order else 1
        idx = max(0, min(len(order) - 1, idx + int(self.preferences.get("formality_shift", 0))))
        return order[idx]

    def length_band(self) -> tuple[int, int]:
        """Acceptable reply length in words (naturalness beats exact imitation)."""
        med = self.effective_length_words()
        lo = 1
        hi = max(4, int(round(med * 2.5)) + 2)
        return lo, hi

    def summary(self) -> dict[str, Any]:
        tang = round(100 * self.effective_tanglish_ratio())
        return {
            "language": f"{tang}% Tanglish / {100 - tang}% English",
            "preferred_language": self.preferred_language,
            "tone": self.effective_formality().replace("_", " ").title(),
            "typical_length": self.typical_reply_length,
            "emoji": "High" if self.emoji_frequency >= 0.8 else "Medium" if self.emoji_frequency >= 0.25 else "Low",
            "common_emojis": self.common_emojis[:5],
            "messages_analyzed": self.messages_analyzed,
            "confidence": round(self.confidence, 2),
            "profile_version": self.profile_version,
        }


@dataclass
class AutoReplyGrant:
    grant_id: str
    scope: GrantScope
    contact_ids: list[str]
    enabled_at: float
    expires_at: float
    mode: ReplyMode = ReplyMode.AUTO_REPLY_UNTIL
    granted_by_user: bool = True
    revoked_at: Optional[float] = None
    include_untrained: bool = False

    def active(self, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        return self.revoked_at is None and self.enabled_at <= now < self.expires_at

    def covers(self, contact_id: str) -> bool:
        # For ALL_DIRECT_CONTACTS, ``contact_ids`` lists people the owner later excluded ("stop replying to her").
        if self.scope == GrantScope.ALL_DIRECT_CONTACTS:
            return contact_id not in self.contact_ids
        return contact_id in self.contact_ids


@dataclass
class IncomingBatch:
    """One or more messages from the same direct chat, understood together."""
    contact_id: str
    chat_id: str
    display_name: str
    message_ids: list[str]
    texts: list[str]
    received_at: float

    @property
    def last_message_id(self) -> str:
        return self.message_ids[-1]

    @property
    def text(self) -> str:
        return "\n".join(t for t in self.texts if t)


@dataclass
class ReplyCandidate:
    text: str
    understood: bool
    model_confidence: float
    language_mode: str
    examples_used: list[int] = field(default_factory=list)
    prompt_chars: int = 0
    generator: str = "llm"


@dataclass
class QualityReport:
    relevance: float
    style_match: float
    language_match: float
    context_consistency: float
    hallucination_risk: float
    sensitive_action_risk: float
    reasons: list[str] = field(default_factory=list)
    sensitive_topics: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.reasons

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["passed"] = self.passed
        return d
