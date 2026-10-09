"""Locked offline evaluation. Predictions never authorize or call a tool."""
import argparse
import asyncio
import json
import time
from collections import Counter
from pathlib import Path
import numpy as np
import psutil
import torch
from scripts.nlp_provisional_data import immutable,canonical,sha
from scripts.nlp_provisional_model import Candidate
from scripts.nlp_provisional_baseline import benchmark as baseline_benchmark
from scripts.stage25_freeze import verify


def capability_adapter(frame,retriever):
    """Candidate frame -> existing capability contract/retriever, no gold lookup."""
    from jarvis.core.capabilities.frame import SemanticFrame
    native=SemanticFrame(intent=frame['action'],actionability=frame['should_execute'] and not frame['negation'],raw_query=frame['raw_text'],confidence=frame['confidence'])
    native.include_constraints=frame['constraints']['include'];native.exclude_constraints=frame['constraints']['exclude']
    native.corrections=frame['corrections'];native.ambiguity=frame['recommendation'] in {'CLARIFY','UNKNOWN'}
    native.entities=[s['surface'] for s in frame['slots']]
    native.language_features={'provenance':'AI_ASSISTED_PROVISIONAL','domain':frame['domain'],'typed_references':frame['references'],'controls_tools':False}
    domains={'FILES':'file','PC':'system windows app','IDE':'workflow project','GMAIL':'google gmail email','CALENDAR':'google calendar','DRIVE':'google drive','WHATSAPP':'whatsapp message','MESSAGES':'message','BROWSER':'browser web','AUTOMATIONS':'automation workflow','PHONE':'phone','MEDIA':'media','CONTROL':'system control','GENERAL':''}
    native.clean_query=' '.join([domains.get(frame['domain'],frame['domain']),frame['action'].lower(),frame['object_type'],*native.entities])
    return [c.id for c,_ in retriever.retrieve(native.clean_query,top_k=10,min_score=0)]


def safe_div(a,b):return a/b if b else None


def gold_slot_set(row):
    return {(s['slot'],s['start'],s['end']) for s in row['frame']['slots'] if s['source']=='TEXT'}


