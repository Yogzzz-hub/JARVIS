# Blind-12: first run and development progress

Blind-12 (1100 cases, 22 phases x 50) was written by independent generator sessions that never saw JARVIS code or earlier sets, checked
for novelty against every phrase in the repo's tests (0 exact, 0 near copies), locked (sha256 `69e4c803...`) at candidate commit
`e2c2ff2` and run once (run A router diagnostic, run B command service end to end, local model not installed -> DEPENDENCY_UNAVAILABLE).

| | First run (unseen) | After development on its failures (now dev data) |
|---|---:|---:|
| Run B strict exact | **32.5%** | 39.0% |
| Run A exact (router only) | 31.9% | 38.5% |
| Critical wrong actions (C3/C4, acted and not exact) | **34** | 9 |
| Cases that fell through to the unavailable model | 317 (208 router-wrong, 71 correct escalation, 38 model required) | 267 (159 / 71 / 37) |

By category (run B, first run -> after): normal 45% -> 54%, paraphrase 16% -> 26%, noisy 41% -> 50%, implicit 6% -> 8%,
context 18% -> 20%, negation/correction 35% -> 36%, ambiguous 52% -> 56%, must-not-act 49% -> 67%, edge 35% -> 36%.
By outcome: action 28% -> 33%, refuse 25% -> 55%, control 30% -> 48%, clarify 53% -> 56%, chat 70% -> 70%.

## What this says

* The 95% target (and >90% on unseen data) is **not met** and is not reachable by the deterministic router alone: even plain, direct
  requests ("normal") are at 54% on unseen wording, and implicit / context-dependent / planning sentences are meant for the local model
  that is not installed here. The first-run figure (32.5%) is the honest generalisation measurement; the second column is development data.
* Blind-11 was at ~70% (router-only tool level) after being trained on; on a fresh set the same router got 32% strict. That gap is the
  overfitting the earlier rounds produced; this round replaced sentence-level fixes with families (below) and tests with new wordings.
* Some failures are harness or product-policy artifacts, listed in docs/BLIND12_FAILURES.md: `wifi_status` is an alias of `network_info`
  in the runtime registry but not in the benchmark's, "mute" is executed as volume read + set 0, lock / sleep ask for confirmation.

## Families fixed from the first run (each with tests on new wordings, not Blind-12 sentences)

Refusals: other people's devices, accounts and private data (also with possessives and "off her phone"), impersonation, abusive or
untraceable messages, tracking a private person, a caller asking for a code, secrets posted publicly, someone else's Wi-Fi password,
drive wipes said as "formats", piracy and wipes with misspelt words. Safe look-alikes are tested (family numbers, birthdays, own history).
Actions: delete synonyms (bin / chuck / toss / throw away), vague delete targets ask which, one message to several people, "fire X off to",
copy / move "X from folder A into folder B", auto-reply grants for a named person, broadcast with a time window, "forward that to everyone"
with nothing to forward asks, shortcut cancel, settings sections, dark / light mode, uninstall phrasings, news / headlines, bookmarks,
zoom, private window, editing (stop dictating, take that back, drop the last N words, copy what is selected), taskbar / monitor / call
speaker, number-word typos, reasons after a command ("..., I want ..."), leading reasons ("I'm stepping out, ..."), Tanglish openers and
settings. Every rewrite layer has guards for scheduled, compound, content, file-like and question forms, and was checked with a with/without
differential over all 46k phrases in the repo's tests.

## Regression (real repo dir, model off)

Phase-500: 106 -> 57 failures; AGI-520 dev 498/520, holdout 385/520 (was 382); phase suites 25 -> 14 failures, blind sets unchanged or better;
pytest: 64 failures vs 66 at the merge commit (none new; two modules need scikit-learn / torch which are not installed). The context suite
loses 4 turns to an upstream change that answers "search for ..." through grounded chat instead of `search_web` (not touched here).

## Next

Blind-12 is development data from now on; the next unseen benchmark is Blind-13. To get near 90-95% the local model must be installed so the
implicit, context and planning cases are answered by it, and the remaining router-wrong families (docs/BLIND12_MODEL_OFF_DEV_R1.md) continue
to be generalised rather than patched.
