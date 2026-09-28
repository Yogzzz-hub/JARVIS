"""Bugs the phase suite / blind sets found: weak keyword guesses never act, relative brightness, compound steps are
translated like single commands, dictation really stops, message words never switch on auto-reply."""
from __future__ import annotations

import asyncio

import pytest

from jarvis.core.router.ollama import DisabledProvider
from jarvis.core.router.router import SmartRouter


@pytest.fixture(scope="module")
def router():
    return SmartRouter(llm_provider=DisabledProvider())


def route(router, text):
    return asyncio.run(router.route(text))


@pytest.mark.parametrize("text", ["i'm feeling tired", "what have i asked you today", "i need my rent agreement, where is it",
                                  "what was the last thing i asked you"])
def test_a_sentence_without_the_actions_keyword_never_triggers_it(router, text):
    d = route(router, text)
    assert d.intent not in ("reply_whatsapp_all", "reply_whatsapp_message", "get_time", "get_app_location")


@pytest.mark.parametrize("text,intent,slots", [
    ("make the screen brighter", "brightness_set", {"step": 20}),
    ("dim the screen", "brightness_set", {"step": -20}),
    ("dim the screen to 30", "brightness_set", {"percent": 30}),
    ("set brightness to 70, actually 50", "brightness_set", {"percent": 50}),
    ("turn off the sound completely", "volume_mute", {}),
    ("silence my computer", "volume_mute", {}),
    ("crank up the volume", "volume_up", {}),
    ("stop dictation", "dictation_mode_control", {"action": "stop"}),
    ("begin dictation mode", "dictation_mode_control", {"action": "start"}),
    ("open logo.png", "open_file", {"path": "logo.png"}),
    ("send draft.docx to my phone", "android_push_file", {"path": "draft.docx"}),
    ("delete the goodnight shortcut", "delete_shortcut", {"phrase": "goodnight"}),
    ("take me to leetcode.com", "open_website", {"url": "leetcode.com"}),
    ("shoot harini a text saying exam went well", "send_whatsapp_message", {"recipient": "harini", "message": "exam went well"}),
    ("tell mom meeting moved to 5", "send_whatsapp_message", {"recipient": "mom", "message": "meeting moved to 5"}),
    ("okay jarvis open android studio", "open_app", {"name": "android studio"}),
])
def test_everyday_wordings(router, text, intent, slots):
    d = route(router, text)
    assert d.intent == intent and d.lane.value == "LANE_0"
    for k, v in slots.items():
        assert str(d.slots.get(k)).lower() == str(v).lower()


def test_desktop_shortcut_is_never_the_desktop_folder(router):
    d = route(router, "delete the desktop shortcut")
    assert d.lane.value == "CLARIFY" and (d.slots or {}).get("path", "").lower() != "desktop"


def test_message_words_never_switch_on_auto_reply(router):
    d = route(router, "respond to anand with don't wait for me")
    assert d.intent == "reply_whatsapp_message"
    assert route(router, "reply to yoga automatically for the next hour").intent == "whatsapp_auto_reply"


def test_would_you_like_is_a_question(router):
    assert route(router, "would you like to play a game").intent is None


def test_mute_capability_no_longer_sends_an_empty_volume_set():
    from jarvis.core.capabilities.registry import get_default_capability_registry
    caps = {c.id: c for c in get_default_capability_registry().list_all()}
    assert caps["windows.volume_mute"].target_tool == "volume_mute"
    assert caps["windows.volume_unmute"].target_tool == "volume_unmute"


def test_dictation_tool_stops_on_pause():
    from jarvis.tools.productivity import dictation

    class Mgr:
        stopped = False

        def stop(self):
            Mgr.stopped = True
            return "notepad"
    orig = dictation.get_dictation_manager
    dictation.get_dictation_manager = lambda: Mgr()
    try:
        out = dictation.DictationModeControlTool().run(dictation.DictationModeInput(action="pause"))
        assert Mgr.stopped and out["active"] is False
    finally:
        dictation.get_dictation_manager = orig