def metrics(rows,predictions):
    n=len(rows);tp=fp=fn=0;counts=Counter();cap_n=0;recall=Counter();critical=Counter()
    for r,p in zip(rows,predictions):
        f=r['frame'];action=f['action_concept'] or 'UNKNOWN'
        for key,truth in {'domain':f['domain'],'action':action,'speech_act':f['speech_act'],'negation':bool(f['negations']),'correction':bool(f['corrections']),'reference':bool(f['references']),'context_required':bool(f['context_required']),'should_execute':bool(f['should_execute'])}.items():counts[key]+=p.get(key)==truth
        gold=gold_slot_set(r);pred={(s['slot'],s['start'],s['end']) for s in p.get('slots',[])}
        tp+=len(gold&pred);fp+=len(pred-gold);fn+=len(gold-pred)
        counts['constraints']+=p.get('constraints')=={'include':f['include_constraints'],'exclude':f['exclude_constraints']}
        counts['unknown_total']+=action=='UNKNOWN' or f['speech_act']=='AMBIGUOUS'
        counts['unknown_correct']+=(action=='UNKNOWN' or f['speech_act']=='AMBIGUOUS') and p.get('recommendation') in {'UNKNOWN','CLARIFY'}
        counts['reference_positive']+=bool(f['references']);counts['reference_tp']+=bool(f['references']) and bool(p.get('reference'))
        counts['correction_positive']+=bool(f['corrections']);counts['correction_tp']+=bool(f['corrections']) and bool(p.get('correction'))
        counts['negation_positive']+=bool(f['negations']);counts['negation_tp']+=bool(f['negations']) and bool(p.get('negation'))
        expected_recipient=(f['recipient'] or {}).get('name') if isinstance(f['recipient'],dict) else f['recipient']
        counts['recipient_total']+=bool(expected_recipient)
        counts['recipient_correct']+=bool(expected_recipient) and p.get('recipient')==expected_recipient
        executable=p.get('recommendation')=='EXECUTE';counts['execute']+=executable;counts['gold_executable']+=bool(f['should_execute'])
        action_ok=p.get('action')==action;domain_ok=p.get('domain')==f['domain'];recipient_ok=p.get('recipient')==expected_recipient
        correct=action_ok and domain_ok and recipient_ok and bool(f['should_execute']) and not f['negations'] and not f['context_required'] and not f['corrections'] and f['speech_act']!='AMBIGUOUS'
        counts['correct_execute']+=executable and correct
        if executable:
            critical['wrong_action']+=not action_ok
            critical['wrong_domain']+=not domain_ok
            critical['wrong_recipient']+=not recipient_ok
            critical['negation_violation']+=bool(f['negations'])
            critical['correction_violation']+=bool(f['corrections']) and not p.get('correction')
            critical['false_execution_ambiguity']+=f['speech_act']=='AMBIGUOUS' or bool(f['context_required'])
            critical['false_action']+=not correct
        counts['raw_wrong_action']+=not action_ok;counts['raw_wrong_domain']+=not domain_ok
        counts['missed_negation']+=bool(f['negations']) and not p.get('negation')
        counts['missed_correction']+=bool(f['corrections']) and not p.get('correction')
        if expected_recipient:counts['raw_wrong_recipient']+=p.get('recipient')!=expected_recipient
        if r.get('capability_gold'):
            cap_n+=1
            for k in (1,3,5,10):recall[k]+=r['capability_gold'] in p.get('capabilities',[])[:k]
    timing=[p.get('latency',{}).get('total_ms',p.get('latency_ms',0)) for p in predictions]
    return {'samples':n,**{k+'_accuracy':safe_div(counts[k],n) for k in ('domain','action','speech_act','negation','correction','reference','context_required','should_execute','constraints')},'slot_precision':safe_div(tp,tp+fp),'slot_recall':safe_div(tp,tp+fn),'slot_f1':safe_div(2*tp,2*tp+fp+fn),'slot_metric':'micro exact (slot type,start,end) on TEXT spans; canonical value and contextual slot metrics are not represented by this score','slot_tp':tp,'slot_fp':fp,'slot_fn':fn,'negation_positive_recall':safe_div(counts['negation_tp'],counts['negation_positive']),'correction_positive_recall':safe_div(counts['correction_tp'],counts['correction_positive']),'reference_positive_recall':safe_div(counts['reference_tp'],counts['reference_positive']),'reference_typed_resolution_accuracy':None,'correction_structured_exact_accuracy':None,'unknown_clarification_accuracy':safe_div(counts['unknown_correct'],counts['unknown_total']),'unknown_cases':counts['unknown_total'],'recipient_accuracy':safe_div(counts['recipient_correct'],counts['recipient_total']),'action_precision_executable_routes':safe_div(counts['correct_execute'],counts['execute']),'action_recall_executable_routes':safe_div(counts['correct_execute'],counts['gold_executable']),'false_action_rate':safe_div(critical['false_action'],n),'execute_recommendations':counts['execute'],'raw_semantic_failures':{k:counts[k] for k in ('raw_wrong_action','raw_wrong_domain','raw_wrong_recipient','missed_negation','missed_correction')},'safety':dict(critical),'critical_failures':critical['false_action'],'capability_cases':cap_n,**{'capability_recall_at_'+str(k):safe_div(recall[k],cap_n) for k in (1,3,5,10)},'latency_p50_ms':float(np.percentile(timing,50)) if timing else None,'latency_p95_ms':float(np.percentile(timing,95)) if timing else None}


def baseline_adapt(records):
    result=[]
    for rec in records:
        slots=[]
        # Production preview has different slot/schema semantics. Unsupported exact-span fields stay missing.
        result.append({**rec,'recipient':rec.get('slots',{}).get('recipient') or rec.get('slots',{}).get('contact'),'reference':rec.get('reference',False),'negation':rec.get('negated',False),'correction':rec.get('correction',False),'slots':slots,'constraints':{},'latency':{'total_ms':rec['latency_ms']}})
    return result


def segmented(rows,predictions):
    result={}
    for language in ('ENGLISH','TANGLISH','MIXED','TAMIL','ASR'):
        take=[i for i,r in enumerate(rows) if r['language']==language]
        result[language]=metrics([rows[i] for i in take],[predictions[i] for i in take])
    result['ALL']=metrics(rows,predictions)
    return result


def verify_frozen(directory):
    run=directory/'candidate';config=json.loads((run/'frozen_configuration.json').read_text())
    for file,key in (('candidate.pt','model_sha256'),('vocab.json','vocab_sha256'),('calibration.json','calibration_sha256')):assert sha(run/file)==config[key],file
    assert sha(Path(__file__).with_name('nlp_provisional_model.py'))==config['model_code_sha256']
    manifest_path=next(directory.glob('stage25_ai_provisional_manifest_*.json'))
    assert sha(manifest_path)==config['dataset_manifest_sha256']
    return json.loads(manifest_path.read_text()),config


