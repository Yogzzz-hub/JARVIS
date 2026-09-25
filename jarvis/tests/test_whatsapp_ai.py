"""WhatsApp AI composition safety, recipient normalization, inbox summaries and planner capability checks."""
from __future__ import annotations

import pytest

from jarvis.integrations.whatsapp.ai import WhatsAppAI, deterministic_compose
from jarvis.tests.fake_ollama import FakeOllama
from jarvis.tools.system.whatsapp_tools import phone_to_jid


@pytest.mark.parametrize("recipient,body,style,expected", [
    ("rahul", "if he is free tonight", "ask", "Are you free tonight?"),
    ("mom", "when she is coming home", "ask", "When are you coming home?"),
    ("rahul", "to call me back", "ask", "Could you call me back?"),
    ("rahul", "whether he likes pizza", "ask", "Do you like pizza?"),
    ("dad", "to take his medicine", "remind", "Just a reminder to take your medicine."),
    ("sis", "that her parcel arrived", "inform", "Your parcel arrived."),
    ("priya", "happy birthday", "wish", "Happy birthday!"),
    ("mom", "that I'll be late for dinner", "direct", "I'll be late for dinner"),
    ("boss", "saying the report is ready", "direct", "The report is ready"),
])
def test_grammar_rewrite(recipient, body, style, expected):
    assert deterministic_compose(recipient, body, style) == expected


@pytest.mark.asyncio
async def test_model_rewrite_is_rejected_when_it_drops_facts_or_sounds_like_an_ai():
    fake = FakeOllama(responder=lambda p: {"message": "The meeting was moved."})
    ai = WhatsAppAI(client=fake.client(chat_model="llama3.2"))
    out = await ai.compose_outgoing("yoga", "that the meeting moved to 5:30", "inform")
    assert out == "The meeting moved to 5:30.", "a rewrite that loses '5:30' must fall back to the grammar draft"

    fake.responder = lambda p: {"message": "As an AI language model, here's the message: hi"}
    assert await ai.compose_outgoing("rahul", "if he is free", "ask") == "Are you free?"

    fake.responder = lambda p: {"message": "Hey Rahul, are you free tonight?"}
    assert await ai.compose_outgoing("rahul", "if he is free tonight", "ask") == "Hey Rahul, are you free tonight?"


@pytest.mark.asyncio
async def test_direct_messages_skip_the_model():
    fake = FakeOllama(responder=lambda p: {"message": "SHOULD NOT BE USED"})
    ai = WhatsAppAI(client=fake.client())
    assert await ai.compose_outgoing("mom", "I reached home", "direct") == "I reached home"
    assert not fake.chat_payloads()


def test_phone_numbers_become_valid_jids():
    assert phone_to_jid("98765 43210", country_code="91") == "919876543210@s.whatsapp.net"
    assert phone_to_jid("+1 (415) 555-0100") == "14155550100@s.whatsapp.net"
    assert phone_to_jid("09876543210", country_code="91") == "919876543210@s.whatsapp.net"
    assert phone_to_jid("x@g.us") == "x@g.us"
    assert phone_to_jid("Mom") is None


def test_inbox_summary_uses_model_and_falls_back(tmp_path):
    msgs = [{"sender": "Rahul", "text": "Can you send the slides?", "urgency": "URGENT"},
            {"sender": "Mom", "text": "Call me when free", "urgency": "NORMAL"}]
    fake = FakeOllama(responder=lambda p: "Rahul urgently needs the slides, and Mom wants a call.")
    ai = WhatsAppAI(client=fake.client(chat_model="llama3.2"))
    assert ai.summarize_sync(msgs, fallback="2 messages") == "Rahul urgently needs the slides, and Mom wants a call."
    assert "untrusted data" in fake.chat_payloads()[0]["messages"][0]["content"]
    offline = WhatsAppAI(client=FakeOllama(reachable=False).client())
    assert offline.summarize_sync(msgs, fallback="2 messages") == "2 messages"


def test_planner_capability_gap_uses_the_whole_registry():
    from jarvis.core.planner.adaptive_planner import AdaptivePlanner
    from jarvis.tests.ai_harness import HARDWARE
    from jarvis.tools.registry import ToolRegistry
    from jarvis.tools.system.app_resolver import AppResolver
    from jarvis.tools.system.native import create_tools

    registry = ToolRegistry()
    registry.discover(create_tools(AppResolver({}), HARDWARE))
    registry.finalize()
    planner = AdaptivePlanner(registry=registry, client=FakeOllama(reachable=False).client())
    # Previously any multi-step WhatsApp request was rejected as "WhatsApp integration is not installed".
    assert planner._detect_missing_capability("find the report and send it to boss on whatsapp", set()) is None
    gap = planner._detect_missing_capability("send an email to the team", set())
    assert gap is not None and gap.capability == "email_messaging"
