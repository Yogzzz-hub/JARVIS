"""Read-only public-concept probes; no held-out data, contacts or outbound messages."""
import json
from pathlib import Path
from time import perf_counter
from uuid import uuid4
import urllib.request

def request(path, body=None):
    data=json.dumps(body,ensure_ascii=False).encode('utf-8') if body is not None else None
    req=urllib.request.Request('http://127.0.0.1:8765'+path,data=data,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=95) as response: return json.loads(response.read())

def main():
    turns=['what is halusination','search in web and summarise','tell me causes','search it',
        'what about overfiting','search and summarize','compare both',
        'hallucination na enna?','web la search panni summary sollu',
        'ஹாலுசினேஷன் என்றால் என்ன?','web la check pannu']
    observations=[]
    for text in turns:
        point=perf_counter()
        result=request('/command',dict(text=text,source='test',request_id='concept_probe_'+uuid4().hex,
            metadata={'response_language':'ENGLISH'}))
        tool=result.get('tool_result') or {}; data=tool.get('data') or {}
        observations.append(dict(raw_text=text,total_http_ms=(perf_counter()-point)*1000,state=result.get('state'),
            route=tool.get('tool_name'),answer=result.get('message'),spoken=result.get('spoken_message'),
            metrics=result.get('metrics'),used_web=data.get('used_web'),model=data.get('model'),sources=data.get('sources')))
        print(json.dumps({k:v for k,v in observations[-1].items() if k not in ('metrics','sources')},ensure_ascii=True),flush=True)
    evidence=Path('reports/conversational_search_evidence'); evidence.mkdir(exist_ok=True)
    (evidence/'live_sequence.json').write_text(json.dumps(dict(turns=observations,health=request('/health')),ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__': main()
