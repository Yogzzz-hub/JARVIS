"""Fresh V2 construction families. Reads V1 TRAIN/DEV only, never retired sets."""
from __future__ import annotations
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from scripts.nlp_provisional_data import canonical,immutable,sha,normalize
from scripts.stage25_gold_data import ROOT,SLOTS,COARSE
from scripts.stage25_freeze import verify,MANIFEST
from scripts.tanglish_stage24_ontology import ACTION_FAMILY

V1=ROOT/'data/nlp_provisional/74c9cca56834dbca2eaa9d74ec63d2326733e2e55ff51f12760e96e6a68d07eb'
DEST=ROOT/'data/nlp_structural_v2'

# Full existing ontology: task objects and domains, not inference sentence rules.
TASKS={
'OPEN':('PC','AppRef','Chrome','application','app.open'),
'CLOSE':('PC','AppRef','Notepad','application','app.close'),
'NAVIGATE':('BROWSER','URLRef','https://github.com/acme/Atlas?ref=v2','URL','browser.open_url'),
'SEARCH':('BROWSER','WebQueryRef','FastAPI Docker networking','query','rag.search_web'),
'FIND':('DRIVE','FileRef','budget.xlsx','file','google.drive_search'),
'SHOW':('FILES','FileRef','diagram.png','file',None),
'LIST':('FILES','FolderRef','Downloads','folder','file.list_directory'),
'READ':('WHATSAPP','MessageRef','latest individual WhatsApp messages','resource_type','whatsapp.read'),
'INSPECT':('FILES','FileRef','package.json','file','file.read_metadata'),
'CHECK':('PC','SystemStatusRef','system memory','resource_type','system.info'),
'VERIFY':('IDE','ProjectRef','backend build','project',None),
'RETRIEVE':('IDE','DataRef','Postgres records','resource_type',None),
'PROVIDE':('GENERAL','AnswerRef','an explanation','resource_type',None),
'ANSWER':('GENERAL','AnswerRef','my question','resource_type',None),
'RETURN':('GENERAL','AnswerRef','the computed answer','resource_type',None),
'EXPLAIN':('IDE','ProjectRef','React component','project',None),
'SUMMARIZE':('GMAIL','MessageRef','Gmail interview thread','resource_type',None),
'SEND':('WHATSAPP','MessageRef','status update','message_content','whatsapp.send'),
'SHARE':('WHATSAPP','MessageRef','meeting notes','message_content','whatsapp.send'),
'FORWARD':('WHATSAPP','MessageRef','previous WhatsApp message','resource_type','whatsapp.send'),
'REPLY':('WHATSAPP','MessageRef','the WhatsApp conversation','resource_type','whatsapp.send'),
'CALL':('PHONE','ContactRef','contact','resource_type',None),
'WRITE':('FILES','FileRef','release_notes.md','file',None),
'TYPE':('PC','TextResource','deployment completed','message_content',None),
'ENTER':('PC','TextResource','the access code','message_content',None),
'INSERT':('FILES','TextResource','a new paragraph','resource_type',None),
'MOVE':('FILES','FileRef','slides.pptx','file','file.move'),
'COPY':('FILES','FileRef','config.yaml','file','file.copy'),
'DOWNLOAD':('DRIVE','FileRef','archive.zip','file','google.drive_download'),
'UPLOAD':('DRIVE','FileRef','results.csv','file','google.drive_upload'),
'ATTACH':('GMAIL','FileRef','proposal.pdf','file',None),
'RENAME':('FILES','FileRef','draft.txt','file','file.rename'),
'CONVERT':('FILES','FileRef','summary.docx','file',None),
'CHANGE':('PC','SettingRef','theme','resource_type',None),
'REPLACE':('FILES','TextResource','the heading','resource_type',None),
'SWITCH':('BROWSER','BrowserTabRef','browser tab','browser_tab',None),
'SET':('PC','Volume','volume','resource_type','windows.volume_set'),
'INCREASE':('PC','Volume','volume','resource_type',None),
'DECREASE':('PC','Brightness','brightness','resource_type',None),
'CREATE':('CALENDAR','CalendarEventRef','design review','resource_type','google.calendar_create'),
'DELETE':('FILES','FileRef','scratch.log','file','file.delete'),
'INSTALL':('PC','AppRef','Ollama','application',None),
'UNINSTALL':('PC','AppRef','old utility','application',None),
'SAVE':('FILES','FileRef','worklog.md','file',None),
'CANCEL':('AUTOMATIONS','WorkflowRef','backup workflow','workflow',None),
'RUN':('IDE','ProjectRef','FastAPI backend','project',None),
'START':('IDE','ServiceRef','Postgres service','resource_type',None),
'STOP':('IDE','ServiceRef','Docker worker','resource_type',None),
'PAUSE':('MEDIA','MediaRef','demo.mp4','file',None),
'RESUME':('MEDIA','MediaRef','music player','resource_type',None),
'RESTART':('IDE','ServiceRef','Next.js server','resource_type',None),
'PLAY':('MEDIA','MediaRef','tutorial.mp3','file',None),
'MUTE':('PC','Volume','audio','resource_type','windows.volume_mute'),
'UNMUTE':('PC','Volume','audio','resource_type','windows.volume_unmute'),
'CLICK':('PC','UIElementRef','submit button','resource_type',None),
'SELECT':('FILES','FileRef','selected.pdf','file',None),
'FILTER':('FILES','FileRef','image files','file_type',None),
'SORT':('FILES','FileRef','documents','resource_type',None),
'CAPTURE':('PC','ScreenshotRef','screen','resource_type','windows.screenshot'),
'COMPARE':('FILES','FileRef','report versions','resource_type',None),
'SUBMIT':('BROWSER','UIElementRef','the completed form','resource_type',None),
'PAY':('BROWSER','PaymentRef','the invoice','resource_type',None),
}
assert set(TASKS)==set(ACTION_FAMILY)

