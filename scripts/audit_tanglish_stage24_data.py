"""Train/development-only consistency audit and stratified review sample."""
from __future__ import annotations

import hashlib
import json
import random
import re
from collections import Counter, defaultdict

from scripts.build_tanglish_semantic_stage2 import BASE, ONTOLOGY
from scripts.build_tanglish_stage21_repair import ACTION_MAP, ELIGIBLE, OUT as REPAIR
from scripts.evaluate_tanglish_stage21 import legacy, read

OUT=BASE/"generated/stage24"
TAMIL_MARKERS={"ah","oda","ku","kitta","kita","la","lendhu","irundhu","pannu",
               "pannunga","panna","venam","venda","vendam","atha","athu","ithu",
               "kaatu","kudu","maathu","anupu","anuppu","mattum","ippo",
               "inniku","naalaiku","thevai","mudiyuma","pannitiya"}


def normalized(row):
    return " ".join(re.findall(r"\w+", " [TURN] ".join(row["previous_turns"][-2:]+[row["text"]]).casefold()))


def issue_codes(row):
    issues=[]
    text=row["text"]
    tokens=set(re.findall(r"[a-z]+",text.casefold()))
    act=row["speech_act"]
    if row["action_concept"] not in ACTION_MAP:
        issues.append("UNKNOWN_ACTION")
    if row["should_act"] != (act in ELIGIBLE):
        issues.append("ACTIONABILITY_LABEL_MISMATCH")
    if row["language"]=="english" and tokens & TAMIL_MARKERS:
        issues.append("ENGLISH_LABEL_CONTAINS_TANGLISH")
    if act in ELIGIBLE and tokens & {"atha","athu","itha","ithu"} and not row["previous_turns"]:
        issues.append("UNRESOLVED_PRONOUN")
    if act=="NEGATED_COMMAND" and not (tokens & {"venam","venda","vendam","pannadha","pannadhinga","not"}
                                        or re.search(r"\bdon['’]?t\b",text.casefold())):
        issues.append("NEGATION_CUE_MISSING")
    if act=="CORRECTION" and not (tokens & {"illa","sorry","actually","wait","dhaan"}):
        issues.append("CORRECTION_CUE_MISSING")
    slots=row.get("slots",{})
    for key in ("recipient","ordinal","file_type"):
        value=slots.get(key)
        if isinstance(value,str) and value not in ("context.selected_resource",) and key=="recipient" and value.casefold() not in text.casefold():
            issues.append("RECIPIENT_NOT_IN_UTTERANCE")
    return sorted(set(issues))


def main():
    train=[legacy(r) for r in read(BASE/"generated/semantic_stage2/train.jsonl.gz")]
    dev=[legacy(r) for r in read(BASE/"generated/semantic_stage2/dev.jsonl.gz")]
    repair_train=read(REPAIR/"train.jsonl.gz")
    repair_dev=read(REPAIR/"dev_no_action.jsonl.gz")+read(REPAIR/"dev_command.jsonl.gz")
    sources={"stage2_train":train,"stage2_dev":dev,"repair_train":repair_train,"repair_dev":repair_dev}
    report={"sources":{},"quality_flags":{},"review_sample_rows":0,
            "test_opened":False,"sealed_holdout_opened":False}
    for source,rows in sources.items():
        flags=Counter(code for row in rows for code in issue_codes(row))
        report["sources"][source]={"rows":len(rows),"speech":dict(Counter(row["speech_act"] for row in rows)),
                                   "language_labels":dict(Counter(row["language"] for row in rows)),
                                   "flags":dict(flags)}
    train_keys={normalized(row) for row in train+repair_train}
    dev_keys={normalized(row) for row in dev+repair_dev}
    report["normalized_train_dev_overlap"]=len(train_keys&dev_keys)
    rng=random.Random(2404)
    categories=defaultdict(list)
    for row in train:
        categories[row["category"]].append(row)
    sample=[]
    for category,items in sorted(categories.items()):
        sample.extend(("stage2_train",category,row) for row in rng.sample(items,min(25,len(items))))
    acts=defaultdict(list)
    for row in repair_train:
        acts[row["speech_act"]].append(row)
    for act,items in sorted(acts.items()):
        sample.extend(("repair_train",act,row) for row in rng.sample(items,min(8,len(items))))
    rng.shuffle(sample)
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/"quality_review_sample.jsonl").open("w",encoding="utf-8") as stream:
        for source,stratum,row in sample:
            stream.write(json.dumps({"source":source,"stratum":stratum,"text":row["text"],
                                     "context":row["previous_turns"],"speech_act":row["speech_act"],
                                     "action_concept":row["action_concept"],"should_act":row["should_act"],
                                     "flags":issue_codes(row)},ensure_ascii=False)+"\n")
    report["review_sample_rows"]=len(sample)
    report["review_sample_sha256"]=hashlib.sha256((OUT/"quality_review_sample.jsonl").read_bytes()).hexdigest()
    (OUT/"quality_audit.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"source_rows":{k:v["rows"] for k,v in report["sources"].items()},
                      "overlap":report["normalized_train_dev_overlap"],
                      "sample":len(sample),"flags":{k:v["flags"] for k,v in report["sources"].items()}},indent=2))


if __name__=="__main__":
    main()
