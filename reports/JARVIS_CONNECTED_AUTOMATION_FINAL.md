# Connected automation integration audit

Date: 2026-10-05. This is an evidence report for the existing JARVIS architecture, not a claim that every requested cross-domain scenario is live. No external message, email, calendar event, or file was sent or changed during this pass.

## Shared execution path

| Component | Status | Evidence and limit |
|---|---|---|
| Core orchestrator | PASS (local) | `Runtime` creates one `CommandService` and routes requests through the shared router, registry, executor, verifier, task manager and event bus. |
| NLP | PARTIAL | The shared router and Tanglish work exist; unseen cross-domain command accuracy was not remeasured here. |
| Capability registry | PASS (local) | The runtime explicitly registers native tools. Existing Gmail search/get/draft/confirmed-send, Calendar find/get/update/delete and Drive list/search/metadata/download/upload/folder tools are now registered through the same factory. The richer connectors acquire OAuth lazily at invocation. |
| Working context | PARTIAL | Shared working memory and reference resolver are wired; cross-domain reference accuracy has no new acceptance set. |
| DAG planner | PASS (local) | Existing `AdaptivePlanner` and `DAGScheduler` are wired once into `CommandService`; focused planner and scheduler tests passed. Live cross-domain plans remain unverified. |
| Policy | PASS (local) | Automated commands re-enter `CommandService`, including its route, confirmation and task-scope grant. Gmail send retains `requires_confirmation=True`. |
| Action ledger | PARTIAL | Existing ledger remains in the execution path. The prior WhatsApp one-shot outgoing ID is externally acknowledged and locally stored, but receiving-phone confirmation is still pending in the [acceptance tracker](../docs/WHATSAPP_FINAL_ACCEPTANCE.md). |

## Connected domains

| Domain | Status | Evidence and limit |
|---|---|---|
| WhatsApp | PARTIAL | Existing fresh Baileys bridge, gateway and SQLite inbox remain the transport. A current direct message is emitted as metadata-only `whatsapp.message_received` **after** SQLite persistence; read-only, history, own, group, placeholder and duplicate messages do not emit it. This new event path has local tests but no new phone-confirmed live test. |
| Gmail | AUTH_REQUIRED | Existing Gmail API client and tools are reused; search/get/draft/send are exposed through the shared registry. A read-only `in:inbox` probe stopped before fetching mail because `GMAIL_READ` is not granted. |
| Calendar | AUTH_REQUIRED | Existing list/create and find/get/update/delete tools are registered. Neither account currently has Calendar read/write scopes, so live behavior was not tested. |
| Drive | AUTH_REQUIRED | Existing list/search/metadata/download/upload/create-folder tools are registered through a lazy client. Neither account currently has Drive read scope, so live behavior was not tested. |
| Browser | PARTIAL | Existing browser tools are registered; no new real-page or cross-domain browser acceptance was run. |
| Computer | PARTIAL | Existing native/desktop tools remain registered; no new device action was run. |
| Files | PARTIAL | Existing file/search tools remain available; no new attachment-to-file live workflow was run. |
| Projects | PARTIAL | Existing discover/run/log/file tools remain available; untrusted project execution was not exercised. |
| Voice | INSUFFICIENT_EVIDENCE | Runtime audio startup exists; no live voice command was tested in this pass. |
| Phone | DEPENDENCY_UNAVAILABLE | Phone actions depend on a connected device; no device acceptance was run in this pass. |

## Automation and safety

| Component | Status | Evidence and limit |
|---|---|---|
| Automation engine | PARTIAL | Existing timed and condition triggers are retained. Owner-authenticated direct-chat WhatsApp event triggers now persist an exact chat ID, optional type, command, fire count, last result and durable message-ID claims. Claims are saved atomically before dispatch to avoid blind retries. The JSON claim list grows with event volume and needs a bounded store for long-running high-volume use. |
| Event bus | PASS (local) | Runtime subscribes the automation engine to the existing bounded `EventBus` and unsubscribes on shutdown. The event contains metadata only; sender text is never interpreted as an automation command. |
| Notifications | PARTIAL | Existing notice path remains; automated dispatch results are recorded, but live owner notification was not verified. |
| Owner remote control | PARTIAL | Existing WhatsApp owner isolation remains. This pass did not test a fresh remote command. |
| Cross-domain workflows | PARTIAL | Shared planner/scheduler can compose registered tools, but the named Gmail→Calendar, WhatsApp→browser/file and Drive paths lack complete live acceptance and, for Drive, runtime registration. |
| Prompt-injection isolation | PASS (local) | Event rules execute only saved owner-authored command text. External message bodies are excluded from event payloads and cannot be substituted into the command. Existing policy/security tests passed; live adversarial acceptance was not run. |
| Dashboard | PARTIAL | Workflows page now describes saved event-rule safety accurately and offers `LIST AUTOMATIONS`. It does not yet provide a full create/edit/inspect UI for typed event rules. |
| Startup/shutdown | PASS (local) | Runtime starts one automation subscription and stops/unsubscribes it before closing the event bus. No new full production restart was performed. |

## Verification

- Combined local planner, Google, runtime, policy, automation and WhatsApp regression selection after all changes: **225 passed**.
- Authorization failure was checked before lazy Drive service creation.
- Syntax compilation and `git diff --check`: passed.
- Desktop UI test modules: **2 skipped** because the optional Qt test dependency is unavailable here; the QML change has no rendered UI acceptance.
- Local event-claim microbenchmark: 100 events, p50 **2.088 ms**, p95 **2.633 ms**; includes JSON claim persistence on a temporary local file. This is not end-to-end messaging or action latency.
- Live read acceptance: existing WhatsApp exact-ID evidence is in the [prior tracker](../docs/WHATSAPP_FINAL_ACCEPTANCE.md); no fresh event automation acceptance. Gmail read returned `AUTHORIZATION_REQUIRED` before data access.
- Live write acceptance: **INSUFFICIENT_EVIDENCE** for this pass; no write was attempted. Prior WhatsApp outgoing receiving-phone confirmation remains pending.
- Automation acceptance: **PASS locally**, **INSUFFICIENT_EVIDENCE live**. Tests cover owner gate, exact-chat/type scope, history/group/own suppression, message-text isolation, restart replay, older-ID replay and event-bus dispatch.

## Dependencies and remaining work

The Google credential store lists two locally `READY` accounts, but neither has `GMAIL_READ`, `GMAIL_COMPOSE`, `CALENDAR_READ`, `CALENDAR_WRITE` or `DRIVE_APP_FILE_READ` scope. Google OAuth must be completed through the existing normal flow before live Google reads or writes can be verified. Cross-domain reference/plan tests are still needed. Email, Calendar, file, browser and project events are not yet published into the shared automation bus. Long-running event claims should move from an ever-growing JSON list to a durable indexed store. Live end-to-end event triggering, dashboard editing, cross-domain plans and notification delivery require separate controlled acceptance; none is marked complete here.
