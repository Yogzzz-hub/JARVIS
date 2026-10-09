import json
import pytest
pytest.importorskip('torch')
pytest.importorskip('transformers')


def setup_frozen(tmp_path,monkeypatch):
    import scripts.nlp_structural_evaluate as ev
    from scripts.nlp_provisional_data import sha
    base=tmp_path/'base';base.mkdir();(base/'weights').write_bytes(b'base')
    (base/'stage24_model_manifest.json').write_text(json.dumps({'files':{'weights':{'sha256':sha(base/'weights')}}}))
    dependency=tmp_path/'registry.py';dependency.write_text('original registry')
    monkeypatch.setattr(ev,'BASE',base);monkeypatch.setattr(ev,'SOURCES',[])
    monkeypatch.setattr(ev,'RUNTIME_SOURCES',[str(dependency)])
    monkeypatch.setattr(ev,'software_versions',lambda:{'python':'fixed','torch':'fixed'})
    monkeypatch.setattr(ev,'verify',lambda:[])
    directory=tmp_path/'data';run=directory/'candidate';run.mkdir(parents=True)
    (directory/'manifest.json').write_text('{}')
    for file in ('candidate.pt','vocab.json','calibration.json','training_report.json'):(run/file).write_text('{}')
    ev.freeze(directory,'candidate');ev.verify_config(directory,'candidate')
    return ev,directory,dependency


def test_registry_dependency_change_refuses_locked_evaluation(tmp_path,monkeypatch):
    ev,directory,dependency=setup_frozen(tmp_path,monkeypatch)
    dependency.write_text('modified capability registry')
    with pytest.raises(AssertionError):ev.verify_config(directory,'candidate')


def test_software_version_change_refuses_locked_evaluation(tmp_path,monkeypatch):
    ev,directory,_=setup_frozen(tmp_path,monkeypatch)
    monkeypatch.setattr(ev,'software_versions',lambda:{'python':'fixed','torch':'changed'})
    with pytest.raises(AssertionError):ev.verify_config(directory,'candidate')
