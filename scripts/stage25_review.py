"""Independent Stage 2.5 audit sampling and local reviewer CLI.

The sampling command creates a queue, not completed reviews. The review
command records decisions only when a human explicitly enters them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from scripts.stage25_admit import read_jsonl, row_digest
from scripts.stage25_gold_data import OUT


def features(row: dict) -> set[str]:
    frame = row["frame"]
    result = {"lang:" + row["language"], "speech:" + frame["speech_act"], "family:" + str(frame["action_family"]), "action:" + str(frame["action_concept"])}
    result.update("slot:" + s["slot"] for s in frame.get("slots", []))
    if frame.get("context_required"):
        result.add("difficult:context")
    if frame.get("corrections"):
        result.add("difficult:correction")
    if frame.get("negations"):
        result.add("difficult:negation")
    if row.get("asr_pair"):
        result.add("difficult:asr")
    if frame["speech_act"] == "AMBIGUOUS":
        result.add("difficult:ambiguity")
    if len(frame.get("slots", [])) >= 4:
        result.add("difficult:complex_frame")
    if frame["action_concept"] in {"SEND", "SHARE", "FORWARD", "DELETE", "INSTALL", "UNINSTALL", "CALL", "ENTER", "UPLOAD", "ATTACH"}:
        result.add("risk:external_or_destructive")
    if frame["action_concept"] and not frame["should_execute"]:
        result.add("difficult:action_word_no_action")
    for verb, pattern in {"anupu": r"anup|அனுப்ப", "maathu": r"maath|mathu|மாற்ற|மாறு", "kudu": r"kudu|kodu|கொடு", "kaatu": r"kaat|காட்ட", "eduthu": r"eduth|eduk|எடு", "podu": r"podu|போடு", "paaru": r"paar|paru|பார்", "sollu": r"soll|solu|சொல்", "pannu": r"pannu|pann|பண்ண"}.items():
        if re.search(pattern, row["text"], re.IGNORECASE):
            result.add("verb:" + verb)
    return result


def select_queue(rows: list[dict], count: int = 750) -> list[dict]:
    if len(rows) < count:
        raise ValueError(f"Need {count} validated rows to sample; found {len(rows)}")
    target_language = 300 if count == 750 else min(count // 3, count // 2)
    available = Counter(row["language"] for row in rows)
    if any(available[language] < target_language for language in ("TANGLISH", "TAMIL")):
        raise ValueError("Insufficient rows in one language for stratified audit")
    stable_hash = {r["id"]: hashlib.sha256(r["id"].encode()).hexdigest() for r in rows}
    stable = sorted(rows, key=lambda r: stable_hash[r["id"]])
    feature_map = {r["id"]: features(r) for r in rows}
    selected: list[dict] = []
    selected_ids: set[str] = set()
    coverage: set[str] = set()
    lang_count = Counter()
    family_count = Counter()

    def add(row: dict) -> None:
        selected.append(row)
        selected_ids.add(row["id"])
        coverage.update(feature_map[row["id"]])
        lang_count[row["language"]] += 1
        family_count[row.get("isolation_group", row["family"])] += 1

    # Cover scarce semantic strata first, while preferring new construction families.
    universe = set().union(*feature_map.values())
    while len(selected) < count and universe - coverage:
        choices = [r for r in stable if r["id"] not in selected_ids]
        best = max(choices, key=lambda r: (len(feature_map[r["id"]] - coverage) * 100 - family_count[r.get("isolation_group", r["family"])] * 5, -lang_count[r["language"]]))
        if not (feature_map[best["id"]] - coverage):
            break
        add(best)
    if count == 750:
        strata = [
            ("correction", 60, lambda r: r["frame"]["speech_act"] == "CORRECTION"),
            ("asr", 50, lambda r: bool(r.get("asr_pair"))),
            ("context", 75, lambda r: bool(r["frame"].get("context_required"))),
            ("negation", 80, lambda r: r["frame"]["speech_act"] == "NEGATED_COMMAND"),
            ("hypothetical", 25, lambda r: r["frame"]["speech_act"] == "HYPOTHETICAL"),
            ("ambiguous", 25, lambda r: r["frame"]["speech_act"] == "AMBIGUOUS"),
            ("capability", 25, lambda r: r["frame"]["speech_act"] == "CAPABILITY_QUERY"),
            ("complex", 75, lambda r: len(r["frame"]["slots"]) >= 4),
            ("high_risk", 125, lambda r: "risk:external_or_destructive" in feature_map[r["id"]]),
            ("action_word_no_action", 150, lambda r: "difficult:action_word_no_action" in feature_map[r["id"]]),
        ]
        for _, minimum, predicate in strata:
            while len(selected) < count and sum(predicate(r) for r in selected) < minimum:
                choices = [r for r in stable if r["id"] not in selected_ids and predicate(r)]
                if not choices:
                    break
                best = min(choices, key=lambda r: (family_count[r.get("isolation_group", r["family"])], stable_hash[r["id"]]))
                add(best)
        slot_frequency = Counter(slot["slot"] for row in rows for slot in row["frame"]["slots"])
        for slot_name in sorted(slot_frequency, key=lambda name: (slot_frequency[name], name)):
            minimum = 5 if slot_frequency[slot_name] < 300 else 2
            while len(selected) < count and sum(any(slot["slot"] == slot_name for slot in row["frame"]["slots"]) for row in selected) < minimum:
                choices = [r for r in stable if r["id"] not in selected_ids and any(slot["slot"] == slot_name for slot in r["frame"]["slots"])]
                if not choices:
                    break
                add(min(choices, key=lambda r: (family_count[r.get("isolation_group", r["family"])], stable_hash[r["id"]])))
        for verb in ("anupu", "maathu", "kudu", "kaatu", "eduthu", "podu", "paaru", "sollu", "pannu"):
            while len(selected) < count and sum("verb:" + verb in feature_map[r["id"]] for r in selected) < 10:
                choices = [r for r in stable if r["id"] not in selected_ids and "verb:" + verb in feature_map[r["id"]]]
                if not choices:
                    break
                add(min(choices, key=lambda r: (family_count[r.get("isolation_group", r["family"])], stable_hash[r["id"]])))
    for language in ("TANGLISH", "TAMIL"):
        groups = defaultdict(list)
        for row in stable:
            if row["language"] == language and row["id"] not in selected_ids:
                groups[row.get("isolation_group", row["family"])].append(row)
        ordered_groups = sorted(groups, key=lambda group: stable_hash[groups[group][0]["id"]])
        cursor = 0
        while lang_count[language] < target_language and len(selected) < count:
            group = ordered_groups[cursor % len(ordered_groups)]
            if groups[group]:
                add(groups[group].pop(0))
            cursor += 1
    choices = sorted((r for r in stable if r["id"] not in selected_ids), key=lambda r: (
            family_count[r.get("isolation_group", r["family"])], stable_hash[r["id"]],
        ))
    for row in choices[: count - len(selected)]:
        add(row)
    return selected


def queue_coverage_errors(rows: list[dict], selected: list[dict]) -> list[str]:
    if len(selected) != 750:
        return ["queue_size"]
    errors = []
    selected_features = Counter(feature for row in selected for feature in features(row))
    full_speech = {r["frame"]["speech_act"] for r in rows}
    full_actions = {r["frame"]["action_concept"] for r in rows}
    full_slots = {slot["slot"] for row in rows for slot in row["frame"]["slots"]}
    if full_speech - {r["frame"]["speech_act"] for r in selected}:
        errors.append("speech_coverage")
    if full_actions - {r["frame"]["action_concept"] for r in selected}:
        errors.append("action_coverage")
    if full_slots - {slot["slot"] for row in selected for slot in row["frame"]["slots"]}:
        errors.append("slot_coverage")
    if any(Counter(r["language"] for r in selected)[lang] < 300 for lang in ("TANGLISH", "TAMIL")):
        errors.append("language_balance")
    minima = {"difficult:context": 75, "difficult:correction": 60, "difficult:negation": 80,
              "difficult:asr": 50, "difficult:ambiguity": 25, "difficult:complex_frame": 75,
              "risk:external_or_destructive": 125, "difficult:action_word_no_action": 150}
    for feature, minimum in minima.items():
        if selected_features[feature] < minimum:
            errors.append("stratum:" + feature)
    for verb in ("anupu", "maathu", "kudu", "kaatu", "eduthu", "podu", "paaru", "sollu", "pannu"):
        if selected_features["verb:" + verb] < 10:
            errors.append("verb:" + verb)
    slot_frequency = Counter(slot["slot"] for row in rows for slot in row["frame"]["slots"])
    for slot_name, full_count in slot_frequency.items():
        selected_count = sum(any(slot["slot"] == slot_name for slot in row["frame"]["slots"]) for row in selected)
        if selected_count < (5 if full_count < 300 else 2):
            errors.append("rare_slot:" + slot_name)
    return errors


def prepare(rows_path: Path, queue_path: Path, count: int) -> None:
    gate_path = rows_path.parent / "stage25_final_gate.json"
    if count == 750:
        if not gate_path.exists():
            raise ValueError("Final distribution quality gate is missing")
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
        if not gate.get("passed") or gate.get("corpus_sha256") != hashlib.sha256(rows_path.read_bytes()).hexdigest():
            raise ValueError("Final distribution gate does not pass for this corpus revision")
    rows = read_jsonl(rows_path)
    if any(r.get("validation_status") != "PASSED" for r in rows):
        raise ValueError("Audit queue requires validator-passed rows")
    selected = select_queue(rows, count)
    if count == 750:
        coverage_errors = queue_coverage_errors(rows, selected)
        if coverage_errors:
            raise ValueError("Risk-stratified queue failed: " + ", ".join(coverage_errors))
    with queue_path.open("w", encoding="utf-8") as stream:
        for row in selected:
            stream.write(json.dumps({"row_id": row["id"], "row_sha256": row_digest(row), "language": row["language"], "text": row["text"], "working_context": row.get("working_context"), "frame": row["frame"], "asr_pair": row.get("asr_pair"), "generation_family": row.get("generation_family"), "construction_family": row.get("construction_family"), "quality_flags": row.get("quality_flags", []), "decision": None, "reason": None}, ensure_ascii=False) + "\n")
    manifest = {"source": str(rows_path), "source_sha256": hashlib.sha256(rows_path.read_bytes()).hexdigest(), "queue_sha256": hashlib.sha256(queue_path.read_bytes()).hexdigest(), "rows": len(selected), "language": dict(Counter(r["language"] for r in selected))}
    (queue_path.parent / "independent_audit_queue_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"queue": str(queue_path), "rows": len(selected), "language": dict(Counter(r["language"] for r in selected)), "speech_act": dict(Counter(r["frame"]["speech_act"] for r in selected))}, ensure_ascii=True, indent=2))


def review(queue_path: Path, audit_path: Path, reviewer: str) -> None:
    import sys
    from scripts.stage25_freeze import verify as verify_freeze
    sys.stdout.reconfigure(encoding="utf-8")
    if not reviewer.strip():
        raise ValueError("Reviewer identity is required")
    if queue_path.resolve() == (OUT / "independent_audit_queue.jsonl").resolve():
        freeze_errors = verify_freeze()
        if freeze_errors:
            raise ValueError("Stage 2.5 freeze mismatch: " + ", ".join(freeze_errors))
    queue = read_jsonl(queue_path)
    manifest_path = queue_path.parent / "independent_audit_queue_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["queue_sha256"] != hashlib.sha256(queue_path.read_bytes()).hexdigest():
        raise ValueError("Audit queue differs from its manifest")
    completed = read_jsonl(audit_path) if audit_path.exists() else []
    done = {r["row_id"]: r.get("row_sha256") for r in completed}
    queue_hash = {r["row_id"]: r["row_sha256"] for r in queue}
    if any(row_id in queue_hash and digest != queue_hash[row_id] for row_id, digest in done.items()):
        raise ValueError("Existing review refers to a changed row; use a new audit file")
    for item in queue:
        if item["row_id"] in done:
            continue
        print("\n" + "=" * 72)
        print(f"{item['row_id']} [{item['language']}]\n{item['text']}")
        print("Context:", json.dumps(item["working_context"], ensure_ascii=True, indent=2))
        print("Frame:", json.dumps(item["frame"], ensure_ascii=True, indent=2))
        if item.get("asr_pair"):
            print("ASR clean/noisy pair:", json.dumps(item["asr_pair"], ensure_ascii=True, indent=2))
        print("Flags:", item["quality_flags"])
        decision = input("Decision [c=CORRECT, i=INCORRECT, e=NEEDS_EDIT, q=quit]: ").strip().lower()
        if decision == "q":
            break
        if decision not in {"c", "i", "e"}:
            print("Invalid decision; row skipped")
            continue
        reason = input("Reason (required for incorrect/edit): ").strip()
        if decision != "c" and not reason:
            print("Reason required; row skipped")
            continue
        categories = []
        if decision != "c":
            raw = input("Error categories (comma-separated: semantic, span, affordance, correction, asr, naturalness, other): ").strip().lower()
            categories = sorted({part.strip() for part in raw.split(",") if part.strip()})
            if not categories or any(part not in {"semantic", "span", "affordance", "correction", "asr", "naturalness", "other"} for part in categories):
                print("Valid error category required; row skipped")
                continue
        critical = input("Critical semantic/safety error? [y/N]: ").strip().lower() == "y" if decision != "c" else False
        result = {"row_id": item["row_id"], "row_sha256": item["row_sha256"], "reviewer": reviewer, "reviewed_utc": datetime.now(timezone.utc).isoformat(), "decision": {"c": "CORRECT", "i": "INCORRECT", "e": "NEEDS_EDIT"}[decision], "reason": reason, "error_categories": categories, "annotation_error": decision != "c", "critical_semantic_error": critical}
        with audit_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(result, ensure_ascii=False) + "\n")
        done[item["row_id"]] = item["row_sha256"]
    print(f"Completed reviews: {len(done)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "review"])
    parser.add_argument("--rows", type=Path, default=OUT / "candidates.jsonl")
    parser.add_argument("--queue", type=Path, default=OUT / "independent_audit_queue.jsonl")
    parser.add_argument("--audit", type=Path, default=OUT / "manual_audit.jsonl")
    parser.add_argument("--count", type=int, default=750)
    parser.add_argument("--reviewer")
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare(args.rows, args.queue, args.count)
    else:
        if not args.reviewer:
            parser.error("--reviewer is required for review")
        review(args.queue, args.audit, args.reviewer)


if __name__ == "__main__":
    main()
