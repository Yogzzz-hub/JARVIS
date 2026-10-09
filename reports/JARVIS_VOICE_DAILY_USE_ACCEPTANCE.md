# JARVIS voice daily-use acceptance — 2026-10-06

## Unified voice gender update

Male is now the saved default for every language: Ryan for English and Rasa Male for Tamil. Switching to female selects Lessac and Rasa Female together; Tanglish/mixed utterances use the same selected gender for both script segments. `config/voice_preferences.json` preserves the choice across restarts. Existing voice commands reach the shared service; “women” is recognized as female. A failed switch reports failure and retains the prior pair instead of claiming success.

Both replacement engines load before publication. Switching stops queued speech, invalidates sentence streaming, clears generic clips and regenerates acknowledgement/wake clips in RAM with the selected voice. Startup regenerates those clips rather than loading unlabelled disk audio from the previous gender. The voice registry/status expose the active gender for both languages. Tamil model attribution: [tinisoft Rasa Male](https://huggingface.co/tinisoft/piper-ta_IN-rasa_male-medium), CC-BY-4.0, AI4Bharat Rasa; pinned revision `0b041f8e882b1e6f41f427169be25bcb0e94f352`, downloaded ONNX checked against publisher LFS SHA-256, with local download manifest.

Verification: seven switch/persistence/failure/language/preview tests passed; voice/integration regression 94 passed with one global-environment Qt skip; gender plus TTS tests 32 passed; final voice/owner/integration subset 59 passed (overlapping counts). Eight actual local synthesis cases produced nonempty WAVs for both genders across English/Tamil/Tanglish/mixed, retained under `reports/voice_gender_evidence`. Dashboard listening samples now follow the selected gender and disable browser caching. These are functional audio checks, not owner listening acceptance. The gender update archives the previous shadow source release; current SHA-256 is `64b56624b447bb377617630827753ddf503c7fa37b4834f5562343da40e56f84`.

**VOICE_OWNER_TEST_REQUIRED. READY_FOR_DAILY_USE: NO. Bare Jarvis: NOT_READY.**

Integration remains **INTEGRATED_SHADOW**. Current production routing is authoritative. This pass improves capture, transcription evidence, talkback and local acceptance tooling; it does not establish real-world wake or command accuracy. No owner microphone recordings or listening ratings have been supplied. No NLP training, candidate promotion or new TEST/HOLDOUT evaluation occurred.

## Wake-word audit

The installed OpenWakeWord artifact is `models/wake/hey_jarvis_v0.1.onnx`, with the existing local feature models. There is no installed, verified dedicated bare-Jarvis artifact. Prior synthetic evidence in `reports/integration_evidence/wake_synthetic.json` detected Hey Jarvis but missed bare Jarvis; those results are not owner-microphone acceptance.

The threshold remains 0.5. Runtime can load an optional `models/wake/jarvis_bare.onnx` with a matching SHA-256 manifest identifying the phrase Jarvis, alongside Hey Jarvis in the same CPU feature/inference engine. Missing, mismatched or incompatible artifacts retain the Hey fallback. No dedicated model was fabricated, downloaded without verification or trained in this pass. **Reliable primary bare-Jarvis activation remains an unmet requirement.**

[Official OpenWakeWord documentation](https://github.com/dscripka/openWakeWord) and its [custom training recipe](https://github.com/dscripka/openWakeWord/blob/main/examples/custom_model.yml) support custom keyword training with substantial positive and negative coverage. The [speaker verifier](https://github.com/dscripka/openWakeWord/blob/main/docs/custom_verifier_models.md) addresses false activations; it does not repair a base model that misses bare Jarvis. A compatible dedicated model and independent recordings are still needed.

## Local owner test

Open **http://127.0.0.1:8765/dashboard/voice-benchmark/page**. Select a prompt and explicitly press Record, then speak during the seven-second capture. The page contains 26 prompts: eight bare-Jarvis positives, two Hey-Jarvis positives, four backgrounds and twelve English/Tanglish/Tamil/mixed STT prompts. Conditions include quiet/loud, fast/slow, near/normal distance, technical tokens, contacts, time, status, negation, corrections, references and composition. Listen to the four language previews and choose CLEAR, OK or BAD.

Recordings remain local under `data/voice_owner_acceptance`. Each take has a pre-capture claim, configuration/source hashes, WAV and result evidence. Claimed prompts cannot be overwritten; interrupted claims remain evidence. Captures reuse the existing microphone hub and STT engine. They pause live intake, close follow-up, serialize STT, discard queued triggers and old preroll, and invalidate pending voice sessions before normal intake resumes. They never call CommandService.handle, planner execution or tools. Candidate output is advisory; worker unavailability is recorded without losing microphone/STT evidence. Recordings are evaluation-only and have no training admission path.

Writes require the local page's process nonce and loopback Host/origin checks. Browser verification observed HTTP 200, 26 prompts, 18 status cards, no page errors, 403 for unauthenticated writes and 409 for an authenticated unknown prompt. Browser checks did not record audio or submit owner ratings.

| Required evidence | Current result |
|---|---|
| Real owner takes | 0 / 26 |
| Bare and Hey TP / FP / FN / TN | Not measured |
| Real TPR / FNR / FPR | Not measured |
| Real wake latency p50 / p95 | Not measured |
| Independent STT semantic / critical-entity correctness | Not reviewed |
| Physical first/last-word clipping | Not reviewed |
| Physical barge-in, self-echo, follow-up and destination playback | Not owner-tested |
| English / Tanglish / Tamil / mixed listening | No CLEAR/OK/BAD ratings |

The utility reports clip-level wake counts separately for bare and Hey, sharing the background negatives. Four seven-second backgrounds are insufficient to establish a daily false-activation rate. Wake latency uses an energy-onset proxy, not manually annotated phrase end. STT is scored from the full recorded clip; this does not validate the live wake-window/VAD path. Semantic correctness remains unset pending independent review. Prompt text is an expectation, not proof that the spoken take matches it. Captured onset and preroll timestamps are diagnostics, not proof that words are unclipped.

## Capture and STT changes

Preroll increased from 500 to 1500 ms within the existing two-second ring; endpoint settings are retained. Sessions expose absolute wake, speech, capture-start and STT-feed timestamps. Microphone status includes selected device, sample rate, RMS/noise and health/change history. Stream loss stops listening with typed-input fallback instead of silently switching microphones.

The existing faster-whisper-small multilingual path remains. Raw recognition text, language, word probabilities, uncertain spans and clarification state are retained. Local metadata supplies bounded vocabulary hints; fuzzy post-recognition contact rewriting was removed. Tamil Unicode and technical identifiers survive. Low or missing word evidence and dropped recognized segments request clarification before local or phone commands reach execution. The word-probability cutoff 0.65 is a conservative development heuristic, **not a calibrated semantic confidence threshold**. High acoustic confidence cannot guarantee correct recipients, times or negation.

Existing synthetic audio was transcribed through the real local STT backend. Outputs include English trailing hallucinations, code-switching errors and technical-token errors. They are retained in `reports/voice_daily_evidence/functional.json`; nonempty output is not counted as accuracy. No 95% STT or semantic acceptance claim is made. Physical microphone clipping, room noise and real owner entity accuracy remain pending.

## Talkback and fallback

The shared JarvisSpeechResponseService, VoiceRegistry and response-language policy remain in use. English and installed Tamil voices warm once under the synthesis lock. Piper uses two CPU intra-op threads with spinning disabled; [ONNX Runtime threading guidance](https://onnxruntime.ai/docs/performance/tune-performance/threading.html) explains the resource tradeoff. Small pronunciation substitutions apply only to output speech, never NLP labels or user text.

Completed sentences begin playback without waiting for the next sentence. Cancellation stops later chunks. A failure after playback has started cannot replay the entire response through fallback. The response coordinator still prevents duplicate final responses. Follow-up status exposes remaining time; silence produces no invented command.

Windows SAPI previously hung the broad test run in pyttsx3's COM loop. The same SAPI fallback now creates and releases native COM objects within each synthesis worker, serializes calls, and polls asynchronous completion with cancellation and a ten-second deadline. This follows the native [Speak](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms723609(v=vs.85)) and [WaitUntilDone](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms723616(v=vs.85)) contracts. Six worker calls produced nonempty PCM; a forced Piper failure produced 76,260 bytes through the common SAPI fallback in 315.55 ms. No replacement speech framework or network service was introduced.

| Synthetic functional measurement | English | Tanglish | Tamil | Mixed |
|---|---:|---:|---:|---:|
| Warm first sentence PCM ready, ms | 261.79 | 373.34 | 316.40 | 524.00 |
| Two-sentence synthesis total, ms | 491.06 | 917.33 | 683.44 | 894.31 |

These are individual functional observations, not p50/p95 or physical speaker-start measurements. Fresh cold English PCM took 4345.14 ms and Tamil 7296.55 ms. Before the thread change, separate observations took 10336.91 and 12190.44 ms; machine load was uncontrolled, so this is not an isolated causal benchmark. Both evidence files are preserved. Fresh backend voice warmup took 5043.15 ms with a 218.55 MiB process-memory increase. The 1.4 MiB subsequent cache-warm delta in the functional test must not be mistaken for full model memory.

Resource snapshot: backend RSS 1000.01 MiB; one-second idle process CPU 29.7% of one core. Whole-machine available RAM was only 257.02 MiB of 16107.87 MiB amid concurrent work. Whole-GPU usage was 4681/6144 MiB; this is not JARVIS-specific VRAM. These uncontrolled snapshots cannot establish steady-state resource acceptance. Real command/STT/wake and physical audio latency distributions remain unmeasured.

## Verification and preserved boundaries

The broad suite completed after the SAPI repair: **3206 passed, 42 failed, 8 skipped, 15 legacy-holdout tests deselected**. Four structural ML tests passed separately in the CUDA environment. The broad run excluded that ML module from the global Python environment. Failures include router/scope, Google registration, WhatsApp and talkback confirmation/ledger behavior; they are unresolved, and no pristine baseline establishes that they predate this pass. The isolated talkback confirmation test also failed with UNCERTAIN rather than SUCCESS. These are acceptance blockers; the suite is not reported as all green.

Final focused verification: **425 passed, 1 skipped** (`voice_daily_verified_final.log`); the skip is Qt in the global Python environment. The final owner/safety module separately passed **34 tests** (`voice_daily_owner_final.log`); those tests overlap the 425 and must not be added to that count. They cover owner persistence/no execution, capture epoch isolation, raw transcripts, low-confidence refusal, Unicode, bounded hints, mic loss, streaming cancellation/no replay, native SAPI worker handling, local control security and existing integration/voice/security behavior. Detailed broad failures remain in `voice_daily_full_regression_final.log`.

Stage 2.5 freeze verification reports frozen=true with no errors. Original V2 model/calibration/configuration verification passes. Frozen data, source labels, human decisions and original manifests were not modified. The new shadow development source release archives its predecessor and has SHA-256 `a876b49d55d30dbe99b6848687c71063f22d9c89c115b13f2d1e2703bf25b15e`. Production router/planner/policy/TaskScope/ToolRegistry/verification/ActionLedger sources were not changed by this voice pass. Existing unrelated workspace changes remain intact.

The voice naturalness module was also run in the actual production virtual environment, including Qt: **16 passed** (`voice_daily_qt_production_environment.log`). This resolves the environment-specific skipped Qt check; these results overlap the focused suite and are not additive. Final live status confirms INTEGRATED_SHADOW, production_authoritative=true, VOICE_OWNER_TEST_REQUIRED and zero owner records.

## Decision and remaining acceptance

**VOICE_OWNER_TEST_REQUIRED; KEEP_CURRENT.** This is an implemented development/test pass, not completed daily-use acceptance. Required next evidence is owner recordings and four listening ratings. Reliable bare activation requires the missing dedicated model; recording the installed Hey model alone cannot satisfy that requirement. Independent semantic/critical-entity review, live clipping/barge-in/follow-up checks, full multilingual NLP acceptance and resolution of broader regression failures remain necessary. No candidate promotion or generated WhatsApp reply execution is authorized by these results.