def test_compound_steps_are_translated_like_single_commands():
    from jarvis.core.commands.service import CommandService

    class Tool:
        def __init__(self, pct):
            self.pct = pct

        def run(self, _):
            return {"percent": self.pct}

    class Reg:
        def contains(self, name):
            return name in ("volume_set", "volume_get", "brightness_set", "brightness_get")

        def get(self, name):
            return Tool(40)
    svc = CommandService.__new__(CommandService)
    svc.registry = Reg()
    assert svc._translate_intent("volume_mute", {}) == ("volume_set", {"percent": 0})
    assert svc._translate_intent("brightness_set", {"step": -20}) == ("brightness_set", {"percent": 20})
    assert svc._translate_intent("brightness_set", {"percent": 70}) == ("brightness_set", {"percent": 70})


def test_google_tools_read_mail_list_and_add_events_with_fake_google():
    from datetime import datetime

    from jarvis.integrations.google.fake_provider import make_fake_calendar_client, make_fake_gmail_client
    from jarvis.tools.system.google_tools import EventCreateTool, EventsListTool, MailListTool, parse_when, time_range

    gmail, _ = make_fake_gmail_client()
    cal, _ = make_fake_calendar_client()
    mail = asyncio.run(MailListTool(gmail).run({"limit": 2}))
    assert mail["count"] == 2 and "latest emails" in mail["message"]
    added = asyncio.run(EventCreateTool(cal).run({"summary": "dentist", "when": "tomorrow at 4"}))
    assert "dentist" in added["message"] and added["items"][0]["start"].split("T")[1].startswith("16:00")
    assert asyncio.run(EventsListTool(cal).run({"time_window": "tomorrow"}))["count"] >= 1
    assert EventCreateTool.definition.requires_confirmation  # adding to the calendar always asks first

    now = datetime(2026, 9, 28, 10, 0).astimezone()  # a Monday
    assert parse_when("friday at 3:30 pm", now).strftime("%a %H:%M") == "Fri 15:30"
    assert parse_when("on friday", now) is None  # no time: JARVIS asks
    start, end = time_range("thursday evening", now)
    assert start.strftime("%a %H") == "Thu 17" and end.hour == 21


def test_google_tools_are_registered_actions():
    from jarvis.tools.system.google_tools import create_google_tools
    assert {t.definition.name for t in create_google_tools()} == {"gmail_list_recent", "calendar_list_events", "calendar_create_event"}


@pytest.mark.parametrize("text", ["is spotify a good app for beginners", "the music is killing my ears, lower it",
                                  "no, don't close audacity", "just let gokul know don't forget the keys",
                                  "who was the last message sent to", "hold on, was that message actually sent",
                                  "ping keerthi on whatsapp and say class is cancelled"])
def test_conversational_sentences_never_trigger_the_wrong_action(router, text):
    d = route(router, text)
    assert d.intent not in ("close_app", "close_window", "forget_fact", "reply_whatsapp_message", "powershell_command")
    if text.startswith(("was", "hold on", "who was")):
        assert d.intent != "send_whatsapp_message"


@pytest.mark.parametrize("text,intent", [
    ("before i forget, open brave", "open_app"),
    ("someone's coming, quickly minimize everything", "show_desktop"),
    ("i'm heading out, lock the pc", "system_power_control"),
    ("don't let me forget to call gokul tomorrow", "set_reminder"),
    ("set vloum to 20", "volume_set"),
    ("say taht one more time", "recent_actions"),
    ("fire gimp up", "open_app"),
    ("shut telegram", "close_app"),
    ("text machan and tell them the exam got postponed", "send_whatsapp_message"),
    ("is my monday morning free", "calendar_list_events"),
])
def test_conversational_commands(router, text, intent):
    assert route(router, text).intent == intent


def test_shell_commands_need_shell_syntax(router):
    assert route(router, "ping 8.8.8.8").intent == "powershell_command"
    assert route(router, "ping arun").intent != "powershell_command"


def test_two_slip_typos_only_rearrange_letters():
    from jarvis.core.router.normalize import correct_command_typos
    assert correct_command_typos("set vloum to 20") == "set volume to 20"
    assert correct_command_typos("terminate vlc player") == "terminate vlc player"
