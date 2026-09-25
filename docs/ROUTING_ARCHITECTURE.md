# JARVIS ULTRA — MULTI-LANE CASCADE ROUTING ARCHITECTURE

## 1. Executive Principle: The Fastest Model Call is the One Never Made
Generative LLMs are non-deterministic, slow (tens to hundreds of milliseconds), and memory-intensive. In daily desktop interaction, the vast majority of commands ("open chrome", "mute", "what time is it") are structured and deterministic.
JARVIS ULTRA employs a disciplined multi-lane cascade router (`SmartRouter`):

```
[Final Authoritative Transcript]
               │
               ▼
   [Conservative Canonicaliser]
               │
               ▼
┌───────────────────────────────┐
│ Lane 0: Typed Grammar & Alias │ ────(Match)────► [Fast-Path Execution (< 0.5 ms)]
└───────────────────────────────┘
               │ (Abstain)
               ▼
┌───────────────────────────────┐
│ Lane 0.5: Fuzzy Candidate     │ ────(Repaired)──► [Retry Lane 0]
└───────────────────────────────┘
               │ (Abstain)
               ▼
┌───────────────────────────────┐
│ Lane 1: Semantic Embeddings   │ ────(Similarity >= Threshold)──► [Lane 0 Dispatch]
└───────────────────────────────┘
               │ (Abstain)
               ▼
┌───────────────────────────────┐
│ Lane 2: Qwen3.5-0.8B (Slot)   │ ────(Single-step)──► [Direct Tool Dispatch]
└───────────────────────────────┘
               │ (Multi-step / Complex)
               ▼
┌───────────────────────────────┐
│ Lane 3: Qwen3.5-4B (Planner)  │ ───────────────────► [Acyclic DAG TaskGraph]
└───────────────────────────────┘
```

---

## 2. Lane Specifications & Budgets

### Lane 0: Deterministic Grammar & Hot Route Cache (< 1.0 ms Budget)
- **Mechanism**: Regex patterns, keyword aliases, and in-memory O(1) LRU `HotRouteCache`.
- **Latency on Real Hardware**: **0.158 ms** (p50), **0.313 ms** (p95).
- **Throughput**: **5,978.7 routes/sec**.
- **Coverage**: ~50–70% of daily user commands.

### Lane 0.5: Conservative Fuzzy & Phonetic Repair
- **Mechanism**: RapidFuzz string distance against personal context lexicon.
- **Rule**: Requires high similarity ($\ge 85\%$) AND a clear margin ($\ge 12\%$) over the second candidate.
- **Safety**: Destructive commands (delete, install, send) NEVER fuzzy-match silently; ambiguity triggers clarification.

### Lane 1: Semantic Embedding Router
- **Mechanism**: Local embedding similarity against canonical route clusters.
- **Abstention Law**: Every route cluster defines an individual cosine threshold. If similarity is below threshold or the top-2 margin is narrow, the router explicitly **ABSTAINS** rather than guessing.

### Lane 2: Structured Slot Filling (Qwen3.5-0.8B Q4)
- **Role**: Invoked only when Lanes 0–1 abstain on an apparent single-step command.
- **Prompt**: Strictly constrained system prompt; outputs compact JSON schema with zero conversational text.
- **Validation**: Pydantic schema validation with at most one repair attempt.

### Lane 3: Multi-Step Task Planner (Qwen3.5-4B Q4)
- **Role**: Invoked for compound multi-step goals ("find my NLP notes, create a folder called Exam Notes, copy the file there and open it").
- **Output**: Typed acyclic DAG `TaskGraph` (never raw shell, code, or scripts).
- **Authority**: Tool risk is independently evaluated by `Policy`; model cannot lower risk.
