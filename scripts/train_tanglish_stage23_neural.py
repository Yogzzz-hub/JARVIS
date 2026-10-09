"""Offline Stage 2.3 neural probe. Reads train/dev only; never invokes capabilities."""
from __future__ import annotations

import json
import pickle
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from fastembed import TextEmbedding
from sklearn.metrics import confusion_matrix
from torch import nn
from torch.nn import functional as F

from scripts.build_tanglish_semantic_stage2 import BASE
from scripts.build_tanglish_stage21_repair import ACTION_MAP, OUT as REPAIR
from scripts.evaluate_tanglish_stage21 import input_text, legacy, read
from scripts.evaluate_tanglish_stage22 import apply_negation_guard, dev_partition, fast_thresholds, rates

ROOT = Path(__file__).resolve().parents[1]
OUT = BASE / "generated/stage23"
MODEL_DIR = ROOT / "models/tanglish_stage23"
ENCODER = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
SLOTS = ("target", "recipient", "ordinal", "file_type", "application", "source", "destination")
SEED = 2303


def rows():
    rng = random.Random(SEED)
    old = [legacy(x) for x in read(BASE / "generated/semantic_stage2/train.jsonl.gz")]
    repair = read(REPAIR / "train.jsonl.gz")
    # A bounded, stratified neural experiment; the unused train rows remain eligible for a later run.
    groups = defaultdict(list)
    for row in old:
        groups[(row["category"], bool(row["should_act"]))].append(row)
    old_sample = []
    for group in groups.values():
        old_sample += rng.sample(group, min(len(group), max(50, round(3500 * len(group) / len(old)))))
    rng.shuffle(repair)
    repair_sample = repair[:5000]
    train = old_sample + repair_sample
    dev = [legacy(x) for x in read(BASE / "generated/semantic_stage2/dev.jsonl.gz")]
    dev += read(REPAIR / "dev_no_action.jsonl.gz") + read(REPAIR / "dev_command.jsonl.gz")
    return train, [r for r in dev if dev_partition(r) == 0], [r for r in dev if dev_partition(r) == 1]


def cached_embeddings(train, cal, evaluation):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "multilingual_minilm_embeddings.npz"
    groups = (train, cal, evaluation)
    lengths = [len(x) for x in groups]
    if path.exists():
        with np.load(path) as saved:
            if list(saved["lengths"]) == lengths:
                vec = saved["vectors"]
                return np.split(vec, np.cumsum(lengths)[:-1])
    model = TextEmbedding(model_name=ENCODER, cache_dir=str(MODEL_DIR / "encoders"), threads=4)
    texts = [input_text(r) for group in groups for r in group]
    start = time.perf_counter()
    vec = np.asarray(list(model.embed(texts, batch_size=64)), dtype=np.float32)
    vec /= np.maximum(np.linalg.norm(vec, axis=1, keepdims=True), 1e-9)
    np.savez_compressed(path, vectors=vec, lengths=np.asarray(lengths))
    print(f"Embedded {len(texts)} train/dev rows in {time.perf_counter()-start:.1f}s", flush=True)
    return np.split(vec, np.cumsum(lengths)[:-1])


def labels(groups):
    speech = sorted({r["speech_act"] for g in groups for r in g})
    action = sorted({r["action_concept"] for g in groups for r in g})
    domain = sorted({r.get("domain") or ACTION_MAP.get(r["action_concept"], ("unknown",))[0]
                     for g in groups for r in g})
    vocab = {"speech": speech, "action": action, "domain": domain}
    maps = {k: {v: i for i, v in enumerate(values)} for k, values in vocab.items()}

    def encode(rows):
        result = {"act": np.asarray([int(r["should_act"]) for r in rows], dtype=np.int64)}
        for key, rowkey in (("speech", "speech_act"), ("action", "action_concept")):
            result[key] = np.asarray([maps[key][r[rowkey]] for r in rows], dtype=np.int64)
        result["domain"] = np.asarray([maps["domain"][r.get("domain") or ACTION_MAP.get(r["action_concept"], ("unknown",))[0]] for r in rows], dtype=np.int64)
        result["negation"] = np.asarray([int(r["speech_act"] == "NEGATED_COMMAND") for r in rows], dtype=np.int64)
        result["correction"] = np.asarray([int(r["speech_act"] == "CORRECTION") for r in rows], dtype=np.int64)
        result["context"] = np.asarray([int(bool(r["previous_turns"])) for r in rows], dtype=np.int64)
        result["slots"] = np.asarray([[float(r.get("slots", {}).get(name) is not None) for name in SLOTS] for r in rows], dtype=np.float32)
        return result
    return vocab, [encode(g) for g in groups]


