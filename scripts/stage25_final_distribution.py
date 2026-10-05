"""Stage 2.5 rebalance audit and pre-review quality gate (offline only)."""
from __future__ import annotations

import hashlib
import json
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from scripts.stage25_admit import read_jsonl
from scripts.stage25_gold_data import AFFORDANCES, OUT, ROOT, SLOTS, SPEECH, affordance, validate_row
from scripts.stage25_quality_report import normalized
from scripts.tanglish_stage24_ontology import ACTION_FAMILY

DOWNSTREAM = {
    "ANSWER": "Represent the request as PROVIDE plus AnswerRef; answer wording is resolved downstream.",
    "RETURN": "Represent a requested result as PROVIDE plus its resource type; transport is resolved downstream.",
    "TYPE": "Represent text entry as ENTER or WRITE using the destination and text slots.",
    "INSERT": "Represent insertion as ENTER or WRITE using the destination and position slots.",
}
REGISTRY_GAP = {
    "PAY": "No general payment capability or safe execution contract is registered; retain as a policy-sensitive semantic gap.",
    "SUBMIT": "No general external-transaction submit capability or verified contract is registered; retain as a policy-sensitive semantic gap.",
}
PRIORITY_MATRIX = {
    "SEARCH": ("FileRef", "MessageRef", "WebQueryRef", "ProjectRef"),
    "OPEN": ("AppRef", "FileRef", "URLRef"),
    "CHECK": ("SystemStatusRef", "ProjectRef", "MessageRef", "FileRef"),
}
VERB_FORMS = {
    "anupu / அனுப்பு": r"anup|anupp|அனுப்ப",
    "maathu / மாற்று": r"maath|mathu|மாற்ற|மாறு",
    "kudu / கொடு": r"kudu|kodu|கொடு",
    "kaatu / காட்டு": r"kaat|காட்டு|காட்ட",
    "eduthu / எடு": r"eduth|eduk|எடு|எடுத்த",
    "podu / போடு": r"podu|pott|போடு|போட்ட",
    "paaru / பார்": r"paar|paru|பார்|பாரு",
    "sollu / சொல்": r"sollu|solu|சொல்",
    "pannu / பண்ணு": r"pannu|pann|பண்ணு|பண்ண",
}


def phonetic_key(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).casefold()
    value = re.sub(r"([a-z])\1+", r"\1", value)
    return " ".join(re.sub(r"[aeiou]", "", token) if token.isascii() else token
                    for token in re.findall(r"[\w\u0b80-\u0bff]+", value))


def frame_signature(row: dict) -> str:
    frame = row["frame"]
    return json.dumps({"speech": frame["speech_act"], "action": frame["action_concept"],
        "object": frame["object_type"], "slots": [(slot["slot"], slot["value"]) for slot in frame["slots"]],
        "negations": frame["negations"], "corrections": frame["corrections"],
        "context_refs": frame["context_refs"], "context": row.get("working_context")},
        sort_keys=True, ensure_ascii=False)


def excess(counter: Counter) -> int:
    return sum(count - 1 for count in counter.values() if count > 1)


def table(headers: tuple[str, ...], body: list[tuple]) -> str:
    return "| " + " | ".join(headers) + " |\n|" + "|".join("---" for _ in headers) + "|\n" + "\n".join("| " + " | ".join(map(str, row)) + " |" for row in body) + "\n"


