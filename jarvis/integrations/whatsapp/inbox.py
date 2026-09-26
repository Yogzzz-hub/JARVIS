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
    chat_name: str = ""  # group subject ("" for one-to-one chats)

    @property
    def is_group(self) -> bool:
        return not WhatsAppInbox.is_direct_chat(self.chat_id)

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
            cols = {r[1] for r in conn.execute("PRAGMA table_info(whatsapp_messages)").fetchall()}
            if "chat_name" not in cols:
                conn.execute("ALTER TABLE whatsapp_messages ADD COLUMN chat_name TEXT NOT NULL DEFAULT ''")
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
            chat_name=(getattr(message, "chat_name", "") or "").strip(),
        )

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO whatsapp_messages (
                    message_id, chat_id, sender_id, sender_display_name,
                    timestamp, type, text, is_from_me, is_read,
                    needs_reply, urgency, summary, replied, chat_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            conn.commit()

        logger.info(
            "Saved WhatsApp message %s from %s (urgency=%s, needs_reply=%s)",
            item.message_id, item.sender_display_name, item.urgency, item.needs_reply,
        )
        return item

    # ------------------------------------------------------------------ chat scope (groups only when asked)
    def _scoped(self, rows: list, limit: int, include_groups: bool, group: Optional[str]) -> List[InboxMessage]:
        """Personal chats only by default; ``group`` (a chat id) = only that group; ``include_groups`` = everything."""
        out: List[InboxMessage] = []
        for r in rows:
            m = self._row_to_msg(r)
            if group:
                if m.chat_id != group:
                    continue
            elif not include_groups and m.is_group:
                continue
            out.append(m)
            if len(out) >= limit:
                break
        return out

    def find_group(self, name: str) -> Optional[Tuple[str, str]]:
        """(chat_id, group name) of the group whose name matches ``name`` ("cse", "CSE group", "the class group")."""
        q = re.sub(r"\b(?:the|my|our|group|grp|chat|whatsapp)\b", " ", (name or "").casefold())
        q = " ".join(q.split())
        if not q:
            return None
        with self._get_conn() as conn:
            rows = conn.execute("SELECT chat_id, chat_name, MAX(timestamp) AS ts FROM whatsapp_messages "
                                "WHERE chat_name != '' GROUP BY chat_id ORDER BY ts DESC").fetchall()
        exact = [r for r in rows if r["chat_name"].casefold() == q]
        partial = [r for r in rows if q in r["chat_name"].casefold()
                   or all(w in r["chat_name"].casefold().split() for w in q.split())]
        hits = exact or partial
        if len(hits) != 1 and not exact:
            return None  # unknown or ambiguous: never guess a group
        return hits[0]["chat_id"], hits[0]["chat_name"]

    def group_names(self) -> List[str]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT DISTINCT chat_name FROM whatsapp_messages WHERE chat_name != ''").fetchall()
        return sorted(r[0] for r in rows)

    def get_messages_needing_reply(self, limit: int = 10, include_groups: bool = False,
                                   group: Optional[str] = None) -> List[InboxMessage]:
        """Pending messages requiring attention ordered by urgency and time (personal chats unless asked)."""
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
                (max(limit * 10, 200),),
            )
            return self._scoped(cursor.fetchall(), limit, include_groups, group)

    def get_unread(self, limit: int = 10, include_groups: bool = False, group: Optional[str] = None) -> List[InboxMessage]:
        """Returns unread incoming messages (personal chats unless asked)."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM whatsapp_messages
                WHERE is_read = 0 AND is_from_me = 0
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (max(limit * 10, 200),),
            )
            return self._scoped(cursor.fetchall(), limit, include_groups, group)

    def get_recent(self, limit: int = 10, include_groups: bool = True, group: Optional[str] = None) -> List[InboxMessage]:
        """Most recent messages regardless of read status (all chats by default: used for indexing)."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM whatsapp_messages ORDER BY timestamp DESC LIMIT ?",
                (limit if include_groups and not group else max(limit * 10, 200),),
            )
            return self._scoped(cursor.fetchall(), limit, include_groups, group)

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
        return not (cid.endswith("@g.us") or cid.endswith("@broadcast") or cid.endswith("@newsletter")
                    or cid.startswith("status@") or cid.endswith("@temp"))

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
                        max_people: int = 5) -> Dict[str, Any]:
        """Who is waiting for a reply and what each one said - one line per person, attributed exactly.

        Personal chats only unless the owner asked about groups (``include_groups``) or one group (``group``).
        Deterministic on purpose: no model can mix up who said what, and it answers instantly.
        """
        # re-check stored flags with the current rules (older rows marked links with "?" as questions)
        pending = [m for m in self.get_messages_needing_reply(limit=40, include_groups=include_groups, group=group)
                   if UrgencyClassifier.analyze(m.text)[1]]
        urgent = [m for m in pending if m.urgency == "URGENT"]
        normal = [m for m in pending if m.urgency != "URGENT"]

        # one entry per person (per chat for personal chats, per sender inside a group), urgent first
        people: Dict[Tuple[str, str], List[InboxMessage]] = {}
        for m in urgent + normal:
            people.setdefault((m.chat_id, m.sender_id), []).append(m)

        lines = []
        for (chat_id, _), msgs in list(people.items())[:max_people]:
            latest = max(msgs, key=lambda x: x.timestamp)
            name = self._spoken_name(latest.sender_display_name or latest.sender_id.split("@")[0])
            where = f" in {latest.chat_name or 'a group'}" if latest.is_group else ""
            is_urgent = any(x.urgency == "URGENT" for x in msgs)
            said = describe_message(latest.text or latest.summary)
            verb = "sent" if not said.startswith('"') else "says"
            if len(msgs) > 1:
                lines.append(f"{'Urgent: ' if is_urgent else ''}{name}{where} sent {len(msgs)} messages; the latest {verb} {said}")
            else:
                lines.append(f"{'Urgent: ' if is_urgent else ''}{name}{where} {verb} {said}")

        n_people = len(people)
        scope = f"the {self._group_label(group)} group" if group else ("your chats" if include_groups else "your personal chats")
        if n_people == 0:
            spoken = f"No one is waiting for a reply in {scope}."
        else:
            head = f"{n_people} {'person is' if n_people == 1 else 'people are'} waiting for a reply in {scope}."
            more = f" And {n_people - max_people} more." if n_people > max_people else ""
            spoken = head + " " + " ".join(ln if re.search(r"[.?!]\"?$", ln) else ln + "." for ln in lines) + more
        if not include_groups and not group:
            groups_waiting = len({m.chat_id for m in self.get_messages_needing_reply(limit=40, include_groups=True) if m.is_group})
            if groups_waiting:
                spoken += (f" {groups_waiting} group chat{'s' if groups_waiting != 1 else ''} also "
                           f"{'have' if groups_waiting != 1 else 'has'} new messages - ask if you want them.")

        return {
            "total_pending": len(pending),
            "people": n_people,
            "urgent_count": len(urgent),
            "normal_count": len(normal),
            "urgent_messages": [m.to_dict() for m in urgent],
            "normal_messages": [m.to_dict() for m in normal],
            "spoken_summary": spoken,
        }

    @staticmethod
    def _spoken_name(name: str) -> str:
        """'sushmitaa mahesh' -> 'Sushmitaa Mahesh', 'Scooby!!' -> 'Scooby' (names read out naturally)."""
        n = re.sub(r"[^\w\s.'-]", "", name or "").strip() or "Someone"
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
