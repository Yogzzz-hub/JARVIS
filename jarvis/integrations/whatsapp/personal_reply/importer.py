"""Import conversation history and turn it into USER-authored reply examples.

Sources:
* a WhatsApp "Export chat" text file (Android ``12/05/24, 9:41 pm - Name: text`` or iOS
  ``[12/05/24, 9:41:23 PM] Name: text``), or
* history already stored by the WhatsApp connector (``WhatsAppInbox``, with ``is_from_me`` flags).

Messages are separated into USER_MESSAGES (the account owner) and CONTACT_MESSAGES. Only the owner's
messages ever describe the owner's style; the contact's messages are used as *context* for examples.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Optional

from jarvis.integrations.whatsapp.personal_reply.models import ChatLine, Direction, ReplyExample, ExampleSource

_ANDROID = re.compile(r"^‎?(?P<date>\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}),?\s+(?P<time>\d{1,2}[:.]\d{2}(?:[:.]\d{2})?)"
                      r"(?:[\s  ]*(?P<ampm>[ap]\.?\s?m\.?))?\s+-\s+(?P<rest>.*)$", re.I)
_IOS = re.compile(r"^‎?\[(?P<date>\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}),?\s+(?P<time>\d{1,2}[:.]\d{2}(?:[:.]\d{2})?)"
                  r"(?:[\s  ]*(?P<ampm>[ap]\.?\s?m\.?))?\]\s+(?P<rest>.*)$", re.I)

# Lines that are not something anybody typed.
SKIP_TEXT = re.compile(
    r"^(?:<media omitted>|<attached:.*>|‎?(?:image|video|audio|sticker|gif|document|contact card) omitted|"
    r"this message was deleted|you deleted this message|null|missed (?:voice|video) call|"
    r"waiting for this message\.?.*|messages and calls are end-to-end encrypted.*|"
    r"<this message was edited>)$", re.I)
_EDITED = re.compile(r"\s*<this message was edited>\s*$", re.I)


class ImportError_(ValueError):
    """Raised with a user-facing explanation (e.g. group export, cannot tell who the owner is)."""


@dataclass
class ParsedChat:
    lines: list[ChatLine]
    participants: list[str]
    owner_name: str
    contact_name: str
    skipped_system: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def user_messages(self) -> list[ChatLine]:
        return [ln for ln in self.lines if ln.direction == Direction.USER]

    @property
    def contact_messages(self) -> list[ChatLine]:
        return [ln for ln in self.lines if ln.direction == Direction.CONTACT]


def _date_order(dates: list[str]) -> str:
    firsts, seconds = [], []
    for d in dates:
        parts = re.split(r"[/.-]", d)
        if len(parts) == 3:
            firsts.append(int(parts[0]))
            seconds.append(int(parts[1]))
    if any(x > 12 for x in seconds) and not any(x > 12 for x in firsts):
        return "MDY"
    return "DMY"


def _to_ts(date: str, time_s: str, ampm: Optional[str], order: str) -> float:
    a, b, y = (int(p) for p in re.split(r"[/.-]", date))
    day, month = (a, b) if order == "DMY" else (b, a)
    if y < 100:
        y += 2000
    parts = [int(p) for p in re.split(r"[:.]", time_s)]
    hour, minute, sec = parts[0], parts[1], parts[2] if len(parts) > 2 else 0
    if ampm:
        pm = ampm.lower().startswith("p")
        if pm and hour < 12:
            hour += 12
        elif not pm and hour == 12:
            hour = 0
    try:
        return datetime(y, month, day, hour, minute, sec).timestamp()
    except ValueError:
        return 0.0


def _norm_name(name: str) -> str:
    return re.sub(r"[^\w+]", "", (name or "").casefold())


def parse_export(text: str, owner_names: Iterable[str] = (), contact_name: str = "") -> ParsedChat:
    raw: list[tuple[str, str, Optional[str], str]] = []  # date, time, ampm, rest
    for line in (text or "").replace("\r\n", "\n").split("\n"):
        m = _IOS.match(line) or _ANDROID.match(line)
        if m:
            raw.append((m.group("date"), m.group("time"), m.group("ampm"), m.group("rest")))
        elif raw and line.strip():
            d, t, ap, rest = raw[-1]
            raw[-1] = (d, t, ap, rest + "\n" + line)  # multi-line message continuation
    if not raw:
        raise ImportError_("This doesn't look like a WhatsApp chat export (no dated message lines found).")
    order = _date_order([r[0] for r in raw])
    entries: list[tuple[float, str, str]] = []
    skipped = 0
    for d, t, ap, rest in raw:
        if ": " not in rest:
            skipped += 1  # system line without a sender
            continue
        sender, body = rest.split(": ", 1)
        body = _EDITED.sub("", body.strip())
        if not body or SKIP_TEXT.match(body.strip()):
            skipped += 1
            continue
        entries.append((_to_ts(d, t, ap, order), sender.strip().lstrip("‎"), body))
    participants = list(dict.fromkeys(s for _, s, _ in entries))
    if len(participants) > 2:
        raise ImportError_(f"This export has {len(participants)} participants, so it's a group chat. "
                           "Personal reply learning uses one-to-one chats only.")
    owner = _pick_owner(participants, owner_names, contact_name)
    contact = next((p for p in participants if p != owner), contact_name or "")
    lines = [ChatLine(timestamp=ts, sender=s, direction=Direction.USER if s == owner else Direction.CONTACT, text=b,
                      message_id=f"imp_{hashlib.sha1(f'{ts}|{s}|{b}'.encode()).hexdigest()[:16]}")
             for ts, s, b in entries]
    return ParsedChat(lines=lines, participants=participants, owner_name=owner, contact_name=contact, skipped_system=skipped)


def _pick_owner(participants: list[str], owner_names: Iterable[str], contact_name: str) -> str:
    owners = {_norm_name(n) for n in owner_names if n}
    owners |= {"you"}
    if len(participants) == 1:
        p = participants[0]
        if _norm_name(p) in owners:
            return p
        raise ImportError_("Only one person wrote in this export, so there are no replies of yours to learn from.")
    by_owner = [p for p in participants if _norm_name(p) in owners]
    if len(by_owner) == 1:
        return by_owner[0]
    if contact_name:
        c = _norm_name(contact_name)
        matches = [p for p in participants if c and (c in _norm_name(p) or _norm_name(p) in c)]
        if len(matches) == 1:
            return next(p for p in participants if p != matches[0])
    raise ImportError_(f"Which of these is you: {', '.join(participants)}? Set your name (owner_name) and import again.")


def lines_from_inbox(inbox: Any, chat_id: str, limit: int = 5000) -> list[ChatLine]:
    """Authorized history already stored by the WhatsApp connector (direct chats only)."""
    if not inbox.is_direct_chat(chat_id):
        raise ImportError_("Group chats are never used for personal reply learning.")
    out = []
    for m in inbox.get_chat_history(chat_id, limit=limit):
        if not m.text or SKIP_TEXT.match(m.text.strip()):
            continue
        out.append(ChatLine(timestamp=m.timestamp, sender=m.sender_display_name, text=m.text, message_id=m.message_id,
                            direction=Direction.USER if m.is_from_me else Direction.CONTACT))
    return out


def _split_for(key: str) -> str:
    h = int(hashlib.sha1(key.encode("utf-8")).hexdigest()[:8], 16) % 100
    return "HOLDOUT" if h < 10 else "DEV" if h < 20 else "TRAIN"


def build_examples(contact_id: str, lines: list[ChatLine], max_gap_s: float = 6 * 3600, burst_s: float = 600,
                   context_turns: int = 3, source: ExampleSource = ExampleSource.IMPORT) -> list[ReplyExample]:
    """Pair what the contact said with how the owner replied (consecutive owner lines form one reply)."""
    lines = sorted(lines, key=lambda ln: ln.timestamp)
    examples: list[ReplyExample] = []
    i = 0
    while i < len(lines):
        if lines[i].direction != Direction.USER:
            i += 1
            continue
        j = i
        reply_parts = [lines[i].text]
        while j + 1 < len(lines) and lines[j + 1].direction == Direction.USER and lines[j + 1].timestamp - lines[j].timestamp <= burst_s:
            j += 1
            reply_parts.append(lines[j].text)
        ctx = []
        k = i - 1
        while k >= 0 and lines[k].direction == Direction.CONTACT and len(ctx) < context_turns:
            if lines[i].timestamp - lines[k].timestamp > max_gap_s:
                break
            ctx.insert(0, lines[k].text)
            k -= 1
        if ctx:
            reply = "\n".join(reply_parts)
            origin_source = ExampleSource.LIVE_USER if lines[i].origin == "live" else source
            examples.append(ReplyExample(contact_id=contact_id, context="\n".join(ctx), reply=reply,
                                         timestamp=lines[i].timestamp, source=origin_source,
                                         split=_split_for(f"{contact_id}|{lines[i].timestamp}|{reply}")))
        i = j + 1
    return examples
