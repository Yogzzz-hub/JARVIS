"""WhatsApp Message Inbox, Urgency Classification, and Response Need Tracker.

Persists incoming/outgoing WhatsApp messages, automatically calculates urgency
and reply requirements, and provides concise summaries for voice and text interfaces.
"""

from __future__ import annotations

import logging
import json
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime
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

# Tanglish questions and requests ("Ena man panra", "eppo varuva", "file anuppu"): as much a question as "what's up?".
_TANGLISH_QUESTION = re.compile(r"\b(?:enna|ena|yenna|epdi|eppadi|epadi|eppo|epo|eppa|enga|yenga|yen|yaaru|yaru|yaar|evlo|"
                                r"evvalavu|ethana|edhuku|ethuku|edhukku|ethukku|ennachu|enachu)\b")
_TANGLISH_REQUEST = re.compile(r"\b(?:anuppu|anupu|anuppunga|sollu|sollunga|kudu|kudunga|call pannu|paaru|paarunga|"
                               r"pannunga|vaanga|vanga)\b")

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
    chat_name: str = ""  # group subject ("" for one-to-one chats)

    @property
    def is_group(self) -> bool:
        return WhatsAppInbox.is_group_chat(self.chat_id)

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
            "chat_name": self.chat_name,
            "is_group": self.is_group,
        }


_URL = re.compile(r"(?:https?://|www\.)\S+", re.I)


def _domain(url: str) -> str:
    host = re.sub(r"^(?:https?://)?(?:www\.)?", "", url, flags=re.I).split("/")[0].split("?")[0]
    return host.lower() or "a website"


def describe_message(text: str, words: int = 14) -> str:
    """Speakable description of a message: links become "a link from dribbble.com", long text is shortened."""
    t = " ".join((text or "").split())
    urls = _URL.findall(t)
    rest = " ".join(_URL.sub(" ", t).split()).strip(" -:,")
    if urls and not rest:
        domains = list(dict.fromkeys(_domain(u) for u in urls))
        return (f"a link from {domains[0]}" if len(urls) == 1 else
                f"{len(urls)} links ({', '.join(domains[:2])})")
    parts = rest.split(" ")
    short = rest if len(parts) <= words else " ".join(parts[:words]) + "..."
    return f'"{short}"' + (f" (with a link from {_domain(urls[0])})" if urls else "")


