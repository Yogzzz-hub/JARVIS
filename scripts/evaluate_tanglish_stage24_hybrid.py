"""Offline lexical + pretrained semantic candidate union with structured reranking.

The 18 authored Stage 2.2 cases have oracle semantic fields and are too small
for acceptance. This module never invokes a capability or availability check.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

from jarvis.core.capabilities.registry import CapabilityRegistry
from jarvis.core.capabilities.retrieval import CapabilityRetriever
from scripts.build_tanglish_semantic_stage2 import BASE
from scripts.evaluate_tanglish_stage22_capabilities import CASES, metrics

ROOT=Path(__file__).resolve().parents[1]
MODEL=ROOT/"models/tanglish_stage24/encoders/multilingual-e5-small"
OUT=BASE/"generated/stage24/capability_hybrid_18.json"


class HybridRanker:
    def __init__(self):
        self.registry=CapabilityRegistry()
        self.lexical=CapabilityRetriever(self.registry)
        self.caps=self.registry.list_all()
        self.tokenizer=AutoTokenizer.from_pretrained(str(MODEL),local_files_only=True,use_fast=True)
        self.model=AutoModel.from_pretrained(str(MODEL),local_files_only=True)
        self.model.eval()
        descriptions=[f"{cap.id.replace('.', ' ')}. {cap.description}. "
                      +"; ".join(cap.keywords+cap.examples) for cap in self.caps]
        self.cap_vectors=self.embed(descriptions,prefix="passage: ")

    def embed(self,texts,prefix="query: "):
        vectors=[]
        with torch.no_grad():
            for start in range(0,len(texts),32):
                batch=self.tokenizer([prefix+x for x in texts[start:start+32]],
                                     padding=True,truncation=True,max_length=96,return_tensors="pt")
                hidden=self.model(**batch).last_hidden_state
                mask=batch["attention_mask"].unsqueeze(-1)
                pooled=(hidden*mask).sum(1)/mask.sum(1)
                vectors.extend(pooled.numpy())
        value=np.asarray(vectors,dtype=np.float32)
        return value/np.maximum(np.linalg.norm(value,axis=1,keepdims=True),1e-9)

    def rank(self,query,action,domain,resource,slots,excluded_families=()):
        lexical=self.lexical.retrieve(query,top_k=len(self.caps),min_score=0)
        lexical_scores={cap.id:score for cap,score in lexical}
        max_lex=max(lexical_scores.values(),default=1) or 1
        similarity=(self.embed([query])@self.cap_vectors.T)[0]
        semantic_order=np.argsort(-similarity)
        candidates={cap.id for cap,_ in lexical[:20]}
        candidates.update(self.caps[i].id for i in semantic_order[:20])
        scored=[]
        for index,cap in enumerate(self.caps):
            if cap.id not in candidates:
                continue
            family=cap.get_family().casefold()
            if family in {x.casefold() for x in excluded_families}:
                continue
            description=(cap.description+" "+" ".join(cap.keywords)).casefold()
            pieces=set(cap.id.replace(".","_").casefold().split("_"))
            action_match=action.casefold() in pieces or action.casefold() in description.split()
            domain_match=domain.casefold() in {family,cap.category.value.casefold(),cap.id.split(".")[0]}
            resource_match=resource.casefold() in description or resource.casefold() in pieces
            available={x.casefold() for x in slots}
            aliases={"application":"name","recipient":"to","file":"path"}
            available|={aliases[x] for x in list(available) if x in aliases}
            required={x.casefold() for x in cap.required_slots}
            score=1.5*math.log1p(max(0.0,lexical_scores.get(cap.id,0))/max_lex)
            score+=1.5*float(similarity[index])
            score+=3.0 if domain_match else -1.5
            score+=2.0 if action_match else 0.0
            score+=.5 if resource_match else 0.0
            score+=.4*len(required&available)-.8*len(required-available)
            # Availability remains unknown offline; risk is metadata, not intent truth.
            scored.append((cap.id,score))
        scored.sort(key=lambda item:(-item[1],item[0]))
        return [cap_id for cap_id,_ in scored], [cap.id for cap,_ in lexical],


def main():
    torch.set_num_threads(4)
    start=time.perf_counter();ranker=HybridRanker()
    hybrid=[];lexical=[]
    for case in CASES:
        ranked,base=ranker.rank(*case[:5])
        hybrid.append(ranked);lexical.append(base)
    gold=[case[-1] for case in CASES]
    assert all(ranker.registry.get(cap_id) is not None for cap_id in gold)
    result={"scope":"18 authored oracle-frame confusion cases; no independent 1,500-case benchmark",
            "registry_capabilities":len(ranker.caps),"candidate_union_topk":20,
            "lexical":metrics(lexical,gold),"hybrid":metrics(hybrid,gold),
            "cases":[{"query":case[0],"gold":case[-1],"lexical_top1":base[0],
                      "hybrid_top1":ranked[0] if ranked else None}
                     for case,ranked,base in zip(CASES,hybrid,lexical)],
            "seconds_including_model_load":time.perf_counter()-start,
            "retrieval_projection":"pretrained E5 embedding; separate from classifier heads",
            "availability_checked":False,"executed_capabilities":False,
            "test_opened":False,"sealed_holdout_opened":False}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"lexical_r1":result["lexical"]["recall_at_1"],
                      "hybrid_r1":result["hybrid"]["recall_at_1"],
                      "hybrid_r5":result["hybrid"]["recall_at_5"]},indent=2))


if __name__=="__main__":
    main()
