# Stage 2.5 training gate

**Freeze verified; independent audit remains 0/750.** The offline conversation-state resolver is pinned separately from the model and cannot authorize execution. The corpus and queue were not regenerated. Admission still refuses solely because all 750 independent human decisions are missing. No Stage 2.5 weights, calibration, TRAIN/CALIBRATION/DEV files, or latency numbers were produced in this continuation.

Training order after a passing audit remains tiny-overfit regression, full multilingual E5-small fine-tuning with actionability, SpeechAct, ActionFamily, ActionConcept, domain, negation, correction, context, and BIO/span slots plus cross-script contrastive supervision, then threshold calibration and DEV evaluation. This is a plan, not a completed run.

**No Stage 2.5 model was trained.** The 30,000-row Q2 corpus and 750-row review queue are ready; the independent audit has 0 completed decisions. The admission command refuses to emit TRAIN, CALIBRATION, and DEV until that audit passes. This is the required stop point in the Stage 2.5 continuation.

The family-aware splitter is implemented and checked without writing training data. Its current projected counts are 24,118 TRAIN, 2,856 CALIBRATION, and 3,026 DEV, with **zero isolation-family overlap**. Exact 80/10/10 proportions are not guaranteed by hashing whole families. Tamil/Tanglish pairs, context sequences, correction families, and ASR parent/children share an isolation group. The split will be materialized only after admission.

After a passing audit, the planned next stage is the compact multilingual E5-small candidate already downloaded for Stage 2.4: tiny-overfit regression, full encoder fine-tuning with actionability, SpeechAct, ActionFamily, ActionConcept, domain, negation, correction, context requirement, and span heads, then calibration and DEV evaluation. The current corpus contains 12,000 cross-script paired families, but no accepted TRAIN partition or 20,000 quality-checked contrastive relations yet. No trained weights, thresholds, VRAM figures, or inference latency are claimed.

The original TEST and sealed HOLDOUT remain unopened. Production JARVIS routing was not modified.
