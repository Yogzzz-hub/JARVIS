"""Fail-closed admission and family split for Stage 2.5 reviewed gold data."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from scripts.stage25_gold_data import OUT, validate_row

MIN_ROWS = 30_000
MIN_AUDIT = 750


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def row_digest(row: dict) -> str:
    payload = {key: row.get(key) for key in ("text", "language", "working_context", "frame")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def row_admission_errors(row: dict) -> list[str]:
    errors = []
    if row.get("quality") not in {"Q2", "Q3"} or row.get("validation_status") != "PASSED":
        errors.append("unvalidated_or_low_quality")
    errors.extend(validate_row(row))
    return errors


def admission_errors(rows: list[dict], audit: list[dict]) -> list[str]:
    errors = []
    if len(rows) < MIN_ROWS:
        errors.append(f"gold_rows_below_{MIN_ROWS}:{len(rows)}")
    if len(audit) < MIN_AUDIT:
        errors.append(f"audited_rows_below_{MIN_AUDIT}:{len(audit)}")
    if len({r["id"] for r in rows}) != len(rows):
        errors.append("duplicate_id")
    text_keys = [(r["language"], " ".join(r["text"].casefold().split()), json.dumps(r.get("working_context"), sort_keys=True, ensure_ascii=False)) for r in rows]
    if len(set(text_keys)) != len(text_keys):
        errors.append("duplicate_normalized_text")
    for row in rows:
        row_errors = row_admission_errors(row)
        if row_errors:
            errors.append("validator_failure" if any(reason != "unvalidated_or_low_quality" for reason in row_errors) else "unvalidated_or_low_quality")
            break
    row_ids = {r["id"] for r in rows}
    if len({a.get("row_id") for a in audit}) != len(audit) or any(a.get("row_id") not in row_ids for a in audit):
        errors.append("audit_ids_invalid")
    if any(a.get("reviewer") is None or a.get("reviewed_utc") is None for a in audit):
        errors.append("audit_provenance_missing")
    if any(a.get("decision") not in {"CORRECT", "INCORRECT", "NEEDS_EDIT"} for a in audit):
        errors.append("audit_decision_missing")
    if any((a.get("decision") != "CORRECT") != bool(a.get("annotation_error")) for a in audit):
        errors.append("audit_error_flag_inconsistent")
    if any(a.get("decision") != "CORRECT" and not a.get("error_categories") for a in audit):
        errors.append("audit_error_category_missing")
    by_id = {r["id"]: r for r in rows}
    if any(a.get("row_sha256") != row_digest(by_id[a["row_id"]]) for a in audit if a.get("row_id") in by_id):
        errors.append("audit_row_hash_mismatch")
    audited_rows = [by_id[a["row_id"]] for a in audit if a.get("row_id") in by_id]
    audited_language = Counter(r["language"] for r in audited_rows)
    if len(audit) >= MIN_AUDIT and (audited_language["TANGLISH"] < 300 or audited_language["TAMIL"] < 300):
        errors.append("audit_language_strata_missing")
    if len(audit) >= MIN_AUDIT:
        full_speech = {r["frame"]["speech_act"] for r in rows}
        audited_speech = {r["frame"]["speech_act"] for r in audited_rows}
        full_actions = {r["frame"]["action_concept"] for r in rows}
        audited_actions = {r["frame"]["action_concept"] for r in audited_rows}
        if full_speech - audited_speech or full_actions - audited_actions:
            errors.append("audit_semantic_strata_missing")
        if any(r.get("asr_pair") for r in rows) and not any(r.get("asr_pair") for r in audited_rows):
            errors.append("audit_asr_stratum_missing")
        audited_slots = {slot["slot"] for row in audited_rows for slot in row["frame"]["slots"]}
        full_slots = {slot["slot"] for row in rows for slot in row["frame"]["slots"]}
        if full_slots - audited_slots:
            errors.append("audit_slot_strata_missing")
        required_strata = {
            "correction": (40, lambda r: r["frame"]["speech_act"] == "CORRECTION"),
            "asr": (50, lambda r: bool(r.get("asr_pair"))),
            "context": (50, lambda r: bool(r["frame"].get("context_required"))),
            "ambiguous": (8, lambda r: r["frame"]["speech_act"] == "AMBIGUOUS"),
        }
        for name, (minimum, predicate) in required_strata.items():
            if sum(predicate(row) for row in audited_rows) < min(minimum, sum(predicate(row) for row in rows)):
                errors.append(f"audit_{name}_stratum_too_small")
    critical = sum(bool(a.get("critical_semantic_error")) for a in audit)
    annotation = sum(bool(a.get("annotation_error")) for a in audit)
    if critical:
        errors.append(f"critical_semantic_errors:{critical}")
    forbidden = {"span", "affordance", "correction", "asr"}
    categories = Counter(category for item in audit for category in item.get("error_categories", []))
    if forbidden & categories.keys():
        errors.append("critical_annotation_categories:" + ",".join(sorted(forbidden & categories.keys())))
    if audit and annotation / len(audit) >= 0.01:
        errors.append(f"annotation_error_rate:{annotation / len(audit):.4f}")
    return sorted(set(errors))


def audit_queue_errors(rows_path: Path, queue_path: Path, manifest_path: Path, audit: list[dict]) -> list[str]:
    if not manifest_path.exists() or not queue_path.exists():
        return ["audit_queue_or_manifest_missing"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("source_sha256") != hashlib.sha256(rows_path.read_bytes()).hexdigest():
        return ["audit_queue_source_hash_mismatch"]
    if manifest.get("queue_sha256") != hashlib.sha256(queue_path.read_bytes()).hexdigest():
        return ["audit_queue_hash_mismatch"]
    queue = read_jsonl(queue_path)
    queue_ids = {item.get("row_id") for item in queue}
    if len(queue) != MIN_AUDIT or len(queue_ids) != MIN_AUDIT or manifest.get("rows") != MIN_AUDIT:
        return ["audit_queue_size_or_ids_invalid"]
    if audit and {item.get("row_id") for item in audit} - queue_ids:
        return ["audit_contains_rows_outside_queue"]
    return []


def split_families(rows: list[dict]) -> dict[str, list[dict]]:
    families = defaultdict(list)
    for row in rows:
        families[row.get("isolation_group", row["family"])].append(row)
    split = {"train": [], "calibration": [], "dev": []}
    for family, group in families.items():
        bucket = int(hashlib.sha256(family.encode()).hexdigest()[:8], 16) % 10
        name = "train" if bucket < 8 else "calibration" if bucket == 8 else "dev"
        split[name].extend(group)
    return split


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=Path, default=OUT / "candidates.jsonl")
    parser.add_argument("--audit", type=Path, default=OUT / "manual_audit.jsonl")
    parser.add_argument("--queue", type=Path, default=OUT / "independent_audit_queue.jsonl")
    parser.add_argument("--queue-manifest", type=Path, default=OUT / "independent_audit_queue_manifest.json")
    args = parser.parse_args()
    from scripts.stage25_freeze import verify as verify_freeze
    if args.rows.resolve() == (OUT / "stage25_candidates.jsonl").resolve():
        freeze_errors = verify_freeze()
        if freeze_errors:
            print(json.dumps({"admitted": False, "reasons": ["freeze_mismatch:" + reason for reason in freeze_errors]}, indent=2))
            raise SystemExit(2)
    rows = read_jsonl(args.rows)
    audit = read_jsonl(args.audit) if args.audit.exists() else []
    errors = admission_errors(rows, audit)
    errors.extend(audit_queue_errors(args.rows, args.queue, args.queue_manifest, audit))
    if errors:
        print(json.dumps({"admitted": False, "reasons": errors}, indent=2))
        raise SystemExit(2)
    split = split_families(rows)
    for name, members in split.items():
        (OUT / f"gold_{name}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in members), encoding="utf-8")
    print(json.dumps({"admitted": True, "rows": {name: len(group) for name, group in split.items()}, "language": dict(Counter(r["language"] for r in rows))}, indent=2))


if __name__ == "__main__":
    main()
