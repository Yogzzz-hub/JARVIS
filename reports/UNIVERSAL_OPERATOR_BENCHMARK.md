# Universal Operator - Benchmark

Measured in the CI container (Linux, no display): routing is the real `SmartRouter` with no AI model; primitive numbers are JARVIS's own overhead on the in-memory desktop/browser/phone (resolution, chord parsing, verification bookkeeping). **Application latency on a real PC (window activation, UIA tree reads, Chrome DevTools, ADB) is not measured here** - it is part of the real-machine acceptance run.

Command: `python scripts/bench_operator.py`

## Routing latency (ms, warm router, 1 canonical wording per scenario)

| Slice | n | p50 | p95 | max |
|---|---:|---:|---:|---:|
| all scenarios | 598 | 2.795 | 8.584 | 194.042 |
| routes to operator tools | 350 | 2.082 | 4.691 | 10.971 |
| android | 58 | 3.274 | 5.668 | 12.931 |
| browser | 72 | 2.259 | 5.503 | 9.691 |
| clipboard | 38 | 2.794 | 4.536 | 8.852 |
| cross | 30 | 3.622 | 7.084 | 14.804 |
| desktop | 66 | 1.916 | 6.09 | 194.042 |
| files | 50 | 4.102 | 7.253 | 8.885 |
| ide | 45 | 2.721 | 4.122 | 9.534 |
| media | 38 | 1.651 | 7.332 | 11.478 |
| system | 36 | 4.474 | 9.434 | 11.334 |
| text | 61 | 1.924 | 4.145 | 5.826 |
| ui | 56 | 2.287 | 4.419 | 6.472 |
| workflow | 48 | 4.814 | 18.776 | 24.506 |

## Primitive overhead (ms, in-process, fake platform)

| Primitive | n | p50 | p95 | max |
|---|---:|---:|---:|---:|
| window.resolve (previous, family, app) over 27 windows | 300 | 0.805 | 1.071 | 5.564 |
| window.focus + verify | 300 | 0.2 | 0.285 | 0.694 |
| ui.resolve over 401 controls (name+role) | 300 | 6.479 | 10.811 | 22.981 |
| ui.resolve ordinal over 401 controls | 300 | 8.188 | 14.198 | 19.083 |
| text.edit delete 2 words (+read-back verify) | 300 | 0.044 | 0.081 | 0.229 |
| dictation.feed (one stable-prefix update) | 300 | 0.625 | 0.858 | 1.432 | per call = value / 12
| browser.open_result(3) (+URL verify) | 300 | 0.083 | 0.141 | 0.409 |
| media.seek_to (+state read-back) | 300 | 0.1 | 0.159 | 0.395 |

## Reading the numbers

* The fast path never calls a model, the planner or retrieval: a parsed operator command is a regex/typed parse plus one registered tool.
* Waits are on observed state (`Desktop.wait_until`: foreground hwnd, window state, clipboard sequence, page URL, prompt box value), not fixed sleeps; the fake platform answers instantly, so these numbers are the floor JARVIS adds, and real latency = this + the OS/app's own response.
* Live dictation work per stable-prefix update is microseconds; end-to-end typing latency is dominated by the recogniser's partial interval (200 ms) and stabilisation.
