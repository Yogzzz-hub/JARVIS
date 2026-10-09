"""WhatsApp personal replies: chat history in many formats, per-person texting habits (emoji, laugh, shorthand,
bursts), Tanglish understanding, and instant replies that skip the model."""
from __future__ import annotations

import asyncio
import io
import json
import zipfile

import pytest

from jarvis.integrations.whatsapp.personal_reply import importer as imp
from jarvis.integrations.whatsapp.personal_reply.feed import parse_any
from jarvis.integrations.whatsapp.personal_reply.models import Authorship, ChatLine, ContactStyleProfile, Direction
from jarvis.integrations.whatsapp.personal_reply.reply_generator import apply_habits
from jarvis.integrations.whatsapp.personal_reply.style_analyzer import analyze
from jarvis.integrations.whatsapp.personal_reply.tanglish_gloss import gloss
from jarvis.integrations.whatsapp.personal_reply.understand import understand
from tests.whatsapp_personal.harness import deliver, make_agent, msg, sends_to

ARUN = "919876543210@s.whatsapp.net"
ANDROID = "12/05/24, 9:41 pm - Arun: saptiya da?\n12/05/24, 9:42 pm - Yoga: aama da 😂\n12/05/24, 9:43 pm - Arun: seri\n"


def _only(chats):
    assert len(chats) == 1
    return chats[0]


# ------------------------------------------------------------------ formats
def test_whatsapp_txt_zip_and_web_copy():
    assert _only(parse_any(ANDROID, "WhatsApp Chat with Arun.txt", owner_names=["Yoga"])).contact_hint == "Arun"
    z = io.BytesIO()
    zipfile.ZipFile(z, "w").writestr("_chat.txt", ANDROID)
    fc = _only(parse_any(z.getvalue(), "WhatsApp Chat - Arun.zip", owner_names=["Yoga"]))
    assert fc.source_format == "whatsapp_export" and [ln.text for ln in fc.chat.user_messages] == ["aama da 😂"]
    web = "[9:41 pm, 12/05/2024] Arun: varuviya?\n[9:42 pm, 12/05/2024] Yoga: varen da 👍\n"
    fc = _only(parse_any(web, owner_names=["Yoga"]))
    assert fc.source_format == "whatsapp_web_copy" and fc.chat.user_messages[0].text == "varen da 👍"
    ios24 = "[12/05/24, 21:41:23] Arun: saptiya?\n[12/05/24, 21:42:01] Yoga: s da 😂😂\n"
    assert _only(parse_any(ios24, owner_names=["Yoga"])).chat.contact_name == "Arun"


def test_json_formats():
    tg = {"name": "Arun", "type": "personal_chat", "messages": [
        {"type": "message", "from": "Arun", "date": "2024-05-12T21:41:00", "text": "enna panra"},
        {"type": "message", "from": "Yoga", "date": "2024-05-12T21:42:00", "text": ["summa da ", {"type": "bold", "text": "nee?"}]}]}
    fc = _only(parse_any(json.dumps(tg), "result.json", owner_names=["Yoga"]))
    assert fc.source_format == "telegram" and fc.chat.user_messages[0].text == "summa da nee?"
    ig = {"participants": [{"name": "Arun"}, {"name": "Yoga"}], "messages": [
        {"sender_name": "Yoga", "content": "haha ð\u009f\u0098\u0082", "timestamp_ms": 1715530000000},
        {"sender_name": "Arun", "content": "lol", "timestamp_ms": 1715529990000}]}
    fc = _only(parse_any(json.dumps(ig), "message_1.json", owner_names=["Yoga"]))
    assert fc.source_format == "instagram" and fc.chat.user_messages[0].text == "haha 😂"  # mojibake repaired
    exporter = {ARUN: {"name": "Arun", "messages": {"1": {"from_me": False, "timestamp": 1715529990, "data": "gm"},
                                                    "2": {"from_me": True, "timestamp": 1715530000, "data": "gm da ☀️"}}},
                "120363000000000001@g.us": {"name": "CSE", "messages": {"1": {"from_me": False, "timestamp": 1, "data": "x"}}}}
    fc = _only(parse_any(json.dumps(exporter)))  # the group chat is skipped
    assert fc.contact_hint == ARUN and fc.chat.user_messages[0].text == "gm da ☀️"
    generic = [{"from": "Arun", "text": "free ah?", "timestamp": 1715529990},
               {"from": "Me", "text": "busy da", "timestamp": 1715530000, "from_me": True}]
    assert _only(parse_any(json.dumps(generic))).chat.user_messages[0].text == "busy da"


