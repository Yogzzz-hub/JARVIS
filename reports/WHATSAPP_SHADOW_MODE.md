# WhatsApp personal brain shadow mode

Observed 2026-10-05 IST. Counts come from the local encrypted style store. No chat bodies or full contact IDs are in this report.

| Measure | Result |
|---|---:|
| LIVE LISTENER | Python and bridge ports open |
| SHADOW DRAFT MODE | 3 contacts SUGGEST_ONLY; no generated auto-reply |
| CONTACTS | 30 |
| DRAFT_READY | 0 |
| VERIFIED_STYLE_BUILDING | 3 |
| AUTO_REPLY_CANDIDATES | 0 |
| VERIFIED MANUAL OWNER | 0 |
| VERIFIED LEGACY OWNER | 106 |
| VERIFIED EDITED DRAFTS | 0 |
| APPROVED AI DRAFTS | 0 |
| TRAIN EXAMPLES | 67 |
| VERIFIED HOLDOUT | 10 |
| VERIFIED REPLAY GENERATED | 9 |
| VERIFIED REPLAY CLARIFICATION DRAFT | 1 |
| VERIFIED REPLAY NEEDS OWNER CONTEXT | 0 |
| VERIFIED REPLAY MODEL UNAVAILABLE | 0 |
| LEGACY HOLDOUT | 0 |
| DRAFTS GENERATED | 0 |
| DRAFTS ACCEPTED | 0 |
| DRAFTS EDITED | 0 |
| DRAFTS REJECTED | 0 |
| BAD_STYLE | 0 |
| WRONG_CONTEXT | 0 |
| DRAFT ACCEPTANCE RATE | N/A |
| AVERAGE EDIT RATIO | N/A |
| LANGUAGE MATCH | 0.222 |
| LENGTH MATCH | 0.666 |
| EMOJI MATCH | 1.0 |
| MODALITY MATCH | 1.0 |
| REPLY/NO-REPLY DECISION | N/A (replied pairs only) |
| FORMALITY MATCH | N/A (not separately scored) |
| SEMANTIC APPROPRIATENESS | 1.0 |
| STYLE SCORE | 1.0 |
| STICKERS INDEXED | 0 |
| MEDIAN DRAFT GENERATION LATENCY | 6213.5 ms |
| P95 DRAFT GENERATION LATENCY | 12225.8 ms |
| PYTHON TESTS | 79/79 focused cases passed |
| NODE TESTS | 24/24 passed |

The 9 generated verified holdout answers are **diagnostic samples**, not a reliable quality estimate. 1 case(s) could use a previously verified same-contact owner clarification as a review-only draft; 0 case(s) had no such evidence and were held. 0 case(s) had no model output. Clarifications do not count as correct factual answers. The owner identified a wrong-direction update draft; that original case remains unrated and is not counted as a successful reply. Owner side-by-side ratings remain pending. The style proxy is not calibrated and must not be treated as approval. Approved legacy rows support draft style but the generated auto-reply gate still requires stronger verified manual/edited evidence and a much larger verified holdout.

The latency probe generated 8 of 9 drafts using generic local prompts before the three owner reviews. It excludes live WhatsApp delivery and does not measure a fresh incoming event. Live shadow drafts will be counted when a new direct message arrives for one of the three configured contacts. General sending and generated auto-reply remain disabled; the prior one-shot outgoing delivery still awaits receiving-phone confirmation.

SQLite integrity: `ok`. The private review sheets and side-by-side case stay in ignored local data.