def main():
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);parser.add_argument('--partition',choices=['DEV','TEST','PROVISIONAL_HOLDOUT'],required=True);args=parser.parse_args()
    directory=args.directory;run=directory/'candidate';manifest,config=verify_frozen(directory)
    assert verify()==[]
    source=directory/(args.partition+'.jsonl');assert sha(source)==manifest['splits'][args.partition]['sha256']
    # Claim consumption before reading either locked evaluation file. No automatic retries.
    if args.partition!='DEV':
        if args.partition=='PROVISIONAL_HOLDOUT':assert (run/'evaluation_TEST.json').exists(),'Run locked TEST first'
        marker=run/(args.partition+'_consumed.json')
        if marker.exists():raise ValueError('One-time evaluation already consumed; retire set before development reuse')
        immutable(marker,canonical({'partition':args.partition,'configuration_sha256':sha(run/'frozen_configuration.json'),'dataset_sha256':sha(source),'evaluation_code_sha256':sha(Path(__file__)),'claimed_before_read':True}))
    rows=[json.loads(x) for x in source.read_text(encoding='utf-8').splitlines() if x]
    from jarvis.core.capabilities.registry import CapabilityRegistry
    from jarvis.core.capabilities.retrieval import CapabilityRetriever
    registry=CapabilityRegistry();retriever=CapabilityRetriever(registry)
    torch.set_num_threads(4);process=psutil.Process();idle_rss=process.memory_info().rss/1048576
    candidate=Candidate(run);loaded_rss=process.memory_info().rss/1048576
    predictions=[];cpu_start=process.cpu_times();started=time.perf_counter()
    for i,row in enumerate(rows):
        frame=candidate.infer(row);t=time.perf_counter();frame['capabilities']=capability_adapter(frame,retriever);retrieval_ms=(time.perf_counter()-t)*1000
        frame['latency']['retrieval_ms']=retrieval_ms;frame['latency']['total_ms']+=retrieval_ms
        predictions.append(frame)
        if i%100==0:print(args.partition,i,'/',len(rows),flush=True)
    elapsed=time.perf_counter()-started;cpu_end=process.cpu_times()
    current_records=json.loads((directory/'production_baseline_DEV.json').read_text())['records'] if args.partition=='DEV' else asyncio.run(baseline_benchmark(rows))
    current=baseline_adapt(current_records)
    report={'status':'AI_ASSISTED_PROVISIONAL','partition':args.partition,'configuration_sha256':sha(run/'frozen_configuration.json'),'human_validated':False,'executed_tools':False,'scope':'synthetic/provisional generalization; not production-quality or human gold','candidate':segmented(rows,predictions),'current_production_preview':segmented(rows,current),'baseline_scope':'deterministic SmartRouter.preview with network/model calls disabled; partial ontology adapter, production slot spans/speech-act missing, full live routing performance not measured','registry_capabilities':len(registry.list_all()),'capability_scope':'only authored rows with independently assigned capability IDs; frozen accepted rows lack capability gold. Missing registry targets count as retrieval misses.','missing_registry_gold':sorted({r['capability_gold'] for r in rows if r.get('capability_gold') and registry.get(r['capability_gold']) is None}),'resource':{'device':candidate.device,'idle_process_rss_mb':idle_rss,'loaded_process_rss_mb':loaded_rss,'rss_after_mb':process.memory_info().rss/1048576,'vram_allocated_mb':torch.cuda.memory_allocated()/1048576 if candidate.device=='cuda' else None,'vram_peak_mb':torch.cuda.max_memory_allocated()/1048576 if candidate.device=='cuda' else None,'startup_ms':candidate.startup_ms,'first_route_ms':predictions[0]['latency']['total_ms'] if predictions else None,'cpu_seconds':(cpu_end.user+cpu_end.system)-(cpu_start.user+cpu_start.system),'wall_seconds':elapsed,'cpu_average_percent':100*((cpu_end.user+cpu_end.system)-(cpu_start.user+cpu_start.system))/elapsed},'latency_components':{key:{'p50_ms':float(np.percentile([p['latency'][key] for p in predictions],50)),'p95_ms':float(np.percentile([p['latency'][key] for p in predictions],95))} for key in predictions[0]['latency']},'failure_records':[{'id':r['id'],'language':r['language'],'expected_action':r['frame']['action_concept'],'predicted_action':p['action'],'expected_domain':r['frame']['domain'],'predicted_domain':p['domain'],'recommendation':p['recommendation'],'categories':[k for k,truth in {'ACTION':r['frame']['action_concept'] or 'UNKNOWN','DOMAIN':r['frame']['domain'],'NEGATION':bool(r['frame']['negations']),'CORRECTION':bool(r['frame']['corrections']),'REFERENCE':bool(r['frame']['references'])}.items() if p[{'ACTION':'action','DOMAIN':'domain','NEGATION':'negation','CORRECTION':'correction','REFERENCE':'reference'}[k]]!=truth]} for r,p in zip(rows,predictions) if p['action']!=(r['frame']['action_concept'] or 'UNKNOWN') or p['domain']!=r['frame']['domain'] or p['negation']!=bool(r['frame']['negations'])],'predictions':predictions}
    immutable(run/('evaluation_'+args.partition+'.json'),canonical(report))
    print(json.dumps({'partition':args.partition,'candidate':report['candidate']['ALL'],'resource':report['resource']},indent=2),flush=True)


if __name__=='__main__':main()
