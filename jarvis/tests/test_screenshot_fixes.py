"""Regression tests for the reported conversation: contacts, installs, logins, bulk WhatsApp replies, follow-up
fragments, honest chat, and voice answers that must not be cut off by JARVIS's own echo."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from jarvis.core.router.ollama import DisabledProvider
from jarvis.core.router.router import SmartRouter


@pytest.fixture(scope="module")
def router():
    return SmartRouter(llm_provider=DisabledProvider())


def route(router, text):
    return asyncio.run(router.route(text))


def test_install_ignores_trailing_instructions_and_points_to_official_page(router):
    d = route(router, "can u install cisco packet tracer and set up and do all installation?")
    assert d.intent == "install_software" and d.slots == {"name": "cisco packet tracer"}
    from jarvis.tools.system.app_tools import manual_download
    name, url, why = manual_download("cisco packet tracer")
    assert name == "Cisco Packet Tracer" and "netacad.com" in url and "Networking Academy" in why


@pytest.mark.parametrize("text,browser", [("open chrome and login linkedin", "chrome"), ("login linkedin in chrome", "chrome"),
                                          ("sign in to my github account", None), ("log into linkedin", None)])
def test_login_opens_the_real_sign_in_page(router, text, browser):
    d = route(router, text)
    assert d.intent == "open_website" and "login" in d.slots["url"] and d.slots.get("browser") == browser


def test_sign_in_message_is_honest():
    from jarvis.tools.system.assistant_tools import OpenWebsiteTool
    out = OpenWebsiteTool(opener=lambda u: None).run({"url": "https://www.linkedin.com/login", "title": "Linkedin sign-in page"})
    assert "press Sign in" in out["message"]


def test_bulk_reply_to_people_typing_to_me(router):
    d = route(router, "i am gng meeting can u hand and reply the guys who are typing to me is i am at work?")
    assert d.intent == "reply_whatsapp_all" and d.slots["message"] == "i am at work"


def test_who_is_a_contact_uses_the_owners_data(router, monkeypatch):
    from jarvis.integrations.whatsapp import people
    monkeypatch.setattr(people, "known_names", lambda: {"yoga"})
    d = route(router, "who is yoga?")
    assert d.intent == "contact_info" and d.slots == {"name": "yoga"}
    assert route(router, "who is sundar pichai").intent != "contact_info"


def test_fragment_completes_the_previous_request():
    from jarvis.core.commands.service import CommandService
    svc = CommandService.__new__(CommandService)
    first = SimpleNamespace(text="reply to everyone who messaged me that I'm at work", model_copy=None)
    svc._expand_fragment(first)
    svc._last_user_text, svc._last_user_at = first.text, __import__("time").monotonic()

    class Req(SimpleNamespace):
        def model_copy(self, update):
            return Req(**{**self.__dict__, **update})
    out = svc._expand_fragment(Req(text="in whatsapp"))
    assert out.text == "reply to everyone who messaged me that I'm at work in whatsapp"
    assert svc._expand_fragment(Req(text="open chrome")).text == "open chrome"


def test_chat_never_claims_actions_it_did_not_do():
    from jarvis.core.llm.assistant import Assistant, HONEST_NO_ACTION, claims_action

    class Client:
        async def chat(self, *a, **k):
            return SimpleNamespace(text="I'll open a new tab in Chrome, navigate to LinkedIn, and log in using your credentials.",
                                   model="m")
    assert claims_action("I'll open a new tab") and not claims_action("You can open Settings and turn on dark mode.")
    reply = asyncio.run(Assistant(client=Client()).respond("can you handle my messages", use_web=False, use_knowledge=False))
    assert reply.text == HONEST_NO_ACTION


def test_factual_questions_use_live_web_grounding():
    from jarvis.core.llm.assistant import needs_live_data
    assert needs_live_data("who is sundar pichai") and needs_live_data("when did chandrayaan 3 land")
    assert not needs_live_data("what is recursion") and not needs_live_data("who is my manager")


def test_voice_follow_up_never_starts_while_jarvis_is_still_composing():
    from jarvis.core.audio.pipeline import VoicePipeline
    p = VoicePipeline.__new__(VoicePipeline)
    out = SimpleNamespace(is_playing=False, queue=[], last_playback_stop_ns=0)
    p.response_engine = SimpleNamespace(audio_output=out, _active_requests={"r1"}, _speech_tasks=set())
    assert p._assistant_speaking()  # next sentence still being synthesised
    p.response_engine = SimpleNamespace(audio_output=out, _active_requests=set(), _speech_tasks=set())
    assert not p._assistant_speaking()
