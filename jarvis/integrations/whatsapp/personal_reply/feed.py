"""Chat history in any common format -> the owner's reply examples for one person.

Supported (detected from the content, not the file name):

* WhatsApp "Export chat": the ``.txt`` (Android / iPhone, 12 or 24 hour clock) or the ``.zip`` the phone shares;
* WhatsApp Web / Desktop copy-paste: ``[9:41 pm, 12/05/2024] Name: text``;
* JSON: WhatsApp Chat Exporter (``{jid: {"name", "messages": {id: {"from_me", "timestamp", "data"}}}}``),
  Telegram Desktop (``result.json``), Instagram / Facebook Messenger (``message_1.json``), or any list of
  ``{"sender"/"from", "text"/"message", "timestamp"/"date", "from_me"}`` objects;
* CSV with a header (sender / text / time / from_me columns, any common names);
* a plain transcript: ``Name: text`` lines (or ``You:`` / ``Me:`` for your own lines), no timestamps needed.

Every source becomes the same (timestamp, sender, text, from_me) rows, so the same one-to-one checks apply:
group chats are refused, and only the owner's own messages ever shape the owner's style.

The feed folder (``data/whatsapp_feed``): drop exports there - one file per person, or a Chat Exporter JSON
with many chats - and say "learn my WhatsApp chats". Each file is imported once (by content hash).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from jarvis.integrations.whatsapp.personal_reply.importer import (
    ImportError_, ParsedChat, chat_from_entries, parse_export,
)

FEED_DIR = Path(__file__).resolve().parents[4] / "data" / "whatsapp_feed"

Entry = tuple[float, str, str, Optional[bool]]


@dataclass
class FeedChat:
    chat: ParsedChat
    contact_hint: str          # a JID when the source has one, else the contact's name
    source_format: str


# ------------------------------------------------------------------ decoding
def decode(data: bytes | str) -> str:
    if isinstance(data, str):
        return data
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


def _unzip(data: bytes) -> list[tuple[str, bytes]]:
    """Chat files inside a WhatsApp / Telegram / Instagram export zip (media is ignored)."""
    out = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist():
            name = info.filename
            if info.is_dir() or info.file_size > 50_000_000 or "__MACOSX" in name:
                continue
            if name.lower().endswith((".txt", ".json", ".csv")):
                out.append((name, z.read(info)))
    if not out:
        raise ImportError_("That zip has no chat text inside (expected _chat.txt or a .json / .csv chat file).")
    return out


# ------------------------------------------------------------------ timestamps
def _ts(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)) or (isinstance(value, str) and re.fullmatch(r"\d{9,13}(?:\.\d+)?", value.strip())):
        v = float(value)
        return v / 1000.0 if v > 1e11 else v
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        pass
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y, %H:%M", "%d/%m/%y %H:%M", "%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M:%S",
                "%d-%m-%Y %H:%M", "%d/%m/%Y %I:%M %p", "%d/%m/%Y, %I:%M %p", "%d.%m.%Y %H:%M"):
        try:
            return datetime.strptime(text, fmt).timestamp()
        except ValueError:
            continue
    return 0.0


def _mojibake(text: str) -> str:
    """Facebook/Instagram exports store UTF-8 as latin-1 escapes ("ð\\x9f\\x98\\x82" for 😂)."""
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def _flag(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    return str(value).strip().lower() in ("1", "true", "yes", "y", "me", "you", "sent", "outgoing", "out")


_SENDER_KEYS = ("sender", "from", "author", "sender_name", "name", "user", "speaker", "who")
_TEXT_KEYS = ("text", "message", "content", "body", "data", "msg")
_TIME_KEYS = ("timestamp", "timestamp_ms", "time", "date", "datetime", "ts", "sent_at", "created_at", "date_unixtime")
_MINE_KEYS = ("from_me", "fromMe", "is_from_me", "isFromMe", "outgoing", "is_outgoing", "me", "sent_by_me")


def _pick(obj: dict, keys: Iterable[str]) -> Any:
    lower = {str(k).lower(): v for k, v in obj.items()}
    for k in keys:
        if k.lower() in lower and lower[k.lower()] not in (None, ""):
            return lower[k.lower()]
    return None


def _text_of(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):  # Telegram: ["plain", {"type": "bold", "text": "x"}]
        return "".join(v if isinstance(v, str) else str(v.get("text", "")) for v in value if isinstance(v, (str, dict)))
    if isinstance(value, dict):
        return str(value.get("text") or value.get("body") or "")
    return ""


# ------------------------------------------------------------------ format parsers
def _json_chats(obj: Any) -> list[tuple[str, str, list[Entry]]]:
    """(format, contact hint, entries) for every one-to-one chat found in a JSON document."""
    # Telegram Desktop: {"name", "type": "personal_chat", "messages": [{"from", "text", "date"}]}
    if isinstance(obj, dict) and isinstance(obj.get("messages"), list) and "type" in obj and any(
            isinstance(m, dict) and "from" in m for m in obj["messages"]):
        if obj.get("type") not in (None, "personal_chat", "saved_messages", "bot_chat"):
            raise ImportError_("This Telegram export is a group or channel. Only one-to-one chats are used.")
        rows = [(_ts(m.get("date_unixtime") or m.get("date")), str(m.get("from") or ""), _text_of(m.get("text")), None)
                for m in obj["messages"] if isinstance(m, dict) and m.get("type", "message") == "message"]
        return [("telegram", str(obj.get("name") or ""), rows)]
    # Instagram / Messenger: {"participants": [{"name"}], "messages": [{"sender_name", "content", "timestamp_ms"}]}
    if isinstance(obj, dict) and isinstance(obj.get("participants"), list) and isinstance(obj.get("messages"), list):
        names = [_mojibake(str(p.get("name", ""))) for p in obj["participants"] if isinstance(p, dict)]
        if len(names) > 2:
            raise ImportError_("This Instagram/Messenger export is a group chat. Only one-to-one chats are used.")
        rows = [(_ts(m.get("timestamp_ms")), _mojibake(str(m.get("sender_name", ""))), _mojibake(str(m.get("content", ""))), None)
                for m in obj["messages"] if isinstance(m, dict) and m.get("content")]
        return [("instagram", names[0] if names else "", rows)]
    # WhatsApp Chat Exporter: {jid: {"name": ..., "messages": {id: {"from_me", "timestamp", "data"}}}}
    if isinstance(obj, dict) and obj and all(isinstance(v, dict) and isinstance(v.get("messages"), (dict, list))
                                             for v in obj.values()):
        chats = []
        for jid, chat in obj.items():
            if str(jid).endswith("@g.us") or chat.get("is_group"):
                continue  # groups are never learned from
            msgs = chat["messages"].values() if isinstance(chat["messages"], dict) else chat["messages"]
            name = str(chat.get("name") or str(jid).split("@")[0])
            rows = []
            for m in msgs:
                if not isinstance(m, dict):
                    continue
                mine = _flag(_pick(m, _MINE_KEYS))
                sender = str(_pick(m, _SENDER_KEYS) or ("You" if mine else name))
                rows.append((_ts(_pick(m, _TIME_KEYS)), sender, _text_of(_pick(m, _TEXT_KEYS)), mine))
            chats.append(("whatsapp_chat_exporter", str(jid) if "@" in str(jid) else name, rows))
        if chats:
            return chats
        raise ImportError_("That file only has group chats. Only one-to-one chats are used.")
    # generic: [{"sender", "text", "time", "from_me"}] or {"messages": [...]}
    items = obj.get("messages") if isinstance(obj, dict) else obj
    if isinstance(items, list) and items and all(isinstance(m, dict) for m in items):
        rows = [(_ts(_pick(m, _TIME_KEYS)), str(_pick(m, _SENDER_KEYS) or ""), _text_of(_pick(m, _TEXT_KEYS)),
                 _flag(_pick(m, _MINE_KEYS))) for m in items]
        if any(r[1] or r[3] is not None for r in rows):
            rows = _complete_flags(rows)
            name = str(obj.get("name") or obj.get("contact") or "") if isinstance(obj, dict) else ""
            return [("json", name, rows)]
    raise ImportError_("I don't recognise this JSON chat format. Use a WhatsApp export, or a list of "
                       '{"sender": ..., "text": ..., "timestamp": ...} messages.')


def _csv_chat(text: str) -> list[Entry]:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
    if not rows or not rows[0]:
        raise ImportError_("The CSV file is empty.")
    out = []
    for r in rows:
        mine = _flag(_pick(r, _MINE_KEYS))
        out.append((_ts(_pick(r, _TIME_KEYS)), str(_pick(r, _SENDER_KEYS) or ("You" if mine else "")), str(_pick(r, _TEXT_KEYS) or ""), mine))
    if not any(e[2] for e in out):
        raise ImportError_("The CSV needs a text/message column (and a sender or from_me column).")
    return _complete_flags(out)


def _complete_flags(rows: list[Entry]) -> list[Entry]:
    """Some rows say from_me, others don't: a sender who is ever marked as the owner is always the owner."""
    if all(r[3] is not None for r in rows):
        return rows
    mine = {s for _, s, _, m in rows if m and s}
    if mine:
        return [(t, s, x, (m if m is not None else s in mine)) for t, s, x, m in rows]
    return [(t, s, x, None) for t, s, x, _ in rows]