EXTRA_TASKS=[
 ('FIND',('FILES','FileRef','notes.pdf','file','file.find')),
 ('SEARCH',('FILES','FileRef','notes.pdf','file','file.find')),
 ('FIND',('GMAIL','MessageRef','interview emails','resource_type','google.read_emails')),
 ('SEARCH',('GMAIL','MessageRef','interview emails','resource_type','google.read_emails')),
 ('READ',('GMAIL','MessageRef','latest Gmail emails','resource_type','google.read_emails')),
 ('LIST',('GMAIL','MessageRef','unread Gmail emails','resource_type','google.read_emails')),
 ('SEND',('GMAIL','MessageRef','draft email','resource_type','google.gmail_send')),
 ('LIST',('WHATSAPP','MessageRef','individual WhatsApp messages','resource_type','whatsapp.read')),
 ('OPEN',('BROWSER','URLRef','https://github.com/team/Atlas','URL','browser.open_url')),
 ('OPEN',('FILES','FileRef','notes.pdf','file','file.open')),
 ('SEARCH',('DRIVE','FileRef','notes.pdf','file','google.drive_search')),
 ('START',('PC','AppRef','Ollama','application','app.open')),
 ('STOP',('PC','AppRef','Ollama','application','app.close')),
]
NATIVE_TAMIL={'OPEN':'திற','CLOSE':'மூடு','READ':'படி','SEND':'அனுப்பு','SHOW':'காட்டு','FIND':'தேடு','CREATE':'உருவாக்கு','DELETE':'அழி','SUMMARIZE':'சுருக்கமாக சொல்','CHECK':'சரிபார்'}
TAMIL_VERBS={'OPEN':'thira','CLOSE':'moodu','READ':'padi','SEND':'anupu','SHOW':'kaatu','LIST':'pattiyal kaatu','SUMMARIZE':'surukkama sollu','DELETE':'azhi','FIND':'thedi edu','SEARCH':'thedi paaru','CHECK':'saripaaru','VERIFY':'uruthi sei','PROVIDE':'kudu','ANSWER':'pathil sollu','EXPLAIN':'vilakku','CALL':'koopidu','WRITE':'ezhuthu','SAVE':'semithu vai','PLAY':'play pannu','STOP':'niruthu','START':'thodangu','PAUSE':'niruthi vai','RESUME':'thodarndhu pannu','REPLY':'pathil anupu','FORWARD':'forward pannu','SHARE':'pagirndhu anupu','CREATE':'uruvakku','COPY':'copy pannu','MOVE':'maathu','RENAME':'peru maathu','CAPTURE':'padam edu','MUTE':'satham niruthu','UNMUTE':'satham thirumba podu'}
SERVICE={'PC':'computer','FILES':'files','BROWSER':'browser','DRIVE':'Drive','WHATSAPP':'WhatsApp','GMAIL':'Gmail','CALENDAR':'Calendar','IDE':'project workspace','GENERAL':'assistant','PHONE':'phone','AUTOMATIONS':'automations','MEDIA':'media player'}


