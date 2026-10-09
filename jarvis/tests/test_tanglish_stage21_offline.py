from scripts.tanglish_stage21_policy import Decision, decide
from scripts.tanglish_stage21_slots import extract_slots


def test_negation_and_question_never_execute():
    for act in ("NEGATED_COMMAND", "QUESTION", "CAPABILITY_QUERY", "STATEMENT", "HYPOTHETICAL"):
        assert decide(act, confidence=1, frame_complete=True, policy_approved=True) == Decision.NO_ACTION


def test_correction_needs_pending_frame_and_policy():
    assert decide("CORRECTION", confidence=1, frame_complete=True, policy_approved=True) == Decision.CLARIFY
    assert decide("CORRECTION", confidence=1, frame_complete=True, pending_frame=True) == Decision.ESCALATE_TO_PLANNER
    assert decide("CORRECTION", confidence=1, frame_complete=True, pending_frame=True, policy_approved=True) == Decision.EXECUTE


def test_command_needs_complete_frame_and_policy():
    assert decide("COMMAND", confidence=.7, frame_complete=True, policy_approved=True) == Decision.ESCALATE_TO_SEMANTIC_MODEL
    assert decide("COMMAND", confidence=1, frame_complete=False, policy_approved=True) == Decision.ESCALATE_TO_PLANNER
    assert decide("COMMAND", confidence=1, frame_complete=True, policy_approved=True) == Decision.EXECUTE


def test_slot_correction_keeps_last_recipient():
    slots = extract_slots("pdf Arun ku illa Naveen ku anuppu")
    assert slots["recipient"] == "Naveen"
    assert slots["file_type"] == "pdf"


def test_context_reference_resolves_to_selected_resource():
    slots = extract_slots("atha Arun ku anuppu", ["pdf files kaatu", "second pdf select panninen"])
    assert slots["target"] == "context.selected_resource"
    assert slots["ordinal"] == "second"
