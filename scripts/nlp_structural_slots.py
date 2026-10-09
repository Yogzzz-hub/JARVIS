"""V2 typed canonical values with optional original-codepoint spans.

Relation grammars operate on markers, never on exact utterances or name lists.
This module cannot resolve a resource or authorize an action.
"""
from __future__ import annotations
import re
from scripts.tanglish_stage24_ontology import ACTION_FAMILY

CONTACT_SLOTS={'contact','recipient','sender','source','destination'}
PARTICLES=re.compile(r'\s+(?:ku|kitta|oda|ah|la|க்கு|கிட்ட|உடைய|இல்)\s*$',re.I)
ORDINALS={'first':1,'second':2,'third':3,'fourth':4,'last':-1,'mudhal':1,'rendaavathu':2,'rendavathu':2,'கடைசி':-1,'முதல்':1,'இரண்டாவது':2}
DATES={'today':'today','indru':'today','innaiku':'today','இன்று':'today','tomorrow':'tomorrow','naalai':'tomorrow','naalaiku':'tomorrow','நாளை':'tomorrow','yesterday':'yesterday','nethu':'yesterday','நேற்று':'yesterday'}
NAME=r"[\w\u0b80-\u0bff]+(?:[-'][\w\u0b80-\u0bff]+)*"
COMMUNICATION={'SEND','FORWARD','SHARE','REPLY','CALL'}


