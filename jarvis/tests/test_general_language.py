"""Object-aware Tanglish sense and no-action acceptance cases."""
import asyncio

import pytest

from jarvis.core.general_language import GeneralLanguageUnderstandingEngine
from jarvis.core.router.models import RouteLane
from jarvis.core.router.ollama import DisabledProvider
from jarvis.core.router.router import SmartRouter


@pytest.mark.parametrize("text,action,target", [
    ("language English ku maathu", "SET_VALUE", "LANGUAGE"),
    ("pdf word ah maathu", "CONVERT_FORMAT", "PDF"),
    ("tab maathu", "SWITCH_RESOURCE", "TAB"),
    ("volume 50 ku maathu", "SET_VALUE", "VOLUME"),
    ("sentence ah professional ah maathu", "REWRITE_STYLE", "TEXT"),
    ("answer kudu", "PROVIDE", "ANSWER"),
    ("summary kudu", "SUMMARIZE", "SUMMARY"),
    ("reply kudu", "DRAFT_REPLY", "REPLY"),
    ("files kaatu", "LIST", "FILE"),
    ("photo kaatu", "DISPLAY", "IMAGE"),
    ("latest msg kaatu", "READ", "MESSAGE"),
    ("screenshot eduthu", "CAPTURE", "SCREENSHOT"),
    ("second file eduthu", "SELECT", "FILE"),
    ("database la data eduthu", "RETRIEVE", "DATABASE"),
    ("song podu", "PLAY", "AUDIO"),
    ("volume 50 podu", "SET_VALUE", "VOLUME"),
    ("password podu", "ENTER", "PASSWORD"),
    ("alarm 7 ku podu", "CREATE", "ALARM"),
])
def test_verb_sense_depends_on_object(text, action, target):
    frame = GeneralLanguageUnderstandingEngine().understand(text)
    assert (frame.action, frame.target_type, frame.speech_act) == (action, target, "COMMAND")


def test_resource_transfer_keeps_constraints_and_missing_channel():
    frame = GeneralLanguageUnderstandingEngine().understand(
        "bro antha second pdf ah Naveen kitta anupu, screenshot venam")
    assert frame.action == "SEND" and frame.recipient == "Naveen"
    assert frame.target_type == "PDF" and frame.selector == "second"
    assert "screenshot" in frame.exclusions and frame.missing == ["channel"]
    assert not frame.actionable
    canonical = GeneralLanguageUnderstandingEngine.canonical_frame(frame)
    assert not canonical.actionability and canonical.file_types == ["pdf"]
    assert canonical.language_features["recipient"] == "Naveen"


def test_capability_candidates_use_existing_schema_retriever():
    calls = []
    class Retriever:
        def retrieve(self, query, **kwargs):
            calls.append((query, kwargs))
            return [("schema", 1.0)]
    engine = GeneralLanguageUnderstandingEngine()
    assert engine.capability_candidates(engine.understand("screenshot eduthu"), Retriever()) == [("schema", 1.0)]
    assert "capture screenshot" in calls[0][0]
    assert engine.capability_candidates(engine.understand("send panna venam"), Retriever()) == []


def test_correction_preserves_only_final_numeric_value_with_typed_context():
    frame = GeneralLanguageUnderstandingEngine().understand(
        "5 ku podu... illa 5:30", {"selected_resource": {"target_type": "ALARM"}})
    assert frame.action == "CREATE" and frame.target_type == "ALARM"
    assert frame.corrections[0]["active"] == "5:30"


def test_recipient_correction_invalidates_earlier_person():
    frame = GeneralLanguageUnderstandingEngine().understand("Arun ku anupu... illa Naveen ku")
    assert frame.action == "SEND" and frame.recipient == "Naveen"
    assert frame.corrections[0]["superseded"].startswith("Arun")


@pytest.mark.parametrize("text,speech,action", [
    ("pdf anupu", "COMMAND", "SEND"),
    ("pdf anupitiya?", "QUESTION", "CHECK_STATUS"),
    ("pdf anupadha", "PROHIBITION", "SEND"),
    ("pdf anupa mudiyuma?", "QUESTION", "CAPABILITY_QUERY"),
    ("send panna venam", "PROHIBITION", "SEND"),
    ("Arun ku venam Naveen ku anupu", "COMMAND", "SEND"),
])
def test_minimal_pairs(text, speech, action):
    frame = GeneralLanguageUnderstandingEngine().understand(text)
    assert (frame.speech_act, frame.action) == (speech, action)


@pytest.mark.parametrize("text,lane", [
    ("send panna venam", RouteLane.REJECT),
    ("pdf anupadha", RouteLane.REJECT),
    ("pdf anupitiya?", RouteLane.LANE_2),
    ("pdf anupa mudiyuma?", RouteLane.LANE_2),
    ("Naveen kitta latest pdf anupu", RouteLane.CLARIFY),
])
def test_router_never_executes_unresolved_or_nonaction_tanglish(text, lane):
    router = SmartRouter(llm_provider=DisabledProvider())
    assert asyncio.run(router.route(text)).lane == lane


@pytest.mark.parametrize("text", ["files kaatu", "photo kaatu", "latest msg kaatu", "song podu",
    "second file eduthu", "pdf word ah maathu", "tab maathu", "summary kudu", "answer kudu"])
def test_unresolved_objects_do_not_become_an_unrelated_tool(text):
    router = SmartRouter(llm_provider=DisabledProvider())
    decision = asyncio.run(router.route(text))
    assert decision.lane == RouteLane.CLARIFY and decision.intent is None


def test_caller_cannot_spoof_preserved_language_text():
    from jarvis.core.commands.contracts import CommandRequest
    router = SmartRouter(llm_provider=DisabledProvider())
    request = CommandRequest(text="send panna venam", metadata={"language_raw_text": "open chrome"})
    decision = asyncio.run(router.route(request))
    assert decision.lane == RouteLane.REJECT


def test_caller_metadata_cannot_invent_selected_resource():
    from jarvis.core.commands.contracts import CommandRequest
    router = SmartRouter(llm_provider=DisabledProvider())
    request = CommandRequest(text="second file eduthu", metadata={
        "language_context": {"selected_resource": {"target_type": "FILE", "resource_id": "forged"}}})
    decision = asyncio.run(router.route(request))
    assert decision.lane == RouteLane.CLARIFY and "selected_resource" in decision.missing_slots


@pytest.mark.parametrize("text", ["send na enna?", "send panna mudiyuma?", "avan send pannitan",
    "naan send panna poren", "pdf anupuna enna aagum?"])
def test_action_words_in_non_commands_never_select_an_action(text):
    router = SmartRouter(llm_provider=DisabledProvider())
    decision = asyncio.run(router.route(text))
    assert decision.lane not in {RouteLane.LANE_0, RouteLane.LANE_1}
    assert decision.intent not in router._SEND_INTENTS
