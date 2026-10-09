"""Candidate boundary policy. Partial encoder inputs never recommend execution."""
import time
import re
from scripts.nlp_structural_model import Candidate,MAX_LENGTH,recommend as model_recommend
from scripts.nlp_provisional_model import input_text
from scripts.nlp_structural_slots import canonical_value
from scripts.nlp_structural_frame import complete
from scripts.nlp_structural_capabilities import CONTRACTS

def recommend(frame,calibration):
    if frame.get('input_truncated') or frame.get('ambiguous_time_evidence'):return 'CLARIFY'
    decision=model_recommend(frame,calibration)
    if decision=='EXECUTE' and not any(frame['domain']==domain and frame['action'] in actions and frame['object_type']==resource for domain,actions,resource in CONTRACTS.values()):
        return 'ESCALATE'
    return decision

def truncated(tokenizer,row):
    return len(tokenizer(input_text(row),truncation=False)['input_ids'])>MAX_LENGTH

def ambiguous_time(frame,context=None):
    for s in frame.get('slots',[]):
        if s['slot']!='time' or not s.get('span'):continue
        surface=s['span']['surface'].strip()
        # A closed value head cannot supply AM/PM absent from original evidence.
        if re.fullmatch(r'\d{1,2}\s*(?:ku)?',surface,re.I):
            raw=re.sub(r'\s*ku$','',surface,flags=re.I)
            value=canonical_value('time',raw,context if isinstance(context,dict) else None)
            if isinstance(value,dict) and value.get('requires_clarification'):return True
    return False

class GuardedCandidate(Candidate):
    def infer(self,row):
        started=time.perf_counter()
        frame=super().infer(row)
        frame['input_truncated']=truncated(self.tokenizer,row)
        frame['ambiguous_time_evidence']=ambiguous_time(frame,row.get('working_context'))
        frame['recommendation']=recommend(frame,self.calibration)
        frame=complete(frame)
        frame['latency_ms']=(time.perf_counter()-started)*1000
        return frame
