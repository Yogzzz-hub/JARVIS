# Stage 2.5 action ontology coverage

Counts refer to the frozen Q2 candidate corpus, before independent human review. A supported label is a language meaning, never tool authorization. The four collapsed labels are represented by typed frames; PAY and SUBMIT need a registered execution and policy contract before language-level training or action.

Corpus SHA-256: `0e826b3f24a768029efe74d5044104f7831cb76a1e9006ab529c822f25a4b1bf`. Supported concepts: 56 of 62.

| ActionConcept | ActionFamily | Total | Tamil | Tanglish | Decision | Required repair |
|---|---|---|---|---|---|---|
| ANSWER | PROVIDE | 0 | 0 | 0 | DOWNSTREAM_TOOL_ONLY | Represent the request as PROVIDE plus AnswerRef; answer wording is resolved downstream. |
| ATTACH | RESOURCE_TRANSFER | 197 | 92 | 105 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| CALL | COMMUNICATE | 301 | 137 | 164 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| CANCEL | LIFECYCLE | 366 | 174 | 192 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| CAPTURE | CAPTURE | 388 | 151 | 237 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| CHANGE | TRANSFORM | 218 | 108 | 110 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| CHECK | INSPECT | 1130 | 546 | 584 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| CLICK | CONTROL | 221 | 108 | 113 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| CLOSE | ACCESS | 497 | 238 | 259 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| COMPARE | ANALYZE | 289 | 123 | 166 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| CONVERT | TRANSFORM | 440 | 150 | 290 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| COPY | RESOURCE_TRANSFER | 1153 | 150 | 1003 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| CREATE | LIFECYCLE | 626 | 302 | 324 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| DECREASE | TRANSFORM | 339 | 150 | 189 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| DELETE | LIFECYCLE | 774 | 367 | 407 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| DOWNLOAD | RESOURCE_TRANSFER | 287 | 122 | 165 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| ENTER | CONTENT_EDIT | 242 | 112 | 130 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| EXPLAIN | PROVIDE | 408 | 148 | 260 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| FILTER | SELECT_ORGANIZE | 284 | 124 | 160 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| FIND | INSPECT | 280 | 128 | 152 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| FORWARD | COMMUNICATE | 506 | 149 | 357 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| INCREASE | TRANSFORM | 445 | 182 | 263 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| INSERT | CONTENT_EDIT | 0 | 0 | 0 | DOWNSTREAM_TOOL_ONLY | Represent insertion as ENTER or WRITE using the destination and position slots. |
| INSPECT | INSPECT | 282 | 121 | 161 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| INSTALL | LIFECYCLE | 298 | 139 | 159 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| LIST | INSPECT | 480 | 223 | 257 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| MOVE | RESOURCE_TRANSFER | 813 | 353 | 460 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| MUTE | CONTROL | 195 | 90 | 105 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| NAVIGATE | ACCESS | 457 | 218 | 239 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| OPEN | ACCESS | 1659 | 816 | 843 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| PAUSE | CONTROL | 295 | 135 | 160 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| PAY | EXTERNAL_TRANSACTION | 0 | 0 | 0 | REGISTRY_GAP | No general payment capability or safe execution contract is registered; retain as a policy-sensitive semantic gap. |
| PLAY | CONTROL | 228 | 114 | 114 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| PROVIDE | PROVIDE | 372 | 146 | 226 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| READ | INSPECT | 912 | 380 | 532 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| RENAME | TRANSFORM | 249 | 110 | 139 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| REPLACE | TRANSFORM | 236 | 110 | 126 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| REPLY | COMMUNICATE | 275 | 125 | 150 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| RESTART | CONTROL | 482 | 234 | 248 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| RESUME | CONTROL | 293 | 138 | 155 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| RETRIEVE | INSPECT | 556 | 146 | 410 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| RETURN | PROVIDE | 0 | 0 | 0 | DOWNSTREAM_TOOL_ONLY | Represent a requested result as PROVIDE plus its resource type; transport is resolved downstream. |
| RUN | CONTROL | 478 | 228 | 250 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| SAVE | LIFECYCLE | 726 | 350 | 376 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| SEARCH | INSPECT | 971 | 465 | 506 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| SELECT | SELECT_ORGANIZE | 1406 | 148 | 1258 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| SEND | COMMUNICATE | 1873 | 606 | 1267 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| SET | TRANSFORM | 746 | 373 | 373 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| SHARE | COMMUNICATE | 280 | 121 | 159 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| SHOW | INSPECT | 1773 | 753 | 1020 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| SORT | SELECT_ORGANIZE | 276 | 115 | 161 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| START | CONTROL | 297 | 137 | 160 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| STOP | CONTROL | 298 | 139 | 159 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| SUBMIT | EXTERNAL_TRANSACTION | 0 | 0 | 0 | REGISTRY_GAP | No general external-transaction submit capability or verified contract is registered; retain as a policy-sensitive semantic gap. |
| SUMMARIZE | PROVIDE | 604 | 302 | 302 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| SWITCH | TRANSFORM | 519 | 242 | 277 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| TYPE | CONTENT_EDIT | 0 | 0 | 0 | DOWNSTREAM_TOOL_ONLY | Represent text entry as ENTER or WRITE using the destination and text slots. |
| UNINSTALL | LIFECYCLE | 294 | 138 | 156 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| UNMUTE | CONTROL | 195 | 90 | 105 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| UPLOAD | RESOURCE_TRANSFER | 1162 | 148 | 1014 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| VERIFY | INSPECT | 281 | 122 | 159 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
| WRITE | CONTENT_EDIT | 280 | 130 | 150 | SUPPORTED_BY_LANGUAGE_MODEL | None before audit |
