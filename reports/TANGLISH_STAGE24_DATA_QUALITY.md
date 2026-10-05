# Tanglish Stage 2.4 data quality audit

**Decision: quarantine the existing synthetic corpus from full encoder fine-tuning until its language labels, semantic equivalence, and object/action compatibility are repaired.** This is a development-data decision. The original Stage 2 TEST and sealed HOLDOUT were not opened.

The audit read 80,000 Stage 2 train, 10,000 Stage 2 development, 16,000 Stage 2.1 repair-train, and 10,000 repair-development rows. Normalized exact input overlap between combined train and combined development was zero. Near-duplicate and construction-family leakage was not re-estimated here. A deterministic stratified sample of **355 train rows** was reviewed: 25 from each of 11 Stage 2 construction categories and eight from each of 10 repair SpeechActs. The sample and counts are preserved in ignored `data/tanglish/generated/stage24/`.

| Finding | Evidence | Effect |
|---|---|---|
| Language labels are unreliable | 7,424/9,875 Stage 2 train rows labelled English and 1,089/1,303 Stage 2 development rows labelled English contain explicit Romanized Tamil markers. | English-only safety and recall slices are invalid as currently labelled. Reclassify at token/utterance level, with UNKNOWN for ambiguous cases. |
| Some ASR positives change or lose meaning | In the 355-row review, `car two files` was labelled COMMAND/LIST; `Deepa oda second FOLDER pour do` COMMAND/CREATE; `report ah a noop tomorrow Naveen kitta` COMMAND/SEND; `Sigma mudiyum munadi answer could do` COMMAND/PROVIDE; `ERROR mattum par who` COMMAND/INSPECT. | Do not align these as clean-command positives. Quarantine the Stage 2 `asr_noise` category until clean source utterances and meaning-preservation checks are available. |
| Object/action combinations can be implausible | Reviewed repair examples include `second audio poi kaatu` labelled NAVIGATE, `first folder run` labelled RUN, `increase first tab` labelled INCREASE, and `latest app enter pannu` labelled ENTER. | Validate action affordances before using such rows for fine ActionConcept and slot supervision. |
| Correction records are sometimes malformed | `third tab forward Arun ku... illa Mohan ku Mohan ku` duplicates the active recipient. | Validate active versus superseded spans and remove malformed cases. |
| Fine SpeechAct labels conflict across source generators | All 4,000 Stage 2 train rows in its `correction` category are labelled COMMAND, while Stage 2.1 repair rows use CORRECTION. Both are action eligible, but the fine labels disagree. | Define one correction annotation policy and create processed copies with provenance before fine SpeechAct training. |
| Actionability cues can be unnatural | Several generated commands combine `pannu` or `venam` in ways a speaker is unlikely to use. | Keep synthetic data as controlled diagnostics until reviewed; raw volume is not evidence of real-language coverage. |

The audit's automated checks found **no unknown ActionConcept** or direct `should_execute`/SpeechAct inconsistency in these sources. They flagged English-labelled utterances containing seed Tanglish markers. That flag is evidence about language labelling, not proof that the utterance's action label is wrong. Pronouns inside quoted metalinguistic examples were excluded from missing-context flags after manual inspection. Review flags are not automatic rejection labels.

The 48-row authored tiny-overfit set in ignored `data/tanglish/generated/stage24/tiny_overfit_train.jsonl` has explicit active character spans for recipient, sender, application, file, ordinal, file type, destination, and number where present. It is suitable **only** to test model capacity and slot decoder mechanics. It cannot support held-out accuracy claims. It has six SpeechActs and eight ActionConcepts; the full ontology and all 33 slots remain unsupervised by this tiny set.

## Data gate before full training

1. Link each ASR corruption to its clean source and reject pairs whose SpeechAct, ActionConcept, entity, or constraint meaning changes.
2. Reclassify language from utterance tokens, audit several hundred ambiguous cases, and build balanced English command/noncommand development families isolated from train.
3. Validate action-object affordances, active correction spans, full slot spans, and frame consistency for every generated row. Keep rejected row IDs and reasons in a manifest.
4. Build independent naturalistic capability queries and typed slot annotations. Registry example paraphrases are insufficient.

No existing row was silently rewritten or promoted to executable training gold. The corpus audit is reproducible with `python -m scripts.audit_tanglish_stage24_data`; the tiny diagnostic is built with `python -m scripts.build_tanglish_stage24_tiny`.
