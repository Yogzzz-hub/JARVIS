# JARVIS complete unified integration

## Screenshot follow-up — ordinal action authority, 2026-10-06

The owner's “what isn the last msg in appa” incorrectly opened a previously referenced Markdown file. The recorded trace shows LANE_0/open_file at confidence 1.0. An isolated reproduction with an active fixture file reproduces that same open_file decision when the old ordinal gate is allowed, and no open decision under the new gate. No files were opened during this reproduction.

The existing contextual ordinal shortcut inferred OPEN from the word “last,” before the later question guard ran. It now requires an explicit open/view command or a terse result selection. Questions, send/delete requests and other ordinal-bearing sentences cannot acquire an OPEN action from that shortcut. General interrogative prefixes also retain their informational speech act, including a misspelled copula. Registered read-only query exceptions remain available. This is a targeted production-router safety guard repair; it changes no candidate model, routing architecture or user-phrase dictionary. No “appa” → WhatsApp alias was added: that wording can also denote a person, so the assistant must not invent its target.

An additional action-history prefix was capturing scoped inbox questions such as asking for the last message in WhatsApp. Inbox scope/received-message evidence now excludes that shortcut unless the question explicitly concerns a sent/replied assistant or owner action. Questions about messages JARVIS sent continue using the existing action record.

Focused coverage includes the reported typo, ordinal-bearing message/email questions with active file context, preserved brief selections and explicit opening commands, context carryover, multilingual routing and policy checks: **144 passed** in `ordinal_final_verified.log`. Isolated scope guard checks: **34 passed**. A combined order-sensitive run recorded two scope failures (OTP-read refusal and pause routing), despite those tests passing in isolation; its evidence is retained in `ordinal_final_regression.log`. These results do not erase the older regression limitations below.

Action-history/follow-up checks separately passed **40 tests** in `ordinal_history_regression.log`; counts overlap. Development source release: `68432a24fe56db4a9d153d73c1474b471b819c252a112ef89a0fe5ab622c5c5c`. The local backend was reloaded with the new guards. Stage 2.5 freeze remains valid. The sections below preserve the earlier talkback checkpoint and its measured results.

## TALKBACK_RELIABILITY_FIX — 2026-10-06

**Classification: TALKBACK_REPAIR_REQUIRED / BACKEND_STABLE (measured local probes).** The known delivery races, false queue timeout, identifier rendering and transport-health defects were repaired. Full talkback acceptance remains open: independent owner listening is absent, and a permanently blocked native synthesis/playback call cannot be forcibly terminated by the Python thread watchdog. This report does not claim a hard delivery guarantee or an all-green repository. READY_FOR_DAILY_USE remains NO.

Production remains authoritative in INTEGRATED_SHADOW. Candidate execution and generated WhatsApp auto-replies remain OFF. No router redesign, NLP retraining, translation-first path, exact-user-phrase repair, locked TEST/HOLDOUT read, outbound WhatsApp message or production model promotion occurred. Existing gender preferences, Personal Reply Brain, policy, registry, verification, confirmation and ledger decisions remain in force.

### Talkback delivery and measured counts

PULSE final delivery now delegates to the existing ResponseEngine/JarvisSpeechResponseService pair. An early coordinator claim no longer counts as successful speech. Streamed speech becomes spoken only after successful enqueue, and delivery becomes DELIVERED only after the audio worker actually starts and completes playback. Each chunk has its own response ID. Failed synthesis before any playback permits a later explicit retry; partially played output and cancelled jobs cannot automatically replay the whole answer. Stream errors remain FAILED even when earlier chunks played.

The latest-job diagnostics include request/response IDs, text generated, TTS requested, language, engine, queue entry, synthesis start/completion, playback start/completion, state, latency and failure/cancellation/suppression reasons. Muting/disabled TTS, explicit text-only, remote/background and phone-owned audio destinations are recorded separately. Sensitive text is suppressed. Male/female voice-change cancellation is marshalled onto the runtime event loop.

Speech-lock wait is bounded at 10 seconds, individual synthesis chunks at 15 seconds and the final job at 120 seconds. Queue initialization allows the known duration of audio ahead plus a bounded startup margin. This matters: the first concurrent live probe exposed a false 10-second timeout while a valid summary was already playing. That evidence is retained in `talkback_reliability_evidence/live_backend_before_queue_budget.json`; it was not erased or counted as success. The new backlog-aware watchdog passed both a focused queued-audio test and the subsequent live pair. Playback timeout cancels the affected request, rather than restarting JARVIS. Native thread recovery after a permanently hung OS/model call remains a limitation; asynchronous cancellation cannot kill that native thread safely.

