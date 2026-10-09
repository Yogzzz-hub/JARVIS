"""Direct multilingual E5 encoder with trainable LoRA and semantic/span heads."""
import json
from pathlib import Path
import time
import torch
from torch import nn
from transformers import AutoModel, AutoTokenizer
from scripts.stage25_gold_data import ROOT, SLOTS, SPEECH
from scripts.tanglish_stage24_ontology import ACTION_FAMILY
from scripts.train_tanglish_stage24_tiny import LoRALinear

BASE=ROOT/'models/tanglish_stage24/encoders/multilingual-e5-small'
MAX_LENGTH=128
HEADS=('domain','action','speech_act','object_type','negation','correction','reference','context_required','should_execute')


def vocab_from_train(rows):
    vocab={
        'domain':sorted({r['frame']['domain'] for r in rows}),
        'action':['UNKNOWN']+sorted(ACTION_FAMILY),
        'speech_act':sorted(SPEECH),
        'object_type':['NONE']+sorted({r['frame']['object_type'] for r in rows if r['frame']['object_type']}),
        **{k:[False,True] for k in ('negation','correction','reference','context_required','should_execute')},
        'slots':sorted(SLOTS)}
    return vocab


def input_text(row):
    # No translation, case folding or identifier rewriting. Context is appended.
    text='query: '+row['text']
    if row.get('working_context'):
        text+='\ncontext: '+json.dumps(row['working_context'],ensure_ascii=False,sort_keys=True)
    return text


def encode(tokenizer,rows,vocab,with_labels=True):
    tokens=tokenizer([input_text(r) for r in rows],padding='max_length',truncation=True,max_length=MAX_LENGTH,return_offsets_mapping=True,return_tensors='pt')
    labels={key:[] for key in HEADS};labels['slot_tags']=[]
    if not with_labels:return tokens,None
    for i,row in enumerate(rows):
        f=row['frame'];values={'domain':f['domain'],'action':f['action_concept'] or 'UNKNOWN','speech_act':f['speech_act'],'object_type':f['object_type'] or 'NONE','negation':bool(f['negations']),'correction':bool(f['corrections']),'reference':bool(f['references']),'context_required':bool(f['context_required']),'should_execute':bool(f['should_execute'])}
        for key,value in values.items():labels[key].append(vocab[key].index(value) if value in vocab[key] else -100)
        tags=[];previous=None
        for start,end in tokens['offset_mapping'][i].tolist():
            if start==end or start<7 or start>=len(row['text'])+7:
                tags.append(-100);previous=None;continue
            match=None
            for n,slot in enumerate(f['slots']):
                if slot['source']=='TEXT' and start<slot['end']+7 and end>slot['start']+7:match=(n,slot['slot']);break
            if match:
                tags.append(1+2*vocab['slots'].index(match[1])+int(previous==match));previous=match
            else:tags.append(0);previous=None
        labels['slot_tags'].append(tags)
    return tokens,{k:torch.tensor(v,dtype=torch.long) for k,v in labels.items()}


class FrameNet(nn.Module):
    def __init__(self,vocab):
        super().__init__();self.vocab=vocab
        self.encoder=AutoModel.from_pretrained(str(BASE),local_files_only=True)
        for p in self.encoder.parameters():p.requires_grad=False
        for layer in self.encoder.encoder.layer[-4:]:
            layer.attention.self.query=LoRALinear(layer.attention.self.query)
            layer.attention.self.value=LoRALinear(layer.attention.self.value)
        self.heads=nn.ModuleDict({k:nn.Linear(self.encoder.config.hidden_size,len(vocab[k])) for k in HEADS})
        self.slot_head=nn.Linear(self.encoder.config.hidden_size,1+2*len(vocab['slots']))

    def forward(self,ids,mask):
        hidden=self.encoder(input_ids=ids,attention_mask=mask).last_hidden_state
        pooled=(hidden*mask.unsqueeze(-1)).sum(1)/mask.sum(1,keepdim=True)
        return {**{k:h(pooled) for k,h in self.heads.items()},'slot_tags':self.slot_head(hidden)}


def scalar_predictions(outputs,vocab,temperature=1.0):
    predictions=[]
    for i in range(len(outputs['action'])):
        record={};confidence=[]
        for key in HEADS:
            probs=(outputs[key][i]/temperature).softmax(-1)
            best=int(probs.argmax());record[key]=vocab[key][best]
            confidence.append(float(probs[best]))
        record['confidence']=min(confidence)
        predictions.append(record)
    return predictions


