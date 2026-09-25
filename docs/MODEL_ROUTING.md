# JARVIS ULTRA — MODEL PROMPTS, SCHEMAS & DAG VALIDATION

## 1. The Principle of Constrained Model Invocations
In JARVIS ULTRA, generative models are treated strictly as structured data transformers, never as autonomous script-writers or unrestricted agents.
- **Routers** output tiny JSON schemas (< 50 tokens).
- **Planners** output acyclic directed graphs (DAGs) of registered tool nodes.
- **Conversational Essays** are strictly suppressed; deterministic templates format verified facts.

---

## 2. Tiny Router (Lane 2) Specification

### System Prompt Design
```
SYSTEM:
You are an intent and slot classifier.
You cannot execute anything.
Choose only from the supplied candidate intents.
Never invent a tool or action.
If information is missing, list it in "missing".
If confidence is insufficient, return intent=null.
Return exactly the required JSON schema.
Do not output conversational text or explanations.

USER:
Utterance: {utterance}
Candidate intents: {candidate_intents}
Candidate entities: {candidate_entities}

OUTPUT SCHEMA:
{
  "intent": string | null,
  "slots": object,
  "missing": string[],
  "confidence": number,
  "multi_step": boolean
}
```

---

## 3. Task Planner (Lane 3) DAG Specification

### TaskNode Schema
```python
class TaskNode(BaseModel):
    id: str                                  # Unique node ID within graph (e.g. "node_1")
    tool: str                                # Exact tool name registered in ToolRegistry
    args: dict[str, Any]                     # Validated argument parameters
    depends_on: list[str] = []               # Predecessor node IDs
    condition: str | None = None             # Optional runtime execution guard
    risk: RiskClass                          # Independently verified by ToolRegistry
    verification: VerificationSpec           # Mandatory typed verification assertion
    timeout_ms: int = 5000                   # Bounded execution window
```

### TaskGraph Schema
```python
class TaskGraph(BaseModel):
    goal: str
    nodes: list[TaskNode]
    assumptions: list[str] = []
    clarification: str | None = None
```

---

## 4. Authoritative Risk Computation & Validation Pipeline

Under NO circumstances does the core runtime trust the model's self-assessed risk level:

```
[Planner LLM Output]
          │
          ▼
   [JSON Parser] ──(Syntax Error)──► [Max 1 Bounded Repair] ──► Fail Safely
          │
          ▼
 [Pydantic Validation]
          │
          ├──► Check: All tool names exist in ToolRegistry
          ├──► Check: Argument types match tool schemas
          ├──► Check: Graph is strictly Acyclic (Cycle detection)
          │
          ▼
 [Authoritative Risk Recomputation]
          │
          └──► Query ToolRegistry for true RiskClass (READ_ONLY vs CONSEQUENTIAL)
               (Model CANNOT lower risk level)
          │
          ▼
   [Policy Engine]
          │
          ├── Consequential: Require Confirmation Ticket
          └── Read-Only / Safe: Authorize for Execution
```