def test_csv_and_plain_transcript():
    csv_text = "time,sender,message,from_me\n2024-05-12 21:41:00,Arun,call pannu,0\n2024-05-12 21:42:00,Yoga,5 min la,1\n"
    fc = _only(parse_any(csv_text, "arun.csv"))
    assert fc.source_format == "csv" and fc.chat.user_messages[0].text == "5 min la"
    fc = _only(parse_any("Arun: dinner ku vaa\nMe: seri da varen 😋\nArun: 8 ku\nMe: ok\n", "Arun.txt"))
    assert fc.source_format == "transcript" and [ln.text for ln in fc.chat.user_messages] == ["seri da varen 😋", "ok"]


def test_group_chats_are_refused_in_every_format():
    tg_group = {"name": "CSE", "type": "private_group", "messages": [{"type": "message", "from": "A", "text": "x"}]}
    ig_group = {"participants": [{"name": "A"}, {"name": "B"}, {"name": "C"}], "messages": [{"sender_name": "A", "content": "x"}]}
    for data in (json.dumps(tg_group), json.dumps(ig_group),
                 "12/05/24, 9:41 pm - A: hi\n12/05/24, 9:42 pm - B: hi\n12/05/24, 9:43 pm - C: hi\n"):
        with pytest.raises(imp.ImportError_, match="group"):
            parse_any(data, owner_names=["A"])


def test_import_file_and_feed_folder(tmp_path):
    agent = make_agent(tmp_path)
    exporter = {ARUN: {"name": "Arun", "messages": {str(i): {"from_me": i % 2 == 1, "timestamp": 1715529990 + i * 60,
                                                             "data": "gm" if i % 2 == 0 else "gm da ☀️"} for i in range(20)}}}
    res = agent.import_file(json.dumps(exporter), "result.json")
    assert res[0]["status"] == "IMPORTED" and agent.store.source_count(ARUN)["USER"] == 10
    assert agent.store.load_profile(ARUN).messages_analyzed > 0
    unknown = ANDROID.replace("Arun", "Zara")
    assert agent.import_file(unknown, "chat.txt", owner_name="Yoga")[0]["status"] == "NEEDS_CONTACT"  # never a guess

    agent.store.upsert_contact("919000000001@s.whatsapp.net", "Priya")
    feed = tmp_path / "feed"
    (feed / "Priya").mkdir(parents=True)
    (feed / "Priya" / "chat.txt").write_text(
        "12/05/24, 9:41 pm - Priya: coming?\n12/05/24, 9:42 pm - Me: yes, 5 mins\n", encoding="utf-8")
    out = agent.import_feed_folder(feed)
    assert [r["name"] for r in out["imported"]] == ["Priya"] and "Priya" in out["message"]
    assert agent.store.load_profile("919000000001@s.whatsapp.net") is not None
    assert agent.import_feed_folder(feed)["imported"] == []  # each file once


# ------------------------------------------------------------------ texting habits
def _lines(texts, gap=3600.0):
    out, t = [], 1_700_000_000.0
    for group in texts:
        for j, text in enumerate(group if isinstance(group, list) else [group]):
            out.append(ChatLine(timestamp=t + j * 20, sender="me", direction=Direction.USER, text=text,
                                provenance=Authorship.USER_TYPED, provenance_confidence=1.0))
        t += gap
    return out


def test_habits_are_learned_per_person():
    prof = analyze("c", "Arun", _lines(["hahaha semma da 😂😂", "u coming tmrw da?", "sooo tired da 😂😂",
                                        ["ok da", "wait 5 min"], "hahaha u r mad 😂😂", ["reached", "call u later da"],
                                        "tmrw sure da 👍", "hahaha 😂😂"]))
    assert prof.emoji_vocab[0] == "😂" and prof.emoji_run == 2 and prof.emoji_position == "end"
    assert prof.laugh_style == "hahaha" and "da" in prof.address_terms
    assert prof.shorthand.get("you") == "u" and prof.shorthand.get("tomorrow") == "tmrw"
    assert prof.burst_rate >= 0.2 and "sooo" in prof.elongation_examples


