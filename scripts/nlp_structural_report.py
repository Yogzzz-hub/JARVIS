"""Append V2 evidence without rewriting V1 model or consumed evaluations."""
import argparse,json
from pathlib import Path
from scripts.nlp_provisional_data import canonical,sha

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def pct(v):return 'N/A' if v is None else f'{v*100:.2f}%'
def triples(m):return ' / '.join(pct(m[k]) for k in ('precision','recall','f1'))
def gates(result,oracle):
    m=result['metrics'];checks={'action':m['action']>=.9,'canonical_slot_f1':(m['canonical_slots']['f1'] or 0)>=.9,
        'recipient':(m['recipient_accuracy'] or 0)>=.95,'negation_positive_recall':(m['negation_positive_recall'] or 0)>=.99,
        'correction_reconstruction':(m['correction_reconstruction'] or 0)>=.95,'reference_typing':(m['reference_type_accuracy'] or 0)>=.95,
        'capability_oracle_at5':oracle['recall_at_5']>=.99,'end_to_end_capability_at5':(m['capability']['recall_at_5'] or 0)>=.98,
        'zero_critical_recommendations':m['counts'].get('critical_recommendations',0)==0,
        'execute_precision':(m['execute_precision'] or 0)>=.99,'useful_execute_coverage':(m['execute_coverage'] or 0)>=.5,
        'warm_p95':result['latency']['p95_ms']<=150,'human_validation':False}
    return checks
