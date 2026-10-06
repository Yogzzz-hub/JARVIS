"""Train/choose/calibrate on TRAIN and DEV only. No evaluation partition reads."""
import os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
import argparse
import json
import random
import time
from pathlib import Path
import numpy as np
import psutil
import torch
from torch.nn import functional as F
from transformers import AutoTokenizer
from scripts.nlp_provisional_model import FrameNet,BASE,HEADS,encode,vocab_from_train,scalar_predictions
from scripts.nlp_provisional_data import immutable,canonical,sha
from scripts.stage25_freeze import verify


def read(path):return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x]


def forward_batches(model,tokens,device,batch=8):
    outputs={k:[] for k in (*HEADS,'slot_tags')};model.eval()
    with torch.inference_mode():
        for start in range(0,len(tokens['input_ids']),batch):
            out=model(tokens['input_ids'][start:start+batch].to(device),tokens['attention_mask'][start:start+batch].to(device))
            for k in outputs:outputs[k].append(out[k].cpu())
    return {k:torch.cat(v) for k,v in outputs.items()}


def valid_ce(logits,label,**kwargs):
    return F.cross_entropy(logits,label,ignore_index=-100,**kwargs) if (label!=-100).any() else logits.sum()*0


def calibration(outputs,labels,rows,vocab):
    results=[]
    for temp in (.5,.75,1.,1.25,1.5,2.,3.):
        loss=float(sum(valid_ce(outputs[k]/temp,labels[k]) for k in HEADS)/len(HEADS))
        results.append((loss,temp))
    _,temperature=min(results)
    predictions=scalar_predictions(outputs,vocab,temperature)
    # Joint exact action/domain plus safety bits; incorrect slots/recipient also forbid DEV execute.
    valid=[]
    for i,(r,p) in enumerate(zip(rows,predictions)):
        f=r['frame']
        slots_ok=bool(((outputs['slot_tags'][i].argmax(-1)==labels['slot_tags'][i])|(labels['slot_tags'][i]==-100)).all())
        correct=(p['action']==(f['action_concept'] or 'UNKNOWN') and p['domain']==f['domain'] and p['should_execute']==f['should_execute'] and p['negation']==bool(f['negations']) and p['correction']==bool(f['corrections']) and p['reference']==bool(f['references']) and slots_ok)
        eligible=p['should_execute'] and not p['negation'] and not p['correction'] and not p['reference'] and not p['context_required'] and p['speech_act']!='AMBIGUOUS' and p['action']!='UNKNOWN'
        valid.append((p['confidence'],correct,eligible,bool(f['should_execute'])))
    candidates=[]
    for threshold in sorted({p[0] for p in valid}):
        chosen=[p for p in valid if p[0]>=threshold and p[2]]
        if len(chosen)>=5 and sum(x[1] for x in chosen)/len(chosen)>=.99:
            candidates.append((len(chosen),threshold,sum(x[1] for x in chosen)/len(chosen)))
    best=max(candidates,default=(0,1.01,None))
    # Other dispositions optimize binary semantic correctness on DEV; no hand-selected thresholds.
    pairs=[(confidence,correct) for confidence,correct,_,_ in valid]
    scored=[]
    for threshold in sorted({x[0] for x in pairs}):
        tp=sum(c>=threshold and ok for c,ok in pairs);fp=sum(c>=threshold and not ok for c,ok in pairs);fn=sum(c<threshold and ok for c,ok in pairs)
        scored.append((2*tp/max(1,2*tp+fp+fn),threshold))
    escalate=max(scored,default=(0,1.01))[1]
    wrong=[c for c,ok in pairs if not ok]
    clarify=float(np.quantile(wrong,.1)) if wrong else min(c for c,_ in pairs)
    clarify=min(clarify,escalate)
    return {'partition':'DEV_ONLY','temperature':temperature,'temperature_nll_grid':results,'execute_threshold':best[1],'execute_dev_cases':best[0],'execute_dev_precision':best[2],'escalate_threshold':escalate,'clarify_threshold':clarify,'policy':'Unresolved references/context clarify; negation/correction/non-command escalate; uncertain commands never authorize tools. Execute is offline recommendation only.','min_execute_calibration_cases':5,'no_safe_execute_threshold':not bool(candidates)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);parser.add_argument('--epochs',type=int,default=8);args=parser.parse_args()
    directory=args.directory
    assert verify()==[]
    manifest_path=next(directory.glob('stage25_ai_provisional_manifest_*.json'));manifest=json.loads(manifest_path.read_text())
    for part in ('TRAIN','DEV'):assert sha(directory/(part+'.jsonl'))==manifest['splits'][part]['sha256']
    assert (directory/'production_baseline_DEV.json').exists(),'Benchmark current production first'
    run=directory/'candidate';run.mkdir(exist_ok=True)
    if (run/'frozen_configuration.json').exists():raise ValueError('Candidate already frozen; do not retrain')
    immutable(run/'training_started.json',canonical({'seed':2505,'epochs':args.epochs,'status':'AI_ASSISTED_PROVISIONAL','training_partition':'TRAIN','selection_and_calibration_partition':'DEV','test_opened':False,'holdout_opened':False}))
    random.seed(2505);np.random.seed(2505);torch.manual_seed(2505);torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True,warn_only=True)
    train=read(directory/'TRAIN.jsonl');dev=read(directory/'DEV.jsonl');vocab=vocab_from_train(train)
    immutable(run/'vocab.json',canonical(vocab))
    tokenizer=AutoTokenizer.from_pretrained(str(BASE),local_files_only=True,use_fast=True)
    tx,ty=encode(tokenizer,train,vocab);dx,dy=encode(tokenizer,dev,vocab)
    device='cuda' if torch.cuda.is_available() else 'cpu';model=FrameNet(vocab).to(device)
    optimizer=torch.optim.AdamW([{'params':[p for p in model.encoder.parameters() if p.requires_grad],'lr':5e-5},{'params':list(model.heads.parameters())+list(model.slot_head.parameters()),'lr':1e-3}],weight_decay=.01)
    weights=torch.full((1+2*len(vocab['slots']),),2.,device=device);weights[0]=.2
    if device=='cuda':torch.cuda.reset_peak_memory_stats()
    process=psutil.Process();history=[];best_loss=float('inf');best_state=None;started=time.perf_counter()
    for epoch in range(args.epochs):
        model.train();order=torch.randperm(len(train)).tolist();losses=[]
        for start in range(0,len(order),8):
            take=order[start:start+8];out=model(tx['input_ids'][take].to(device),tx['attention_mask'][take].to(device))
            loss=sum(valid_ce(out[k],ty[k][take].to(device)) for k in HEADS)
            loss+=2*valid_ce(out['slot_tags'].reshape(-1,out['slot_tags'].shape[-1]),ty['slot_tags'][take].reshape(-1).to(device),weight=weights)
            optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.);optimizer.step();losses.append(float(loss.detach()))
        out=forward_batches(model,dx,device)
        dev_loss=float(sum(valid_ce(out[k],dy[k]) for k in HEADS)+2*valid_ce(out['slot_tags'].reshape(-1,out['slot_tags'].shape[-1]),dy['slot_tags'].reshape(-1)))
        action=float((out['action'].argmax(-1)==dy['action']).float().mean())
        item={'epoch':epoch+1,'loss':float(np.mean(losses)),'dev_loss':dev_loss,'dev_action_accuracy':action,'elapsed_seconds':time.perf_counter()-started,'rss_mb':process.memory_info().rss/1048576}
        history.append(item);print(json.dumps(item),flush=True)
        (run/'progress.json').write_bytes(canonical({'stage':'TRAINING','epoch':epoch+1,'epochs':args.epochs,'history':history,'estimated_remaining_seconds':item['elapsed_seconds']/(epoch+1)*(args.epochs-epoch-1)}))
        if dev_loss<best_loss:
            best_loss=dev_loss;best_state={k:v.detach().cpu().clone() for k,v in model.state_dict().items() if k.startswith('heads.') or k.startswith('slot_head.') or '.down.' in k or '.up.' in k};best_epoch=epoch+1
    model.load_state_dict(best_state,strict=False)
    torch.save(best_state,run/'candidate.pt')
    out=forward_batches(model,dx,device);cal=calibration(out,dy,dev,vocab);immutable(run/'calibration.json',canonical(cal))
    report={'status':'AI_ASSISTED_PROVISIONAL','human_validation':False,'seed':2505,'device':device,'strategy':'LoRA query/value last four E5 layers plus domain/action/speech/resource/safety and BIO slot heads','trainable_parameters':sum(p.numel() for p in model.parameters() if p.requires_grad),'epochs':args.epochs,'chosen_epoch':best_epoch,'chosen_on':'minimum DEV loss','history':history,'elapsed_seconds':time.perf_counter()-started,'peak_rss_mb':max(r['rss_mb'] for r in history),'peak_vram_mb':torch.cuda.max_memory_allocated()/1048576 if device=='cuda' else None,'encoder_revision':'614241f622f53c4eeff9890bdc4f31cfecc418b3','max_length':128,'train_truncated_rows':sum(len(tokenizer(input_text)['input_ids'])>128 for input_text in [r['text'] for r in train]),'test_opened':False,'holdout_opened':False}
    immutable(run/'training_report.json',canonical(report))
    config={'provenance':'AI_ASSISTED_PROVISIONAL','dataset_manifest_sha256':sha(manifest_path),'model_sha256':sha(run/'candidate.pt'),'vocab_sha256':sha(run/'vocab.json'),'calibration_sha256':sha(run/'calibration.json'),'training_code_sha256':sha(Path(__file__)),'model_code_sha256':sha(ROOT/'scripts/nlp_provisional_model.py'),'production_enabled':False,'shadow_enabled':False,'evaluation_policy':'TEST and PROVISIONAL_HOLDOUT one-time; no post-evaluation tuning','base_revision':report['encoder_revision'],'max_length':128}
    immutable(run/'frozen_configuration.json',canonical(config))
    (run/'progress.json').write_bytes(canonical({'stage':'TRAINED_CALIBRATED_FROZEN','chosen_epoch':best_epoch,'calibration':cal}))
    print(json.dumps({'trained':True,'chosen_epoch':best_epoch,'calibration':cal,'elapsed_seconds':report['elapsed_seconds']},indent=2),flush=True)


from scripts.stage25_gold_data import ROOT
if __name__=='__main__':main()
