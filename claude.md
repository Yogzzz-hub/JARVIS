JARVIS EDGE
PHASE 1 — ULTRA-LOW-LATENCY CORE ENGINE

ROLE
====

You are the lead systems architect and performance engineer implementing
Phase 1 of JARVIS EDGE.

Read and obey the existing PROJECT CONSTITUTION / PROMPT 0 before doing
anything.

Build ONLY Phase 1.

Do not implement:
- Ollama
- any LLM
- Whisper
- wake word
- TTS
- embeddings
- semantic search
- Gmail
- Calendar
- browser automation
- vision
- phone app
- planner

Those belong to later phases.

This phase must create an extremely fast, lightweight and reliable foundation
that every later Jarvis subsystem can use without architectural rewrites.


==================================================
PRIMARY ENGINEERING TARGET
==================================================

JARVIS must ultimately feel instantaneous for deterministic commands.

Examples:

"open chrome"
"open calculator"
"volume 30"
"show desktop files"

Phase 1 therefore MUST be designed around this rule:

THE HOT PATH MUST NEVER WAIT FOR NON-ESSENTIAL WORK.

The following MUST NOT block command execution:

- SQLite telemetry writes
- log-file writes
- metrics persistence
- non-critical event subscribers
- filesystem indexing
- diagnostic collection
- background cleanup
- model initialization
- expensive process scanning

The critical path should approximately be:

request received
    ↓
validate boundary
    ↓
resolve command
    ↓
registry lookup
    ↓
invoke native tool
    ↓
FIRST ACTION STARTED

Persistence, logging and analytics should normally happen asynchronously.

Verification happens after the action starts and controls whether SUCCESS
may be reported.

Optimize separately for:

1. time-to-first-action
2. verification time
3. total completion time

Never combine these into one misleading latency number.


==================================================
TARGET HARDWARE
==================================================

Windows 11
16 GB RAM
NVIDIA RTX 3050

Phase 1 uses NO GPU.

Target idle RAM:
prefer < 100 MB
hard acceptance ceiling < 150 MB

Do not optimize for a web server with thousands of users.

This is primarily a single-user local real-time agent.

Prefer:

low latency
low RAM
low CPU
predictable behavior
simple architecture

over:

distributed-system complexity
multiple workers
unnecessary abstractions


==================================================
RUNTIME ARCHITECTURE
==================================================

Use:

Python 3.12
FastAPI
Uvicorn
asyncio
Pydantic v2
SQLite
psutil
mss
pycaw
standard Python logging
pytest
pytest-asyncio

Windows event loop:

Use the normal asyncio Windows Proactor event loop.

DO NOT attempt to install or force uvloop on Windows.

Uvicorn:

workers = 1
loop = asyncio

Use httptools when available.

Preferred:

http = httptools

fallback:

http = h11

For WebSockets prefer the current Uvicorn Sans-I/O WebSocket implementation:

ws = websockets-sansio

Keep this configurable because later benchmarks may show wsproto performs
better on the actual target machine.

Disable WebSocket per-message compression by default:

ws_per_message_deflate = false

Reason:
later voice frames will be frequent and compression can add unnecessary CPU
and latency.

Use bounded queues.

Never create an unbounded event/message queue.

Disable Uvicorn access logging in normal production mode.

Development mode may enable it.


==================================================
CRITICAL DESIGN RULE
==================================================

DO NOT architect the application as:

HTTP endpoint
 -> event bus
 -> subscriber
 -> database
 -> executor
 -> tool

That adds avoidable latency and hidden dependencies.

Instead use:

Gateway
   ↓
CommandService
   ↓
ToolRegistry
   ↓
ExecutionEngine
   ↓
Tool

DIRECT Python calls perform critical execution.

The EventBus is OBSERVABILITY and coordination infrastructure.

It must not be required to perform a simple deterministic command.

Example:

POST /command
      ↓
CommandService.handle()
      ↓
ToolRegistry.get()
      ↓
tool.run()

Events such as:

request.received
tool.started
tool.finished

are emitted alongside the direct path.

A slow metrics subscriber must never delay open_app().


==================================================
REPOSITORY STRUCTURE
==================================================

Create:

jarvis/
│
├── apps/
│   └── mobile/
│
├── config/
│   └── jarvis.toml
│
├── core/
│   ├── gateway/
│   ├── commands/
│   ├── events/
│   ├── tasks/
│   ├── executor/
│   ├── verifier/
│   ├── response/
│   ├── metrics/
│   ├── persistence/
│   ├── router/
│   ├── context/
│   ├── planner/
│   ├── audio/
│   ├── stt/
│   └── tts/
│
├── tools/
│   ├── base.py
│   ├── registry.py
│   └── system/
│
├── memory/
├── models/
├── security/
├── db/
│   └── migrations/
├── logs/
├── scripts/
├── tests/
└── docs/

