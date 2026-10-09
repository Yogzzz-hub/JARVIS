"""Aggregate-only multilingual checkpoint; never consume evaluation answers."""
import json
from pathlib import Path
from jarvis.core.language_shadow import ShadowStore


def pct(x):return 'N/A' if x is None else f'{100*x:.2f}%'


def main():
    dev=json.loads(Path('data/nlp_shadow/development/decoder_DEV.json').read_text(encoding='utf-8'))
    state=ShadowStore().state()
    frozen=json.loads(Path('data/nlp_shadow/shadow_configuration.json').read_text())
    evidence=Path('data/nlp_shadow/worker_smoke.json')
    smoke=json.loads(evidence.read_text()) if evidence.exists() else {}
    verification=json.loads(Path('data/nlp_shadow/verification.json').read_text())
    activation=json.loads(Path('data/nlp_shadow/activation.json').read_text())
    after=dev['after'];before=dev['before'];neg=dev['negation_after']
    lines=['# JARVIS multilingual language layer — shadow checkpoint',
      '', '**Deployment: SHADOW_READY / KEEP_CURRENT. Candidate execution authority: OFF.**',
      '', '2026-10-05. English, Tanglish, Tamil, mixed English/Tanglish, mixed Tamil/English and ASR text enter one advisory JarvisLanguageUnderstandingService. Production routing/planning/policy still decide and execute. No encoder retraining or production classifier replacement occurred.',
      '', 'The V2 model and its original frozen configuration are preserved. The new decoder and shadow integration have a separate source-hashed configuration. Historical V2 TEST/HOLDOUT measurements do not validate this decoder; those consumed sets were not reopened, rerun or used for tuning.',
      '', 'Human audit remains DEFERRED: 10 owner REJECT decisions, 0 APPROVE/FIX_LABEL. Shadow choices are a separate review history and never become audit approvals, training labels or admission automatically.',
      '', '## Inputs and semantics',
      '', '| Input | Integration |', '|---|---|',
      '| Typed chat / HTTP / CLI | CommandService captures raw input before existing normalization; actual production decision is queued afterward |',
      '| Voice/STT | Same CommandService observer; final STT raw text, no separate voice encoder |',
      '| Dashboard | Existing command bridge supplies a dashboard source tag |',
      '| Authenticated owner WhatsApp | Existing gateway verifies owner; same command observer |',
      '| Phone client | Existing gateway command path; phone source tag supported |',
      '| Automation builder | Advisory /dashboard/nlp/understand endpoint and automation trigger/condition projection |',
      '| Normal direct-contact WhatsApp | Conversation-only shadow features; history, groups, owner messages and undecrypted placeholders excluded |',
      '', 'All candidate modes use the same retained V2 encoder and native SemanticFrame adapter. Raw text, original-codepoint spans, typed canonical values, contact roles, resource identifiers, temporal values, quantities, constraints, negations, corrections and unresolved references remain available. New semantic fields use the existing frame language_features contract; the production frame class was not redesigned.',
      '', 'No translation-first candidate path exists. Existing production normalization remains authoritative during this transition. Technical tokens and names are not rewritten. Deterministic routes do not wait for inference. A bounded queue (32 pending cases) feeds a separate CPU worker with one Torch thread and zero candidate tool or network calls.',
      '', 'Covered ontology retains V2’s 62 action heads and existing capability contracts. WhatsApp, Gmail, Calendar, Drive, Browser, Computer, Files, Projects/IDE, Automations, System, Phone, Voice, reminders, search, notifications and knowledge can enter the shared adapter; complete natural-language coverage for every registered tool is NOT established.',
      '', 'Sequential connectors produce advisory semantic steps; trigger/condition/schedule fields remain planner inputs. This pass does not install automations, execute a candidate DAG or validate all multistep dependencies. WorkingContext must resolve references; reference values stay null. Bare-hour ambiguity is retained rather than inventing afternoon times.',
      '', '## DEV-only repair measurements',
      '', 'These are provisional synthetic/AI-assisted labels, not real-world accuracy. Repair development reads only preserved DEV rows and predictions; capability retrieval is recomputed from repaired predicted frames. Negation scope lacks independent gold, so scope accuracy is N/A.',
      '', '| Metric | V2 DEV | Repaired DEV |', '|---|---:|---:|']
    for label,key in [('Domain','domain'),('Action','action'),('Recipient','recipient_accuracy'),('Source/sender','sender_accuracy'),('Time','time_accuracy'),('Ordinal','ordinal_accuracy'),('Correction reconstruction','correction_reconstruction'),('Reference type, legacy gold taxonomy','reference_type_accuracy'),('Speech act','speech_act'),('Unknown/clarify','unknown_clarify')]:
        lines.append(f'| {label} | {pct(before[key])} | {pct(after[key])} |')
    lines += [f"| Canonical slot precision | {pct(before['canonical_slots']['precision'])} | {pct(after['canonical_slots']['precision'])} |",
              f"| Canonical slot recall | {pct(before['canonical_slots']['recall'])} | {pct(after['canonical_slots']['recall'])} |",
              f"| Canonical slot F1 | {pct(before['canonical_slots']['f1'])} | {pct(after['canonical_slots']['f1'])} |",
              '', f"Negation P/R/F1: {pct(neg['precision'])} / {pct(neg['recall'])} / {pct(neg['f1'])}; TP {neg['tp']}, FP {neg['fp']}, FN {neg['fn']}. Prior DEV P/R/F1: {pct(dev['negation_before']['precision'])} / {pct(dev['negation_before']['recall'])} / {pct(dev['negation_before']['f1'])}.",
              '', 'Repairs use role markers, canonical identifier/numeric/ordinal evidence, correction reconstruction, quote/URL masking and contextual negative morphology. Light verbs do not select an action; the retained encoder does. Quoted content, reported history, questions, hypotheses and domain exclusions are distinguished conservatively. These grammars still need real-language validation.',
              '', 'Typed references include file/message/email/contact/tab/Drive/event/project and ordinal references. Specific new types differ from V2’s generic reference gold; legacy exact-type accuracy falls. This is an acceptance blocker, not a claimed improvement. Full typed reference resolution, complete constraint gold and all 33 slot types remain incompletely covered.',
              '', '| DEV language | N | Action | Canonical slot F1 | Reference | Speech act |', '|---|---:|---:|---:|---:|---:|']
    for lang,m in dev['languages'].items():
        lines.append(f"| {lang} | {m['n']} | {pct(m['action'])} | {pct(m['canonical_slots']['f1'])} | {pct(m['reference_type_accuracy'])} | {pct(m['speech_act'])} |")
    cap=after['capability']
    lines += ['', f"Repaired DEV Capability R@1/@3/@5/@10 ({cap['cases']} atomic gold cases): "+' / '.join(pct(cap['recall_at_'+str(k)]) for k in (1,3,5,10))+'. Retrieval remains an offline metadata overlay, not proof of live tool availability or complete registry coverage.',
      '', '## WhatsApp and response language',
      '', 'Normal contact content never enters the command observer with owner authority. Conversation shadow stores only relevant meaning features: language, speech act, question type, personal-state requirement, typed references and conversation mode. Full incoming text, contact identity and resolved resource IDs are omitted from durable conversation records.',
      '', 'Personal Reply Brain retains recent conversation, owner/contact style, dyadic profile and truth/state gates. Candidate conversation meaning is advisory and recorded separately; it does not replace production reply-needed or truth classification. The WhatsApp dashboard identifies Unified JARVIS NLP as the shadow source. Generated auto-replies are held while WHATSAPP_GENERATED_REPLY_SHADOW and MULTILINGUAL_NLP_SHADOW are enabled; owner grants are not deleted. Manual reply/draft paths retain existing authorization.',
      '', 'A response-language policy supports explicit preference, contact preference and current language. Candidate-driven multilingual response rendering is not activated. Existing production and personal renderers remain in place; complete Tamil/mixed rendering quality is unvalidated. No friend-written command can authorize a tool or generated reply through this service.',
      '', '## Shadow collection and owner review',
      '', f"MULTILINGUAL_NLP_SHADOW = true is configured separately from the frozen V2 evaluation configuration. Backend reload verified: {activation['backend_reloaded']}; live gateway shadow endpoint verified: {activation['gateway_shadow_endpoint_verified']}; backend health: {activation['health_status']}. The worker loads lazily on the first eligible input. Source comparisons use actual recorded route intent/slots and available trace fields, never expected labels. Missing production fields remain N/A. Contract-equivalent actions are compared without a gold-aware FIND/SEARCH conversion.",
      '', 'NLP Intelligence → Shadow Disagreements shows original owner input, production output, candidate SemanticFrame and field agreements. Owner choices: PRODUCTION_CORRECT, CANDIDATE_CORRECT, BOTH_CORRECT, BOTH_WRONG, UNSURE. Host checks and a per-process write token protect saves. Decisions are append-only/resumable and latest decisions drive counts. Browser tests intercept every review request.',
      '', f"Real command cases: {state['counts'].get('command',0)}. Conversation cases: {state['counts'].get('conversation',0)}. Automation-builder cases: {state['counts'].get('automation_builder',0)}. Owner reviewed: {state['owner_reviewed']}.",
      '', f"Owner comparative counts: {json.dumps(state['review_counts'],sort_keys=True)}.",
      '', f"Agreement: {json.dumps(state['agreement'],sort_keys=True)}. Agreement is not accuracy. Disagreement-selected reviews are not a representative population benchmark.",
      '', 'Real-world action/domain/slot/recipient/sender/time/ordinal/reference/correction/negation/speech accuracy and Capability Recall@K: NOT MEASURED. No actual owner usage is fabricated from smoke tests. Owner comparison choices alone do not supply complete slot or capability gold. Enough reviewed real evidence and independent labels are still required before reporting those metrics.',
      '', 'Candidate EXECUTE precision: N/A. Candidate EXECUTE coverage: 0%. Candidate tool/auto-reply authority is always false. The original DEV execute threshold remains disabled; repairs do not establish complete safe frame correctness. This is a temporary acceptance failure, not 100% precision. Future calibration must use DEV/eligible reviewed development evidence, never evaluation rows.',
      '', '## Evaluation isolation, latency and resources',
      '', 'V3_REALISTIC_TEST has 32 newly authored realistic-style cases / 32 declared constructions across English, Tanglish, Tamil, mixed technical language and ASR, including short/long requests, corrections, negation, references and composition. It is sealed and UNCONSUMED. Labels are AI-authored and partial, not human-validated; semantic-family distance is not independently verified. It cannot alone establish final acceptance. No V2 evaluation sentence/failure was deliberately imported.',
      '', 'Locked V3 manifest: data/nlp_shadow/evaluation/manifest_ontology_r1.json; dataset V3_REALISTIC_TEST_ONTOLOGY_R1.jsonl. Dataset preflight found the unsupported action REMIND in the initial AI seed. That seed is preserved and excluded; the new version uses shared CREATE plus a typed reminder resource. This is annotation-schema repair before any evaluation, not model tuning. No V3 prediction was generated. Historical consumed V2 evaluations remain evidence only for their original frozen decoder and cannot validate this pass.',
      '', f"Isolated CPU worker smoke evidence: {json.dumps(smoke,sort_keys=True)}. Smoke inputs are development probes, not real shadow cases or acceptance data. Startup is reported separately; the small sample does not establish representative p95 latency.",
      '', 'Real-shadow p50/p95 latency: '+json.dumps(state['latency'],sort_keys=True)+'. Worker records elapsed inference/repair/retrieval/comparison time and process RAM. It allocates zero VRAM. Cold model loading runs outside the production task. Whole-machine idle RAM, CPU impact under sustained traffic, all-source latency and English live regression remain unmeasured.',
      '', '## Verification and deployment decision',
      '', f"{verification['tests_passed']} tests passed; {verification['tests_skipped']} Qt dashboard module skipped because PySide6 is absent from that test interpreter. Tests cover raw preservation, sender/recipient correction, Unicode negation, typed unresolved references, status queries, composition, secret omission, bounded source/owner eligibility, persistence, owner-review history, browser writes/XSS and unchanged command results. Existing personal-reply/provenance/audit tests pass with the shadow switch initially OFF; the explicit ON auto-reply hold is tested separately.",
      '', 'Frozen corpus/queue/manifests, human audit history, V2 model/calibration/configuration and production router/registry/retrieval remain unchanged. Shared observer hooks and source tags were added; candidate predictions never replace production decisions. Owner shadow decisions are stored only in data/nlp_shadow/shadow.sqlite3.',
      '', f"Shadow configuration version: {frozen['version']}. V2 configuration hash: {frozen['v2_configuration_sha256']}.",
      '', '**KEEP_CURRENT + SHADOW_READY. No production promotion.** Canonical slot F1 and reference quality remain below targets; real-world evidence, full regression, complete safety/constraint/WorkingContext coverage and useful calibrated execution coverage are outstanding. Model retraining is not justified solely by more epochs and was not performed.',
      '', 'One-step shadow rollback: set MULTILINGUAL_NLP_SHADOW=false atomically in jarvis/config/nlp_candidate.json. Pending candidate inference may finish, but it cannot execute. Generated-auto-reply hold follows the shadow switch; original owner policy remains responsible for any resumed replies. No working model is overwritten.', '']
    Path('reports/JARVIS_MULTILINGUAL_LANGUAGE_LAYER_FINAL.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':main()
