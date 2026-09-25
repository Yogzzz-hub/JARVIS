"""Unit tests for Dynamic Capability RAG and Natural Language Routing."""

import pytest
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.router.router import SmartRouter
from jarvis.core.router.models import RouteLane
from jarvis.core.capabilities.context import CapabilityContextBuilder
from jarvis.core.capabilities.registry import get_default_capability_registry
from jarvis.core.capabilities.retrieval import CapabilityRetriever


@pytest.fixture
def router():
    return SmartRouter()


@pytest.mark.asyncio
async def test_say_hi_to_yoga_in_whatsapp(router):
    decision = await router.route(CommandRequest(text="say hi to yoga in whatsapp"))
    assert decision.lane == RouteLane.LANE_0
    assert decision.intent == "send_whatsapp_message"
    assert decision.slots.get("recipient", "").lower() == "yoga"
    assert decision.slots.get("message", "").lower() == "hi"


@pytest.mark.asyncio
async def test_say_hi_to_yoga(router):
    decision = await router.route(CommandRequest(text="say hi to yoga"))
    assert decision.lane == RouteLane.LANE_0
    assert decision.intent == "send_whatsapp_message"
    assert decision.slots.get("recipient", "").lower() == "yoga"
    assert decision.slots.get("message", "").lower() == "hi"


@pytest.mark.asyncio
async def test_tell_yoga_hi(router):
    decision = await router.route(CommandRequest(text="tell yoga hi"))
    assert decision.lane == RouteLane.LANE_0
    assert decision.intent == "send_whatsapp_message"
    assert decision.slots.get("recipient", "").lower() == "yoga"
    assert decision.slots.get("message", "").lower() == "hi"


@pytest.mark.asyncio
async def test_phone_screen_mirror_routing(router):
    decision = await router.route(CommandRequest(text="show my phone screen"))
    assert decision.lane == RouteLane.LANE_0
    assert decision.intent == "android_open_control"


@pytest.mark.asyncio
async def test_phone_status_routing(router):
    decision = await router.route(CommandRequest(text="is my phone connected"))
    assert decision.lane == RouteLane.LANE_0
    assert decision.intent == "android_status"


def test_capability_context_builder_overview():
    summary = CapabilityContextBuilder.build_connected_overview()
    assert "WHATSAPP" in summary
    assert "GOOGLE AUTOMATIONS" in summary
    assert "ANDROID PHONE" in summary
    assert "WINDOWS APPLICATIONS" in summary
    assert "SYSTEM HARDWARE" in summary


def test_capability_rag_retrieval():
    reg = get_default_capability_registry()
    retriever = CapabilityRetriever(reg)
    rag_text = CapabilityContextBuilder.retrieve_relevant_context("say hi to yoga in whatsapp", retriever=retriever)
    assert "whatsapp" in rag_text.lower()
    assert "send_whatsapp_message" in rag_text
