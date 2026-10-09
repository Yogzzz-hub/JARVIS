"""Mandatory tiny-overfit gate for a trainable hierarchical encoder.

Uses only the 48 authored TRAIN diagnostics. This deliberately measures fit,
not generalization; no test, holdout, capability, or executor is accessed.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import psutil
import torch
from torch import nn
from torch.nn import functional as F
from transformers import AutoModel, AutoTokenizer

from scripts.build_tanglish_semantic_stage2 import BASE

ROOT=Path(__file__).resolve().parents[1]
MODEL=ROOT/"models/tanglish_stage24/encoders/multilingual-e5-small"
TRAIN=BASE/"generated/stage24/tiny_overfit_train.jsonl"
OUT=BASE/"generated/stage24"
MAX_LENGTH=64


class HierarchicalFrameNet(nn.Module):
    def __init__(self,vocab):
        super().__init__()
        self.encoder=AutoModel.from_pretrained(str(MODEL),local_files_only=True)
        size=self.encoder.config.hidden_size
        self.heads=nn.ModuleDict({
            "speech_coarse":nn.Linear(size,len(vocab["speech_coarse"])),
            "speech_act":nn.Linear(size,len(vocab["speech_act"])),
            "action_family":nn.Linear(size,len(vocab["action_family"])),
            "action_concept":nn.Linear(size,len(vocab["action_concept"])),
            "should_execute":nn.Linear(size,2),
            "negated":nn.Linear(size,2),
            "slot_tags":nn.Linear(size,1+2*len(vocab["slot_types"])),
        })

    def forward(self,ids,mask):
        hidden=self.encoder(input_ids=ids,attention_mask=mask).last_hidden_state
        pooled=(hidden*mask.unsqueeze(-1)).sum(1)/mask.sum(1,keepdim=True)
        output={name:head(hidden if name=="slot_tags" else pooled)
                for name,head in self.heads.items()}
        return output


class LoRALinear(nn.Module):
    def __init__(self,base:nn.Linear,rank:int=8,alpha:float=16.0):
        super().__init__()
        self.base=base
        self.down=nn.Linear(base.in_features,rank,bias=False)
        self.up=nn.Linear(rank,base.out_features,bias=False)
        nn.init.kaiming_uniform_(self.down.weight,a=5**.5)
        nn.init.zeros_(self.up.weight)
        self.scale=alpha/rank

    def forward(self,x):
        return self.base(x)+self.up(self.down(x))*self.scale


def dataset():
    rows=[json.loads(line) for line in TRAIN.open(encoding="utf-8")]
    vocab={key:sorted({row[key] for row in rows}) for key in
           ("speech_coarse","speech_act","action_family","action_concept")}
    vocab["slot_types"]=sorted({slot for row in rows for slot in row["slots"]})
    tokenizer=AutoTokenizer.from_pretrained(str(MODEL),local_files_only=True,use_fast=True)
    tokens=tokenizer(["query: "+r["text"] for r in rows],padding="max_length",
                     truncation=True,max_length=MAX_LENGTH,return_offsets_mapping=True,return_tensors="pt")
    prefix=len("query: ")
    slot_tags=torch.full(tokens["input_ids"].shape,-100,dtype=torch.long)
    for i,row in enumerate(rows):
        for j,(start,end) in enumerate(tokens["offset_mapping"][i].tolist()):
            if start==end or not tokens["attention_mask"][i,j]:
                continue
            slot_tags[i,j]=0
            for slot,span in row["slots"].items():
                left,right=span["start"]+prefix,span["end"]+prefix
                if start<right and end>left:
                    index=vocab["slot_types"].index(slot)
                    prior=slot_tags[i,:j]
                    slot_tags[i,j]=2+2*index if torch.any(prior==1+2*index) or torch.any(prior==2+2*index) else 1+2*index
                    break
        for slot,span in row["slots"].items():
            index=vocab["slot_types"].index(slot)
            if not torch.any(slot_tags[i]==1+2*index):
                raise ValueError(f"Unaligned slot: {i} {slot} {span}")
    labels={key:torch.tensor([vocab[key].index(row[key]) for row in rows])
            for key in ("speech_coarse","speech_act","action_family","action_concept")}
    labels["should_execute"]=torch.tensor([int(r["should_execute"]) for r in rows])
    labels["negated"]=torch.tensor([int(r["negated"]) for r in rows])
    labels["slot_tags"]=slot_tags
    return rows,vocab,tokens,labels


def choose_trainable(model,strategy):
    if strategy=="full":
        return
    for parameter in model.encoder.parameters():
        parameter.requires_grad=False
    if strategy=="last2":
        for layer in model.encoder.encoder.layer[-2:]:
            for parameter in layer.parameters():
                parameter.requires_grad=True
    elif strategy=="lora":
        for layer in model.encoder.encoder.layer[-4:]:
            layer.attention.self.query=LoRALinear(layer.attention.self.query)
            layer.attention.self.value=LoRALinear(layer.attention.self.value)
    elif strategy!="frozen":
        raise ValueError(strategy)


def accuracy(model,tokens,labels,device):
    model.eval()
    predictions={key:[] for key in labels}
    with torch.no_grad():
        for ids in range(0,len(tokens["input_ids"]),8):
            output=model(tokens["input_ids"][ids:ids+8].to(device),tokens["attention_mask"][ids:ids+8].to(device))
            for key in predictions:
                predictions[key].append(output[key].argmax(-1).cpu())
    pred={key:torch.cat(value) for key,value in predictions.items()}
    result={key:float((pred[key]==gold).float().mean()) for key,gold in labels.items() if key!="slot_tags"}
    mask=labels["slot_tags"]!=-100
    gold=labels["slot_tags"][mask];guess=pred["slot_tags"][mask]
    result["slot_token_accuracy"]=float((guess==gold).float().mean())
    result["slot_sequence_exact"]=float(((pred["slot_tags"]==labels["slot_tags"])|~mask).all(1).float().mean())
    # Span-positive micro F1 (outside-token accuracy would hide missed spans).
    positive_gold=(gold>0);positive_pred=(guess>0)
    tp=int((positive_gold&positive_pred&(guess==gold)).sum())
    fp=int((positive_pred&~(positive_gold&(guess==gold))).sum())
    fn=int((positive_gold&~(positive_pred&(guess==gold))).sum())
    result["slot_positive_f1"]=2*tp/max(1,2*tp+fp+fn)
    return result


def slot_errors(model,tokens,labels,rows,device):
    model.eval();predictions=[]
    with torch.no_grad():
        for start in range(0,len(rows),8):
            output=model(tokens["input_ids"][start:start+8].to(device),
                         tokens["attention_mask"][start:start+8].to(device))
            predictions.extend(output["slot_tags"].argmax(-1).cpu().tolist())
    problems=[]
    for i,row in enumerate(rows):
        valid=labels["slot_tags"][i]!=-100
        wrong=(torch.tensor(predictions[i])!=labels["slot_tags"][i])&valid
        if not torch.any(wrong):
            continue
        differences=[]
        for j in torch.nonzero(wrong).flatten().tolist():
            start,end=tokens["offset_mapping"][i,j].tolist()
            differences.append({"offset":[start,end],"gold":int(labels["slot_tags"][i,j]),
                                "predicted":int(predictions[i][j])})
        problems.append({"row":i,"text":row["text"],"differences":differences})
    return problems


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--strategy",choices=("frozen","last2","lora","full"),default="last2")
    parser.add_argument("--epochs",type=int,default=20)
    args=parser.parse_args()
    random.seed(2406);np.random.seed(2406);torch.manual_seed(2406)
    torch.set_num_threads(4)
    rows,vocab,tokens,labels=dataset()
    device="cuda" if torch.cuda.is_available() else "cpu"
    model=HierarchicalFrameNet(vocab)
    choose_trainable(model,args.strategy)
    model.to(device)
    if device=="cuda":
        torch.cuda.reset_peak_memory_stats()
    head_params=[p for p in model.heads.parameters() if p.requires_grad]
    encoder_params=[p for p in model.encoder.parameters() if p.requires_grad]
    optimizer=torch.optim.AdamW([{"params":encoder_params,"lr":3e-5},
                                 {"params":head_params,"lr":8e-4}],weight_decay=.01)
    slot_weights=torch.full((1+2*len(vocab["slot_types"]),),4.0,device=device)
    slot_weights[0]=.15
    process=psutil.Process();rss=[];history=[]
    started=time.perf_counter()
    for epoch in range(args.epochs):
        model.train();order=torch.randperm(len(rows)).tolist();losses=[]
        for start in range(0,len(order),4):
            take=order[start:start+4]
            output=model(tokens["input_ids"][take].to(device),tokens["attention_mask"][take].to(device))
            loss=0
            for key,weight in (("speech_coarse",.5),("speech_act",1.0),("action_family",.5),
                               ("action_concept",1.0),("should_execute",.5),("negated",.3)):
                loss=loss+weight*F.cross_entropy(output[key],labels[key][take].to(device))
            loss=loss+2*F.cross_entropy(output["slot_tags"].reshape(-1,output["slot_tags"].shape[-1]),
                                        labels["slot_tags"][take].reshape(-1).to(device),
                                        weight=slot_weights,ignore_index=-100)
            optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);optimizer.step()
            losses.append(float(loss.detach()))
        metrics=accuracy(model,tokens,labels,device)
        item={"epoch":epoch+1,"loss":float(np.mean(losses)),**metrics}
        history.append(item);rss.append(process.memory_info().rss)
        print(f"epoch {epoch+1}: speech={metrics['speech_act']:.3f} action={metrics['action_concept']:.3f} slotF1={metrics['slot_positive_f1']:.3f} slotExact={metrics['slot_sequence_exact']:.3f}",flush=True)
        if all(metrics[key]>=.98 for key in ("speech_act","action_concept","slot_positive_f1","slot_sequence_exact")):
            break
    report={"strategy":args.strategy,"base_encoder":"intfloat/multilingual-e5-small",
            "base_revision":"614241f622f53c4eeff9890bdc4f31cfecc418b3",
            "rows":len(rows),"epochs":len(history),"device":device,
            "trainable_parameters":sum(p.numel() for p in model.parameters() if p.requires_grad),
            "total_parameters":sum(p.numel() for p in model.parameters()),
            "history":history,"near_perfect_fit":all(history[-1][key]>=.98 for key in
                    ("speech_act","action_concept","slot_positive_f1","slot_sequence_exact")),
            "elapsed_seconds":time.perf_counter()-started,
            "peak_rss_mb":max(rss)/1048576 if rss else None,
            "peak_vram_mb":torch.cuda.max_memory_allocated()/1048576 if device=="cuda" else None,
            "test_opened":False,"sealed_holdout_opened":False,"production_connected":False}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/f"tiny_overfit_{args.strategy}.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    (OUT/f"tiny_overfit_{args.strategy}_errors.json").write_text(
        json.dumps(slot_errors(model,tokens,labels,rows,device),indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("strategy","near_perfect_fit","epochs","elapsed_seconds","peak_rss_mb","peak_vram_mb")}),flush=True)


if __name__=="__main__":
    main()
