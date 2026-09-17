# JARVIS EDGE — Phase 4: Adaptive Complex Planner & Verified DAG Scheduler

## 1. Overview & Core Philosophy

Phase 4 gives JARVIS EDGE the ability to interpret novel, multi-step user requests and compile them into safe, typed, executable task graphs (`TaskGraph`).

### The Cardinal Architectural Rule
> **THE LLM IS A PLANNER. IT IS NOT THE EXECUTOR.**
> - Never execute LLM-generated PowerShell, shell scripts, or arbitrary code.
> - Never dynamically call arbitrary tool names invented by the model.
> - Never trust self-reported success from an LLM.
> - Execution permissions, risk tiers, implementation methods, and verification logic belong strictly to the trusted `ToolRegistry` and system policy, never the model prompt.

---

## 2. The Planning Cascade

Planning is an expensive operation and must remain rare. Phase 2 handles single-intent and simple compound requests (< 3 actions) in microseconds without invoking a planner. When Lane 2 is triggered, JARVIS executes a staged deterministic cascade:

```
                  USER REQUEST (Lane 2)
                            │
                            ▼
               ┌───────────────────────────┐
               │ 1. PLAN TEMPLATE CACHE    │
               └─────────────┬─────────────┘
                             │
                     HIT ────┴──── MISS
                      │             │
                      ▼             ▼
             Instantiate Graph  ┌─────────────────────────────┐
                      │         │ 2. DETERMINISTIC DECOMPOSER │
                      │         └───────────┬─────────────────┘
                      │                     │
                      │             HIT ────┴──── MISS
                      │              │             │
                      │              ▼             ▼
                      │       Validated Graph ┌───────────────────────────┐
                      │              │        │ 3. CAPABILITY RETRIEVER   │
                      │              │        └───────────┬───────────────┘
                      │              │                    │
                      │              │                    ▼
                      │              │       Top-12 Compact Tool Schemas
                      │              │                    │
                      │              │                    ▼
                      │              │        ┌───────────────────────────┐
                      │              │        │ 4. COMPLEXITY ANALYZER    │
                      │              │        └───────────┬───────────────┘
                      │              │                    │
                      │              │        LOW/MED ────┴──── HIGH
                      │              │           │                │
                      │              │           ▼                ▼
                      │              │      Small Model       Full Model
                      │              │     (qwen3:1.7b)       (qwen3:4b)
                      │              │           │                │
                      │              │           └────────┬───────┘
                      │              │                    │
                      │              │                    ▼
                      │              │       Structured TaskGraph JSON
                      │              │                    │
                      │              └────────────┬───────┘
                      │                           │
                      ▼                           ▼
            ┌───────────────────────────────────────────────┐
            │ 5. DETERMINISTIC GRAPH VALIDATOR (20 Checks)  │
            └───────────────────────┬───────────────────────┘
                                    │
                            VALID ──┴── INVALID
                              │            │
                              │            ▼
                              │   One-Shot Targeted Repair
                              │   (Inject Validator Errors)
                              │            │
                              │     VALID ─┴─ INVALID
                              │       │          │
                              ▼       ▼          ▼
                        ┌───────────┐      Report Capability Gap /
                        │ OPTIMIZER │      Clarification Prompt
                        └─────┬─────┘
                              │
                              ▼
            ┌───────────────────────────────────┐
            │ 6. PARALLEL DAG SCHEDULER         │
            │  - Reverse Adjacency / Ready Set  │
            │  - Structured Concurrency         │
            │  - Resource Locks (file, system)  │
            │  - Phase 3 Ambiguity Guard        │
            │  - Phase 4 Minimal Risk Gate      │
            └─────────────────┬─────────────────┘
                              │
                              ▼
            ┌───────────────────────────────────┐
            │ 7. VERIFIED GRAPH RESULT          │
            └───────────────────────────────────┘
```

---

## 3. TaskGraph Contract & Schemas (`core/planner/schema.py`)

### TaskGraph
- `graph_id`: Unique identifier (e.g. `g_a1b2c3d4e5f6`).
- `goal`: Original user instruction.
- `goal_summary`: Short human-readable summary.
- `nodes`: List of `TaskNode` objects (maximum 20 nodes).
- `blocking_questions`: Clarification questions required before execution.
- `missing_capabilities`: Missing system tools identified during analysis.
- `planner_model`: Model utilized (`qwen3:1.7b`, `qwen3:4b`, or `deterministic`).
- `registry_version`: Tool catalog fingerprint.
- `schema_version`: Contract version (`1.0.0`).

### TaskNode
- `id`: Simple normalized identifier (`n1`, `n2`, ...).
- `tool`: Registered tool name (e.g. `find_file`, `copy_file`).
- `args`: Explicit literal parameters.
- `bindings`: Dynamic data flow bindings from upstream nodes.
- `depends_on`: Explicit upstream dependency node IDs.
- `condition`: Declarative condition DSL.
- `on_failure`: `FAIL_DEPENDENTS`, `CONTINUE_INDEPENDENT`, or `OPTIONAL`.
- `description`: Short description (<= 200 characters).

### ValueBinding
Typed binding connecting upstream output paths to downstream input arguments:
```json
{
  "source": {
    "node_id": "n1",
    "output_path": "results[0].path"
  }
}
```

### Declarative Condition DSL
Strict declarative condition without `eval()` or `exec()`:
- Supported operators: `EQ`, `NE`, `GT`, `GTE`, `LT`, `LTE`, `EXISTS`, `NOT_EXISTS`, `IS_TRUE`, `IS_FALSE`.
- Operands: `ValueBinding` or primitive literals (string, integer, float, boolean).

