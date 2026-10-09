"""Warm read-only timings plus one real local talkback delivery observation."""
import asyncio
import json
from pathlib import Path
from time import perf_counter
from uuid import uuid4
from scripts.conversational_search_probe import request

async def main():
    rows=[]
    for raw,language,source in [('what is halusination','ENGLISH','test'),
        ('search in web and summarise','ENGLISH','test'),('tell me causes','ENGLISH','test'),
        ('search it','ENGLISH','test'),('what about overfiting','ENGLISH','test'),
        ('search and summarize','ENGLISH','test'),('compare both','ENGLISH','test'),
        ('halucination na enna?','TANGLISH','test'),('web la check pannu','TANGLISH','test'),
        ('ஹாலுசினேஷன் என்றால் என்ன?','TAMIL','test'),('web la check pannu','TAMIL','test'),
        ('what is Kafka','ENGLISH','voice')]:
        rid='warm_concept_'+uuid4().hex; started=perf_counter()
        result=await asyncio.to_thread(request,'/command',dict(text=raw,source=source,request_id=rid,
            metadata={'response_language':language}))
        tool=result.get('tool_result') or {};data=tool.get('data') or {}
        row=dict(raw_text=raw,language=language,request_id=rid,state=result.get('state'),
            route=tool.get('tool_name'),answer=result.get('message'),spoken=result.get('spoken_message'),
            metrics=result.get('metrics'),total_http_ms=(perf_counter()-started)*1000,used_web=data.get('used_web'),
            sources=data.get('sources'),model=data.get('model'))
        rows.append(row);print(json.dumps(row,ensure_ascii=True),flush=True)
    deadline=perf_counter()+40
    while perf_counter()<deadline:
        status=await asyncio.to_thread(request,'/dashboard/voice-language')
        job=status['tts'].get('latest_speech_job') or {}
        if job.get('request_id')==rows[-1]['request_id'] and job.get('state') in ('DELIVERED','FAILED','CANCELLED'): break
        await asyncio.sleep(.2)
    output=dict(turns=rows,tts=status['tts'],health=await asyncio.to_thread(request,'/health'))
    path=Path('reports/conversational_search_evidence/warm_sequence.json')
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__': asyncio.run(main())
