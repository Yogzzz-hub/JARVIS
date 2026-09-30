"""Spoken auto-reply requests with an away message, "i need python 3.12", and clear talkback."""
from __future__ import annotations

import asyncio
import time

import pytest

from jarvis.integrations.whatsapp.personal_reply.agent import away_text
from jarvis.integrations.whatsapp.personal_reply.commands import parse_command


def test_rambled_meeting_request_turns_on_auto_reply_with_the_message():
    cmd = parse_command("i am gng to attend metting so do auto reply who is sending messging me that i am busy at mettting")
    assert cmd["action"] == "enable" and cmd["everyone"] and cmd["note"] == "i am busy at mettting"
    assert away_text(cmd["note"]) == "I'm busy at meeting. I'll get back to you soon."


@pytest.mark.parametrize("text,everyone,who,note,window", [
    ("do autoreply in whatsapp for 10 min", True, "", "", True),
    ("auto reply to everyone for 1 hour saying I am in a meeting", True, "", "i am in a meeting", True),
    ("auto reply whoever messages me for 20 mins saying in class", True, "", "in class", True),
    ("set auto reply for 2 hours tell them i am driving", True, "", "i am driving", True),
    ("auto reply to kumar for 30 minutes", False, "kumar", "", True),
    ("reply to Yoga automatically for the next hour", False, "yoga", "", True),
])
def test_auto_reply_phrasings(text, everyone, who, note, window):
    cmd = parse_command(text)
    assert (cmd["everyone"], cmd["who"], cmd["note"], cmd["has_window"]) == (everyone, who, note, window)


def test_unchanged_auto_reply_rules():
    assert parse_command("respond to anand with dont wait for me") is None  # one reply, not a window
    assert parse_command("auto reply in groups for 1 hour") == {"action": "refuse_groups"}
    assert parse_command("stop whatsapp auto reply") == {"action": "disable_all"}


def test_away_message_is_sent_once_per_person_without_the_model(tmp_path):
    from jarvis.integrations.whatsapp.personal_reply.agent import PersonalReplyAgent
    from jarvis.integrations.whatsapp.personal_reply.store import PersonalReplyStore

    sent = []

    class Transport:
        async def send_text(self, to, text, quoted=None):
            sent.append((to, text))
            return {"success": True, "result": {"message_id": f"m{len(sent)}", "status": "SENT"}}

    class NoModel:
        async def generate(self, *a, **k):
            raise AssertionError("the model must not be used for a dictated away message")

    agent = PersonalReplyAgent(store=PersonalReplyStore(tmp_path / "pr.db"), transport=Transport(), generator=NoModel(),
                               coalesce_s=0.0, use_jde=False)
    res = agent.enable([], time.time() + 3600, everyone=True, note="i am in a meeting")
    assert "I'm in a meeting. I'll get back to you soon." in res["message"]
    from jarvis.integrations.whatsapp.personal_reply.models import IncomingBatch
    jid = "919000000001@s.whatsapp.net"

    def batch(mid):
        return IncomingBatch(contact_id=jid, chat_id=jid, display_name="Kumar", message_ids=[mid], texts=["hi, free now?"],
                             received_at=time.time())
    first = asyncio.run(agent.process_batch(batch("i1")))
    second = asyncio.run(agent.process_batch(batch("i2")))
    assert [t for _, t in sent] == ["I'm in a meeting. I'll get back to you soon."]
    assert first["status"] != second["status"]


@pytest.mark.parametrize("text,intent,slots", [
    ("i need python 3.12", "install_software", {"name": "python 3.12"}),
    ("i want node 20", "install_software", {"name": "node 20"}),
    ("get me jdk 17", "install_software", {"name": "jdk 17"}),
    ("do autoreply in whatsapp for 10 min", "whatsapp_auto_reply", None),
    ("do i have python installed", "check_app_installed", {"name": "python"}),
])
def test_routing(text, intent, slots):
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter

    d = asyncio.run(SmartRouter(llm_provider=DisabledProvider()).route(text))
    assert d.intent == intent and (slots is None or d.slots == slots)


def test_clarifications_are_questions():
    from jarvis.core.router.ollama import clarify_question
    assert "auto reply" in clarify_question("whatsapp_auto_reply", "action")
    assert clarify_question("send_whatsapp_message", "recipient") == "Who should I send it to?"
