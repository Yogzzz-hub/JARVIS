from scripts.nlp_structural_frame import normalize_literal_values,complete
from scripts.nlp_structural_policy import ambiguous_time,recommend


def test_open_numeric_ranges_and_identifiers_survive_canonical_frame():
    frame={'slots':[{'slot':'count','value':1,'span':{'surface':'137'}},
                    {'slot':'time','value':'11:00','span':{'surface':'9:45 pm'}},
                    {'slot':'file','value':'Next.js.config.ts','span':{'surface':'Next.js.config.ts'}}]}
    normalize_literal_values(frame)
    assert frame['slots'][0]['value']==137
    assert frame['slots'][1]['value']=='21:45'
    assert frame['slots'][2]['value']=='Next.js.config.ts'


def test_bare_time_cannot_acquire_am_pm_from_closed_model_head():
    frame={'slots':[{'slot':'time','value':'16:00','span':{'surface':'4 ku'}}]}
    assert ambiguous_time(frame)
    assert not ambiguous_time(frame,{'afternoon_low_hours':True})


def test_unsupported_capability_contract_cannot_recommend_execution():
    f={'action':'VERIFY','domain':'IDE','object_type':'ProjectRef','confidence':.99,
       'speech_act':'COMMAND','context_required':False,'reference':False,'negation':False,
       'unresolved_correction':False,'should_execute':True}
    cal={'execute_threshold':.9,'escalate_threshold':.6,'clarify_threshold':.3}
    assert recommend(f,cal)=='ESCALATE'


def test_ordinal_reference_remains_unresolved_in_existing_frame_contract():
    frame={'domain':'FILES','action':'OPEN','object_type':'FileRef','raw_text':'open second one',
           'slots':[],'values':{'ordinal':2},'reference':True,'context_required':True,
           'references':[],'corrections':[],'negation':False,'speech_act':'COMMAND',
           'recommendation':'CLARIFY','confidence':.8}
    out=complete(frame)
    assert out['references']==[{'type':'OrdinalRef','ordinal':2,'requires_context_resolution':True,'value':None}]
    assert out['jarvis_semantic_frame']['language_features']['controls_tools'] is False
    assert out['jarvis_semantic_frame']['actionability'] is False
