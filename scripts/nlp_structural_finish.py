"""One-shot offline completion after all DEV training ablations finish.

Do not rerun consumed evaluations. This runner has no planner/tool/deployment API.
"""
import argparse,json,subprocess,sys
from pathlib import Path
from scripts.nlp_provisional_data import immutable,canonical,sha
from scripts.stage25_freeze import verify


def finish(directory):
    for name in ('canonical_only','canonical_aux','legacy_coverage'):
        for file in ('training_report.json','calibration.json','evaluation_DEV.json','bio_decoder_DEV.json'):
            assert (directory/name/file).exists(),f'Incomplete DEV experiment: {name}/{file}'
    assert not (directory/'selected_candidate.json').exists(),'Already frozen; never restart the one-shot runner'
    for partition in ('TEST_V2','PROVISIONAL_HOLDOUT_V2'):
        assert not (directory/(partition+'_consumed.json')).exists()
    def run(module,*args):
        subprocess.run([sys.executable,'-m',module,str(directory),*args],check=True)
    run('scripts.nlp_structural_select')
    # The selector verifies base/model/source hashes and seals the configuration.
    run('scripts.nlp_structural_evaluate','--name','candidate','--partition','DEV')
    run('scripts.nlp_structural_diagnostics')
    run('scripts.nlp_structural_evaluate','--name','candidate','--partition','TEST_V2')
    run('scripts.nlp_structural_evaluate','--name','candidate','--partition','PROVISIONAL_HOLDOUT_V2')
    from scripts.nlp_structural_evaluate import verify_config
    verify_config(directory,'candidate')
    preservation={}
    for snapshot in ('preservation_snapshot.json','production_preservation_snapshot.json'):
        for file,expected in json.loads((directory/snapshot).read_text()).items():
            assert sha(Path(file))==expected,file
            preservation[file]=True
    assert verify()==[]
    from scripts.nlp_structural_data import V1
    inputs=json.loads((directory/'verified_v1_development_inputs.json').read_text())['inputs']
    for partition,expected in inputs.items():assert sha(V1/(partition+'.jsonl'))==expected,partition
    tests=json.loads((directory/'test_verification.json').read_text())
    additional=json.loads((directory/'dependency_test_verification.json').read_text())
    tests['groups'].append({'scope':additional['scope'],'passed':additional['passed'],'failed':additional['failed']})
    tests['total_passed']+=additional['passed'];tests['test_hashes'].update(additional['test_hashes'])
    for file,expected in tests['test_hashes'].items():assert sha(Path(file))==expected,file
    markers={}
    for partition in ('TEST_V2','PROVISIONAL_HOLDOUT_V2'):
        marker=json.loads((directory/(partition+'_consumed.json')).read_text())
        assert marker['claimed_before_read'] and marker['configuration_sha256']==sha(directory/'candidate/frozen_configuration.json')
        markers[partition]=marker
    immutable(directory/'verification.json',canonical({'tests':tests,'frozen_source_verified':True,
        'preservation':preservation,'configuration_verified':True,'V1_development_inputs_verified':True,'consumption_claims':markers,
        'production_enabled':False,'shadow_enabled':False,'human_validation':'DEFERRED'}))
    run('scripts.nlp_structural_report')
    path=Path('jarvis/config/nlp_candidate.json');config=json.loads(path.read_text())
    current=config['CURRENT_PRODUCTION'].copy()
    config['NLP_CANDIDATE'].update({'dataset_directory':directory.as_posix(),'artifact_directory':'candidate',
        'trained':True,'accepted':False,'production_enabled':False,'shadow_enabled':False,
        'mode':'offline_development_only','stage':'STRUCTURAL_REPAIR_V2','human_validation':'DEFERRED'})
    config['deployment_state']='MORE_DEVELOPMENT_REQUIRED'
    assert config['CURRENT_PRODUCTION']==current
    path.write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
    print('STRUCTURAL_REPAIR_V2 complete: MORE_DEVELOPMENT_REQUIRED; production unchanged; shadow OFF',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);finish(parser.parse_args().directory)
