"""Freeze a DEV-selected V2 configuration and consume fresh evaluations once."""
import argparse,json,time,platform
from importlib.metadata import version
from pathlib import Path
from collections import Counter
import numpy as np
import psutil,torch
from scripts.nlp_structural_model import BASE
from scripts.nlp_structural_policy import GuardedCandidate as Candidate
from scripts.nlp_structural_train import read
from scripts.nlp_structural_metrics import metrics
from scripts.nlp_structural_capabilities import OfflineFrameRetriever
from scripts.nlp_provisional_data import immutable,canonical,sha
from scripts.stage25_freeze import verify

SOURCES=['nlp_structural_model.py','nlp_structural_policy.py','nlp_structural_frame.py','nlp_structural_slots.py','nlp_structural_metrics.py','nlp_structural_capabilities.py','nlp_structural_train.py','nlp_structural_evaluate.py','nlp_structural_select.py','nlp_structural_data.py','nlp_provisional_data.py','nlp_provisional_model.py','train_tanglish_stage24_tiny.py']
RUNTIME_SOURCES=['jarvis/core/capabilities/frame.py','jarvis/core/capabilities/registry.py',
    'jarvis/core/capabilities/retrieval.py','jarvis/core/capabilities/models.py',
    'jarvis/integrations/google/drive/tools.py','jarvis/integrations/google/drive/models.py',
    'jarvis/integrations/google/drive/client.py']

def software_versions():
    return {'python':platform.python_version(),**{package:version(package) for package in
        ('torch','transformers','tokenizers','numpy','pydantic','psutil')}}
def freeze(directory,name):
    assert verify()==[];run=directory/name
    base_manifest=json.loads((BASE/'stage24_model_manifest.json').read_text())
    for f,v in base_manifest['files'].items():assert sha(BASE/f)==v['sha256'],f
    config={'dataset_manifest_sha256':sha(directory/'manifest.json'),'selected_experiment':name,
        'selection':'highest DEV .4 action + .2 domain + .4 canonical F1; all ablations DEV only',
        'files':{f:sha(run/f) for f in ['candidate.pt','vocab.json','calibration.json','training_report.json']},
        'source_hashes':{f:sha(Path('scripts')/f) for f in SOURCES},
        'runtime_dependency_hashes':{f:sha(Path(f)) for f in RUNTIME_SOURCES},
        'production_enabled':False,'shadow_enabled':False,'human_validation':'DEFERRED',
        'base_revision':'614241f622f53c4eeff9890bdc4f31cfecc418b3','encoder_manifest_sha256':sha(BASE/'stage24_model_manifest.json'),
        'base_files':{f:v['sha256'] for f,v in base_manifest['files'].items()},'software':software_versions()}
    immutable(run/'frozen_configuration.json',canonical(config));immutable(directory/'selected_candidate.json',canonical({'experiment':name,'configuration_sha256':sha(run/'frozen_configuration.json')}))
    return config
def verify_config(directory,name):
    run=directory/name;config=json.loads((run/'frozen_configuration.json').read_text())
    selection=json.loads((directory/'selected_candidate.json').read_text())
    assert selection['experiment']==name and selection['configuration_sha256']==sha(run/'frozen_configuration.json')
    assert sha(directory/'manifest.json')==config['dataset_manifest_sha256']
    for f,h in config['files'].items():assert sha(run/f)==h,f
    for f,h in config['source_hashes'].items():assert sha(Path('scripts')/f)==h,f
    for f,h in config['runtime_dependency_hashes'].items():assert sha(Path(f))==h,f
    assert config['software']==software_versions(),'Runtime software versions changed'
    assert sha(BASE/'stage24_model_manifest.json')==config['encoder_manifest_sha256']
    for f,h in config['base_files'].items():assert sha(BASE/f)==h,f
    assert not config['production_enabled'] and not config['shadow_enabled'];assert verify()==[]
def claim_once(path,evidence):
    with path.open('xb') as f:f.write(canonical(evidence))