Create __init__.py where appropriate.

Future-phase directories should contain only clean interfaces/stubs.

Do not implement future functionality.


==================================================
1. CONFIGURATION
==================================================

Create:

config/jarvis.toml

Sections:

[server]
host = "127.0.0.1"
port = 8765
workers = 1
http_backend = "httptools"
ws_backend = "websockets-sansio"
ws_compression = false
access_log = false

[performance]
event_queue_size = 1024
persistence_queue_size = 4096
metric_queue_size = 4096
verify_poll_ms = 50
verify_timeout_ms = 3000

[database]
journal_mode = "WAL"
synchronous = "NORMAL"
busy_timeout_ms = 3000

[paths]
db = "db/jarvis.db"
logs = "logs/jarvis.jsonl"
models = "models"

[features]
router_ai = false
planner = false
voice = false
tts = false
phone = false
google = false
browser = false
vision = false

[models]
fast = ""
planner = ""
vision = ""

Load configuration ONCE at startup.

Do not repeatedly parse TOML during requests.

Expose immutable config objects after startup.


==================================================
2. HIGH-RESOLUTION LATENCY CLOCK
==================================================

Create:

core/metrics/clock.py

Use:

time.perf_counter_ns()

for duration measurement.

Do NOT use:

datetime.now()

for latency calculations.

Wall-clock timestamps may still be stored for audit/history.

Every Task should capture:

received_ns
dispatch_started_ns
tool_started_ns
tool_returned_ns
verification_started_ns
verification_finished_ns
response_ready_ns

Derived metrics:

gateway_parse_ms
command_resolution_ms
registry_lookup_ms
dispatch_ms
first_action_ms
tool_return_ms
verification_ms
total_ms

first_action_ms is especially important.

Definition:

time from request accepted by Jarvis
until the actual tool invocation begins.

Do NOT include app startup verification inside first_action_ms.


==================================================
3. COMMAND SERVICE
==================================================

Create:

core/commands/service.py

This becomes the permanent entry point for commands.

Interface approximately:

async handle(request: CommandRequest) -> CommandResult

Phase-1 temporary deterministic grammar:

open <app>
volume <0-100>
list <path>
screenshot
time
system info

The real intelligent router arrives in Phase 2.

CommandService should DIRECTLY invoke ToolRegistry / ExecutionEngine.

It must NOT require:

EventBus round trip
SQLite round trip
log flush
metrics flush

before tool execution.


==================================================
4. TOOL CONTRACT
==================================================

Create strict Pydantic v2 contracts.

RiskLevel:

READ_ONLY
REVERSIBLE
EXTERNAL_EFFECT
DESTRUCTIVE
PRIVILEGED

ExecutionMethod:

NATIVE
API
CLI
UIA
DOM
VISION
COORDINATES

ToolDefinition:

name
description
input_model
output_model
read_only
requires_confirmation
risk
timeout_s
version
tags
execution_method

ToolResult:

success
data
error
evidence
duration_ms
tool_name
method_used

VerificationResult:

verified
confidence
evidence
error
duration_ms

Reject unknown fields where appropriate:

extra = "forbid"

Generate JSON schema once and CACHE it.

Do not regenerate schemas on every /tools request.

Do not use @validate_call on every internal function.

Validation belongs primarily at:

external boundaries
tool arguments
tool outputs
planner contracts later

Avoid repeatedly validating already trusted internal objects.


==================================================
5. TOOL REGISTRY
==================================================

Create:

tools/registry.py

Capabilities:

register()
get()
contains()
list()
search_by_tag()
export_schema()
discover()

Requirements:

O(1) name lookup using dictionary.

Tool discovery occurs ONCE during startup.

Schema export occurs ONCE after registry finalization and is cached.

Reject:

duplicate names
invalid contracts
missing definitions

Registry reads after startup should require no disk access.

Measure registry lookup latency in benchmarks.


==================================================
6. APP RESOLVER — IMPORTANT LATENCY FEATURE
==================================================

DO NOT scan the Start Menu every time the user says "open chrome".

Create:

tools/system/app_resolver.py

Build an application index during startup/background initialization.

Resolution sources:

