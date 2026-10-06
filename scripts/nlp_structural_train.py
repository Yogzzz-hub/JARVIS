"""V2 development-only fitting, controlled auxiliary-loss ablation and calibration."""
import os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
import argparse,json,random,time
from pathlib import Path
import numpy as np
import psutil,torch
from torch.nn import functional as F
from transformers import AutoTokenizer
from scripts.nlp_structural_model import FrameNet,BASE,HEADS,encode,vocabulary,decode,recommend
from scripts.nlp_structural_metrics import metrics,joint_correct
from scripts.nlp_structural_capabilities import OfflineFrameRetriever,oracle
from scripts.nlp_provisional_data import canonical,immutable,sha
from scripts.stage25_freeze import verify

def read(path):return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x]
def ce(logits,labels,**kw):return F.cross_entropy(logits,labels,ignore_index=-100,**kw) if (labels!=-100).any() else logits.sum()*0
def batches(model,x,device,batch=16):
    parts={};model.eval()
    with torch.inference_mode():
        for start in range(0,len(x['input_ids']),batch):
            output=model(x['input_ids'][start:start+batch].to(device),x['attention_mask'][start:start+batch].to(device))
            for k,v in output.items():parts.setdefault(k,[]).append(v.cpu())
    return {k:torch.cat(v) for k,v in parts.items()}
def predictions(rows,out,x,vocab,temp=1,mode='canonical'):
    return [decode(row,{k:v[i] for k,v in out.items()},x['offset_mapping'][i].tolist(),vocab,temp,mode) for i,row in enumerate(rows)]
def calibrate(rows,out,x,vocab):
    _,labels=encode(AutoTokenizer.from_pretrained(str(BASE),local_files_only=True),rows,vocab)
    grid=[(float(sum(ce(out[k]/t,labels[k]) for k in HEADS)),t) for t in (.5,.75,1,1.5,2,3)]
    temperature=min(grid)[1];pred=predictions(rows,out,x,vocab,temperature)
    provisional={'execute_threshold':0,'escalate_threshold':0,'clarify_threshold':0}
    eligible=[recommend(p,provisional)=='EXECUTE' for p in pred]
    pairs=[(p['confidence'],joint_correct(r,p),ok) for r,p,ok in zip(rows,pred,eligible)]
    candidates=[]
    for t in sorted({c for c,_,e in pairs if e}):
        selected=[ok for c,ok,e in pairs if e and c>=t]
        if len(selected)>=20 and sum(selected)/len(selected)>=.99:candidates.append((len(selected),t,sum(selected)/len(selected)))
    best=max(candidates,default=(0,1.01,None));scores=[]
    for t in sorted({c for c,_,_ in pairs}):
        tp=sum(c>=t and ok for c,ok,_ in pairs);fp=sum(c>=t and not ok for c,ok,_ in pairs);fn=sum(c<t and ok for c,ok,_ in pairs)
        scores.append((2*tp/max(1,2*tp+fp+fn),t))
    escalate=max(scores)[1];wrong=[c for c,ok,_ in pairs if not ok]
    return {'partition':'DEV_ONLY','temperature':temperature,'temperature_nll_grid':grid,'execute_threshold':best[1],
        'execute_dev_cases':best[0],'execute_dev_precision':best[2],'minimum_cases':20,
        'escalate_threshold':escalate,'clarify_threshold':min(escalate,float(np.quantile(wrong,.1)) if wrong else escalate),
        'no_safe_execute_threshold':not candidates,'controls_tools':False}