class SharedSemanticNet(nn.Module):
    def __init__(self, vocab):
        super().__init__()
        self.shared = nn.Sequential(nn.Linear(384, 256), nn.GELU(), nn.Dropout(.12), nn.Linear(256, 128), nn.GELU())
        self.heads = nn.ModuleDict({k: nn.Linear(128, n) for k, n in {
            "act": 2, "speech": len(vocab["speech"]), "action": len(vocab["action"]),
            "domain": len(vocab["domain"]), "negation": 2, "correction": 2,
            "context": 2, "slots": len(SLOTS)}.items()})

    def forward(self, x):
        z = self.shared(x)
        return {key: head(z) for key, head in self.heads.items()}, z


def pair_indices(rows):
    rng=random.Random(SEED)
    families = defaultdict(lambda: defaultdict(list))
    for i, row in enumerate(rows):
        if "pair_family" in row:
            families[row["pair_family"]][row["speech_act"]].append(i)
    pairs = []
    for acts in families.values():
        commands = acts.get("COMMAND", [])
        negatives = sum((acts.get(k, []) for k in ("NEGATED_COMMAND", "CAPABILITY_QUERY", "QUESTION", "STATEMENT")), [])
        if commands and negatives:
            for command in commands:
                pairs.append((command, rng.choice(negatives)))
    return pairs


def positive_pairs(rows, pairs):
    rng=random.Random(SEED)
    substitutions=((r"\banuppu\b","anupu"),(r"\banupu\b","anuppu"),
                   (r"\bpannu\b","pannunga"),(r"\bmaathu\b","mathu"),
                   (r"\bvenam\b","vendam"),(r"\bkaatu\b","kaattu"))
    selected=rng.sample(pairs,min(600,len(pairs)))
    records=[]
    for anchor,negative in selected:
        original=rows[anchor]["text"]
        variant=original
        for pattern,replacement in substitutions:
            updated=re.sub(pattern,replacement,variant,flags=re.I)
            if updated!=variant:
                variant=updated
                break
        if variant==original:
            variant="please "+original.removeprefix("bro ").removeprefix("please ")
        records.append((anchor,variant,negative))
    return records


def cached_positives(rows, records):
    path=OUT/"multilingual_minilm_positive_pairs.npz"
    if path.exists():
        with np.load(path) as saved:
            if len(saved["vectors"])==len(records):
                return saved["vectors"]
    model=TextEmbedding(model_name=ENCODER,cache_dir=str(MODEL_DIR/"encoders"),threads=4)
    texts=[]
    for anchor,variant,_ in records:
        item=dict(rows[anchor]);item["text"]=variant
        texts.append(input_text(item))
    vectors=np.asarray(list(model.embed(texts,batch_size=64)),dtype=np.float32)
    vectors/=np.maximum(np.linalg.norm(vectors,axis=1,keepdims=True),1e-9)
    np.savez_compressed(path,vectors=vectors)
    return vectors


