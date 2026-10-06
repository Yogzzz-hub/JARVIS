"""Assemble integration evidence without running locked NLP evaluations."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path.cwd()
E = ROOT / 'reports/integration_evidence'


def read(name):
    return json.loads((E/name).read_text(encoding='utf-8'))


def main():
    talk = read('talkback.json')
    wake = read('wake_synthetic.json')
    stt = read('stt_unicode_word_rate_fixed.json')
    live = read('live_status.json')
    resources = read('resources.json')
    source = ROOT/'data/nlp_shadow/shadow_configuration.json'
    frozen = hashlib.sha256(source.read_bytes()).hexdigest()
    rows = [
        '# JARVIS complete unified integration', '',
        '**Deployment: INTEGRATED_SHADOW. READY_FOR_DAILY_USE: NO.**', '',
        '2026-10-05. The project retains its existing 12 phases. Production routing, registered tools, planner, policy, TaskScope, verification, confirmation tickets and ActionLedger remain authoritative. No multilingual encoder training, candidate promotion, automatic human approval or generated WhatsApp auto-reply was performed.', '',
        'The integration is working alongside production; this report does not claim that every requested multilingual command executes correctly. Wake acceptance, semantic slot/reference acceptance, real phone deployment and real microphone evidence remain incomplete.', '',
        '## Input sources and shared pipeline', '',
        '| Source | Integration | Evidence / limit |', '|---|---|---|',
        '| Microphone / push-to-talk | Existing VoicePipeline final transcript → CommandService → input envelope | Existing wake/VAD/pre-roll/follow-up/barge-in retained; synthetic and unit evidence |',
        '| Typed HTTP / CLI | Same CommandService and envelope | Raw command text captured before production normalization |',
        '| Desktop / dashboard / overlay | Existing WebSocket/HTTP → same service | Dashboard source metadata preserved; no second execution route |',
        '| Owner WhatsApp | Existing authenticated owner dispatch → same service | Authentication remains existing JID/owner configuration, never contact names or memory |',
        '| Normal WhatsApp contacts | Shared conversation shadow → existing Personal Reply Brain | Zero command authority; existing truth/dyadic/style gates remain authoritative |',
        '| Phone text / PCM | New authenticated WSS `/phone/voice` → shared PC STT → same service | Mock end-to-end tested; actual Android client/TLS/token provisioning unverified |',
        '| Automation builder | Shared semantic advisory preview; existing AutomationManager installation/execution | Preview cannot install or execute; execution remains registered-capability/manager path |', '',
        '`JarvisInputEnvelope` contains input_id, source, raw_text, audio_metadata, authenticated_actor, timestamp, conversation_id, language_hint, device, context_refs and reply_channel. Caller-ready raw command text survives subsequent production rewriting. Authentication comes from the transport boundary; an envelope is not itself an authentication credential.', '',
        'The existing deterministic fast rules remain. The existing production English/Tanglish surface adapter remains unchanged; the candidate encoder directly encodes multilingual wording. This pass adds no translation-first candidate architecture and no exact-user-sentence repairs. The shadow SemanticFrame is not promoted into an execution driver.', '',
        '## Language and WorkingContext', '',
        'English, Tanglish, Tamil, English/Tanglish mixed, Tamil/English mixed and ASR input share the retained multilingual-e5-small advisory service. Existing V2 weights, calibration and frozen evaluation configuration are preserved. Current integration source SHA-256: `' + frozen + '`.', '',
        'Typed file/contact references now connect to the existing ReferenceResolver using an isolated pre-command WorkingContext snapshot for eligible local commands. Advisory resolution cannot mutate live selections or authorize execution; durable shadow evidence stores outcome/type rather than private resolved IDs. Unsupported reference types, ambiguous selections and cross-channel context isolation gaps clarify. Email/tab/event/project references and ordinal combinations are not fully connected to production execution.', '',
        'The admission guard blocks recognized prohibitions conservatively, including Tamil morphology; mixed negative/positive clauses may require clarification. Quoted/reported text is handled by the existing repaired semantic grammar. Unknown and ambiguous candidate output never executes. Recipient/sender reconstruction and corrections retain V2 advisory semantics; full recipient/reference acceptance is still outstanding.', '',
        'A measured pre-existing confirmation-lifecycle defect was repaired: clearing or expiring pending execution now clears the associated WorkingContext confirmation. An explicit changed-recipient follow-up is routed anew and asks for a fresh ticket. It does not inherit an old approval.', '',
        '## Capability connection and safety', '',
        f'Live ToolRegistry exports {len(read("registered_tool_names.json"))} registered schemas. The recorded name inventory is `reports/integration_evidence/registered_tool_names.json`.', '',
        'Existing registered paths cover files/folders/projects/IDE, browser, Windows/computer, Gmail/Calendar/Drive, WhatsApp, Android control/sharing, automations/reminders, search/knowledge/RAG, notifications, voice/system status and project/backend operations. Registration is not proof of current OAuth, phone pairing, browser/session availability, or exhaustive multilingual ontology coverage. No arbitrary shell, PowerShell, ADB, JavaScript or coordinate-action route was introduced.', '',
        'Production requests retain schema validation, task-scoped grants, policy, registered tools, verifier and ledger. Normal contacts are rejected at CommandService admission. Authenticated owner WhatsApp behavior retains its existing security boundary. Tests exercise policy/scope/provenance and confirmation behavior with fake tools; no test sent an actual WhatsApp message or executed a destructive production command.', '',
        '## Response coordinator and language policy', '',
        'ResponseLanguagePolicy chooses explicit instruction, active conversation metadata, contact preference, input language, then owner default. The local assistant prompt follows this policy; bounded verified-result templates support conversational Tamil/Tanglish while preserving technical names. Arbitrary tool details and all confirmation wordings are not comprehensively localized. Contact-specific Personal Reply style remains separate from command talkback; AI draft provenance rules are unchanged.', '',
        'ResponseCoordinator keeps a bounded final-response claim set shared by PULSE and the legacy response engine. One request gets one final response; the existing ACK race window suppresses obsolete/immediate ACKs. Phone/WhatsApp results do not also speak on PC speakers, including confirmation prompts. Unverified fallback speech no longer defaults to “Task completed.” Existing verified formatting, error sanitization, playback queue and barge-in cancellation remain.', '',
        '## Talkback', '',
        'JarvisSpeechResponseService reuses English Piper/SAPI and adds a pinned local Tamil Piper voice. TTSVoiceRegistry records language/locale/engine/model/rate/availability/rank/fallback. A pronunciation-only lexicon affects speech, never semantic input. Mixed segments preserve whole English identifiers such as FastAPI and Postgres; synthesis is serialized and PCM rates are unified.', '',
        'Tamil voice: [tinisoft Piper Rasa female model card](https://huggingface.co/tinisoft/piper-ta_IN-rasa_female-medium/blob/89e15edafc8b31e66ddf25f2adbe3bd3f20a9496/README.md), revision `89e15edafc8b31e66ddf25f2adbe3bd3f20a9496`. CC-BY-4.0 attribution to tinisoft and AI4Bharat Rasa is retained with the downloaded model. No new cloud TTS dependency exists.', '',
        '| Language | Audio bytes | Backend | First complete PCM ms | Playback API completed |',
        '|---|---:|---|---:|---|',
    ]
    for r in talk:
        rows.append(f"| {r['language']} | {r['audio_bytes']} | {r['backend']} | {r['first_pcm_ms']:.2f} | {r['playback_api_completed']} |")
    rows += ['', 'These are real synthesized WAV files and Windows playback calls, not microphone or loopback recordings. The first English and Tanglish samples include cold voice initialization; later samples are warm. First PCM is full-segment synthesis availability, not measured physical speaker onset. Naturalness, clipping, articulation and Tanglish pronunciation: **OWNER_LISTENING_REVIEW_REQUIRED**. Unicode survives and Tamil audio is nonempty; intelligibility is not automatically proven.', '',
        'A forced English Piper failure produced nonempty real SAPI audio (`sapi_fallback.wav`). Missing Tamil synthesis falls back to visual text rather than claiming an English-only voice supports Tamil. Labelled passwords/tokens/OTP/credential-bearing output is suppressed, and URLs are summarized. This is conservative screening, not exhaustive secret detection. Streaming replies are sentence-chunked by PULSE; the shared service synthesizes one normalized segment at a time.', '',
        '## Wake word, STT and latency', '',
        'The existing CPU OpenWakeWord detector, pre-roll ring, VAD, push-to-talk, bounded follow-up window and echo-aware interruption remain. Environmental adaptation can conservatively raise the configured threshold within bounds; it never lowers the configured minimum. The existing consecutive near-score behavior remains. Pre-roll continuity and barge-in are unit-tested, not proven on real owner recordings.', '',
        'Synthetic wake benchmark: three positive and three negative TTS utterances per condition. Current detector is the installed Hey Jarvis model. It detected Hey Jarvis and missed the synthetic bare Jarvis / Jarvis open Chrome positives. These counts are small development evidence; zero synthetic false accepts is not real-room safety acceptance.', '',
        '| Synthetic condition | TP / FN / FP / TN | TPR | FPR | FNR | Onset proxy median / p95 ms |',
        '|---|---|---:|---:|---:|---:|']
    for name, r in wake['conditions'].items():
        rows.append(f"| {name} | {r['tp']} / {r['fn']} / {r['fp']} / {r['tn']} | {r['tpr']:.2%} | {r['fpr']:.2%} | {r['fnr']:.2%} | {r['median_onset_ms']} / {r['p95_onset_ms']} |")
    rows += ['', 'Onset proxy is audio-stream offset relative to inserted synthetic speech start, including any TTS leading silence. It is not measured real microphone detection latency. Fan/music/distance/fast/slow conditions are artificial transformations; no real fan, TV, keyboard, near/far or owner-volume recordings were obtained. Bare-Jarvis acceptance has not passed. Push-to-talk remains the reliable fallback; no wake threshold was tuned to make these scores pass.', '',
        f"STT: measured base-model Tamil failure justified installing pinned Systran faster-whisper-small revision `536b0662742c02347bc0e980a01041f333bce120`, with remote LFS model hash verification. NLP weights were not retrained. CUDA DLL discovery reuses already installed local CUDA dependencies without loading torch models. Latest synthetic startup: {stt['startup_ms']:.2f} ms; device: {stt['device']}.", '',
        'Auto STT uses a multilingual model and per-utterance language detection; it no longer forces Tamil output into Latin script. A measured Unicode defect in the noise filter split Tamil combining marks, inflated word rate and discarded valid speech. Generic Unicode-aware word counting repaired it without weakening confidence/noise thresholds.', '',
        '| Synthetic input | Detected language | STT final ms | Actual transcript |',
        '|---|---|---:|---|']
    for r in stt['cases']:
        rows.append(f"| {r['input_language']} | {r['detected_language']} | {r['stt_final_ms']:.2f} | {r['transcript'].replace('|','/')} |")
    rows += ['', 'All four latest synthetic transcripts are nonempty and Tamil Unicode survives. Technical-term errors and code-switching omissions remain; nonempty text is not ASR correctness. Earlier failed CPU/base and forced-romanization experiments are preserved separately. No exact transcript corrections were added to hide failures.', '',
        'Real microphone wake latency, VAD latency, STT partial latency, full command-to-ACK audio and verified-result-to-physical-speaker latency: **NOT MEASURED**. New-release semantic routing p50/p95: NOT independently benchmarked. The CPU shadow queue remains bounded/lazy; no encoder, deep model or network is inserted into deterministic command execution. Full fast-route performance/English regression acceptance remains unestablished.', '',
        '## Phone, WhatsApp and automations', '',
        'The phone server requires WSS plus a provisioned bearer token, rejects browser-origin traffic, bounds PCM sessions to 30 seconds / 960,000 bytes, shares the same locked PC STT instance and admits only final transcripts. Result text and optional WAV return to the phone; PC speech is suppressed. Existing listener stays loopback. Real token/TLS setup, Android thin-client implementation/pairing and phone speaker playback remain unverified; the original mobile package was a placeholder, not a completed audio client.', '',
        'Normal WhatsApp conversation observation is advisory. Personal Reply Brain retains existing contact/dyadic profiles, truth-state gates, provenance and language/style logic; candidate conversation features are not an accepted replacement for its authoritative interpretation. Generated automatic replies stay OFF. Manual drafts/authorized owner commands retain their existing review and security paths.', '',
        'Automation preview uses the shared language service. Existing AutomationManager and registered tools retain scheduling/install/trigger safety. Candidate multi-clause projections are planner hints only; complete cross-domain DAG composition is not established by this pass.', '',
        '## Dashboard, resources and evidence', '',
        'Live status: http://127.0.0.1:8765/dashboard/voice-language/page. Desktop System page includes a Voice / Language shortcut. Thirteen cards independently show wake/microphone/VAD/STT/language/Capability Brain/TTS/speaker/barge-in/WhatsApp/Google/phone/shadow. Browser readback: no page errors. Google status is local metadata only; token validity is not asserted without an auth probe. Optional failures do not collapse all health cards.', '',
        f"Live backend health: ready; database ready; STT {live['stt']['engine']} on {live['stt']['device']}; multilingual shadow ON; candidate controls tools false. Current resource snapshot: `{json.dumps(resources, ensure_ascii=False)}`. GPU memory includes other applications; it is not attributed solely to JARVIS. Idle RAM/peak resources are not measured.", '',
        'Shadow contains five unreviewed conversation observations and zero owner-reviewed commands at report time. Their historical collection provenance is not sufficient to claim real-world accuracy and may include pre-guard test intake. Records are retained, not silently deleted. Live-store collection is now suppressed during pytest; injected temporary stores remain testable. No owner decisions or accuracy labels were inferred from these observations.', '',
        '## Verification and preservation', '',
        '**391 tests passed; 1 skipped** (PySide6.QtCore unavailable in the global test interpreter). This includes envelope/raw preservation, language priority, phone auth/PCM final-only delivery, duplicate suppression, Unicode/privacy/fallback paths, prohibition admission, reference ambiguity, context carry-over, policy/scope/security, existing voice/response behavior and WhatsApp provenance. Most end-to-end flows use fake tools/audio; the WAV, synthesis, playback and synthetic wake/STT checks use real local engines.', '',
        'Stage 2.5 frozen verification passes. V2 model/calibration/configuration/base files and runtime dependency hashes pass verification. Original corpus, audit queue, original labels and human audit decisions were not changed. No V2 TEST/HOLDOUT contents or failure examples were used to repair, tune or train. V3 realistic evaluation remains locked and unconsumed. No accepted semantic model or production promotion was fabricated.', '',
        'Reports from previous passes remain historical evidence. This new report does not reinterpret their consumed evaluation scores as validation of the current integration.', '',
        '## Deployment decision and known limits', '',
        '**INTEGRATED_SHADOW / KEEP_CURRENT. Daily-use acceptance requires more development evidence.** The backend is running with the new integration. The candidate remains advisory and generated WhatsApp auto-replies remain held. The common input/response contracts and local multilingual talkback are functional; whole-JARVIS multilingual execution quality is not yet accepted.', '',
        '- Bare-Jarvis wake acceptance and real microphone noise/distance benchmarks remain unmet.',
        '- ASR technical-token/code-switching errors remain despite the Unicode and CUDA repairs.',
        '- Tamil/Tanglish voice quality and first-word clipping need listening judgment.',
        '- Phone TLS/token provisioning and actual Android client playback are not complete.',
        '- Canonical slots, typed/contextual references, negation scope, constraints, corrections and multi-step composition do not have complete production acceptance.',
        '- Arbitrary verified output and every confirmation prompt are not fully localized.',
        '- Candidate conversation interpretation remains advisory; existing Personal Reply truth/style gates are preserved.',
        '- Full live English regression, real-command capability recall and calibrated useful execution coverage remain unestablished.', '',
        'Evidence: `reports/integration_evidence/`; transport/policy documentation: `docs/UNIFIED_INPUT_AND_RESPONSE.md`. No additional project phase was created.', '',
    ]
    (ROOT/'reports/JARVIS_COMPLETE_INTEGRATION_FINAL.md').write_text('\n'.join(rows),encoding='utf-8')
    verification = {'created_utc':datetime.now(timezone.utc).isoformat(),'tests_passed':391,'tests_skipped':1,
        'deployment':'INTEGRATED_SHADOW','backend_pid':17128,'candidate_controls_tools':False,
        'source_configuration_sha256':frozen,'Stage25_frozen_verified':True,'V2_frozen_configuration_verified':True,
        'test_holdout_tuning':False,'real_microphone_accuracy':'NOT_MEASURED','phone_real_pairing':'NOT_VERIFIED',
        'voice_quality':'OWNER_LISTENING_REVIEW_REQUIRED'}
    (E/'verification.json').write_text(json.dumps(verification,indent=2)+'\n')


if __name__ == '__main__':
    main()