| Evidence window | Text generated | TTS requested | Delivered | Failures | Suppressions | Duplicate suppressions |
|---|---:|---:|---:|---:|---:|---:|
| Synthetic fixtures, actual local speaker playback | 6 | 6 | 4 | 1 | 1 | 1 |
| Final concurrent live WhatsApp probes, completion checked | 2 | 2 | 2 | 0 | 0 | 0 |

The synthetic failure intentionally disables Tamil synthesis and records TTS_UNAVAILABLE_FOR_LANGUAGE; the suppression intentionally supplies credential-like text. A forced English Piper failure successfully used existing Windows SAPI and completed real playback. Hardware error count was 0. The duplicate fixture was suppressed without replay. These are test injections, not six real owner commands or independent listening ratings. Counters cover bounded process-local history, not lifetime reliability.

Evidence: `talkback_reliability_evidence/physical_delivery.json`, `live_backend.json` and `live_delivery_trace.json`. They preserve playback state/timestamps and identifiers for diagnostics; live message bodies are not exported into these probe artifacts.

### WhatsApp response quality

Verified inbox results now produce distinct visual and spoken views from the same data, without a second LLM call. Visual summaries have a headline, counts, bounded important-chat previews and a next-action line. Speech is shorter and normally at most 55 words. An incomplete-sync caveat appears once. Group unread-message counts are described as messages, rather than inventing a count of groups. The main UI shows the first three lines; the existing conversation panel retains the full response.

Rendering resolves saved contact identities through the existing resolver before display names, aliases and conversation labels. Unresolved numeric/JID/hash identifiers become “one contact.” Identifier masking applies to normal WhatsApp final responses and fallback formatting. Credential-like previews are withheld, long previews are shortened and local times use HH:MM without unnecessary “India Standard Time.” English, Tanglish, Tamil and mixed-language rendering tests preserve these safeguards. Explicit technical/debug requests retain the existing diagnostic exception. Pattern-based credential detection is not an exhaustive secret detector.

The current production router still sends the tested latest-message question to `ollama_chat`. A bounded, read-only chronological incoming-direct-message snapshot now grounds that chat answer; it does not invoke a tool or replace the route. Its query orders by timestamp rather than Personal Reply Brain reply priority. Partial WhatsApp LLM output is withheld until the sanitized final is ready, avoiding identifiers split across streaming tokens. The snapshot describes locally available direct messages and warns that remote completeness is not guaranteed. Group-specific latest queries and full factual acceptance across every scope remain unvalidated. Existing tool verification of an LLM completion is not independent proof of message accuracy.

Final live scenarios:

| Scenario | Result | Raw identifier leak | Spoken words | Visual lines |
|---|---|---|---:|---:|
| “summarize my whatsapp” | PARTIAL_SUCCESS; verified local summary, sync caveat retained | NO | 36 | 8 |
| “what is the latest msg i got in whatsapp” | SUCCESS; existing chat route with local snapshot | NO | 16 | 1 |

Both final speech jobs completed playback. Fixtures separately check exact contact-resolution priority, unknown contacts, sensitive previews, short local times, incomplete sync and all four response language modes. Actual latest-message wording is model-dependent; no exact sentence was patched.

### Backend, heartbeat and reconnect

Confirmed defects included ping timing measured at send rather than matching pong receipt, immediate OFFLINE display on socket loss and blocking SQLite audit work on the event loop. A captured regression stack shows the event-loop thread inside AuditLogger SQLite logging. An earlier live backend stack was idle in the asyncio poller, so it does not establish that a backend crash caused every historical disconnect. No single historical root cause is asserted beyond the defects directly observed.

Executor audit/stat/outcome writes now run off the event loop. Ledger admission remains one ordered, locked worker operation: duplicate check, PREPARED, TOCTOU and STARTED retain their existing decisions before execution. No security checks, SQL failure behavior or ledger invariants were weakened. Read-only Personal Reply status no longer initializes/resumes background brain jobs, and contacts/status database work uses thread boundaries.

The desktop bridge tracks socket state, ping/pong/event times, backend health, reconnect attempts and reason. It uses ONLINE/DEGRADED/RECONNECTING/OFFLINE, a 10-second unavailable-health grace and jittered 250/500/1000/2000/5000-ms reconnect delays. Matching pong receipt determines latency. Reconnect restores subscriptions/status and queries existing pending task snapshots without resending commands. Request ID plus outcome version/state prevents duplicate finals while permitting legitimate later outcomes. Existing visible conversation survives transport changes. Diagnostics expose the connection evidence; optional integration health does not determine core ONLINE status.