class UrgencyClassifier:
    """Classifies message urgency and whether a reply is expected."""

    @classmethod
    def analyze(cls, text: str, is_from_me: bool = False) -> Tuple[str, bool, str]:
        """Returns (urgency, needs_reply, summary)."""
        clean = text.strip()
        if not clean:
            return "LOW", False, "Empty message"
        urls = _URL.findall(clean)
        if urls:
            # A link's "?" is a query string, not a question: judge only the words around it.
            words = " ".join(_URL.sub(" ", clean).split())
            if not words:
                return "LOW", False, f"Shared a link from {_domain(urls[0])}"
            urgency, needs_reply, _ = cls.analyze(words, is_from_me=is_from_me)
            return urgency, needs_reply, (clean[:77] + "...") if len(clean) > 80 else clean

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
        tanglish = bool(_TANGLISH_QUESTION.search(lower) or _TANGLISH_REQUEST.search(lower))
        is_request = has_question_mark or has_question_phrase or tanglish or is_urgent

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
        self._sync_event = threading.Event()
        self._intelligence_lock = threading.RLock()
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

    def contains_message(self, message_id: str, chat_id: str) -> bool:
        """True only after this exact message is durable in the canonical inbox."""
        if not message_id or not chat_id:
            return False
        with self._get_conn() as conn:
            return conn.execute("SELECT 1 FROM whatsapp_messages WHERE message_id=? AND chat_id=?",
                                (message_id, chat_id)).fetchone() is not None

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
            cols = {r[1] for r in conn.execute("PRAGMA table_info(whatsapp_messages)").fetchall()}
            if "chat_name" not in cols:
                conn.execute("ALTER TABLE whatsapp_messages ADD COLUMN chat_name TEXT NOT NULL DEFAULT ''")
            # WhatsApp's own unread badge per chat, reported by the bridge (what the phone shows).
            conn.execute("""
                CREATE TABLE IF NOT EXISTS whatsapp_chats (
                    chat_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL DEFAULT '',
                    unread INTEGER NOT NULL DEFAULT 0,
                    last_ts REAL NOT NULL DEFAULT 0,
                    is_group INTEGER NOT NULL DEFAULT 0,
                    last_text TEXT NOT NULL DEFAULT '',
                    last_sender TEXT NOT NULL DEFAULT '',
                    last_from_me INTEGER NOT NULL DEFAULT 0,
                    updated REAL NOT NULL DEFAULT 0
                )
            """)
            conn.execute("CREATE TABLE IF NOT EXISTS whatsapp_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            if conn.execute("PRAGMA user_version").fetchone()[0] < 1:
                # Before unread tracking, only answered questions were ever marked read: everything older than a
                # day would otherwise count as unread forever.
                conn.execute("UPDATE whatsapp_messages SET is_read = 1 WHERE is_from_me = 0 AND timestamp < ?",
                             (time.time() - 24 * 3600,))
                conn.execute("PRAGMA user_version = 1")
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
        is_from_me = bool(is_from_me or getattr(message, "is_from_me", False))
        text = message.text or ""
        urgency, needs_reply, summary = UrgencyClassifier.analyze(text, is_from_me=is_from_me)

        ts = self._parse_ts(message.timestamp)

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
            chat_name=(getattr(message, "chat_name", "") or "").strip(),
        )

        if message.state != "READY":
            from jarvis.integrations.whatsapp.incoming_trace import trace_incoming
            trace_incoming(stage="sqlite", event_type="incoming_message", message_id=item.message_id,
                           chat_jid=item.chat_id, sqlite_result="SKIPPED_PENDING_DECRYPTION")
            return item

        with self._get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            prior = conn.execute("SELECT chat_id FROM whatsapp_messages WHERE message_id=?", (item.message_id,)).fetchone()
            if prior and prior[0] != item.chat_id:
                raise ValueError("Message identity cannot change thread")
            # a message seen again (history sync, late delivery) keeps its read / replied state
            conn.execute(
                """
                INSERT INTO whatsapp_messages (
                    message_id, chat_id, sender_id, sender_display_name,
                    timestamp, type, text, is_from_me, is_read,
                    needs_reply, urgency, summary, replied, chat_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET
                    chat_id = excluded.chat_id, sender_id = excluded.sender_id,
                    sender_display_name = excluded.sender_display_name, timestamp = excluded.timestamp,
                    type = excluded.type, text = excluded.text, is_from_me = excluded.is_from_me,
                    needs_reply = excluded.needs_reply, urgency = excluded.urgency, summary = excluded.summary,
                    chat_name = excluded.chat_name
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
                    item.chat_name,
                ),
            )
            if item.is_from_me:
                conn.execute(
                    """
                    UPDATE whatsapp_messages
                    SET replied = 1, is_read = 1
                    WHERE (chat_id = ? OR sender_id = ?) AND is_from_me = 0 AND timestamp <= ?
                    """,
                    (item.chat_id, item.chat_id, item.timestamp),
                )
            if not prior:
                conn.execute("INSERT OR REPLACE INTO whatsapp_meta (key, value) VALUES ('last_sqlite_insert_at', ?)",
                             (datetime.now().astimezone().isoformat(),))
            conn.commit()

        from jarvis.integrations.whatsapp.incoming_trace import trace_incoming
        trace_incoming(stage="sqlite", event_type="incoming_message", message_id=item.message_id,
                       chat_jid=item.chat_id, from_me=item.is_from_me, message_type=item.type,
                       timestamp=item.timestamp, sqlite_result="DEDUPE_EXISTING" if prior else "INSERTED")

        # Preserve reply/media metadata and invalidate thread context before generation.
        from jarvis.integrations.whatsapp.intelligence.engine import get_intelligence
        get_intelligence(self).persist(message.model_copy(update={"is_from_me": is_from_me}))

        logger.info(
            "Saved WhatsApp message %s from %s (urgency=%s, needs_reply=%s)",
            item.message_id, item.sender_display_name, item.urgency, item.needs_reply,
        )
        return item

    @staticmethod
    def _parse_ts(value: Any) -> float:
        """Epoch seconds from the bridge's ISO time ("2026-09-29T16:27:00.000Z") or a number; now when missing."""
        if value in (None, ""):
            return time.time()
        try:
            return float(value)
        except (TypeError, ValueError):
            pass
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except ValueError:
            return time.time()

    # ------------------------------------------------------------------ chat scope (groups only when asked)
    def _scoped(self, rows: list, limit: int, include_groups: bool, group: Optional[str],
                group_only: bool = False) -> List[InboxMessage]:
        """Personal chats only by default; ``group`` (a chat id) = only that group; ``include_groups`` = everything."""
        out: List[InboxMessage] = []
        for r in rows:
            m = self._row_to_msg(r)
            if not (self.is_direct_chat(m.chat_id) or self.is_group_chat(m.chat_id)):
                continue
            if group:
                if m.chat_id != group:
                    continue
            elif group_only and not self.is_group_chat(m.chat_id):
                continue
            elif not group_only and not include_groups and m.is_group:
                continue
            out.append(m)
            if len(out) >= limit:
                break
        return out

    @staticmethod
    def _scope_sql(include_groups: bool, group: Optional[str], group_only: bool) -> tuple[str, tuple]:
        """Apply chat scope before LIMIT, so a busy other scope cannot starve results."""
        if group:
            return "chat_id = ? AND chat_id LIKE '%@g.us'", (group,)
        direct = "(chat_id LIKE '%@s.whatsapp.net' OR chat_id LIKE '%@lid' OR chat_id LIKE '%@c.us')"
        group_chat = "chat_id LIKE '%@g.us'"
        if group_only:
            return group_chat, ()
        if include_groups:
            return f"({direct} OR {group_chat})", ()
        return direct, ()

    def find_group(self, name: str) -> Optional[Tuple[str, str]]:
        """(chat_id, group name) of the group whose name matches ``name`` ("cse", "CSE group", "the class group")."""
        q = re.sub(r"\b(?:the|my|our|group|grp|chat|whatsapp)\b", " ", (name or "").casefold())
        q = " ".join(q.split())
        if not q:
            return None
        with self._get_conn() as conn:
            rows = conn.execute("SELECT chat_id, chat_name, MAX(timestamp) AS ts FROM whatsapp_messages "
                                "WHERE chat_name != '' AND chat_id LIKE '%@g.us' "
                                "GROUP BY chat_id ORDER BY ts DESC").fetchall()
        exact = [r for r in rows if r["chat_name"].casefold() == q]
        partial = [r for r in rows if q in r["chat_name"].casefold()
                   or all(w in r["chat_name"].casefold().split() for w in q.split())]
        hits = exact or partial
        if len(hits) != 1 and not exact:
            return None  # unknown or ambiguous: never guess a group
        return hits[0]["chat_id"], hits[0]["chat_name"]

    def group_names(self) -> List[str]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT DISTINCT chat_name FROM whatsapp_messages "
                                "WHERE chat_name != '' AND chat_id LIKE '%@g.us'").fetchall()
        return sorted(r[0] for r in rows)

    def get_messages_needing_reply(self, limit: int = 10, include_groups: bool = False,
                                   group: Optional[str] = None, group_only: bool = False) -> List[InboxMessage]:
        """Pending messages requiring attention ordered by urgency and time (personal chats unless asked)."""
        scope_sql, scope_args = self._scope_sql(include_groups, group, group_only)
        with self._get_conn() as conn:
            cursor = conn.execute(
                f"""
                SELECT * FROM whatsapp_messages
                WHERE needs_reply = 1 AND replied = 0 AND is_from_me = 0 AND {scope_sql}
                ORDER BY
                    CASE urgency
                        WHEN 'URGENT' THEN 1
                        WHEN 'NORMAL' THEN 2
                        ELSE 3
                    END,
                    timestamp DESC
                LIMIT ?
                """,
                (*scope_args, limit),
            )
            return self._scoped(cursor.fetchall(), limit, include_groups, group, group_only)

    def get_unread(self, limit: int = 10, include_groups: bool = False, group: Optional[str] = None,
                   group_only: bool = False) -> List[InboxMessage]:
        """Unread incoming messages, newest first (personal chats unless asked).

        A chat WhatsApp shows as unread whose messages JARVIS never received contributes its last message.
        """
        out: List[InboxMessage] = []
        for chat in self.unread_chats(include_groups=include_groups, group=group, group_only=group_only):
            msgs = chat["messages"] or ([self._preview_message(chat)] if chat["last_text"] else [])
            if not chat["is_group"]:
                for m in msgs:  # the name the phone shows (saved contact name)
                    m.sender_display_name = chat["name"]
            out.extend(msgs)
        out.sort(key=lambda m: m.timestamp, reverse=True)
        return out[:limit]

    def get_recent(self, limit: int = 10, include_groups: bool = True, group: Optional[str] = None,
                   group_only: bool = False) -> List[InboxMessage]:
        """Most recent messages regardless of read status (all chats by default: used for indexing)."""
        scope_sql, scope_args = self._scope_sql(include_groups, group, group_only)
        with self._get_conn() as conn:
            cursor = conn.execute(
                f"SELECT * FROM whatsapp_messages WHERE {scope_sql} ORDER BY timestamp DESC LIMIT ?",
                (*scope_args, limit),
            )
            return self._scoped(cursor.fetchall(), limit, include_groups, group, group_only)

    def get_chat_history(self, chat_id: str, limit: int = 8) -> List[InboxMessage]:
        """Most recent messages of one conversation, oldest first (for reply context)."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM whatsapp_messages WHERE chat_id = ? OR sender_id = ? ORDER BY timestamp DESC LIMIT ?",
                (chat_id, chat_id, limit),
            )
            return list(reversed([self._row_to_msg(r) for r in cursor.fetchall()]))

    @staticmethod
    def is_direct_chat(chat_id: str) -> bool:
        """One-to-one chat (not a group, broadcast list, status update or channel)."""
        cid = (chat_id or "").lower()
        return cid.endswith("@s.whatsapp.net") or cid.endswith("@lid") or cid.endswith("@c.us")

    @staticmethod
    def is_group_chat(chat_id: str) -> bool:
        return (chat_id or "").lower().endswith("@g.us")

    def recent_direct_senders(self, since_s: float = 12 * 3600, limit: int = 15,
                              unanswered_only: bool = True, include_groups: bool = False) -> List[InboxMessage]:
        """Latest incoming message of each person who wrote recently, newest first.

        One entry per chat. Group chats are skipped unless ``include_groups``; with ``unanswered_only``
        a chat is skipped when the owner already wrote after the person's last message.
        """
        cutoff = time.time() - max(60.0, float(since_s))
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM whatsapp_messages WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT 2000", (cutoff,)
            ).fetchall()
        seen: set[str] = set()
        out: List[InboxMessage] = []
        for row in rows:
            msg = self._row_to_msg(row)
            if msg.chat_id in seen:
                continue
            seen.add(msg.chat_id)
            if not include_groups and not self.is_direct_chat(msg.chat_id):
                continue
            if msg.is_from_me:
                if unanswered_only:
                    continue
                # the owner spoke last; still list the person with their latest incoming message
                prev = next((self._row_to_msg(r) for r in rows if r["chat_id"] == msg.chat_id and not r["is_from_me"]), None)
                if prev is None:
                    continue
                msg = prev
            if unanswered_only and msg.replied:
                continue
            out.append(msg)
            if len(out) >= limit:
                break
        return out

    def owner_samples(self, limit: int = 6, max_len: int = 160) -> List[str]:
        """A few of the owner's own recent messages (used to match their texting style)."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT text FROM whatsapp_messages WHERE is_from_me = 1 AND length(text) BETWEEN 3 AND ? "
                "ORDER BY timestamp DESC LIMIT ?", (max_len, limit * 3)
            ).fetchall()
        texts: List[str] = []
        for (text,) in rows:
            t = (text or "").strip()
            if t and t not in texts and not t.lower().startswith(("http", "jarvis")):
                texts.append(t)
            if len(texts) >= limit:
                break
        return texts

    def find_latest_incoming(self, who: str = "", direct_only: bool | None = None) -> Optional[InboxMessage]:
        """Latest message not sent by the owner, optionally from a sender name / number / JID.

        Without a name, only one-to-one chats are considered (a reply never lands in a group by
        accident); with a name, one-to-one chats are preferred over group messages.
        """
        who_clean = (who or "").strip().casefold()
        digits = "".join(ch for ch in who_clean if ch.isdigit())
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM whatsapp_messages WHERE is_from_me = 0 ORDER BY needs_reply DESC, timestamp DESC LIMIT 400"
            ).fetchall()
        candidates = [self._row_to_msg(r) for r in rows]
        if direct_only is None:
            direct_only = not who_clean
        direct = [m for m in candidates if self.is_direct_chat(m.chat_id)]
        if direct_only:
            candidates = direct
        else:
            candidates = direct + [m for m in candidates if not self.is_direct_chat(m.chat_id)]
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

    def mark_chat_read(self, chat_id: str, before_ts: Optional[float] = None) -> int:
        """The owner wrote in (or opened) the chat: its incoming messages up to ``before_ts`` are read."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "UPDATE whatsapp_messages SET is_read = 1 WHERE chat_id = ? AND is_from_me = 0 AND is_read = 0 "
                "AND timestamp <= ?", (chat_id, time.time() + 60 if before_ts is None else before_ts))
            conn.commit()
            return cursor.rowcount

    # ------------------------------------------------------------------ WhatsApp's own unread badges (from the bridge)
    def update_chats(self, chats: List[Dict[str, Any]], full: bool = False, synced: bool = False,
                     generation: str = "", synced_generation: str = "", event_meta: Optional[Dict[str, Any]] = None) -> int:
        """Stores each chat's unread badge as WhatsApp shows it.

        The newest ``unread`` incoming messages of a chat stay unread and older ones become read; a chat at 0 is
        read. With ``full`` and ``synced`` the list covers every chat that has unread messages, so any other chat
        is read too. Returns the number of chats stored.
        """
        synced = bool(synced and (not generation or generation == synced_generation))
        stored: List[str] = []
        with self._get_conn() as conn:
            if not generation and conn.execute("SELECT 1 FROM whatsapp_meta WHERE key = 'connector_state'").fetchone():
                synced = False  # an older bridge cannot prove current-session completeness
            if generation:
                conn.execute("INSERT OR REPLACE INTO whatsapp_meta (key, value) VALUES ('sync_generation', ?)",
                             (generation,))
                conn.execute("INSERT OR REPLACE INTO whatsapp_meta (key, value) VALUES ('synced_generation', ?)",
                             (synced_generation if synced else "",))
            for key in ("last_history_event", "last_chat_state_event", "last_message_event", "store_age_seconds"):
                value = (event_meta or {}).get(key)
                if value is not None:
                    conn.execute("INSERT OR REPLACE INTO whatsapp_meta (key, value) VALUES (?, ?)",
                                 (key, str(value)))
            for key, value in ((event_meta or {}).get("counts") or {}).items():
                if key in {"chats", "direct", "groups", "unread_direct_chats", "unread_direct_messages"}:
                    conn.execute("INSERT OR REPLACE INTO whatsapp_meta (key, value) VALUES (?, ?)",
                                 ("bridge_count_" + key, str(int(value))))
            for c in chats or []:
                cid = str((c or {}).get("chat_id") or "").strip()
                if not (self.is_direct_chat(cid) or self.is_group_chat(cid)):
                    continue
                try:
                    unread = max(0, int(c.get("unread") or 0))
                    last_ts = float(c.get("last_ts") or 0)
                except (TypeError, ValueError):
                    continue
                conn.execute(
                    """
                    INSERT INTO whatsapp_chats (chat_id, name, unread, last_ts, is_group, last_text, last_sender,
                                                last_from_me, updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(chat_id) DO UPDATE SET
                        name = CASE WHEN excluded.name != '' THEN excluded.name ELSE whatsapp_chats.name END,
                        unread = excluded.unread, last_ts = MAX(whatsapp_chats.last_ts, excluded.last_ts),
                        is_group = excluded.is_group, last_text = excluded.last_text,
                        last_sender = excluded.last_sender, last_from_me = excluded.last_from_me,
                        updated = excluded.updated
                    """,
                    (cid, str(c.get("name") or "").strip(), unread, last_ts,
                    1 if self.is_group_chat(cid) else 0,
                     str(c.get("last_text") or "")[:300], str(c.get("last_sender") or "").strip(),
                     1 if c.get("last_from_me") else 0, time.time()),
                )
                if synced or not full:
                    self._sync_read_flags(conn, cid, unread)
                stored.append(cid)
            if full and synced:
                listed = set(stored)
                for (cid,) in conn.execute("SELECT chat_id FROM whatsapp_chats WHERE unread > 0").fetchall():
                    if cid not in listed:
                        conn.execute("UPDATE whatsapp_chats SET unread = 0, updated = ? WHERE chat_id = ?", (time.time(), cid))
                        self._sync_read_flags(conn, cid, 0)
            conn.execute("INSERT OR REPLACE INTO whatsapp_meta (key, value) VALUES ('chats_synced', ?)",
                         ("1" if synced else "0",))
            if synced:
                conn.execute("INSERT OR REPLACE INTO whatsapp_meta (key, value) VALUES ('last_successful_sync_at', ?)",
                             (datetime.now().astimezone().isoformat(),))
            conn.commit()
        if self.chats_synced():
            self._sync_event.set()
        else:
            self._sync_event.clear()
        return len(stored)

    @staticmethod
    def _sync_read_flags(conn: sqlite3.Connection, chat_id: str, unread: int) -> None:
        if unread <= 0:
            conn.execute("UPDATE whatsapp_messages SET is_read = 1 WHERE chat_id = ? AND is_from_me = 0 AND is_read = 0",
                         (chat_id,))
            return
        conn.execute(
            """
            UPDATE whatsapp_messages SET is_read = 1
            WHERE chat_id = ? AND is_from_me = 0 AND is_read = 0 AND message_id NOT IN (
                SELECT message_id FROM whatsapp_messages WHERE chat_id = ? AND is_from_me = 0
                ORDER BY timestamp DESC LIMIT ?)
            """, (chat_id, chat_id, unread))

    def chats_synced(self) -> bool:
        """WhatsApp's full chat list has been received: chats without a badge are read."""
        with self._get_conn() as conn:
            meta = dict(conn.execute("SELECT key, value FROM whatsapp_meta WHERE key IN "
                                     "('chats_synced', 'sync_generation', 'synced_generation', 'connector_state')").fetchall())
        return (meta.get("chats_synced") == "1" and
                (not meta.get("connector_state") or bool(meta.get("sync_generation"))) and
                (not meta.get("sync_generation") or meta.get("sync_generation") == meta.get("synced_generation")))

    def sync_state(self) -> str:
        """Whether the current bridge session supplied a complete chat snapshot."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT value FROM whatsapp_meta WHERE key = 'connector_state'").fetchone()
        state = row[0] if row else ""
        if state == "AUTH_REQUIRED":
            return state
        if state in {"NOT_CONNECTED", "ERROR"}:
            return state
        return "READY" if self.chats_synced() else "PARTIAL_SYNC"

    def wait_for_ready(self, timeout: float = 1.5) -> bool:
        """Brief event-driven wait for a current-session chat snapshot."""
        if self.sync_state() == "READY":
            return True
        if self.sync_state() in {"NOT_CONNECTED", "AUTH_REQUIRED", "ERROR"}:
            return False
        with self._get_conn() as conn:
            row = conn.execute("SELECT value FROM whatsapp_meta WHERE key = 'connector_state'").fetchone()
        if not row:  # synthetic/offline inbox: no active connector to wait for
            return False
        self._sync_event.wait(max(0.0, min(float(timeout), 2.0)))
        return self.sync_state() == "READY"

    def set_connector_state(self, bridge_state: str) -> None:
        state = str(bridge_state or "").upper()
        if state in {"PAIRING_REQUIRED", "AUTH_REQUIRED"}:
            state = "AUTH_REQUIRED"
        elif state in {"CONNECTED", "READY"}:
            state = "READY"
        elif state in {"CONNECTING", "RECONNECTING", "SYNCING"}:
            state = "SYNCING"
        elif state in {"DEGRADED", "ERROR"}:
            state = "ERROR"
        else:
            state = "NOT_CONNECTED"
        with self._get_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO whatsapp_meta (key, value) VALUES ('connector_state', ?)", (state,))
            if state != "READY":
                conn.execute("INSERT OR REPLACE INTO whatsapp_meta (key, value) VALUES ('chats_synced', '0')")
                conn.execute("INSERT OR REPLACE INTO whatsapp_meta (key, value) VALUES ('synced_generation', '')")
                self._sync_event.clear()
            conn.commit()

    def set_bridge_runtime(self, identity: Dict[str, Any], diagnostics: Dict[str, Any]) -> None:
        """Persist metadata-only bridge identity for the local diagnostics view."""
        with self._get_conn() as conn:
            for key, value in (("bridge_identity", identity), ("bridge_runtime_diagnostics", diagnostics)):
                conn.execute("INSERT OR REPLACE INTO whatsapp_meta (key, value) VALUES (?, ?)",
                             (key, json.dumps(value)))
            conn.commit()

    def record_python_event(self) -> None:
        """Store receipt time only; message IDs and bodies stay in the opt-in trace."""
        with self._get_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO whatsapp_meta (key, value) VALUES ('last_python_event_at', ?)",
                         (datetime.now().astimezone().isoformat(),))
            conn.commit()

    def record_live_acceptance(self, *, generation: str, phone_received: bool,
                               message_received: bool, message_id: str = "",
                               observed_after: float | None = None) -> None:
        """Record a phone-confirmed probe against an exact persisted incoming ID.

        Aggregate Baileys event counts cannot establish that the particular
        phone-confirmed test reached this bridge generation.
        """
        if not phone_received:
            return
        with self._get_conn() as conn:
            current = conn.execute("SELECT value FROM whatsapp_meta WHERE key='sync_generation'").fetchone()
            if current and current[0] == generation:
                if message_received and message_id and observed_after is not None:
                    matched = conn.execute("SELECT chat_id,timestamp FROM whatsapp_messages WHERE message_id=? AND is_from_me=0",
                                           (message_id,)).fetchone()
                    if matched and self.is_direct_chat(matched[0]) and matched[1] >= observed_after:
                        conn.execute("INSERT OR REPLACE INTO whatsapp_meta VALUES ('acceptance_verified_generation', ?)", (generation,))
                        conn.execute("DELETE FROM whatsapp_meta WHERE key='acceptance_failed_generation'")
                elif not message_received:
                    conn.execute("INSERT OR REPLACE INTO whatsapp_meta VALUES ('acceptance_failed_generation', ?)", (generation,))
                conn.commit()

    def diagnostics(self) -> Dict[str, Any]:
        """Aggregate, body-free connector and message-store diagnostics."""
        with self._get_conn() as conn:
            meta = dict(conn.execute("SELECT key, value FROM whatsapp_meta").fetchall())
            chats = conn.execute("SELECT COUNT(*), SUM(CASE WHEN is_group = 0 THEN 1 ELSE 0 END), "
                                 "SUM(CASE WHEN is_group != 0 THEN 1 ELSE 0 END), "
                                 "SUM(CASE WHEN is_group = 0 AND unread > 0 THEN 1 ELSE 0 END), "
                                 "SUM(CASE WHEN is_group = 0 THEN unread ELSE 0 END), MAX(updated) "
                                 "FROM whatsapp_chats").fetchone()
            msgs = conn.execute("SELECT COUNT(*), MIN(timestamp), MAX(timestamp), COUNT(DISTINCT chat_id) "
                                "FROM whatsapp_messages WHERE is_from_me = 0").fetchone()
            per_chat = conn.execute("SELECT chat_id, COUNT(*) AS n FROM whatsapp_messages WHERE is_from_me = 0 "
                                    "GROUP BY chat_id ORDER BY n DESC LIMIT 300").fetchall()
            missing_bodies = conn.execute("SELECT COUNT(*) FROM whatsapp_chats AS c WHERE c.unread > 0 "
                                          "AND c.unread > (SELECT COUNT(*) FROM whatsapp_messages AS m "
                                          "WHERE m.chat_id = c.chat_id AND m.is_from_me = 0 AND m.is_read = 0)").fetchone()[0]
        def bridge_count(key: str, local: int) -> int:
            try:
                return int(meta["bridge_count_" + key])
            except (KeyError, ValueError):
                return local

        connector = meta.get("connector_state", "UNKNOWN")
        history_state = self.sync_state()
        runtime = json.loads(meta.get("bridge_runtime_diagnostics", "{}"))
        # A current chat/badge snapshot does not establish complete historical message coverage.
        local_history_available = bool(msgs[0])
        chat_snapshot_current = history_state == "READY"
        stream_verified = (connector == "READY" and runtime.get("generation") == meta.get("sync_generation")
                           and meta.get("acceptance_verified_generation") == meta.get("sync_generation"))
        stream_failed = (connector == "READY" and not stream_verified and bool(meta.get("sync_generation"))
                         and meta.get("acceptance_failed_generation") == meta.get("sync_generation"))
        # A socket can be open while Baileys is still buffering every inbound event.
        # Live acceptance requires a separately verified test message from the phone.
        return {"connector_state": connector,
                "transport_connected": connector == "READY",
                "event_stream_verified": stream_verified,
                "event_stream_failed": stream_failed,
                "authenticated": bool(json.loads(meta.get("bridge_identity", "{}")).get("auth_registered")),
                "prompt_delivery_verified": stream_verified,
                "local_history_available": local_history_available,
                "chat_snapshot_current": chat_snapshot_current,
                "history_complete": False,
                "sync_in_progress": connector == "SYNCING" or (connector == "READY" and
                                     (runtime.get("event_health") or {}).get("received_pending_notifications") is False),
                "last_raw_event_at": (runtime.get("event_health") or {}).get("last_raw_node_at"),
                "last_upsert_at": (runtime.get("event_health") or {}).get("last_message_event"),
                "last_python_event_at": meta.get("last_python_event_at"),
                "last_sqlite_insert_at": meta.get("last_sqlite_insert_at"),
                "last_successful_sync_at": meta.get("last_successful_sync_at"),
                "overall_state": ("EVENT_STREAM_FAILED" if stream_failed else "DEGRADED_LIVE" if connector == "READY" and
                                  not stream_verified else
                                  "READY" if connector == "READY" and history_state == "READY" else
                                  "LIVE_ONLY" if stream_verified else history_state),
                "history_sync_state": history_state, "chat_count": bridge_count("chats", chats[0]),
                "direct_chat_count": bridge_count("direct", chats[1] or 0),
                "group_count": bridge_count("groups", chats[2] or 0),
                "unread_direct_chat_count": bridge_count("unread_direct_chats", chats[3] or 0),
                "unread_message_count": bridge_count("unread_direct_messages", chats[4] or 0),
                "last_chat_state_event": meta.get("last_chat_state_event"),
                "last_history_event": meta.get("last_history_event"),
                "last_message_event": meta.get("last_message_event"),
                "store_age_seconds": meta.get("store_age_seconds"),
                "sync_generation": meta.get("sync_generation"),
                "synced_generation": meta.get("synced_generation"),
                "last_persisted_chat_update": chats[5],
                "stored_inbound_messages": msgs[0], "oldest_message_timestamp": msgs[1],
                "newest_message_timestamp": msgs[2], "chats_with_stored_messages": msgs[3],
                "message_counts_per_chat": [{"chat_id": r[0], "stored_inbound": r[1]} for r in per_chat],
                "unread_chats_missing_message_bodies": missing_bodies,
                "bridge_identity": json.loads(meta.get("bridge_identity", "{}")),
                "bridge_runtime_diagnostics": json.loads(meta.get("bridge_runtime_diagnostics", "{}"))}

    def unread_chats(self, include_groups: bool = False, group: Optional[str] = None,
                     max_messages: int = 10, group_only: bool = False) -> List[Dict[str, Any]]:
        """Chats with unread messages, most recent first.

        Each entry: chat_id, name, is_group, unread (WhatsApp's badge count), messages (stored unread messages,
        newest first), last_text / last_sender / last_ts (WhatsApp's last message, even if JARVIS never got it).
        Chats the bridge has not reported (an older bridge, or messages from before tracking started) use the
        inbox's own flags, where a later message from the owner in the chat means read.
        """
        with self._get_conn() as conn:
            synced = bool((conn.execute("SELECT value FROM whatsapp_meta WHERE key = 'chats_synced'").fetchone() or ["0"])[0] == "1")
            badges = {r["chat_id"]: r for r in conn.execute("SELECT * FROM whatsapp_chats").fetchall()}
            rows = conn.execute("SELECT * FROM whatsapp_messages WHERE is_from_me = 0 AND is_read = 0 "
                                "ORDER BY timestamp DESC LIMIT 3000").fetchall()
            own_last = dict(conn.execute("SELECT chat_id, MAX(timestamp) FROM whatsapp_messages WHERE is_from_me = 1 "
                                         "GROUP BY chat_id").fetchall())
        stored: Dict[str, List[InboxMessage]] = {}
        for r in rows:
            m = self._row_to_msg(r)
            if own_last.get(m.chat_id, float("-inf")) >= m.timestamp:
                continue  # the owner wrote after it: read
            stored.setdefault(m.chat_id, []).append(m)

        def in_scope(chat_id: str, is_group: bool) -> bool:
            if not (self.is_direct_chat(chat_id) or self.is_group_chat(chat_id)):
                return False
            if group:
                return chat_id == group and self.is_group_chat(chat_id)
            if group_only:
                return self.is_group_chat(chat_id)
            return include_groups or not is_group

        out: List[Dict[str, Any]] = []
        for cid, b in badges.items():
            if b["unread"] <= 0 or not in_scope(cid, bool(b["is_group"])):
                continue
            msgs = stored.get(cid, [])[:min(b["unread"], max_messages)]
            out.append(self._chat_entry(cid, bool(b["is_group"]), b["unread"], msgs, b))
        if not synced:
            # without WhatsApp's badges nothing ever says a chat was read on the phone: only the last few days count
            newest = max((m[0].timestamp for m in stored.values()), default=0.0)
            for cid, msgs in stored.items():
                msgs = [m for m in msgs if m.timestamp >= newest - 3 * 24 * 3600]
                if not msgs or (cid in badges and badges[cid]["unread"] > 0) or not in_scope(cid, not self.is_direct_chat(cid)):
                    continue
                out.append(self._chat_entry(cid, not self.is_direct_chat(cid), len(msgs), msgs[:max_messages], None))
        out.sort(key=lambda e: max(e["last_ts"], e["messages"][0].timestamp if e["messages"] else 0), reverse=True)
        return out

    def _chat_entry(self, chat_id: str, is_group: bool, unread: int, msgs: List[InboxMessage],
                    badge: Optional[sqlite3.Row]) -> Dict[str, Any]:
        name = (badge["name"] if badge is not None else "") or ""
        if not name and msgs:
            name = (msgs[0].chat_name if is_group else msgs[0].sender_display_name) or ""
        if not name and is_group:
            label = self._group_label(chat_id)
            name = "" if label == "selected" else label
        if not name and badge is not None and not is_group and not badge["last_from_me"]:
            name = badge["last_sender"]
        if not name:
            name = "a group" if is_group else "+" + chat_id.split("@")[0]
        last_text = ""
        if badge is not None and not badge["last_from_me"]:
            last_text = badge["last_text"] or ""
        return {
            "chat_id": chat_id,
            "name": name,
            "is_group": is_group,
            "unread": max(int(unread), len(msgs)),
            "messages": msgs,
            "last_text": last_text,
            "last_sender": (badge["last_sender"] if badge is not None else "") or "",
            "last_ts": float(badge["last_ts"]) if badge is not None else (msgs[0].timestamp if msgs else 0.0),
        }

    def _preview_message(self, chat: Dict[str, Any]) -> InboxMessage:
        """WhatsApp's last message of a chat JARVIS has no copy of (reported by the bridge)."""
        text = chat["last_text"]
        sender = chat["last_sender"] if chat["is_group"] else chat["name"]
        urgency, needs_reply, summary = UrgencyClassifier.analyze(text)
        return InboxMessage(message_id=f"chat:{chat['chat_id']}", chat_id=chat["chat_id"], sender_id=chat["chat_id"],
                            sender_display_name=sender or chat["name"], timestamp=chat["last_ts"] or time.time(),
                            type="text", text=text, is_from_me=False, is_read=False, needs_reply=needs_reply,
                            urgency=urgency, summary=summary, replied=False,
                            chat_name=chat["name"] if chat["is_group"] else "")

    def mark_as_read(self, message_id: str) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE whatsapp_messages SET is_read = 1 WHERE message_id = ?",
                (message_id,),
            )
            conn.commit()

    @staticmethod
    def _speakable(text: str, words: int = 16) -> str:
        t = " ".join((text or "").split())
        parts = t.split(" ")
        return t if len(parts) <= words else " ".join(parts[:words]) + "..."

    def summarize_inbox(self, include_groups: bool = False, group: Optional[str] = None,
                        max_people: int = 5, max_age_hours: Optional[float] = 48.0,
                        group_only: bool = False) -> Dict[str, Any]:
        """What is unread, who sent it and what each person said - one line per person, attributed exactly.

        Unread follows WhatsApp's own badges when the bridge reports them. Questions and requests are flagged
        ("Mom asks ..."), urgent ones come first. Personal chats only unless the owner asked about groups
        (``include_groups``) or one group (``group``); otherwise groups are only counted. Deterministic on
        purpose: no model can mix up who said what, and it answers instantly.
        """
        sync_state = self.sync_state()
        chats = self.unread_chats(include_groups=True)
        if group:
            scoped = [c for c in chats if c["chat_id"] == group]
        elif group_only:
            scoped = [c for c in chats if c["is_group"]]
        elif include_groups:
            scoped = chats
        else:
            scoped = [c for c in chats if not c["is_group"]]

        # one entry per person: per chat for personal chats, per sender inside a group
        entries: List[Dict[str, Any]] = []
        for chat in scoped:
            if chat["is_group"] and chat["messages"]:
                senders: Dict[str, List[InboxMessage]] = {}
                for m in chat["messages"]:
                    senders.setdefault(m.sender_id, []).append(m)
                for msgs in senders.values():
                    entries.append({"chat": chat, "name": msgs[0].sender_display_name or msgs[0].sender_id.split("@")[0],
                                    "msgs": msgs, "count": len(msgs), "text": ""})
            else:
                entries.append({"chat": chat, "name": chat["name"] if not chat["is_group"] else (chat["last_sender"] or chat["name"]),
                                "msgs": chat["messages"], "count": chat["unread"], "text": chat["last_text"]})
        for e in entries:
            flags = [UrgencyClassifier.analyze(m.text or "") for m in e["msgs"]] or (
                [UrgencyClassifier.analyze(e["text"])] if e["text"] else [])
            e["urgent"] = any(f[0] == "URGENT" for f in flags)
            e["asks"] = any(f[1] for f in flags)
            e["ts"] = max([m.timestamp for m in e["msgs"]] or [e["chat"]["last_ts"]])
        entries.sort(key=lambda e: (not e["urgent"], not e["asks"], -e["ts"]))

        lines = [self._unread_line(e, show_group=bool((include_groups or group_only) and not group)) for e in entries[:max_people]]
        n_msgs = sum(c["unread"] for c in scoped)
        n_people = len(entries)
        label = self._group_label(group) if group else ""
        if group:
            named = next((c["name"] for c in scoped), "") or label
            head = (f"The {named} group has {n_msgs} unread message{'s' if n_msgs != 1 else ''}." if n_msgs
                    else f"No unread messages in the {label} group.")
        elif group_only:
            head = (f"You have {n_msgs} unread group message{'s' if n_msgs != 1 else ''} in {len(scoped)} group chats."
                    if n_msgs else "You have no unread group messages.")
        elif include_groups:
            n_chats = len(scoped)
            head = (f"You have {n_msgs} unread WhatsApp message{'s' if n_msgs != 1 else ''} in {n_chats} "
                    f"chat{'s' if n_chats != 1 else ''}." if n_msgs else "You have no unread WhatsApp messages.")
        else:
            head = ("No unread messages in your personal chats." if not n_msgs else
                    f"You have {n_msgs} unread message{'s' if n_msgs != 1 else ''}"
                    + (f" from {n_people} people." if n_people > 1 else "."))
        if sync_state != "READY":
            if n_msgs == 0:
                head = ("WhatsApp is not connected, so I can't verify whether you have unread messages."
                        if sync_state == "NOT_CONNECTED" else
                        "WhatsApp needs authentication, so I can't verify whether you have unread messages."
                        if sync_state == "AUTH_REQUIRED" else
                        "WhatsApp history is not fully synced, so I can't verify whether you have unread messages.")
            else:
                head += " WhatsApp history is not fully synced; these counts may be incomplete."
        spoken = head
        if lines:
            spoken += " " + " ".join(ln if re.search(r"[.?!]\"?\)?$", ln) else ln + "." for ln in lines)
            if n_people > max_people:
                spoken += f" And {n_people - max_people} more {'person' if n_people - max_people == 1 else 'people'}."

        # read on the phone but not answered yet (a question from today)
        if not group and not group_only:
            unread_ids = {c["chat_id"] for c in chats}
            with self._get_conn() as conn:
                own_last = dict(conn.execute("SELECT chat_id, MAX(timestamp) FROM whatsapp_messages WHERE is_from_me = 1 "
                                             "GROUP BY chat_id").fetchall())
            waiting = []
            for m in self.get_messages_needing_reply(limit=20, include_groups=include_groups):
                if (m.chat_id in unread_ids or m.timestamp < time.time() - 24 * 3600
                        or own_last.get(m.chat_id, float("-inf")) >= m.timestamp
                        or not UrgencyClassifier.analyze(m.text)[1]):
                    continue
                name = self._spoken_name(self._chat_display_name(m))
                if name not in waiting:
                    waiting.append(name)
            if waiting:
                who = ", ".join(waiting[:3]) + (f" and {len(waiting) - 3} more" if len(waiting) > 3 else "")
                spoken += f" Still waiting for your reply: {who}."

        groups_unread = [c for c in chats if c["is_group"]] if not include_groups and not group else []
        if groups_unread:
            g_msgs = sum(c["unread"] for c in groups_unread)
            names = ", ".join(f"{c['name']}: {c['unread']}" for c in groups_unread[:3])
            more = " and more" if len(groups_unread) > 3 else ""
            spoken += (f" {len(groups_unread)} group chat{'s' if len(groups_unread) != 1 else ''} also "
                       f"{'have' if len(groups_unread) != 1 else 'has'} {g_msgs} unread message{'s' if g_msgs != 1 else ''} "
                       f"({names}{more}) - ask if you want them.")

        pending = [m for e in entries for m in e["msgs"] if UrgencyClassifier.analyze(m.text or "")[1]]
        urgent = [m for m in pending if UrgencyClassifier.analyze(m.text or "")[0] == "URGENT"]
        normal = [m for m in pending if m not in urgent]
        return {
            "total_pending": len(pending),
            "people": n_people,
            "urgent_count": len(urgent),
            "normal_count": len(normal),
            "urgent_messages": [m.to_dict() for m in urgent],
            "normal_messages": [m.to_dict() for m in normal],
            "unread_count": n_msgs,
            "unread_messages": n_msgs,
            "total_direct_chats": self.diagnostics()["direct_chat_count"],
            "unread_direct_chats": sum(1 for c in chats if not c["is_group"]),
            "generated_at": datetime.now().astimezone().isoformat(),
            "sync_state": sync_state,
            "unread_chats": [{"chat_id": c["chat_id"], "name": c["name"], "unread": c["unread"], "is_group": c["is_group"], "timestamp": c["last_ts"]}
                             for c in scoped],
            "groups_unread": sum(c["unread"] for c in groups_unread),
            "spoken_summary": spoken,
        }

    _MEDIA_WORDS = {"image": "a photo", "voice_note": "a voice note", "audio": "an audio clip", "document": "a document"}

    def _unread_line(self, e: Dict[str, Any], show_group: bool) -> str:
        """'Urgent: Mom asks "call me"' / 'Sanjana Ssk sent 2 messages; the latest asks "Ena man panra"'."""
        name = self._spoken_name(e["name"])
        where = f" in {e['chat']['name']}" if show_group and e["chat"]["is_group"] else ""
        latest = max(e["msgs"], key=lambda m: m.timestamp) if e["msgs"] else None
        if latest is not None and not (latest.text or "").strip() and latest.type in self._MEDIA_WORDS:
            said = self._MEDIA_WORDS[latest.type]
        elif latest is not None:
            said = describe_message(latest.text or latest.summary)
        elif e["text"]:
            said = describe_message(e["text"])
        else:
            n = e["count"]
            return f"{name}{where}: {n} unread message{'s' if n != 1 else ''}"
        asks = UrgencyClassifier.analyze((latest.text if latest is not None else e["text"]) or "")[1]
        verb = ("asks" if asks else "says") if said.startswith('"') else "sent"
        prefix = "Urgent: " if e["urgent"] else ""
        if e["count"] > 1:
            return f"{prefix}{name}{where} sent {e['count']} messages; the latest {verb} {said}"
        return f"{prefix}{name}{where} {verb} {said}"

    def _chat_display_name(self, m: InboxMessage) -> str:
        with self._get_conn() as conn:
            row = conn.execute("SELECT name FROM whatsapp_chats WHERE chat_id = ?", (m.chat_id,)).fetchone()
        if row and row[0] and not m.is_group:
            return row[0]
        return m.sender_display_name or m.sender_id.split("@")[0]

    @staticmethod
    def _spoken_name(name: str) -> str:
        """'sushmitaa mahesh' -> 'Sushmitaa Mahesh', 'Scooby!!' -> 'Scooby' (names read out naturally)."""
        from jarvis.core.response.whatsapp import IDENTIFIER
        if IDENTIFIER.search(name or '') or (name or '').isdigit() or '@' in (name or ''):
            return 'one contact'
        n = re.sub(r"[^\w\s.'-]", "", name or "").strip() or "one contact"
        return n.title() if n.islower() else n

    def _group_label(self, chat_id: Optional[str]) -> str:
        if not chat_id:
            return ""
        with self._get_conn() as conn:
            row = conn.execute("SELECT chat_name FROM whatsapp_messages WHERE chat_id = ? AND chat_name != '' LIMIT 1",
                               (chat_id,)).fetchone()
        return row[0] if row else "selected"

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
            chat_name=(row["chat_name"] if "chat_name" in row.keys() else "") or "",
        )
