# Unified Knowledge Architecture in JARVIS EDGE v1.0

## 1. The "One Knowledge" Invariant
JARVIS EDGE maintains **ONE** unified knowledge and retrieval architecture.
- **NO** independent `whatsapp_memory.db`.
- **NO** secondary vector database.
- **NO** duplicate RAG databases.

All retrieval flows through `KnowledgeService`, which unifies:
1. Local filesystem files & metadata (SearchEngine)
2. Project documents and repositories (SearchEngine & KnowledgeEngine)
3. Structural document chunks and PDFs (KnowledgeEngine FTS5)
4. Layered conversational and workflow memory (Phase 12 store)
5. WhatsApp multimodal material: ingested documents, OCR contexts, voice transcripts

---

## 2. Retrieval Pipeline & Reciprocal Rank Fusion (RRF)

```
User Query
    │
    ▼
Scope Resolver
    │  (Filters eligible scopes: scope:user, scope:whatsapp:chat:<id>, etc.)
    ▼
Unified Retriever
    ├── Files & Project Tree (SearchEngine Level 0 - 3)
    ├── FTS5 Document Chunks (KnowledgeEngine)
    ├── Ingested WhatsApp Documents & Transcripts
    └── Layered Conversation Memory
    │
    ▼
Pre-Ranking Scope Filter (ZERO data leakage enforcement)
    │
    ▼
Reciprocal Rank Fusion (RRF) (k=60)
    │
    ▼
Final Context Ranking (Relevance 0.1 - 1.0)
```

---

## 3. Supported Knowledge Queries
- `"Find the PDF Rahul sent me yesterday."` -> Searches WhatsApp document chunks with `scope:whatsapp`.
- `"Search my documents for machine learning notes."` -> Searches local documents and RAG chunks.
- `"Summarize the PDF I just sent on WhatsApp and compare it with my local notes."` -> Unifies WhatsApp attachment chunks with local document notes.