def evaluate(directory,name,partition):
    verify_config(directory,name);run=directory/name;manifest=json.loads((directory/'manifest.json').read_text())
    source=directory/(partition+'.jsonl');assert sha(source)==manifest['splits'][partition]['sha256']
    if partition!='DEV':claim_once(directory/(partition+'_consumed.json'),{'partition':partition,'configuration_sha256':sha(run/'frozen_configuration.json'),'source_sha256':sha(source),'claimed_before_read':True,'time_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
    rows=read(source);torch.set_num_threads(4);process=psutil.Process();cpu_start=process.cpu_times();started=time.perf_counter()
    candidate=Candidate(run);loaded=process.memory_info().rss/1048576;retriever=OfflineFrameRetriever();records=[];latencies=[];retrieval=[]
    for row in rows:
        p=candidate.infer(row);start=time.perf_counter();p['capabilities']=retriever.retrieve_frame(p);ms=(time.perf_counter()-start)*1000
        p['latency_ms']+=ms;retrieval.append(ms);latencies.append(p['latency_ms']);records.append(p)
    cpu_end=process.cpu_times();wall=time.perf_counter()-started
    all_metrics=metrics(rows,records);languages={lang:metrics([r for r in rows if r['language']==lang],[p for r,p in zip(rows,records) if r['language']==lang]) for lang in sorted({r['language'] for r in rows})}
    confusions=Counter((r['frame']['action_concept'] or 'UNKNOWN',p['action']) for r,p in zip(rows,records) if p['action']!=(r['frame']['action_concept'] or 'UNKNOWN'))
    def gold_label(row,key):return row['frame']['action_concept'] or 'UNKNOWN' if key=='action' else row['frame'][key]
    matrices={key:Counter((gold_label(r,key),p[key]) for r,p in zip(rows,records)) for key in ('action','domain','speech_act')}
    top_other={key:[{'gold':a,'predicted':b,'count':n} for (a,b),n in Counter({pair:n for pair,n in matrix.items() if pair[0]!=pair[1]}).most_common(12)] for key,matrix in matrices.items() if key!='action'}
    result={'partition':partition,'configuration_sha256':sha(run/'frozen_configuration.json'),'metrics':all_metrics,'languages':languages,
        'latency':{'p50_ms':float(np.percentile(latencies[1:],50)),'p95_ms':float(np.percentile(latencies[1:],95)),
            'first_route_ms':latencies[0],'startup_ms':candidate.startup_ms,'retrieval_p95_ms':float(np.percentile(retrieval,95))},
        'resources':{'loaded_rss_mb':loaded,'post_rss_mb':process.memory_info().rss/1048576,'vram_mb':torch.cuda.memory_allocated()/1048576,'cpu_one_core_percent':100*((cpu_end.user-cpu_start.user)+(cpu_end.system-cpu_start.system))/wall},
        'top_action_confusions':[{'gold':a,'predicted':b,'count':n} for (a,b),n in confusions.most_common(12)],'records':records,
        'top_domain_confusions':top_other['domain'],'top_speech_act_confusions':top_other['speech_act'],
        'confusion_matrices':{key:[{'gold':a,'predicted':b,'count':n} for (a,b),n in matrix.items()] for key,matrix in matrices.items()},
        'scope':'OFFLINE_DEVELOPMENT. No tool calls, shadow hooks, or production edits. Provisional synthetic labels.'}
    immutable(run/('locked_evaluation_'+partition+'.json'),canonical(result));print(json.dumps({k:v for k,v in result.items() if k not in ('records','languages')},indent=2),flush=True)
    return result
def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--name',required=True);p.add_argument('--freeze',action='store_true');p.add_argument('--partition',choices=['DEV','TEST_V2','PROVISIONAL_HOLDOUT_V2']);a=p.parse_args()
    if a.freeze:freeze(a.directory,a.name)
    if a.partition:evaluate(a.directory,a.name,a.partition)
if __name__=='__main__':main()
