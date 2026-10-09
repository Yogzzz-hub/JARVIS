"""Registry-derived development retrieval probe; no capability is invoked.

The generated queries paraphrase registry examples. They are useful for coverage
and regression checks but are not independent natural-language gold labels.
"""
from __future__ import annotations

import json
import random
from collections import Counter, defaultdict

import numpy as np
import torch
from fastembed import TextEmbedding

from jarvis.core.capabilities.registry import CapabilityRegistry
from jarvis.core.capabilities.retrieval import CapabilityRetriever
from scripts.build_tanglish_semantic_stage2 import BASE
from scripts.evaluate_tanglish_stage22_capabilities import CASES, metrics, rank
from scripts.train_tanglish_stage23_neural import ENCODER, MODEL_DIR, OUT, SharedSemanticNet


def variants(example):
    q=example.strip().rstrip(".")
    return [q, f"please {q}", f"JARVIS, {q}", f"{q} for me"]


def encode(model,texts):
    values=np.asarray(list(model.embed(texts,batch_size=64)),dtype=np.float32)
    values/=np.maximum(np.linalg.norm(values,axis=1,keepdims=True),1e-9)
    return values


def main():
    registry=CapabilityRegistry(); caps=registry.list_all()
    rng=random.Random(2304)
    examples=[]
    for cap in caps:
        for source in cap.examples:
            for text in variants(source):
                examples.append((text,cap.id,cap.get_family()))
    # Preserve at least one item from each real registry capability and family.
    by_cap=defaultdict(list)
    for item in examples:
        by_cap[item[1]].append(item)
    chosen=[rng.choice(items) for items in by_cap.values()]
    remaining=[item for item in examples if item not in chosen]
    chosen+=rng.sample(remaining,min(1050-len(chosen),len(remaining)))
    rng.shuffle(chosen)
    gold=[x[1] for x in chosen]
    if any(registry.get(item) is None for item in gold):
        raise RuntimeError("A gold ID is absent from CapabilityRegistry")
    retriever=CapabilityRetriever(registry)
    baseline=[[cap.id for cap,_ in retriever.retrieve(q,top_k=len(caps),min_score=0)] for q,_,_ in chosen]
    encoder=TextEmbedding(model_name=ENCODER,cache_dir=str(MODEL_DIR/"encoders"),threads=4)
    cap_text=[f"{cap.id.replace('.', ' ')}. {cap.description}. {'; '.join(cap.examples)}" for cap in caps]
    all_vectors=encode(encoder,[x[0] for x in chosen]+cap_text)
    qvec=all_vectors[:len(chosen)]; cvec=all_vectors[len(chosen):]
    base_similarity=qvec@cvec.T
    ids=np.asarray([cap.id for cap in caps])
    semantic=[ids[np.argsort(-row)].tolist() for row in base_similarity]
    neural=None
    checkpoint=MODEL_DIR/"candidate_dev_only.pt"
    if checkpoint.exists():
        saved=torch.load(checkpoint,map_location="cpu",weights_only=False)
        net=SharedSemanticNet(saved["vocab"]);net.load_state_dict(saved["weights"]);net.eval()
        with torch.no_grad():
            _,qz=net(torch.from_numpy(qvec));_,cz=net(torch.from_numpy(cvec))
            qz=torch.nn.functional.normalize(qz,dim=1).numpy()
            cz=torch.nn.functional.normalize(cz,dim=1).numpy()
        neural=[ids[np.argsort(-row)].tolist() for row in qz@cz.T]
    authored=[rank(case,registry,retriever) for case in CASES]
    families=sorted({cap.get_family() for cap in caps})
    result={"registry_capabilities":len(caps),"registry_families":families,
            "derived_cases":len(chosen),"label_provenance":"inherited from CapabilityRegistry.examples",
            "independence_warning":"Queries paraphrase examples also indexed by the retriever; these scores are optimistic and are not acceptance evidence.",
            "lexical":metrics(baseline,gold),"pretrained_embedding":metrics(semantic,gold),
            "neural_projection":metrics(neural,gold) if neural else None,
            "per_family_top1":{},"authored_confusions":{"cases":len(CASES),
                "lexical":metrics([x[1] for x in authored],[c[-1] for c in CASES]),
                "frame_aware":metrics([x[0] for x in authored],[c[-1] for c in CASES])},
            "executed_capabilities":False,"live_availability_checked":False}
    family_of={cap.id:cap.get_family() for cap in caps}
    result["family_confusions"]={}
    for name,ranks in (("lexical",baseline),("pretrained",semantic),("neural",neural)):
        if ranks is None:
            continue
        confusion=Counter((chosen[i][2],family_of.get(row[0],"UNKNOWN"))
                          for i,row in enumerate(ranks) if row and row[0]!=gold[i])
        result["family_confusions"][name]=[
            {"gold_family":true,"predicted_family":pred,"errors":count}
            for (true,pred),count in confusion.most_common(20)]
    for family in families:
        at=[i for i,x in enumerate(chosen) if x[2]==family]
        result["per_family_top1"][family]={"cases":len(at),
            "lexical":sum(baseline[i] and baseline[i][0]==gold[i] for i in at)/len(at),
            "pretrained":sum(semantic[i][0]==gold[i] for i in at)/len(at),
            "neural":sum(neural[i][0]==gold[i] for i in at)/len(at) if neural else None}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"capability_dev.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"derived_cases":len(chosen),"families":len(families),
                      "lexical_r1":result["lexical"]["recall_at_1"],
                      "embedding_r1":result["pretrained_embedding"]["recall_at_1"],
                      "neural_r1":result["neural_projection"]["recall_at_1"] if neural else None},indent=2))


if __name__=="__main__":
    main()
