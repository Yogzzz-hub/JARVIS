"""Choose under one final DEV policy, recalibrate, then seal; no TEST reads."""
import argparse,gc,json
from pathlib import Path
import torch
from transformers import AutoTokenizer
from scripts.nlp_structural_model import Candidate,BASE,encode
from scripts.nlp_structural_policy import recommend,truncated,ambiguous_time
from scripts.nlp_structural_frame import complete
from scripts.nlp_structural_train import read,batches,predictions,calibrate
from scripts.nlp_structural_metrics import metrics,joint_correct
from scripts.nlp_structural_capabilities import OfflineFrameRetriever
from scripts.nlp_provisional_data import canonical,immutable,sha
from scripts.nlp_structural_evaluate import freeze

def select(directory):
    if (directory/'selected_candidate.json').exists():raise ValueError('Configuration already frozen')
    for part in ('TEST_V2','PROVISIONAL_HOLDOUT_V2'):
        assert not (directory/(part+'_consumed.json')).exists()
    rows=read(directory/'DEV.jsonl');tokenizer=AutoTokenizer.from_pretrained(str(BASE),local_files_only=True,use_fast=True)
    torch.set_num_threads(4);ranked=[]
    for name in ('canonical_only','canonical_aux','legacy_coverage'):
        c=Candidate(directory/name);x,_=encode(tokenizer,rows,c.vocab,False);out=batches(c.model,x,c.device)
        cal=calibrate(rows,out,x,c.vocab);pred=predictions(rows,out,x,c.vocab,cal['temperature'])
        for row,p in zip(rows,pred):
            p['recommendation']='UNKNOWN'
            p['input_truncated']=truncated(tokenizer,row)
            p['ambiguous_time_evidence']=ambiguous_time(p,row.get('working_context'))
        pred=[complete(p) for p in pred]
        # Refit execute eligibility under the final boundary guard on DEV only.
        pairs=[(p['confidence'],joint_correct(r,p),recommend(p,{**cal,'execute_threshold':0})=='EXECUTE') for r,p in zip(rows,pred)]
        safe=[]
        for t in sorted({confidence for confidence,_,eligible in pairs if eligible}):
            chosen=[ok for confidence,ok,eligible in pairs if eligible and confidence>=t]
            if len(chosen)>=20 and sum(chosen)/len(chosen)>=.99:safe.append((len(chosen),t,sum(chosen)/len(chosen)))
        count,threshold,precision=max(safe,default=(0,1.01,None))
        cal.update({'execute_dev_cases':count,'execute_threshold':threshold,'execute_dev_precision':precision,'no_safe_execute_threshold':not safe,'boundary_guard':'CLARIFY when encoder input exceeds 128 tokens'})
        retriever=OfflineFrameRetriever()
        for i,p in enumerate(pred):
            p['recommendation']=recommend(p,cal);pred[i]=complete(p);pred[i]['capabilities']=retriever.retrieve_frame(pred[i])
        m=metrics(rows,pred);objective=.4*m['action']+.2*m['domain']+.4*(m['canonical_slots']['f1'] or 0)
        immutable(directory/name/'final_policy_DEV.json',canonical({'metrics':m,'objective':objective,'calibration':cal,
            'trainable_parameters':sum(p.numel() for p in c.model.parameters() if p.requires_grad),
            'total_parameters':sum(p.numel() for p in c.model.parameters()),'scope':'same final schema/policy evaluated on DEV only'}))
        ranked.append((objective,name,cal));del c,out,x,pred;gc.collect();torch.cuda.empty_cache()
    _,name,cal=max(ranked);origin=directory/name;run=directory/'candidate';run.mkdir(exist_ok=True)
    for f in ('candidate.pt','vocab.json'):immutable(run/f,(origin/f).read_bytes())
    report=json.loads((origin/'training_report.json').read_text());report['source_experiment']=name
    parameters=json.loads((origin/'final_policy_DEV.json').read_text())
    report.update({k:parameters[k] for k in ('trainable_parameters','total_parameters')})
    immutable(run/'training_report.json',canonical(report));immutable(run/'calibration.json',canonical(cal))
    immutable(run/'bio_decoder_DEV.json',(origin/'bio_decoder_DEV.json').read_bytes())
    immutable(directory/'candidate_selection_DEV.json',canonical({'selected':name,'ranked':[{'objective':s,'experiment':n} for s,n,_ in ranked],
        'policy':'highest final-policy DEV objective; candidate weights unchanged; confidence recalibrated DEV only',
        'source_model_sha256':sha(origin/'candidate.pt'),'copied_model_sha256':sha(run/'candidate.pt')}))
    freeze(directory,'candidate');(run/'progress.json').write_bytes(canonical({'stage':'TRAINED_CALIBRATED_FROZEN','source_experiment':name,'chosen_epoch':report['chosen_epoch']}))
    print(json.dumps({'selected':name,'frozen':True,'calibration':cal},indent=2),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);select(p.parse_args().directory)
