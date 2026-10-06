import pytest
torch=pytest.importorskip('torch')
pytest.importorskip('transformers')
from transformers import AutoTokenizer
from scripts.nlp_structural_model import BASE,vocabulary,encode,token_bounds,recommend
from scripts.nlp_structural_data import generated
from scripts.nlp_structural_evaluate import claim_once

def test_end_exclusive_token_alignment_whitespace_subwords_unicode_and_punctuation():
    rows=[r for r in generated() if r['partition']=='TRAIN']
    vocab=vocabulary(rows);tok=AutoTokenizer.from_pretrained(str(BASE),local_files_only=True,use_fast=True)
    samples=[next(r for r in rows if r['language']==lang and r['frame']['slots']) for lang in ('ENGLISH','TANGLISH','TAMIL','MIXED','ASR')]
    x,y=encode(tok,samples,vocab)
    for i,row in enumerate(samples):
        for s in row['frame']['slots']:
            idx=vocab['slots'].index(s['slot']);start=int(y['start'][i,idx]);end=int(y['end'][i,idx])
            assert start>0 and end>=start
            a=x['offset_mapping'][i,start,0].item()-7;b=x['offset_mapping'][i,end,1].item()-7
            a,b=token_bounds(row['text'],a,b)
            assert 0<=a<b<=len(row['text'])
            assert row['text'][a:b].strip()

def test_no_execution_for_negation_context_status_hypothetical_or_unresolved_correction():
    f={'action':'SEND','confidence':.99,'speech_act':'COMMAND','context_required':False,'reference':False,
        'negation':False,'unresolved_correction':False,'should_execute':True}
    c={'execute_threshold':.9,'escalate_threshold':.6,'clarify_threshold':.3}
    assert recommend(f,c)=='EXECUTE'
    for key in ('negation','context_required','reference','unresolved_correction'):
        assert recommend({**f,key:True},c)!='EXECUTE'
    for speech in ('STATUS_QUERY','QUESTION','INFORMATION','AMBIGUOUS'):
        assert recommend({**f,'speech_act':speech},c)!='EXECUTE'
    assert recommend(f,{**c,'execute_threshold':1.01})!='EXECUTE'
    from scripts.nlp_structural_policy import recommend as guarded_recommend
    assert guarded_recommend({**f,'input_truncated':True},c)=='CLARIFY'

def test_locked_partition_claim_cannot_be_reused(tmp_path):
    marker=tmp_path/'consumed.json';claim_once(marker,{'claimed_before_read':True})
    with pytest.raises(FileExistsError):claim_once(marker,{'rerun':True})

def test_frozen_configuration_refuses_changed_model_calibration_and_base(tmp_path,monkeypatch):
    import json
    import scripts.nlp_structural_evaluate as ev
    from scripts.nlp_provisional_data import sha
    base=tmp_path/'base';base.mkdir();(base/'weights').write_bytes(b'base')
    (base/'stage24_model_manifest.json').write_text(json.dumps({'files':{'weights':{'sha256':sha(base/'weights')}}}))
    monkeypatch.setattr(ev,'BASE',base);monkeypatch.setattr(ev,'SOURCES',[]);monkeypatch.setattr(ev,'verify',lambda:[])
    directory=tmp_path/'data';run=directory/'model';run.mkdir(parents=True)
    (directory/'manifest.json').write_text('{}')
    for f in ('candidate.pt','vocab.json','calibration.json','training_report.json'):(run/f).write_text('{}')
    ev.freeze(directory,'model');ev.verify_config(directory,'model')
    (run/'calibration.json').write_text('{"execute_threshold":0}')
    with pytest.raises(AssertionError):ev.verify_config(directory,'model')
    (run/'calibration.json').write_text('{}');(base/'weights').write_bytes(b'changed')
    with pytest.raises(AssertionError):ev.verify_config(directory,'model')

def test_vectorized_typed_heads_preserve_outputs_and_gradients():
    from scripts.nlp_structural_model import stacked_linear
    import copy
    torch.manual_seed(42)
    heads=torch.nn.ModuleDict({str(i):torch.nn.Linear(7,2) for i in range(33)})
    other=copy.deepcopy(heads);x=torch.randn(2,9,7,requires_grad=True);y=x.detach().clone().requires_grad_()
    expected=torch.cat([h(x) for h in heads.values()],dim=-1);actual=stacked_linear(y,other)
    assert torch.allclose(expected,actual,atol=1e-6)
    expected.square().sum().backward();actual.square().sum().backward()
    assert torch.allclose(x.grad,y.grad,atol=1e-5)
    for a,b in zip(heads.values(),other.values()):
        assert torch.allclose(a.weight.grad,b.weight.grad,atol=1e-5)
        assert torch.allclose(a.bias.grad,b.bias.grad,atol=1e-5)
