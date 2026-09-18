# JARVIS EDGE — Memory Engine Architecture

## 1. Layered Memory Architecture

Memory is divided into six distinct operational layers:

```
+-------------------------------------------------------------------+
| 1. SESSION MEMORY     (Active command chain; ephemeral RAM)       |
+-------------------------------------------------------------------+
| 2. WORKING MEMORY     (Bounded 50-item working set; p95 < 0.001ms)|
+-------------------------------------------------------------------+
| 3. EPISODIC MEMORY    (Structured execution summaries; SQLite)    |
+-------------------------------------------------------------------+
| 4. SEMANTIC KNOWLEDGE (Explicit facts with full provenance)       |
+-------------------------------------------------------------------+
| 5. PREFERENCE MEMORY  (Operational non-sensitive user settings)   |
+-------------------------------------------------------------------+
| 6. WORKFLOW MEMORY    (Approved parameterized execution DAGs)     |
+-------------------------------------------------------------------+
```

---

## 2. Provenance & Conflict Resolution

Every durable memory records mandatory provenance metadata:
```python
@dataclass
class MemoryProvenance:
    source_type: MemorySourceType      # USER_EXPLICIT, VERIFIED_ACTION, USER_CORRECTION
    source_reference: Optional[str]    # Originating command or verified node ID
    confidence: MemoryConfidence       # EXPLICIT, VERIFIED, INFERRED_HIGH, INFERRED_LOW
    created_at: float
    last_used: float
    use_count: int
    successful_use_count: int
    correction_count: int
    supersedes_id: Optional[str]      # Links previous superseded memory
```

### Conflict Resolution Strategy
When an explicit correction occurs (e.g., `"Use Edge from now on"` superseding `"Chrome"`):
1. The existing record is marked `SUPERSEDED` and retained for audit/provenance history.
2. The new memory record points back to `supersedes_id`.
3. Current lookups immediately return the new active record.
4. Silent overwriting is strictly prohibited.

---

## 3. Privacy & Untrusted Data Protection

- **Secret Filter**: All incoming candidates are evaluated with strict regular expressions matching API keys (`sk-[a-zA-Z0-9_\-]{20,}`, `AIza[0-9A-Za-z_\-]{20,}`), private keys (`-----BEGIN PRIVATE KEY-----`), OTPs (`\b\d{6}\b`), and passwords. Matches are rejected with `REJECT: sensitive secret or credential pattern detected`.
- **Untrusted Source Immunity**: Content from email bodies, downloaded web pages, screen text, or third-party documents is classified as `UNTRUSTED_EXTERNAL_CONTENT` and rejected from creating durable memory.

---

## 4. Performance & Retrieval Cascade

Lookups follow a strict cascaded fast-path:
1. **Working Memory Exact** (RAM): $p95 = 0.0003\text{ ms}$
2. **Structured Exact SQL Index** (SQLite): $p95 = 2.28\text{ ms}$
3. **FTS5 Lexical Search** (SQLite Full-Text Search): $p95 = 5.05\text{ ms}$
4. **Vector Similarity** (Optional sqlite-vec): CPU-friendly on-demand embeddings.
5. **Degradation**: If vector extensions are unavailable, lexical FTS5 and structured indexing operate without interruption.
