from scripts.tanglish_stage22_frame import RefCandidate, WorkingContext, extract_frame
from scripts.evaluate_tanglish_stage22 import command_negated, dev_partition, route


def test_tri_state_preserves_uncertainty():
    import numpy as np
    state = route(np.array([.02, .5, .98]), np.array([.5, .5, .5]), .1, .9, .1, .9)
    assert list(state) == ["NO_ACTION", "UNCERTAIN", "EXECUTE_CANDIDATE"]


def test_minimal_pair_family_stays_in_one_dev_partition():
    first = {"text":"pdf anuppu", "previous_turns":[], "pair_family":"dev:SEND:anupu:pdf:7"}
    second = {"text":"pdf anupadha", "previous_turns":[], "pair_family":"dev:SEND:anupu:pdf:7"}
    assert dev_partition(first) == dev_partition(second)


def test_full_action_negation_preserves_object_exclusion():
    assert command_negated("send panna venam")
    assert command_negated("don't submit the form")
    assert not command_negated("PDF mattum anuppu screenshot venam")
    assert not command_negated("Arun ku venam Naveen ku anuppu")


def test_correction_supersedes_recipient():
    frame = extract_frame("report.pdf Arun ku anuppu... illa Naveen ku", speech_act="CORRECTION", action_concept="SEND")
    assert frame.slots["recipient"].surface == "Naveen"
    assert frame.corrections == [{"slot": "recipient", "superseded": "Arun", "active": "Naveen"}]
    assert frame.slots["file"].surface == "report.pdf"


def test_context_reference_and_exclusion():
    context = WorkingContext(selected_resource=RefCandidate("FileRefCandidate", "report.pdf", "selected_resource"))
    frame = extract_frame("atha Naveen ku anuppu, PDF mattum screenshot venam", context,
                          speech_act="COMMAND", action_concept="SEND")
    assert frame.slots["selected_resource"] == context.selected_resource
    assert frame.slots["include_constraint"] == {"file_type": "PDF"}
    assert frame.slots["exclude_constraint"] == "screenshot"


def test_missing_reference_stays_unresolved():
    frame = extract_frame("atha Naveen ku anuppu", speech_act="COMMAND", action_concept="SEND")
    assert "selected_resource" in frame.unresolved


def test_numeric_and_app_correction():
    frame = extract_frame("volume 70... actually 40", action_concept="SET")
    assert frame.slots["quantity"] == 40
    assert frame.corrections[0]["superseded"] == "70"
    app = extract_frame("Chrome open pannu, sorry Edge", action_concept="OPEN")
    assert app.slots["application"].surface == "Edge"


def test_schema_contains_required_fields():
    from scripts.tanglish_stage22_frame import SLOT_SCHEMA
    assert {"recipient", "url", "date_range", "time_range", "include_constraint",
            "exclude_constraint", "selected_resource", "quoted_resource"} <= set(SLOT_SCHEMA)


def test_capability_ranking_separates_delivery_channels():
    from jarvis.core.capabilities.registry import CapabilityRegistry
    from jarvis.core.capabilities.retrieval import CapabilityRetriever
    from scripts.evaluate_tanglish_stage22_capabilities import CASES, rank
    registry = CapabilityRegistry()
    retriever = CapabilityRetriever(registry)
    for case in CASES:
        if case[-1] in {"whatsapp.send", "google.gmail_send"}:
            ranked, _ = rank(case, registry, retriever)
            assert ranked[0] == case[-1]