The Qt test uses a real local WebSocket server that drops the connection after one second: RECONNECTING → ONLINE occurs automatically, with no OFFLINE transition. Separate tests preserve visible conversation and verify correlated pong timing. Gateway socket teardown now finishes subscription/task cleanup under cancellation.

| Probe | Samples | Heartbeat p50 ms | p95 ms | Max ms | Final core health |
|---|---:|---:|---:|---:|---|
| Concurrent live WhatsApp summary/latest and TTS | 50 | 1.29 | 3.52 | 332.82 | ready |
| Synthetic CPU STT load plus actual advisory NLP submissions | 80 | 1.47 | 2.96 | 16.97 | ready |

The inference probe loaded the local small Whisper model on CPU and completed three eight-second synthetic-audio transcriptions in 8.88 seconds including loading. They returned no recognized segments; this measures compute isolation, not STT accuracy. Eight real advisory NLP submissions completed in the backend's existing process-isolated worker: completed counter 23 → 31, worker errors unchanged at 4. No tools ran. This tests local CPU load concurrent with the gateway and actual backend NLP work, not a recorded owner microphone session or the GPU production STT profile. Evidence: `talkback_reliability_evidence/inference_stress.json`.

Gateway health/pong tests pass with optional WhatsApp/model services absent. Actual live probes remained ready while the WhatsApp bridge reported disconnected. Injected unavailable Tamil TTS stayed local to its speech job in the standalone playback fixture; unavailable TTS/optional-worker objects do not prevent test gateway heartbeats. A live kill/restart of every integration was not performed. BACKEND_STABLE applies to these bounded observations, not an indefinite uptime guarantee.

### Verification and remaining acceptance

Final complete relevant regression: **489 passed, 1 skipped** in `talkback_complete_final_regression.log`, covering integration, voice, scope/policy, context, WhatsApp provenance, read-only inbox and phone/web behavior. Core/security checks additionally report **358 passed, 1 skipped** in `talkback_final_core_regression.log`. Latest queue/stream/backend focused verification: **65 passed** in `talkback_queue_watchdog_checks.log`. Production-environment Qt/UI/voice tests: **76 passed, 1 skipped**, with the skip for a singleton lacking qmldir. Counts overlap and must not be added.

The expanded run in `talkback_release_regression.log` reports **398 passed, 16 failed, 3 skipped**. All 16 failures are in `test_whatsapp_personal_reply.py`, including autonomous-send expectations and a drafting timeout; they are unresolved and were not repaired by enabling generated auto-replies. Earlier broader historical failures remain recorded below. This pass does not establish full Personal Reply Brain regression acceptance. Compilation and whitespace checks pass. Stage 2.5 frozen verification reports `frozen: true`, `errors: []`; original model/evaluation artifacts and owner audit decisions remain untouched.

Development source release SHA-256: `007566ecf425d2720bc114bf6e5b028e35749df057aae5c104c3bee150a7f4f8`; prior configuration bytes are archived separately. This refresh authorizes development source drift only; it is not a candidate deployment or changed evaluation manifest. The local backend serves the updated code at port 8765.

**Remaining:** independent owner listening/microphone acceptance, safe recovery from permanently blocked native audio/model calls, broad latest-message scope/factual checks and the unresolved Personal Reply Brain regression failures. Therefore TALKBACK_REPAIR_REQUIRED remains the conservative final talkback classification despite successful measured playback; BACKEND_STABLE is limited to the tested transport/load windows. No new daily-use acceptance claim is made.

2026-10-06 voice preference update: **male across English, Tamil and Tanglish by default**. The existing female/male switch now changes the entire English/Tamil pair, persists across restarts, stops old queued speech and refreshes acknowledgement clips. Eight actual local synthesis cases passed across both genders and four language modes; independent listening acceptance remains pending. Details are recorded in [voice acceptance report](JARVIS_VOICE_DAILY_USE_ACCEPTANCE.md). Development source release: `64b56624b447bb377617630827753ddf503c7fa37b4834f5562343da40e56f84`.

## 2026-10-06 voice daily-use acceptance update

