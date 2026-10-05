# Stage 2.5 final Tamil/Tanglish distribution

**Pre-review machine gate: PASS.** Corpus SHA-256 `0e826b3f24a768029efe74d5044104f7831cb76a1e9006ab529c822f25a4b1bf`. These are synthetic Q2 candidates; naturalness and semantic fidelity require the independent 750-row human audit. TEST and HOLDOUT were not read.

## Corpus and action balance

| Language | Rows |
|---|---|
| TAMIL | 12000 |
| TANGLISH | 18000 |

SEND + SHARE + FORWARD: 2,659/30,000 (8.86%).

| ActionFamily | Rows |
|---|---|
| ACCESS | 2613 |
| ANALYZE | 289 |
| CAPTURE | 388 |
| COMMUNICATE | 3235 |
| CONTENT_EDIT | 522 |
| CONTROL | 2982 |
| INSPECT | 6665 |
| LIFECYCLE | 3084 |
| None | 68 |
| PROVIDE | 1384 |
| RESOURCE_TRANSFER | 3612 |
| SELECT_ORGANIZE | 1966 |
| TRANSFORM | 3192 |

| ActionConcept | Rows | Tamil | Tanglish |
|---|---|---|---|
| ATTACH | 197 | 92 | 105 |
| CALL | 301 | 137 | 164 |
| CANCEL | 366 | 174 | 192 |
| CAPTURE | 388 | 151 | 237 |
| CHANGE | 218 | 108 | 110 |
| CHECK | 1130 | 546 | 584 |
| CLICK | 221 | 108 | 113 |
| CLOSE | 497 | 238 | 259 |
| COMPARE | 289 | 123 | 166 |
| CONVERT | 440 | 150 | 290 |
| COPY | 1153 | 150 | 1003 |
| CREATE | 626 | 302 | 324 |
| DECREASE | 339 | 150 | 189 |
| DELETE | 774 | 367 | 407 |
| DOWNLOAD | 287 | 122 | 165 |
| ENTER | 242 | 112 | 130 |
| EXPLAIN | 408 | 148 | 260 |
| FILTER | 284 | 124 | 160 |
| FIND | 280 | 128 | 152 |
| FORWARD | 506 | 149 | 357 |
| INCREASE | 445 | 182 | 263 |
| INSPECT | 282 | 121 | 161 |
| INSTALL | 298 | 139 | 159 |
| LIST | 480 | 223 | 257 |
| MOVE | 813 | 353 | 460 |
| MUTE | 195 | 90 | 105 |
| NAVIGATE | 457 | 218 | 239 |
| None | 68 | 34 | 34 |
| OPEN | 1659 | 816 | 843 |
| PAUSE | 295 | 135 | 160 |
| PLAY | 228 | 114 | 114 |
| PROVIDE | 372 | 146 | 226 |
| READ | 912 | 380 | 532 |
| RENAME | 249 | 110 | 139 |
| REPLACE | 236 | 110 | 126 |
| REPLY | 275 | 125 | 150 |
| RESTART | 482 | 234 | 248 |
| RESUME | 293 | 138 | 155 |
| RETRIEVE | 556 | 146 | 410 |
| RUN | 478 | 228 | 250 |
| SAVE | 726 | 350 | 376 |
| SEARCH | 971 | 465 | 506 |
| SELECT | 1406 | 148 | 1258 |
| SEND | 1873 | 606 | 1267 |
| SET | 746 | 373 | 373 |
| SHARE | 280 | 121 | 159 |
| SHOW | 1773 | 753 | 1020 |
| SORT | 276 | 115 | 161 |
| START | 297 | 137 | 160 |
| STOP | 298 | 139 | 159 |
| SUMMARIZE | 604 | 302 | 302 |
| SWITCH | 519 | 242 | 277 |
| UNINSTALL | 294 | 138 | 156 |
| UNMUTE | 195 | 90 | 105 |
| UPLOAD | 1162 | 148 | 1014 |
| VERIFY | 281 | 122 | 159 |
| WRITE | 280 | 130 | 150 |

## Speech and slots

| SpeechAct | Rows |
|---|---|
| ACKNOWLEDGEMENT | 16 |
| AMBIGUOUS | 238 |
| CAPABILITY_QUERY | 1750 |
| CHAT | 20 |
| COMMAND | 13527 |
| CONFIRMATION | 16 |
| CORRECTION | 1866 |
| HYPOTHETICAL | 700 |
| META_CONTROL | 67 |
| NEGATED_COMMAND | 4436 |
| QUESTION | 651 |
| STATEMENT | 2448 |
| STATUS_QUERY | 4265 |

