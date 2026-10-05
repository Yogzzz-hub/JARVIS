"""WhatsApp Messaging Tools for JARVIS EDGE.
Integrates with ContactResolver, Phase 5 Policy, and ActionLedger.
Risk Class: EXTERNAL_EFFECT.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
import time
from typing import Any, Literal, Optional
from pydantic import Field

from jarvis.integrations.whatsapp.contact_resolver import ContactResolver
from jarvis.security.confirmation.manager import ConfirmationManager
from jarvis.security.ledger.models import LedgerState
from jarvis.tools.base import Contract, ExecutionMethod, IdempotencyClass, RiskLevel, Tool, ToolDefinition

logger = logging.getLogger("jarvis.tools.whatsapp")


def _default_country_code() -> str:
    try:
        import tomllib
        from jarvis.config import ROOT
        path = ROOT.parent / "config/whatsapp.toml"
        if path.exists():
            with path.open("rb") as f:
                return str(tomllib.load(f).get("whatsapp", {}).get("default_country_code", "91")).lstrip("+")
    except Exception:
        pass
    return "91"


def phone_to_jid(raw: str, country_code: str | None = None) -> str | None:
    """'+91 98765 43210' / '9876543210' / 'x@s.whatsapp.net' -> JID; None when not a phone number."""
    raw = (raw or "").strip()
    if "@" in raw:
        return raw
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 7 or len(digits) > 15 or re.search(r"[A-Za-z]", raw):
        return None
    if raw.startswith("+") or raw.startswith("00"):
        digits = digits[2:] if raw.startswith("00") else digits
    elif len(digits) == 10:
        digits = (country_code or _default_country_code()) + digits
    elif len(digits) == 11 and digits.startswith("0"):
        digits = (country_code or _default_country_code()) + digits[1:]
    return f"{digits}@s.whatsapp.net"


_last_sent: dict[str, Any] = {}


def get_last_sent() -> dict[str, Any]:
    """Return info about the most recently sent WhatsApp message."""
    return dict(_last_sent)



class SendWhatsAppMessageInput(Contract):
    recipient: str = Field(min_length=1, max_length=256, description="Contact name, phone number, or WhatsApp JID")
    message: str = Field(min_length=1, max_length=4096, description="Message text to send")
    confirmation_ticket: Optional[str] = Field(default=None, description="Confirmation ticket ID if action required approval")
    allow_group: bool = Field(default=False, description="Only True when the owner explicitly asked to write in a group")


class SendWhatsAppMessageOutput(Contract):
    status: str
    recipient: str
    recipient_jid: str
    message: str
    message_id: Optional[str] = None
    ticket_id: Optional[str] = None
    action_ledger_status: str = "COMMITTED"
    evidence: dict = Field(default_factory=dict)


class SendWhatsAppMessageTool(Tool):
    definition = ToolDefinition(
        name="send_whatsapp_message",
        description="Sends a WhatsApp message to a specified contact or phone number. Requires contact resolution and verified transport receipt. Risk level: EXTERNAL_EFFECT.",
        input_model=SendWhatsAppMessageInput,
        output_model=SendWhatsAppMessageOutput,
        read_only=False,
        risk=RiskLevel.EXTERNAL_EFFECT,
        timeout_s=30.0,
        tags=("messaging", "whatsapp", "communication"),
        execution_method=ExecutionMethod.CLI,
        idempotency=IdempotencyClass.NON_IDEMPOTENT,
    )

    def __init__(
        self,
        transport: Any = None,
        contact_resolver: Optional[ContactResolver] = None,
        confirmation_manager: Optional[ConfirmationManager] = None,
    ) -> None:
        self.transport = transport
        self.resolver = contact_resolver or ContactResolver()
        self.confirmation_manager = confirmation_manager

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = SendWhatsAppMessageInput(**arguments)

        recipient_raw = arguments.recipient.strip()
        msg_text = arguments.message.strip()
        allow_group = arguments.allow_group

        # 0. A group only when the owner named it ("send hi to the CSE group") - never by accident.
        named_group = group_scope_from_text(recipient_raw).get("group") if _GROUP_WORD.search(recipient_raw) else None
        if named_group:
            from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
            group_id, label = _resolve_group(WhatsAppInbox.get_default(), named_group)
            if group_id is None:
                return {"status": "FAILED", "recipient": recipient_raw, "recipient_jid": "", "message": label,
                        "message_id": None, "action_ledger_status": "CANCELLED", "evidence": {"unknown_group": named_group}}
            recipient_raw, allow_group = group_id, True
        if "@" in recipient_raw and not recipient_raw.endswith(("@s.whatsapp.net", "@lid")) and not allow_group:
            return {"status": "FAILED", "recipient": recipient_raw, "recipient_jid": recipient_raw,
                    "message": "That is a group chat. I only write in a group when you name it, e.g. 'send it to the CSE group'.",
                    "message_id": None, "action_ledger_status": "CANCELLED", "evidence": {"group_blocked": True}}

        # 1. Contact Resolution & Ambiguity Check
        contact, ambiguous, prompt = self.resolver.resolve(recipient_raw)
        if ambiguous:
            return {
                "status": "AMBIGUOUS_CONTACT",
                "recipient": recipient_raw,
                "recipient_jid": "",
                "message": prompt or f"Multiple contacts match '{recipient_raw}'. Please clarify.",
                "message_id": None,
                "action_ledger_status": "CANCELLED",
                "evidence": {"ambiguous_contacts": [c.display_name for c in ambiguous]},
            }

        target_jid = contact.jid if contact else phone_to_jid(recipient_raw)
        resolved_name = contact.display_name if contact else recipient_raw
        if named_group:
            target_jid, resolved_name = recipient_raw, f"the {_last_group.get('name', 'group')} group"
        if not target_jid:
            return {
                "status": "FAILED",
                "recipient": recipient_raw,
                "recipient_jid": "",
                "message": (f"I don't have a WhatsApp number for {recipient_raw}. Add it under [whatsapp.contacts] in "
                            f"config/whatsapp.toml, import your contacts.vcf, or tell me the phone number."),
                "message_id": None,
                "action_ledger_status": "CANCELLED",
                "evidence": {"unknown_contact": recipient_raw},
            }

        # 2. Confirmation Verification for EXTERNAL_EFFECT
        ticket_id = arguments.confirmation_ticket
        if ticket_id and self.confirmation_manager:
            ticket = self.confirmation_manager.get_ticket(ticket_id)
            ticket_st = getattr(ticket, "status", None) if ticket else None
            ticket_st_val = getattr(ticket_st, "value", str(ticket_st)) if ticket_st else ""
            if not ticket or ticket_st_val not in ("APPROVED", "CONSUMED"):
                return {
                    "status": "CONFIRMATION_REQUIRED",
                    "recipient": resolved_name,
                    "recipient_jid": target_jid,
                    "message": f"Confirmation required to send message to {resolved_name}.",
                    "ticket_id": ticket_id,
                    "action_ledger_status": "REQUESTED",
                    "evidence": {"requires_approval": True},
                }

        # 3. Transport Send Execution & Receipt Verification
        res = None
        request_submitted = False
        if not self.transport:
            # Fallback: connect directly to local Baileys bridge WebSocket (ws://127.0.0.1:8768)
            try:
                import websockets, uuid, json, asyncio
                async def _direct_bridge_send():
                    nonlocal request_submitted
                    async with websockets.connect("ws://127.0.0.1:8768/commands", open_timeout=4.0) as ws:
                        req_id = str(uuid.uuid4())
                        request_submitted = True
                        await ws.send(json.dumps({
                            "id": req_id,
                            "action": "send_text",
                            "payload": {"to": target_jid, "text": msg_text}
                        }))
                        start_wait = time.time()
                        while time.time() - start_wait < 8.0:
                            raw = await asyncio.wait_for(ws.recv(), timeout=4.0)
                            msg = json.loads(raw)
                            if msg.get("id") == req_id:
                                if not msg.get("success", False):
                                    return msg
                                return msg.get("result") or {"status": "UNCERTAIN"}
                        raise TimeoutError("WhatsApp bridge did not acknowledge message delivery within deadline")
                res = asyncio.run(_direct_bridge_send())
            except Exception as bridge_exc:
                logger.warning("Direct bridge send error: %s", bridge_exc)
                return {
                    "status": "UNCERTAIN" if request_submitted else "FAILED",
                    "recipient": resolved_name,
                    "recipient_jid": target_jid,
                    "message": f"WhatsApp transport error: {bridge_exc}",
                    "message_id": None,
                    "action_ledger_status": "UNCERTAIN" if request_submitted else "FAILED",
                    "evidence": {"transport_connected": False, "error": str(bridge_exc)},
                }
        else:
            try:
                import asyncio
                transport_loop = getattr(self.transport, "_loop", None)
                if transport_loop and transport_loop.is_running():
                    if hasattr(self.transport, "send_text"):
                        fut = asyncio.run_coroutine_threadsafe(
                            self.transport.send_text(target_jid, msg_text),
                            transport_loop
                        )
                        res = fut.result(timeout=10.0)
                    elif hasattr(self.transport, "sendTextMessage"):
                        fut = asyncio.run_coroutine_threadsafe(
                            self.transport.sendTextMessage(target_jid, msg_text),
                            transport_loop
                        )
                        res = fut.result(timeout=10.0)
                    else:
                        raise ValueError("Configured WhatsApp transport has no send method")
                else:
                    if hasattr(self.transport, "send_text"):
                        res = asyncio.run(self.transport.send_text(target_jid, msg_text))
                    elif hasattr(self.transport, "sendTextMessage"):
                        res = asyncio.run(self.transport.sendTextMessage(target_jid, msg_text))
                    else:
                        raise ValueError("Configured WhatsApp transport has no send method")
            except Exception as exc:
                logger.error("Failed to send WhatsApp message via transport: %s", exc)
                return {
                    "status": "FAILED" if isinstance(exc, ValueError) else "UNCERTAIN",
                    "recipient": resolved_name,
                    "recipient_jid": target_jid,
                    "message": f"Transport failure: {exc}",
                    "message_id": None,
                    "action_ledger_status": "FAILED" if isinstance(exc, ValueError) else "UNCERTAIN",
                    "evidence": {"transport_connected": True, "error": str(exc)},
                }

        send_result = res.get("result") if (isinstance(res, dict) and isinstance(res.get("result"), dict)) else res
        msg_id = send_result.get("message_id") if isinstance(send_result, dict) else None
        acknowledged = isinstance(res, dict) and (res.get("success") is True or res.get("status") == "SENT")
        uncertain = (isinstance(res, dict) and res.get("status") == "UNCERTAIN") or (
            isinstance(send_result, dict) and send_result.get("status") == "UNCERTAIN") or (
            not msg_id and (acknowledged or isinstance(send_result, dict) and send_result.get("status") == "SENT"))
        if uncertain:
            return {"status": "UNCERTAIN", "recipient": resolved_name, "recipient_jid": target_jid,
                    "message": "WhatsApp submission outcome is uncertain. Check the conversation before retrying.",
                    "message_id": None, "action_ledger_status": "UNCERTAIN",
                    "evidence": {"transport_ack": False, "outcome_unknown": True}}
        is_sent = (
            (isinstance(send_result, dict) and send_result.get("status") == "SENT")
            or (isinstance(res, dict) and res.get("success") is True)
        )

        if not is_sent or not msg_id:
            err_msg = (res.get("error") if isinstance(res, dict) else None) or "WhatsApp message delivery not confirmed by bridge"
            return {
                "status": "FAILED",
                "recipient": resolved_name,
                "recipient_jid": target_jid,
                "message": err_msg,
                "message_id": None,
                "action_ledger_status": "FAILED",
                "evidence": {"transport_ack": False, "raw_response": str(res)},
            }

        # Mark existing messages in this conversation as replied
        try:
            from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
            WhatsAppInbox.get_default().mark_as_replied(target_jid)
        except Exception:
            pass

        # Record last sent for follow-up questions ("to whom did you send", "who did you message")
        _last_sent.clear()
        _last_sent.update({
            "recipient": resolved_name,
            "recipient_jid": target_jid,
            "message": msg_text,
            "timestamp": time.time(),
        })

        # Only report verified sent when transport ACK is confirmed
        return {
            "status": "SENT",
            "recipient": resolved_name,
            "recipient_jid": target_jid,
            "message": f"Message sent to {resolved_name}: '{msg_text}'",
            "message_id": msg_id,
            "ticket_id": ticket_id,
            "action_ledger_status": LedgerState.COMMITTED.value,
            "evidence": {
                "transport_ack": True,
                "delivered_to": target_jid,
                "message_id": msg_id,
                "timestamp": time.time(),
            },
        }


# =====================================================================
# Group scope: group chats are only read / summarised / answered when the owner names them
# =====================================================================

_GROUP_WORD = re.compile(r"\b(?:groups?|grps?)\b", re.I)
_GROUP_FILLER = set("""summarize summarise summary read check show list reply respond send tell text message say said
did does do they he she them me i you what what's whats is are was any new unread latest recent last messages message msgs msg
chats chat whatsapp all every each my the our a an in from of on to for at with that this those these there here please
jarvis hey ok can could would will pending and""".split())


def group_scope_from_text(text: str) -> dict[str, Any]:
    """Resolve requested chat scope before a read; sending still uses only the named group."""
    t = " ".join((text or "").lower().split())
    both = bool(re.search(r"\b(?:personal|individual|direct)(?:\s+(?:messages?|msgs?|chats?))?\s+(?:and|&)\s+"
                          r"(?:groups?|grps?)\b", t)
                or (re.search(r"\b(?:both|all)\b", t)
                    and re.search(r"\b(?:personal|individual|direct)\b", t) and _GROUP_WORD.search(t)))
    m = re.search(r"^(.*?)\b(?:groups?|grps?)\b", t)
    if not m:
        if re.search(r"\b(?:personal|individual|direct)\s+(?:chats?|messages?|msgs?)\b", t):
            return {"scope": "DIRECT_ONLY"}
        return {}
    if both:
        return {"scope": "DIRECT_AND_GROUP"}
    words = re.findall(r"[\w&'-]+", m.group(1))
    # the group's name is the run of words right before "group", after the verbs / articles / prepositions
    if words and words[-1] in ("that", "this", "same"):
        return {"group": "that", "scope": "GROUP_ONLY"}
    while words and words[0] in _GROUP_FILLER:
        words.pop(0)
    cut = max((i for i, w in enumerate(words) if w in ("in", "from", "of", "on", "to", "for", "at")), default=-1)
    words = [w for w in words[cut + 1:]]
    while words and words[0] in _GROUP_FILLER:
        words.pop(0)
    name = " ".join(words).strip()
    if not name or all(w in _GROUP_FILLER for w in words):
        return {"scope": "GROUP_ONLY"}
    return {"group": name, "scope": "GROUP_ONLY"}


_last_group: dict[str, str] = {}  # the group the owner last named ("reply in that group")


def _resolve_group(inbox: Any, name: str) -> tuple[Optional[str], str]:
    """(chat_id, label) for a named group, or (None, explanation). "that group" = the group named last."""
    if re.fullmatch(r"\s*(?:that|this|the same|same)\s*", name or "") and _last_group:
        return _last_group["chat_id"], _last_group["name"]
    hit = inbox.find_group(name) if hasattr(inbox, "find_group") else None
    if hit:
        _last_group.update(chat_id=hit[0], name=hit[1])
        return hit[0], hit[1]
    known = inbox.group_names() if hasattr(inbox, "group_names") else []
    hint = f" Groups I know: {', '.join(known[:6])}." if known else ""
    return None, f"I couldn't find exactly one group called '{name}'.{hint}"


# =====================================================================
# Read WhatsApp Messages Tool
# =====================================================================

_COMMAND_ECHO = re.compile(r"^\s*(?:approve|reject|confirm|cancel|yes|no)\b.*\btkt_\w+|\btkt_[0-9a-f]{6,}\b", re.I)


class ReadWhatsAppMessagesInput(Contract):
    filter: str = Field(default="unread", description="Filter: 'unread' (as WhatsApp shows it), 'needs_reply', 'urgent', or 'all'")
    limit: int = Field(default=5, ge=1, le=50, description="Max messages to retrieve")
    include_groups: bool = Field(default=False, description="Also read group chats (only when the owner asks about groups)")
    scope: Literal["DIRECT_ONLY", "GROUP_ONLY", "DIRECT_AND_GROUP"] = "DIRECT_ONLY"
    group: str = Field(default="", max_length=80, description="Read only this named group (only when the owner names it)")
    sender: str = Field(default="", max_length=80, description="Only messages from this person (name or number)")
    count_only: bool = Field(default=False, description="Answer 'how many' questions: the exact total, per person")


class ReadWhatsAppMessagesOutput(Contract):
    status: str
    count: int
    filter: str
    messages: list[dict]
    spoken_summary: str


class ReadWhatsAppMessagesTool(Tool):
    definition = ToolDefinition(
        name="read_whatsapp_messages",
        description="Reads incoming WhatsApp messages filtered by unread status, urgency, or reply requirements. Risk level: READ_ONLY.",
        input_model=ReadWhatsAppMessagesInput,
        output_model=ReadWhatsAppMessagesOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=5.0,
        tags=("messaging", "whatsapp", "inbox"),
        execution_method=ExecutionMethod.CLI,
    )

    def __init__(self, inbox: Any = None) -> None:
        self._inbox = inbox

    @property
    def inbox(self):
        if self._inbox is None:
            from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
            self._inbox = WhatsAppInbox.get_default()
        return self._inbox

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = ReadWhatsAppMessagesInput(**arguments)

        filt = arguments.filter.lower().strip()
        lim = 1000 if (arguments.count_only or arguments.sender.strip()) else arguments.limit
        group_id, label = None, ""
        if arguments.group.strip():
            group_id, label = _resolve_group(self.inbox, arguments.group)
            if group_id is None:
                return {"status": "NOT_FOUND", "count": 0, "filter": filt, "messages": [], "spoken_summary": label}
        mode = "GROUP_ONLY" if group_id else ("DIRECT_AND_GROUP" if arguments.include_groups else arguments.scope)
        scope = {"include_groups": mode == "DIRECT_AND_GROUP", "group": group_id,
                 "group_only": mode == "GROUP_ONLY"}

        if filt == "urgent":
            raw_msgs = [m for m in self.inbox.get_messages_needing_reply(limit=lim, **scope) if m.urgency == "URGENT"]
        elif filt == "unread":
            raw_msgs = self.inbox.get_unread(limit=lim, **scope)
        elif filt == "all":
            raw_msgs = self.inbox.get_recent(limit=lim, **scope)
        else:  # "needs_reply"
            raw_msgs = self.inbox.get_messages_needing_reply(limit=lim, **scope)

        # Hide JARVIS plumbing stored before owner messages were tagged (commands, approvals).
        msg_dicts = [m.to_dict() for m in raw_msgs
                     if not m.is_from_me and not _COMMAND_ECHO.search(m.text or "")
                     and (m.sender_display_name or "").strip().casefold() not in ("owner", "me", "jarvis")]
        who_filter = arguments.sender.strip().casefold()
        if who_filter:
            digits = re.sub(r"\D", "", who_filter)
            msg_dicts = [m for m in msg_dicts if who_filter in (m.get("sender") or "").casefold()
                         or (len(digits) >= 6 and digits in re.sub(r"\D", "", m.get("chat_id") or ""))]
        count = len(msg_dicts)

        where = f" in {label}" if group_id else (" in group chats" if mode == "GROUP_ONLY" else
                                                     "" if mode == "DIRECT_AND_GROUP" else " in your personal chats")
        if arguments.count_only and filt == "unread" and not who_filter and hasattr(self.inbox, "unread_chats"):
            # WhatsApp's own badge counts (a chat can have more unread messages than JARVIS received)
            chats = self.inbox.unread_chats(**scope)
            total = sum(c["unread"] for c in chats)
            sync_state = self.inbox.sync_state()
            spoken = self._badge_count_summary(chats, where, arguments) if sync_state == "READY" or total else (
                "WhatsApp history is not fully synced, so I can't verify the unread count.")
            if sync_state != "READY" and total:
                spoken += " WhatsApp history is not fully synced; this count may be incomplete."
            return {"status": "SUCCESS" if sync_state == "READY" else "PARTIAL_SYNC", "count": total,
                    "filter": filt, "messages": msg_dicts[:arguments.limit], "spoken_summary": spoken}
        if arguments.count_only:
            incomplete = filt == "unread" and self.inbox.sync_state() != "READY"
            spoken = self._count_summary(msg_dicts, filt, where, arguments)
            if incomplete:
                spoken = (spoken + " WhatsApp history is not fully synced; this count may be incomplete."
                          if count else "WhatsApp history is not fully synced, so I can't verify the unread count.")
            return {"status": "PARTIAL_SYNC" if incomplete else "SUCCESS", "count": count,
                    "filter": filt, "messages": msg_dicts[:arguments.limit], "spoken_summary": spoken}
        if who_filter and count == 0:
            incomplete = filt == "unread" and self.inbox.sync_state() != "READY"
            spoken = (f"WhatsApp history is not fully synced, so I can't verify unread messages from {arguments.sender.strip()}."
                      if incomplete else f"No {filt.replace('_', ' ')} WhatsApp messages from {arguments.sender.strip()}.")
            return {"status": "PARTIAL_SYNC" if incomplete else "SUCCESS", "count": 0, "filter": filt,
                    "messages": [], "spoken_summary": spoken}
        msg_dicts = msg_dicts[:max(arguments.limit, 5)] if who_filter else msg_dicts
        if count == 0:
            spoken = ("WhatsApp history is not fully synced, so I can't verify whether you have unread messages."
                      if filt == "unread" and self.inbox.sync_state() != "READY" else
                      f"You have no {filt.replace('_', ' ')} WhatsApp messages{where}.")
        else:
            items_spoken = []
            for m in msg_dicts[:3]:
                who = m["sender"] + (f" in {m.get('chat_name') or 'a group'}" if m.get("is_group") and not group_id else "")
                from jarvis.integrations.whatsapp.inbox import describe_message
                urg_prefix = f"Urgent from {who}" if m["urgency"] == "URGENT" else f"From {who}"
                items_spoken.append(f"{urg_prefix}: {describe_message(m['text'] or m['summary'])}")
            spoken = f"Found {count} message{'s' if count > 1 else ''}{where}: " + ". ".join(items_spoken)

        incomplete = filt == "unread" and self.inbox.sync_state() != "READY"
        if incomplete and count:
            spoken += " WhatsApp history is not fully synced; these messages may be incomplete."
        return {
            "status": "PARTIAL_SYNC" if incomplete else "SUCCESS",
            "count": count,
            "filter": filt,
            "messages": msg_dicts,
            "spoken_summary": spoken,
        }

    def _badge_count_summary(self, chats: list[dict], where: str, arguments: Any) -> str:
        """'You have 4 unread WhatsApp messages in your personal chats from 3 people: Sanjana Ssk 2, ...' (exact)."""
        n = sum(c["unread"] for c in chats)
        if n == 0:
            text = f"You have no unread WhatsApp messages{where}."
        else:
            people = ", ".join(f"{c['name']} {c['unread']}" for c in chats[:5])
            more = f" and {len(chats) - 5} more chats" if len(chats) > 5 else ""
            text = (f"You have {n} unread WhatsApp message{'s' if n != 1 else ''}{where}"
                    + (f" from {len(chats)} chats: {people}{more}." if len(chats) > 1 else f", all from {chats[0]['name']}."))
            if arguments.scope == "DIRECT_ONLY" and not arguments.include_groups and not arguments.group.strip():
                text = text.replace(" chats:", " people:", 1).replace(" more chats", " more people", 1)
        if arguments.scope == "DIRECT_ONLY" and not arguments.include_groups and not arguments.group.strip():
            groups = [c for c in self.inbox.unread_chats(include_groups=True) if c["is_group"]]
            if groups:
                g = sum(c["unread"] for c in groups)
                text += f" Group chats have {g} more in {len(groups)} group{'s' if len(groups) != 1 else ''}."
        return text

    def _count_summary(self, msgs: list[dict], filt: str, where: str, arguments: Any) -> str:
        """'You have 12 unread WhatsApp messages in your personal chats: Sushmitaa 5, Scooby 4, Arun 3.' (exact)"""
        kind = {"unread": "unread", "needs_reply": "waiting", "urgent": "urgent", "all": "recent"}.get(filt, filt)
        n = len(msgs)
        if n == 0:
            text = f"You have no {kind} WhatsApp messages{where}."
        else:
            per = Counter(m.get("sender") or "someone" for m in msgs)
            people = ", ".join(f"{name} {c}" for name, c in per.most_common(5))
            more = f" and {len(per) - 5} more people" if len(per) > 5 else ""
            text = (f"You have {n} {kind} WhatsApp message{'s' if n != 1 else ''}{where}"
                    + (f" from {len(per)} people: {people}{more}." if len(per) > 1 else f", all from {people.rsplit(' ', 1)[0]}."))
        if not arguments.include_groups and not arguments.group.strip():
            try:
                groups = [m for m in (self.inbox.get_unread(limit=1000, include_groups=True) if filt == "unread" else [])
                          if getattr(m, "is_group", False) and not m.is_from_me]
                if groups:
                    chats = len({m.chat_id for m in groups})
                    text += f" Group chats have {len(groups)} more in {chats} group{'s' if chats != 1 else ''}."
            except Exception:
                pass
        return text


# =====================================================================
# Summarize WhatsApp Messages Tool
# =====================================================================

class SummarizeWhatsAppMessagesInput(Contract):
    include_all: bool = Field(default=False, description="Whether to include already read messages")
    include_groups: bool = Field(default=False, description="Also summarise group chats (only when the owner asks about groups)")
    scope: Literal["DIRECT_ONLY", "GROUP_ONLY", "DIRECT_AND_GROUP"] = "DIRECT_ONLY"
    group: str = Field(default="", max_length=80, description="Summarise only this named group (only when the owner names it)")


class SummarizeWhatsAppMessagesOutput(Contract):
    status: str
    total_pending: int
    urgent_count: int
    normal_count: int
    spoken_summary: str
    urgent_messages: list[dict]
    normal_messages: list[dict]
    unread_count: int = 0
    sync_state: str = "PARTIAL_SYNC"
    total_direct_chats: int = 0
    unread_direct_chats: int = 0
    unread_messages: int = 0
    groups_unread_count: int = 0
    generated_at: str = ""


class SummarizeWhatsAppMessagesTool(Tool):
    definition = ToolDefinition(
        name="summarize_whatsapp_messages",
        description="Summarizes all pending WhatsApp messages requiring attention, grouping and highlighting urgent messages. Risk level: READ_ONLY.",
        input_model=SummarizeWhatsAppMessagesInput,
        output_model=SummarizeWhatsAppMessagesOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=15.0,
        tags=("messaging", "whatsapp", "summary"),
        execution_method=ExecutionMethod.CLI,
    )

    def __init__(self, inbox: Any = None) -> None:
        self._inbox = inbox

    @property
    def inbox(self):
        if self._inbox is None:
            from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
            self._inbox = WhatsAppInbox.get_default()
        return self._inbox

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = SummarizeWhatsAppMessagesInput(**arguments)
        group_id = None
        if arguments.group.strip():
            group_id, label = _resolve_group(self.inbox, arguments.group)
            if group_id is None:
                return {"status": "NOT_FOUND", "total_pending": 0, "urgent_count": 0, "normal_count": 0,
                        "spoken_summary": label, "urgent_messages": [], "normal_messages": []}
        # Deterministic and attributed per person: instant, and a model can never mix up who said what.
        if hasattr(self.inbox, "wait_for_ready"):
            self.inbox.wait_for_ready()
        mode = "GROUP_ONLY" if group_id else ("DIRECT_AND_GROUP" if arguments.include_groups else arguments.scope)
        data = self.inbox.summarize_inbox(include_groups=mode == "DIRECT_AND_GROUP", group=group_id,
                                          group_only=mode == "GROUP_ONLY")
        spoken = data["spoken_summary"]
        return {
            "status": "SUCCESS" if data.get("sync_state") == "READY" else "PARTIAL_SYNC",
            "total_pending": data["total_pending"],
            "urgent_count": data["urgent_count"],
            "normal_count": data["normal_count"],
            "spoken_summary": spoken,
            "urgent_messages": data["urgent_messages"],
            "normal_messages": data["normal_messages"],
            "unread_count": data.get("unread_count", 0),
            "sync_state": data.get("sync_state", "PARTIAL_SYNC"),
            "total_direct_chats": data.get("total_direct_chats", 0),
            "unread_direct_chats": data.get("unread_direct_chats", 0),
            "unread_messages": data.get("unread_messages", 0),
            "groups_unread_count": data.get("groups_unread", 0),
            "generated_at": data.get("generated_at", ""),
        }



# =====================================================================
# Draft WhatsApp Reply Tool (AI)
# =====================================================================

class DraftWhatsAppReplyInput(Contract):
    recipient: str = Field(default="", max_length=256, description="Whose message to reply to (name/number); empty = latest message needing a reply")
    instruction: str = Field(default="", max_length=1024, description="Optional guidance for what the reply should say")


class DraftWhatsAppReplyOutput(Contract):
    status: str
    recipient: str
    recipient_jid: str
    original_message: str
    draft: str
    message: str
    next_action: dict = Field(default_factory=dict)


class DraftWhatsAppReplyTool(Tool):
    """Writes a reply to the latest WhatsApp message with the local model; sending is a separate, confirmed step."""

    definition = ToolDefinition(
        name="reply_whatsapp_message",
        description="Drafts a reply to the latest WhatsApp message (from a person, or the latest needing a reply) using the conversation and optional guidance, then asks to send it.",
        input_model=DraftWhatsAppReplyInput,
        output_model=DraftWhatsAppReplyOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=60.0,
        tags=("messaging", "whatsapp", "reply", "ai"),
        execution_method=ExecutionMethod.API,
    )

    def __init__(self, ai: Any = None) -> None:
        self.ai = ai

    async def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = DraftWhatsAppReplyInput(**arguments)
        from jarvis.integrations.whatsapp.ai import get_whatsapp_ai
        ai = self.ai or get_whatsapp_ai()
        named_group = group_scope_from_text(arguments.recipient).get("group") if _GROUP_WORD.search(arguments.recipient) else None
        if named_group:  # "reply in the CSE group saying ..." - only because the owner named the group
            group_id, label = _resolve_group(ai.inbox, named_group)
            if group_id is None:
                return {"status": "NOT_FOUND", "recipient": arguments.recipient, "recipient_jid": "", "original_message": "",
                        "draft": "", "message": label, "next_action": {}}
            draft = await ai.draft_reply(group_id, arguments.instruction, in_group=True)
            if draft is None:
                return {"status": "NOT_FOUND", "recipient": label, "recipient_jid": group_id, "original_message": "",
                        "draft": "", "message": f"There's nothing in the {label} group to reply to yet.", "next_action": {}}
            return {"status": "DRAFTED", "recipient": f"the {label} group", "recipient_jid": group_id,
                    "original_message": draft.original[:500], "draft": draft.text,
                    "message": f"Reply in the {label} group: {draft.text}",
                    "next_action": {"tool": "send_whatsapp_message",
                                    "arguments": {"recipient": group_id, "message": draft.text, "allow_group": True},
                                    "display_recipient": f"the {label} group"}}
        draft = await ai.draft_reply(arguments.recipient, arguments.instruction)
        if draft is None:
            who = f" from {arguments.recipient}" if arguments.recipient else ""
            return {"status": "NOT_FOUND", "recipient": arguments.recipient, "recipient_jid": "", "original_message": "",
                    "draft": "", "message": f"I couldn't find a WhatsApp message{who} to reply to.", "next_action": {}}
        return {
            "status": "DRAFTED",
            "recipient": draft.recipient,
            "recipient_jid": draft.recipient_jid,
            "original_message": draft.original[:500],
            "draft": draft.text,
            "message": f"Reply to {draft.recipient}: {draft.text}",
            "next_action": {"tool": "send_whatsapp_message", "arguments": {"recipient": draft.recipient_jid, "message": draft.text},
                            "display_recipient": draft.recipient},
        }


# =====================================================================
# Reply to everyone who messaged me (AI, direct chats only)
# =====================================================================

class ReplyWhatsAppAllInput(Contract):
    message: str = Field(default="", max_length=2048, description="What to tell everyone who messaged (e.g. \"I'm in a meeting, free in an hour\"); empty = reuse the last instruction or draft a reply per chat")
    request: str = Field(default="", max_length=2048, description="The owner's full request (used for constraints like 'don't reply in groups')")
    hours: float = Field(default=12.0, gt=0, le=168, description="Only people who messaged within this many hours")
    include_groups: bool = Field(default=False, description="Also reply in group chats (off by default)")
    max_people: int = Field(default=10, ge=1, le=25, description="Maximum number of chats to reply to")
    exclude: list[str] = Field(default_factory=list, description="People not to reply to ('everyone except Arun' -> ['Arun'])")


class ReplyWhatsAppAllOutput(Contract):
    status: str
    count: int = 0
    recipients: list[str] = Field(default_factory=list)
    drafts: list[dict] = Field(default_factory=list)
    skipped_groups: int = 0
    message: str
    confirm_prompt: str = ""
    next_action: dict = Field(default_factory=dict)


class ReplyWhatsAppAllTool(Tool):
    """Drafts one personal reply for every person who messaged recently (one-to-one chats only); sending is confirmed."""

    definition = ToolDefinition(
        name="reply_whatsapp_all",
        description="Replies to everyone who messaged you recently on WhatsApp (e.g. 'tell everyone who texted me I'm busy'). "
                    "One-to-one chats only - groups are skipped unless asked. Drafts a personal message per person, then asks before sending.",
        input_model=ReplyWhatsAppAllInput,
        output_model=ReplyWhatsAppAllOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=120.0,
        tags=("messaging", "whatsapp", "reply", "bulk", "ai"),
        execution_method=ExecutionMethod.API,
    )

    def __init__(self, ai: Any = None, inbox: Any = None) -> None:
        self.ai = ai
        self.inbox = inbox

    async def run(self, arguments: Any) -> dict[str, Any]:
        import asyncio
        from jarvis.integrations.whatsapp.ai import get_whatsapp_ai, split_bulk_instruction

        if isinstance(arguments, dict):
            arguments = ReplyWhatsAppAllInput(**arguments)
        ai = self.ai or get_whatsapp_ai()
        inbox = self.inbox or ai.inbox

        message, wants_groups = split_bulk_instruction(arguments.message)
        _, request_groups = split_bulk_instruction(arguments.request)
        include_groups = arguments.include_groups or wants_groups or request_groups
        reused = False
        if not message:
            message = ai.recent_instruction()
            reused = bool(message)
        if message:
            ai.remember_instruction(message)

        people = await asyncio.to_thread(inbox.recent_direct_senders, arguments.hours * 3600, arguments.max_people, True, include_groups)
        if arguments.exclude:   # "everyone except Arun": the excluded people get nothing
            skip = [x.lower().strip() for x in arguments.exclude if x.strip()]
            people = [m for m in people if not any(x in (m.sender_display_name or m.sender_id or "").lower() for x in skip)]
        all_recent = await asyncio.to_thread(inbox.recent_direct_senders, arguments.hours * 3600, 50, True, True)
        skipped_groups = 0 if include_groups else sum(1 for m in all_recent if not inbox.is_direct_chat(m.chat_id))
        if not people:
            extra = f" ({skipped_groups} group chat{'s' if skipped_groups != 1 else ''} skipped)" if skipped_groups else ""
            return {"status": "NOT_FOUND", "count": 0, "recipients": [], "drafts": [], "skipped_groups": skipped_groups,
                    "message": f"Nobody is waiting for a reply in your personal chats from the last {arguments.hours:g} hours{extra}."}

        async def draft_for(msg):
            name = msg.sender_display_name or msg.sender_id.split("@")[0]
            if message:
                text = await ai.compose_for_person(name, msg.chat_id, message, msg.text)
            else:
                reply = await ai.draft_reply(msg.sender_id if "@" in msg.sender_id else msg.chat_id)
                text = reply.text if reply else "Got your message, I'll get back to you soon."
            target = msg.chat_id if "@" in msg.chat_id else msg.sender_id
            return {"recipient": target, "name": name, "message": text, "their_message": (msg.text or "")[:200]}

        drafts = await asyncio.gather(*(draft_for(m) for m in people))
        names = [d["name"] for d in drafts]
        who = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
        lines = "; ".join(f"{d['name']}: \"{d['message']}\"" for d in drafts[:6])
        more = f" (+{len(drafts) - 6} more)" if len(drafts) > 6 else ""
        groups_note = f" I skipped {skipped_groups} group chat{'s' if skipped_groups != 1 else ''}." if skipped_groups else ""
        basis = f" using your earlier message \"{message}\"" if reused else ""
        prompt = (f"I'll reply to {len(drafts)} {'person' if len(drafts) == 1 else 'people'} in personal chats ({who}){basis}. "
                  f"{lines}{more}.{groups_note} Shall I send {'it' if len(drafts) == 1 else 'them'}?")
        return {
            "status": "DRAFTED",
            "count": len(drafts),
            "recipients": names,
            "drafts": drafts,
            "skipped_groups": skipped_groups,
            "message": prompt,
            "confirm_prompt": prompt,
            "next_action": {"tool": "send_whatsapp_bulk",
                            "arguments": {"messages": [{"recipient": d["recipient"], "name": d["name"], "message": d["message"]} for d in drafts]},
                            "display_recipient": who},
        }


class BulkMessageItem(Contract):
    recipient: str = Field(min_length=1, max_length=256, description="WhatsApp JID or phone number")
    name: str = Field(default="", max_length=256)
    message: str = Field(min_length=1, max_length=4096)


class SendWhatsAppBulkInput(Contract):
    messages: list[BulkMessageItem] = Field(min_length=1, max_length=25, description="One message per recipient")
    confirmation_ticket: Optional[str] = Field(default=None, description="Confirmation ticket ID if action required approval")


class SendWhatsAppBulkOutput(Contract):
    status: str
    sent: list[str] = Field(default_factory=list)
    failed: list[dict] = Field(default_factory=list)
    message: str


class SendWhatsAppBulkTool(Tool):
    """Sends several (already approved) WhatsApp messages, one per person."""

    definition = ToolDefinition(
        name="send_whatsapp_bulk",
        description="Sends a prepared WhatsApp message to each of several people (after confirmation). Risk level: EXTERNAL_EFFECT.",
        input_model=SendWhatsAppBulkInput,
        output_model=SendWhatsAppBulkOutput,
        read_only=False,
        risk=RiskLevel.EXTERNAL_EFFECT,
        timeout_s=180.0,
        tags=("messaging", "whatsapp", "communication", "bulk"),
        execution_method=ExecutionMethod.CLI,
        idempotency=IdempotencyClass.NON_IDEMPOTENT,
    )

    def __init__(self, transport: Any = None, confirmation_manager: Optional[ConfirmationManager] = None) -> None:
        self.transport = transport
        self.confirmation_manager = confirmation_manager

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = SendWhatsAppBulkInput(**arguments)
        sender = SendWhatsAppMessageTool(transport=self.transport)
        sent, failed = [], []
        for item in arguments.messages:
            name = item.name or item.recipient.split("@")[0]
            try:
                res = sender.run(SendWhatsAppMessageInput(recipient=item.recipient, message=item.message))
            except Exception as exc:  # one failure must not stop the others
                res = {"status": "FAILED", "message": str(exc)}
            if res.get("status") == "SENT":
                sent.append(name)
            else:
                failed.append({"name": name, "error": res.get("message", "failed")})
        if sent and not failed:
            status, text = "SENT", f"Sent to {len(sent)} {'person' if len(sent) == 1 else 'people'}: {', '.join(sent)}."
        elif sent:
            status = "PARTIAL"
            text = f"Sent to {', '.join(sent)}; couldn't reach {', '.join(f['name'] for f in failed)}."
        else:
            status, text = "FAILED", f"Couldn't send any of the messages ({failed[0]['error'] if failed else 'unknown error'})."
        return {"status": status, "sent": sent, "failed": failed, "message": text}


# =====================================================================
# Who is <contact>? (answered from the owner's contacts and chats)
# =====================================================================

class ContactInfoInput(Contract):
    name: str = Field(min_length=1, max_length=80, description="Contact name to describe")


class ContactInfoOutput(Contract):
    status: str
    message: str
    name: str = ""
    jid: str = ""


class ContactInfoTool(Tool):
    definition = ToolDefinition(
        name="contact_info",
        description="Tells who one of the owner's contacts is: number, last WhatsApp message, how often they chat and "
                    "the owner's usual style with them. Read only.",
        input_model=ContactInfoInput,
        output_model=ContactInfoOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=10.0,
        tags=("contacts", "whatsapp", "people"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = ContactInfoInput(**arguments)
        from jarvis.integrations.whatsapp.people import describe_person
        return describe_person(arguments.name)