**VOICE_OWNER_TEST_REQUIRED. INTEGRATED_SHADOW retained. READY_FOR_DAILY_USE: NO. Bare Jarvis: NOT_READY.** The installed wake model remains Hey Jarvis; no verified dedicated bare-Jarvis model exists. Optional hash-verified dual-model loading is implemented without lowering the threshold, but does not establish wake acceptance.

This pass adds 1500 ms preroll, microphone health/timing evidence, raw multilingual transcripts and uncertain-word clarification before local/phone routing, bounded metadata hints without fuzzy contact rewriting, voice warmup, immediate completed-sentence streaming without replay, and worker-local native Windows SAPI fallback. A shared-microphone 26-prompt local test isolates recordings from command execution and training. Four language listening previews accept CLEAR/OK/BAD ratings. Open http://127.0.0.1:8765/dashboard/voice-benchmark/page; the refreshed backend serves the voice-language page with HTTP 200.

Owner evidence remains **0 recordings and 0 ratings**. Real wake rates, physical clipping/barge-in/follow-up, STT semantic accuracy and real latency distributions are pending. Synthetic warm first-sentence PCM observations were 262–524 ms; these are not physical playback p50/p95. Cold synthesis remains several seconds. Dedicated bare activation and independent owner review remain required.

Final focused verification: **425 passed, 1 skipped**; final owner/safety module **34 passed**, overlapping that count. Structural ML checks separately **4 passed**. Broader regression: **3206 passed, 42 failed, 8 skipped, 15 legacy-holdout tests deselected**. Routing/scope, WhatsApp and talkback confirmation/ledger failures remain unresolved; this pass does not claim an all-green repository or daily acceptance. The SAPI COM hang was diagnosed and repaired; actual concurrent fallback PCM and common-service fallback were verified.

Stage 2.5 freeze and original V2 model/config verification pass. No NLP retraining, locked TEST/HOLDOUT consumption or production router/planner/policy/TaskScope/ToolRegistry/verification/ActionLedger source changes occurred in this voice pass. Updated development source release SHA-256: `a876b49d55d30dbe99b6848687c71063f22d9c89c115b13f2d1e2703bf25b15e`; previous release bytes are archived. Full evidence and limits: [JARVIS_VOICE_DAILY_USE_ACCEPTANCE.md](JARVIS_VOICE_DAILY_USE_ACCEPTANCE.md).

The voice naturalness module also passed all **16 tests** in the production virtual environment, including the Qt check skipped by global Python. Counts overlap the focused run. Final live status confirms production remains authoritative and no owner samples exist.

The following sections preserve the earlier integration checkpoint and its historical measurements.

**Deployment: INTEGRATED_SHADOW. READY_FOR_DAILY_USE: NO.**

2026-10-05. The project retains its existing 12 phases. Production routing, registered tools, planner, policy, TaskScope, verification, confirmation tickets and ActionLedger remain authoritative. No multilingual encoder training, candidate promotion, automatic human approval or generated WhatsApp auto-reply was performed.

The integration is working alongside production; this report does not claim that every requested multilingual command executes correctly. Wake acceptance, semantic slot/reference acceptance, real phone deployment and real microphone evidence remain incomplete.

## Input sources and shared pipeline

| Source | Integration | Evidence / limit |
|---|---|---|
| Microphone / push-to-talk | Existing VoicePipeline final transcript → CommandService → input envelope | Existing wake/VAD/pre-roll/follow-up/barge-in retained; synthetic and unit evidence |
| Typed HTTP / CLI | Same CommandService and envelope | Raw command text captured before production normalization |
| Desktop / dashboard / overlay | Existing WebSocket/HTTP → same service | Dashboard source metadata preserved; no second execution route |
| Owner WhatsApp | Existing authenticated owner dispatch → same service | Authentication remains existing JID/owner configuration, never contact names or memory |
| Normal WhatsApp contacts | Shared conversation shadow → existing Personal Reply Brain | Zero command authority; existing truth/dyadic/style gates remain authoritative |
| Phone text / PCM | New authenticated WSS `/phone/voice` → shared PC STT → same service | Mock end-to-end tested; actual Android client/TLS/token provisioning unverified |
| Automation builder | Shared semantic advisory preview; existing AutomationManager installation/execution | Preview cannot install or execute; execution remains registered-capability/manager path |

`JarvisInputEnvelope` contains input_id, source, raw_text, audio_metadata, authenticated_actor, timestamp, conversation_id, language_hint, device, context_refs and reply_channel. Caller-ready raw command text survives subsequent production rewriting. Authentication comes from the transport boundary; an envelope is not itself an authentication credential.