| Slot | Annotations |
|---|---|
| URL | 495 |
| application | 1957 |
| attachment | 199 |
| browser | 1014 |
| browser_tab | 754 |
| contact | 681 |
| count | 443 |
| date | 4944 |
| date_range | 118 |
| destination | 3949 |
| device | 4172 |
| exclude_constraint | 148 |
| file | 869 |
| file_type | 10690 |
| folder | 192 |
| include_constraint | 146 |
| message_content | 376 |
| number | 1225 |
| ordinal | 6528 |
| percentage | 162 |
| project | 4696 |
| quantity | 143 |
| query | 151 |
| quoted_resource | 135 |
| recipient | 3060 |
| resource_type | 7477 |
| selected_resource | 3083 |
| sender | 6119 |
| source | 556 |
| spatial_relation | 122 |
| time | 548 |
| time_range | 190 |
| workflow | 192 |

| Slots per frame | Rows |
|---|---|
| 0 | 0 |
| 1 | 6792 |
| 2 | 12201 |
| 3 | 9820 |
| 4+ | 1187 |

## Action × object coverage

Only observed valid combinations are listed. Priority matrix holes are checked at 50 rows per combination; other valid affordances remain candidate expansion areas.

| ActionConcept | ObjectType | Rows | Affordance |
|---|---|---|---|
| ATTACH | FileRef | 197 | VALID |
| CALL | ContactRef | 301 | VALID |
| CANCEL | WorkflowRef | 366 | VALID |
| CAPTURE | ScreenshotRef | 388 | VALID |
| CHANGE | TextResource | 218 | VALID |
| CHECK | FileRef | 316 | VALID |
| CHECK | MessageRef | 298 | VALID |
| CHECK | ProjectRef | 307 | VALID |
| CHECK | SystemStatusRef | 209 | VALID |
| CLICK | UIElementRef | 221 | VALID |
| CLOSE | AppRef | 497 | VALID |
| COMPARE | FileRef | 289 | VALID |
| CONVERT | FileRef | 440 | VALID |
| COPY | FileRef | 1153 | VALID |
| CREATE | CalendarEventRef | 556 | VALID |
| CREATE | FolderRef | 70 | VALID |
| DECREASE | Brightness | 53 | VALID |
| DECREASE | Volume | 286 | VALID |
| DELETE | FileRef | 774 | VALID |
| DOWNLOAD | FileRef | 287 | VALID |
| ENTER | TextResource | 242 | VALID |
| EXPLAIN | TextResource | 408 | VALID |
| FILTER | FileRef | 284 | VALID |
| FIND | FileRef | 280 | VALID |
| FORWARD | MessageRef | 506 | VALID |
| INCREASE | Brightness | 358 | VALID |
| INCREASE | Volume | 87 | VALID |
| INSPECT | FileRef | 282 | VALID |
| INSTALL | AppRef | 298 | VALID |
| LIST | CalendarEventRef | 190 | VALID |
| LIST | FileRef | 290 | VALID |
| MOVE | FileRef | 813 | VALID |
| MUTE | Volume | 195 | VALID |
| NAVIGATE | BrowserPageRef | 307 | VALID |
| NAVIGATE | URLRef | 150 | VALID |
| OPEN | AppRef | 507 | VALID |
| OPEN | FileRef | 807 | VALID |
| OPEN | URLRef | 345 | VALID |
| PAUSE | ProjectRef | 295 | VALID |
| PLAY | AudioRef | 228 | VALID |
| PROVIDE | AnswerRef | 372 | VALID |
| READ | FileRef | 449 | VALID |
| READ | MessageRef | 463 | VALID |
| RENAME | FileRef | 249 | VALID |
| REPLACE | TextResource | 236 | VALID |
| REPLY | MessageRef | 275 | VALID |
| RESTART | ProjectRef | 482 | VALID |
| RESUME | ProjectRef | 293 | VALID |
| RETRIEVE | DataRef | 556 | VALID |
| RUN | ProjectRef | 286 | VALID |
| RUN | WorkflowRef | 192 | VALID |
| SAVE | FileRef | 726 | VALID |
| SEARCH | FileRef | 229 | VALID |
| SEARCH | MessageRef | 301 | VALID |
| SEARCH | ProjectRef | 290 | VALID |
| SEARCH | WebQueryRef | 151 | VALID |
| SELECT | FileRef | 1406 | VALID |
| SEND | FileRef | 1739 | VALID |
| SEND | MessageRef | 134 | VALID |
| SET | Brightness | 82 | VALID |
| SET | Volume | 664 | VALID |
| SHARE | FileRef | 280 | VALID |
| SHOW | FileRef | 1390 | VALID |
| SHOW | MessageRef | 383 | VALID |
| SORT | FileRef | 276 | VALID |
| START | ProjectRef | 297 | VALID |
| STOP | ProjectRef | 298 | VALID |
| SUMMARIZE | MessageRef | 604 | VALID |
| SWITCH | BrowserTabRef | 519 | VALID |
| UNINSTALL | AppRef | 294 | VALID |
| UNMUTE | Volume | 195 | VALID |
| UPLOAD | FileRef | 1162 | VALID |
| VERIFY | FileRef | 281 | VALID |
| WRITE | TextResource | 280 | VALID |

