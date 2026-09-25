# JARVIS review and rating

Review date: 2026-09-18. Baseline commit:
`454f79141d99af2ecea749b9ed487e0464531ac5`.

## Rating

**Overall engineering assessment: 6/10 after this enhancement pass.**
The starting working tree was approximately **4.5/10** for the requested real-world
deployment. These are judgment-based ratings, not measured acceptance percentages.

| Area | Rating / 10 | Evidence and limits |
| --- | ---: | --- |
| Architecture and modularity | 7 | Typed tools, policy, scheduler, router and subsystem boundaries exist. Runtime integration is incomplete. |
| Core command reliability | 7 | Regression coverage and live gateway smoke pass; unsupported capabilities now fail clearly. |
| Safety and verification | 6 | Cancellation and compound verification repaired; existing policy tests pass. Full end-to-end confirmation and recovery are not accepted. |
| Testability | 8 | 282 historical tests and 121 new regressions pass. Historical files remain deleted in the user's tree and are tested from an isolated copy. |
| Installation and diagnostics | 7 | Reusable setup, diagnostics, corrected dependencies and duplicate-start protection. Optional feature setup remains incomplete. |
| Daily voice assistant readiness | 3 | Microphone/speakers discovered; no accepted PTT/STT/wake/TTS runtime integration. |
| Generalized computer tasks | 4 | Application discovery improved; package installation, app closing and broad browser/UI workflows are not exposed end to end. |

## Review coverage

Inventoried and hashed all 278 first-party text/configuration files present at the
start of review and syntax-parsed all 237 Python files. Focused semantic review
covered runtime/configuration, gateway, command dispatch, routing, execution,
verification, policy, app resolution, search lifecycle and voice interfaces.
This is not a claim of line-by-line security certification of every subsystem.
Virtual environments, bundled runtimes, models, audio binaries and browser caches
were excluded from source review; they are not authored application code.

Checkpoint: `.runtime/review/before-review.zip`.
Inventory: `.runtime/review/inventory.json`.
Original Git status and commit are recorded alongside them. The Git repository
root is the parent Desktop directory; unrelated Desktop files were not edited.
Pre-existing deletions of tests, scripts and reports were preserved.

## Enhancements made

- Control requests now signal active tasks and remain admissible when both native
  execution slots are occupied. Correct task-state transitions prevent cancellation
  acknowledgements from raising an internal error.
- Compound actions validate inputs before dispatch, stop on execution/verification
  failure, and no longer fabricate successful verification.
- Planner execution uses the policy-aware executor and does not label a partial
  graph as full success. Current runtime configuration keeps the planner disabled.
- Missing capabilities produce a normal failed result instead of an unhandled
  registry lookup exception.
- Runtime honors disabled AI routing/planning, avoiding unintended model requests.
- Common punctuation, curly apostrophe negation, time questions, compound spoken
  numbers, volume phrases and Edge aliases route correctly. Malformed numbers
  are rejected rather than silently truncated.
- App Paths enumeration discovers executable registrations beyond the built-in
  aliases. Automatically discovered executables are restricted to installation
  roots; explicit user aliases remain available for other locations.
- Startup reserves an exclusive Windows socket before creating runtime resources.
- Browser-origin HTTP actions are rejected, consistent with the WebSocket boundary.
- Search connections, enrichment tasks, router clients and audio output are closed
  during normal runtime shutdown. TOML search arrays now validate correctly.
- Added dependency declarations, setup/diagnostics scripts, regression tests and
  a daily-use guide. CLI HTTP errors now include the server's explanation.

## Verification

- **403 tests passed**: 282 recovered release tests + 121 new regression tests.
  The new tests include 100 app-language variants; these are text routing tests,
  not 100 recorded speech tests.
- `pip check`: **No broken requirements found** after replacing incompatible
  PyYAML, RapidFuzz and lxml wheel installations with Python 3.12 Windows wheels.
- Live isolated HTTP service: health ready, 15 tools, database ready; time and
  system information succeed; cancellation with no active work succeeds; missing
  close-app capability and disabled planner return controlled failures; browser
  origin command returns HTTP 403; graceful shutdown completes.
- Observed isolated startup: approximately **2.22 seconds**, **74.34 MiB RSS**.
  This is one observation, not a p95/p99 benchmark or voice/action latency claim.
- Actual occupied-port launch refused before runtime startup. The existing service
  on port 8765 was preserved and must be restarted to use the edited code.
- Realtek microphone and speakers were discovered. Playwright Chromium is available;
  browser fixture, UI mock, vision fake-provider and Google fake-provider tests pass.
  This does not establish manual Windows/voice acceptance.

Evidence: `.runtime/review/all-results.xml`, `live-smoke.json`, `diagnostics.json`.
Repeat the full review suite with:

```powershell
.\.venv\Scripts\python.exe scripts/run_review_tests.py
```

Install test dependencies with `pip install -e ".[test]"` in this virtual environment
and Chromium with `python -m playwright install chromium` if needed. The historical
browser tests use the repository's dedicated browser profile and may update its
cache files. No normal Chrome profile is used.

## Remaining activation work

The provided master prompt's completion criteria are **not met**. Do not label this
deployment "REAL-WORLD ACTIVATION COMPLETE". Remaining work includes configuration
and runtime integration of production voice/STT/TTS and wake word, on-device
spoken acceptance, durable cross-command context and initial file indexing,
package search/install/verification and confirmations, safe app closing, browser
and UI capability registration, planner/model lifecycle, restart-recovery drills,
and actual performance benchmarks. Existing optional feature fields are typed as
`Literal[False]`, and model names as empty literals; enabling them requires an
integrated implementation rather than a flag edit. Ollama was unreachable during
diagnostics. Google remains disconnected; Android is optional and not activated.