# WhatsApp Web / Desktop copy: "[9:41 pm, 12/05/2024] Name: text"
_WEB_COPY = re.compile(r"^\[(?P<time>\d{1,2}[:.]\d{2})\s*(?P<ampm>[ap]\.?\s?m\.?)?,\s*(?P<date>\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})\]\s+"
                       r"(?P<sender>[^:]{1,60}):\s?(?P<text>.*)$", re.I)
_TRANSCRIPT = re.compile(r"^(?P<sender>[^:\[\]]{1,40}):\s+(?P<text>.+)$")
_ME = re.compile(r"^(?:you|me|myself|i|owner|mine)$", re.I)


def _web_copy(text: str) -> list[Entry]:
    rows: list[Entry] = []
    for line in text.splitlines():
        m = _WEB_COPY.match(line.strip())
        if m:
            ts = _ts(f"{m.group('date')} {m.group('time').replace('.', ':')}{(' ' + m.group('ampm').replace('.', '').replace(' ', '').upper()) if m.group('ampm') else ''}")
            rows.append((ts, m.group("sender").strip(), m.group("text"), None))
        elif rows and line.strip():
            t, s, x, mine = rows[-1]
            rows[-1] = (t, s, x + "\n" + line, mine)
    return rows


def _transcript(text: str) -> list[Entry]:
    rows: list[Entry] = []
    for i, line in enumerate(text.splitlines()):
        m = _TRANSCRIPT.match(line.strip())
        if m:
            sender = m.group("sender").strip()
            rows.append((1_600_000_000.0 + len(rows) * 60, sender, m.group("text"), True if _ME.match(sender) else None))
        elif rows and line.strip():
            t, s, x, mine = rows[-1]
            rows[-1] = (t, s, x + "\n" + line.strip(), mine)
    if rows and any(r[3] for r in rows):
        rows = [(t, s, x, bool(m)) for t, s, x, m in rows]  # "You:" / "Me:" marks the owner's lines
    return rows