The existing deterministic fast rules remain. The existing production English/Tanglish surface adapter remains unchanged; the candidate encoder directly encodes multilingual wording. This pass adds no translation-first candidate architecture and no exact-user-sentence repairs. The shadow SemanticFrame is not promoted into an execution driver.

## Language and WorkingContext

English, Tanglish, Tamil, English/Tanglish mixed, Tamil/English mixed and ASR input share the retained multilingual-e5-small advisory service. Existing V2 weights, calibration and frozen evaluation configuration are preserved. Current integration source SHA-256: `b9655fbe9c748b630fb847fcfb4ce4551b4a079352c7fa7bfd753394ce27a6dc`.

Typed file/contact references now connect to the existing ReferenceResolver using an isolated pre-command WorkingContext snapshot for eligible local commands. Advisory resolution cannot mutate live selections or authorize execution; durable shadow evidence stores outcome/type rather than private resolved IDs. Unsupported reference types, ambiguous selections and cross-channel context isolation gaps clarify. Email/tab/event/project references and ordinal combinations are not fully connected to production execution.

The admission guard blocks recognized prohibitions conservatively, including Tamil morphology; mixed negative/positive clauses may require clarification. Quoted/reported text is handled by the existing repaired semantic grammar. Unknown and ambiguous candidate output never executes. Recipient/sender reconstruction and corrections retain V2 advisory semantics; full recipient/reference acceptance is still outstanding.

A measured pre-existing confirmation-lifecycle defect was repaired: clearing or expiring pending execution now clears the associated WorkingContext confirmation. An explicit changed-recipient follow-up is routed anew and asks for a fresh ticket. It does not inherit an old approval.

## Capability connection and safety

Live ToolRegistry exports 233 registered schemas. The recorded name inventory is `reports/integration_evidence/registered_tool_names.json`.

Existing registered paths cover files/folders/projects/IDE, browser, Windows/computer, Gmail/Calendar/Drive, WhatsApp, Android control/sharing, automations/reminders, search/knowledge/RAG, notifications, voice/system status and project/backend operations. Registration is not proof of current OAuth, phone pairing, browser/session availability, or exhaustive multilingual ontology coverage. No arbitrary shell, PowerShell, ADB, JavaScript or coordinate-action route was introduced.

Production requests retain schema validation, task-scoped grants, policy, registered tools, verifier and ledger. Normal contacts are rejected at CommandService admission. Authenticated owner WhatsApp behavior retains its existing security boundary. Tests exercise policy/scope/provenance and confirmation behavior with fake tools; no test sent an actual WhatsApp message or executed a destructive production command.

## Response coordinator and language policy

ResponseLanguagePolicy chooses explicit instruction, active conversation metadata, contact preference, input language, then owner default. The local assistant prompt follows this policy; bounded verified-result templates support conversational Tamil/Tanglish while preserving technical names. Arbitrary tool details and all confirmation wordings are not comprehensively localized. Contact-specific Personal Reply style remains separate from command talkback; AI draft provenance rules are unchanged.

ResponseCoordinator keeps a bounded final-response claim set shared by PULSE and the legacy response engine. One request gets one final response; the existing ACK race window suppresses obsolete/immediate ACKs. Phone/WhatsApp results do not also speak on PC speakers, including confirmation prompts. Unverified fallback speech no longer defaults to “Task completed.” Existing verified formatting, error sanitization, playback queue and barge-in cancellation remain.

## Talkback

JarvisSpeechResponseService reuses English Piper/SAPI and adds a pinned local Tamil Piper voice. TTSVoiceRegistry records language/locale/engine/model/rate/availability/rank/fallback. A pronunciation-only lexicon affects speech, never semantic input. Mixed segments preserve whole English identifiers such as FastAPI and Postgres; synthesis is serialized and PCM rates are unified.

