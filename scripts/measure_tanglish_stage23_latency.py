"""Offline batch-one CPU latency sample on development examples."""
from __future__ import annotations

import json
import pickle
import random
import time

import numpy as np
import psutil
import torch
from fastembed import TextEmbedding

from scripts.evaluate_tanglish_stage21 import input_text
from scripts.train_tanglish_stage23_neural import ENCODER, MODEL_DIR, OUT, ROOT, SharedSemanticNet, rows


def percentiles(values):
    return {key:float(np.percentile(values,p)) for key,p in (("p50",50),("p95",95),("p99",99))}


def main():
    _,_,evaluation=rows()
    sample=random.Random(2305).sample(evaluation,min(120,len(evaluation)))
    with (ROOT/"models/tanglish_stage21/candidate_dev_only.pkl").open("rb") as stream:
        old=pickle.load(stream)
    saved=torch.load(MODEL_DIR/"candidate_dev_only.pt",map_location="cpu",weights_only=False)
    net=SharedSemanticNet(saved["vocab"]);net.load_state_dict(saved["weights"]);net.eval()
    started=time.perf_counter()
    encoder=TextEmbedding(model_name=ENCODER,cache_dir=str(MODEL_DIR/"encoders"),threads=4)
    cold_load=(time.perf_counter()-started)*1000
    thresholds=saved["thresholds"]
    process=psutil.Process()
    rss=[process.memory_info().rss]
    fast=[];semantic=[];total=[];escalated=0
    for row in sample:
        text=input_text(row)
        a=time.perf_counter()
        p=float(old["gate"].predict_proba(old["vectorizer"].transform([text]))[0,1])
        b=time.perf_counter()
        if thresholds["fast_no_action"]<p<thresholds["fast_execute"]:
            vector=np.asarray([next(encoder.embed([text]))],dtype=np.float32)
            vector/=np.maximum(np.linalg.norm(vector,axis=1,keepdims=True),1e-9)
            with torch.no_grad():
                net(torch.from_numpy(vector))
            escalated+=1
        c=time.perf_counter()
        fast.append((b-a)*1000)
        if c>b:
            semantic.append((c-b)*1000)
        total.append((c-a)*1000)
        rss.append(process.memory_info().rss)
    report={"rows":len(sample),"cpu":"Windows CPU; ONNX Runtime + PyTorch head",
            "cold_encoder_load_ms":cold_load,"fast_ms":percentiles(fast),
            "semantic_ms":percentiles(semantic) if semantic else None,
            "total_ms":percentiles(total),"escalated_rows":escalated,
            "sample_rss_peak_mb":max(rss)/1048576,
            "gpu_vram_measured":False,"production_integrated":False,
            "test_opened":False,"sealed_holdout_opened":False}
    (OUT/"latency_dev.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
