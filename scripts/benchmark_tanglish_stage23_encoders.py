"""Development-only pretrained encoder comparison; does not read test/holdout."""
from __future__ import annotations

import gzip
import json
import random
import statistics
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import truststore
from fastembed import TextEmbedding

from scripts.build_tanglish_semantic_stage2 import BASE
from scripts.evaluate_tanglish_stage21 import input_text, read

ROOT = Path(__file__).resolve().parents[1]
OUT = BASE / "generated/stage23"
MODELS = [
    ("sentence-transformers/all-MiniLM-L6-v2", "models/tanglish_stage2/encoders"),
    ("BAAI/bge-small-en-v1.5", "models/tanglish_stage2/encoders"),
    ("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", "models/tanglish_stage23/encoders"),
]


def sample(rows, n, seed):
    rng = random.Random(seed)
    if len(rows) <= n:
        return rows
    return rng.sample(rows, n)


def repair_pairs(limit=200):
    groups = defaultdict(dict)
    for name in ("dev_no_action", "dev_command"):
        with gzip.open(BASE / f"generated/stage21/{name}.jsonl.gz", "rt", encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                groups[row["pair_family"]][row["speech_act"]] = row["text"]
    result = []
    for family, acts in groups.items():
        if "COMMAND" not in acts:
            continue
        negative = next((acts[k] for k in ("NEGATED_COMMAND","CAPABILITY_QUERY","QUESTION","STATEMENT") if k in acts),None)
        if negative:
            anchor = acts["COMMAND"]
            positive = anchor.replace("bro ", "").replace("please ", "").replace("JARVIS ", "")
            # A lightweight polite variant stays in the same semantic program.
            positive = "please " + positive
            result.append((anchor,positive,negative))
    return sample(result,limit,233)


def encode(model,texts,batch=64):
    value=np.asarray(list(model.embed(texts,batch_size=batch)),dtype=np.float32)
    value/=np.maximum(np.linalg.norm(value,axis=1,keepdims=True),1e-9)
    return value


def main():
    truststore.inject_into_ssl()
    train=sample(read(BASE / "generated/semantic_stage2/train.jsonl.gz"),800,231)
    dev=sample(read(BASE / "generated/semantic_stage2/dev.jsonl.gz"),250,232)
    pairs=repair_pairs()
    texts=[input_text(r) for r in train+dev]+[x for group in pairs for x in group]
    report={"train_neighbors":len(train),"dev_queries":len(dev),"hard_pairs":len(pairs),
            "models":[],"test_opened":False,"sealed_holdout_opened":False}
    for name,cache in MODELS:
        started=time.perf_counter()
        model=TextEmbedding(model_name=name,cache_dir=cache,threads=4)
        load_ms=(time.perf_counter()-started)*1000
        started=time.perf_counter()
        vec=encode(model,texts)
        bulk_ms=(time.perf_counter()-started)*1000/len(texts)
        neighbors=vec[:len(train)]
        queries=vec[len(train):len(train)+len(dev)]
        similarity=queries@neighbors.T
        top=np.argsort(-similarity,axis=1)[:,:5]
        labels=np.array([r["semantic_frame"]["action_concept"] for r in train])
        gold=np.array([r["semantic_frame"]["action_concept"] for r in dev])
        pair_vec=vec[len(train)+len(dev):].reshape(len(pairs),3,-1)
        positive=np.sum(pair_vec[:,0,:]*pair_vec[:,1,:],axis=1)
        negative=np.sum(pair_vec[:,0,:]*pair_vec[:,2,:],axis=1)
        warm=[]
        for text in texts[len(train):len(train)+30]:
            t=time.perf_counter(); next(model.embed([text])); warm.append((time.perf_counter()-t)*1000)
        report["models"].append({"name":name,"dim":int(vec.shape[1]),"cold_load_ms":load_ms,
            "bulk_ms_per_row":bulk_ms,"warm_batch1_p50_ms":float(np.percentile(warm,50)),
            "warm_batch1_p95_ms":float(np.percentile(warm,95)),
            "action_recall_at_1":float(np.mean(labels[top[:,0]]==gold)),
            "action_recall_at_5":float(np.mean(np.any(labels[top]==gold[:,None],axis=1))),
            "hard_pair_accuracy":float(np.mean(positive>negative)),
            "hard_pair_mean_margin":float(np.mean(positive-negative))})
        print(name,report["models"][-1]["action_recall_at_1"],report["models"][-1]["hard_pair_accuracy"],flush=True)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"encoder_benchmark.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":
    main()
