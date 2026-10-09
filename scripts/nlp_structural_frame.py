"""Canonical candidate payload and existing JARVIS SemanticFrame adapter.

Neither adapter resolves identities/resources or invokes a planner/tool.
"""
from dataclasses import asdict
import re
from datetime import date
from jarvis.core.capabilities.frame import SemanticFrame
from scripts.nlp_structural_slots import canonical_value

def normalize_literal_values(frame):
    # Open numeric/date ranges must not be limited to TRAIN's closed value vocabulary.
    for s in frame.get('slots',[]):
        evidence=(s.get('span') or {}).get('surface','').strip();kind=s['slot'];value=None
        if kind in {'count','number','ordinal','percentage'}:
            m=re.fullmatch(r'([+-]?\d+(?:\.\d+)?)(?:%)?',evidence)
            if m:value=float(m[1]) if '.' in m[1] else int(m[1])
        elif kind=='time':
            parsed=canonical_value(kind,evidence)
            if isinstance(parsed,str) and re.fullmatch(r'\d{2}:\d{2}',parsed):value=parsed
        elif kind=='date' and re.fullmatch(r'\d{4}-\d{2}-\d{2}',evidence):
            try:value=date.fromisoformat(evidence).isoformat()
            except ValueError:pass
        if value is not None:s['value']=value;frame.setdefault('values',{})[kind]=value
    return frame

def complete(frame):
    frame=normalize_literal_values(frame);values=frame.get('values',{});result=dict(frame)
    include=[s['value'] for s in frame['slots'] if s['slot']=='include_constraint']
    exclude=[s['value'] for s in frame['slots'] if s['slot']=='exclude_constraint']
    resource_values={k:v for k,v in values.items() if k in {'file','folder','application','browser','URL','project','resource_type'}}
    target=values.get('contact') or frame.get('sender') or frame.get('owner')
    result.update({'intent':frame['action'],'target':target,
        'resource':{'type':frame['object_type'],'identifiers':resource_values,'requires_context_resolution':bool(frame['reference'] or frame['context_required'])},
        'time':{k:values[k] for k in ('date','time') if k in values},'ordinal':values.get('ordinal'),
        'scope':'latest' if values.get('ordinal')==-1 else None,
        'constraints':{'include':include,'exclude':exclude}})
    if frame['reference'] and isinstance(values.get('ordinal'),int):
        result['references']=[{'type':'OrdinalRef','ordinal':values['ordinal'],'requires_context_resolution':True,'value':None}]
    native=SemanticFrame(intent=result['intent'],actionability=result['recommendation']=='EXECUTE',
        raw_query=result['raw_text'],confidence=result['confidence'],ambiguity=result['recommendation'] in {'CLARIFY','UNKNOWN'})
    native.entities=[str(s['value']) for s in frame['slots']]
    native.positive_targets=[str(target)] if target is not None else []
    native.include_constraints=[str(v) for v in include];native.exclude_constraints=[str(v) for v in exclude]
    native.corrections=result['corrections'];native.user_prohibitions=[result['action']] if result['negation'] else []
    native.ordinals=[values['ordinal']] if isinstance(values.get('ordinal'),int) else []
    native.clean_query=' '.join([result['domain'],result['action'],result['object_type'] or '',*native.entities])
    native.language_features={'domain':result['domain'],'resource':result['resource'],'speech_act':result['speech_act'],
        'typed_references':result['references'],'temporal_values':result['time'],'controls_tools':False,'provenance':'AI_ASSISTED_PROVISIONAL'}
    result['jarvis_semantic_frame']=asdict(native)
    return result