## Context, correction, negation, noise

| Context reference | Rows |
|---|---|
| active_app | 215 |
| active_thread | 204 |
| browser_tab | 205 |
| current_project | 219 |
| previous_result | 209 |
| selected_resource | 2670 |

| Corrected active slot | Rows |
|---|---|
| application | 300 |
| destination | 300 |
| file_type | 300 |
| number | 300 |
| recipient | 366 |
| time | 300 |

| Negated action | Rows |
|---|---|
| CALL | 68 |
| CANCEL | 66 |
| CAPTURE | 79 |
| CHANGE | 48 |
| CHECK | 202 |
| CLICK | 48 |
| CLOSE | 106 |
| COMPARE | 60 |
| CONVERT | 66 |
| COPY | 237 |
| CREATE | 66 |
| DECREASE | 70 |
| DELETE | 66 |
| DOWNLOAD | 69 |
| EXPLAIN | 99 |
| FILTER | 50 |
| FIND | 60 |
| FORWARD | 66 |
| INCREASE | 83 |
| INSPECT | 58 |
| INSTALL | 70 |
| LIST | 66 |
| MOVE | 66 |
| NAVIGATE | 66 |
| OPEN | 132 |
| PAUSE | 71 |
| PLAY | 48 |
| PROVIDE | 88 |
| READ | 66 |
| REPLY | 52 |
| RESTART | 106 |
| RESUME | 64 |
| RETRIEVE | 133 |
| RUN | 64 |
| SAVE | 62 |
| SEARCH | 184 |
| SELECT | 313 |
| SEND | 66 |
| SET | 66 |
| SHARE | 73 |
| SHOW | 66 |
| SORT | 56 |
| START | 68 |
| STOP | 68 |
| SUMMARIZE | 106 |
| SWITCH | 106 |
| UNINSTALL | 69 |
| UPLOAD | 246 |
| VERIFY | 64 |
| WRITE | 64 |

Context-required rows: 3,722. Correction rows: 1,866. ASR positive rows: 1,500; each was checked against its clean frame.

## Surface polysemy diagnostic

The following counts use a simple predicate-tail proxy (text after the last explicit slot), paired with the labelled action. Corrections and unusual word orders can be missed; these are not an independently measured verb-sense score.

