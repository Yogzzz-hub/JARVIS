"""E5 V2: hierarchical semantic heads + independent typed pointers/value heads."""
import json
import time
from pathlib import Path
import torch
from torch import nn
from transformers import AutoTokenizer
from scripts.nlp_provisional_model import FrameNet as OldFrameNet,BASE,input_text
from scripts.stage25_gold_data import SLOTS,SPEECH
from scripts.tanglish_stage24_ontology import ACTION_FAMILY
from scripts.nlp_structural_slots import typed_slot,canonical_value,reconstruct,reference_type

HEADS=('domain','action','action_family','speech_act','object_type','negation','correction','reference','context_required','should_execute','reference_type')
VALUE_TYPES=('date','time','ordinal','count','number','percentage')
MAX_LENGTH=128


def labels_for(row):
    f=row['frame'];action=f['action_concept'] or 'UNKNOWN'
    return {'domain':f['domain'],'action':action,'action_family':ACTION_FAMILY.get(action,'UNKNOWN'),
        'speech_act':f['speech_act'],'object_type':f['object_type'] or 'NONE','negation':bool(f['negations']),
        'correction':bool(f['corrections']),'reference':bool(f['references']),'context_required':bool(f['context_required']),
        'should_execute':bool(f['should_execute']),
        'reference_type':reference_type(f['object_type'],f['domain']) if f['references'] else 'NONE'}


def vocabulary(rows):
    vocab={k:sorted({labels_for(r)[k] for r in rows},key=str) for k in HEADS}
    vocab['action']=['UNKNOWN']+sorted(ACTION_FAMILY)
    vocab['action_family']=['UNKNOWN']+sorted(set(ACTION_FAMILY.values()))
    vocab['speech_act']=sorted(SPEECH);vocab['slots']=sorted(SLOTS)
    vocab['reference_type']=sorted({'NONE','SelectedFileRef','PreviousMessageRef','BrowserTabRef','ContactRef','EmailRef','OrdinalRef','SelectedResourceRef'})
    vocab['canonical_values']={kind:sorted({json.dumps(s['value'],sort_keys=True,ensure_ascii=False) for r in rows for s in r['frame']['slots'] if s['slot']==kind}) for kind in VALUE_TYPES}
    return vocab


def token_bounds(text,start,end):
    while start<end and text[start].isspace():start+=1
    while end>start and text[end-1].isspace():end-=1
    return start,end


def encode(tokenizer,rows,vocab,labels=True):
    tokens=tokenizer([input_text(r) for r in rows],padding='max_length',truncation=True,max_length=MAX_LENGTH,return_offsets_mapping=True,return_tensors='pt')
    if not labels:return tokens,None
    n=len(rows);types=len(vocab['slots']);gold={k:torch.tensor([vocab[k].index(labels_for(r)[k]) if labels_for(r)[k] in vocab[k] else -100 for r in rows]) for k in HEADS}
    gold['start']=torch.zeros((n,types),dtype=torch.long);gold['end']=torch.zeros((n,types),dtype=torch.long)
    gold['bio']=torch.full(tokens['input_ids'].shape,-100,dtype=torch.long)
    for kind,values in vocab['canonical_values'].items():gold['value_'+kind]=torch.full((n,),-100,dtype=torch.long)
    for i,row in enumerate(rows):
        offsets=tokens['offset_mapping'][i].tolist();text=row['text'];seen={}
        for j,(left,right) in enumerate(offsets):
            start,end=token_bounds(text,max(0,left-7),min(len(text),right-7)) if left>=7 and right<=len(text)+7 else (0,0)
            if end<=start:continue
            gold['bio'][i,j]=0
            for sl in row['frame']['slots']:
                if sl['source']!='TEXT':continue
                if start<sl['end'] and end>sl['start']:
                    idx=vocab['slots'].index(sl['slot']);marker=(sl['slot'],sl['start'])
                    gold['bio'][i,j]=1+2*idx+int(marker in seen);seen[marker]=True;break
        for sl in row['frame']['slots']:
            if sl['source']!='TEXT':continue
            start,end=sl['start'],sl['end'];value=sl['value']
            # Names/identifiers have canonical boundaries independent of grammatical suffixes.
            if isinstance(value,str) and value in text[start:end]:start+=text[start:end].rfind(value);end=start+len(value)
            matched=[]
            for j,(left,right) in enumerate(offsets):
                a,b=token_bounds(text,max(0,left-7),min(len(text),right-7)) if left>=7 and right<=len(text)+7 else (0,0)
                if b>a and a<end and b>start:matched.append(j)
            if matched:
                idx=vocab['slots'].index(sl['slot']);gold['start'][i,idx]=matched[0];gold['end'][i,idx]=matched[-1]
            if sl['slot'] in VALUE_TYPES:
                values=vocab['canonical_values'][sl['slot']];serialized=json.dumps(sl['value'],sort_keys=True,ensure_ascii=False)
                if serialized in values:gold['value_'+sl['slot']][i]=values.index(serialized)
    return tokens,gold