Tamil voice: [tinisoft Piper Rasa female model card](https://huggingface.co/tinisoft/piper-ta_IN-rasa_female-medium/blob/89e15edafc8b31e66ddf25f2adbe3bd3f20a9496/README.md), revision `89e15edafc8b31e66ddf25f2adbe3bd3f20a9496`. CC-BY-4.0 attribution to tinisoft and AI4Bharat Rasa is retained with the downloaded model. No new cloud TTS dependency exists.

| Language | Audio bytes | Backend | First complete PCM ms | Playback API completed |
|---|---:|---|---:|---|
| ENGLISH | 115200 | piper | 6214.81 | True |
| TANGLISH | 119296 | piper+piper_tamil | 3652.81 | True |
| TAMIL | 89088 | piper_tamil | 173.05 | True |
| MIXED_TAMIL_ENGLISH | 160256 | piper+piper_tamil | 562.18 | True |

These are real synthesized WAV files and Windows playback calls, not microphone or loopback recordings. The first English and Tanglish samples include cold voice initialization; later samples are warm. First PCM is full-segment synthesis availability, not measured physical speaker onset. Naturalness, clipping, articulation and Tanglish pronunciation: **OWNER_LISTENING_REVIEW_REQUIRED**. Unicode survives and Tamil audio is nonempty; intelligibility is not automatically proven.

A forced English Piper failure produced nonempty real SAPI audio (`sapi_fallback.wav`). Missing Tamil synthesis falls back to visual text rather than claiming an English-only voice supports Tamil. Labelled passwords/tokens/OTP/credential-bearing output is suppressed, and URLs are summarized. This is conservative screening, not exhaustive secret detection. Streaming replies are sentence-chunked by PULSE; the shared service synthesizes one normalized segment at a time.

## Wake word, STT and latency

The existing CPU OpenWakeWord detector, pre-roll ring, VAD, push-to-talk, bounded follow-up window and echo-aware interruption remain. Environmental adaptation can conservatively raise the configured threshold within bounds; it never lowers the configured minimum. The existing consecutive near-score behavior remains. Pre-roll continuity and barge-in are unit-tested, not proven on real owner recordings.

Synthetic wake benchmark: three positive and three negative TTS utterances per condition. Current detector is the installed Hey Jarvis model. It detected Hey Jarvis and missed the synthetic bare Jarvis / Jarvis open Chrome positives. These counts are small development evidence; zero synthetic false accepts is not real-room safety acceptance.

| Synthetic condition | TP / FN / FP / TN | TPR | FPR | FNR | Onset proxy median / p95 ms |
|---|---|---:|---:|---:|---:|
| quiet | 1 / 2 / 0 / 3 | 33.33% | 0.00% | 66.67% | 840.0 / 840.0 |
| fan_synthetic | 1 / 2 / 0 / 3 | 33.33% | 0.00% | 66.67% | 840.0 / 840.0 |
| music_synthetic | 1 / 2 / 0 / 3 | 33.33% | 0.00% | 66.67% | 840.0 / 840.0 |
| far_synthetic | 1 / 2 / 0 / 3 | 33.33% | 0.00% | 66.67% | 840.0 / 840.0 |
| fast_synthetic | 1 / 2 / 0 / 3 | 33.33% | 0.00% | 66.67% | 760.0 / 760.0 |
| slow_synthetic | 1 / 2 / 0 / 3 | 33.33% | 0.00% | 66.67% | 1000.0 / 1000.0 |

Onset proxy is audio-stream offset relative to inserted synthetic speech start, including any TTS leading silence. It is not measured real microphone detection latency. Fan/music/distance/fast/slow conditions are artificial transformations; no real fan, TV, keyboard, near/far or owner-volume recordings were obtained. Bare-Jarvis acceptance has not passed. Push-to-talk remains the reliable fallback; no wake threshold was tuned to make these scores pass.

STT: measured base-model Tamil failure justified installing pinned Systran faster-whisper-small revision `536b0662742c02347bc0e980a01041f333bce120`, with remote LFS model hash verification. NLP weights were not retrained. CUDA DLL discovery reuses already installed local CUDA dependencies without loading torch models. Latest synthetic startup: 9574.60 ms; device: cuda.

Auto STT uses a multilingual model and per-utterance language detection; it no longer forces Tamil output into Latin script. A measured Unicode defect in the noise filter split Tamil combining marks, inflated word rate and discarded valid speech. Generic Unicode-aware word counting repaired it without weakening confidence/noise thresholds.

| Synthetic input | Detected language | STT final ms | Actual transcript |
|---|---|---:|---|
| english | en | 1208.12 | Backhand is running. A PI health is okay. |
| tanglish | ta | 528.15 | இருக்கு |
| tamil | ta | 1145.26 | வணக்கம் சரிப்பார்ப்பு முடிந்தது |
| mixed_tamil_english | en | 658.63 | Fast a PI backhand. Post your connection. Okay. |

All four latest synthetic transcripts are nonempty and Tamil Unicode survives. Technical-term errors and code-switching omissions remain; nonempty text is not ASR correctness. Earlier failed CPU/base and forced-romanization experiments are preserved separately. No exact transcript corrections were added to hide failures.

Real microphone wake latency, VAD latency, STT partial latency, full command-to-ACK audio and verified-result-to-physical-speaker latency: **NOT MEASURED**. New-release semantic routing p50/p95: NOT independently benchmarked. The CPU shadow queue remains bounded/lazy; no encoder, deep model or network is inserted into deterministic command execution. Full fast-route performance/English regression acceptance remains unestablished.

## Phone, WhatsApp and automations

The phone server requires WSS plus a provisioned bearer token, rejects browser-origin traffic, bounds PCM sessions to 30 seconds / 960,000 bytes, shares the same locked PC STT instance and admits only final transcripts. Result text and optional WAV return to the phone; PC speech is suppressed. Existing listener stays loopback. Real token/TLS setup, Android thin-client implementation/pairing and phone speaker playback remain unverified; the original mobile package was a placeholder, not a completed audio client.

Normal WhatsApp conversation observation is advisory. Personal Reply Brain retains existing contact/dyadic profiles, truth-state gates, provenance and language/style logic; candidate conversation features are not an accepted replacement for its authoritative interpretation. Generated automatic replies stay OFF. Manual drafts/authorized owner commands retain their existing review and security paths.

Automation preview uses the shared language service. Existing AutomationManager and registered tools retain scheduling/install/trigger safety. Candidate multi-clause projections are planner hints only; complete cross-domain DAG composition is not established by this pass.

## Dashboard, resources and evidence

Live status: http://127.0.0.1:8765/dashboard/voice-language/page. Desktop System page includes a Voice / Language shortcut. Thirteen cards independently show wake/microphone/VAD/STT/language/Capability Brain/TTS/speaker/barge-in/WhatsApp/Google/phone/shadow. Browser readback: no page errors. Google status is local metadata only; token validity is not asserted without an auth probe. Optional failures do not collapse all health cards.

Live backend health: ready; database ready; STT models/whisper/small on cuda; multilingual shadow ON; candidate controls tools false. Current resource snapshot: `{"processes": [{"pid": 17128, "role": "gateway", "rss_mib": 1021.28515625, "cpu_one_core_percent_snapshot": 28.4}, {"pid": 72956, "role": "child_worker", "rss_mib": 4.82421875, "cpu_one_core_percent_snapshot": 0.0}, {"pid": 72032, "role": "child_worker", "rss_mib": 1275.44921875, "cpu_one_core_percent_snapshot": 0.0}], "gpu_device_snapshot": "NVIDIA GeForce RTX 3050 6GB Laptop GPU, 5095, 6144", "gpu_snapshot_includes_other_applications": true, "idle_ram": "NOT_MEASURED", "peak_resources": "NOT_MEASURED"}`. GPU memory includes other applications; it is not attributed solely to JARVIS. Idle RAM/peak resources are not measured.

Shadow contains five unreviewed conversation observations and zero owner-reviewed commands at report time. Their historical collection provenance is not sufficient to claim real-world accuracy and may include pre-guard test intake. Records are retained, not silently deleted. Live-store collection is now suppressed during pytest; injected temporary stores remain testable. No owner decisions or accuracy labels were inferred from these observations.

## Verification and preservation

**391 tests passed; 1 skipped** (PySide6.QtCore unavailable in the global test interpreter). This includes envelope/raw preservation, language priority, phone auth/PCM final-only delivery, duplicate suppression, Unicode/privacy/fallback paths, prohibition admission, reference ambiguity, context carry-over, policy/scope/security, existing voice/response behavior and WhatsApp provenance. Most end-to-end flows use fake tools/audio; the WAV, synthesis, playback and synthetic wake/STT checks use real local engines.

Stage 2.5 frozen verification passes. V2 model/calibration/configuration/base files and runtime dependency hashes pass verification. Original corpus, audit queue, original labels and human audit decisions were not changed. No V2 TEST/HOLDOUT contents or failure examples were used to repair, tune or train. V3 realistic evaluation remains locked and unconsumed. No accepted semantic model or production promotion was fabricated.

Reports from previous passes remain historical evidence. This new report does not reinterpret their consumed evaluation scores as validation of the current integration.

## Deployment decision and known limits

**INTEGRATED_SHADOW / KEEP_CURRENT. Daily-use acceptance requires more development evidence.** The backend is running with the new integration. The candidate remains advisory and generated WhatsApp auto-replies remain held. The common input/response contracts and local multilingual talkback are functional; whole-JARVIS multilingual execution quality is not yet accepted.

- Bare-Jarvis wake acceptance and real microphone noise/distance benchmarks remain unmet.
- ASR technical-token/code-switching errors remain despite the Unicode and CUDA repairs.
- Tamil/Tanglish voice quality and first-word clipping need listening judgment.
- Phone TLS/token provisioning and actual Android client playback are not complete.
- Canonical slots, typed/contextual references, negation scope, constraints, corrections and multi-step composition do not have complete production acceptance.
- Arbitrary verified output and every confirmation prompt are not fully localized.
- Candidate conversation interpretation remains advisory; existing Personal Reply truth/style gates are preserved.
- Full live English regression, real-command capability recall and calibrated useful execution coverage remain unestablished.

Evidence: `reports/integration_evidence/`; transport/policy documentation: `docs/UNIFIED_INPUT_AND_RESPONSE.md`. No additional project phase was created.


## WhatsApp owner conversation flow ? 2026-10-06

Unread discovery speaks recent unique personal contact names in latest-message order, rather than message previews. The inventory includes all unread personal chats, not only urgent/question messages. A contact name selected from this inventory reads that chat's latest actual message; subsequent `reply` selects the same chat. Selection is exact, channel-isolated, expires after 15 minutes and is cleared on a different task. Saved contact names use the same resolver as presentation; ambiguous names require clarification. Group and secret-message presentation policies remain in place.

Manual reply drafting uses actual selected-chat history and the existing truth/provenance validator. Generic acknowledgements, empty generations and unsupported promises do not become fallback drafts. If a safe contextual reply cannot be generated, the owner is asked what to say. Generated drafts are not treated as owner instructions. Bulk contextual drafting also has no static acknowledgement fallback. Sending retains the existing confirmation and authorization gates. Generated automatic replies remain OFF; no live message was sent during verification.

Verification: 73 tests passed in the combined owner-flow/talkback/conversational/AI integration run; 38 passed in the subsequent owner-flow/talkback/AI integration run. After the channel/saved-name repair, all 10 focused owner-flow tests passed. The final combined owner-flow, conversational-search and AI integration run passed all 62 tests. The restarted backend reports ready with 233 tools, database ready and zero dropped persistence events. Frozen Stage 2.5 verification reports `frozen: true`, no errors. These tests use isolated/fake messages and model responses; they establish flow and safeguards, not real-world reply quality or owner listening acceptance.

## CONVERSATIONAL_SEARCH_REPAIR ? development evidence

Bounded per-channel topic state preserves original wording and resolves glossary-supported technical spelling variations without fuzzy matching contacts, filenames or other critical identifiers. Knowledge questions remain questions. Stable concepts use the existing chat model without RAG, planner or browser execution. Explicit web follow-ups construct queries from topic state, rank technical-domain relevance, fetch at most three public pages in parallel, clean HTML and use one grounded model answer. Sources remain untrusted data; absent/rejected evidence produces an explicit failure. Visual answers include source links, while spoken answers are shorter. Diagnostics are developer-only.

The 11-turn read-only English-override live sequence completed through the chat path with the intended topics; independent assistant evidence records web retrieval and one model call per answer. The 39-test conversational suite passed. The larger regression run recorded 531 passes, one skip and one stale fake-search fixture failure; the fetched-source fixture was corrected and all 13 AI integration tests then passed. This is not a claim that the entire repository test suite passes.

Remaining acceptance defects are recorded rather than hidden: warm multilingual measurements include native Tamil relevance/language-output failures and English output contaminated by earlier Tamil conversation history. Explicit language prompting and Tamil relevance morphology were repaired, but final live multilingual acceptance is not established. Measured HTTP command time also exceeded assistant-stage time substantially on some runs; SQL/executor contention remains a hypothesis, not an established diagnosis. TTS delivery was observed but does not validate spoken content or owner listening quality. Bounded fetch count and warm cache are implemented; reliable end-to-end latency under ordinary machine load is not established.

Classification: **CONTEXT_REPAIR_REQUIRED / WEB_SEARCH_REPAIR_REQUIRED / LATENCY_REPAIR_REQUIRED** for final daily-use acceptance. Development tests and successful English probes do not override remaining multilingual and latency evidence. CURRENT_PRODUCTION stays authoritative, multilingual candidate execution stays OFF, and no TEST/HOLDOUT or frozen training artifact was used for this repair.
