"""Corrections, exclusions, prohibitions, typed removal, coordination, event slots and typed references.

New constructions of each mechanism (not Blind-11 sentences).
"""
from __future__ import annotations

import pytest

from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.context.carryover import CarryOver
from jarvis.core.router.models import RouteLane
from jarvis.core.router.router import SmartRouter
from jarvis.core.semantics.constraints import apply_correction, extract_exclusions, normalize_event_time, prohibitions


async def _route(text: str):
    return await SmartRouter().route(CommandRequest(text=text))


# ------------------------------------------------------------------------------------------------------ corrections
@pytest.mark.parametrize("text,expected", [
    ("text Meena I'm running late, no, text Kavitha", "text Kavitha I'm running late"),
    ("set a reminder for 7, no wait, 7:15", "set a reminder for 7:15"),
    ("book the room for thursday, actually friday", "book the room for friday"),
    ("volume thirty, sorry, sixty", "volume sixty"),
    ("launch firefox, i mean brave", "launch brave"),
    ("lock the pc, no, restart it", "restart it"),
])
def test_corrections_supersede_the_old_value(text, expected):
    assert apply_correction(text)[0] == expected


@pytest.mark.parametrize("text", [
    "type dear sir, wait for my reply",
    "send anu sorry, actually I can't come today",
    "tell him no, we are not coming",
])
def test_corrections_never_rewrite_content_being_sent_or_typed(text):
    assert apply_correction(text)[0] == text


@pytest.mark.asyncio
async def test_superseded_recipient_and_time_are_not_executable():
    d = await _route("message Suresh I'm on my way, no, message Ganesh")
    assert d.intent == "send_whatsapp_message" and d.slots["recipient"] == "Ganesh" and "Suresh" not in str(d.slots)
    d = await _route("put dinner with anu at 7, no, at 8 on my calendar")
    assert d.intent == "calendar_create_event" and "8" in d.slots["when"] and " 7" not in d.slots["when"], d.slots


# ------------------------------------------------------------------------------------------------ exclusions / negation
def test_exclusions_and_prohibitions_are_extracted():
    assert extract_exclusions("reply to everyone I'm driving, except mom") == ("reply to everyone I'm driving", ["mom"])
    assert prohibitions("don't send anything, just show me who messaged") == ("show me who messaged", ["send anything"])


@pytest.mark.asyncio
async def test_exclusion_travels_with_the_bulk_reply_not_inside_the_message():
    d = await _route("tell everyone who texted me I'm in a meeting, except Lakshmi")
    assert d.intent == "reply_whatsapp_all" and d.slots.get("exclude") == ["Lakshmi"]
    assert "Lakshmi" not in d.slots.get("message", "")


@pytest.mark.asyncio
async def test_prohibited_effect_on_the_prohibited_object_never_runs():
    d = await _route("don't uninstall teams, just close it")
    assert d.intent != "uninstall_software"
    d = await _route("don't open youtube, open spotify")
    assert d.intent == "open_app" and d.slots.get("name") == "spotify"


@pytest.mark.asyncio
async def test_set_wide_action_that_cannot_keep_the_exclusion_asks():
    d = await _route("minimise everything except the calculator")
    assert d.lane in (RouteLane.LANE_0, RouteLane.CLARIFY)
    if d.lane == RouteLane.LANE_0:
        assert d.intent == "window_op" and d.slots.get("action") == "isolate"


# ------------------------------------------------------------------------------------------------ typed removal
@pytest.mark.asyncio
@pytest.mark.parametrize("text,path_end", [
    ("throw out draft_v2.docx from documents", "Documents/draft_v2.docx"),
    ("I no longer need installer.msi in downloads", "Downloads/installer.msi"),
    ("toss the notes.txt file on my desktop", "Desktop/notes.txt"),
])
async def test_removal_of_a_typed_file_is_a_scoped_delete(text, path_end):
    d = await _route(text)
    assert d.intent == "delete_file" and d.slots["path"].replace("\\", "/").endswith(path_end), (text, d.slots)


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["throw away my downloads folder", "get rid of the documents"])
async def test_removal_of_a_whole_user_folder_is_refused(text):
    d = await _route(text)
    assert d.lane == RouteLane.REJECT, (text, d.lane, d.intent)


@pytest.mark.asyncio
async def test_removal_of_non_files_goes_elsewhere():
    d = await _route("remove the zoom app from this laptop")
    assert d.intent == "uninstall_software"


# ------------------------------------------------------------------------------------------------ coordination
@pytest.mark.asyncio
async def test_coordinated_objects_are_separate_actions():
    d = await _route("uninstall teams and skype")
    assert [s.arguments.get("name") for s in d.subcommands] == ["teams", "skype"]
    d = await _route("send Anitha good morning and Rahul see you soon")
    assert [(s.arguments["recipient"], s.arguments["message"]) for s in d.subcommands] == \
        [("Anitha", "good morning"), ("Rahul", "see you soon")]
    d = await _route("send ravi salt and pepper")
    assert d.intent == "send_whatsapp_message" and d.slots["message"] == "salt and pepper"


# ------------------------------------------------------------------------------------------------ event slots
@pytest.mark.parametrize("when,clean,minutes", [
    ("on monday at 10 for 45 minutes", "on monday at 10", 45),
    ("tomorrow at 2 for two hours", "tomorrow at 2", 120),
    ("at 5 pm tusday", "at 5 pm tuesday", None),
    ("saterday morning for half an hour", "saturday morning", 30),
])
def test_event_time_is_typed(when, clean, minutes):
    assert normalize_event_time(when) == (clean, minutes)


# ------------------------------------------------------------------------------------------------ typed references
def test_person_pronoun_resolves_only_from_the_active_person_thread():
    c = CarryOver()
    c.record("show me messages from Farhan", "read_whatsapp_messages", {"sender": "farhan"})
    assert c.rewrite("text him I'll call later") == "text Farhan I'll call later"
    c.record("open notepad", "open_app", {"name": "notepad"})
    assert c.rewrite("text him I'll call later") is None   # the active thread is no longer a person


def test_event_change_only_while_the_event_waits_for_a_yes():
    c = CarryOver()
    c.record("add yoga tomorrow at 6 to my calendar", "calendar_create_event", {"summary": "yoga"}, pending=True)
    assert c.rewrite("make it 90 minutes") == "add yoga tomorrow at 6 for 90 minutes"
    c = CarryOver()
    c.record("add yoga tomorrow at 6 to my calendar", "calendar_create_event", {"summary": "yoga"}, pending=False)
    assert c.rewrite("make it 90 minutes") != "add yoga tomorrow at 6 for 90 minutes"
