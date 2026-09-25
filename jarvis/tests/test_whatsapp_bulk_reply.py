"""'Tell everyone who messaged me I'm busy': personal chats only, one confirmation, follow-ups reuse the message."""
from __future__ import annotations

import time

import pytest

from jarvis.integrations.whatsapp.ai import split_bulk_instruction
from jarvis.integrations.whatsapp.models import NormalizedWhatsAppMessage
from jarvis.tests.ai_harness import AIHarness, route_by_prompt

PERSONAL = "The owner wants to tell"


def _msg(chat: str, sender: str, name: str, text: str, mid: str, ago_s: float = 60, from_me: bool = False):
    return NormalizedWhatsAppMessage(message_id=mid, chat_id=chat, sender_id=sender, sender_display_name=name,
                                     timestamp=str(time.time() - ago_s), text=text, is_from_me=from_me)


def _seed(inbox):
    # The screenshot scenario: Devi and Dr Nisha wrote in groups, Rahul and Priya wrote personally.
    inbox.add_message(_msg("120363@g.us", "919000000001@s.whatsapp.net", "devi", "NIDAR 2026-27 drone challenge", "g1", 300))
    inbox.add_message(_msg("120364@g.us", "919000000002@s.whatsapp.net", "Dr Nisha", "TEAM 62 CONTACT ME IMMEDIATELY", "g2", 200))
    inbox.add_message(_msg("919000000003@s.whatsapp.net", "919000000003@s.whatsapp.net", "Rahul", "Are you coming for lunch?", "d1", 120))
    inbox.add_message(_msg("919000000004@s.whatsapp.net", "919000000004@s.whatsapp.net", "Priya Sharma", "Call me when free", "d2", 90))
    # Arun already got an answer from the owner: not waiting any more.
    inbox.add_message(_msg("919000000005@s.whatsapp.net", "919000000005@s.whatsapp.net", "Arun", "ok bro", "d3", 500))
    inbox.add_message(_msg("919000000005@s.whatsapp.net", "me", "Me", "see you tmrw da", "d4", 400, from_me=True))


def personalise(payload):
    content = payload["messages"][-1]["content"]
    name = content.split("The owner wants to tell ", 1)[1].split(" on WhatsApp", 1)[0]
    return {"message": f"Hi {name.split()[0]}, I'm in a meeting right now, I'll be available in 1 hour."}


@pytest.mark.parametrize("text,body,groups", [
    ("I am busy, I will be available in one hour", "I am busy, I will be available in one hour", False),
    ("this is for only person to person. Don't reply in groups", "", False),
    ("you just reply those guys only", "", False),
    ("I'm driving, include groups too", "I'm driving", True),
])
def test_delivery_constraints_are_never_sent_as_text(text, body, groups):
    assert split_bulk_instruction(text) == (body, groups)


@pytest.mark.asyncio
async def test_everyone_who_messaged_gets_a_personal_reply_but_groups_are_skipped(tmp_path):
    h = AIHarness(tmp_path, route_by_prompt([(PERSONAL, personalise)]))
    try:
        _seed(h.inbox)
        res = await h.say("Now I am going to meeting you just send all the guys who are messaging to me that "
                          "I am busy, I will be available in one hour.")
        assert res.state == "WAITING_CONFIRMATION", res.message
        assert "Rahul" in res.message and "Priya" in res.message
        assert "devi" not in res.message.lower() and "nisha" not in res.message.lower() and "Arun" not in res.message
        assert "2 group chats" in res.message
        assert not h.transport.sent_messages, "nothing is sent before the owner says yes"
        prompts = [p["messages"][-1]["content"] for p in h.chat_payloads(PERSONAL)]
        assert prompts and all("I am busy, I will be available in one hour" in p for p in prompts)

        done = await h.say("yes")
        assert done.state == "SUCCESS", done.message
        sent = {m["to"]: m["text"] for m in h.transport.sent_messages}
        assert set(sent) == {"919000000003@s.whatsapp.net", "919000000004@s.whatsapp.net"}
        assert sent["919000000003@s.whatsapp.net"].startswith("Hi Rahul")
        assert not any(to.endswith("@g.us") for to in sent)
    finally:
        await h.close()


