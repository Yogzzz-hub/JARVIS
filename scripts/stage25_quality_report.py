"""Reproducible Stage 2.5 candidate and audit-queue diagnostics."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict

from scripts.stage25_admit import read_jsonl, split_families
from scripts.stage25_gold_data import OUT, SLOTS, validate_row


def normalized(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(re.findall(r"[\w\u0b80-\u0bff]+", value))


def report() -> dict:
    rows_path = OUT / "stage25_candidates.jsonl"
    rejected_path = OUT / "stage25_rejected.jsonl"
    queue_path = OUT / "independent_audit_queue.jsonl"
    rows = read_jsonl(rows_path)
    rejected = read_jsonl(rejected_path)
    queue = read_jsonl(queue_path) if queue_path.exists() else []
    bad = Counter(reason for row in rows for reason in validate_row(row))
    text_keys = Counter((r["language"], normalized(r["text"]), json.dumps(r.get("working_context"), sort_keys=True, ensure_ascii=False)) for r in rows)
    frame_keys = Counter(json.dumps({"speech": r["frame"]["speech_act"], "action": r["frame"]["action_concept"], "object": r["frame"]["object_type"], "slots": [(s["slot"], s["value"]) for s in r["frame"]["slots"]], "context": r.get("working_context")}, sort_keys=True, ensure_ascii=False) for r in rows)
    structures = Counter(r["construction_family"] for r in rows)
    split = split_families(rows)
    split_families_set = {name: {r["isolation_group"] for r in members} for name, members in split.items()}
    family_leakage = sum(len(split_families_set[a] & split_families_set[b]) for a, b in (("train", "calibration"), ("train", "dev"), ("calibration", "dev")))
    slot_counts = Counter(s["slot"] for r in rows for s in r["frame"]["slots"])
    queue_ids = {r["row_id"] for r in queue}
    result = {
        "rows": len(rows), "source_sha256": hashlib.sha256(rows_path.read_bytes()).hexdigest(),
        "rejected_rows": len(rejected), "rejection_reasons": dict(Counter(reason for r in rejected for reason in r.get("reasons", []))),
        "validator_errors_in_candidates": dict(bad),
        "language": dict(Counter(r["language"] for r in rows)),
        "speech_act": dict(Counter(r["frame"]["speech_act"] for r in rows)),
        "action_family": dict(Counter(str(r["frame"]["action_family"]) for r in rows)),
        "action_concept": dict(Counter(str(r["frame"]["action_concept"]) for r in rows)),
        "slot_counts": dict(slot_counts), "supported_slot_names": sorted(slot_counts), "unsupported_slot_names": sorted(SLOTS - slot_counts.keys()),
        "distinct_semantic_frames": len(frame_keys), "normalized_text_context_duplicate_excess": sum(n - 1 for n in text_keys.values() if n > 1),
        "construction_families": len(structures), "largest_construction_family": structures.most_common(1),
        "top_10_construction_family_share": sum(n for _, n in structures.most_common(10)) / len(rows),
        "rows_in_families_over_250": sum(n for n in structures.values() if n > 250),
        "context_rows": sum(bool(r["frame"].get("context_required")) for r in rows),
        "asr_rows": sum(bool(r.get("asr_pair")) for r in rows),
        "cross_script_paired_families": sum(len({r["language"] for r in members}) == 2 for members in _group(rows).values()),
        "planned_family_split_rows": {name: len(members) for name, members in split.items()},
        "planned_family_leakage": family_leakage,
        "audit_queue_rows": len(queue), "audit_queue_sha256": hashlib.sha256(queue_path.read_bytes()).hexdigest() if queue else None,
        "audit_queue_language": dict(Counter(r["language"] for r in queue)),
        "audit_queue_all_ids_present": len(queue_ids) == len(queue) and queue_ids <= {r["id"] for r in rows},
        "audit_queue_asr": sum(bool(r.get("asr_pair")) for r in rows if r["id"] in queue_ids),
        "audit_queue_context": sum(bool(r["frame"].get("context_required")) for r in rows if r["id"] in queue_ids),
        "human_reviewed": 0,
    }
    (OUT / "stage25_quality_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def _group(rows: list[dict]) -> dict[str, list[dict]]:
    families = defaultdict(list)
    for row in rows:
        families[row["family"]].append(row)
    return families


if __name__ == "__main__":
    print(json.dumps(report(), ensure_ascii=True, indent=2))
