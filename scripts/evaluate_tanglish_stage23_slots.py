"""Seven-field slot-presence diagnostic on Stage 2.1 repair DEV only.

This is deliberately not a full SemanticFrame or value/span evaluation.
"""
from __future__ import annotations

import json

import numpy as np
import torch

from scripts.train_tanglish_stage23_neural import MODEL_DIR, OUT, SLOTS, SharedSemanticNet, rows


def prf(gold, pred):
    tp=int(np.sum(gold & pred)); fp=int(np.sum(~gold & pred)); fn=int(np.sum(gold & ~pred))
    return {"tp":tp,"fp":fp,"fn":fn,"precision":tp/max(1,tp+fp),
            "recall":tp/max(1,tp+fn),"f1":2*tp/max(1,2*tp+fp+fn)}


def main():
    _,_,evaluation=rows()
    with np.load(OUT/"multilingual_minilm_embeddings.npz") as cached:
        lengths=list(cached["lengths"])
        vector=cached["vectors"][sum(lengths[:2]):]
    if len(vector)!=len(evaluation):
        raise RuntimeError("Embedding cache does not match evaluation partition")
    saved=torch.load(MODEL_DIR/"candidate_dev_only.pt",map_location="cpu",weights_only=False)
    model=SharedSemanticNet(saved["vocab"]);model.load_state_dict(saved["weights"]);model.eval()
    indices=[i for i,row in enumerate(evaluation) if set(SLOTS)<=set(row.get("slots",{}))]
    logits=[]
    with torch.no_grad():
        for batch in np.array_split(vector[indices],max(1,int(np.ceil(len(indices)/512)))):
            output,_=model(torch.from_numpy(batch))
            logits.append(output["slots"].numpy())
    pred=np.concatenate(logits)>0
    gold=np.asarray([[row["slots"][name] is not None for name in SLOTS] for row in (evaluation[i] for i in indices)],dtype=bool)
    report={"scope":"seven supervised slot-presence fields on synthetic repair DEV; no value/span correctness",
            "rows":len(indices),"micro":prf(gold,pred),
            "presence_exact_match":float(np.mean(np.all(gold==pred,axis=1))),
            "per_slot":{name:prf(gold[:,i],pred[:,i]) for i,name in enumerate(SLOTS)},
            "full_semantic_frame_exact_match":None,"slot_value_f1":None,
            "test_opened":False,"sealed_holdout_opened":False}
    (OUT/"slot_presence_dev.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"rows":report["rows"],"micro":report["micro"],
                      "presence_exact_match":report["presence_exact_match"]},indent=2))


if __name__=="__main__":
    main()