def build_frame(row,pred,tags,offsets,vocab):
    slots=[];current=None
    for tag,(start,end) in zip(tags,offsets):
        start-=7;end-=7
        if start<0 or end<=start or end>len(row['text']) or tag==0:
            current=None;continue
        name=vocab['slots'][(tag-1)//2]
        if tag%2==0 and current is not None and current['slot']==name:
            current['end']=end;current['surface']=row['text'][current['start']:end];current['value']=current['surface']
        else:
            current={'slot':name,'start':start,'end':end,'surface':row['text'][start:end],'value':row['text'][start:end],'source':'TEXT'}
            slots.append(current)
    values={s['slot']:s['value'] for s in slots}
    frame={**pred,'raw_text':row['text'],'slots':slots,'recipient':values.get('recipient'),'target':values.get('contact') or values.get('file') or values.get('application'),'resource':values.get('file') or values.get('resource_type'),'constraints':{'include':[s['value'] for s in slots if s['slot']=='include_constraint'],'exclude':[s['value'] for s in slots if s['slot']=='exclude_constraint']},'negations':[{'scope':'ACTION'}] if pred['negation'] else [],'corrections':[{'kind':'LATEST_CORRECTION','requires_context_validation':True}] if pred['correction'] else [],'references':[{'kind':'selected_resource','type':pred['object_type'],'requires_context_resolution':True}] if pred['reference'] else [],'temporal':{s['slot']:s['value'] for s in slots if s['slot'] in {'time','date','date_range','time_range'}},'ordinal':values.get('ordinal')}
    return frame


def recommendation(pred,calibration):
    confidence=pred['confidence']
    if pred['action']=='UNKNOWN':return 'UNKNOWN'
    if pred['speech_act']=='AMBIGUOUS' or pred['context_required'] or pred['reference']:return 'CLARIFY'
    # Corrections must never authorize an unresolved action composition.
    if pred['negation'] or pred['correction'] or not pred['should_execute']:return 'ESCALATE'
    if confidence>=calibration['execute_threshold']:return 'EXECUTE'
    if confidence>=calibration['escalate_threshold']:return 'ESCALATE'
    if confidence>=calibration['clarify_threshold']:return 'CLARIFY'
    return 'UNKNOWN'


class Candidate:
    def __init__(self,directory,device=None):
        self.directory=Path(directory);start=time.perf_counter()
        self.device=device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.vocab=json.loads((self.directory/'vocab.json').read_text())
        self.model=FrameNet(self.vocab)
        state=torch.load(self.directory/'candidate.pt',map_location='cpu',weights_only=True)
        self.model.load_state_dict(state,strict=False);self.model.to(self.device).eval()
        self.tokenizer=AutoTokenizer.from_pretrained(str(BASE),local_files_only=True,use_fast=True)
        self.calibration=json.loads((self.directory/'calibration.json').read_text())
        self.startup_ms=(time.perf_counter()-start)*1000

    def infer(self,row):
        total=time.perf_counter();normalized=' '.join(row['text'].split());normalize_ms=(time.perf_counter()-total)*1000
        # Encode the raw text so predicted offsets always refer to original wording.
        t=time.perf_counter();tokens,_=encode(self.tokenizer,[row],self.vocab,False)
        tokenize_ms=(time.perf_counter()-t)*1000
        t=time.perf_counter()
        with torch.inference_mode():out=self.model(tokens['input_ids'].to(self.device),tokens['attention_mask'].to(self.device))
        if self.device=='cuda':torch.cuda.synchronize()
        encoder_ms=(time.perf_counter()-t)*1000
        t=time.perf_counter();cpu={k:v.cpu() for k,v in out.items()};pred=scalar_predictions(cpu,self.vocab,self.calibration['temperature'])[0]
        frame=build_frame(row,pred,cpu['slot_tags'][0].argmax(-1).tolist(),tokens['offset_mapping'][0].tolist(),self.vocab)
        frame['normalized_text']=normalized;frame['recommendation']=recommendation(frame,self.calibration);frame['controls_tools']=False
        frame_ms=(time.perf_counter()-t)*1000
        frame['latency']={'normalization_ms':normalize_ms,'tokenization_ms':tokenize_ms,'encoder_ms':encoder_ms,'frame_ms':frame_ms,'total_ms':(time.perf_counter()-total)*1000}
        return frame