def test_draft_is_rewritten_in_the_owners_habits():
    prof = ContactStyleProfile(contact_id="c", messages_analyzed=40, emoji_frequency=0.8, emoji_vocab=["😂", "👍", "❤️"],
                               emoji_run=2, laugh_style="hahaha", shorthand={"you": "u", "tomorrow": "tmrw"}, burst_rate=0.0)
    assert apply_habits("lol see you tomorrow 😆", prof) == "hahaha see u tmrw 😂😂"
    assert apply_habits("so sorry 😢", prof).strip() == "so sorry"  # no sad emoji of theirs: dropped, never 😂
    assert apply_habits("ok\nwill call", prof) == "ok will call"  # they send one message
    prof.burst_rate = 0.6
    assert apply_habits("Reached home. Will call you.", prof) == "Reached home.\nWill call u."


# ------------------------------------------------------------------ understanding
def test_tanglish_understanding():
    assert understand("saptiya da", use_jde=False).intent == "QUESTION"
    assert understand("naalaiku varuviya?", use_jde=False).intent == "QUESTION"
    assert understand("seri da", use_jde=False).intent == "ACK"
    assert understand("resume ah anuppu da", use_jde=False).requests_pc_action  # files always wait for the owner
    assert "varuviya = will you come?" in gloss("naalaiku varuviya?") and "naalaiku = tomorrow" in gloss("naalaiku varuviya?")


def test_meaning_hints_reach_the_model_prompt():
    from jarvis.integrations.whatsapp.personal_reply.context_builder import build
    ctx = build("c", "Arun", ContactStyleProfile(contact_id="c"), [], [], ["naalaiku varuviya?"])
    assert "MEANING_HINTS" in ctx.user and "will you come?" in ctx.user
    assert "MEANING_HINTS" not in build("c", "Arun", ContactStyleProfile(contact_id="c"), [], [], ["see you at 5"]).user


# ------------------------------------------------------------------ speed + sending
def _history(pairs, start=1715500000):
    lines = []
    for i, (them, me) in enumerate(pairs):
        t = start + i * 7200
        lines.append(f"[{_d(t)}] Arun: {them}")
        for j, part in enumerate(me if isinstance(me, list) else [me]):
            lines.append(f"[{_d(t + 30 + j * 20)}] Me: {part}")
    return "\n".join(lines) + "\n"


def _d(ts):
    from datetime import datetime
    return datetime.fromtimestamp(ts).strftime("%d/%m/%y, %H:%M:%S")


def test_greetings_get_the_owners_own_reply_instantly(tmp_path):
    class NoModel:
        async def chat_json(self, *a, **k):
            raise AssertionError("a greeting the owner always answers the same way needs no model")

    agent = make_agent(tmp_path, llm=NoModel())
    agent.import_chat(ARUN, "Arun", export_text=_history([("gm", "gm da ☀️")] * 12 + [("ok", "👍")] * 12))

    async def run():
        return await agent.draft(ARUN, ["gm"])
    d = asyncio.run(run())
    assert d["candidate"].generator == "instant" and d["candidate"].text == "gm da ☀️"


def test_bursty_texter_gets_several_short_messages_and_echoes_are_not_learned(tmp_path):
    agent = make_agent(tmp_path)
    pairs = [(f"where are you {i}", ["reached office", "will call later"]) for i in range(30)]
    agent.import_chat(ARUN, "Arun", export_text=_history(pairs))
    agent.burst_gap_s = 0
    assert agent.store.load_profile(ARUN).burst_rate >= 0.9
    assert agent._message_parts(ARUN, "reached office\nwill call later") == ["reached office", "will call later"]

    async def run():
        agent.enable([ARUN], agent.clock() + 3600)
        return await deliver(agent, msg(ARUN, "where are you now", "Arun"))
    out = asyncio.run(run())
    assert out["status"] == "NEEDS_USER_REVIEW"
    # Provisional export history cannot authorize a generated live send.
    assert sends_to(agent, ARUN) == []
    for part in [m["text"] for m in sends_to(agent, ARUN)]:
        echo = agent.learn_owner_message(msg(ARUN, part, "Me", from_me=True))
        assert echo.get("learned") is not True  # JARVIS's own messages never train the owner's style


# ------------------------------------------------------------------ commands
def test_learn_chats_command_routing():
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter
    r = SmartRouter(llm_provider=DisabledProvider())
    for text, intent in [("learn my whatsapp chats", "whatsapp_learn_chats"), ("import my chat exports", "whatsapp_learn_chats"),
                         ("chats ellam learn pannu", "whatsapp_learn_chats"), ("summarize my chats", "summarize_whatsapp_messages"),
                         ("read my chats", "read_whatsapp_messages"), ("any new chats", "summarize_whatsapp_messages")]:
        assert asyncio.run(r.route(text)).intent == intent, text