1. built-in aliases
2. exact cached executable paths
3. Windows App Paths registry where practical
4. cached Start Menu shortcuts
5. shutil.which()
6. additional user-defined aliases

Initial aliases:

chrome
edge
notepad
calculator
calc
vscode
vs code
explorer
file explorer
terminal
cmd
powershell
settings

Store resolved results in RAM:

normalized app name
 -> launch target

Cache successful resolutions.

Never repeatedly search disk paths for common apps.

If resolver cache needs rebuilding, do it in background.

The command execution hot path should become approximately:

normalize app name
dictionary lookup
native launch


==================================================
7. SYSTEM TOOLS
==================================================

Implement:

open_app(name)

close_app(name) interface may be stubbed for Phase 2 if not needed.

list_directory(path, limit)

get_time()

system_info()

volume_get()

volume_set(percent)

take_screenshot(path?)

For launching executables prefer direct process/native calls.

Do NOT invoke:

cmd.exe /c ...

when a direct API exists.

Do NOT use:

shell=True

For associated files/directories, Windows os.startfile() is acceptable.

For executables use direct subprocess/native launching where appropriate.

Return from the launch primitive quickly.

Verification happens separately.


==================================================
8. VERIFICATION ARCHITECTURE
==================================================

Very important:

DO NOT delay the initial tool action while performing verification.

Flow:

launch requested
     ↓
tool invocation begins          ← first_action timestamp
     ↓
launch call returns
     ↓
verification begins
     ↓
verification evidence found
     ↓
SUCCESS

open_app verification can use:

psutil.process_iter(attrs=...)
known process aliases
process existence
process creation changes where useful

Cache appropriate process metadata.

Do not repeatedly perform expensive full process inspection with unnecessary
attributes.

Verifier polls asynchronously with a short configurable interval.

Do NOT busy-loop.

If verification fails:

return an honest failure or uncertain result.

Never report success solely because:

os.startfile()
subprocess.Popen()

did not throw an exception.


==================================================
9. EVENT BUS
==================================================

Create an in-process asyncio pub/sub system.

Events:

request.received
task.state_changed
tool.started
tool.finished
verification.finished
response.ready
metrics.recorded

IMPORTANT:

EventBus is not the command execution mechanism.

Non-critical subscribers must be isolated.

One slow subscriber must not block other subscribers.

Use bounded queues.

Define behavior when a non-critical queue is full:

- aggregate metrics
- drop diagnostic-only events with a counter
- NEVER crash execution

Critical security/audit events introduced in later phases will use stronger
persistence rules.


==================================================
10. NON-BLOCKING PERSISTENCE
==================================================

This is a major performance requirement.

Do NOT perform an SQLite COMMIT in the command hot path for telemetry.

Create:

core/persistence/writer.py

Use:

one dedicated persistence worker
+
bounded queue
+
batched writes

Standard sqlite3 is sufficient.

Database configuration:

PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=3000;

Where appropriate also use:

PRAGMA foreign_keys=ON;

The worker should combine multiple telemetry inserts into short transactions.

Tables:

requests
task_events
tool_runs
metrics
kv_settings

Future migrations must be supported.

Important:

command execution starts independently of telemetry persistence.

Add graceful shutdown:

drain queue
commit remaining records
checkpoint if appropriate
close connection


==================================================
11. LOGGING WITHOUT HOT-PATH DISK I/O
==================================================

Use Python:

logging.handlers.QueueHandler
logging.handlers.QueueListener

Request-handling code places log records into memory queue.

A separate listener performs file writes.

Use rotating JSONL log:

logs/jarvis.jsonl

Fields:

timestamp
level
request_id
component
event
duration_ms
message

Never perform a synchronous file flush for every ordinary command.

Debug mode may be more verbose.

Normal mode should remain lightweight.


==================================================
12. TASK STATE MACHINE
==================================================

States:

IDLE
LISTENING
UNDERSTANDING
ACKNOWLEDGED
PLANNING
EXECUTING
VERIFYING
SUCCESS
FAILED
RESPONDING
CANCELLED

Explicit transition table.

Illegal transitions raise an internal error.

Task:

request_id
source
raw_text
state
created_at
high-resolution state timestamps
result
cancellation token

TaskManager:

create()
transition()
get()
recent()
cancel()

Active tasks remain in RAM.

Persistence is asynchronous.


==================================================
13. GATEWAY
==================================================

FastAPI endpoints:

GET /health
GET /tools
POST /command
GET /tasks/{id}

WebSocket:

/ws

Control message types:

command
task_state
task_result
error
ping
pong

