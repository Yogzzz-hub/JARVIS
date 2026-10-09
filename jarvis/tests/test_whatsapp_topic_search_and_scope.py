"""Cross-chat topic search ("latest message about my project deadline") and "group" used as a verb."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from jarvis.core.router.ollama import DisabledProvider
from jarvis.core.router.router import SmartRouter
from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
from jarvis.integrations.whatsapp.models import NormalizedWhatsAppMessage
from jarvis.tools.system.whatsapp_tools import ReadWhatsAppMessagesTool, group_scope_from_text


@pytest.fixture(scope="module")
def router():
    return SmartRouter(llm_provider=DisabledProvider())


def _msg(inbox, mid, chat, name, ts, text):
    inbox.add_message(NormalizedWhatsAppMessage(message_id=mid, chat_id=chat, sender_id=chat, sender_display_name=name,
                                                timestamp=ts, type="text", text=text))


@pytest.mark.parametrize("text,expected", [
    ("summarize my unread whatsapp messages, prioritize important personal chats, group related messages, "
     "and tell me what needs a reply", {"scope": "DIRECT_ONLY"}),
    ("group them by person and summarize my whatsapp messages", {}),
    ("summarize the CSE group", {"group": "cse", "scope": "GROUP_ONLY"}),
    ("summarize group chats", {"scope": "GROUP_ONLY"}),
    ("summarize my personal and group messages", {"scope": "DIRECT_AND_GROUP"}),
])
def test_group_verb_is_not_a_group_name(text, expected):
    assert group_scope_from_text(text) == expected


def test_summary_with_group_verb_routes_to_personal_chats(router):
    d = asyncio.run(router.route("Jarvis, summarize my unread WhatsApp messages, prioritize important personal chats, "
                                 "group related messages, and tell me what needs a reply. Don't read internal IDs aloud."))
    assert d.intent == "summarize_whatsapp_messages"
    assert "group" not in d.slots


@pytest.mark.parametrize("text,topic", [
    ("Find the latest message about my project deadline across my chats, identify who sent it, summarize the relevant "
     "context, and show the original message.", "project deadline"),
    ("search for messages about the wedding", "wedding"),
    ("what's the latest message about rent", "rent"),
    ("show me messages regarding the hostel fees on whatsapp", "hostel fees"),
])
def test_topic_search_routes_to_one_cross_chat_read(router, text, topic):
    d = asyncio.run(router.route(text))
    assert d.intent == "read_whatsapp_messages"
    assert d.slots["topic"] == topic


@pytest.mark.parametrize("text", ["find the file about project deadline", "find emails about the invoice"])
def test_topic_search_leaves_files_and_email_alone(router, text):
    assert asyncio.run(router.route(text)).intent != "read_whatsapp_messages"


def test_topic_search_returns_latest_match_with_sender(tmp_path: Path):
    inbox = WhatsAppInbox(tmp_path / "inbox.db")
    _msg(inbox, "m1", "111@s.whatsapp.net", "Arun", "2026-09-20T10:00:00Z", "The project deadline is Friday")
    _msg(inbox, "m2", "222@s.whatsapp.net", "Priya", "2026-09-21T10:00:00Z", "Project deadline moved to Monday!")
    _msg(inbox, "m3", "333@s.whatsapp.net", "Ravi", "2026-09-22T10:00:00Z", "lunch at 1?")
    _msg(inbox, "m4", "444@g.us", "Team", "2026-09-19T10:00:00Z", "deadline reminder for the project")
    out = ReadWhatsAppMessagesTool(inbox).run({"filter": "all", "topic": "project deadline", "limit": 3})
    assert out["status"] == "SUCCESS"
    assert [m["message_id"] for m in out["messages"]] == ["m2", "m1", "m4"]
    assert out["spoken_summary"].startswith("The latest message about project deadline is from Priya")
    assert "Monday" in out["spoken_summary"]


def test_topic_search_falls_back_to_any_word_and_reports_nothing(tmp_path: Path):
    inbox = WhatsAppInbox(tmp_path / "inbox.db")
    _msg(inbox, "m1", "111@s.whatsapp.net", "Arun", "2026-09-20T10:00:00Z", "submit before the deadline")
    tool = ReadWhatsAppMessagesTool(inbox)
    assert [m["message_id"] for m in tool.run({"filter": "all", "topic": "project deadline"})["messages"]] == ["m1"]
    empty = tool.run({"filter": "all", "topic": "wedding"})
    assert empty["count"] == 0 and "couldn't find" in empty["spoken_summary"]