@pytest.mark.asyncio
async def test_follow_up_reuses_the_earlier_message_and_ignores_constraints(tmp_path):
    h = AIHarness(tmp_path, route_by_prompt([(PERSONAL, personalise)]))
    try:
        _seed(h.inbox)
        first = await h.say("tell everyone who messaged me that I am busy, I will be available in one hour")
        assert first.state == "WAITING_CONFIRMATION"
        await h.say("no")
        again = await h.say("You just reply the guys who are messaging to me that this is for only person to person. "
                            "Don't reply in groups.")
        assert again.state == "WAITING_CONFIRMATION", again.message
        assert "earlier message" in again.message and "person to person" not in again.message
        third = await h.say("Those who are texting me, you just reply those guys only.")
        assert third.state == "WAITING_CONFIRMATION", third.message
        assert "Rahul" in third.message and "devi" not in third.message.lower()
    finally:
        await h.close()


@pytest.mark.asyncio
async def test_plain_reply_never_lands_in_a_group(tmp_path):
    h = AIHarness(tmp_path, route_by_prompt([("Write the owner's next reply", {"message": "Sure, on my way."})]))
    try:
        h.inbox.add_message(_msg("919000000003@s.whatsapp.net", "919000000003@s.whatsapp.net", "Rahul", "where are you?", "d1", 600))
        h.inbox.add_message(_msg("120363@g.us", "919000000001@s.whatsapp.net", "devi", "Register for NIDAR", "g1", 30))
        res = await h.say("reply to the last message")
        assert res.state == "WAITING_CONFIRMATION", res.message
        assert "Rahul" in res.message and "devi" not in res.message.lower()
    finally:
        await h.close()


@pytest.mark.asyncio
async def test_nobody_waiting_is_reported_plainly(tmp_path):
    h = AIHarness(tmp_path, route_by_prompt([]))
    try:
        h.inbox.add_message(_msg("120363@g.us", "919000000001@s.whatsapp.net", "devi", "hello all", "g1", 30))
        res = await h.say("reply to everyone who texted me that I'm busy")
        assert "Nobody is waiting" in res.message and "1 group chat skipped" in res.message
        assert not h.transport.sent_messages
    finally:
        await h.close()


@pytest.mark.asyncio
async def test_owner_can_ask_about_their_whatsapp_chats(tmp_path):
    from jarvis.integrations.whatsapp.memory import WhatsAppMemory

    seen = []

    def chat(payload):
        seen.append(payload)
        return "Rahul said the Goa trip is on the 14th."

    h = AIHarness(tmp_path, route_by_prompt([("You are JARVIS, a helpful", chat)]))
    try:
        h.inbox.add_message(_msg("919000000003@s.whatsapp.net", "919000000003@s.whatsapp.net", "Rahul",
                                 "Goa trip is fixed for the 14th, bring your passport", "d1", 3600))
        memory = WhatsAppMemory(h.knowledge.knowledge_engine, h.inbox, owner_name="Ashok")
        assert memory.index_chat("919000000003@s.whatsapp.net") >= 1
        res = await h.say("what did rahul say about the goa trip")
        assert res.state == "SUCCESS", res.message
        grounding = seen[-1]["messages"][-1]["content"]
        assert "Goa trip is fixed for the 14th" in grounding

        # On WhatsApp channels the private chat history is never used as context.
        scoped = await h.assistant._knowledge_context("goa trip passport", {"scope:user", "scope:documents"})
        assert not scoped
    finally:
        await h.close()


def test_unread_messages_never_list_the_owners_own_commands(tmp_path):
    from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
    from jarvis.tools.system.whatsapp_tools import ReadWhatsAppMessagesTool

    inbox = WhatsAppInbox(tmp_path / "i.db")
    inbox.add_message(_msg("919999999999@s.whatsapp.net", "919999999999@s.whatsapp.net", "Owner", "Open Notepad", "o1", 60))
    inbox.add_message(_msg("919999999999@s.whatsapp.net", "919999999999@s.whatsapp.net", "Owner", "APPROVE tkt_264fc79809cb", "o2", 50))
    inbox.add_message(_msg("919000000003@s.whatsapp.net", "919000000003@s.whatsapp.net", "Rahul", "Are you coming for lunch?", "d1", 40))
    res = ReadWhatsAppMessagesTool(inbox=inbox).run({"filter": "unread", "limit": 10})
    assert res["count"] == 1 and "Rahul" in res["spoken_summary"] and "Notepad" not in res["spoken_summary"]