---

## 4. Deterministic Graph Validator (`core/planner/validator.py`)

Every graph must pass the strict 20-order deterministic validation before execution:
1. **Schema version check**: Must match system version.
2. **Node ID format & uniqueness**: Must follow `^n[1-9][0-9]*$` with zero duplicates.
3. **Node count limit**: Maximum 20 nodes per graph.
4. **Tool existence**: Every tool must exist in `ToolRegistry`.
5. **Tool permission in build**: Tool must be registered and active.
6. **Input argument schema**: Supplied literal arguments must conform to Pydantic types.
7. **Binding reference existence**: Upstream node must exist.
8. **Upstream topological order**: Bound nodes must precede the consumer.
9. **Output path verification**: Path (e.g. `results[0].path`) must statically exist in tool's output model.
10. **Input/Output type compatibility**: Target argument type must accept upstream output type.
11. **Dependency existence**: All `depends_on` IDs must exist.
12. **Self-dependency prohibition**: Node cannot depend on itself.
13. **Cycle detection**: Deterministic Kahn's algorithm; cycles return `GRAPH_CYCLE`.
14. **Graph depth bound**: Maximum dependency depth <= 8.
15. **Fan-out / Fan-in bound**: Maximum outgoing or incoming edges per node <= 8.
16. **Restricted condition validation**: Valid operator and resolved operands.
17. **Unresolved required arguments**: Required arguments must be present in `args` or `bindings`.
18. **Capability gap validation**: Structured capability gaps handled.
19. **Ambiguous search protection**: Guards against blind consumption of ambiguous search results.
20. **Tool catalog fingerprint verification**: Hash match ensures cache consistency.

---

## 5. Tool Capability Retriever (`core/planner/tool_retriever.py`)

To conserve token budget and eliminate tool hallucination, the capability retriever extracts the Top-12 most relevant tools using a cascaded heuristic:
1. Action verb mapping (`find` -> `find_file`, `copy` -> `copy_file`).
2. Domain keywords (`pdf`, `notes`, `folder`, `desktop`).
3. Inverted token index over descriptions and tags.
4. Lexical token overlap with RapidFuzz scoring.

### Schema Compaction
Tool schemas sent to the planner are stripped of implementation details, licenses, and long docstrings:
```json
{
  "name": "copy_file",
  "description": "Copy an existing local file.",
  "input": {
    "source": "str",
    "destination": "str"
  },
  "required": ["source", "destination"],
  "output": {
    "path": "str",
    "copied": "bool"
  }
}
```

---

## 6. DAG Scheduler & Concurrency Engine (`core/scheduler/`)

### Ready-Set Algorithm
- Atomic dependency counters: `remaining_deps[node_id]`.
- Reverse adjacency list: `dependents_map[parent_id] -> [child_id, ...]`.
- Independent root nodes execute immediately in parallel up to `max_concurrency = 4`.
- When parent node completes, dependent counters decrement; nodes hitting zero are placed into the ready queue.

### Structured Concurrency & Failure Isolation
- Tool execution is wrapped in `_execute_node_safe`: exceptions are captured as structured `NodeResult(state=NodeState.FAILED)`, preventing event loop crashes.
- When an upstream node fails:
  - Transitive dependents are marked `SKIPPED_DEPENDENCY_FAILED`.
  - Independent branches continue executing unimpeded.

### Deadlock-Free Resource Locking
- `ResourceLockManager` identifies conflicting operations sharing resource keys (e.g. `file:c:\notes.pdf`, `directory:c:\desktop\exam`).
- Acquires locks in sorted order across parallel branches to eliminate circular wait and deadlocks.

### Ambiguous Search Result Guard
- If `find_file` returns `is_ambiguous=True` or multiple candidates without deterministic disambiguation:
  - Dependent state-changing operations (e.g. `copy_file`, `move_file`) are marked `BLOCKED_AMBIGUOUS_INPUT`.
  - Graph returns `GraphStatus.NEEDS_CLARIFICATION`.

### Minimal Phase-4 Risk Gate
- Tools with risk `EXTERNAL_EFFECT`, `DESTRUCTIVE`, or `PRIVILEGED` are intercepted:
  - Return `needs_policy_confirmation=True`.
  - Execution is halted with `GraphStatus.NEEDS_CONFIRMATION` pending the Phase 5 confirmation engine.

---

## 7. Plan Template Cache (`core/planner/cache.py`)

- **In-Memory LRU**: 512 entries for instant retrieval (< 1 ms p95).
- **SQLite Persistent Store**: `plan_cache` table for cross-session reuse.
- **Task Shape Generalization**: Caches parameterized shapes rather than literal entity values.
- **Fingerprint Invalidation**: Purged automatically when `ToolRegistry` fingerprint changes.
- **Promotion Heuristic**: Promoted to SQLite after 3 successful executions.

---

## 8. Developer & Inspection CLI

### Plan-Only Mode
Inspect planned TaskGraph JSON and ASCII DAG without executing:
```powershell
python -m jarvis.cli --plan-only "Find my NLP notes, copy them into a new folder called NLP Study on Desktop and open the folder."
```

### Explain-Plan Mode
Inspect timings, candidate tools, graph depth, and validation metrics:
```powershell
python -m jarvis.cli --explain-plan "Find my NLP notes and OS notes"
```

### System Quality Report
View complete Phase 4 metrics, cache hit rates, validity, and latency percentiles:
```powershell
python -m jarvis.report planner
```