def train_model(vectors, encoded, train_rows, vocab, records, positive_vectors):
    torch.manual_seed(SEED)
    torch.set_num_threads(4)
    model = SharedSemanticNet(vocab)
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.01)
    x = torch.from_numpy(vectors[0])
    y = {k: torch.from_numpy(v) for k, v in encoded[0].items()}
    positives=torch.from_numpy(positive_vectors)
    rng = np.random.default_rng(SEED)
    history = []
    best_loss = float("inf")
    best_weights = None
    stale = 0
    cal_x = torch.from_numpy(vectors[1])
    cal_y = {k: torch.from_numpy(v) for k, v in encoded[1].items()}
    for epoch in range(20):
        model.train()
        order = rng.permutation(len(x))
        losses = []
        for ids in np.array_split(order, max(1, int(np.ceil(len(order)/256)))):
            output, _ = model(x[ids])
            loss = 2.5 * F.cross_entropy(output["act"], y["act"][ids])
            for key, weight in (("speech",1.0),("action",.8),("domain",.5),
                                ("negation",.5),("correction",.3),("context",.2)):
                loss = loss + weight*F.cross_entropy(output[key], y[key][ids])
            # Slot-presence targets are partial; the loss trains a representation only.
            loss = loss + .15*F.binary_cross_entropy_with_logits(output["slots"], y["slots"][ids])
            if records:
                take = rng.choice(len(records), size=min(32,len(records)), replace=False)
                anchor = torch.tensor([records[i][0] for i in take])
                negative = torch.tensor([records[i][2] for i in take])
                # Positive surface varies, while same-family negations/questions are hard negatives.
                _, a = model(x[anchor]); _, positive = model(positives[take]); _, n = model(x[negative])
                loss = loss + .4*F.triplet_margin_loss(a, positive, n, margin=.3)
            optimizer.zero_grad(); loss.backward(); optimizer.step()
            losses.append(float(loss.detach()))
        model.eval()
        cal_losses=[]
        with torch.no_grad():
            for ids in np.array_split(np.arange(len(cal_x)), max(1,int(np.ceil(len(cal_x)/512)))):
                output,_=model(cal_x[ids])
                cal_loss=2.5*F.cross_entropy(output["act"],cal_y["act"][ids])
                for key,weight in (("speech",1.0),("action",.8),("domain",.5),
                                   ("negation",.5),("correction",.3),("context",.2)):
                    cal_loss=cal_loss+weight*F.cross_entropy(output[key],cal_y[key][ids])
                cal_losses.append(float(cal_loss))
        current={"epoch":epoch+1,"train_loss":float(np.mean(losses)),
                 "calibration_loss":float(np.mean(cal_losses))}
        history.append(current)
        print(f"epoch {epoch+1} train {current['train_loss']:.3f} cal {current['calibration_loss']:.3f}",flush=True)
        if current["calibration_loss"] < best_loss-.005:
            best_loss=current["calibration_loss"]
            best_weights={k:v.clone() for k,v in model.state_dict().items()}
            stale=0
        else:
            stale+=1
            if stale>=3:
                break
    if best_weights is not None:
        model.load_state_dict(best_weights)
    return model, history, len(records)


def infer(model, vectors):
    model.eval()
    result = defaultdict(list)
    started = time.perf_counter()
    with torch.no_grad():
        for batch in np.array_split(vectors, max(1,int(np.ceil(len(vectors)/512)))):
            outputs, _ = model(torch.from_numpy(batch))
            for key, value in outputs.items():
                result[key].append(value.numpy())
    elapsed = time.perf_counter()-started
    logits = {k: np.concatenate(v) for k,v in result.items()}
    return logits, elapsed


def choose_threshold(y, probability):
    order = np.argsort(-probability)
    target = y[order].astype(bool)
    tp = np.cumsum(target); fp = np.cumsum(~target)
    precision = tp / np.maximum(tp+fp,1)
    far = fp / max(1,int(np.sum(~target)))
    valid = np.flatnonzero((precision >= .995) & (far < .002))
    execute = float(probability[order[valid[-1]]]) if len(valid) else 1.01
    # Keep false NO_ACTION on commands below 0.5% in calibration.
    ascending = np.sort(probability[y.astype(bool)])
    no = float(ascending[max(0,int(np.floor(.005*len(ascending)))-1)]) if len(ascending) else -1.0
    return no, execute


def fast_scores(cal, evaluation):
    with (ROOT/"models/tanglish_stage21/candidate_dev_only.pkl").open("rb") as stream:
        old=pickle.load(stream)
    scores=[old["gate"].predict_proba(old["vectorizer"].transform(input_text(r) for r in group))[:,1]
            for group in (cal,evaluation)]
    return scores[0],scores[1],old["thresholds"].get("hierarchical_gate")