def read(path):return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def span(text,kind,surface,value=None,occurrence=-1):
    start=text.rfind(surface) if occurrence==-1 else text.find(surface)
    assert start>=0,(kind,surface,text)
    return {'slot':kind,'start':start,'end':start+len(surface),'surface':surface,'value':surface if value is None else value,'source':'TEXT'}


def render(style,language,body):
    en=[f'{body}, please',f'I would like you to {body}',f'The next task is to {body}',f'Please help me {body}',f'When ready, {body}',f'My request: {body}',f'Could you handle this: {body}',f'For this task, {body}',f'Here is what needs doing: {body}',f'Once you have a moment, {body}',f'The instruction I am giving is: {body}',f'As the next step in my work, {body}']
    ta=[f'{body} da',f'enaku {body}',f'adutha velai {body}',f'konjam {body}',f'ready aana {body}',f'en request {body}',f'ithu help pannu: {body}',f'intha velai ku {body}',f'seiyanum nu nenachathu: {body}',f'neram iruntha {body}',f'naan solra velai: {body}',f'en velaila adutha step: {body}']
    native=[f'{body}',f'தயவுசெய்து {body}',f'எனக்கு வேண்டும்: {body}',f'உடனடியாக {body}',f'இப்பொழுது {body}',f'ஒரு கோரிக்கை: {body}',f'முடிந்த வரை சீக்கிரம்: {body}',f'இந்த வேலையைச் செய் {body}',f'புதிய கோரிக்கை: {body}',f'அடுத்த நடவடிக்கையாக {body}',f'இந்த வேலைக்காக மட்டும்: {body}',f'ஒரு உதவியாக எனக்காக செய்யவும் {body}']
    return (en if language=='ENGLISH' else native if language=='TAMIL' else ta)[style]


def construction(style,language,verb,obj,service,recipient):
    """Independent word-order constructions, grouped across translated variants.

    Wrappers alone are not independent families. The predicate, object, service
    and relation positions vary here before polarity/correction is attached.
    """
    if language=='ENGLISH':
        forms=[f'{verb} {obj} using {service}',f'in {service}, {verb} {obj}',
            f'for {obj}, use {service} to {verb}',f'use {service} and {verb} {obj}',
            f'{obj} is the resource to {verb} in {service}',f'I need {obj} handled by {verb} in {service}',
            f'the {service} task on {obj} requires {verb}',f'with {service} as the service, {verb} {obj}',
            f'make {service} {verb} this resource: {obj}',f'{verb} is my requested operation for {obj}, via {service}',
            f'within {service}, the operation on {obj} should be {verb}',f'please apply {verb} to {obj}; service: {service}']
        return forms[style]+(f' to {recipient}' if recipient else '')
    forms=[f'{service} la {obj} {verb}',f'{obj} ah {service} la {verb}',
        f'{service} use pannitu {verb} {obj}',f'{verb} seiyanum {obj}, service {service}',
        f'{obj} ku operation {verb}, {service} la',f'{service} moolama {obj} ah {verb}',
        f'{verb} than velai, resource {obj}, {service} la',f'{obj} pathi {service} la {verb} sei',
        f'{service} eduthu {verb} sei: {obj}',f'operation {verb}; {obj} ah use pannu {service} la',
        f'{obj} resource vechu {verb} seiyanum, {service}',f'{service} ullae seiya vendiya velai {verb}, resource {obj}']
    return forms[style]+(f' {recipient} ku' if recipient else '')


