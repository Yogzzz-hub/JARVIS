"""WhatsApp Message Inbox, Urgency Classification, and Response Need Tracker.

Persists incoming/outgoing WhatsApp messages, automatically calculates urgency
and reply requirements, and provides concise summaries for voice and text interfaces.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jarvis.config import ROOT
from jarvis.integrations.whatsapp.models import NormalizedWhatsAppMessage

logger = logging.getLogger("jarvis.whatsapp.inbox")

URGENT_KEYWORDS = frozenset({
    "urgent", "asap", "emergency", "immediately", "call me now", "call me asap",
    "important", "deadline", "by today", "need this now", "critical", "right away",
    "at once", "respond quickly", "urgent reply", "where are you",
})

PASSIVE_ACKS = frozenset({
    "ok", "okay", "k", "kk", "cool", "great", "nice", "noted", "got it", "sure",
    "thanks", "thank you", "thx", "np", "no problem", "haha", "lol", "yep",
    "yeah", "done", "alright", "all right", "bye", "tc", "take care",
})

QUESTION_STARTERS = (
    "can you", "could you", "would you", "will you", "do you", "did you",
    "where", "when", "what", "why", "how", "who", "which", "are you", "is it",
    "please send", "please confirm", "please check", "let me know",
)


@dataclass
class InboxMessage:
    message_id: str
    chat_id: str
    sender_id: str
    sender_display_name: str
    timestamp: float
    type: str
    text: str
    is_from_me: bool
    is_read: bool
    needs_reply: bool
    urgency: str  # 'URGENT', 'NORMAL', 'LOW'
    summary: str
    replied: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "chat_id": self.chat_id,
            "sender_id": self.sender_id,
            "sender": self.sender_display_name,
            "timestamp": self.timestamp,
            "type": self.type,
            "text": self.text,
            "is_from_me": self.is_from_me,
            "is_read": self.is_read,
            "needs_reply": self.needs_reply,
            "urgency": self.urgency,
            "summary": self.summary,
            "replied": self.replied,
        }


class UrgencyClassifier:
    """Classifies message urgency and whether a reply is expected."""

    @classmethod
    def analyze(cls, text: str, is_from_me: bool = False) -> Tuple[str, bool, str]:
        """Returns (urgency, needs_reply, summary)."""
        clean = text.strip()
        if not clean:
            return "LOW", False, "Empty message"

        lower = clean.lower()
        norm_words = set(re.findall(r"\b\w+\b", lower))

        # Check urgency
        is_urgent = any(kw in lower for kw in URGENT_KEYWORDS)

        # Check if passive acknowledgment
        if lower.rstrip(".!?") in PASSIVE_ACKS:
            summary = clean[:60]
            return "LOW", False, summary

        # Check question / request intent
        has_question_mark = "?" in clean
        has_question_phrase = any(lower.startswith(qs) or f" {qs}" in lower for qs in QUESTION_STARTERS)
        is_request = has_question_mark or has_question_phrase or is_urgent

        if is_from_me:
            needs_reply = False
            urgency = "LOW"
        else:
            needs_reply = bool(is_urgent or is_request)
            if is_urgent:
                urgency = "URGENT"
            elif is_request:
                urgency = "NORMAL"
            else:
                urgency = "LOW"

        # Generate 1-line summary
        if len(clean) > 80:
            summary = clean[:77] + "..."
        else:
            summary = clean

        return urgency, needs_reply, summary


class WhatsAppInbox:
    """SQLite-backed message inbox for WhatsApp with urgency categorization."""

    _instance: Optional[WhatsAppInbox] = None

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            db_path = ROOT / "data/whatsapp_inbox.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @classmethod
    def get_default(cls) -> WhatsAppInbox:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS whatsapp_messages (
                    message_id TEXT PRIMARY KEY,
                    chat_id TEXT NOT NULL,
                    sender_id TEXT NOT NULL,
                    sender_display_name TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    type TEXT NOT NULL,
                    text TEXT NOT NULL,
                    is_from_me INTEGER NOT NULL DEFAULT 0,
                    is_read INTEGER NOT NULL DEFAULT 0,
                    needs_reply INTEGER NOT NULL DEFAULT 0,
                    urgency TEXT NOT NULL DEFAULT 'LOW',
                    summary TEXT NOT NULL,
                    replied INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wa_chat ON whatsapp_messages(chat_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wa_needs_reply ON whatsapp_messages(needs_reply, replied);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wa_urgency ON whatsapp_messages(urgency);")
            conn.commit()

    def add_message(
        self,
        message: NormalizedWhatsAppMessage,
        is_from_me: bool = False,
    ) -> InboxMessage:
        """Stores message and computes urgency and reply requirement."""
        text = message.text or ""
        urgency, needs_reply, summary = UrgencyClassifier.analyze(text, is_from_me=is_from_me)

        ts = time.time()
        if message.timestamp:
            try:
                ts = float(message.timestamp)
            except ValueError:
                ts = time.time()

        item = InboxMessage(
            message_id=message.message_id,
            chat_id=message.chat_id,
            sender_id=message.sender_id,
            sender_display_name=message.sender_display_name or message.sender_id.split("@")[0],
            timestamp=ts,
            type=message.type,
            text=text,
            is_from_me=is_from_me,
            is_read=is_from_me,  # own messages are inherently read
            needs_reply=needs_reply,
            urgency=urgency,
            summary=summary,
            replied=False,
        )

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO whatsapp_messages (
                    message_id, chat_id, sender_id, sender_display_name,
                    timestamp, type, text, is_from_me, is_read,
                    needs_reply, urgency, summary, replied
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.message_id,
                    item.chat_id,
                    item.sender_id,
                    item.sender_display_name,
                    item.timestamp,
                    item.type,
                    item.text,
                    1 if item.is_from_me else 0,
                    1 if item.is_read else 0,
                    1 if item.needs_reply else 0,
                    item.urgency,
                    item.summary,
                    1 if item.replied else 0,
                ),
            )
            conn.commit()

        logger.info(
            "Saved WhatsApp message %s from %s (urgency=%s, needs_reply=%s)",
            item.message_id, item.sender_display_name, item.urgency, item.needs_reply,
        )
        return item

    def get_messages_needing_reply(self, limit: int = 10) -> List[InboxMessage]:
        """Returns pending messages requiring attention ordered by urgency and time."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM whatsapp_messages
                WHERE needs_reply = 1 AND replied = 0 AND is_from_me = 0
                ORDER BY
                    CASE urgency
                        WHEN 'URGENT' THEN 1
                        WHEN 'NORMAL' THEN 2
                        ELSE 3
                    END,
                    timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [self._row_to_msg(r) for r in rows]

    def get_unread(self, limit: int = 10) -> List[InboxMessage]:
        """Returns unread incoming messages."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM whatsapp_messages
                WHERE is_read = 0 AND is_from_me = 0
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [self._row_to_msg(r) for r in cursor.fetchall()]

    def get_recent(self, limit: int = 10) -> List[InboxMessage]:
        """Returns most recent messages regardless of read status."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM whatsapp_messages ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
            return [self._row_to_msg(r) for r in cursor.fetchall()]

    def get_chat_history(self, chat_id: str, limit: int = 8) -> List[InboxMessage]:
        """Most recent messages of one conversation, oldest first (for reply context)."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM whatsapp_messages WHERE chat_id = ? OR sender_id = ? ORDER BY timestamp DESC LIMIT ?",
                (chat_id, chat_id, limit),
            )
            return list(reversed([self._row_to_msg(r) for r in cursor.fetchall()]))

    def find_latest_incoming(self, who: str = "") -> Optional[InboxMessage]:
        """Latest message not sent by the owner, optionally from a sender name / number / JID."""
        who_clean = (who or "").strip().casefold()
        digits = "".join(ch for ch in who_clean if ch.isdigit())
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM whatsapp_messages WHERE is_from_me = 0 ORDER BY needs_reply DESC, timestamp DESC LIMIT 200"
            ).fetchall()
        candidates = [self._row_to_msg(r) for r in rows]
        if not who_clean:
            pending = [m for m in candidates if m.needs_reply and not m.replied]
            return (pending or candidates or [None])[0]
        for msg in candidates:
            name = (msg.sender_display_name or "").casefold()
            if who_clean == name or who_clean in name.split() or (len(who_clean) >= 3 and name.startswith(who_clean)):
                return msg
            if digits and len(digits) >= 6 and digits in "".join(ch for ch in msg.sender_id if ch.isdigit()):
                return msg
            if who_clean in (msg.chat_id.casefold(), msg.sender_id.casefold()):
                return msg
        return None

    def mark_as_replied(self, chat_id: str) -> int:
        """Marks all pending messages in a given chat as replied."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                UPDATE whatsapp_messages
                SET replied = 1, is_read = 1
                WHERE (chat_id = ? OR sender_id = ?) AND needs_reply = 1
                """,
                (chat_id, chat_id),
            )
            conn.commit()
            return cursor.rowcount

    def mark_as_read(self, message_id: str) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE whatsapp_messages SET is_read = 1 WHERE message_id = ?",
                (message_id,),
            )
            conn.commit()

    def summarize_inbox(self) -> Dict[str, Any]:
        """
        Produces a rich structured summary of the inbox with priority breakdown
        and a speech-optimized string for voice output.
        """
        pending = self.get_messages_needing_reply(limit=20)
        urgent = [m for m in pending if m.urgency == "URGENT"]
        normal = [m for m in pending if m.urgency == "NORMAL"]

        total_pending = len(pending)

        # Build natural spoken text
        if total_pending == 0:
            spoken = "You have no unread WhatsApp messages requiring a reply."
        else:
            parts = []
            if urgent:
                u_senders = ", ".join(f"{m.sender_display_name} saying '{m.summary}'" for m in urgent[:2])
                parts.append(f"You have {len(urgent)} urgent message{'s' if len(urgent)>1 else ''}: from {u_senders}")
            if normal:
                n_senders = ", ".join(f"{m.sender_display_name} asking '{m.summary}'" for m in normal[:2])
                parts.append(f"{len(normal)} message{'s' if len(normal)>1 else ''} needing a response: from {n_senders}")
            spoken = ". ".join(parts) + ". Would you like to reply to any of them?"

        return {
            "total_pending": total_pending,
            "urgent_count": len(urgent),
            "normal_count": len(normal),
            "urgent_messages": [m.to_dict() for m in urgent],
            "normal_messages": [m.to_dict() for m in normal],
            "spoken_summary": spoken,
        }

    def _row_to_msg(self, row: sqlite3.Row) -> InboxMessage:
        return InboxMessage(
            message_id=row["message_id"],
            chat_id=row["chat_id"],
            sender_id=row["sender_id"],
            sender_display_name=row["sender_display_name"],
            timestamp=row["timestamp"],
            type=row["type"],
            text=row["text"],
            is_from_me=bool(row["is_from_me"]),
            is_read=bool(row["is_read"]),
            needs_reply=bool(row["needs_reply"]),
            urgency=row["urgency"],
            summary=row["summary"],
            replied=bool(row["replied"]),
        )
