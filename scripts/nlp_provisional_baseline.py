"""Read-only deterministic CURRENT_PRODUCTION preview; never call tools/models."""
import argparse
import asyncio
import json
import time
from pathlib import Path
from scripts.nlp_provisional_data import immutable, canonical, sha


async def benchmark(rows):
    from jarvis.core.router.router import SmartRouter
    from jarvis.core.capabilities.registry import CapabilityRegistry
    from jarvis.core.capabilities.retrieval import CapabilityRetriever
    from jarvis.core.capabilities.frame import FrameExtractor
    class NoNetwork:
        async def classify(self,*args,**kwargs):
            raise RuntimeError("Model call forbidden in offline production baseline")
    router=SmartRouter(llm_provider=NoNetwork())
    registry=CapabilityRegistry();retriever=CapabilityRetriever(registry);extractor=FrameExtractor()
    records=[]
    for row in rows:
        start=time.perf_counter()
        try:
            decision=await asyncio.wait_for(router.preview(row["text"]),timeout=5)
            extracted=extractor.extract(row["text"])
            caps=retriever.retrieve(row["text"],top_k=10,min_score=0)
            tool=router.catalog.intents.get(decision.intent)
            cap_matches=[c for c in registry.list_all() if tool and c.target_tool==tool.tool]
            action=str(decision.slots.get("action") or (decision.intent or "").split('_')[0]).upper()
            action={"SEARCH":"FIND" if row['frame']['action_concept']=='FIND' else "SEARCH","TAKE":"CAPTURE","LAUNCH":"OPEN"}.get(action,action)
            domain=None
            if cap_matches:
                prefix=cap_matches[0].id.split('.')[0]
                domain={"whatsapp":"WHATSAPP","file":"FILES","app":"PC","windows":"PC","system":"PC","browser":"BROWSER","workflow":"IDE","automation":"AUTOMATIONS"}.get(prefix)
                if prefix=='google':
                    capid=cap_matches[0].id
                    domain="CALENDAR" if 'calendar' in capid else "DRIVE" if 'drive' in capid else "GMAIL"
            recommendation='EXECUTE' if decision.state=='READY_TO_EXECUTE' else 'CLARIFY' if decision.state=='NEEDS_CLARIFICATION' else 'UNKNOWN'
            record={"id":row['id'],"intent":decision.intent,"action":action or None,"domain":domain,"slots":decision.slots,"negated":bool(extracted.user_prohibitions),"correction":bool(extracted.corrections),"reference":bool(extracted.references),"speech_act":None,"recommendation":recommendation,"capabilities":[c.id for c,_ in caps],"latency_ms":(time.perf_counter()-start)*1000,"error":None}
        except Exception as exc:
            record={"id":row['id'],"error":type(exc).__name__+': '+str(exc),"recommendation":"UNKNOWN","latency_ms":(time.perf_counter()-start)*1000,"capabilities":[]}
        records.append(record)
    return records


def main():
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);args=parser.parse_args()
    source=args.directory/'DEV.jsonl'
    rows=[json.loads(x) for x in source.read_text(encoding='utf-8').splitlines() if x]
    target=args.directory/'production_baseline_DEV.json'
    if target.exists():
        print('Existing immutable production baseline retained');return
    records=asyncio.run(benchmark(rows))
    immutable(target,canonical({'scope':'CURRENT_PRODUCTION deterministic preview; model/planner calls disabled, no tool execution. This is not a full live runtime benchmark. Ontology conversion is partial; unmapped fields count as missing.','input_sha256':sha(source),'records':records}))
    print(json.dumps({'cases':len(rows),'errors':sum(bool(r['error']) for r in records),'file':str(target)},indent=2))


if __name__=='__main__':main()