Use Pydantic models at external boundaries.

Keep messages compact.

No unnecessary nesting.

Return typed response models.

Do not perform expensive encoding transformations manually.

Internal components must NOT call REST endpoints to communicate with one
another.

They call Python services directly.


==================================================
14. WEBSOCKET LATENCY PREPARATION
==================================================

The phone arrives in Phase 8, but prepare the transport correctly now.

WebSocket requirements:

persistent connection
small bounded queues
compression disabled
binary frame support reserved
low-copy design
request_id on every command
protocol version field

Do not reconnect for every command.

Later audio will travel across the existing persistent connection.

Do not implement audio now.


==================================================
15. NETWORK SETTINGS
==================================================

Phase 1 binds only:

127.0.0.1

Do NOT expose LAN access yet.

LAN pairing/authentication comes later.

Do not manually disable TCP_NODELAY.

Use standard asyncio TCP behavior.

No unnecessary polling between gateway and engine.

Everything inside the PC should be event-driven.


==================================================
16. SYSTEM INFO
==================================================

system_info() returns:

OS
Python
CPU
RAM
GPU name
GPU VRAM

Query NVIDIA information using nvidia-smi if available.

DO NOT run nvidia-smi repeatedly.

Cache static hardware data at startup.

Only dynamic values such as current RAM use may be refreshed when requested.


==================================================
17. RESPONSE ENGINE — TEXT ONLY
==================================================

Phase 1 has no TTS.

Create a clean interface so Phase 7 can attach TTS later.

ResponseEngine receives verified ToolResult / GraphResult.

For Phase 1 return concise text:

"Chrome is open."

"Volume set to 30%."

"Screenshot saved."

Never generate these with an LLM.


==================================================
18. STARTUP SEQUENCE
==================================================

Optimize startup.

Startup order:

load config
    ↓
initialize high-resolution metrics
    ↓
open persistence worker
    ↓
run migrations
    ↓
initialize ToolRegistry
    ↓
build/cached app resolver
    ↓
cache tool JSON schemas
    ↓
start log listener
    ↓
start gateway
    ↓
ready

NO MODEL LOADING.

Emit:

JARVIS_READY

with:

startup_ms
RAM_MB
tool_count
database_status


==================================================
19. GRACEFUL SHUTDOWN
==================================================

On Ctrl+C/service shutdown:

stop accepting requests
cancel active safe tasks
flush event queue
flush persistence queue
flush log queue
commit DB
close DB
close gateway

Shutdown must not leave SQLite corrupted.


==================================================
20. BENCHMARKING — MANDATORY
==================================================

Create:

scripts/bench_core.py

Benchmark at least 1000 iterations where applicable.

Report:

p50
p95
p99
mean
max

Measure independently:

Pydantic command validation
registry lookup
direct command resolution
event emission
persistence enqueue
GET /health round-trip
WebSocket ping round-trip
text-command dispatch
first_action_ms

For app-launch tests, separate:

JARVIS dispatch latency

from:

Windows application startup latency.

Do not claim Windows app startup time as Jarvis processing time.


==================================================
PERFORMANCE TARGETS
==================================================

These are engineering targets on the target PC, not fake guarantees.

Registry lookup:

p95 < 0.25 ms

Phase-1 deterministic command resolution:

p95 < 2 ms

Persistence enqueue:

p95 < 0.5 ms

Non-blocking event publication:

p95 < 0.5 ms

Request accepted -> tool invocation start:

target p95 < 20 ms locally

WebSocket command overhead on localhost:

measure and minimize;
do not set an artificial sleep anywhere.

Idle CPU:

approximately 0% when unused,
excluding OS measurement noise.

Idle RAM:

prefer < 100 MB,
must remain < 150 MB.

NO polling loops that wake constantly.

Use events/awaitables/timers.


==================================================
ACCURACY / RELIABILITY TARGETS
==================================================

Accuracy is more important than saving a few microseconds.

Never trade validation/verification for fake speed.

Requirements:

100% valid tool schema enforcement

100% duplicate tool rejection

100% illegal task-state-transition rejection

deterministic app alias resolution

verified result before SUCCESS

no raw shell execution

no shell=True

no arbitrary PowerShell

no guessed paths

no silent exception swallowing


==================================================
21. TESTS
==================================================

Create comprehensive tests for:

configuration

ToolDefinition

ToolResult

VerificationResult

registry duplicate detection

registry discovery

cached schema generation

application alias resolution

application-cache reuse

state-machine legal transitions

state-machine illegal transitions

