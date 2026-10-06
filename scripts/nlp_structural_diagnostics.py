"""Known development probes. Never training, calibration, TEST or HOLDOUT."""
import argparse,json
from pathlib import Path
import torch
from scripts.nlp_structural_policy import GuardedCandidate as Candidate
from scripts.nlp_provisional_data import canonical,immutable
from scripts.nlp_structural_data import V1,read
from scripts.nlp_structural_metrics import metrics
from scripts.nlp_structural_capabilities import OfflineFrameRetriever

CASES=[
 ('Naveen ku file send pannu',{'action':'SEND','recipient':'Naveen'}),
 ('Arun kitta message send pannu',{'action':'SEND','recipient':'Arun'}),
 ('Deepa ku anuppu',{'action':'SEND','recipient':'Deepa'}),
 ('Priya anupuna PDF read pannu',{'action':'READ','sender':'Priya'}),
 ('Ravi oda file open pannu',{'action':'OPEN','owner':'Ravi'}),
 ('Mohan ku forward pannu',{'action':'FORWARD','recipient':'Mohan'}),
 ('Naveen ku... actually Arun ku send pannu',{'action':'SEND','recipient':'Arun','correction':True}),
 ('gmail la latest mail open pannu',{'domain':'GMAIL','action':'OPEN'}),
 ('find my interview email in Gmail',{'domain':'GMAIL','action':'FIND'}),
 ('read the latest WhatsApp message from Naveen',{'domain':'WHATSAPP','action':'READ','sender':'Naveen'}),
 ('send pannadha',{'negation':True}),
 ('delete venam',{'negation':True}),
 ('open pannadha just summarize pannu',{'negation':True}),
 ('backend running ah?',{'action':'CHECK','speech_act':'STATUS_QUERY'}),
 ('open pannalama?',{'must_not_execute':True}),
 ('that PDF ah summarize pannu',{'reference':True,'reference_type':'SelectedFileRef'}),
 ('open it',{'reference':True,'must_not_execute':True}),
 ('open the second one',{'reference':True,'reference_type':'OrdinalRef','must_not_execute':True}),
 ('11 ku... illa 4 ku meeting move pannu',{'correction':True,'must_not_execute':True}),
 ('actually send pannadha draft mattum',{'negation':True,'must_not_execute':True}),
 ('not Gmail, WhatsApp la check pannu',{'domain':'WHATSAPP','must_not_execute':True}),
]
def evaluate(directory):
    torch.set_num_threads(4);candidate=Candidate(directory/'candidate');records=[]
    for text,expected in CASES:
        p=candidate.infer({'text':text,'working_context':None});checks={}
        for key,value in expected.items():
            if key=='must_not_execute':checks[key]=p['recommendation']!='EXECUTE'
            elif key=='reference_type':checks[key]=bool(p['references']) and p['references'][0]['type']==value
            else:checks[key]=p.get(key)==value
        records.append({'text':text,'expected':expected,'checks':checks,'prediction':p})
    result={'scope':'Known DEVELOPMENT probes only; not used for tuning, training, calibration or acceptance; no tools called',
        'cases':len(records),'all_checks_passed_cases':sum(all(r['checks'].values()) for r in records),'records':records}
    immutable(directory/'candidate/diagnostics_DEVELOPMENT.json',canonical(result));print(json.dumps({k:v for k,v in result.items() if k!='records'}))
    rows=read(V1/'DEV.jsonl');retriever=OfflineFrameRetriever();pred=[]
    for r in rows:
        p=candidate.infer(r);p['capabilities']=retriever.retrieve_frame(p);pred.append(p)
    immutable(directory/'candidate/paired_V1_DEV.json',canonical({'scope':'paired historical DEV only; no retired evaluation reads; no tuning',
        'metrics':metrics(rows,pred),'languages':{l:metrics([r for r in rows if r['language']==l],[p for r,p in zip(rows,pred) if r['language']==l]) for l in sorted({r['language'] for r in rows})}}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);evaluate(p.parse_args().directory)
