"""English + Thanglish: Thanglish commands work, replies follow the owner's language, English is untouched."""
from __future__ import annotations

import asyncio

import pytest

from jarvis.core import multilingual as ml
from jarvis.core.router.ollama import DisabledProvider
from jarvis.core.router.router import SmartRouter


@pytest.fixture(autouse=True)
def _fresh_preference(tmp_path, monkeypatch):
    monkeypatch.setattr(ml, "_STATE", tmp_path / "language.json")


@pytest.fixture(scope="module")
def router():
    return SmartRouter(llm_provider=DisabledProvider())


@pytest.mark.parametrize("thanglish,english,intent", [
    ("chrome open pannu", "open chrome", "open_app"),
    ("Jarvis, notepad close pannu da", "close notepad", "close_app"),
    ("volume konjam kammi pannu", "volume down", "volume_down"),
    ("sound jaasthi pannu", "volume up", "volume_up"),
    ("volume 30 ku vai", "set volume to 30", "volume_set"),
    ("youtube la lofi music podu", "play lofi music on youtube", "play_youtube"),
    ("screenshot edu", "take a screenshot", "take_screenshot"),
    ("amma ku late aagum nu message anuppu", "send a message to amma saying late aagum", "send_whatsapp_message"),
    ("time enna", "what time is it", "get_time"),
    ("battery evlo iruku", "what's my battery", "battery_status"),
    ("pc lock pannu", "lock pc", "system_power_control"),
    ("mute pannu", "mute", "volume_mute"),
    ("google la ipl score thedu", "search google for ipl score", "open_website"),
    ("chrome la gmail open pannu", "open gmail", "open_app"),
    ("Hello World type pannu", "type Hello World", "dictate_text"),
])
def test_thanglish_commands_become_english_commands(router, thanglish, english, intent):
    assert ml.to_english_command(thanglish) == english
    assert asyncio.run(router.route(english)).intent == intent
    assert ml.reply_language(thanglish) == ml.THANGLISH


def test_message_keeps_the_owners_words_and_casing():
    assert ml.to_english_command("Arun kitta naan varala nu sollu") == "send a message to Arun saying naan varala"


@pytest.mark.parametrize("text", ["open chrome", "what is the capital of france", "open the edu portal",
                                  "set volume to 30", "send a message to arun saying ok", "take a screenshot"])
def test_english_is_never_rewritten_or_answered_in_thanglish(text):
    assert ml.to_english_command(text) == text
    assert ml.reply_language(text) == ml.ENGLISH


def test_benchmark_english_is_untouched():
    import glob
    import json
    for f in glob.glob("tests/generalization/*.jsonl"):
        for line in open(f, encoding="utf-8"):
            t = json.loads(line).get("input")
            if isinstance(t, str):
                assert ml.to_english_command(t) == t and ml.reply_language(t) == ml.ENGLISH, t


def test_language_switch_commands_and_preference(router):
    for text, mode in [("reply in thanglish", "thanglish"), ("Thanglish la pesu", "thanglish"),
                       ("english la pesu", "english"), ("talk to me in english", "english"), ("reply in my language", "auto")]:
        d = asyncio.run(router.route(text))
        assert d.intent == "set_reply_language" and d.slots == {"mode": mode}
    from jarvis.tools.system.language_tools import SetReplyLanguageTool
    out = SetReplyLanguageTool().run({"mode": "thanglish"})
    assert out["status"] == "SUCCESS" and "Thanglish" in out["message"]
    assert ml.reply_language("open chrome") == ml.THANGLISH  # pinned
    SetReplyLanguageTool().run({"mode": "auto"})
    assert ml.reply_language("open chrome") == ml.ENGLISH and ml.reply_language("chrome open pannu") == ml.THANGLISH


def test_confirmations_in_thanglish_and_other_text_unchanged():
    assert ml.in_thanglish("Chrome is open.") == "Chrome open panniten."
    assert ml.in_thanglish("Volume set to 30 percent.") == "Volume 30 percent ku vechiten."
    assert ml.in_thanglish("Playing lofi music on YouTube.") == "YouTube la lofi music play panren."
    assert ml.in_thanglish("Paris is the capital of France.") == "Paris is the capital of France."


def test_command_service_sets_language_and_rewrites(monkeypatch):
    from jarvis.core.commands.contracts import CommandRequest
    from jarvis.core.commands.service import CommandService

    svc = CommandService.__new__(CommandService)

    async def main(text):
        req = svc._language(CommandRequest(text=text))
        return req.text, ml.REPLY_LANGUAGE.get()
    assert asyncio.run(main("chrome open pannu")) == ("open chrome", ml.THANGLISH)
    assert asyncio.run(main("open chrome")) == ("open chrome", ml.ENGLISH)
    assert asyncio.run(main("english la pesu"))[1] == ml.ENGLISH  # the switch answers in the new language


def test_chat_is_told_to_answer_in_thanglish():
    from jarvis.core.llm.assistant import Assistant

    async def prompt(language):
        ml.REPLY_LANGUAGE.set(language)
        return Assistant(client=object()).system_prompt(speakable=True)
    assert "Thanglish" in asyncio.run(prompt(ml.THANGLISH))
    assert "Thanglish" not in asyncio.run(prompt(ml.ENGLISH))


def test_speech_recognition_uses_the_multilingual_model_for_thanglish():
    from jarvis.core.stt.faster_whisper_engine import FasterWhisperEngine
    th = FasterWhisperEngine(model="small.en", thanglish=True)
    assert th.model_name_str == "small" and "pannu" in th.initial_prompt
    assert FasterWhisperEngine(model="small.en").model_name_str == "small.en"
    assert th._fix_names("க்ரோம் ஓபன் பண்ணு") == "krom opan pannu"  # Tamil letters -> English letters


def test_tamil_script_romanisation():
    assert ml.tamil_to_latin("வணக்கம்") == "vanakkam"
    assert ml.has_tamil_script("சரி") and not ml.has_tamil_script("seri")