def train(directory,name,aux,max_epochs,coverage='full'):
    manifest=json.loads((directory/'manifest.json').read_text());assert verify()==[]
    for part in ('TRAIN','DEV'):assert sha(directory/(part+'.jsonl'))==manifest['splits'][part]['sha256']
    coverage_gate=json.loads((directory/'missing_action_domain_combinations.json').read_text())
    assert not any(coverage_gate['missing_train_pairs'][l] for l in ('ENGLISH','TANGLISH','MIXED')),'Supported action/domain coverage gate failed'
    assert (directory/'production_baseline_DEV.json').exists()
    train=read(directory/'TRAIN.jsonl');dev=read(directory/'DEV.jsonl')
    gate=oracle(dev,OfflineFrameRetriever());assert gate['recall_at_1']>=.90 and gate['recall_at_3']>=.97 and gate['recall_at_5']>=.99
    immutable(directory/'capability_oracle_DEV.json',canonical(gate))
    if coverage=='legacy':
        # Coverage ablation uses only preexisting TRAIN action/language coverage, never reserved data.
        before=json.loads((directory/'coverage_before_TRAIN_DEV.json').read_text())
        allowed={(r['action'],r['language']) for r in before if r['split']=='TRAIN'}
        train=[r for r in train if (r['frame']['action_concept'] or 'UNKNOWN',r['language']) in allowed]
    run=directory/name;run.mkdir(exist_ok=True)
    if (run/'candidate.pt').exists():raise ValueError('Do not overwrite completed experiment')
    recipe={'seed':2506,'batch':16,'max_epochs':max_epochs,'patience':3,'auxiliary_bio_weight':aux,'coverage':coverage,
        'training_precision':'CUDA autocast FP16 with GradScaler; DEV/inference FP32',
        'encoder_lr':1e-4,'head_lr':1e-3,'typed_pointer_loss_weight':3,'pointer_absence_weight':.05,
        'sources':{f:sha(Path('scripts')/f) for f in ('nlp_structural_model.py','nlp_structural_slots.py','nlp_structural_metrics.py','nlp_structural_train.py','nlp_structural_capabilities.py')},
        'dataset_manifest_sha256':sha(directory/'manifest.json'),'TEST_opened':False,'HOLDOUT_opened':False}
    immutable(run/'train_recipe.json',canonical(recipe))
    random.seed(2506);np.random.seed(2506);torch.manual_seed(2506);torch.set_num_threads(4)
    vocab=vocabulary(read(directory/'TRAIN.jsonl'));immutable(run/'vocab.json',canonical(vocab))
    tok=AutoTokenizer.from_pretrained(str(BASE),local_files_only=True,use_fast=True)
    tx,ty=encode(tok,train,vocab);dx,dy=encode(tok,dev,vocab)
    model=FrameNet(vocab).cuda();device='cuda';process=psutil.Process()
    optimizer=torch.optim.AdamW([{'params':[p for p in model.encoder.parameters() if p.requires_grad],'lr':1e-4},
        {'params':list(model.heads.parameters())+list(model.slot_head.parameters())+list(model.pointers.parameters())+list(model.values.parameters()),'lr':1e-3}],weight_decay=.01)
    scaler=torch.amp.GradScaler('cuda')
    bio_weights=torch.ones(1+2*len(vocab['slots']),device=device);bio_weights[0]=.15
    history=[];best=-1;best_epoch=0;started=time.perf_counter();torch.cuda.reset_peak_memory_stats()
    for epoch in range(max_epochs):
        for f,h in recipe['sources'].items():assert sha(Path('scripts')/f)==h,'Training source changed: '+f
        model.train();order=torch.randperm(len(train)).tolist();losses=[]
        for start in range(0,len(order),16):
            take=order[start:start+16]
            with torch.autocast(device_type='cuda',dtype=torch.float16):out=model(tx['input_ids'][take].cuda(),tx['attention_mask'][take].cuda())
            # Loss accumulation and validation remain FP32.
            out={k:v.float() for k,v in out.items()}
            loss=sum(ce(out[k],ty[k][take].cuda()) for k in HEADS)
            for key in ('start','end'):
                target=ty[key][take].cuda();raw=F.cross_entropy(out[key].reshape(-1,out[key].shape[-1]),target.reshape(-1),reduction='none').reshape(target.shape)
                weight=torch.where(target==0,.05,1.);loss+=3*(raw*weight).sum()/weight.sum()
            for key in out:
                if key.startswith('value_'):loss+=ce(out[key],ty[key][take].cuda())
            if aux:loss+=aux*ce(out['bio'].reshape(-1,out['bio'].shape[-1]),ty['bio'][take].reshape(-1).cuda(),weight=bio_weights)
            optimizer.zero_grad();scaler.scale(loss).backward();scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(),1);scaler.step(optimizer);scaler.update();losses.append(float(loss.detach()))
        out=batches(model,dx,device);pred=predictions(dev,out,dx,vocab)
        for p in pred:p['recommendation']='UNKNOWN';p['capabilities']=[]
        m=metrics(dev,pred);objective=.4*m['action']+.2*m['domain']+.4*(m['canonical_slots']['f1'] or 0)
        item={'epoch':epoch+1,'loss':float(np.mean(losses)),'dev_objective':objective,'dev_action':m['action'],'dev_domain':m['domain'],'dev_canonical_f1':m['canonical_slots']['f1'],'elapsed_seconds':time.perf_counter()-started,'rss_mb':process.memory_info().rss/1048576}
        history.append(item);print(json.dumps({'experiment':name,**item}),flush=True)
        (run/'progress.json').write_bytes(canonical({'stage':'TRAINING','history':history,'epoch':epoch+1,'epochs':max_epochs}))
        if objective>best+1e-4:
            best=objective;best_epoch=epoch+1
            state={k:v.detach().cpu().clone() for k,v in model.state_dict().items() if k.startswith(('heads.','slot_head.','pointers.','values.')) or '.down.' in k or '.up.' in k}
            torch.save(state,run/'best_pending.pt')
        if epoch+1-best_epoch>=3:break
    model.load_state_dict(torch.load(run/'best_pending.pt',weights_only=True),strict=False)
    torch.save(torch.load(run/'best_pending.pt',weights_only=True),run/'candidate.pt')
    out=batches(model,dx,device);cal=calibrate(dev,out,dx,vocab);immutable(run/'calibration.json',canonical(cal))
    report={'seed':2506,'selection':'DEV objective .4 action + .2 domain + .4 canonical F1; patience 3; minimum improvement .0001',
        'auxiliary_bio_loss_weight':aux,'coverage':coverage,'train_rows':len(train),'chosen_epoch':best_epoch,'history':history,'elapsed_seconds':time.perf_counter()-started,
        'peak_rss_mb':max(h['rss_mb'] for h in history),'peak_vram_mb':torch.cuda.max_memory_allocated()/1048576,'test_opened':False,'holdout_opened':False,'bitwise_reproducibility_established':False}
    immutable(run/'training_report.json',canonical(report));(run/'progress.json').write_bytes(canonical({'stage':'TRAINED_DEV_ONLY','chosen_epoch':best_epoch}))
    retriever=OfflineFrameRetriever();pred=predictions(dev,out,dx,vocab,cal['temperature'])
    for p in pred:p['recommendation']=recommend(p,cal);p['capabilities']=retriever.retrieve_frame(p)
    result={'metrics':metrics(dev,pred),'languages':{lang:metrics([r for r in dev if r['language']==lang],[p for r,p in zip(dev,pred) if r['language']==lang]) for lang in sorted({r['language'] for r in dev})},'records':pred}
    immutable(run/'evaluation_DEV.json',canonical(result))
    bio=predictions(dev,out,dx,vocab,cal['temperature'],'bio')
    for p in bio:p['recommendation']='UNKNOWN';p['capabilities']=[]
    immutable(run/'bio_decoder_DEV.json',canonical({'metrics':metrics(dev,bio),'scope':'same V2 weights, auxiliary BIO decoder; not V1 weights'}))
    return result['metrics']
def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--name',default='canonical_aux');p.add_argument('--aux',type=float,default=.5);p.add_argument('--epochs',type=int,default=24);p.add_argument('--coverage',choices=['full','legacy'],default='full');a=p.parse_args()
    print(json.dumps(train(a.directory,a.name,a.aux,a.epochs,a.coverage)),flush=True)
if __name__=='__main__':main()
