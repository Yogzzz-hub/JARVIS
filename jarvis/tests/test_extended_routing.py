"""Routing of phone control, messaging, knowledge, web, reminders and open questions (deterministic, no model)."""
from __future__ import annotations

import pytest

from jarvis.core.router.models import RouteLane
from jarvis.core.router.ollama import DisabledProvider
from jarvis.core.router.router import SmartRouter
from jarvis.memory.working_memory import WorkingMemory


@pytest.fixture
def router():
    return SmartRouter(llm_provider=DisabledProvider(), working_memory=WorkingMemory())


CASES = [
    # phone
    ("lock my phone", "android_key", {"key": "sleep"}),
    ("turn up the volume on my phone", "android_key", {"key": "volume_up"}),
    ("pause the music on my phone", "android_key", {"key": "media_play_pause"}),
    ("take a screenshot of my phone", "android_screenshot", {}),
    ("open spotify on my phone", "android_open_app", {"app_name": "spotify"}),
    ("call 9876543210 on my phone", "android_dial", {"number": "9876543210"}),
    ("type hello world on my phone", "android_input", {"action": "text", "text": "hello world"}),
    ("is my phone connected", "android_status", {}),
    ("Phone connectivity?", "android_status", {}),
    # messaging
    ("ask rahul if he is free tonight", "send_whatsapp_message", {"recipient": "rahul", "message": "if he is free tonight"}),
    ("remind dad to take his medicine on whatsapp", "send_whatsapp_message", {"recipient": "dad", "message": "to take his medicine"}),
    ("let yoga know the meeting moved to 5pm", "send_whatsapp_message", {"recipient": "yoga", "message": "the meeting moved to 5pm"}),
    ("whatsapp boss saying the report is ready", "send_whatsapp_message", {"recipient": "boss", "message": "the report is ready"}),
    ("reply to rahul", "reply_whatsapp_message", {"recipient": "rahul"}),
    ("reply to the last message saying on my way", "reply_whatsapp_message", {"instruction": "on my way"}),
    # knowledge
    ("learn my documents folder", "knowledge_ingest", {"path": "documents"}),
    ("what do my documents say about the refund policy", "knowledge_search", {"question": "the refund policy"}),
    ("search my notes for password hints", "search_notes", {"query": "password hints"}),
    # web
    ("search amazon for noise cancelling headphones", "open_website", {"url": "https://www.amazon.in/s?k=noise+cancelling+headphones"}),
    ("search for lo-fi beats on youtube", "open_website", {"url": "https://www.youtube.com/results?search_query=lo-fi+beats"}),
    ("go to wikipedia.org", "open_website", {"url": "wikipedia.org"}),
    # reminders
    ("remind me to drink water in 10 minutes", "set_reminder", {"text": "drink water in 10 minutes"}),
    ("show my reminders", "list_reminders", {}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("text,intent,slots", CASES)
async def test_extended_routes(router, text, intent, slots):
    decision = await router.route(text)
    assert decision.lane == RouteLane.LANE_0, (text, decision)
    assert decision.intent == intent
    for key, value in slots.items():
        assert decision.slots.get(key) == value, (text, decision.slots)


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [
    "tell me a joke",
    "what's the weather today",
    "how are you",
    "what is the capital of france",
    "which level is the office parking on",
    "and where should visitors go",
    "what is the office wifi password",
    "explain recursion like I'm five",
])
async def test_conversation_goes_to_the_assistant_not_a_tool(router, text):
    decision = await router.route(text)
    assert decision.lane == RouteLane.LANE_2 and decision.intent is None, (text, decision)


@pytest.mark.asyncio
@pytest.mark.parametrize("text,intent", [
    ("take a screenshot", "take_screenshot"),
    ("what time is it", "get_time"),
    ("where is my resume", "find_file"),
    ("is my wifi connected", "wifi_status"),
    ("send this file to my phone", "localsend_file"),
    ("tell rahul hi", "send_whatsapp_message"),
])
async def test_existing_commands_are_unaffected(router, text, intent):
    decision = await router.route(text)
    assert decision.intent == intent, (text, decision)


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [
    "Search Google for recent news on AI, save top 3 article links, and open first link in Chrome.",
    "Take a screenshot of the dashboard, save to Desktop, and draft email to the team.",
    "remind me to call mom and then open chrome",
])
async def test_compound_requests_are_left_to_the_planner(router, text):
    from jarvis.core.router.extended import match_extended
    assert match_extended(text, "r") is None


def test_move_and_copy_never_take_the_destination_as_the_source():
    from jarvis.core.capabilities.registry import get_default_capability_registry
    from jarvis.core.capabilities.slot_extractor import extract_slots

    registry = get_default_capability_registry()
    slots, missing = extract_slots(registry.get("file.move"), "move the invoice to documents")
    assert slots.get("source") != "Documents" and "source" in missing, "would have moved the Documents folder"
    slots, _ = extract_slots(registry.get("file.copy"), r"copy C:\temp\a.txt to desktop")
    assert slots["source"] == r"C:\temp\a.txt"
    slots, _ = extract_slots(registry.get("file.move"), "move my downloads folder to desktop")
    assert slots["source"] == "Downloads"


@pytest.mark.asyncio
@pytest.mark.parametrize("text,goal", [
    ("use the browser to find the price of a Pixel 9 on Flipkart", "find the price of a Pixel 9 on Flipkart"),
    ("find the price of iphone 16 on amazon", "find the price of iphone 16 on amazon"),
])
async def test_browsing_goals_go_to_the_web_agent(router, text, goal):
    decision = await router.route(text)
    assert decision.intent == "web_task" and decision.slots["goal"] == goal
