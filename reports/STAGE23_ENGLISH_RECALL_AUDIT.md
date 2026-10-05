# Stage 2.3 English and clear-command recall audit

This audit used only Stage 2 train and development data. The original test and sealed holdout remain unopened. The local machine-readable counts and score distributions are in ignored `data/tanglish/generated/stage23/english_audit.json`.

## What the English metric actually measured

The Stage 2.2 evaluation partition contains **632 rows labelled English, all 632 actionable commands**. It contains no English questions, negated commands, statements, or other no-action examples. Therefore the reported 100% English trigger precision and 100% speech-act accuracy are not evidence of English no-action safety. The 632 examples are all from the synthetic `clear` category.

The underlying Stage 2 `clear` data is likewise command-only: 16,000 train rows, including 9,875 labelled English, and 2,000 dev rows, including 1,303 labelled English. Train and dev use different construction-family templates by design. The Stage 2.1 repair generator labels most of its English-like snippets as Tanglish or mixed, so it does not supply a reliable English no-action evaluation stratum. This is a dataset composition and language-label problem, not a result that can be fixed by moving a single threshold.

## Score and routing evidence

| Development subset | True commands | Median fast score | Median fallback score | Candidate | Uncertain | False NO_ACTION |
|---|---:|---:|---:|---:|---:|---:|
| English | 632 | 0.833 | 0.931 | 159 | 473 | 0 |
| Clear, all languages | 966 | 0.818 | 0.920 | 234 | 730 | 2 |
| ASR-like | 173 | 0.609 | 0.698 | 10 | 120 | 43 |

The Stage 2.2 thresholds were 0.936 for the fast candidate and 0.976 for the fallback candidate. The English command median lies below both. **473 of 632 English commands were withheld as UNCERTAIN**, explaining the 25.16% candidate recall. The uncertainty policy prevented these from becoming false NO_ACTION decisions, but no measured planner resolved them.

The existing action and speech heads score the English subset perfectly because its labels and constructions are simple and homogeneous. That does not establish semantic understanding. The dev syntax differs from train, and examples such as “Sigma pathi pesumbodhu, NOTE ah write” are marked English despite Tanglish grammatical particles. Some context rows replace a resource with “atha” while retaining an English label. This further weakens the language-specific metric.

## Root causes and repair requirements

1. **Evaluation composition:** English has no no-action negatives, so English precision and specificity cannot be estimated.
2. **Language labels:** Category-based generation mislabels English/Tanglish spans. Detect language from the actual utterance and previous turns, then audit the labels.
3. **Calibration:** Global thresholds calibrated against the mixed development pool leave many valid English commands in UNCERTAIN. Lowering them without representative English negatives would be unsafe.
4. **Representation and split:** Stage 2 train/dev have isolated synthetic constructions. The fall in command scores on clear dev supports a generalization issue, although this audit cannot isolate its exact share from calibration.
5. **ASR:** ASR-like commands show both low scores and 43 false NO_ACTION decisions among 173 commands. Their generated corruptions need independent review before model tuning.

Next evaluation data should include independently reviewed English commands and matched English noncommands, polite question-form requests, negations, statements, corrections, and context-dependent cases. Keep matched families within one split. Use the existing public corpora only for language statistics; do not assign arbitrary public utterances executable labels. No English phrase rules were added.
