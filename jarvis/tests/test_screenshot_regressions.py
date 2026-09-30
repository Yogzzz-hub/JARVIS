"""Regressions for natural requests being mistaken for application launches."""
import pytest

from jarvis.core.router.ollama import DisabledProvider
from jarvis.core.router.router import SmartRouter
from jarvis.tools.system.app_resolver import AppResolver, LaunchTarget


@pytest.fixture
def resolver():
    resolver = AppResolver(auto_build=False)
    resolver.cache = {"chrome": LaunchTarget("chrome.exe", ("chrome.exe",)),
                      "whatsapp": LaunchTarget("https://web.whatsapp.com", (), True)}
    return resolver


@pytest.mark.parametrize("text", ["login linkedin in chrome", "in whatsapp", "reply in whatsapp",
                                  "unrelated chrome request"])
def test_resolver_does_not_discard_command_words(resolver, text):
    with pytest.raises(ValueError):
        resolver.resolve(text)


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["open chrome and login linkedin", "login linkedin in chrome",
                                  "can u sign in to linkedin using chrome", "log into linkedin"])
async def test_login_is_one_browser_goal(resolver, text):
    decision = await SmartRouter(llm_provider=DisabledProvider(), app_resolver=resolver).route(text)
    assert decision.intent in ("web_task", "open_website")
    url = decision.slots.get("url") or decision.slots.get("start_url") or ""
    assert "linkedin.com" in url
    assert not decision.subcommands


@pytest.mark.asyncio
async def test_installation_boilerplate_is_not_a_package_name():
    decision = await SmartRouter(llm_provider=DisabledProvider()).route(
        "can u install cisco packet tracer and set up and do all installation?")
    assert decision.intent == "install_software"
    assert decision.slots["name"] == "cisco packet tracer"


@pytest.mark.parametrize("action", ["login linkedin", "install zoom", "reply to Rahul", "configure settings"])
def test_compound_actions_are_not_extra_app_names(action):
    from jarvis.core.router.catalog import IntentCatalog
    from jarvis.core.router.complexity import check_deterministic_compound
    decision = check_deterministic_compound(f"open chrome and {action}", IntentCatalog.get_default(), "test")
    assert decision is not None and decision.needs_planner
    assert not decision.subcommands


@pytest.mark.asyncio
async def test_typing_to_me_means_bulk_reply():
    decision = await SmartRouter(llm_provider=DisabledProvider()).route(
        "i am gng meeting can u hand and reply the guys who are typing to me is i am at work?")
    assert decision.intent == "reply_whatsapp_all"
    assert "i am at work" in decision.slots["message"]


@pytest.mark.asyncio
async def test_channel_fragment_never_launches_an_app(resolver):
    decision = await SmartRouter(llm_provider=DisabledProvider(), app_resolver=resolver).route("in whatsapp")
    assert decision.lane.value == "CLARIFY"


def test_identity_uses_exact_contacts_only(monkeypatch):
    from jarvis.core.llm.assistant import Assistant
    from jarvis.integrations.whatsapp import contact_resolver
    contacts = contact_resolver.ContactResolver([
        contact_resolver.ContactEntry(jid="test", display_name="Yoga"),
        contact_resolver.ContactEntry(jid="other", display_name="Yoga Teacher"),
    ])
    monkeypatch.setattr(contact_resolver, "ContactResolver", lambda: contacts)
    evidence = Assistant._contact_context("who is yoga?")
    assert len(evidence) == 1
    assert "Saved WhatsApp contact: Yoga." in evidence[0]["snippet"]
    assert not Assistant._contact_context("who is yog?")


def test_compound_summary_describes_the_actual_result():
    from jarvis.core.commands.service import CommandService
    assert CommandService._compound_result("open_app", {"name": "chrome"})["summary"] == "Chrome is open."
    result = CommandService._compound_result("install_software", {"message": "Already installed."})
    assert result["summary"] == "Already installed."