class FrameNet(OldFrameNet):
    def __init__(self,vocab):
        super().__init__(vocab);size=self.encoder.config.hidden_size;self.vocab=vocab
        self.heads=nn.ModuleDict({k:nn.Linear(size,len(vocab[k])) for k in HEADS})
        # Every schema type has an independent start/end distribution; CLS means absent.
        self.pointers=nn.ModuleDict({name:nn.Linear(size,2) for name in vocab['slots']})
        self.values=nn.ModuleDict({name:nn.Linear(size,len(values)) for name,values in vocab['canonical_values'].items() if values})

    def forward(self,ids,mask):
        hidden=self.encoder(input_ids=ids,attention_mask=mask).last_hidden_state
        pooled=(hidden*mask.unsqueeze(-1)).sum(1)/mask.sum(1,keepdim=True)
        # Same independent parameters/heads, one matrix multiplication instead of
        # 33 tiny GPU launches. Concatenation preserves autograd to every type.
        pointer=stacked_linear(hidden,self.pointers).reshape(*hidden.shape[:2],len(self.pointers),2)
        pointer=pointer.masked_fill(~mask[:,:,None,None].bool(),-1e4)
        pieces=stacked_linear(pooled,self.heads).split([h.out_features for h in self.heads.values()],dim=-1)
        return {**dict(zip(self.heads,pieces)),'start':pointer[:,:,:,0].transpose(1,2),
                'end':pointer[:,:,:,1].transpose(1,2),'bio':self.slot_head(hidden),
                **{'value_'+k:head(pooled) for k,head in self.values.items()}}


def stacked_linear(hidden,heads):
    return torch.nn.functional.linear(hidden,torch.cat([h.weight for h in heads.values()],dim=0),torch.cat([h.bias for h in heads.values()],dim=0))


def decode(row,output,offsets,vocab,temperature=1.,mode='canonical'):
    pred={};conf=[]
    for key in HEADS:
        probs=(output[key]/temperature).softmax(-1);best=int(probs.argmax());pred[key]=vocab[key][best];conf.append(float(probs[best]))
    pred['confidence']=min(conf);text=row['text'];slots=[]
    if mode=='bio':
        current=None
        for tag,(a,b) in zip(output['bio'].argmax(-1).tolist(),offsets):
            a-=7;b-=7
            if a<0 or b>len(text) or b<=a or tag==0:current=None;continue
            kind=vocab['slots'][(tag-1)//2]
            if tag%2==0 and current is not None and current['slot']==kind:
                current=typed_slot(text,kind,current['span']['start'],b);slots[-1]=current
            else:current=typed_slot(text,kind,a,b);slots.append(current)
    else:
        starts=output['start'].argmax(-1).tolist();ends=output['end'].argmax(-1).tolist()
        for idx,kind in enumerate(vocab['slots']):
            start,end=starts[idx],ends[idx]
            if start==0 or end==0 or end<start:continue
            a,b=offsets[start][0]-7,offsets[end][1]-7
            if not 0<=a<b<=len(text):continue
            slot=typed_slot(text,kind,a,b)
            if kind in vocab['canonical_values'] and vocab['canonical_values'][kind] and 'value_'+kind in output:
                # Typed semantic value head is independent of optional lexical surface offsets.
                slot['value']=json.loads(vocab['canonical_values'][kind][int(output['value_'+kind].argmax())])
            slots.append(slot)
    if mode!='bio':
        # Multiple time mentions are needed to reconstruct superseded/active values.
        import re
        if pred['correction']:
            for m in re.finditer(r'\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b',text,re.I):
                slots.append(typed_slot(text,'time',*m.span()))
        reconstructed=reconstruct(text,slots,pred['action'],pred['domain'],pred['object_type'],has_correction=pred['correction'],has_reference=pred['reference'],context=row.get('working_context'))
    else:
        reconstructed={'slots':slots,'values':{s['slot']:s['value'] for s in slots},'recipient':None,'sender':None,'corrections':[],'references':[],'unresolved_correction':True}
    frame={**pred,**reconstructed,'raw_text':text,'controls_tools':False}
    if pred['reference']:
        frame['references']=[{'type':pred['reference_type'],'requires_context_resolution':True,'value':None}]
    return frame


def recommend(frame,calibration):
    if frame['action']=='UNKNOWN':return 'UNKNOWN'
    if frame['speech_act']=='AMBIGUOUS' or frame['context_required'] or frame['reference'] or frame.get('unresolved_slot'):return 'CLARIFY'
    if frame['negation'] or frame['unresolved_correction'] or not frame['should_execute'] or frame['speech_act'] not in {'COMMAND','CORRECTION'}:return 'ESCALATE'
    if frame['confidence']>=calibration['execute_threshold']:return 'EXECUTE'
    if frame['confidence']>=calibration['escalate_threshold']:return 'ESCALATE'
    if frame['confidence']>=calibration['clarify_threshold']:return 'CLARIFY'
    return 'UNKNOWN'


class Candidate:
    def __init__(self,directory,device=None):
        self.directory=Path(directory);self.vocab=json.loads((self.directory/'vocab.json').read_text())
        self.device=device or ('cuda' if torch.cuda.is_available() else 'cpu')
        start=time.perf_counter();self.model=FrameNet(self.vocab)
        self.model.load_state_dict(torch.load(self.directory/'candidate.pt',map_location='cpu',weights_only=True),strict=False)
        self.model.to(self.device).eval();self.tokenizer=AutoTokenizer.from_pretrained(str(BASE),local_files_only=True,use_fast=True)
        self.calibration=json.loads((self.directory/'calibration.json').read_text());self.startup_ms=(time.perf_counter()-start)*1000

    def infer(self,row):
        start=time.perf_counter();tokens,_=encode(self.tokenizer,[row],self.vocab,False)
        with torch.inference_mode():out=self.model(tokens['input_ids'].to(self.device),tokens['attention_mask'].to(self.device))
        if self.device=='cuda':torch.cuda.synchronize()
        output={k:v[0].cpu() for k,v in out.items()};frame=decode(row,output,tokens['offset_mapping'][0].tolist(),self.vocab,self.calibration['temperature'])
        frame['recommendation']=recommend(frame,self.calibration);frame['latency_ms']=(time.perf_counter()-start)*1000
        return frame
