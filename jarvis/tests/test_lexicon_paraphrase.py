"""Lexicon paraphrase layer: concepts and shapes, with new constructions (not Blind-11 sentences).

Each family is tested with several different wordings of the same intent, spelling noise, and a negative control that
must NOT be rewritten (a message, a name, an app, a scheduled command, a different tool).
"""
from __future__ import annotations

import pytest

from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.router.lexicon_rewrite import global_repair, precise, repair
from jarvis.core.router.models import RouteLane
from jarvis.core.router.paraphrase import settings_command, words_to_int
from jarvis.core.router.router import SmartRouter


async def _route(text: str):
    return await SmartRouter().route(CommandRequest(text=text))


# ------------------------------------------------------------------------------------------------ numbers and levels
@pytest.mark.parametrize("words,n", [("twenty five", 25), ("fourty", 40), ("one fifty", 150), ("a quarter", 25), ("seventy", 70),
                                     ("hundred", 100), ("three quarters", 75), ("7", 7), ("nine", 9)])
def test_number_words(words, n):
    assert words_to_int(words) == n


@pytest.mark.parametrize("text,expected", [
    ("pump the sound all the way up", "set volume to 100"),
    ("set the volum to sixty", "set volume to 60"),
    ("bring the brightness down to a quarter", "set brightness to 25"),
    ("brightness at eighty percent", "set brightness to 80"),
    ("dim the screen to about thirty", "set brightness to 30"),
    ("volume to the minimum", "set volume to 0"),
])
def test_level_commands_are_understood_by_meaning(text, expected):
    assert settings_command(text) == expected


@pytest.mark.parametrize("text", [
    "at 6 pm set the volume to 20",             # scheduled: the scheduler's, not an immediate level change
    "open spotify and set volume to 40",         # part of a plan
    "tell ravi the volume is at 50",             # the owner's words
    "speak up",                                  # JARVIS's own voice
])
def test_level_rewrite_never_fires_on_scheduled_compound_or_spoken_content(text):
    assert settings_command(text) is None


# ------------------------------------------------------------------------------------------------ spelling repair
@pytest.mark.parametrize("text,expected", [
    ("opn the blutooth settings", "open the bluetooth settings"),
    ("refersh the pag", "refresh the page"),
    ("clipbord histry", "clipboard history"),
    ("extrct the audio frm it", "extract the audio from it"),
])
def test_command_words_are_repaired_but_ordinary_english_is_not(text, expected):
    assert global_repair(text) == expected


def test_repair_leaves_names_and_plain_words_alone():
    assert global_repair("open krita and meet divya") == "open krita and meet divya"
    assert repair("the screen is bright") == "the screen is bright"


# ------------------------------------------------------------------------------------------------ routed end to end
@pytest.mark.asyncio
@pytest.mark.parametrize("text,intent", [
    ("lock this computer up", "system_power_control"),
    ("how long until my laptop dies", "battery_status"),
    ("grab a screen shot", "take_screenshot"),
    ("fone wifi on", "android_toggle"),
    ("kill the phone's bluetooth", "android_toggle"),
    ("ring up my cousin Meera", "android_dial"),
    ("what's sitting on my clipboard", "clipboard_op"),
    ("make the page text bigger", "browser_quick_action"),
    ("bring back the tab I closed by mistake", "browser_quick_action"),
    ("did meera message me today", "read_whatsapp_messages"),
    ("how many unread emails do I have", "gmail_list_recent"),
    ("what's left on my to-do list", "todo"),
    ("which reminders are still pending", "list_reminders"),
    ("what tables are in the gamma database", "database_schema_read"),
    ("show the frontend logs for delta", "project_logs"),
    ("switch this call to speaker", "phone_op"),
    ("go with the female voice from now on", "set_voice"),
])
async def test_paraphrases_reach_the_right_capability(text, intent):
    d = await _route(text)
    assert d.intent == intent, (text, d.lane, d.intent, d.slots)


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [
    "shut docker desktop",                    # an app, not the computer
    "open task manager then close telegram",  # a plan, not a to-do list
    "move focus to the next field",           # UI focus, not a file move or a study mode
    "text divya that the meeting is at 4",    # a message, not a calendar query
])
async def test_loose_words_do_not_trigger_unrelated_rewrites(text):
    assert precise(text) is None, (text, precise(text))


@pytest.mark.asyncio
async def test_pronoun_only_commands_with_nothing_to_refer_to_ask_instead_of_guessing():
    for text in ("rename it", "turn that off", "put that file in the other folder"):
        d = await SmartRouter().route(CommandRequest(text=text))
        assert d.lane in (RouteLane.CLARIFY, RouteLane.LANE_0) and (d.lane == RouteLane.CLARIFY or d.intent not in ("rename_file", "move_file")), (text, d.lane, d.intent)


# ------------------------------------------------------------------------------------------------ over-repair guards
@pytest.mark.parametrize("text", ["check that the file really got deleted", "tidy up my downloads", "the files were moved yesterday"])
def test_real_inflections_and_ordinary_words_are_not_spelling_repaired(text):
    assert global_repair(text) == text


@pytest.mark.asyncio
@pytest.mark.parametrize("text,intent", [
    ("can you copy the path of this file", "file_op"),          # "path" is also a Tamil word; the English imperative decides
    ("could you please copy the path of this file", "file_op"),
    ("tidy up my downloads", "organize_downloads"),
])
async def test_english_commands_with_tamil_lookalike_words_are_commands(text, intent):
    d = await _route(text)
    assert d.intent == intent, (text, d.lane, d.intent)


@pytest.mark.parametrize("text", [
    "go back 15 seconds", "take me back to my editor", "let's talk about CUDA, now go back to ollama",   # not a browser back
    "close this file tab", "close the other tab", "open this result in a new tab",
    "attach the current screenshot", "remove the screenshot attachment", "show me the screenshot I just took", "trash the old screenshot",
    "how do screenshots work", "refresh yoga's style profile from my approved chat history",
    "call me back", "call me later", "phone volume up", "ring my phone",
    "cut audio from 01:00 for 45 seconds", "volume 101", "volume 1.5", "bump up the call volume",
    "in 2 hours turn off wifi on my phone", "turn off bluetooth on the laptop, keep the phone's on", "connect to my phone over wifi",
    "need a fresh password for my new gmail account", "create an event from the time in that email", "tomorrow at 5 pm to my calendar",
    "duplicate the todo list on my desktop", "what task is running", "what does cancelling a task do",
    "save a summary of this chat to notes", "summarize that message", "can you remember things between sessions?",
    "keep voice responsive while a heavy rag task runs", "put this download into my project folder",
])
def test_rewrite_never_fires_on_look_alike_requests(text):
    assert precise(text) is None, (text, precise(text))
