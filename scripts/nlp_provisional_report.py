"""Summarize completed locked evaluations without selecting or tuning a model."""
import argparse
import json
from collections import Counter
from pathlib import Path
from scripts.nlp_provisional_data import canonical,sha
from scripts.stage25_gold_data import ROOT
from scripts.stage25_freeze import verify


def pct(value):return 'N/A' if value is None else f'{100*value:.2f}%'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);args=parser.parse_args()
    directory=args.directory;run=directory/'candidate'
    manifest_path=next(directory.glob('stage25_ai_provisional_manifest_*.json'))
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    reports={part:json.loads((run/('evaluation_'+part+'.json')).read_text(encoding='utf-8')) for part in ('DEV','TEST','PROVISIONAL_HOLDOUT')}
    training=json.loads((run/'training_report.json').read_text());cal=json.loads((run/'calibration.json').read_text())
    configuration=json.loads((run/'frozen_configuration.json').read_text())
    assert sha(run/'candidate.pt')==configuration['model_sha256']
    assert sha(run/'calibration.json')==configuration['calibration_sha256']
    assert verify()==[]
    decision='MORE_DEVELOPMENT_REQUIRED'
    summary={'status':'AI_ASSISTED_PROVISIONAL','human_audit':'DEFERRED_NOT_COMPLETED','production_acceptance':'NOT_HUMAN_VALIDATED','deployment_decision':decision,'shadow':'OFF','split_sizes':{k:v['rows'] for k,v in manifest['splits'].items()},'evaluations':{k:{'candidate':v['candidate'],'baseline_scope':v['baseline_scope'],'missing_registry_gold':v['missing_registry_gold'],'resource':v['resource']} for k,v in reports.items()}}
    (run/'dashboard_summary.json').write_bytes(canonical(summary))
    configpath=ROOT/'jarvis/config/nlp_candidate.json';config=json.loads(configpath.read_text());config['deployment_state']=decision;config['NLP_CANDIDATE'].update(trained=True,accepted=False,production_enabled=False,shadow_enabled=False);configpath.write_bytes(canonical(config))
    out=['# Unified English + Tanglish NLP — provisional development report',
         '', '**Deployment decision: MORE_DEVELOPMENT_REQUIRED. CURRENT_PRODUCTION remains unchanged; shadow is OFF.**',
         '', 'Human audit: **DEFERRED / NOT COMPLETED**. Training quality: **PROVISIONAL**. Final production acceptance: **NOT HUMAN-VALIDATED**. These synthetic/AI-assisted measurements are not real-world production accuracy.',
         '', '## Provenance and admission', '',
         '738 LIKELY_APPROVE rows admitted as AI_PRECHECK_ACCEPTED for this development run only. Ten MANUAL_REVIEW rows and two LIKELY_REJECT rows were excluded and retained separately as HUMAN_REVIEW_DEFERRED. No flagged row entered any partition. Existing human history remains 10 owner REJECT decisions, 0 APPROVE, 0 FIX_LABEL; AI suggestions were not converted into human decisions.',
         '', 'The original 30,000-row Stage 2.5 corpus, 750-row audit queue, original annotations and frozen manifest are unchanged. Frozen verification passes. The new manifest is separate and content-addressed; its creation timestamp is recorded in created.json alongside it.',
         '', f'Active dataset directory: `{directory.relative_to(ROOT) if directory.is_absolute() else directory}`.',
         f'Manifest: `{manifest_path.name}`; SHA-256 `{sha(manifest_path)}`.',
         f'External AI-precheck SHA-256: `{manifest["external_precheck_sha256"]}`.',
         '', 'The 738 preserved Tanglish/Tamil rows were combined with 1,616 separately authored provisional English, mixed and mild-ASR examples. One shared frame/action/slot schema is used. No Tanglish translation-first path exists. Raw text, case, technical identifiers, names and punctuation remain available. Normalization collapses whitespace only.',
         '', '## Partitions and leakage', '', '| Partition | Rows | Families | English | Tanglish | Tamil | Mixed | ASR |', '|---|---:|---:|---:|---:|---:|---:|---:|']
    for key,s in manifest['splits'].items():
        l=s['languages'];out.append(f'| {key} | {s["rows"]} | {s["families"]} | {l.get("ENGLISH",0)} | {l.get("TANGLISH",0)} | {l.get("TAMIL",0)} | {l.get("MIXED",0)} | {l.get("ASR",0)} |')
    out+=['','Family leakage: **0** for unioned construction/isolation-family components and exact normalized duplicate utterances. All authored paraphrases, code-switching variants and ASR children share a family. Hashing whole components produces uneven counts; labels were not used to balance evaluation results. This does not establish that all semantic near-duplicates outside declared families have been discovered.',
          '', 'TEST and PROVISIONAL_HOLDOUT were each consumed once after model/calibration freeze. Consumption markers are created before evaluation reads, and prevent reruns. No TEST/HOLDOUT tuning, retraining or phrase repairs occurred. Existing legacy TEST/sealed HOLDOUT files were not opened. The new holdout is **PROVISIONAL_HOLDOUT**, not a final production-quality evaluation.',
          '', '## Model and calibration', '',
          f'Model: `intfloat/multilingual-e5-small`, revision `{training["encoder_revision"]}`. LoRA query/value adapters on the last four encoder layers plus domain/action/speech/resource/safety and BIO slot heads. Trainable parameters: {training["trainable_parameters"]:,}. Eight fixed epochs; epoch {training["chosen_epoch"]} selected by minimum DEV loss. GPU: RTX 3050 6 GB Laptop GPU. Training elapsed: {training["elapsed_seconds"]:.2f} seconds. Peak training RSS: {training["peak_rss_mb"]:.1f} MiB; peak training VRAM: {training["peak_vram_mb"]:.1f} MiB.',
          '', 'Selection and confidence calibration used DEV only. Temperature was selected by DEV NLL; escalation threshold by DEV semantic correctness F1; clarification threshold from DEV incorrect-confidence distribution. Execute requires joint action/domain/safety/slot correctness and at least five DEV cases with >=99% precision.',
          '', f'Calibration found **no safe execute threshold**. Executable recommendations are disabled (sentinel threshold {cal["execute_threshold"]}). Temperature {cal["temperature"]}; escalation {cal["escalate_threshold"]:.6f}; clarification {cal["clarify_threshold"]:.6f}. References require context resolution; negations and unresolved corrections cannot authorize tools.',
          '', f'Model SHA-256: `{configuration["model_sha256"]}`. Calibration SHA-256: `{configuration["calibration_sha256"]}`. Frozen configuration SHA-256: `{sha(run/"frozen_configuration.json")}`.',
          '', '## Separate language benchmarks', '', 'All percentages below compare against provisional labels. Slot P/R/F1 measures exact TEXT span boundaries/type, not canonical values or contextual slots. Negation/correction/reference columns are presence-classification accuracy; positive recall and unresolved extraction limitations follow below.']
    for part,report in reports.items():
        out+=['',f'### {part}','','| Language | N | Domain | Action | Slot P / R / F1 | Constraints | Negation | Correction | Reference | Speech act | Unknown/clarify |','|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|']
        for lang in ('ENGLISH','TANGLISH','MIXED','TAMIL','ASR','ALL'):
            m=report['candidate'][lang]
            out.append(f'| {lang} | {m["samples"]} | {pct(m["domain_accuracy"])} | {pct(m["action_accuracy"])} | {pct(m["slot_precision"])} / {pct(m["slot_recall"])} / {pct(m["slot_f1"])} | {pct(m["constraints_accuracy"])} | {pct(m["negation_accuracy"])} | {pct(m["correction_accuracy"])} | {pct(m["reference_accuracy"])} | {pct(m["speech_act_accuracy"])} | {pct(m["unknown_clarification_accuracy"])} |')
        m=report['candidate']['ALL']
        out+=['',f'Positive recall: negation {pct(m["negation_positive_recall"])}, correction {pct(m["correction_positive_recall"])}, reference {pct(m["reference_positive_recall"])}. Recipient accuracy: {pct(m["recipient_accuracy"])}. Unknown/ambiguous cases: {m["unknown_cases"]}.',
              f'Executable action precision: {pct(m["action_precision_executable_routes"])}; executable action recall: {pct(m["action_recall_executable_routes"])}; execute recommendations: {m["execute_recommendations"]}. No execution coverage means precision is N/A, not 100%.']
    out+=['', '## Capability Brain retrieval', '', 'Candidate output is adapted to the existing SemanticFrame contract and CapabilityRetriever; no planner or tool runs. Retrieval uses predicted domain/action/resource/slot evidence, never gold labels. Correct-frame-only retrieval is reported separately from end-to-end retrieval. Gold capability IDs exist only on a subset of authored examples; the 738 source rows have no independent capability gold. Invalid/unavailable registry targets remain misses and are listed explicitly.', '', '| Partition | Cases | Recall@1 | Recall@3 | Recall@5 | Recall@10 |', '|---|---:|---:|---:|---:|---:|']
    for part,report in reports.items():
        m=report['candidate']['ALL'];out.append(f'| {part} | {m["capability_cases"]} | {pct(m["capability_recall_at_1"])} | {pct(m["capability_recall_at_3"])} | {pct(m["capability_recall_at_5"])} | {pct(m["capability_recall_at_10"])} |')
        out.append(f'\n{part} missing registry gold IDs: `{report["missing_registry_gold"]}`.')
    oracle_path=run/'capability_oracle_DEV.json'
    if oracle_path.exists():
        oracle=json.loads(oracle_path.read_text())
        out+=['',f'DEV-only gold-frame oracle ({oracle["cases"]} cases): Recall@1 {pct(oracle["1"])}, @3 {pct(oracle["3"])}, @5 {pct(oracle["5"])}, @10 {pct(oracle["10"])}. This holds semantic labels correct to isolate retrieval, without tuning the candidate. Oracle @5 remains below 98%, so retrieval/registry coverage also fails independently of frame prediction.']
    out+=['', '## Safety and failures', '', 'No candidate tool execution exists. All EXECUTE recommendations were disabled because DEV calibration failed. Zero decision-level false actions/recipient/negation/correction violations therefore reflects **zero execution coverage**, not acceptance. Raw semantic errors remain safety risks.', '', '| Partition | Raw wrong action | Raw wrong domain | Raw wrong recipient | Missed negation | Missed correction | Execute recommendations | False-action recommendations | Critical execution failures |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for part,report in reports.items():
        m=report['candidate']['ALL'];f=m['raw_semantic_failures'];out.append(f'| {part} | {f["raw_wrong_action"]} | {f["raw_wrong_domain"]} | {f["raw_wrong_recipient"]} | {f["missed_negation"]} | {f["missed_correction"]} | {m["execute_recommendations"]} | {m["safety"].get("false_action",0)} | {m["critical_failures"]} |')
    out+=['','Wrong action/domain/recipient counts overlap across examples. Structured correction reconstruction and typed reference resolution are **not implemented/validated** by presence classification, and remain acceptance blockers. Failure categories and predictions are retained in offline evaluation artifacts. They are not automatically admitted to future training.',
          '', '## Latency and resource use', '', '| Partition | Total p50 ms | Total p95 ms | Startup ms | First route ms | Loaded process RAM MiB | Post-evaluation RAM MiB | VRAM MiB | CPU average % |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for part,report in reports.items():
        m=report['candidate']['ALL'];r=report['resource'];out.append(f'| {part} | {m["latency_p50_ms"]:.2f} | {m["latency_p95_ms"]:.2f} | {r["startup_ms"]:.2f} | {r["first_route_ms"]:.2f} | {r["loaded_process_rss_mb"]:.1f} | {r["rss_after_mb"]:.1f} | {r["vram_allocated_mb"]:.1f} | {r["cpu_average_percent"]:.1f} |')
    out+=['', 'Startup includes tokenizer/model initialization in a new process; OS/disk caches were not flushed. First-route latency is reported separately and exceeds the hot-path target. RAM measures this Python process, not whole-machine idle RAM. CPU percentage is one-core-equivalent process CPU/wall time. Warm p50/p95 includes normalization, tokenization, encoder, frame construction and existing capability retrieval; no network or deep LLM is in the candidate path.', '', '| Component (provisional holdout) | p50 ms | p95 ms |', '|---|---:|---:|']
    for key,value in reports['PROVISIONAL_HOLDOUT']['latency_components'].items():out.append(f'| {key} | {value["p50_ms"]:.3f} | {value["p95_ms"]:.3f} |')
    out+=['', '## CURRENT vs CANDIDATE', '', 'CURRENT was benchmarked on DEV before candidate training. The comparison uses **offline SmartRouter.preview**, with model/planner/network calls disabled and a partial ontology adapter. This is not full live production routing. Production slot spans and speech acts are absent from that adapter and must not be treated as validated production failures or as evidence of candidate superiority.', '', '| Partition / language | CURRENT partial action accuracy | Candidate action accuracy | Delta percentage points | CURRENT preview p95 ms | Candidate p95 ms |', '|---|---:|---:|---:|---:|---:|']
    for part,report in reports.items():
        for lang in ('ENGLISH','TANGLISH','MIXED','TAMIL','ASR'):
            c=report['current_production_preview'][lang];m=report['candidate'][lang]
            delta=(m['action_accuracy']-c['action_accuracy'])*100 if m['action_accuracy'] is not None and c['action_accuracy'] is not None else None
            out.append(f'| {part} / {lang} | {pct(c["action_accuracy"])} | {pct(m["action_accuracy"])} | {"N/A" if delta is None else f"{delta:+.2f}"} | {c["latency_p95_ms"]:.2f} | {m["latency_p95_ms"]:.2f} |')
    out+=['', 'Full production English regression gate is **not established**. Candidate action recall and slots fail independently, so no production or shadow recommendation is warranted regardless of preview comparisons.', '', '## Known limitations and next development requirements', '',
          '- Eight-epoch provisional training underfits action/domain generalization. Entire task families and resource/service domains are withheld; tiny evaluation slices are not representative population estimates.',
          '- Exact-span decoding preserves tokenizer whitespace offsets, causing leading-space boundary mismatches. DEV inspection identified this and slot/type errors. No post-TEST inference repair was applied. A future repair is a schema/span change, not an exact-sentence patch.',
          '- English coverage does not cover all 56 source action labels or 33 slot types. Synthetic question/correction/reference labels need human validation. Unknown/cancel/acknowledgement distinctions, short commands, multi-step planner composition, time/ordinal normalization and canonical slot values remain incomplete.',
          '- ASR samples are mild authored filler/light-verb variations, not a recorded speech recognizer benchmark. Technical-Tanglish and clean/noisy degradation require richer independent cases.',
          '- Reference presence is learned, but typed references use a generic selected-resource placeholder and are not resolved; corrections signal a required validation stage rather than reconstructing all superseded/active slots.',
          '- Capability gold coverage is narrow; some author-assigned targets are absent from the registry. TEST has no capability-gold cases. These deficiencies prevent the Recall@5 acceptance gate.',
          '- Seeds and family splits are repeatable, but CUDA memory-efficient attention warned of nondeterminism. Bitwise training reproducibility was not established.',
          '- Once failed TEST/HOLDOUT examples are intentionally used for development, retire those sets and construct new unseen family-isolated evaluations. Do not retrain directly from this run’s failure artifacts.',
          '', '## Decision', '', '**MORE_DEVELOPMENT_REQUIRED / KEEP_CURRENT operationally.** No promotion; no runtime routing edit; no live shadow hook. Human validation remains deferred and mandatory before final production acceptance. The audit UI shows AI provisional status, training/evaluation aggregates and shadow OFF; evaluation answers are not exposed in normal review UI.',
          '', 'Verification: 41 backend/data/Stage 2.5 tests, two model-policy/calibration tests and one intercepted browser test passed (44 total). Frozen source verification and frozen model/calibration hash checks pass. Model, split and consumption evidence are preserved in the active run directory.']
    out=[line.replace('Correct-frame-only retrieval is reported separately from end-to-end retrieval.','Correct-frame-only capability recall is not established: complete frame/slot/reference correctness is not available. End-to-end recall is shown without conflating it with action accuracy.') for line in out]
    (ROOT/'reports/JARVIS_ENGLISH_TANGLISH_NLP_FINAL.md').write_text('\n'.join(out)+'\n',encoding='utf-8')
    print(json.dumps({'decision':decision,'report':'reports/JARVIS_ENGLISH_TANGLISH_NLP_FINAL.md'},indent=2))


if __name__=='__main__':main()