def varied_object(kind,default,style):
    # Shared objects across action concepts prevent action-specific identifier shortcuts.
    pools={'file':['budget.xlsx','design.pdf','package.json','notes.txt','photo.png','archive.zip','review.md','metrics.csv','report.docx','diagram.svg','slides.pptx','recording.wav'],
        'folder':['Downloads','Documents','Projects','Archive','Assets','Exports','Inbox','Shared','Drafts','Backups','Reports','Media'],
        'application':['Chrome','Notepad','Firefox','Calculator','Terminal','Explorer','Edge','Paint','Ollama','Docker','VSCode','Teams'],
        'project':['Atlas','Backend','FastAPI','React','Next.js','Postgres','Ollama','Docker','Mercury','Apollo','Zephyr','Orion']}
    if kind in pools:return pools[kind][style]
    if kind=='URL':return f'https://github.com/team{style}/Atlas?ref=branch{style}'
    return default


NATIVE_INF={'OPEN':'திறக்க','CLOSE':'மூட','READ':'படிக்க','SEND':'அனுப்ப','SHOW':'காட்ட','FIND':'தேட','CREATE':'உருவாக்க','DELETE':'அழிக்க','SUMMARIZE':'சுருக்கமாக சொல்ல','CHECK':'சரிபார்க்க'}

def native_construction(style,action,obj,service,state):
    v=NATIVE_TAMIL[action];inf=NATIVE_INF[action]
    if state=='REFERENCE':obj='அதை'
    if state=='STATUS_QUERY':
        forms=[f'{service} இல் {obj} நிலை என்ன?',f'{obj} இப்போது எப்படி உள்ளது, {service} இல்?',
            f'{service} பயன்படுத்தும்போது {obj} நிலை தெரியுமா?',f'{obj} இன் தற்போதைய நிலையை {service} மூலம் சொல்ல முடியுமா?',
            f'{service} இல் இருக்கும் {obj} பற்றி என்ன நிலவரம்?',f'நிலை தெரிந்துகொள்ள வேண்டியது {obj}; சேவை {service}',
            f'{obj} பற்றிய நிலவரம் தேவை; {service} மூலம் தெரியுமா?',f'{service} பயன்படுத்தி சொல்லவும்: {obj} இன் நிலை என்ன?',
            f'சேவை {service}; உருப்படி {obj}; அதன் தற்போதைய நிலை என்ன?',f'{obj} இன் நிலையை {service} கொண்டு பார்க்க முடியுமா?',
            f'{service} மூலம் தெரிந்துகொள்ள வேண்டிய நிலவரம்: {obj} எப்படி உள்ளது?',f'எனக்காக நிலை சொல்ல முடியுமா; இந்த {obj}; சேவை {service}']
    else:
        forms=[f'{service} இல் {obj} {v}',f'{obj} ஐ {v}; {service} பயன்படுத்தவும்',
            f'{service} வழியாக {v}: {obj}',f'{obj} மீது செய்ய வேண்டிய செயல் {v}; சேவை {service}',
            f'{service} இல் இருக்கும் {obj} ஐ {inf} வேண்டும்',f'{inf} வேண்டிய உருப்படி {obj}; சேவை {service}',
            f'{obj} பற்றிய என் கோரிக்கை {inf}; {service} பயன்படுத்தவும்',f'{service} பயன்படுத்தவும்; அடுத்து {obj} ஐ {v}',
            f'சேவை {service}; செயல் {v}; உருப்படி {obj}',f'{obj} ஐ {service} கொண்டு {inf} என விரும்புகிறேன்',
            f'{service} மூலம் {inf} வேண்டும்: {obj}',f'எனக்காக {inf}; இந்த {obj}; சேவை {service}']
    return forms[style]


