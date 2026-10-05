"""Offline train/calibration/evaluation gap diagnostic for the frozen encoder."""
from __future__ import annotations

import json
from collections import Counter

import numpy as np
import torch

from scripts.train_tanglish_stage23_neural import MODEL_DIR, OUT, SharedSemanticNet, labels, rows


def main():
    groups=rows()
    vocab, targets=labels(groups)
    with np.load(OUT/"multilingual_minilm_embeddings.npz") as cached:
        vectors=np.split(cached["vectors"],np.cumsum(cached["lengths"])[:-1])
    saved=torch.load(MODEL_DIR/"candidate_dev_only.pt",map_location="cpu",weights_only=False)
    model=SharedSemanticNet(saved["vocab"]);model.load_state_dict(saved["weights"]);model.eval()
    report={"partitions":{},"test_opened":False,"sealed_holdout_opened":False}
    for name,group,vec,gold in zip(("train","calibration","evaluation"),groups,vectors,targets):
        output={key:[] for key in ("act","speech","action","domain")}
        with torch.no_grad():
            for batch in np.array_split(vec,max(1,int(np.ceil(len(vec)/512)))):
                logits,_=model(torch.from_numpy(batch))
                for key in output:
                    output[key].append(np.argmax(logits[key].numpy(),axis=1))
        pred={key:np.concatenate(value) for key,value in output.items()}
        row={"rows":len(group),**{f"{key}_accuracy":float(np.mean(pred[key]==gold[key])) for key in output}}
        row["by_language"]={}
        for language in sorted({item["language"] for item in group}):
            indices=np.asarray([i for i,item in enumerate(group) if item["language"]==language])
            row["by_language"][language]={"rows":len(indices),
                "speech_accuracy":float(np.mean(pred["speech"][indices]==gold["speech"][indices])),
                "action_accuracy":float(np.mean(pred["action"][indices]==gold["action"][indices]))}
        row["by_category"]={}
        for category in sorted({item.get("category","repair") for item in group}):
            indices=np.asarray([i for i,item in enumerate(group) if item.get("category","repair")==category])
            row["by_category"][category]={"rows":len(indices),
                "speech_accuracy":float(np.mean(pred["speech"][indices]==gold["speech"][indices])),
                "action_accuracy":float(np.mean(pred["action"][indices]==gold["action"][indices]))}
        confusion=Counter((vocab["action"][int(gold["action"][i])],vocab["action"][int(pred["action"][i])])
                          for i in range(len(group)) if pred["action"][i]!=gold["action"][i])
        row["top_action_confusions"]=[{"gold":a,"predicted":b,"count":n} for (a,b),n in confusion.most_common(15)]
        report["partitions"][name]=row
    (OUT/"generalization_gap.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:{key:value for key,value in v.items() if key!="top_action_confusions"}
                      for k,v in report["partitions"].items()},indent=2))


if __name__=="__main__":
    main()
