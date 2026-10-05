from copy import deepcopy

from dataclasses import replace
import random

from scripts.stage25_admit import admission_errors, audit_queue_errors, row_admission_errors, row_digest, split_families
from scripts.stage25_gold_data import PAIRS, affordance, build_row, validate_row
from scripts.stage25_generate import SCENARIOS, generate_scene, metalinguistic_rows, rebalanced_slot_rows, slot_coverage_rows, special_rows, typed_context_rows
from scripts.stage25_review import select_queue
from scripts.stage25_final_distribution import DOWNSTREAM, REGISTRY_GAP
from scripts.tanglish_stage24_ontology import ACTION_FAMILY


def test_seed_rows_have_valid_schema_and_shared_meaning():
    for pair in PAIRS:
        tanglish = build_row(pair, "TANGLISH")
        tamil = build_row(pair, "TAMIL")
        assert validate_row(tanglish) == []
        assert validate_row(tamil) == []
        for key in ("speech_act", "action_family", "action_concept", "object_type", "should_execute", "negations", "exclude_constraints"):
            assert tanglish["frame"][key] == tamil["frame"][key]
        assert [(s["slot"], s["value"]) for s in tanglish["frame"]["slots"]] == [(s["slot"], s["value"]) for s in tamil["frame"]["slots"]]


def test_affordance_rejects_nonsense_and_contextualizes_folder_run():
    assert affordance("INCREASE", "BrowserTabRef") == "INVALID"
    assert affordance("RUN", "FolderRef") == "CONTEXT_REQUIRED"
    assert affordance("RUN", "FolderRef", {"folder_has_project": True}) == "VALID"


def test_validator_rejects_broken_spans_and_negated_execution():
    row = build_row(PAIRS[0], "TANGLISH")
    row["frame"]["slots"][0]["end"] += 1
    assert "broken_span" in validate_row(row)
    row = build_row(PAIRS[1], "TANGLISH")
    row["frame"]["should_execute"] = True
    assert "unsafe_execution_label" in validate_row(row)


def test_unreviewed_candidates_cannot_be_admitted():
    row = build_row(PAIRS[0], "TANGLISH")
    errors = admission_errors([row], [])
    assert any("gold_rows_below" in e for e in errors)
    assert "unvalidated_or_low_quality" in errors


def test_equivalent_scripts_remain_in_one_split():
    rows = [build_row(pair, lang) for pair in PAIRS for lang in ("TANGLISH", "TAMIL")]
    split = split_families(rows)
    owner = {row["isolation_group"]: name for name, group in split.items() for row in group}
    for name, group in split.items():
        assert all(owner[row["isolation_group"]] == name for row in group)


def test_asr_positive_cannot_change_negation_or_recipient():
    row = build_row(PAIRS[0], "TANGLISH")
    clean = deepcopy(row["frame"])
    noisy = deepcopy(clean)
    noisy["slots"][0]["value"] = "Arun"
    row["asr_pair"] = {"clean_text": row["text"], "noisy_text": "Arun ku PDF anuppu", "clean_frame": clean, "noisy_frame": noisy, "meaning_preserved": True}
    assert "meaning_changing_asr_positive" in validate_row(row)


def test_historical_second_pdf_frame_preserves_all_constraints():
    pair = next(pair for pair in PAIRS if pair.family == "send_pdf_yesterday")
    for language in ("TANGLISH", "TAMIL"):
        frame = build_row(pair, language)["frame"]
        assert frame["action_concept"] == "SEND"
        assert frame["sender"] == {"type": "ContactRefCandidate", "name": "Naveen"}
        assert frame["recipient"] == {"type": "ContactRefCandidate", "name": "Arun"}
        assert frame["ordinal"] == 2
        assert frame["temporal"]["date"] == "yesterday"
        assert frame["exclude_constraints"] == ["screenshot"]
        assert frame["should_execute"] is True


def test_q2_validation_does_not_require_review_status():
    row = build_row(PAIRS[0], "TANGLISH")
    row["quality"] = "Q2"
    row["validation_status"] = "PASSED"
    assert row["review_status"] == "UNREVIEWED"
    assert row_admission_errors(row) == []


