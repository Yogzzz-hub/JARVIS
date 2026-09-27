"""'Who is Yoga?' answered from the owner's own data: contacts, recent WhatsApp chats and the learned reply style.

``known_person`` is used by the router (cached, cheap) so general questions such as "who is Elon Musk" still go
to chat; ``describe_person`` builds the spoken answer.
"""
from __future__ import annotations

import re
import time
from typing import Any, Optional

_CACHE: dict[str, Any] = {"at": 0.0, "names": set()}
TTL_S = 300.0


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (name or "").lower()).strip()


def _inbox():
    from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
    return WhatsAppInbox.get_default()


def known_names() -> set[str]:
    if time.time() - _CACHE["at"] < TTL_S:
        return _CACHE["names"]
    names: set[str] = set()
    try:
        from jarvis.integrations.whatsapp.contact_resolver import ContactResolver
        for c in ContactResolver()._contacts:
            n = _norm(c.display_name)
            if n:
                names.add(n)
                names.add(n.split()[0])
    except Exception:
        pass
    try:
        with _inbox()._get_conn() as conn:
            for (n,) in conn.execute("SELECT DISTINCT sender_display_name FROM whatsapp_messages WHERE is_from_me = 0 LIMIT 2000"):
                n = _norm(n)
                if n and not n.isdigit():
                    names.add(n)
                    names.add(n.split()[0])
    except Exception:
        pass
    _CACHE.update(at=time.time(), names=names)
    return names


def known_person(name: str) -> bool:
    n = _norm(name)
    return bool(n) and len(n) >= 2 and n in known_names()


def _ago(ts: float) -> str:
    d = max(0.0, time.time() - ts)
    if d < 3600:
        return f"{max(1, int(d // 60))} minutes ago"
    if d < 86400:
        return f"{int(d // 3600)} hours ago"
    return f"{int(d // 86400)} days ago"


def describe_person(name: str) -> dict[str, Any]:
    query = (name or "").strip()
    contact, ambiguous, _ = (None, [], None)
    try:
        from jarvis.integrations.whatsapp.contact_resolver import ContactResolver
        contact, ambiguous, _ = ContactResolver().resolve(query)
    except Exception:
        pass
    if ambiguous:
        names = ", ".join(c.display_name for c in ambiguous[:4])
        return {"status": "AMBIGUOUS", "message": f"You have more than one {query} in your contacts: {names}. Which one?"}

    inbox = _inbox()
    msg = None
    try:
        msg = inbox.find_latest_incoming(contact.jid if contact else query, direct_only=True) or \
            inbox.find_latest_incoming(contact.display_name if contact else query, direct_only=True)
    except Exception:
        pass
    display = contact.display_name if contact else (msg.sender_display_name if msg else query)
    jid = contact.jid if contact else (msg.chat_id if msg else "")
    if not contact and not msg:
        return {"status": "NOT_FOUND", "message": f"{query} isn't in your contacts or WhatsApp chats."}

    number = (contact.phone_number if contact and contact.phone_number else jid.split("@")[0]) if jid else ""
    parts = [f"{display} is one of your WhatsApp contacts" + (f" (+{number.lstrip('+')})" if number else "") + "."]
    if msg:
        from jarvis.integrations.whatsapp.inbox import describe_message
        parts.append(f"Their last message came {_ago(msg.timestamp)}: {describe_message(msg.text)}.")
        try:
            history = inbox.get_chat_history(msg.chat_id, limit=40)
            parts.append(f"You have {len(history)} recent messages with them.")
        except Exception:
            pass
    try:
        from jarvis.integrations.whatsapp.personal_reply.agent import get_personal_reply_agent
        prof = get_personal_reply_agent().store.load_profile(jid) if jid else None
        if prof is not None:
            s = prof.summary()
            parts.append(f"You usually write to them in {s['preferred_language'].title()} ({s['tone'].lower()}, "
                         f"{s['typical_length']}).")
    except Exception:
        pass
    return {"status": "SUCCESS", "name": display, "jid": jid, "message": " ".join(parts)}
