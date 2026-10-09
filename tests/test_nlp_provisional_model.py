"""Offline policy/calibration tests; no encoder load or evaluation-data access."""
import copy
import pytest

torch=pytest.importorskip('torch')
pytest.importorskip('transformers')
from scripts.nlp_provisional_model import recommendation, build_frame, HEADS
from scripts.nlp_provisional_train import calibration


def test_uncertainty_negation_corrections_references_never_execute():
    cal={'execute_threshold':.9,'escalate_threshold':.6,'clarify_threshold':.3}
    base={'confidence':.99,'action':'SEND','speech_act':'COMMAND','context_required':False,
          'reference':False,'negation':False,'correction':False,'should_execute':True}
    assert recommendation(base,cal)=='EXECUTE'
    for key in ('negation','correction','reference','context_required'):
        assert recommendation({**base,key:True},cal)!='EXECUTE'
    assert recommendation({**base,'confidence':.2},cal)=='UNKNOWN'
    assert recommendation({**base,'action':'UNKNOWN'},cal)=='UNKNOWN'
    assert recommendation({**base,'speech_act':'AMBIGUOUS'},cal)=='CLARIFY'
    assert recommendation(base,{**cal,'execute_threshold':1.01})!='EXECUTE'


def test_calibration_with_no_joint_correct_cases_disables_execute():
    vocab={'action':['UNKNOWN','SEND'],'domain':['FILES','WHATSAPP'],
           'speech_act':['COMMAND','AMBIGUOUS'],'object_type':['FileRef','MessageRef'],
           **{k:[False,True] for k in ('negation','correction','reference','context_required','should_execute')}}
    outputs={k:torch.tensor([[4.,0.]]*6) for k in HEADS}
    outputs['should_execute']=torch.tensor([[0.,4.]]*6)
    outputs['slot_tags']=torch.tensor([[[4.,0.,0.]]]*6)
    labels={k:torch.zeros(6,dtype=torch.long) for k in HEADS};labels['action']=torch.ones(6,dtype=torch.long)
    labels['slot_tags']=torch.zeros((6,1),dtype=torch.long)
    rows=[{'frame':{'action_concept':'SEND','domain':'FILES','should_execute':True,'negations':[],
                    'corrections':[],'references':[]}} for _ in range(6)]
    result=calibration(outputs,labels,rows,vocab)
    assert result['partition']=='DEV_ONLY'
    assert result['no_safe_execute_threshold']
    assert result['execute_threshold']>1