def test_new_scenario_generation_and_audit_sampler():
    rows = []
    for scene in SCENARIOS[:3]:
        for left, right, _ in generate_scene(replace(scene, quota=12), random.Random(25)):
            for row in (left, right):
                row["validation_status"] = "PASSED"
                assert validate_row(row) == []
                rows.append(row)
    queue = select_queue(rows, 20)
    assert len({r["id"] for r in queue}) == 20
    assert sum(r["language"] == "TAMIL" for r in queue) >= 6
    assert sum(r["language"] == "TANGLISH" for r in queue) >= 6


def test_special_speech_acts_include_nonaction_and_meta_control():
    rows = [row for left, right, _ in special_rows(random.Random(25)) for row in (left, right)]
    acts = {r["frame"]["speech_act"] for r in rows}
    assert {"CHAT", "QUESTION", "ACKNOWLEDGEMENT", "CONFIRMATION", "AMBIGUOUS", "META_CONTROL"} <= acts
    assert all(validate_row(row) == [] for row in rows)


def test_context_slot_has_no_fabricated_span():
    pair = next(pair for pair in PAIRS if pair.family == "send_pdf_context")
    row = build_row(pair, "TANGLISH")
    slot = next(s for s in row["frame"]["slots"] if s["slot"] == "selected_resource")
    assert slot["source"] == "CONTEXT"
    assert (slot["start"], slot["end"], slot["surface"]) == (None, None, None)
    assert validate_row(row) == []


def test_all_33_slots_have_explicit_coverage_probes():
    rows = [row for left, right, _ in slot_coverage_rows() for row in (left, right)]
    assert all(validate_row(row) == [] for row in rows)
    assert {"URL", "message_content", "date_range", "time_range", "include_constraint", "exclude_constraint", "selected_resource"} <= {slot["slot"] for row in rows for slot in row["frame"]["slots"]}


def test_review_digest_changes_with_semantic_frame():
    row = build_row(PAIRS[0], "TANGLISH")
    changed = deepcopy(row)
    changed["frame"]["recipient"]["name"] = "Arun"
    assert row_digest(row) != row_digest(changed)


def test_admission_rejects_audit_outside_pinned_queue(tmp_path):
    import hashlib
    import json

    rows = tmp_path / "rows.jsonl"
    queue = tmp_path / "queue.jsonl"
    manifest = tmp_path / "manifest.json"
    rows.write_text("candidate\n", encoding="utf-8")
    queue.write_text("".join(json.dumps({"row_id": str(i)}) + "\n" for i in range(750)), encoding="utf-8")
    manifest.write_text(json.dumps({"source_sha256": hashlib.sha256(rows.read_bytes()).hexdigest(), "queue_sha256": hashlib.sha256(queue.read_bytes()).hexdigest(), "rows": 750}), encoding="utf-8")
    assert audit_queue_errors(rows, queue, manifest, [{"row_id": "unselected"}]) == ["audit_contains_rows_outside_queue"]
    queue.write_text(queue.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert audit_queue_errors(rows, queue, manifest, []) == ["audit_queue_hash_mismatch"]


def test_rebalanced_context_keys_are_typed_and_grounded():
    pairs = typed_context_rows()
    assert len(pairs) == 500
    assert {r["frame"]["context_refs"][0] for pair in pairs for r in pair[:2]} == {"active_thread", "active_app", "current_project", "browser_tab", "previous_result"}
    assert all(validate_row(r) == [] for pair in pairs for r in pair[:2])
    assert all(slot["start"] is None for pair in pairs for r in pair[:2] for slot in r["frame"]["slots"] if slot["source"] == "CONTEXT")


def test_metalinguistic_action_mention_does_not_execute():
    source = generate_scene(SCENARIOS[0], random.Random(25))
    derived = metalinguistic_rows(source, count=1)
    assert {row["frame"]["speech_act"] for pair in derived for row in pair[:2]} == {"QUESTION", "HYPOTHETICAL"}
    assert all(not row["frame"]["should_execute"] and validate_row(row) == [] for pair in derived for row in pair[:2])


def test_ontology_decisions_cover_every_label_without_unknown_status():
    assert not (set(DOWNSTREAM) & set(REGISTRY_GAP))
    assert set(DOWNSTREAM) | set(REGISTRY_GAP) <= set(ACTION_FAMILY)
    assert len(set(ACTION_FAMILY) - set(DOWNSTREAM) - set(REGISTRY_GAP)) == 56
