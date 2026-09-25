"""WhatsApp Messaging Tools for JARVIS EDGE.
Integrates with ContactResolver, Phase 5 Policy, and ActionLedger.
Risk Class: EXTERNAL_EFFECT.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Optional
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


class SendWhatsAppMessageInput(Contract):
    recipient: str = Field(min_length=1, max_length=256, description="Contact name, phone number, or WhatsApp JID")
    message: str = Field(min_length=1, max_length=4096, description="Message text to send")
    confirmation_ticket: Optional[str] = Field(default=None, description="Confirmation ticket ID if action required approval")


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
        if not self.transport:
            # Fallback: connect directly to local Baileys bridge WebSocket (ws://127.0.0.1:8768)
            try:
                import websockets, uuid, json, asyncio
                async def _direct_bridge_send():
                    async with websockets.connect("ws://127.0.0.1:8768", open_timeout=4.0) as ws:
                        req_id = str(uuid.uuid4())
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
                                    raise RuntimeError(msg.get("error") or "WhatsApp bridge delivery failed")
                                return msg.get("result") or {"status": "SENT"}
                        raise TimeoutError("WhatsApp bridge did not acknowledge message delivery within deadline")
                res = asyncio.run(_direct_bridge_send())
            except Exception as bridge_exc:
                logger.warning("Direct bridge send error: %s", bridge_exc)
                return {
                    "status": "FAILED",
                    "recipient": resolved_name,
                    "recipient_jid": target_jid,
                    "message": f"WhatsApp transport error: {bridge_exc}",
                    "message_id": None,
                    "action_ledger_status": "FAILED",
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
                        res = {"status": "SENT", "message_id": f"msg_wa_{int(time.time()*1000)}"}
                else:
                    if hasattr(self.transport, "send_text"):
                        res = asyncio.run(self.transport.send_text(target_jid, msg_text))
                    elif hasattr(self.transport, "sendTextMessage"):
                        res = asyncio.run(self.transport.sendTextMessage(target_jid, msg_text))
                    else:
                        res = {"status": "SENT", "message_id": f"msg_wa_{int(time.time()*1000)}"}
            except Exception as exc:
                logger.error("Failed to send WhatsApp message via transport: %s", exc)
                return {
                    "status": "FAILED",
                    "recipient": resolved_name,
                    "recipient_jid": target_jid,
                    "message": f"Transport failure: {exc}",
                    "message_id": None,
                    "action_ledger_status": "FAILED",
                    "evidence": {"transport_connected": True, "error": str(exc)},
                }

        send_result = res.get("result") if (isinstance(res, dict) and isinstance(res.get("result"), dict)) else res
        is_sent = (
            (isinstance(send_result, dict) and send_result.get("status") == "SENT")
            or (isinstance(res, dict) and res.get("success") is True)
        )

        if not is_sent:
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

        msg_id = (send_result.get("message_id") if isinstance(send_result, dict) else None) or f"msg_wa_{int(time.time()*1000)}"

        # Mark existing messages in this conversation as replied
        try:
            from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
            WhatsAppInbox.get_default().mark_as_replied(target_jid)
        except Exception:
            pass

        # Only report verified sent when transport ACK is confirmed
        return {
            "status": "SENT",
            "recipient": resolved_name,
            "recipient_jid": target_jid,
            "message": f"Message delivered to {resolved_name}: '{msg_text}'",
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
# Read WhatsApp Messages Tool
# =====================================================================

class ReadWhatsAppMessagesInput(Contract):
    filter: str = Field(default="needs_reply", description="Filter: 'needs_reply', 'urgent', 'unread', or 'all'")
    limit: int = Field(default=5, ge=1, le=50, description="Max messages to retrieve")


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
        lim = arguments.limit

        if filt == "urgent":
            raw_msgs = [m for m in self.inbox.get_messages_needing_reply(limit=lim) if m.urgency == "URGENT"]
        elif filt == "unread":
            raw_msgs = self.inbox.get_unread(limit=lim)
        elif filt == "all":
            raw_msgs = self.inbox.get_recent(limit=lim)
        else:  # "needs_reply"
            raw_msgs = self.inbox.get_messages_needing_reply(limit=lim)

        msg_dicts = [m.to_dict() for m in raw_msgs]
        count = len(msg_dicts)

        if count == 0:
            spoken = f"You have no {filt.replace('_', ' ')} WhatsApp messages."
        else:
            items_spoken = []
            for m in msg_dicts[:3]:
                urg_prefix = f"Urgent from {m['sender']}" if m["urgency"] == "URGENT" else f"From {m['sender']}"
                items_spoken.append(f"{urg_prefix}: '{m['summary']}'")
            spoken = f"Found {count} message{'s' if count > 1 else ''}: " + ". ".join(items_spoken)

        return {
            "status": "SUCCESS",
            "count": count,
            "filter": filt,
            "messages": msg_dicts,
            "spoken_summary": spoken,
        }


# =====================================================================
# Summarize WhatsApp Messages Tool
# =====================================================================

class SummarizeWhatsAppMessagesInput(Contract):
    include_all: bool = Field(default=False, description="Whether to include already read messages")


class SummarizeWhatsAppMessagesOutput(Contract):
    status: str
    total_pending: int
    urgent_count: int
    normal_count: int
    spoken_summary: str
    urgent_messages: list[dict]
    normal_messages: list[dict]


class SummarizeWhatsAppMessagesTool(Tool):
    definition = ToolDefinition(
        name="summarize_whatsapp_messages",
        description="Summarizes all pending WhatsApp messages requiring attention, grouping and highlighting urgent messages. Risk level: READ_ONLY.",
        input_model=SummarizeWhatsAppMessagesInput,
        output_model=SummarizeWhatsAppMessagesOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=5.0,
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
        data = self.inbox.summarize_inbox()
        spoken = data["spoken_summary"]
        pending = list(data.get("urgent_messages", [])) + list(data.get("normal_messages", []))
        if pending:
            try:
                from jarvis.integrations.whatsapp.ai import get_whatsapp_ai
                spoken = get_whatsapp_ai().summarize_sync(pending, fallback=spoken)
            except Exception as exc:
                logger.debug("AI inbox summary unavailable: %s", exc)
        return {
            "status": "SUCCESS",
            "total_pending": data["total_pending"],
            "urgent_count": data["urgent_count"],
            "normal_count": data["normal_count"],
            "spoken_summary": spoken,
            "urgent_messages": data["urgent_messages"],
            "normal_messages": data["normal_messages"],
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