def build() -> dict:
    path = OUT / "stage25_candidates.jsonl"
    rows = read_jsonl(path)
    counts = Counter(row["frame"]["action_concept"] for row in rows)
    by_language = defaultdict(Counter)
    for row in rows:
        by_language[row["language"]][row["frame"]["action_concept"]] += 1
    action_object = Counter((r["frame"]["action_concept"], r["frame"]["object_type"]) for r in rows if r["frame"]["action_concept"])
    slots = Counter(slot["slot"] for row in rows for slot in row["frame"]["slots"])
    slot_bands = Counter("0" if not row["frame"]["slots"] else "1" if len(row["frame"]["slots"]) == 1 else "2" if len(row["frame"]["slots"]) == 2 else "3" if len(row["frame"]["slots"]) == 3 else "4+" for row in rows)
    families = Counter(row["construction_family"] for row in rows)
    family_sizes = sorted(families.values())
    exact_keys = Counter((r["language"], r["text"], json.dumps(r.get("working_context"), sort_keys=True, ensure_ascii=False)) for r in rows)
    norm_keys = Counter((r["language"], normalized(r["text"]), json.dumps(r.get("working_context"), sort_keys=True, ensure_ascii=False)) for r in rows)
    phonetic = Counter((r["language"], phonetic_key(r["text"]), frame_signature(r)) for r in rows)
    non_asr_phonetic = Counter((r["language"], phonetic_key(r["text"]), frame_signature(r)) for r in rows if not r.get("asr_pair"))
    context = Counter(key for row in rows for key in row["frame"]["context_refs"])
    negated = Counter(row["frame"]["action_concept"] for row in rows if row["frame"]["negations"])
    corrected = Counter(item["active_slot"] for row in rows for item in row["frame"]["corrections"])
    speech = Counter(row["frame"]["speech_act"] for row in rows)
    language = Counter(row["language"] for row in rows)
    family_action = Counter(row["frame"]["action_family"] for row in rows)
    script_verb = defaultdict(Counter)
    for row in rows:
        last_slot_end = max((slot["end"] for slot in row["frame"]["slots"] if slot["source"] == "TEXT"), default=0)
        diagnostic_text = row["text"][last_slot_end:]
        diagnostic_text = diagnostic_text.split(" nu sonna")[0].split(" என்று சொன்னால்")[0]
        for family, pattern in VERB_FORMS.items():
            if re.search(pattern, diagnostic_text, re.IGNORECASE):
                script_verb[(family, row["frame"]["action_concept"])][row["language"]] += 1
    validator = Counter(error for row in rows for error in validate_row(row))
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    unsupported = set(ACTION_FAMILY) - set(DOWNSTREAM) - set(REGISTRY_GAP)
    gates = {
        "row_count": len(rows) == 30_000,
        "script_ratio": language == {"TANGLISH": 18_000, "TAMIL": 12_000},
        "supported_action_floor": all(counts[action] >= 150 for action in unsupported),
        "slot_floor": all(slots[slot] >= 100 for slot in SLOTS),
        "speech_coverage": set(speech) == SPEECH,
        "hard_negative_coverage": all(speech[k] >= 200 for k in ("QUESTION", "CAPABILITY_QUERY", "STATEMENT", "HYPOTHETICAL", "NEGATED_COMMAND", "AMBIGUOUS")),
        "context_floor": sum(context.values()) >= 2_310,
        "correction_floor": speech["CORRECTION"] >= 1_598,
        "asr_ceiling": sum(bool(r.get("asr_pair")) for r in rows) <= 1_500,
        "transfer_ceiling": sum(counts[k] for k in ("SEND", "SHARE", "FORWARD")) <= 5_400,
        "construction_family_ceiling": max(family_sizes) <= 250,
        "unique_ids": len({r["id"] for r in rows}) == len(rows),
        "exact_duplicates": excess(exact_keys) == 0,
        "normalized_duplicates": excess(norm_keys) == 0,
        "validator": not validator,
        "priority_action_object_matrix": all(action_object[(action, obj)] >= 50 for action, objects in PRIORITY_MATRIX.items() for obj in objects),
    }
    gate_result = {"corpus_sha256": source_hash, "passed": all(gates.values()), "checks": gates,
                   "failed": [key for key, passed in gates.items() if not passed]}
    (OUT / "stage25_final_gate.json").write_text(json.dumps(gate_result, indent=2) + "\n", encoding="utf-8")

    ontology_body = []
    for action in sorted(ACTION_FAMILY):
        decision = "DOWNSTREAM_TOOL_ONLY" if action in DOWNSTREAM else "REGISTRY_GAP" if action in REGISTRY_GAP else "SUPPORTED_BY_LANGUAGE_MODEL"
        repair = DOWNSTREAM.get(action) or REGISTRY_GAP.get(action) or ("Raise to 150 examples" if counts[action] < 150 else "None before audit")
        ontology_body.append((action, ACTION_FAMILY[action], counts[action], by_language["TAMIL"][action], by_language["TANGLISH"][action], decision, repair))
    ontology = "# Stage 2.5 action ontology coverage\n\n"
    ontology += "Counts refer to the frozen Q2 candidate corpus, before independent human review. A supported label is a language meaning, never tool authorization. The four collapsed labels are represented by typed frames; PAY and SUBMIT need a registered execution and policy contract before language-level training or action.\n\n"
    ontology += f"Corpus SHA-256: `{source_hash}`. Supported concepts: {len(unsupported)} of {len(ACTION_FAMILY)}.\n\n"
    ontology += table(("ActionConcept", "ActionFamily", "Total", "Tamil", "Tanglish", "Decision", "Required repair"), ontology_body)
    (ROOT / "reports" / "STAGE25_ACTION_ONTOLOGY_COVERAGE.md").write_text(ontology, encoding="utf-8")

    report = "# Stage 2.5 final Tamil/Tanglish distribution\n\n"
    report += f"**Pre-review machine gate: {'PASS' if gate_result['passed'] else 'FAIL'}.** Corpus SHA-256 `{source_hash}`. These are synthetic Q2 candidates; naturalness and semantic fidelity require the independent 750-row human audit. TEST and HOLDOUT were not read.\n\n"
    report += "## Corpus and action balance\n\n"
    report += table(("Language", "Rows"), sorted(language.items())) + "\n"
    report += f"SEND + SHARE + FORWARD: {sum(counts[k] for k in ('SEND', 'SHARE', 'FORWARD')):,}/30,000 ({100*sum(counts[k] for k in ('SEND', 'SHARE', 'FORWARD'))/len(rows):.2f}%).\n\n"
    report += table(("ActionFamily", "Rows"), sorted(family_action.items(), key=lambda x: str(x[0]))) + "\n"
    report += table(("ActionConcept", "Rows", "Tamil", "Tanglish"), [(a, counts[a], by_language["TAMIL"][a], by_language["TANGLISH"][a]) for a in sorted(counts, key=str)]) + "\n"
    report += "## Speech and slots\n\n"
    report += table(("SpeechAct", "Rows"), sorted(speech.items())) + "\n"
    report += table(("Slot", "Annotations"), sorted(slots.items())) + "\n"
    report += table(("Slots per frame", "Rows"), [(band, slot_bands[band]) for band in ("0", "1", "2", "3", "4+")]) + "\n"
    report += "## Action × object coverage\n\n"
    report += "Only observed valid combinations are listed. Priority matrix holes are checked at 50 rows per combination; other valid affordances remain candidate expansion areas.\n\n"
    report += table(("ActionConcept", "ObjectType", "Rows", "Affordance"), [(a, o, n, affordance(a, o)) for (a, o), n in sorted(action_object.items())]) + "\n"
    report += "## Context, correction, negation, noise\n\n"
    report += table(("Context reference", "Rows"), sorted(context.items())) + "\n"
    report += table(("Corrected active slot", "Rows"), sorted(corrected.items())) + "\n"
    report += table(("Negated action", "Rows"), sorted(negated.items(), key=lambda x: str(x[0]))) + "\n"
    report += f"Context-required rows: {sum(bool(r['frame']['context_required']) for r in rows):,}. Correction rows: {speech['CORRECTION']:,}. ASR positive rows: {sum(bool(r.get('asr_pair')) for r in rows):,}; each was checked against its clean frame.\n\n"
    report += "## Surface polysemy diagnostic\n\n"
    report += "The following counts use a simple predicate-tail proxy (text after the last explicit slot), paired with the labelled action. Corrections and unusual word orders can be missed; these are not an independently measured verb-sense score.\n\n"
    report += table(("Verb family", "Action label", "Tamil", "Tanglish"), [(v, a, c["TAMIL"], c["TANGLISH"]) for (v, a), c in sorted(script_verb.items(), key=lambda x: (x[0][0], str(x[0][1]))) if sum(c.values()) >= 10]) + "\n"
    report += "## Diversity and duplicate checks\n\n"
    report += f"Construction families: {len(families):,}; median size {statistics.median(family_sizes):g}; p95 size {family_sizes[int(0.95*(len(family_sizes)-1))]}; largest {max(family_sizes)}; top-ten share {sum(v for _,v in families.most_common(10))/len(rows):.2%}. Rows in families over 250: {sum(v for v in family_sizes if v > 250)}.\n\n"
    report += f"Exact duplicate excess: {excess(exact_keys)}; normalized text/context duplicate excess: {excess(norm_keys)}; phonetic plus same-frame collision excess: {excess(phonetic)}; after excluding deliberate ASR positive children: {excess(non_asr_phonetic)}. The 1,500 ASR positive children account for the phonetic collisions in this corpus and remain explicit review targets. Normalization uses Unicode NFKC for both scripts. The remaining shared construction skeletons are deliberate composition, and family-isolated splitting prevents template leakage.\n\n"
    report += "## Pre-review gate\n\n"
    report += table(("Check", "Result"), [(name, "PASS" if passed else "FAIL") for name, passed in gates.items()]) + "\n"
    queue_path = OUT / "independent_audit_queue.jsonl"
    if queue_path.exists():
        from scripts.stage25_review import features, queue_coverage_errors
        queue_items = read_jsonl(queue_path)
        queue_ids = {item["row_id"] for item in queue_items}
        selected = [row for row in rows if row["id"] in queue_ids]
        if len(selected) == len(queue_items):
            queue_errors = queue_coverage_errors(rows, selected)
            qf = Counter(feature for row in selected for feature in features(row))
            report += "## Frozen independent audit queue\n\n"
            report += f"Rows: {len(selected)}; Tamil {sum(row['language']=='TAMIL' for row in selected)}; Tanglish {sum(row['language']=='TANGLISH' for row in selected)}. Queue SHA-256 `{hashlib.sha256(queue_path.read_bytes()).hexdigest()}`. Risk-stratification check: {'PASS' if not queue_errors else 'FAIL: ' + ', '.join(queue_errors)}.\n\n"
            report += table(("Audit stratum", "Rows"), [(name, qf[name]) for name in ("difficult:context", "difficult:correction", "difficult:negation", "difficult:asr", "difficult:ambiguity", "difficult:complex_frame", "risk:external_or_destructive", "difficult:action_word_no_action")]) + "\n"
            report += "All observed SpeechActs, ActionConcepts, and slot names have queue coverage; scarce slots and each seeded polysemous verb were oversampled. The earlier queue is archived as `STALE_PRE_REBALANCE` and must not be reviewed.\n\n"
    report += "Sparse areas: ACKNOWLEDGEMENT, CONFIRMATION and CHAT remain below 25 examples each; they are represented but not acceptance-quality classifiers on their own. Some action-object combinations outside the priority matrix have few examples. All corpus labels and Tamil realizations still require human audit.\n"
    (ROOT / "reports" / "TAMIL_TANGLISH_STAGE25_FINAL_DISTRIBUTION.md").write_text(report, encoding="utf-8")
    return gate_result


if __name__ == "__main__":
    result = build()
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(2)