def combined_state(fast, neural, fast_no, fast_ex, neural_no, neural_ex):
    state=np.full(len(fast),"UNCERTAIN",dtype="<U18")
    state[fast<=fast_no]="NO_ACTION"
    state[fast>=fast_ex]="EXECUTE_CANDIDATE"
    undecided=state=="UNCERTAIN"
    state[undecided & (neural<=neural_no)]="NO_ACTION"
    state[undecided & (neural>=neural_ex)]="EXECUTE_CANDIDATE"
    return state


def choose_combined(y, fast, neural, fast_no, fast_ex, rows):
    undecided=(fast>fast_no)&(fast<fast_ex)
    true_neural=np.sort(neural[undecided & y.astype(bool)])
    neural_no=float(true_neural[max(0,int(np.floor(.003*len(true_neural)))-1)]) if len(true_neural) else -1.0
    best=(1.01,-1.0)
    for candidate in np.unique(np.quantile(neural[undecided],np.linspace(.25,1,500))):
        state=apply_negation_guard(combined_state(fast,neural,fast_no,fast_ex,neural_no,float(candidate)),rows)
        result=rates(y.astype(bool),state)
        precision=result["action_trigger_precision"]
        if precision is not None and precision>=.995 and result["false_action_rate"]<.002:
            if result["candidate_command_recall"]>best[1]:
                best=(float(candidate),result["candidate_command_recall"])
    return neural_no,best[0]


def score(model, vectors, encoded, rows, vocab):
    logits, elapsed = infer(model,vectors)
    p = F.softmax(torch.from_numpy(logits["act"]),dim=1).numpy()[:,1]
    return {"p":p,"logits":logits,"time":elapsed}


