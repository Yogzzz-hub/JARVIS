import json
from pathlib import Path
import pytest
from scripts.nlp_structural_data import generated,coverage,TASKS
from scripts.tanglish_stage24_ontology import ACTION_FAMILY
from scripts.nlp_structural_metrics import metrics
from scripts.nlp_structural_slots import typed_slot,reconstruct

def test_full_training_coverage_and_declared_family_isolation():
    rows=list(generated());parts={p:{r['family'] for r in rows if r['partition']==p} for p in ('TRAIN','DEV','TEST_V2','PROVISIONAL_HOLDOUT_V2')}
    assert set(TASKS)==set(ACTION_FAMILY)
    for a in parts:
        for b in parts:
            if a!=b:assert not parts[a]&parts[b]
    for lang in ('ENGLISH','TANGLISH','MIXED'):
        assert set(ACTION_FAMILY)<= {r['frame']['action_concept'] for r in rows if r['partition']=='TRAIN' and r['language']==lang}
    for row in rows:
        assert '???' not in row['text']
        for s in row['frame']['slots']:assert row['text'][s['start']:s['end']]==s['surface']

def test_status_queries_do_not_start_resources_and_asr_stays_in_family():
    rows=list(generated());index={r['id']:r for r in rows}
    for r in rows:
        if r['frame']['speech_act']=='STATUS_QUERY':
            assert r['frame']['action_concept']=='CHECK' and not r['frame']['should_execute']
            assert r['frame']['recipient'] is None and all(s['slot']!='recipient' for s in r['frame']['slots'])
        if r['id'].endswith('_asr'):
            parent=index[r['id'][:-4]];assert r['family']==parent['family'] and r['partition']==parent['partition']

def test_zero_execution_coverage_is_not_perfect_precision():
    row=next(r for r in generated() if r['frame']['speech_act']=='COMMAND')
    pred={'action':row['frame']['action_concept'],'domain':row['frame']['domain'],'speech_act':'COMMAND','slots':[],
        'negation':False,'correction':False,'reference':False,'corrections':[],'references':[],'recommendation':'UNKNOWN','should_execute':True}
    m=metrics([row],[pred]);assert m['execute_precision'] is None and m['execute_coverage']==0

def test_unicode_and_repeated_evidence_use_codepoints_end_exclusive():
    text='பிரியா க்கு, இல்லை Deepa க்கு'
    frame=reconstruct(text,[],'SEND','WHATSAPP','MessageRef',has_correction=True)
    assert frame['recipient']=='Deepa' and frame['corrections'][0]['superseded']=='பிரியா'
    for s in frame['slots']:assert text[s['span']['start']:s['span']['end']]==s['span']['surface']

def test_oracle_overlay_does_not_change_new_production_registry():
    from jarvis.core.capabilities.registry import CapabilityRegistry
    from scripts.nlp_structural_capabilities import OfflineFrameRetriever,oracle
    before={c.id for c in CapabilityRegistry().list_all()};overlay=OfflineFrameRetriever()
    rows=[r for r in generated() if r['partition']=='DEV'];result=oracle(rows,overlay)
    assert result['recall_at_1']>=.9 and result['recall_at_5']>=.99
    assert {c.id for c in CapabilityRegistry().list_all()}==before
    assert 'google.drive_download' not in before
