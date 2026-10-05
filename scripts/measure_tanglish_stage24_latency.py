"""Offline warm batch-one encoder timing on TRAIN/DEV text only."""
from __future__ import annotations

import json
import random
import time
from pathlib import Path

import numpy as np
import psutil
import torch
from fastembed import TextEmbedding
from transformers import AutoModel, AutoTokenizer

from scripts.build_tanglish_semantic_stage2 import BASE
from scripts.evaluate_tanglish_stage21 import input_text, read

ROOT=Path(__file__).resolve().parents[1]
E5=ROOT/"models/tanglish_stage24/encoders/multilingual-e5-small"
OUT=BASE/"generated/stage24/latency_dev.json"


def quantiles(values):
    return {label:float(np.percentile(values,p)) for label,p in (("p50",50),("p95",95),("p99",99))}


def e5_timing(texts,device):
    process=psutil.Process();started=time.perf_counter()
    tokenizer=AutoTokenizer.from_pretrained(str(E5),local_files_only=True,use_fast=True)
    model=AutoModel.from_pretrained(str(E5),local_files_only=True).to(device)
    model.eval()
    cold=(time.perf_counter()-started)*1000
    times=[];rss=[]
    if device=="cuda":
        torch.cuda.reset_peak_memory_stats()
    with torch.no_grad():
        for text in texts:
            batch=tokenizer("query: "+text,return_tensors="pt",truncation=True,max_length=64).to(device)
            if device=="cuda":
                torch.cuda.synchronize()
            start=time.perf_counter()
            model(**batch)
            if device=="cuda":
                torch.cuda.synchronize()
            times.append((time.perf_counter()-start)*1000)
            rss.append(process.memory_info().rss)
    result={"cold_load_ms":cold,"warm_forward_ms":quantiles(times[5:]),
            "rss_peak_mb":max(rss)/1048576,
            "vram_peak_mb":torch.cuda.max_memory_allocated()/1048576 if device=="cuda" else None}
    del model
    if device=="cuda":
        torch.cuda.empty_cache()
    return result


def fastembed_timing(name,texts,cache):
    process=psutil.Process();started=time.perf_counter()
    model=TextEmbedding(model_name=name,cache_dir=str(cache),threads=4)
    cold=(time.perf_counter()-started)*1000
    times=[];rss=[]
    for text in texts:
        start=time.perf_counter()
        next(model.embed([text]))
        times.append((time.perf_counter()-start)*1000)
        rss.append(process.memory_info().rss)
    return {"cold_load_ms":cold,"warm_forward_ms":quantiles(times[5:]),
            "rss_peak_mb":max(rss)/1048576,"vram_peak_mb":None}


def main():
    torch.set_num_threads(4)
    rng=random.Random(2407)
    rows=rng.sample(read(BASE/"generated/semantic_stage2/dev.jsonl.gz"),60)
    texts=[input_text(row) for row in rows]
    report={"rows":len(texts),"note":"base encoder only; no Stage 2.4 model was promoted",
            "models":{},"test_opened":False,"sealed_holdout_opened":False}
    report["models"]["multilingual_minilm_cpu"]=fastembed_timing(
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",texts,
        ROOT/"models/tanglish_stage23/encoders")
    report["models"]["potion_multilingual_cpu"]=fastembed_timing(
        "minishlab/potion-multilingual-128M",texts,
        ROOT/"models/tanglish_stage24/encoders/fastembed")
    report["models"]["e5_small_cpu"]=e5_timing(texts,"cpu")
    if torch.cuda.is_available():
        report["models"]["e5_small_gpu"]=e5_timing(texts,"cuda")
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v["warm_forward_ms"] for k,v in report["models"].items()},indent=2))


if __name__=="__main__":
    main()
