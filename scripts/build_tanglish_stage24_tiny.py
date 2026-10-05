"""Small authored, span-checked TRAIN diagnostic for Stage 2.4.

This set tests whether a model can intentionally overfit. It is never used
to claim held-out language, slot, or execution accuracy.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.build_tanglish_semantic_stage2 import BASE
from scripts.tanglish_stage24_ontology import ACTION_FAMILY, SPEECH_COARSE

OUT=BASE/"generated/stage24/tiny_overfit_train.jsonl"

# action, speech, utterance, active span values. Corrections list only the
# active value; superseded values are a separate semantic field.
CASES=[
    ("SEND","COMMAND","Naveen ku second PDF anuppu",{"recipient":"Naveen","ordinal":"second","file_type":"PDF"}),
    ("SEND","NEGATED_COMMAND","Naveen ku second PDF anuppadha",{"recipient":"Naveen","ordinal":"second","file_type":"PDF"}),
    ("SEND","QUESTION","Naveen ku second PDF anupitiya?",{"recipient":"Naveen","ordinal":"second","file_type":"PDF"}),
    ("SEND","CAPABILITY_QUERY","Can you send the second PDF to Naveen?",{"recipient":"Naveen","ordinal":"second","file_type":"PDF"}),
    ("SEND","STATEMENT","I sent the second PDF to Naveen yesterday",{"recipient":"Naveen","ordinal":"second","file_type":"PDF"}),
    ("SEND","CORRECTION","Arun ku illa Naveen ku second PDF anuppu",{"recipient":"Naveen","ordinal":"second","file_type":"PDF"}),
    ("FORWARD","COMMAND","Forward Naveen's latest message to Arun",{"sender":"Naveen","recipient":"Arun"}),
    ("FORWARD","NEGATED_COMMAND","Don't forward Naveen's message to Arun",{"sender":"Naveen","recipient":"Arun"}),
    ("FORWARD","QUESTION","Did you forward Naveen's message to Arun?",{"sender":"Naveen","recipient":"Arun"}),
    ("FORWARD","CAPABILITY_QUERY","Can you forward Naveen's message to Arun?",{"sender":"Naveen","recipient":"Arun"}),
    ("FORWARD","STATEMENT","I forwarded Naveen's message to Arun",{"sender":"Naveen","recipient":"Arun"}),
    ("FORWARD","CORRECTION","Forward Naveen's message to Priya, sorry, to Arun",{"sender":"Naveen","recipient":"Arun"}),
    ("READ","COMMAND","Naveen oda latest message padi",{"sender":"Naveen"}),
    ("READ","NEGATED_COMMAND","Naveen oda message padikka venam",{"sender":"Naveen"}),
    ("READ","QUESTION","Did you read Naveen's latest message?",{"sender":"Naveen"}),
    ("READ","CAPABILITY_QUERY","Can you read Naveen's latest message?",{"sender":"Naveen"}),
    ("READ","STATEMENT","I read Naveen's latest message",{"sender":"Naveen"}),
    ("READ","CORRECTION","Read Arun's message, illa Naveen oda message",{"sender":"Naveen"}),
    ("OPEN","COMMAND","Chrome ah open pannu",{"application":"Chrome"}),
    ("OPEN","NEGATED_COMMAND","Chrome open panna venam",{"application":"Chrome"}),
    ("OPEN","QUESTION","Did you open Chrome?",{"application":"Chrome"}),
    ("OPEN","CAPABILITY_QUERY","Can you open Chrome?",{"application":"Chrome"}),
    ("OPEN","STATEMENT","I opened Chrome",{"application":"Chrome"}),
    ("OPEN","CORRECTION","Open Edge, illa Chrome ah open pannu",{"application":"Chrome"}),
    ("SET","COMMAND","volume 40 ku maathu",{"number":"40"}),
    ("SET","NEGATED_COMMAND","volume 40 ku maatha venam",{"number":"40"}),
    ("SET","QUESTION","Did you set volume to 40?",{"number":"40"}),
    ("SET","CAPABILITY_QUERY","Can you set the volume to 40?",{"number":"40"}),
    ("SET","STATEMENT","I set the volume to 40",{"number":"40"}),
    ("SET","CORRECTION","volume 50 illa 40 ku maathu",{"number":"40"}),
    ("CONVERT","COMMAND","invoice.pdf Word ku maathu",{"file":"invoice.pdf","destination":"Word"}),
    ("CONVERT","NEGATED_COMMAND","invoice.pdf Word ku maatha venam",{"file":"invoice.pdf","destination":"Word"}),
    ("CONVERT","QUESTION","Did you convert invoice.pdf to Word?",{"file":"invoice.pdf","destination":"Word"}),
    ("CONVERT","CAPABILITY_QUERY","Can you convert invoice.pdf to Word?",{"file":"invoice.pdf","destination":"Word"}),
    ("CONVERT","STATEMENT","I converted invoice.pdf to Word",{"file":"invoice.pdf","destination":"Word"}),
    ("CONVERT","CORRECTION","Convert report.pdf, illa invoice.pdf to Word",{"file":"invoice.pdf","destination":"Word"}),
    ("CAPTURE","COMMAND","screen shot eduthu",{}),
    ("CAPTURE","NEGATED_COMMAND","screenshot edukka venam",{}),
    ("CAPTURE","QUESTION","Did you take a screenshot?",{}),
    ("CAPTURE","CAPABILITY_QUERY","Can you take a screenshot?",{}),
    ("CAPTURE","STATEMENT","I took a screenshot",{}),
    ("CAPTURE","CORRECTION","Take a photo, illa screenshot eduthu",{}),
    ("SELECT","COMMAND","rendaavathu PDF eduthu",{"ordinal":"rendaavathu","file_type":"PDF"}),
    ("SELECT","NEGATED_COMMAND","rendaavathu PDF edukka venam",{"ordinal":"rendaavathu","file_type":"PDF"}),
    ("SELECT","QUESTION","Did you select the second PDF?",{"ordinal":"second","file_type":"PDF"}),
    ("SELECT","CAPABILITY_QUERY","Can you select the second PDF?",{"ordinal":"second","file_type":"PDF"}),
    ("SELECT","STATEMENT","I selected the second PDF",{"ordinal":"second","file_type":"PDF"}),
    ("SELECT","CORRECTION","Select the first PDF, illa second PDF",{"ordinal":"second","file_type":"PDF"}),
]


def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    rows=[]
    for action,speech,text,slots in CASES:
        spans={}
        for key,value in slots.items():
            start=text.casefold().rfind(value.casefold())
            if start<0:
                raise ValueError((text,key,value))
            spans[key]={"start":start,"end":start+len(value),"surface":text[start:start+len(value)]}
        row={"text":text,"speech_act":speech,"speech_coarse":SPEECH_COARSE[speech],
             "action_concept":action,"action_family":ACTION_FAMILY[action],
             "should_execute":speech in {"COMMAND","CORRECTION"},
             "negated":speech=="NEGATED_COMMAND","slots":spans,
             "label_source":"authored_tiny_overfit_diagnostic"}
        rows.append(row)
    assert len(rows)==48
    with OUT.open("w",encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row,ensure_ascii=False)+"\n")
    print(json.dumps({"rows":len(rows),"sha256":hashlib.sha256(OUT.read_bytes()).hexdigest(),
                      "actions":len({x["action_concept"] for x in rows}),
                      "speech_acts":len({x["speech_act"] for x in rows})}))


if __name__=="__main__":
    main()