# ------------------------------------------------------------------ entry point
def _hint_from_name(filename: str) -> str:
    stem = Path(filename or "").stem
    m = re.search(r"(?:WhatsApp Chat (?:with|-)\s*|Chat with\s+)(?P<n>.+)$", stem, re.I)
    name = m.group("n") if m else ("" if stem.lower() in ("_chat", "chat", "result", "message_1", "messages", "export") else stem)
    return re.sub(r"[_]+", " ", name).strip()


def parse_any(data: bytes | str, filename: str = "", owner_names: Iterable[str] = (), contact_name: str = "") -> list[FeedChat]:
    """Every one-to-one chat in ``data`` (a file's bytes or pasted text), whatever the format."""
    owner_names = list(owner_names)
    if isinstance(data, bytes) and data[:2] == b"PK":
        out: list[FeedChat] = []
        errors = []
        for name, blob in _unzip(data):
            try:
                out += parse_any(blob, name, owner_names, contact_name or _hint_from_name(filename))
            except ImportError_ as exc:
                errors.append(str(exc))
        if not out:
            raise ImportError_(errors[0] if errors else "No one-to-one chat found in that zip.")
        return out
    text = decode(data).replace("\r\n", "\n").lstrip("﻿")
    hint = contact_name or _hint_from_name(filename)
    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            obj = None
        if obj is not None:
            return [FeedChat(chat_from_entries(rows, owner_names, hint or name), hint or name, fmt)
                    for fmt, name, rows in _json_chats(obj)]
    first_lines = [ln for ln in text.splitlines() if ln.strip()][:5]
    if first_lines and sum(bool(_WEB_COPY.match(ln.strip())) for ln in first_lines) >= min(2, len(first_lines)):
        return [FeedChat(chat_from_entries(_web_copy(text), owner_names, hint), hint, "whatsapp_web_copy")]
    try:
        return [FeedChat(parse_export(text, owner_names=owner_names, contact_name=hint), hint, "whatsapp_export")]
    except ImportError_ as exc:
        if "doesn't look like" not in str(exc):
            raise
    header = first_lines[0].lower() if first_lines else ""
    if (filename.lower().endswith(".csv") or re.search(r"(?:sender|from|author).*(?:,|;|\t).*(?:text|message|content)|"
                                                       r"(?:text|message|content).*(?:,|;|\t).*(?:sender|from|author)", header)):
        return [FeedChat(chat_from_entries(_csv_chat(text), owner_names, hint), hint, "csv")]
    rows = _transcript(text)
    if len(rows) >= 2:
        return [FeedChat(chat_from_entries(rows, owner_names, hint), hint, "transcript")]
    raise ImportError_("I couldn't read that chat. Supported: WhatsApp export (.txt or .zip), WhatsApp Web copy, "
                       "Telegram / Instagram / Chat Exporter JSON, CSV, or 'Name: message' lines.")


def file_hash(data: bytes | str) -> str:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()[:24]