| Verb family | Action label | Tamil | Tanglish |
|---|---|---|---|
| anupu / அனுப்பு | REPLY | 125 | 0 |
| anupu / அனுப்பு | SEND | 590 | 1251 |
| eduthu / எடு | CAPTURE | 151 | 237 |
| eduthu / எடு | RETRIEVE | 146 | 410 |
| eduthu / எடு | SELECT | 148 | 1258 |
| kaatu / காட்டு | LIST | 223 | 257 |
| kaatu / காட்டு | NAVIGATE | 33 | 40 |
| kaatu / காட்டு | SHOW | 688 | 939 |
| kudu / கொடு | PROVIDE | 72 | 112 |
| kudu / கொடு | REPLY | 0 | 150 |
| kudu / கொடு | SEND | 8 | 8 |
| kudu / கொடு | SUMMARIZE | 302 | 302 |
| maathu / மாற்று | CHANGE | 108 | 110 |
| maathu / மாற்று | CONVERT | 150 | 290 |
| maathu / மாற்று | MOVE | 142 | 249 |
| maathu / மாற்று | RENAME | 110 | 0 |
| maathu / மாற்று | REPLACE | 110 | 0 |
| maathu / மாற்று | SWITCH | 123 | 277 |
| paaru / பார் | CHECK | 546 | 58 |
| paaru / பார் | READ | 355 | 413 |
| paaru / பார் | VERIFY | 122 | 0 |
| pannu / பண்ணு | ATTACH | 0 | 92 |
| pannu / பண்ணு | CALL | 0 | 152 |
| pannu / பண்ணு | CANCEL | 0 | 176 |
| pannu / பண்ணு | CHECK | 0 | 445 |
| pannu / பண்ணு | CLICK | 0 | 108 |
| pannu / பண்ணு | CLOSE | 0 | 242 |
| pannu / பண்ணு | COMPARE | 0 | 152 |
| pannu / பண்ணு | COPY | 0 | 937 |
| pannu / பண்ணு | CREATE | 0 | 35 |
| pannu / பண்ணு | DECREASE | 0 | 172 |
| pannu / பண்ணு | DELETE | 0 | 380 |
| pannu / பண்ணு | DOWNLOAD | 0 | 152 |
| pannu / பண்ணு | ENTER | 0 | 112 |
| pannu / பண்ணு | FILTER | 0 | 152 |
| pannu / பண்ணு | FORWARD | 0 | 248 |
| pannu / பண்ணு | INCREASE | 0 | 252 |
| pannu / பண்ணு | INSPECT | 0 | 150 |
| pannu / பண்ணு | INSTALL | 0 | 150 |
| pannu / பண்ணு | MOVE | 0 | 150 |
| pannu / பண்ணு | MUTE | 0 | 90 |
| pannu / பண்ணு | NAVIGATE | 0 | 67 |
| pannu / பண்ணு | OPEN | 0 | 816 |
| pannu / பண்ணு | PAUSE | 0 | 150 |
| pannu / பண்ணு | RENAME | 0 | 110 |
| pannu / பண்ணு | REPLACE | 0 | 110 |
| pannu / பண்ணு | RESTART | 0 | 236 |
| pannu / பண்ணு | RESUME | 0 | 150 |
| pannu / பண்ணு | RUN | 0 | 228 |
| pannu / பண்ணு | SAVE | 0 | 357 |
| pannu / பண்ணு | SEARCH | 0 | 469 |
| pannu / பண்ணு | SHARE | 0 | 150 |
| pannu / பண்ணு | SORT | 0 | 150 |
| pannu / பண்ணு | START | 0 | 150 |
| pannu / பண்ணு | STOP | 0 | 150 |
| pannu / பண்ணு | UNINSTALL | 0 | 150 |
| pannu / பண்ணு | UNMUTE | 0 | 90 |
| pannu / பண்ணு | UPLOAD | 0 | 966 |
| pannu / பண்ணு | VERIFY | 0 | 150 |
| podu / போடு | CREATE | 252 | 194 |
| podu / போடு | MOVE | 0 | 61 |
| podu / போடு | PLAY | 90 | 34 |
| podu / போடு | SET | 0 | 273 |
| sollu / சொல் | EXPLAIN | 53 | 33 |
| sollu / சொல் | PROVIDE | 57 | 33 |
| sollu / சொல் | READ | 19 | 2 |

## Diversity and duplicate checks

Construction families: 1,884; median size 12; p95 size 50; largest 240; top-ten share 4.76%. Rows in families over 250: 0.

Exact duplicate excess: 0; normalized text/context duplicate excess: 0; phonetic plus same-frame collision excess: 1500; after excluding deliberate ASR positive children: 0. The 1,500 ASR positive children account for the phonetic collisions in this corpus and remain explicit review targets. Normalization uses Unicode NFKC for both scripts. The remaining shared construction skeletons are deliberate composition, and family-isolated splitting prevents template leakage.

## Pre-review gate

| Check | Result |
|---|---|
| row_count | PASS |
| script_ratio | PASS |
| supported_action_floor | PASS |
| slot_floor | PASS |
| speech_coverage | PASS |
| hard_negative_coverage | PASS |
| context_floor | PASS |
| correction_floor | PASS |
| asr_ceiling | PASS |
| transfer_ceiling | PASS |
| construction_family_ceiling | PASS |
| unique_ids | PASS |
| exact_duplicates | PASS |
| normalized_duplicates | PASS |
| validator | PASS |
| priority_action_object_matrix | PASS |

## Frozen independent audit queue

Rows: 750; Tamil 300; Tanglish 450. Queue SHA-256 `4144afbf69084beb222e0fcd712019345986a97ff5d6f9122a38269a033c5be4`. Risk-stratification check: PASS.

| Audit stratum | Rows |
|---|---|
| difficult:context | 89 |
| difficult:correction | 66 |
| difficult:negation | 101 |
| difficult:asr | 51 |
| difficult:ambiguity | 25 |
| difficult:complex_frame | 77 |
| risk:external_or_destructive | 180 |
| difficult:action_word_no_action | 391 |

All observed SpeechActs, ActionConcepts, and slot names have queue coverage; scarce slots and each seeded polysemous verb were oversampled. The earlier queue is archived as `STALE_PRE_REBALANCE` and must not be reviewed.

Sparse areas: ACKNOWLEDGEMENT, CONFIRMATION and CHAT remain below 25 examples each; they are represented but not acceptance-quality classifiers on their own. Some action-object combinations outside the priority matrix have few examples. All corpus labels and Tamil realizations still require human audit.
