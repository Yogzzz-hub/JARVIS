"""Test / benchmark harness for the WhatsApp personal reply agent (fake transport, temp databases, fixed clock)."""
from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any, Optional

from jarvis.integrations.whatsapp.fake_transport import FakeWhatsAppTransport
from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
from jarvis.integrations.whatsapp.models import NormalizedWhatsAppMessage
from jarvis.integrations.whatsapp.personal_reply.agent import PersonalReplyAgent
from jarvis.integrations.whatsapp.personal_reply.auto_reply_policy import AutoReplyPolicy
from jarvis.integrations.whatsapp.personal_reply.crypto import DataBox, test_key
from jarvis.integrations.whatsapp.personal_reply.reply_generator import ReplyGenerator
from jarvis.integrations.whatsapp.personal_reply.store import PersonalReplyStore
from jarvis.security.ledger.ledger import ActionLedger
from jarvis.security.policy.evaluator import PolicyEvaluator
from tests.whatsapp_personal.synthetic import CONTACTS, StandInLLM, export_text

_ids = itertools.count(1)


class Clock:
    def __init__(self, t: float = 1_790_000_000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


class FlakyTransport(FakeWhatsAppTransport):
    """Fake transport whose next sends can time out (outcome unknown) or be refused (disconnected)."""

    def __init__(self) -> None:
        super().__init__()
        self.mode = "ok"

    async def send_text(self, to: str, text: str, quoted: Optional[dict] = None) -> dict[str, Any]:
        if self.mode == "timeout":
            self.sent_messages.append({"to": to, "text": text, "status": "MAYBE"})
            raise TimeoutError("bridge did not answer")
        if self.mode == "disconnected":
            raise ConnectionError("WhatsApp transport is disconnected")
        return await super().send_text(to, text, quoted)


def make_agent(tmp: Path, llm: Any = None, clock: Optional[Clock] = None, transport: Any = None, auto_untrained: bool = False,
               encrypted: bool = True, db_name: str = "jarvis.db", inbox: Any = None) -> PersonalReplyAgent:
    store = PersonalReplyStore(tmp / db_name, box=DataBox(key=test_key(), use_keyring=False) if encrypted else DataBox(use_keyring=False))
    clock = clock or Clock()
    return PersonalReplyAgent(
        store=store, transport=transport if transport is not None else FlakyTransport(),
        inbox=inbox or WhatsAppInbox(tmp / "inbox.db"), generator=ReplyGenerator(client=llm or StandInLLM()),
        policy=AutoReplyPolicy(store, auto_reply_untrained=auto_untrained), ledger=ActionLedger(tmp / db_name),
        policy_evaluator=PolicyEvaluator(), coalesce_s=0, owner_names=["Me"], clock=clock, use_jde=False)


def train(agent: PersonalReplyAgent, *keys: str, n: int = 120) -> None:
    for k in keys or tuple(CONTACTS):
        c = CONTACTS[k]
        agent.import_chat(c["jid"], c["name"], export_text=export_text(k, n=n))


def msg(chat_id: str, text: str, name: str = "", message_id: str = "", from_me: bool = False, state: str = "READY",
        group_sender: str = "") -> NormalizedWhatsAppMessage:
    return NormalizedWhatsAppMessage(
        message_id=message_id or f"m{next(_ids)}", chat_id=chat_id, sender_id=group_sender or chat_id,
        sender_display_name=name or chat_id.split("@")[0], timestamp="1790000000", type="text", text=text,
        is_from_me=from_me, state=state, is_group=chat_id.endswith("@g.us"))


async def deliver(agent: PersonalReplyAgent, message: NormalizedWhatsAppMessage) -> dict[str, Any]:
    """What the gateway does: record real messages in the inbox (thread context), then hand them to the agent."""
    from jarvis.integrations.whatsapp.personal_reply.dedupe import is_placeholder
    if not is_placeholder(message):
        try:
            agent.inbox.add_message(message, is_from_me=message.is_from_me)
        except Exception:
            pass
    return await agent.handle_incoming(message)


def sends_to(agent: PersonalReplyAgent, chat_id: Optional[str] = None) -> list[dict[str, Any]]:
    return [m for m in agent.transport.sent_messages if chat_id is None or m["to"] == chat_id]
