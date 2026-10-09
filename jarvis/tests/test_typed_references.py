"""Typed reference resolution (P9): a reference is resolved by the type of thing it can point at and the turn it follows,
never by raw recency, and an unresolved reference is never used as a name.

New constructions of each mechanism, not Blind-11 sentences.
"""
from __future__ import annotations

import pytest

from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.context.carryover import CarryOver
from jarvis.core.router.models import RouteLane
from jarvis.core.router.router import SmartRouter
from jarvis.core.semantics.references import is_list_reference, is_reference, kind, ordinal


async def _route(text: str):
    return await SmartRouter().route(CommandRequest(text=text))


def _after(text: str, tool: str, slots: dict, pending: bool = False) -> CarryOver:
    c = CarryOver()
    c.record(text, tool, slots, pending=pending)
    return c


# ------------------------------------------------------------------------------------------------ what a reference is
@pytest.mark.parametrize("value,ref,pos,k", [
    ("the third of those", True, 3, None),
    ("the fourth email in that list", True, 4, "email"),
    ("result number three", True, 3, "result"),
    ("that old one", True, None, None),
    ("athu", True, None, None),
    ("the youtube tab", False, None, "tab"),       # names youtube: a description, not only a reference
    ("a new tab", False, None, "tab"),
    ("spotify", False, None, None),
])
def test_reference_expressions_are_typed(value, ref, pos, k):
    assert is_reference(value) is ref and ordinal(value) == pos and kind(value) == k


def test_a_position_in_results_is_a_list_reference():
    assert is_list_reference("link number 2") and not is_list_reference("the second of those")


# ------------------------------------------------------------------------------------------------ never a literal name
@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["launch the third of those", "kill that old one", "compress that folder up",
                                  "where is it kept", "close athu"])
async def test_an_unresolved_reference_is_never_an_entity_name(text):
    d = await _route(text)
    for v in (d.slots or {}).values():
        assert not (isinstance(v, str) and is_reference(v)), (text, d.lane, d.intent, d.slots)


@pytest.mark.asyncio
async def test_a_position_in_search_results_opens_that_result():
    d = await _route("open link number three")
    assert d.intent == "browser_op" and d.slots.get("ordinal") == 3, (d.intent, d.slots)


@pytest.mark.asyncio
async def test_a_remark_after_the_command_is_not_its_object():
    d = await _route("close notepad, I'm finished writing")
    assert d.intent == "close_app" and d.slots.get("name") == "notepad", d.slots


# ------------------------------------------------------------------------------------------------ resolution by type
def test_on_off_flip_uses_the_last_toggle():
    c = _after("turn off wifi on my phone", "android_toggle", {"setting": "wifi", "on": False})
    assert c.rewrite("switch it back on") == "turn on wifi on my phone"
    c = _after("enable night light", "system_op", {"action": "night_light"})
    assert c.rewrite("disable that again") == "disable night light"


@pytest.mark.parametrize("prev,tool,slots,follow,expected", [
    ("turn off bluetooth on my phone", "android_toggle", {"setting": "bluetooth"}, "and the hotspot too", "turn off hotspot on my phone"),
    ("what's on my calendar for monday", "calendar_list_events", {"time_window": "monday"}, "and what about wednesday",
     "what's on my calendar for wednesday"),
    ("set the brightness to 70", "brightness_set", {"percent": 70}, "do the same for volume", "set the volume to 70"),
    ("set the brightness to 70", "brightness_set", {"percent": 70}, "and the volume to the same level", "set the volume to 70"),
])
def test_a_sibling_of_the_same_kind_replaces_its_sibling(prev, tool, slots, follow, expected):
    assert _after(prev, tool, slots).rewrite(follow) == expected


def test_repeat_and_intensify_only_safe_commands():
    assert _after("zoom in", "browser_quick_action", {"action": "zoom_in"}).rewrite("again, a bit more") == "zoom in"
    assert _after("speak faster", "speech_control", {"action": "faster"}).rewrite("faster than that") == "speak faster"
    assert _after("send ravi I'm home", "send_whatsapp_message", {"recipient": "ravi", "message": "I'm home"}).rewrite("do it again") is None


def test_refinement_keeps_the_list_and_adds_the_qualifier():
    c = _after("show my emails from amazon", "gmail_list_recent", {"sender": "amazon"})
    assert c.rewrite("just the unread ones") == "show my unread emails from amazon"


def test_pronoun_object_of_a_reversible_verb_is_the_typed_resource_before_it():
    c = _after("open quarterly_report.docx", "open_file", {"path": "quarterly_report.docx"})
    assert c.rewrite("copy it to the desktop") == "copy quarterly_report.docx to the desktop"
    assert c.rewrite("delete it") is None                      # destructive verbs never take a guessed object
    c = _after("is zoom installed", "check_app_installed", {"name": "zoom"})
    assert c.rewrite("then install it") == "install zoom"
    assert c.rewrite("where is it installed") == "where is zoom installed"


def test_type_mismatch_does_not_resolve():
    c = _after("open notepad", "open_app", {"name": "notepad"})
    assert c.rewrite("rename it to scratch") is None           # an app is not a file to rename


def test_introspection_and_forget_follow_ups():
    c = _after("message Priya that I'm on my way", "send_whatsapp_message", {"recipient": "Priya", "message": "I'm on my way"})
    assert c.rewrite("who did that go to") == "who did you send that to"
    c = _after("remember my locker is number 12", "remember_fact", {"fact": "my locker is number 12"})
    assert c.rewrite("actually forget that") == "forget that my locker is number 12"


def test_tanglish_demonstrative_is_it():
    c = _after("open calculator", "open_app", {"name": "calculator"})
    assert c.rewrite("close atha") == "close calculator"


def test_extend_and_settings_page_and_device_continuity():
    c = _after("turn on auto reply for Kavin", "whatsapp_auto_reply", {"who": "Kavin"})
    assert c.rewrite("extend it to everyone") == "turn on auto reply for everyone"
    c = _after("open settings", "open_system_settings", {"page": "main"})
    assert c.rewrite("go to the display section in there") == "open display settings"
    c = _after("mirror my phone screen", "android_mirror", {})
    assert c.rewrite("tap on wifi") == "tap on wifi on my phone"


def test_nothing_resolves_while_a_yes_is_pending():
    c = _after("turn off wifi on my phone", "android_toggle", {"setting": "wifi"}, pending=True)
    assert c.rewrite("switch it back on") is None