def generated():
    for style in range(12):
        partition='TRAIN' if style<6 else 'DEV' if style<8 else 'TEST_V2' if style<10 else 'PROVISIONAL_HOLDOUT_V2'
        # New contexts and identities for each reserved syntax family.
        person=['Leela','Kiran','Farah','Suresh','Divya','Ajay','Malini','Prakash','Nerina','Sanjit','Kesavan','Roshini'][style]
        previous=['Bala','Vijay','Imran','Rekha','Ganesh','Asha','Dinesh','Nithya','Bhuvan','Tarini','Yazhini','Krishna'][style]
        for action,(domain,resource,obj,kind,capability) in [*TASKS.items(),*EXTRA_TASKS]:
            obj=varied_object(kind,obj,style)
            for language in ('ENGLISH','TANGLISH','MIXED','TAMIL'):
                if language=='TAMIL' and action not in NATIVE_TAMIL:continue
                verb=action.lower() if language!='TANGLISH' else TAMIL_VERBS.get(action,action.lower()+' pannu')
                for state in ('COMMAND','NEGATED_COMMAND','STATUS_QUERY','CORRECTION','REFERENCE'):
                    communication=action in {'SEND','SHARE','FORWARD','REPLY','CALL'} and state!='STATUS_QUERY'
                    body=f'{verb} {obj} using {SERVICE[domain]}' if language=='ENGLISH' else f'{SERVICE[domain]} la {obj} {verb}'
                    if language=='MIXED':body+=' pannu'
                    if communication:body+=f' to {person}' if language=='ENGLISH' else f' {person} ku'
                    if state=='NEGATED_COMMAND':
                        body='do not '+body if language=='ENGLISH' else body+' venam'
                    elif state=='STATUS_QUERY':
                        body=f'check the status of {obj} in {SERVICE[domain]}' if language=='ENGLISH' else f'{SERVICE[domain]} la {obj} {verb} aacha?'
                    elif state=='CORRECTION':
                        if communication:body=body.replace(person,previous)+(f', actually to {person}' if language=='ENGLISH' else f', illa {person} ku')
                        else:body+=(f' at 11 am, actually at 4 pm' if language=='ENGLISH' else ' 11 am ku, illa 4 pm ku')
                    elif state=='REFERENCE':
                        body=f'{verb} that using {SERVICE[domain]}' if language=='ENGLISH' else f'{SERVICE[domain]} la atha {verb}'+(' pannu' if language=='MIXED' else '')
                    if language=='TAMIL':
                        body=native_construction(style,action,obj,SERVICE[domain],state)
                        if communication:body+=f' {person} க்கு'
                        if state=='NEGATED_COMMAND':body='வேண்டாம்: '+body
                        elif state=='CORRECTION':
                            body=body.replace(person,previous)+f', இல்லை {person} க்கு' if communication else body+' 11 am, இல்லை 4 pm'
                    if language!='TAMIL':
                        active_person=previous if state=='CORRECTION' and communication else person
                        if state=='STATUS_QUERY':
                            base=construction(style,language,'check' if language!='TANGLISH' else 'saripaaru',obj,SERVICE[domain],active_person if communication else None)
                            body=base+(' status?' if language=='ENGLISH' else ' nilai enna?')
                        elif state=='REFERENCE':body=construction(style,language,verb,'that' if language=='ENGLISH' else 'atha',SERVICE[domain],None)
                        else:
                            body=construction(style,language,verb,obj,SERVICE[domain],active_person if communication else None)
                            if state=='NEGATED_COMMAND':body=('do not ' if language=='ENGLISH' else 'seiya venam: ')+body
                            if state=='CORRECTION':
                                body+=(f', actually to {person}' if language=='ENGLISH' else f', illa {person} ku') if communication else (' at 11 am, actually at 4 pm' if language=='ENGLISH' else ' 11 am ku, illa 4 pm ku')
                    text=render(style,language,body)
                    slots=[]
                    if state!='REFERENCE':slots.append(span(text,kind,obj))
                    if communication and state!='REFERENCE' and person in text:slots.append(span(text,'recipient',person,person))
                    corrections=[]
                    if state=='CORRECTION':
                        if communication:corrections=[{'slot':'recipient','superseded':previous,'active':person}]
                        else:
                            slots.append(span(text,'time','4 pm','16:00'))
                            corrections=[{'slot':'time','superseded':'11:00','active':'16:00'}]
                    # A status request means CHECK; it never starts the resource.
                    concept='CHECK' if state=='STATUS_QUERY' else action
                    speech='COMMAND' if state=='REFERENCE' else state
                    references=[]
                    if state=='REFERENCE':
                        from scripts.nlp_structural_slots import reference_type
                        references=[{'type':reference_type(resource,domain),'requires_context_resolution':True,'value':None}]
                    frame={'domain':domain,'action_concept':concept,'action_family':ACTION_FAMILY[concept],'speech_act':speech,'object_type':resource,'slots':slots,'negations':[{'scope':'ACTION'}] if state=='NEGATED_COMMAND' else [],'corrections':corrections,'references':references,'should_execute':state in {'COMMAND','CORRECTION','REFERENCE'},'context_required':state=='REFERENCE','recipient':{'name':person} if communication and state!='REFERENCE' and person in text else None,'sender':None,'temporal':{'time':'16:00'} if state=='CORRECTION' and not communication else {},'ordinal':None,'include_constraints':[],'exclude_constraints':[]}
                    # Status of a capability is not the same as performing it.
                    gold=capability if concept==action else None
                    identifier=hashlib.sha256((str(style)+action+domain+resource+language+state).encode()).hexdigest()[:20]
                    yield {'id':'v2_'+identifier,'text':text,'raw_text':text,'language':language,'frame':frame,'working_context':None,'family':'v2_syntax_'+str(style),'partition':partition,'capability_gold':gold,'provenance':'NEW_AUTHORED_DEVELOPMENT_PROVISIONAL'}
                    if language=='MIXED' and state in {'COMMAND','NEGATED_COMMAND'}:
                        noise='uh '+text.replace(' pannu',' panu')
                        child=json.loads(json.dumps(frame))
                        for sl in child['slots']:
                            pos=noise.rfind(sl['surface']);sl['start'],sl['end']=pos,pos+len(sl['surface'])
                        yield {'id':'v2_'+identifier+'_asr','text':noise,'raw_text':noise,'language':'ASR','frame':child,'working_context':None,'family':'v2_syntax_'+str(style),'partition':partition,'capability_gold':gold,'provenance':'NEW_AUTHORED_MILD_ASR_PROVISIONAL'}
        # Separate speech-act/unknown diagnostics in every syntax family.
        for language,text,speech in [('ENGLISH','thank you','ACKNOWLEDGEMENT'),('MIXED','seri thanks','ACKNOWLEDGEMENT'),('ENGLISH','handle the thing somehow','AMBIGUOUS'),('TANGLISH','ethavathu atha sei','AMBIGUOUS')]:
            text=render(style,language,text)
            frame={'domain':'GENERAL','action_concept':None,'action_family':None,'speech_act':speech,'object_type':None,'slots':[],'negations':[],'corrections':[],'references':[],'should_execute':False,'context_required':False,'recipient':None,'sender':None,'temporal':{},'ordinal':None,'include_constraints':[],'exclude_constraints':[]}
            yield {'id':'v2_unknown_'+str(style)+language+speech,'text':text,'raw_text':text,'language':language,'frame':frame,'working_context':None,'family':'v2_syntax_'+str(style),'partition':partition,'capability_gold':None,'provenance':'NEW_AUTHORED_DEVELOPMENT_PROVISIONAL'}


