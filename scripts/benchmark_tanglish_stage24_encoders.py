"""Development-only compact multilingual encoder comparison.

Authored semantic pairs are diagnostic, not an independent acceptance set.
The retrieval probe uses only Stage 2 TRAIN/DEV and inherits synthetic labels.
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path

import numpy as np
import psutil
import torch
import truststore
from fastembed import TextEmbedding
from transformers import AutoModel, AutoTokenizer

from scripts.build_tanglish_semantic_stage2 import BASE
from scripts.evaluate_tanglish_stage21 import input_text, read

ROOT=Path(__file__).resolve().parents[1]
OUT=BASE/"generated/stage24/encoder_benchmark.json"
E5=ROOT/"models/tanglish_stage24/encoders/multilingual-e5-small"
PAIRS=[
    ("Send the second PDF to Naveen","Naveen ku rendaavathu PDF anuppu","Did you send the second PDF to Naveen?","cross_language"),
    ("Forward the latest message to Arun","latest msg Arun kitta forward pannu","Don't forward the latest message to Arun","cross_language"),
    ("Read Naveen's last message","Naveen oda last msg padi","Can you read Naveen's last message?","cross_language"),
    ("Set volume to 40","volume 40 ku maathu","Did you set volume to 40?","cross_language"),
    ("Convert the PDF to Word","PDF ah Word ku maathu","Don't convert the PDF to Word","cross_language"),
    ("Switch to the second Chrome tab","Chrome second tab ku maathu","Did you switch to the second Chrome tab?","cross_language"),
    ("Take a screenshot","screenshot eduthu","Can you take a screenshot?","cross_language"),
    ("Select the second PDF","rendaavathu PDF eduthu","Don't select the second PDF","cross_language"),
    ("Play the song","song podu","Did you play the song?","cross_language"),
    ("Search the web for Atlas","Atlas pathi web la thedu","Can you search the web for Atlas?","cross_language"),
    ("Naveen ku PDF anuppu","Naveen ku PDF anupu","Naveen ku PDF anupadha","phonetic"),
    ("volume 40 ku maathu","volume 40 ku mathu","volume 40 ku maatha venam","phonetic"),
    ("Chrome open pannu","Chrome open panu","Chrome open panna venam","phonetic"),
    ("Naveen kitta PDF anuppu","Naveen kita PDF anupu","Naveen kitta PDF anupitiya?","phonetic"),
    ("send the PDF to Naveen","send PDF to Naveen","did you send the PDF to Naveen?","english_equivalence"),
    ("open the Chrome browser","launch Chrome browser","can Chrome be opened?","english_equivalence"),
    ("turn down the volume","decrease the volume","did you decrease the volume?","english_equivalence"),
    ("show the latest message","display the latest message","don't show the latest message","english_equivalence"),
    ("Naveen ku PDF anuppu","Naveen ku PDF anpu","Naveen ku PDF anupitiya?","asr_like"),
    ("second file select pannu","second file select panu","second file select pannadha","asr_like"),
    ("Chrome tab maathu","Chrome tap maathu","Chrome tab maatha venam","asr_like"),
    ("latest msg kaatu","latest mesg kaatu","latest msg kaatadha","asr_like"),
    ("PDF Word ku maathu","PDF Word ku convert pannu","volume 40 ku maathu","polysemy"),
    ("screenshot eduthu","screen capture pannu","second file eduthu","polysemy"),
    ("song podu","music play pannu","volume 40 podu","polysemy"),
]


def normalize(value):
    value=np.asarray(value,dtype=np.float32)
    return value/np.maximum(np.linalg.norm(value,axis=1,keepdims=True),1e-9)


def fastembed_vectors(name,texts):
    cache=(ROOT/"models/tanglish_stage23/encoders" if "MiniLM-L12-v2" in name
           else ROOT/"models/tanglish_stage24/encoders/fastembed")
    model=TextEmbedding(model_name=name,cache_dir=str(cache),threads=4)
    return normalize(list(model.embed(texts,batch_size=64)))


def e5_vectors(texts):
    tokenizer=AutoTokenizer.from_pretrained(E5,local_files_only=True,use_fast=True)
    model=AutoModel.from_pretrained(E5,local_files_only=True)
    model.eval()
    vectors=[]
    with torch.no_grad():
        for start in range(0,len(texts),32):
            batch=tokenizer(["query: "+x for x in texts[start:start+32]],
                            padding=True,truncation=True,max_length=64,return_tensors="pt")
            hidden=model(**batch).last_hidden_state
            mask=batch["attention_mask"].unsqueeze(-1)
            pooled=(hidden*mask).sum(dim=1)/mask.sum(dim=1)
            vectors.extend(pooled.numpy())
    return normalize(vectors)


def main():
    truststore.inject_into_ssl()
    torch.set_num_threads(4)
    rng=random.Random(2405)
    train=rng.sample(read(BASE/"generated/semantic_stage2/train.jsonl.gz"),500)
    dev=rng.sample(read(BASE/"generated/semantic_stage2/dev.jsonl.gz"),200)
    texts=[item for anchor,positive,negative,_ in PAIRS for item in (anchor,positive,negative)]
    texts += [input_text(r) for r in train+dev]
    process=psutil.Process()
    report={"pairs":len(PAIRS),"train_neighbors":len(train),"dev_queries":len(dev),
            "models":[],"test_opened":False,"sealed_holdout_opened":False}
    choices=[("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
              lambda x:fastembed_vectors("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",x)),
             ("intfloat/multilingual-e5-small",e5_vectors),
             ("minishlab/potion-multilingual-128M",
              lambda x:fastembed_vectors("minishlab/potion-multilingual-128M",x))]
    labels=np.asarray([r["semantic_frame"]["action_concept"] for r in train])
    gold=np.asarray([r["semantic_frame"]["action_concept"] for r in dev])
    for name,encode in choices:
        started=time.perf_counter();before=process.memory_info().rss
        try:
            vectors=encode(texts)
        except Exception as exc:
            report["models"].append({"name":name,"error":str(exc)})
            print(name,"FAILED",str(exc),flush=True)
            continue
        elapsed=time.perf_counter()-started
        n_pairs=len(PAIRS)
        p=vectors[:3*n_pairs].reshape(n_pairs,3,-1)
        positive=np.sum(p[:,0]*p[:,1],axis=1)
        negative=np.sum(p[:,0]*p[:,2],axis=1)
        neighbors=vectors[3*n_pairs:3*n_pairs+len(train)]
        queries=vectors[3*n_pairs+len(train):]
        top=np.argsort(-(queries@neighbors.T),axis=1)[:,:5]
        by_group={}
        for category in sorted({x[3] for x in PAIRS}):
            indices=[i for i,x in enumerate(PAIRS) if x[3]==category]
            by_group[category]={"pairs":len(indices),"positive_above_negative":float(np.mean(positive[indices]>negative[indices])),
                                "mean_margin":float(np.mean(positive[indices]-negative[indices]))}
        row={"name":name,"dim":vectors.shape[1],"seconds_including_load":elapsed,
             "bulk_ms_per_row_including_load":1000*elapsed/len(texts),
             "rss_delta_mb":(process.memory_info().rss-before)/1048576,
             "pair_accuracy":float(np.mean(positive>negative)),"by_pair_group":by_group,
             "action_recall_at_1":float(np.mean(labels[top[:,0]]==gold)),
             "action_recall_at_5":float(np.mean(np.any(labels[top]==gold[:,None],axis=1)))}
        report["models"].append(row)
        print(name,row["pair_accuracy"],row["action_recall_at_1"],flush=True)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":
    main()
