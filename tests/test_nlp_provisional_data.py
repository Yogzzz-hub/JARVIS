import copy
import hashlib
from pathlib import Path

from scripts.nlp_provisional_data import authored_rows, normalize, split_rows, immutable


def test_family_and_duplicate_union_no_leakage():
    rows=[{'id':str(i),'family':'family:'+str(i),'text':'unique utterance '+str(i)} for i in range(120)]
    rows.extend([{'id':'related','family':'family:3','text':'paraphrase'},
                 {'id':'duplicate','family':'another','text':'unique utterance 3'},
                 {'id':'construction_a','family':'one','construction_family':'shared','text':'construction first'},
                 {'id':'construction_b','family':'two','construction_family':'shared','text':'construction second'}])
    split=split_rows(rows);part={r['id']:k for k,group in split.items() for r in group}
    assert part['3']==part['related']==part['duplicate']
    assert part['construction_a']==part['construction_b']
    assert split_rows(copy.deepcopy(rows))==split
    sets=[{r['split_family'] for r in group} for group in split.values()]
    assert all(not a&b for i,a in enumerate(sets) for b in sets[i+1:])


def test_immutable_outputs(tmp_path):
    path=tmp_path/'locked.json';immutable(path,b'original');immutable(path,b'original')
    import pytest
    with pytest.raises(ValueError):immutable(path,b'replacement')
    assert path.read_bytes()==b'original'


def test_raw_identifiers_and_authored_spans():
    assert normalize('  Next.js  https://a.test/Q?ID=3   Arun@example.com  ')== 'Next.js https://a.test/Q?ID=3 Arun@example.com'
    rows=list(authored_rows());assert any(r['language']=='ASR' for r in rows)
    for r in rows:
        assert r['raw_text']==r['text']
        for s in r['frame']['slots']:
            assert r['text'][s['start']:s['end']]==s['surface']


def test_provisional_manifest_excludes_flagged_and_preserves_ontology():
    import json
    from scripts.nlp_provisional_data import DEST
    from scripts.unified_nlp_audit import AuditStore
    store=AuditStore();ai=store.precheck()
    expected={k for k,v in ai.items() if v['ai_precheck_status']=='LIKELY_APPROVE'}
    manifests=list(DEST.glob('*/stage25_ai_provisional_manifest_*.json'))
    assert manifests
    for path in manifests:
        value=json.loads(path.read_text())
        assert set(value['accepted_row_ids'])==expected
        assert len(value['excluded_row_ids'])==12
        assert not set(value['accepted_row_ids'])&set(value['excluded_row_ids'])
        assert value['human_audit']=='DEFERRED_NOT_COMPLETED'
        assert not value['human_approval_inferred']
        assert value['family_leakage']==0
        # Hash-check evaluation files without reading their annotations.
        for split in value['splits'].values():
            assert hashlib.sha256((path.parent/split['file']).read_bytes()).hexdigest()==split['sha256']