def main():
    train, cal, evaluation = rows()
    vectors = cached_embeddings(train,cal,evaluation)
    vocab, encoded = labels((train,cal,evaluation))
    checkpoint=MODEL_DIR/"candidate_dev_only.pt"
    if "--evaluate-only" in sys.argv:
        saved=torch.load(checkpoint,map_location="cpu",weights_only=False)
        model=SharedSemanticNet(saved["vocab"])
        model.load_state_dict(saved["weights"])
        prior=json.loads((OUT/"neural_dev.json").read_text(encoding="utf-8"))
        history=prior["loss_history"]
        pair_count=prior["contrastive_pair_families"]
    else:
        records=positive_pairs(train,pair_indices(train))
        positive_vectors=cached_positives(train,records)
        model, history, pair_count = train_model(vectors,encoded,train,vocab,records,positive_vectors)
    cal_out=score(model,vectors[1],encoded[1],cal,vocab)
    ev_out=score(model,vectors[2],encoded[2],evaluation,vocab)
    no, execute=choose_threshold(encoded[1]["act"],cal_out["p"])
    fast_cal,fast_eval,stage21_threshold=fast_scores(cal,evaluation)
    fast_no,fast_ex=fast_thresholds(encoded[1]["act"].astype(bool),fast_cal)
    neural_no,neural_ex=choose_combined(encoded[1]["act"],fast_cal,cal_out["p"],fast_no,fast_ex,cal)
    def summarize(output, gold, rows, state):
        summary=rates(gold["act"].astype(bool),state)
        tp,fp,fn=summary["tp"],summary["fp"],summary["fn"]
        summary["candidate_action_f1"]=2*tp/max(1,2*tp+fp+fn)
        for key in ("speech","action","domain","negation","correction","context"):
            summary[f"{key}_accuracy"]=float(np.mean(np.argmax(output["logits"][key],axis=1)==gold[key]))
        speech_pred=np.argmax(output["logits"]["speech"],axis=1)
        summary["speech_confusion_labels"]=vocab["speech"]
        summary["speech_confusion_matrix"]=confusion_matrix(gold["speech"],speech_pred,labels=list(range(len(vocab["speech"])))).tolist()
        command_class=vocab["speech"].index("COMMAND")
        command_mask=gold["speech"]==command_class
        summary["semantic_command_recall"]=float(np.mean(speech_pred[command_mask]==command_class))
        negated_class=vocab["speech"].index("NEGATED_COMMAND")
        negated_mask=gold["speech"]==negated_class
        summary["negated_command_recognition"]=float(np.mean(speech_pred[negated_mask]==negated_class))
        summary["negated_execution_blocking"]=float(np.mean(state[negated_mask]!="EXECUTE_CANDIDATE"))
        summary["slot_presence_micro_accuracy"]=float(np.mean((output["logits"]["slots"]>0)==gold["slots"]))
        summary["head_batch_ms_per_row"]=1000*output["time"]/len(rows)
        summary["by_category"]={}
        for category in sorted({r.get("category","repair") for r in rows}):
            ids=np.array([i for i,r in enumerate(rows) if r.get("category","repair")==category])
            summary["by_category"][category]=rates(gold["act"][ids].astype(bool),state[ids])
        summary["by_language"]={}
        for language in sorted({r["language"] for r in rows}):
            ids=np.array([i for i,r in enumerate(rows) if r["language"]==language])
            summary["by_language"][language]=rates(gold["act"][ids].astype(bool),state[ids])
        summary["risk_false_action"]={}
        from scripts.build_tanglish_stage21_repair import HIGH_RISK
        high=np.asarray([r["action_concept"] in HIGH_RISK for r in rows])
        for label,mask in (("high_risk_proxy",high),("other",~high)):
            summary["risk_false_action"][label]=rates(gold["act"][mask].astype(bool),state[mask])
        return summary
    standalone_cal=np.where(cal_out["p"]>=execute,"EXECUTE_CANDIDATE",np.where(cal_out["p"]<=no,"NO_ACTION","UNCERTAIN"))
    standalone_eval=np.where(ev_out["p"]>=execute,"EXECUTE_CANDIDATE",np.where(ev_out["p"]<=no,"NO_ACTION","UNCERTAIN"))
    fast_eval_state=apply_negation_guard(np.where(fast_eval>=fast_ex,"EXECUTE_CANDIDATE",np.where(fast_eval<=fast_no,"NO_ACTION","UNCERTAIN")),evaluation)
    combined_cal=apply_negation_guard(combined_state(fast_cal,cal_out["p"],fast_no,fast_ex,neural_no,neural_ex),cal)
    combined_eval=apply_negation_guard(combined_state(fast_eval,ev_out["p"],fast_no,fast_ex,neural_no,neural_ex),evaluation)
    report={"encoder":ENCODER,"base_encoder_frozen":True,"train_rows":len(train),
            "calibration_rows":len(cal),"evaluation_rows":len(evaluation),"contrastive_pair_families":pair_count,
            "epochs":len(history),"loss_history":history,
            "thresholds":{"standalone_no_action":no,"standalone_execute":execute,
                          "fast_no_action":fast_no,"fast_execute":fast_ex,
                          "neural_no_action":neural_no,"neural_execute":neural_ex},
            "calibration":summarize(cal_out,encoded[1],cal,combined_cal),
            "evaluation":summarize(ev_out,encoded[2],evaluation,combined_eval),
            "standalone_evaluation":rates(encoded[2]["act"].astype(bool),standalone_eval),
            "fast_evaluation":rates(encoded[2]["act"].astype(bool),fast_eval_state),
            "stage21_gate_at_original_threshold":rates(encoded[2]["act"].astype(bool),
                 np.where(fast_eval>=stage21_threshold,"EXECUTE_CANDIDATE","NO_ACTION")),
            "fast_path_coverage":float(np.mean(fast_eval_state!="UNCERTAIN")),
            "semantic_escalation_rate":float(np.mean(fast_eval_state=="UNCERTAIN")),
            "planner_escalation_rate":float(np.mean(combined_eval=="UNCERTAIN")),
            "test_opened":False,"sealed_holdout_opened":False,"executed_capabilities":False}
    MODEL_DIR.mkdir(parents=True,exist_ok=True)
    torch.save({"weights":model.state_dict(),"vocab":vocab,"encoder":ENCODER,"thresholds":report["thresholds"]},MODEL_DIR/"candidate_dev_only.pt")
    (OUT/"neural_dev.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"train":len(train),"cal":len(cal),"eval":len(evaluation),"metrics":report["evaluation"]},indent=2),flush=True)


if __name__=="__main__":
    main()