EventBus subscriber isolation

EventBus bounded queues

persistence worker

batched SQLite writes

fresh DB migration

WAL configuration

logging queue

gateway /health

gateway /tools

gateway /command

WebSocket ping/pong

WebSocket command round trip

open_app mocked launcher

verification success

verification failure

cancellation

graceful shutdown

No test should require:

Ollama
GPU
internet
Google
phone


==================================================
22. FAILURE HANDLING
==================================================

No broad:

except Exception:
    pass

Every failure must either:

return structured failure

or

be logged with request_id.

Expected failures must not crash Jarvis.

Unexpected core failures should fail loudly in development.


==================================================
23. DEPENDENCIES
==================================================

Keep dependency count small.

Every dependency must:

be completely free
have an acceptable open-source license
be documented in docs/LICENSES.md

Before adding a new dependency:

state why Python stdlib/current dependency is insufficient.

Do not add:

Redis
PostgreSQL
Docker
Celery
RabbitMQ
Kafka
cloud databases
cloud APIs

for this local Phase-1 core.


==================================================
24. DOCUMENTATION
==================================================

Create:

docs/ARCHITECTURE.md
docs/PERFORMANCE.md
docs/PROGRESS.md
docs/LICENSES.md

ARCHITECTURE.md must include the hot path:

Gateway
 -> CommandService
 -> ToolRegistry
 -> ExecutionEngine
 -> Tool
 -> Verifier
 -> ResponseEngine

and side channels:

             ├── EventBus
             ├── Metrics queue
             ├── Persistence queue
             └── Logging queue

Make it visually clear that side channels do NOT block first action.


==================================================
25. REQUIRED COMMAND TEST
==================================================

This must work:

python -m jarvis

Then:

python -m jarvis.cli "open notepad"

Expected architecture:

CLI
 ↓
localhost gateway
 ↓
CommandService
 ↓
direct deterministic resolver
 ↓
ToolRegistry O(1)
 ↓
open_app
 ↓
native Windows launch
 ↓
first_action timestamp
 ↓
async verification
 ↓
SUCCESS
 ↓
"Notepad is open."

Telemetry/log persistence happens in parallel and must not determine
first-action latency.


==================================================
ACCEPTANCE CHECKLIST
==================================================

Do not declare Phase 1 complete until every item has evidence.

[ ] Service starts without any AI model loaded.

[ ] Idle RAM < 150 MB.

[ ] Idle CPU is effectively near zero.

[ ] Uvicorn runs one worker.

[ ] Windows asyncio configuration works correctly.

[ ] httptools is used when available and h11 fallback works.

[ ] WebSocket persistent connection works.

[ ] Compression is disabled for the control WebSocket.

[ ] Command hot path performs no required SQLite write before tool invocation.

[ ] Command hot path performs no synchronous file-log write.

[ ] EventBus subscriber delay cannot delay open_app.

[ ] Tool registry lookup is O(1).

[ ] Tool schemas are cached.

[ ] App resolution uses cached index rather than disk scan per command.

[ ] "open notepad" starts invocation with local first_action_ms target
    p95 < 20 ms, excluding Windows application startup.

[ ] Notepad SUCCESS is reported only after verifier evidence.

[ ] SQLite uses WAL.

[ ] SQLite synchronous mode is NORMAL.

[ ] Persistence is queued/batched.

[ ] Logging uses QueueHandler/QueueListener or equivalent non-blocking design.

[ ] perf_counter_ns is used for latency measurements.

[ ] p50/p95/p99 benchmark results exist.

[ ] GET /health works.

[ ] GET /tools works.

[ ] POST /command works.

[ ] WebSocket command round trip works.

[ ] graceful shutdown drains persistence/log queues.

[ ] all tests pass.

[ ] docs/PERFORMANCE.md contains actual benchmark numbers.

[ ] docs/PROGRESS.md contains PASS/FAIL evidence for every checklist item.


==================================================
FINAL INSTRUCTION
==================================================

Do not simply generate files and claim success.

Work in this order:

inspect repository
↓
brief implementation plan
↓
implement
↓
run tests
↓
fix failures
↓
run benchmarks
↓
inspect RAM/CPU
↓
manually test open notepad
↓
update documentation
↓
print acceptance checklist with actual evidence

If a latency target fails:

DO NOT hide it.

Profile it.

Identify exactly which component consumed the time.

Optimize that component.

Run the benchmark again.

Report before/after numbers.

Do NOT begin Phase 2.

STOP after Phase 1 is completely tested and documented.