# Browser workflow implementation and acceptance

Status: **EXPERIMENTAL / MORE_DEVELOPMENT_REQUIRED**. This is a bounded navigation implementation, not universal browser acceptance.

`BrowserProgram` is declarative owner data: explicit origins, exact completion signal, Next/Continue labels, step and time budgets. `BrowserWorkflow` observes the existing Playwright page, proposes one typed action, checks task scope/policy/freshness, enforces origin limits before redirects, acts, verifies changed state and checkpoints metadata. One lock owns each page. Resume requires the exact last verified page state and never replays a private URL or submitted action.

The workflow only automates ordinary navigation links. Authentication, CAPTCHA, graded assessment, ambiguous targets, buttons, JS handlers, forms and download controls pause. Unsupported actions cannot fall through into raw Python/JavaScript. The registered outer tool requires confirmation and uses the existing executor/ledger path. Per-step durable ActionLedger integration is not complete; checkpoints do not substitute for financial/submit duplicate protection, so those effects remain paused.

Browser snapshots mask credential values, use observation-specific UUIDs and bounded controls, and mark page text untrusted. State hashes cover all bounded controls rather than the first fifty. Fill examines the actual resolved input, not only its friendly label. Generic click requires consequential confirmation, pauses high-risk labels, and reports UNCERTAIN when dispatch produces no observed state change. A changed DOM is not proof of a business transaction.

Browser manager startup now recognizes its persistent context, tracks unique tab IDs and closes ephemeral browsers. Downloads reject empty files and hash in bounded chunks. No new browser driver or foreign agent runtime was introduced.

Initial automated acceptance: nine local real-Chromium fixture tests passed, including twelve successive Next/Continue transitions, duplicate-label pause, CAPTCHA/graded/payment pause, missing scope, stop, credential masking/fill refusal, injected instruction isolation and stale observation rejection. These are SYNTHETIC fixtures executed in a real browser. Added checks cover noop clicks and purchase controls; final results are recorded below.

Not accepted: arbitrary websites, iframe/shadow/virtualized controls, full upload/form/download workflows, vision fallback, universal language goal planning, real portal tasks, authentication challenges or external submissions. No 95% action or 90% universal task-success claim is made from the limited fixture set.
