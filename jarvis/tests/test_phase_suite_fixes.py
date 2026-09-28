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