def canonical_value(kind,value,context=None):
    if not isinstance(value,str):return value
    value=value.strip()
    if kind in CONTACT_SLOTS:
        value=PARTICLES.sub('',value)
        value=re.sub(r'^(?:to|from|with)\s+','',value,flags=re.I)
        value=re.sub(r"(?:'s|’s)$",'',value)
    if kind in {'ordinal','count','number','quantity','percentage'}:
        simple=value.lower().strip('., ')
        if kind=='ordinal' and simple in ORDINALS:return ORDINALS[simple]
        if re.fullmatch(r'-?\d+',simple):return int(simple)
    if kind=='date':return DATES.get(value.casefold(),value)
    if kind=='time':
        m=re.fullmatch(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?(?:\s+ku)?',value,re.I)
        if m:
            hour=int(m[1]);minute=int(m[2] or 0);period=(m[3] or '').lower()
            if period:hour=hour%12+(12 if period=='pm' else 0)
            elif (context or {}).get('afternoon_low_hours'):
                # Explicit context policy: low hours afternoon, higher hours morning.
                if 1<=hour<=7:hour+=12
            elif not m[2] and 1<=hour<=12:
                return {'hour':hour,'minute':minute,'requires_clarification':True}
            if hour<=23 and minute<=59:return f'{hour:02}:{minute:02}'
    return value


def typed_slot(text,kind,start,end,*,value=None,relation=None):
    # Python/fast-tokenizer indices use Unicode codepoints, [start,end).
    while start<end and text[start].isspace():start+=1
    while end>start and text[end-1].isspace():end-=1
    surface=text[start:end]
    result={'slot':kind,'value':canonical_value(kind,surface if value is None else value),
            'span':{'start':start,'end':end,'surface':surface},'source':'TEXT'}
    if relation:result['relation']=relation
    return result


def contacts(text,action):
    found=[]
    for pattern,kind,relation in [
        (rf'\b(?P<name>{NAME})\s+(?:ku|kitta|க்கு)(?=\s|[,.;]|$)','recipient' if action in COMMUNICATION else 'contact','TO'),
        (rf'\b(?P<name>{NAME})\s+(?:anupuna|anupina|sent|அனுப்பிய)(?=\s|[,.;]|$)','sender','SENT_BY'),
        (rf'\b(?P<name>{NAME})\s+oda\b','source','OWNER'),
        (rf'\bfrom\s+(?P<name>{NAME})\b','sender','FROM'),
        (rf'\bto\s+(?P<name>{NAME})\b','recipient' if action in COMMUNICATION else 'destination','TO'),
        (rf"\b(?P<name>{NAME})['’]s\b",'source','OWNER'),
    ]:
        for m in re.finditer(pattern,text,re.I):
            name=m.group('name')
            # Numeric/time tokens are not people merely because a dative marker follows.
            if name.isdigit() or name.casefold() in {'am','pm'} or name.upper() in ACTION_FAMILY:continue
            start,end=m.span('name');found.append(typed_slot(text,kind,start,end,relation=relation))
    unique={ (s['slot'],s['span']['start'],s['value']):s for s in found }
    return sorted(unique.values(),key=lambda s:s['span']['start'])


def reference_type(resource,domain):
    if resource in {'FileRef','FolderRef'}:return 'SelectedFileRef'
    if resource=='BrowserTabRef':return 'BrowserTabRef'
    if resource=='ContactRef':return 'ContactRef'
    if resource=='MessageRef':return 'EmailRef' if domain=='GMAIL' else 'PreviousMessageRef'
    return 'OrdinalRef' if resource=='OrdinalRef' else 'SelectedResourceRef'


def reconstruct(text,slots,action,domain,resource,*,has_correction=False,has_reference=False,context=None):
    result=list(slots);relations=contacts(text,action)
    evidence={str(s['value']) for s in slots if s['slot'] in CONTACT_SLOTS}
    # Lowercase ordinary nouns with dative suffixes need typed entity evidence.
    # Capitalized names/Unicode names remain marker-bound candidates; case alone
    # never determines their recipient/sender/owner role.
    relations=[s for s in relations if not str(s['value']).isascii() or str(s['value'])[:1].isupper() or str(s['value']) in evidence]
    # A resource's dative marker is not sufficient evidence of a person.
    # Outside communication domains, keep typed pointer evidence authoritative.
    if domain not in {'WHATSAPP','GMAIL','MESSAGES','PHONE'}:
        predicted={s['slot'] for s in slots}
        relations=[s for s in relations if s['slot'] not in {'contact','destination'} or s['slot'] in predicted]
    if has_correction:
        for m in re.finditer(r'\b\d{1,2}(?::\d{2})?\s*(?:am|pm|ku)\b',text,re.I):
            sl=typed_slot(text,'time',*m.span())
            sl['value']=canonical_value('time',sl['span']['surface'],context)
            result.append(sl)
    # Marker-bound relation candidates take precedence over a generic name span.
    for kind in {'recipient','sender','source','destination','contact'}:
        same=[s for s in relations if s['slot']==kind]
        if same:
            result=[s for s in result if s['slot']!=kind]+same
    corrections=[]
    marker=re.search(r'\b(?:actually|instead|illa|illai|no|இல்லை)(?=\s|[,.;]|$)',text,re.I)
    if has_correction and marker:
        for kind in {s['slot'] for s in result}:
            candidates=sorted((s for s in result if s['slot']==kind and s.get('span')),key=lambda s:s['span']['start'])
            earlier=[s for s in candidates if s['span']['end']<=marker.start()]
            later=[s for s in candidates if s['span']['start']>=marker.end()]
            if earlier and later and earlier[-1]['value']!=later[-1]['value']:
                corrections.append({'slot':kind,'superseded':earlier[-1]['value'],'active':later[-1]['value']})
                result=[s for s in result if s['slot']!=kind]+[later[-1]]
    # A contextual field is an unresolved typed reference, never an invented name.
    refs=[]
    if has_reference:
        kind='OrdinalRef' if re.search(r'\b(?:first|second|third|last|one)\b',text,re.I) else reference_type(resource,domain)
        refs=[{'type':kind,'requires_context_resolution':True,'value':None}]
    for slot in result:
        slot['value']=canonical_value(slot['slot'],slot['value'],context)
    # Duplicate canonical values count once; optional surface evidence is retained.
    values={}
    for slot in sorted(result,key=lambda s:(s.get('span') or {}).get('start',-1)):
        values[slot['slot']]=slot['value']
    return {'slots':result,'values':values,'recipient':values.get('recipient'),'sender':values.get('sender'),
            'owner':next((s['value'] for s in result if s.get('relation')=='OWNER'),None),
            'corrections':corrections,'references':refs,'unresolved_correction':has_correction and not corrections,
            'unresolved_slot':any(isinstance(v,dict) and v.get('requires_clarification') for v in values.values())}


def canonical_set(slots):
    import json
    return {(s['slot'],json.dumps(canonical_value(s['slot'],s['value']),ensure_ascii=False,sort_keys=True)) for s in slots}


def span_set(slots):
    return {(s['slot'],s['span']['start'],s['span']['end']) for s in slots if s.get('span')}
