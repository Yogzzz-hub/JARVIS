"""Follow-up intelligence: 'tell me ...' is a question, never a message to someone called 'me'; JARVIS remembers
what it did and answers 'who did you send that to?' truthfully; WhatsApp counts are exact."""
from __future__ import annotations

import asyncio

import pytest

from jarvis.core.action_log import ActionLog, answer_followup, get_action_log, is_followup
from jarvis.core.router.ollama import DisabledProvider
from jarvis.core.router.router import SmartRouter


@pytest.fixture(scope="module")
def router():
    return SmartRouter(llm_provider=DisabledProvider())


def route(router, text):
    return asyncio.run(router.route(text))


@pytest.mark.parametrize("text,intent,slots", [
    ("tell me the total unread msg in whatsapp", "read_whatsapp_messages", {"filter": "unread", "count_only": True}),
    ("tell me how many unread messages i have", "read_whatsapp_messages", {"filter": "unread", "count_only": True}),
    ("tell me who messaged me", "summarize_whatsapp_messages", {}),
    ("tell me what arun said", "read_whatsapp_messages", {"filter": "all", "sender": "arun", "limit": 5}),
    ("what did amma send", "read_whatsapp_messages", {"filter": "all", "sender": "amma", "limit": 5}),
    ("show me my battery", "battery_status", {}),
    ("tell me the time", "get_time", {}),
])
def test_tell_me_is_a_question_about_what_follows(router, text, intent, slots):
    d = route(router, text)
    assert d.intent == intent and d.slots == slots


@pytest.mark.parametrize("text", ["tell me I'm awesome", "tell me a joke", "tell me about black holes",
                                  "Tell me what notepad is used for.", "Tell me what system info means."])
def test_tell_me_never_sends_a_message_or_acts(router, text):
    d = route(router, text)
    assert d.intent not in SmartRouter._SEND_INTENTS and d.lane.value != "LANE_0"  # conversation, not an action


@pytest.mark.parametrize("text", ["send a message to me saying hi", "message him saying ok", "tell it hello"])
def test_pronouns_are_never_contacts(router, text):
    d = route(router, text)
    assert d.lane.value in ("CLARIFY", "LANE_2") and (d.slots or {}).get("recipient", "").lower() not in ("me", "him", "it", "to")


def test_real_messages_still_work(router):
    d = route(router, "tell arun I will come")
    assert d.intent == "send_whatsapp_message" and d.slots["recipient"] == "Arun"
    assert route(router, "tell everyone who messaged me that I'm busy").intent == "reply_whatsapp_all"


@pytest.mark.parametrize("text", ["to whom u have sent", "who did you send that to", "what did you just do", "did it send",
                                  "what did you say", "what was the message", "Jarvis, who did u message"])
def test_followups_go_to_the_action_record(router, text):
    assert is_followup(text)
    d = route(router, text)
    assert d.intent == "recent_actions" and d.slots["question"]


def test_followup_answers_come_from_what_really_happened():
    log = ActionLog()
    assert "haven't done anything" in answer_followup("what did you just do", log)
    log.record("send_whatsapp_message", {"recipient": "Me", "message": "The total unread message"}, "SUCCESS",
               "Message delivered to Me on WhatsApp.")
    ans = answer_followup("to whom u have sent", log)
    assert "Me" in ans and "The total unread message" in ans and "your own chat" in ans
    log.record("open_app", {"name": "chrome"}, "SUCCESS", "Chrome is open.")
    assert "opened chrome" in answer_followup("what did you just do", log)
    assert "Arun" not in answer_followup("who did you send that to", log)  # still the last *message*, to Me
    log.record("_chat", {}, "SUCCESS", "Paris is the capital of France.")
    assert answer_followup("what did you say", log) == "Paris is the capital of France."
    log.record("send_whatsapp_message", {"recipient": "Arun", "message": "hi"}, "FAILED", "Not connected")
    assert answer_followup("did it send", log).startswith("No")


def test_command_service_records_actions_and_the_chat_sees_them(monkeypatch):
    from jarvis.core.commands.service import CommandService
    from jarvis.core.llm.assistant import Assistant
    from jarvis.core.router.models import ReasonCode, RouteDecision, RouteLane, RouteSource
    from jarvis.core.tasks.manager import State
    from jarvis.tools.base import ToolResult

    get_action_log().clear()
    svc = CommandService.__new__(CommandService)
    decision = RouteDecision(request_id="r1", lane=RouteLane.LANE_0, intent="send_whatsapp_message",
                             slots={"recipient": "arun", "message": "on my way"}, confidence=1.0, source=RouteSource.EXACT,
                             normalized_text="tell arun on my way", reason_code=ReasonCode.EXACT_PATTERN)
    svc._last_decisions = {"r1": decision}

    class Task:
        request_id = "r1"
    svc._log_action(Task(), State.SUCCESS, "Sent to Arun.",
                    ToolResult(success=True, data={"recipient": "Arun Kumar"}, tool_name="send_whatsapp_message"))
    last = get_action_log().last()
    assert last.tool == "send_whatsapp_message" and last.args["recipient"] == "Arun Kumar"  # the resolved contact
    prompt = Assistant(client=object()).system_prompt(speakable=True)
    assert 'sent the WhatsApp message "on my way" to Arun Kumar' in prompt
    get_action_log().clear()


def test_unread_count_is_exact_and_per_person(tmp_path):
    from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
    from jarvis.integrations.whatsapp.models import NormalizedWhatsAppMessage
    from jarvis.tools.system.whatsapp_tools import ReadWhatsAppMessagesTool

    inbox = WhatsAppInbox(tmp_path / "inbox.db")
    for i in range(12):
        who, jid = [("Sushmitaa", "91111@s.whatsapp.net"), ("Scooby", "92222@s.whatsapp.net")][i % 2]
        inbox.add_message(NormalizedWhatsAppMessage(message_id=f"m{i}", chat_id=jid, sender_id=jid, sender_display_name=who,
                                                    timestamp=str(1000 + i), text=f"msg {i}", is_group=False))
    inbox.add_message(NormalizedWhatsAppMessage(message_id="g1", chat_id="1203@g.us", sender_id="x@s.whatsapp.net",
                                                sender_display_name="Devi", timestamp="2000", text="hi all", is_group=True,
                                                chat_name="CSE"))
    tool = ReadWhatsAppMessagesTool(inbox=inbox)
    out = tool.run({"filter": "unread", "count_only": True})
    assert out["count"] == 12  # not capped at 5
    assert out["spoken_summary"].startswith("You have 12 unread WhatsApp messages in your personal chats from 2 people")
    assert "Sushmitaa 6" in out["spoken_summary"] and "Group chats have 1 more in 1 group" in out["spoken_summary"]
    one = tool.run({"filter": "all", "sender": "scooby"})
    assert one["count"] == 6 and all(m["sender"] == "Scooby" for m in one["messages"])