def write(directory):
    selected=load(directory/'selected_candidate.json')['experiment'];run=directory/selected
    data=load(directory/'manifest.json');train=load(run/'training_report.json');cal=load(run/'calibration.json')
    oracle=load(directory/'capability_oracle_DEV.json');paired=load(directory/'paired_repaired_oracle_DEV.json')
    evaluations={p:load(run/('locked_evaluation_'+p+'.json')) for p in ('DEV','TEST_V2','PROVISIONAL_HOLDOUT_V2')}
    check=gates(evaluations['PROVISIONAL_HOLDOUT_V2'],oracle)
    check['all_measured_warm_p95_within_150_ms']=all(r['latency']['p95_ms']<=150 for r in evaluations.values())
    text=['## STRUCTURAL_REPAIR_V2','', '**Decision: MORE_DEVELOPMENT_REQUIRED. CURRENT_PRODUCTION unchanged; candidate OFFLINE_DEVELOPMENT; shadow OFF.**','',
        'Human audit remains deferred: 10 owner REJECT decisions, no APPROVE/FIX_LABEL decisions. This pass does not seal a human-audited manifest or grant production acceptance. All new data and measurements remain synthetic/AI-assisted development evidence.','',
        '### Root causes and repairs','',
        'V1 coupled canonical values to brittle BIO boundaries, including tokenizer whitespace. V2 uses 33 independent typed start/end heads, separate closed-value heads for time/date/count/ordinal/number/percentage, and an optional BIO auxiliary loss. Character evidence uses original Unicode codepoints and end-exclusive spans; canonical values are evaluated independently. Technical tokens retain their original spelling.','',
        'Recipient, sender and owner reconstruction uses relation markers and action/domain evidence. Numeric time tokens and ontology verbs cannot become contacts merely because they precede a relation marker. Corrections retain superseded and active values. Bare times require context to distinguish morning/afternoon. Typed references remain unresolved and require WorkingContext; NLP never invents a resolved resource. Status queries use CHECK and cannot authorize START/RUN.','',
        'The shared action-family/action heads retain the existing 62-action ontology. A coverage audit found missing English/mixed training labels in V1. Newly authored V2 development data covers every action in English, Tanglish and mixed TRAIN. Coverage does not imply that every intent has an executable registered capability.','',
        'The capability repair is an offline registry overlay: three existing Drive tool definitions supply metadata without constructing clients or calling tools. Typed domain/action/resource contracts fix namespace/action ambiguity, including Gmail FIND/SEARCH → read/search-email capability. Production registry and router files were not changed.','',
        '### Data, coverage and isolation','',f'Active dataset: `{directory.as_posix()}`. Manifest SHA-256: `{sha(directory/"manifest.json")}`. Full action × domain × language × split counts: `coverage_v2.csv`; missing/thin coverage: `coverage_diagnostics.json`.','',
        '| Partition | Rows | Declared families | English | Tanglish | Tamil | Mixed | ASR |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for p,v in data['splits'].items():text.append('| '+p+' | '+str(v['rows'])+' | '+str(v['families'])+' | '+' | '.join(str(v['languages'].get(l,0)) for l in ('ENGLISH','TANGLISH','TAMIL','MIXED','ASR'))+' |')
    slot_coverage=load(directory/'slot_coverage_development.json')['missing_train_slot_types']
    text+=['','TRAIN slot-type coverage (TEXT or CONTEXT gold): '+', '.join(language+' '+str(33-len(missing))+'/33' for language,missing in slot_coverage.items())+'. Detailed zero-filled TRAIN/DEV counts and missing types are in slot_coverage_development.json. Every type has a head; that does not supply missing positive examples. Action/domain coverage uses the declared supported pair inventory, not the full Cartesian product of every domain and action.','']
    text+=['','Declared construction-family intersections and exact normalized duplicate intersections: 0. All language and mild-ASR children stay with their parent construction. Only eligible V1 TRAIN/DEV source rows are reused; retired V1 TEST/HOLDOUT rows and their failures were not used.','',
        'The fresh authored evaluations reserve two construction families each, with new sample IDs and varied resource identifiers. Entity-value novelty is not guaranteed. This is a narrow synthetic construction benchmark, not a verified natural-language semantic-distance holdout. Shared ontology/primitive clause patterns still exist across families; a comprehensive near-paraphrase independence audit is not established. Native Tamil is limited to ten authored native-verb concepts plus existing source coverage; naturalness and labels still require human validation. These limitations block final production acceptance.','',
        'Earlier preflight datasets and interrupted experiments were retired before locked evaluation when development checks revealed role-label defects, identifier shortcuts and repeated Tamil core constructions. One exploratory run completed DEV-only fitting/calibration; its results were discarded. The final dataset uses distinct Tamil constructions across reserved families. None of these preflight candidates is selected.','',
        '### Training, selection and calibration','',f'Encoder remains multilingual-e5-small at revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`. Selected experiment: `{selected}`. Best epoch: {train["chosen_epoch"]}; {len(train["history"])} epochs actually run. Selection: {train["selection"]}. Training elapsed {train["elapsed_seconds"]:.2f} s; maximum observed epoch-end process RAM {train["peak_rss_mb"]:.1f} MiB; peak allocated VRAM {train["peak_vram_mb"]:.1f} MiB.','',
        f'DEV-only calibration: temperature {cal["temperature"]}, execute threshold {cal["execute_threshold"]:.6f}, escalate {cal["escalate_threshold"]:.6f}, clarify {cal["clarify_threshold"]:.6f}. Calibration requires at least 20 joint-correctness cases at >=99% observed precision; this is an empirical DEV criterion, not a statistical guarantee. Execute is an offline recommendation only.','',
        'Negation, unresolved corrections, references, context dependency and non-command speech acts cannot recommend execution. Zero coverage does not pass. A 50% eligible-command coverage floor is reported as a development usefulness check, not a tuned confidence threshold. CUDA bitwise reproducibility is not established.','',
        f'Model SHA-256 `{sha(run/"candidate.pt")}`. Calibration SHA-256 `{sha(run/"calibration.json")}`. Configuration SHA-256 `{sha(run/"frozen_configuration.json")}`. All inference/training source hashes were frozen before locked evaluation. TEST_V2 and PROVISIONAL_HOLDOUT_V2 each have a one-time consumption claim written before reading; neither influenced training, calibration or candidate selection.','',
        '### DEV ablations','', '| Experiment | Action | Canonical slot F1 | Exact span F1 | Recipient |','|---|---:|---:|---:|---:|']
    historical=load(directory/'historical_DEV_ablations.json');old=historical['A_v1_BIO_canonicalized_values']
    text.append('| A: V1 BIO, canonical scoring on V1 DEV | '+ ' | '.join(pct(old[k]) if k in old else 'N/A' for k in ('action',))+' | '+pct(old['canonical_slots']['f1'])+' | '+pct(old['exact_spans']['f1'])+' | '+pct(old['recipient_accuracy'])+' |')
    for name,label in [('canonical_only','B: typed canonical, no BIO loss'),('canonical_aux','C: typed canonical + BIO auxiliary'),('legacy_coverage','D: same typed model, legacy action/language coverage')]:
        p=directory/name/'final_policy_DEV.json'
        if p.exists():
            m=load(p)['metrics'];text.append(f'| {label} | {pct(m["action"])} | {pct(m["canonical_slots"]["f1"])} | {pct(m["exact_spans"]["f1"])} | {pct(m["recipient_accuracy"])} |')
    bio=load(run/'bio_decoder_DEV.json')['metrics'];text.append(f'| Same selected V2 weights, BIO decoder only | {pct(bio["action"])} | {pct(bio["canonical_slots"]["f1"])} | {pct(bio["exact_spans"]["f1"])} | {pct(bio["recipient_accuracy"])} |')
    text+=['',f'Selected source ablation: `{train.get("source_experiment",selected)}`. Trainable parameters: {train.get("trainable_parameters","not recorded")}; total parameters: {train.get("total_parameters","not recorded")}.','',
        'B/C/D are rescored under the same final DEV boundary policy. Training uses CUDA FP16 autocast/GradScaler; DEV and inference use FP32. Vectorized typed-head outputs and gradients were checked against separate heads. If the selected model has no BIO loss, its BIO head is untrained and that decoder comparison is diagnostic only. Literal numeric/date/time evidence is preserved beyond the closed training vocabulary. Truncated inputs and ambiguous bare times require clarification; executable recommendations require a known typed capability contract.','']
    text+=['','B/C use identical TRAIN/DEV, seed, objective and stopping rule; their loss formulation differs. D filters V2 TRAIN by V1 action/language coverage and consequently also changes row count/composition; it is a coverage ablation, not a row-matched causal study. A is historical and uses a different DEV set, so it cannot isolate decoder changes from data/model changes.','',
        'E: paired gold-frame oracle on the same 240 V1 DEV cases improves Recall@1/@3/@5/@10 from 66.67/83.33/83.33/83.33% to '+ '/'.join(pct(paired[f'recall_at_{k}']) for k in (1,3,5,10))+'. New V2 DEV oracle ('+str(oracle['cases'])+' atomic gold cases): '+ '/'.join(pct(oracle[f'recall_at_{k}']) for k in (1,3,5,10))+'. This validates the covered contracts, not the entire registry, live availability or composition.','',
        '### Separate language and slot benchmarks','',
        '| Set / language | N | Domain | Action | Canonical P/R/F1 | Exact span P/R/F1 | Recipient | Sender | Time | Ordinal | Negation positive recall | Correction reconstruction | Reference type | Speech act | Unknown/clarify |','|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for part,result in evaluations.items():
        for lang,m in [*result['languages'].items(),('ALL',result['metrics'])]:
            text.append('| '+part+' / '+lang+' | '+str(m['n'])+' | '+pct(m['domain'])+' | '+pct(m['action'])+' | '+triples(m['canonical_slots'])+' | '+triples(m['exact_spans'])+' | '+' | '.join(pct(m[k]) for k in ('recipient_accuracy','sender_accuracy','time_accuracy','ordinal_accuracy','negation_positive_recall','correction_reconstruction','reference_type_accuracy','speech_act','unknown_clarify'))+' |')
    text+=['','N/A means no eligible gold cases. Presence accuracy is not substituted for reconstruction or positive recall. Exact-span scores remain sensitive to tokenizer subword/particle boundaries. Canonical scores count typed values, including incorrect/extraneous values. Sender/ordinal and all 33 types are not exhaustively represented in fresh evaluation; focused diagnostics do not substitute for benchmark coverage.','',
        '| Set | Recipient gold | Sender gold | Time gold | Ordinal gold | Negation gold | Correction gold | Reference gold | Unknown gold | Eligible commands |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for part,result in evaluations.items():
        c=result['metrics']['counts'];text.append('| '+part+' | '+' | '.join(str(c.get(k,0)) for k in ('recipient_n','sender_n','time_n','ordinal_n','negation_n','correction_n','reference_n','unknown_n','executable_n'))+' |')
    text+=['','### Capability, safety and executable recommendations','',
        '| Set | Capability cases | R@1 | R@3 | R@5 | R@10 | Execute precision | Eligible-command coverage | Critical wrong recommendations | Missed negation | Raw wrong action | Raw wrong domain |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for part,result in evaluations.items():
        m=result['metrics'];c=m['counts'];cap=m['capability']
        text.append('| '+part+' | '+str(cap['cases'])+' | '+' | '.join(pct(cap[f'recall_at_{k}']) for k in (1,3,5,10))+' | '+pct(m['execute_precision'])+' | '+pct(m['execute_coverage'])+' | '+str(c.get('critical_recommendations',0))+' | '+str(c.get('missed_negation',0))+' | '+str(c.get('raw_wrong_action',0))+' | '+str(c.get('raw_wrong_domain',0))+' |')
    text+=['','| Set | Raw wrong recipient | Missed correction | Wrong-recipient EXECUTE | Negation EXECUTE violation | Correction EXECUTE violation | Ambiguity EXECUTE violation | False-positive negation | Negation overall accuracy |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for part,result in evaluations.items():
        m=result['metrics'];c=m['counts']
        false_positive_negation=m['n']-c.get('negation_accuracy',0)-c.get('missed_negation',0)
        text.append('| '+part+' | '+' | '.join(str(c.get(k,0)) for k in ('raw_wrong_recipient','missed_correction','wrong_recipient_recommendations','negation_violation_recommendations','correction_violation_recommendations','ambiguity_execution_recommendations'))+' | '+str(false_positive_negation)+' | '+pct(m['negation_accuracy'])+' |')
    text+=['','No tools were executed. Critical counts are wrong offline EXECUTE recommendations scored against measured canonical/action/domain/speech/safety correctness, not claims about real tool incidents or complete frame correctness. Complete constraints, reference typing and resource correctness are not included in this joint calibration criterion. A safe abstention policy cannot compensate for poor recall, low coverage or raw semantic failures. Constraint extraction, cross-domain multi-step composition and contextual reference resolution remain unvalidated; no promotion/rollback or shadow hook was introduced.','',
        '### Latency and resources','', '| Set | Warm p50 ms | Warm p95 ms | First route ms | Startup ms | Loaded RAM MiB | Post RAM MiB | Allocated VRAM MiB | CPU % |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for part,r in evaluations.items():
        l=r['latency'];v=r['resources'];text.append('| '+part+' | '+' | '.join(f'{x:.2f}' for x in (l['p50_ms'],l['p95_ms'],l['first_route_ms'],l['startup_ms'],v['loaded_rss_mb'],v['post_rss_mb'],v['vram_mb'],v['cpu_one_core_percent']))+' |')
    text+=['','Warm latency excludes the first route and includes tokenization, encoder, canonical/frame construction and offline capability retrieval. Startup measures model/tokenizer initialization in a fresh process after framework imports, without forced cache eviction; full process-launch latency is not measured. RAM is this Python process; VRAM is allocated tensor memory, not whole-GPU utilization; CPU is one-core-equivalent process CPU/wall time. No network or deep LLM participates.','',
        'Measured latency varies substantially between the three processes. DEV and TEST_V2 exceed the preferred 150 ms warm p95 target, while the provisional holdout is below it. Other machine activity was not controlled; the cause is not established. No evaluation was rerun to obtain a faster number. The all-measured-runs latency check fails.','',
        '### CURRENT versus CANDIDATE and decision','',
        'CURRENT production was preview-benchmarked on fresh DEV before training with network/model/planner execution disabled. The adapter is partial and cannot establish a full English regression gate. V2 comparisons use production_baseline_independent_DEV.json, derived solely from recorded intent/slots; SEARCH remains SEARCH without consulting expected labels. The original helper used gold-aware SEARCH/FIND conversion, so its immutable recording is preserved but that conversion is excluded from this comparison. Production paths, registry, planner and tools remain unchanged.','',
        '| Provisional holdout gate | Pass |','|---|---|']
    for k,v in check.items():text.append('| '+k+' | '+('YES' if v else 'NO')+' |')
    text+=['','**MORE_DEVELOPMENT_REQUIRED.** No shadow recommendation or promotion. Human validation, richer independent evaluation families, full production English regression, complete constraints/references/correction coverage and critical semantic safety acceptance remain required. Evaluation failures are recorded only; they are not automatically admitted to training. Once intentionally used for development, these V2 evaluation sets must be retired and replaced.','']
    baseline=load(directory/'production_baseline_independent_DEV.json')['records'];dev=read_rows(directory/'DEV.jsonl');candidate=evaluations['DEV']['records']
    comparison=[]
    for lang in sorted({r['language'] for r in dev}):
        indexes=[i for i,r in enumerate(dev) if r['language']==lang]
        current=sum(baseline[i].get('action')==(dev[i]['frame']['action_concept'] or 'UNKNOWN') for i in indexes)/len(indexes)
        new=evaluations['DEV']['languages'][lang]['action'];comparison.append({'language':lang,'current_partial_preview_action':current,'candidate_action':new,'delta':new-current})
    text+=['| DEV language | CURRENT partial action | Candidate action | Delta pp |','|---|---:|---:|---:|']
    for r in comparison:text.append(f'| {r["language"]} | {pct(r["current_partial_preview_action"])} | {pct(r["candidate_action"])} | {r["delta"]*100:+.2f} |')
    paired_model=load(run/'paired_V1_DEV.json')['metrics'];focused=load(run/'diagnostics_DEVELOPMENT.json')
    text+=['','Paired before/after on the same historical V1 DEV: action '+pct(old['action'])+' -> '+pct(paired_model['action'])+', canonical slot F1 '+pct(old['canonical_slots']['f1'])+' -> '+pct(paired_model['canonical_slots']['f1'])+', recipient '+pct(old['recipient_accuracy'])+' -> '+pct(paired_model['recipient_accuracy'])+'. This development comparison was not used for model selection.','',
        f'Focused known development probes: {focused["all_checks_passed_cases"]}/{focused["cases"]} cases passed every stated check. These probes are neither training examples nor acceptance evidence. Detailed predicted frames and failed checks are retained in diagnostics_DEVELOPMENT.json.','',
        'Top V2 DEV action confusions: '+json.dumps(evaluations['DEV']['top_action_confusions'])+'.','',
        'Top V2 DEV domain confusions: '+json.dumps(evaluations['DEV']['top_domain_confusions'])+'.','',
        'Top V2 DEV speech-act confusions: '+json.dumps(evaluations['DEV']['top_speech_act_confusions'])+'.','',
        'Remaining structural gaps: legacy broad domains coexist with explicit service domains; full namespace reconciliation is not established. Canonical scoring includes gold contextual slots although NLP leaves references unresolved. Source/contact distinctions, negation scope, domain/action corrections, short and hypothetical requests and tool-required argument completeness remain incompletely validated. EXECUTE is only an offline semantic recommendation, not proof of tool readiness. Raw negation misses remain semantic safety failures even when abstention suppresses execution. High positive negation recall coexists with many false-positive negations, which suppress valid requests; it is not evidence that negation understanding passes overall.','',
        'Verification: '+str(load(directory/'verification.json')['tests']['total_passed'])+' unique tests passed, including slot/schema/Unicode/relation/coverage/ASR-family/status-query/offline-registry/policy/consumption and dependency/software drift refusal. Frozen source and owner audit histories remain byte-identical. Detailed verification evidence is stored separately in verification.json.','']
    report=Path('reports/JARVIS_ENGLISH_TANGLISH_NLP_FINAL.md');old=report.read_text(encoding='utf-8').split('## STRUCTURAL_REPAIR_V2')[0].rstrip();report.write_text(old+'\n\n'+'\n'.join(text),encoding='utf-8')
    summary={'status':'AI_ASSISTED_PROVISIONAL','stage':'STRUCTURAL_REPAIR_V2','shadow':'OFF','deployment_decision':'MORE_DEVELOPMENT_REQUIRED',
        'dataset_directory':directory.as_posix(),'selected_experiment':selected,'splits':data['splits'],'gates':check,
        'benchmarks':{p:{k:r[k] for k in ('metrics','languages','latency','resources')} for p,r in evaluations.items()},'current_partial_preview_comparison':comparison}
    (run/'dashboard_summary.json').write_bytes(canonical(summary));return summary
def read_rows(p):return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x]
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);write(p.parse_args().directory)
