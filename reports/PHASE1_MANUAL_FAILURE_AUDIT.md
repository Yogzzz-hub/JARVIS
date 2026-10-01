# Phase 1 manual failure audit - status, task control and runtime introspection

Scope: the eight requests that failed in manual dashboard testing. Each was traced through
normalize → SmartRouter/JDE → capability retrieval → slot/constraint extraction → planner → ToolRegistry /
CommandService → CommandResult → ResponseFormatter. No new architecture was added: the fixes repair the existing
router, CommandService, TaskManager, DAGScheduler and formatter paths.

## Root causes

| # | Request | Path before | Root cause |
|---|---------|-------------|------------|
| 1 | "Tell me whether JARVIS is healthy, but don't start or restart anything." | no exact rule → complexity gate (two clauses) → LLM planner → 1-node graph → `CommandService._graph_message` | (a) No deterministic route for questions about JARVIS itself. (b) `_graph_message` only used `ResponseFormatter.format_verified_tool`; a tool without a template returned "Task completed…", which was dropped, so the reply fell back to the scheduler's step count "Completed all 1 steps successfully." - the health result was discarded. |
| 2 | "What parts of JARVIS are unavailable right now, and which ones can still work?" | no rule → LANE_2 chat model | No capability for component availability; runtime state was answered by the general chat model, which cannot know it (and offered web search). |
| 3 | "Stop the current task but keep listening for my next command." | capability retrieval: "stop" + "current" → `pc_quick_action` (media pause) → missing slot → "Please provide required details" | Stop/cancel of a task had no priority over keyword retrieval; "task" was not a recognised object. ("stop the task" alone even matched dictation pause.) |
| 4 | "Show me current CPU, memory and GPU usage without opening Task Manager." | complexity gate → planner → 1-node graph | Same as 1(b): live metrics were computed and discarded by the step-count summary. `system_info` (static hardware) is the only matching tool, and it has no live CPU/GPU load. |
| 5 | "Tell me what command is currently executing and how far it has actually reached." | question guard → LANE_2 chat | No runtime task-status capability. The chat model read the action log context and repeated the previous action ("pc quick action (action pause)" - the real, mis-routed result of #3) as if it were running, then offered web search. TaskManager had no notion of steps, so no real progress existed to report. |
| 6 | "Cancel only the background job, not the foreground task I'm waiting for." | no rule → LLM classification / planner → graph with `install_software` + `empty_recycle_bin` → policy confirmation | (a) No foreground/background model in TaskManager; the existing cancel cancelled every task. (b) **No check that a model-chosen risky tool is related to the request**: the planner's hallucinated install / recycle-bin steps went straight to the confirmation prompt. |
| 7 | "What failed during the previous command, and what successfully completed?" | question guard → chat model with action-log context | No reader of the previous CommandResult / plan node results. The action log lists raw tool ids (`pc_quick_action`, `dag_scheduler`), which the model echoed; the answer was also repeated because the same text came from two summaries. |
| 8 | "Give me current JARVIS status without waking any heavy AI models." | "status" → `system_diagnostics` (fast, deterministic) | Worked. Preserved - it is now also reached by the introspection router, before any model. |

Cross-cutting: negative constraints ("don't start or restart", "without opening Task Manager", "without waking…")
were visible to keyword retrieval and to the negation guard; the negated verbs could become the action.

## Fixes (general mechanisms, no sentence-specific rules)

1. **Introspection / control routing before retrieval, planner and any model** - `jarvis/core/router/introspection.py`,
   called first in `SmartRouter.route`. Intents: `system_diagnostics` (health), `jarvis_availability`,
   `resource_usage`, `task_status` (incl. stuck), `previous_outcome`, `cancel_task` (scope foreground / background,
   `keep_listening`). Classification is by feature (cancel verb + task object, JARVIS subject + health/status words,
   resource nouns + usage cue, previous/last + task noun + outcome words …), not by sentence.
   - Negative constraints are extracted first and removed from the text used for intent detection; the negated verbs
     are passed as `constraints` and can never become the action.
   - "How do I cancel a task?" style questions are left to the knowledge/chat flow (no execution).
   - Media/meeting/alarm objects ("stop the music", "cancel my meeting") are not task control.
2. **Runtime-state handlers** - `jarvis/core/commands/introspection.py`, dispatched in `CommandService` (read-only,
   no model/web): live psutil CPU/RAM + `nvidia-smi` GPU, component availability grouped from the existing health
   checks, running tasks with real step progress, the previous command's per-step outcome, scoped cancellation.
3. **Task model** - `Task.background`, `Task.intent`, `Task.steps`, `Task.steps_total`, `TaskManager.active_tasks()`.
   The DAG scheduler reports each finished step (`on_step`), so progress is only ever what really finished.
   Cancellation targets foreground tasks by default and background jobs only when named; the voice listener is
   never touched. The CONTROL lane ("stop", "cancel") now also leaves background jobs alone.
4. **Unrelated risky tools are blocked** - `CommandService._unanchored_risky`: a DESTRUCTIVE / PRIVILEGED /
   EXTERNAL_EFFECT or package tool chosen by a model or fuzzy match (single tool or planner graph) must be named in
   the request (tool name or tag words); otherwise JARVIS does nothing and asks, instead of proposing a confirmation.
5. **Structured results survive** - `_graph_message` falls back to the node output's `summary` / `spoken_summary` /
   `message` / `answer` before the step count; the health summary now reads "JARVIS is healthy. N/M checks passed…".
6. **One command → one final response** - `_finalize` returns the existing result when a task was already finalized;
   UI and speech both come from that single `CommandResult`.
7. **Readable step names** - action log / outcomes use human names ("media / PC quick action", "plan") instead of
   tool ids.

## Before → after routes

| Request | Before | After |
|---------|--------|-------|
| 1 health, don't restart | planner → "Completed all 1 steps successfully." | `system_diagnostics` → "JARVIS is healthy. N/M checks passed…" (constraints: start, restart) |
| 2 unavailable parts | chat model, suggests web search | `jarvis_availability` → "Available: … Unavailable: … Working with limits: …" |
| 3 stop task, keep listening | `pc_quick_action` → "Please provide required details" | `cancel_task` scope=foreground → "No foreground task is currently running…" / "Cancelled …. I'm still listening." |
| 4 CPU/RAM/GPU | planner → "Completed all 1 steps successfully." | `resource_usage` → "CPU 27%, RAM 0.6 of 16 GB (4%), GPU …" |
| 5 current command + progress | chat model, invented "pc quick action" | `task_status` → real running tasks with "k of n steps finished", or "No foreground task is currently running." |
| 6 cancel background only | planner → confirm install_software + empty_recycle_bin | `cancel_task` scope=background → only background jobs cancelled; foreground keeps running |
| 7 previous command outcome | chat model, raw tool ids, duplicated | `previous_outcome` → "The previous command, "…", failed. Completed: … Failed: … (reason). Skipped: … (an earlier step failed)." |
| 8 status without heavy models | `system_diagnostics` (fast) | unchanged, now also first-routed |

## Tests

`jarvis/tests/test_phase1_introspection.py`: the 8 original sentences, 10-12 unseen paraphrases for each intent
(health, availability, resources, task status, stuck, previous outcome, cancel foreground, cancel background), the
adversarial cases (knowledge question, "don't install/delete anything", media/meeting cancels, "stop" alone),
constraint survival, and end-to-end runs through the real CommandService with a fake model that records calls:
0 model calls, 0 web searches, real CPU/RAM values, scoped cancellation of real running tasks, per-step previous
outcome, blocked unrelated risky tools, and a single final response per command.
