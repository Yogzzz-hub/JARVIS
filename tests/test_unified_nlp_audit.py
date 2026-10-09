import copy
import json

import pytest

from scripts.stage25_admit import read_jsonl
from scripts.stage25_gold_data import OUT
from scripts.unified_nlp_audit import AuditStore, validate_precheck


@pytest.fixture
def store(tmp_path):
    queue = read_jsonl(OUT / "independent_audit_queue.jsonl")[:2]
    (tmp_path / "independent_audit_queue.jsonl").write_text(
        "".join(json.dumps(q) + "\n" for q in queue), encoding="utf-8")
    return AuditStore(tmp_path, check=lambda: [])


def payload(store, decision="APPROVE"):
    return {"sample_id": store.queue[0]["row_id"], "reviewer": "owner", "decision": decision}


def test_resume_and_ambiguity_resolution(store):
    store.save(payload(store, "AMBIGUOUS"))
    resumed = AuditStore(store.directory, check=lambda: [])
    assert resumed.status()["reviewed"] == 1
    assert not resumed.status()["admission_ready"]
    resumed.save(payload(resumed))
    assert resumed.status()["counts"]["AMBIGUOUS"] == 0
    assert len(read_jsonl(store.path)) == 2


def test_correction_preserves_original(store):
    item = copy.deepcopy(store.queue[0])
    corrected = copy.deepcopy(item["frame"])
    corrected["confidence"] = 0.8
    store.save({**payload(store, "FIX_LABEL"), "corrected_labels": corrected})
    record = store.latest()[item["row_id"]]
    assert record["original_labels"] == item["frame"]
    assert record["corrected_labels"] == corrected
    assert store.queue[0] == item
    with pytest.raises(ValueError):
        store.save({**payload(store), "text": "replacement"})
    with pytest.raises(ValueError):
        store.save({**payload(store, "FIX_LABEL"), "corrected_labels": {}})


def test_freeze_and_provenance_fail_closed(store):
    store.check = lambda: ["files"]
    with pytest.raises(ValueError):
        store.save(payload(store))
    store.check = lambda: []
    store.save(payload(store))
    records = read_jsonl(store.path)
    records[0]["row_sha256"] = "tampered"
    store.path.write_text(json.dumps(records[0]) + "\n")
    with pytest.raises(ValueError):
        store.latest()


def test_admission_excludes_reject_and_is_immutable(store):
    with pytest.raises(ValueError):
        store.admit()
    store.save(payload(store))
    store.save({**payload(store, "REJECT"), "sample_id": store.queue[1]["row_id"]})
    result = store.admit()
    assert result["admitted"] == 1
    assert store.admit() == result
    manifest = json.loads(__import__('pathlib').Path(result["manifest"]).read_text())
    assert manifest["admitted"][0]["row_id"] == store.queue[0]["row_id"]


def test_real_frozen_evidence_and_zero_admission():
    store = AuditStore()
    assert len(store.queue) == 750
    assert not store.status()["admission_ready"]


def precheck_rows(queue):
    return [{"row_id": q["row_id"], "text": q["text"], "language": q["language"],
             "original_frame": q["frame"], "suggested_status": "LIKELY_APPROVE",
             "confidence": "HIGH", "reason": "AI suggestion only"} for q in queue]


@pytest.mark.parametrize("change", ["duplicate", "text", "id", "frame", "status", "missing"])
def test_precheck_mismatch_refused(store, change):
    rows = copy.deepcopy(precheck_rows(store.queue))
    if change == "duplicate":
        rows[1] = rows[0]
    elif change == "missing":
        rows.pop()
    elif change == "frame":
        rows[0]["original_frame"]["should_execute"] = True
    else:
        rows[0][{"text": "text", "id": "row_id", "status": "suggested_status"}[change]] = "INVALID"
    with pytest.raises(ValueError):
        validate_precheck(rows, store.queue)
    assert not store.path.exists()


def test_import_auxiliary_does_not_approve(tmp_path):
    queue = read_jsonl(OUT / "independent_audit_queue.jsonl")
    queue_path = tmp_path / "independent_audit_queue.jsonl"
    queue_path.write_text("".join(json.dumps(q) + "\n" for q in queue))
    source = tmp_path / "input.jsonl"
    rows = precheck_rows(queue)
    rows[0]["suggested_status"] = "MANUAL_REVIEW"
    source.write_text("".join(json.dumps(r) + "\n" for r in rows))
    store = AuditStore(tmp_path, check=lambda: [])
    original = queue_path.read_bytes()
    store.import_precheck(source)
    assert store.status()["reviewed"] == 0
    assert store.status()["flagged_human_review"] == {"reviewed": 0, "total": 1}
    assert queue_path.read_bytes() == original
    assert not store.path.exists()
    with pytest.raises(ValueError):
        store.save({**payload(store), "decision": "LIKELY_APPROVE"})
    with pytest.raises(ValueError):
        store.admit()
    store.save(payload(store))
    assert store.status()["flagged_human_review"]["reviewed"] == 1


def test_malformed_nested_correction_is_validation_error(store):
    frame = copy.deepcopy(store.queue[0]["frame"])
    frame["slots"] = ["not a structured slot"]
    with pytest.raises(ValueError, match="Malformed structured annotation"):
        store.save({**payload(store, "FIX_LABEL"), "corrected_labels": frame})
    assert not store.path.exists()
