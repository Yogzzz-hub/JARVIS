"""New, sealed realistic-style evaluation; synthetic and not human validated.

No consumed V2 evaluations are read. This set is not used for decoder tuning.
It stays unconsumed until a later frozen candidate evaluation.
"""
import hashlib
import json
from pathlib import Path

CASES = [
 ('ENGLISH','app-short','Launch Vivaldi please.','PC','OPEN',{'application':'Vivaldi'}),
 ('ENGLISH','email-natural','Could you locate the invoice from Aerolite in my inbox?','GMAIL','FIND',{'query':'invoice from Aerolite'}),
 ('ENGLISH','file-natural','I need the notes in sprint-17.txt read out.','FILES','READ',{'file':'sprint-17.txt'}),
 ('ENGLISH','event-explicit','Put a design review on my calendar for 2026-11-18 at 14:25.','CALENDAR','CREATE',{'date':'2026-11-18','time':'14:25'}),
 ('ENGLISH','project-status','Is the Helix API server healthy right now?','IDE','CHECK',{'project':'Helix'}),
 ('ENGLISH','drive-natural','Find the Helix architecture diagram in Drive for me.','DRIVE','FIND',{'query':'Helix architecture diagram'}),
 ('ENGLISH','system-short','A little quieter, please.','PC','DECREASE',{}),
 ('ENGLISH','knowledge-natural','What does a Postgres index do for this query?','GENERAL','ANSWER',{}),
 ('TANGLISH','relation-natural','Sahana anupina budget.csv ah Leela kitta share pannunga.','WHATSAPP','SHARE',{'sender':'Sahana','recipient':'Leela','file':'budget.csv'}),
 ('TANGLISH','project-natural','Helix project oda build status eppadi irukku?','IDE','CHECK',{'project':'Helix'}),
 ('TANGLISH','drive-short','Drive la sprint retrospective thedu.','DRIVE','SEARCH',{'query':'sprint retrospective'}),
 ('TANGLISH','app-politeness','Vivaldi ah konjam launch pannunga.','PC','OPEN',{'application':'Vivaldi'}),
 ('TANGLISH','file-negation','budget.csv remove pannatha, information mattum sollunga.','FILES','INSPECT',{'file':'budget.csv'}),
 ('TANGLISH','recipient-correction','Leela kitta forward pannunga; actually Sahana kitta.','WHATSAPP','FORWARD',{'recipient':'Sahana'}),
 ('TANGLISH','time-uncertainty','night 9 ku follow up nyabagam paduthu.','CALENDAR','REMIND',{'time':'21:00'}),
 ('TANGLISH','reference-natural','munnadi therinja report ah padichu sollunga.','FILES','READ',{}),
 ('TAMIL','tamil-request','விவால்டி உலாவியைத் தொடங்கு.','PC','OPEN',{'application':'விவால்டி'}),
 ('TAMIL','tamil-status','ஹீலிக்ஸ் சேவையகத்தின் நிலை எப்படி உள்ளது?','IDE','CHECK',{'project':'ஹீலிக்ஸ்'}),
 ('TAMIL','tamil-reminder','நாளை இரவு ஒன்பது மணிக்கு நினைவூட்டு.','CALENDAR','REMIND',{'date':'tomorrow','time':'21:00'}),
 ('TAMIL','tamil-reference','முந்தைய கோப்பை வாசித்துக் காட்டு.','FILES','READ',{}),
 ('MIXED','technical-natural','Docker container health eppadi, status mattum report pannu.','IDE','CHECK',{'application':'Docker'}),
 ('MIXED','url-natural','https://docs.example.org/guide?v=3 indha link ah browser la kaattu.','BROWSER','OPEN',{'URL':'https://docs.example.org/guide?v=3'}),
 ('MIXED','sequential-natural','Vivaldi launch pannitu Helix release notes search pannunga.','PC','OPEN',{'application':'Vivaldi'}),
 ('MIXED','automation-condition','Helix health check fail aana notify me please.','AUTOMATIONS','CREATE',{'project':'Helix'}),
 ('MIXED','automation-recurring','Every weekday morning inbox summary enakku venum.','AUTOMATIONS','CREATE',{}),
 ('MIXED_TAMIL_ENGLISH','tamil-technical','Helix backend நிலையை மட்டும் சரிபார்.','IDE','CHECK',{'project':'Helix'}),
 ('MIXED_TAMIL_ENGLISH','tamil-file','sprint-17.txt கோப்பை வாசி, மாற்ற வேண்டாம்.','FILES','READ',{'file':'sprint-17.txt'}),
 ('MIXED_TAMIL_ENGLISH','tamil-contact','சஹானா அனுப்பிய budget.csv கோப்பை லீலாவுக்கு அனுப்பு.','WHATSAPP','SEND',{'sender':'சஹானா','recipient':'லீலா','file':'budget.csv'}),
 ('ASR','asr-app','uh can you launsh Vivaldi please','PC','OPEN',{'application':'Vivaldi'}),
 ('ASR','asr-time','remind me at fourteen twenty five tomorrow uh','CALENDAR','REMIND',{'date':'tomorrow','time':'14:25'}),
 ('ASR','asr-contact','Sahana sent the budget dot csv share that with Leela','WHATSAPP','SHARE',{'sender':'Sahana','recipient':'Leela'}),
 ('ASR','asr-status','helix back end running aa just check','IDE','CHECK',{'project':'helix'}),
]


def main():
    target = Path('data/nlp_shadow/evaluation')
    target.mkdir(parents=True, exist_ok=True)
    rows = [{'id':f'v3-realistic-{i:03}', 'family':f'v3-independent-{family}', 'language':lang,
             'raw_text':text, 'expected':{'domain':domain,'action':action,'values':values},
             'annotation_status':'AI_AUTHORED_UNVALIDATED', 'evaluation_only':True}
            for i,(lang,family,text,domain,action,values) in enumerate(CASES,1)]
    raw = ''.join(json.dumps(row, ensure_ascii=False, sort_keys=True)+'\n' for row in rows).encode('utf-8')
    path = target/'V3_REALISTIC_TEST.jsonl'
    if path.exists():
        assert path.read_bytes() == raw, 'Existing evaluation must never be replaced'
    else:
        with path.open('xb') as f:f.write(raw)
    manifest = {'dataset':'V3_REALISTIC_TEST','sha256':hashlib.sha256(raw).hexdigest(),'rows':len(rows),
                'families':len({r['family'] for r in rows}),'status':'LOCKED_UNCONSUMED_AI_AUTHORED',
                'human_validated':False,'used_for_tuning':False,'near_paraphrase_independence_verified':False,
                'scope':'Realistic-style synthetic cases, not actual owner usage or final acceptance.',
                'source':'independently authored; no V2 TEST/HOLDOUT content reads'}
    m=target/'manifest.json';encoded=json.dumps(manifest,sort_keys=True,indent=2).encode()
    if m.exists():assert m.read_bytes()==encoded
    else:
        with m.open('xb') as f:f.write(encoded)
    print(json.dumps(manifest))


if __name__=='__main__':main()
