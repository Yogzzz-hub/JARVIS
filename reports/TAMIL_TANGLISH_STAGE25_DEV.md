# Stage 2.5 DEV acceptance status

**Recommendation: RETRAIN, contingent on a passing human audit.** Current operational status is awaiting 750 independent reviews, not a measured DEV failure. No Stage 2.5 model has been trained or evaluated, so DEV acceptance metrics remain N/A. The original TEST and sealed HOLDOUT remain unopened. This recommendation does not authorize training before admission.

The offline conversation-state policy and frozen data revision pass 24 focused tests and freeze verification. The 16 corpus machine gates were already passing and the admission recheck now reports only `audited_rows_below_750:0`. The state policy has no production execution path; any future approval must revalidate the exact pending ticket.

**Decision: AWAIT HUMAN AUDIT.** The generator and validators produced 30,000 Q2 rows, and an independent 750-row review queue exists. No independent decision has been recorded, so admission, TRAIN/CALIBRATION/DEV split creation, model training, and DEV model evaluation remain blocked. The original TEST and sealed HOLDOUT are unopened.

The rebalanced corpus's machine checks found zero validator errors, zero normalized utterance/context duplicates, and zero planned family leakage. All 56 supported action labels have at least 150 rows, and all 33 slots have at least 100 annotations. These are data-integrity and coverage results, not model metrics. Action trigger precision, executable recall, false action rate, SpeechAct and ActionConcept accuracy, slot F1, reference resolution, verb-sense accuracy, capability Recall@5, and inference latency are **N/A** until a model is trained and independently evaluated.

`python -m pytest tests/test_stage25_gold_data.py tests/test_stage25_conversation_state.py -q` passes 24 focused safety, data, and state-policy tests. `python -m scripts.stage25_quality_report` and `python -m scripts.stage25_final_distribution` reproduce the distributions and pre-review gate. The current admission check refuses solely because `audited_rows_below_750:0`.

The DEV targets remain those in the user's master prompt: action precision at least 99%, false action rate below 0.5%, no-action specificity and negation at least 99%, executable recall at least 90%, SpeechAct and ActionConcept at least 90%, slot F1 and reference accuracy at least 90%, capability Recall@5 at least 98%, and zero critical semantic safety failures. No threshold has been tuned against TEST or HOLDOUT.
