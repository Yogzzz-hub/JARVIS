"""Read only Stage 2 train/dev artifacts; diagnose English and clear routing."""
from __future__ import annotations

import json
import pickle
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.sparse import hstack

from scripts.build_tanglish_semantic_stage2 import BASE
from scripts.build_tanglish_stage21_repair import OUT as S21
from scripts.evaluate_tanglish_stage21 import input_text, legacy, read
from scripts.evaluate_tanglish_stage22 import apply_negation_guard, dev_partition, route

ROOT = Path(__file__).resolve().parents[1]
OUT = BASE / "generated/stage23"


def percentile(values):
    if len(values) == 0:
        return None
    return {str(q):float(np.percentile(values,q)) for q in (0,10,25,50,75,90,100)}


def main():
    with (ROOT / "models/tanglish_stage21/candidate_dev_only.pkl").open("rb") as stream:
        old = pickle.load(stream)
    with (BASE / "generated/stage22/semantic_fallback.pkl").open("rb") as stream:
        fallback = pickle.load(stream)
    tri = json.loads((BASE / "generated/stage22/tri_state_dev.json").read_text(encoding="utf-8"))
    dev = [legacy(r) for r in read(BASE / "generated/semantic_stage2/dev.jsonl.gz")]
    dev += read(S21 / "dev_no_action.jsonl.gz") + read(S21 / "dev_command.jsonl.gz")
    rows = [r for r in dev if dev_partition(r)==1]
    texts = [input_text(r) for r in rows]
    word = old["vectorizer"].transform(texts)
    fast = old["gate"].predict_proba(word)[:,1]
    semantic = fallback["head"].predict_proba(hstack((word,fallback["encoder"].transform(texts)),format="csr"))[:,1]
    t = tri["thresholds"]
    fast_state = apply_negation_guard(route(fast,semantic,t["t_no_action"],t["t_execute"],-1,2),rows)
    final = apply_negation_guard(route(fast,semantic,t["t_no_action"],t["t_execute"],
                                       t["t_semantic_no_action"],t["t_semantic_execute"]),rows)
    report = {"scope":"Stage 2.2 development evaluation partition only", "groups":{},
              "train_clear_english":{}, "test_opened":False,"sealed_holdout_opened":False}
    original_train = [r for r in read(BASE / "generated/semantic_stage2/train.jsonl.gz") if r["category"]=="clear"]
    original_dev = [r for r in read(BASE / "generated/semantic_stage2/dev.jsonl.gz") if r["category"]=="clear"]
    for label, subset in (("train",original_train),("dev",original_dev)):
        report["train_clear_english"][label] = {"rows":len(subset),
            "language":dict(Counter(r["language"] for r in subset)),
            "speech":dict(Counter(r["semantic_frame"]["speech_act"] for r in subset)),
            "should_act":dict(Counter(str(r["semantic_frame"]["should_act"]) for r in subset)),
            "construction_families":dict(Counter(r["construction_family"] for r in subset))}
    masks = {
        "english":np.array([r.get("language")=="english" for r in rows]),
        "clear":np.array([r.get("category")=="clear" for r in rows]),
        "english_clear":np.array([r.get("language")=="english" and r.get("category")=="clear" for r in rows]),
        "tanglish":np.array([r.get("language")=="tanglish" for r in rows]),
        "asr_noise":np.array([r.get("category")=="asr_noise" for r in rows]),
    }
    for name, mask in masks.items():
        idx = np.where(mask)[0]
        command = np.array([rows[i]["should_act"] for i in idx],dtype=bool)
        fast_slice = fast[idx]; sem_slice=semantic[idx]
        fs=fast_state[idx]; state=final[idx]
        report["groups"][name] = {"rows":len(idx),"commands":int(sum(command)),
            "fast_command_scores":percentile(fast_slice[command]),
            "semantic_command_scores":percentile(sem_slice[command]),
            "fast_noncommand_scores":percentile(fast_slice[~command]),
            "semantic_noncommand_scores":percentile(sem_slice[~command]),
            "fast_command_routes":dict(Counter(fs[command])),
            "final_command_routes":dict(Counter(state[command])),
            "final_noncommand_routes":dict(Counter(state[~command])),
            "missed_command_actions":dict(Counter(rows[i]["action_concept"] for j,i in enumerate(idx) if command[j] and state[j]!="EXECUTE_CANDIDATE")),
            "missed_command_examples":[{"text":rows[i]["text"],"fast_score":float(fast[i]),"semantic_score":float(semantic[i]),
                                        "route":str(final[i])} for j,i in enumerate(idx) if command[j] and final[i]!="EXECUTE_CANDIDATE"][:20]}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"english_audit.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:{x:v[x] for x in ("rows","commands","fast_command_scores","semantic_command_scores","final_command_routes")}
                      for k,v in report["groups"].items()},indent=2))


if __name__ == "__main__":
    main()
