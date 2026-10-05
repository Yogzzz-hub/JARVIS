"""Small hand-specified frame probes; never evaluates sealed data or invokes tools."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.tanglish_stage22_frame import RefCandidate, TemporalRange, WorkingContext, extract_frame

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/tanglish/generated/stage22"
SELECTED = WorkingContext(selected_resource=RefCandidate("FileRefCandidate", "report.pdf", "selected_resource"))

# Expectations were written independently of extractor output. They cover selected fields,
# not the complete 33-slot schema; whole-frame accuracy must not be inferred from them.
CASES = [
    ("report.pdf Arun ku anuppu... illa Naveen ku", "SEND", None,
     {"file":"report.pdf", "recipient":"Naveen", "file_type":"PDF"}, "recipient"),
    ("atha Naveen ku anuppu PDF mattum screenshot venam", "SEND", SELECTED,
     {"selected_resource":"report.pdf", "recipient":"Naveen", "include_constraint":{"file_type":"PDF"}, "exclude_constraint":"screenshot"}, None),
    ("volume 70... actually 40", "SET", None, {"quantity":40, "number":70}, "quantity"),
    ("Chrome open pannu, sorry Edge", "OPEN", None, {"application":"Edge"}, "application"),
    ("open https://example.com", "OPEN", None, {"url":"https://example.com", "resource_type":"URLResource"}, None),
    ("Chrome second tab ku maathu", "SWITCH", None, {"browser":"Chrome", "browser_tab":"second", "ordinal":2}, None),
    ("report.pdf mail la anuppu", "SEND", None, {"file":"report.pdf", "file_type":"PDF"}, None),
    ("send \"JARVIS check\" to Naveen", "SEND", None, {"text_content":"JARVIS check", "quoted_resource":"JARVIS check"}, None),
    ("folder Atlas create pannu", "CREATE", None, {"folder":"Atlas"}, None),
    ("alarm tomorrow at 7:30", "CREATE", None, {"date":"tomorrow", "time":"7:30"}, None),
    ("PDF mattum anuppu screenshot venam", "SEND", None,
     {"include_constraint":{"file_type":"PDF"}, "exclude_constraint":"screenshot"}, None),
    ("atha Arun ku anuppu", "SEND", None, {"recipient":"Arun", "selected_resource":None}, None),
    ("Arun ku venam Naveen ku anuppu", "SEND", None,
     {"recipient":"Naveen", "exclude_constraint":"arun"}, None),
    ("Chrome lendhu Edge ku maathu", "SWITCH", None,
     {"source":"chrome", "destination":"edge", "application":"Edge"}, None),
    ("Naveen oda latest PDF kaatu", "SHOW", None,
     {"sender":"Naveen", "file_type":"PDF", "ordinal":-1}, None),
    ("show reports from tomorrow to next week", "SHOW", None,
     {"date_range":("tomorrow","next week")}, None),
    ("send panna venam", "SEND", None, {"recipient":None}, None),
]


def canonical(value):
    if isinstance(value, RefCandidate):
        return value.surface
    if isinstance(value, TemporalRange):
        return (value.start, value.end)
    return value


def main():
    counts = {}
    tp = fp = fn = exact = 0
    cases = []
    for text, action, context, expected, correction_slot in CASES:
        frame = extract_frame(text, context, action_concept=action)
        row_exact = True
        for key, gold in expected.items():
            guess = canonical(frame.slots[key])
            passed = guess == gold
            row_exact &= passed
            if gold is not None:
                if passed:
                    tp += 1
                else:
                    fn += 1
                    if guess is not None:
                        fp += 1
            elif guess is not None:
                fp += 1
            entry = counts.setdefault(key, {"support":0,"correct":0})
            entry["support"] += 1
            entry["correct"] += passed
        if correction_slot:
            row_exact &= bool(frame.corrections and frame.corrections[0]["slot"] == correction_slot)
        exact += row_exact
        cases.append({"text":text,"selected_field_match":bool(row_exact)})
    precision = tp/max(1,tp+fp); recall = tp/max(1,tp+fn)
    result = {"cases":len(CASES), "scope":"hand-specified selected fields only; not whole SemanticFrame accuracy",
              "slot_precision":precision,"slot_recall":recall,
              "slot_f1":2*precision*recall/(precision+recall) if precision+recall else 0,
              "selected_field_exact_match":exact/len(CASES),
              "per_slot":{k:{**v,"accuracy":v["correct"]/v["support"]} for k,v in counts.items()},
              "case_results":cases,"whole_semantic_frame_exact_match":None}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"frame_probe.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("cases","slot_precision","slot_recall","slot_f1","selected_field_exact_match")},indent=2))


if __name__ == "__main__":
    main()