def coverage(rows):
    counts=Counter((r['frame']['action_concept'] or 'UNKNOWN',r['frame']['domain'],r['language'],r['partition']) for r in rows)
    return [{'action':a,'domain':d,'language':l,'split':s,'count':n} for (a,d,l,s),n in sorted(counts.items())]


def prepare():
    assert verify()==[]
    rows=list(generated());old=[]
    for partition in ('TRAIN','DEV'):
        for row in read(V1/(partition+'.jsonl')):
            if row['provenance']=='AI_PRECHECK_ACCEPTED':
                # Only old development data is eligible; reserved V2 evaluation is authored afresh.
                row={**row,'family':'eligible_v1:'+row['split_family'],'partition':partition,'raw_text':row['text']};rows.append(row)
            old.append({**row,'partition':partition})
    parts={k:[r for r in rows if r['partition']==k] for k in ('TRAIN','DEV','TEST_V2','PROVISIONAL_HOLDOUT_V2')}
    families={k:{r['family'] for r in group} for k,group in parts.items()}
    assert all(not families[a]&families[b] for a in families for b in families if a!=b)
    texts={k:{normalize(r['text']).casefold() for r in group} for k,group in parts.items()}
    assert all(not texts[a]&texts[b] for a in texts for b in texts if a!=b),'Exact-text split leakage'
    for row in rows:
        for sl in row['frame']['slots']:
            if sl['source']=='TEXT':assert row['text'][sl['start']:sl['end']]==sl['surface']
    digest=hashlib.sha256(canonical(rows)).hexdigest();directory=DEST/digest
    manifest={'status':'AI_ASSISTED_PROVISIONAL','human_audit':'DEFERRED','source_frozen_manifest_sha256':sha(MANIFEST),'v1_directory':str(V1.relative_to(ROOT)),'retired_sets':['TEST','PROVISIONAL_HOLDOUT'],'retired_rows_used_for_training':0,'split_policy':'12 reserved syntax construction families; all action/domain/language/paraphrase/ASR variants stay together. V1 source rows reuse original TRAIN/DEV assignments only.','family_leakage':0,'splits':{}}
    for name,group in parts.items():
        path=directory/(name+'.jsonl');immutable(path,''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in group).encode())
        manifest['splits'][name]={'file':path.name,'rows':len(group),'sha256':sha(path),'families':len(families[name]),'languages':dict(Counter(r['language'] for r in group))}
    immutable(directory/'manifest.json',canonical(manifest))
    immutable(directory/'coverage_before_TRAIN_DEV.json',canonical(coverage(old)))
    immutable(directory/'coverage_v2.json',canonical(coverage(rows)))
    missing={lang:sorted(set(ACTION_FAMILY)-{r['frame']['action_concept'] for r in parts['TRAIN'] if r['language']==lang}) for lang in ('ENGLISH','TANGLISH','MIXED')}
    immutable(directory/'coverage_diagnostics.json',canonical({'missing_supported_train_actions':missing,'thin_threshold':20,'thin_train_actions':{lang:{a:sum(r['frame']['action_concept']==a and r['language']==lang for r in parts['TRAIN']) for a in ACTION_FAMILY if sum(r['frame']['action_concept']==a and r['language']==lang for r in parts['TRAIN'])<20} for lang in missing},'missing_tamil_train_actions':sorted(set(ACTION_FAMILY)-{r['frame']['action_concept'] for r in parts['TRAIN'] if r['language']=='TAMIL'})}))
    with (directory/'coverage_v2.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['action','domain','language','split','count']);writer.writeheader();writer.writerows(coverage(rows))
    print(json.dumps({'directory':str(directory),'splits':manifest['splits'],'missing_train_actions':missing},indent=2));return directory


if __name__=='__main__':prepare()
