"""KnowledgeEngine providing explicit RAG collections, document chunking, scoped hybrid search.

Retrieval = BM25 over an FTS5 index (always available) fused with cosine similarity over
Ollama embeddings (when an embedding model is installed) using Reciprocal Rank Fusion.
Privacy scopes are enforced on every candidate *before* ranking, for both retrievers.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

import numpy as np

from jarvis.core.knowledge.rerank import rerank

from jarvis.core.knowledge.models import (
    AccessPolicy,
    KnowledgeChunk,
    KnowledgeCollection,
    KnowledgeItem,
    KnowledgeScopeFilter,
    KnowledgeSourceType,
    TrustLevel,
)

logger = logging.getLogger("jarvis.core.knowledge.engine")

FTS_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "am", "do", "does", "did", "of", "in", "on",
    "at", "to", "for", "from", "by", "with", "about", "as", "and", "or", "not", "no", "it", "its", "this",
    "that", "these", "those", "what", "which", "who", "whom", "whose", "when", "where", "why", "how", "i",
    "me", "my", "you", "your", "we", "our", "they", "their", "he", "she", "his", "her", "can", "could",
    "would", "should", "will", "shall", "may", "might", "must", "please", "tell", "show", "give", "find",
    "search", "any", "some", "there", "here", "has", "have", "had", "jarvis", "document", "documents",
    "file", "files", "pdf", "notes", "summarize", "summary", "explain", "say", "says", "said",
}
INDEXABLE_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".csv", ".json", ".yaml", ".yml", ".toml", ".ini", ".log",
    ".py", ".js", ".ts", ".java", ".c", ".cpp", ".cs", ".go", ".rs", ".html", ".css", ".sql",
    ".pdf", ".docx",
}
RRF_K = 60.0


def build_fts_query(text: str, max_terms: int = 12) -> str:
    """Natural language -> FTS5 query: OR of meaningful terms (prefix-matched when long enough).

    A raw sentence would be an implicit AND of every word ("what is the refund policy"
    would require "what", "is" and "the" to appear), which almost never matches.
    """
    terms: list[str] = []
    for token in re.findall(r"[A-Za-z0-9]+", text.lower()):
        if token in FTS_STOPWORDS or len(token) < 2 or token in terms:
            continue
        terms.append(token)
        if len(terms) >= max_terms:
            break
    if not terms:
        return ""
    return " OR ".join(f'"{t}"*' if len(t) >= 4 else f'"{t}"' for t in terms)


class KnowledgeEngine:
    """
    Manages user-selected local RAG collections with structural document chunking,
    FTS5 lexical search, optional dense vectors, namespace scopes, and strict
    untrusted-content boundaries.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._vector_cache: dict[str, tuple[int, list[str], np.ndarray]] = {}
        self._write_version = 0
        self._stats_cache: Optional[tuple[int, float, tuple[int, tuple[str, ...]]]] = None
        self._ensure_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _ensure_tables(self):
        with self._get_connection() as conn:
            migration_file = Path(__file__).resolve().parent.parent.parent / "db/migrations/006_phase12_intelligence.sql"
            if migration_file.exists():
                try:
                    conn.executescript(migration_file.read_text(encoding="utf-8"))
                except sqlite3.OperationalError:
                    pass

            # Safe column additions for scoping
            cursor = conn.cursor()
            try:
                cursor.execute("PRAGMA table_info(rag_chunks)")
                existing_cols = {row["name"] for row in cursor.fetchall()}
                if "owner_scope" not in existing_cols:
                    cursor.execute("ALTER TABLE rag_chunks ADD COLUMN owner_scope TEXT DEFAULT 'scope:user'")
                if "conversation_scope" not in existing_cols:
                    cursor.execute("ALTER TABLE rag_chunks ADD COLUMN conversation_scope TEXT DEFAULT ''")
                if "privacy_scope" not in existing_cols:
                    cursor.execute("ALTER TABLE rag_chunks ADD COLUMN privacy_scope TEXT DEFAULT 'scope:documents'")
                if "trust_level" not in existing_cols:
                    cursor.execute("ALTER TABLE rag_chunks ADD COLUMN trust_level TEXT DEFAULT 'DATA_ONLY'")
                if "source_type" not in existing_cols:
                    cursor.execute("ALTER TABLE rag_chunks ADD COLUMN source_type TEXT DEFAULT 'RAG_CHUNK'")
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS rag_vectors (
                        chunk_id TEXT NOT NULL,
                        model TEXT NOT NULL,
                        dim INTEGER NOT NULL,
                        vector BLOB NOT NULL,
                        PRIMARY KEY (chunk_id, model)
                    )
                    """
                )
                conn.commit()
            except Exception as exc:
                logger.debug("Knowledge schema upgrade skipped: %s", exc)

    # ------------------------------------------------------------------ collections
    def create_collection(
        self,
        name: str,
        source_roots: List[str],
        file_filters: Optional[List[str]] = None,
        access_policy: AccessPolicy = AccessPolicy.PUBLIC,
        owner_scope: str = "scope:user",
    ) -> KnowledgeCollection:
        col_id = f"col_{hashlib.sha256(name.encode('utf-8')).hexdigest()[:8]}"
        col = KnowledgeCollection(
            collection_id=col_id,
            name=name,
            source_roots=source_roots,
            file_filters=file_filters or [".txt", ".md", ".pdf", ".py"],
            access_policy=access_policy,
            owner_scope=owner_scope,
        )

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO rag_collections (
                    collection_id, name, source_roots_json, file_filters_json, access_policy
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    col.collection_id,
                    col.name,
                    json.dumps(col.source_roots),
                    json.dumps(col.file_filters),
                    col.access_policy.value,
                ),
            )
            conn.commit()
        return col

    def get_or_create_collection(self, name: str, source_roots: Optional[List[str]] = None) -> KnowledgeCollection:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM rag_collections WHERE name = ?", (name,)).fetchone()
        if row:
            roots = set(json.loads(row["source_roots_json"] or "[]")) | set(source_roots or [])
            return self.create_collection(name, sorted(roots), json.loads(row["file_filters_json"] or "[]") or None)
        return self.create_collection(name, list(source_roots or []))

    def list_collections(self) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT c.collection_id, c.name, c.source_roots_json,
                       COUNT(k.chunk_id) AS chunks, COUNT(DISTINCT k.file_path) AS files
                FROM rag_collections c LEFT JOIN rag_chunks k ON k.collection_id = c.collection_id
                GROUP BY c.collection_id ORDER BY c.name
                """
            ).fetchall()
        return [
            {"collection_id": r["collection_id"], "name": r["name"], "roots": json.loads(r["source_roots_json"] or "[]"),
             "chunks": r["chunks"], "files": r["files"]}
            for r in rows
        ]

    # ------------------------------------------------------------------ indexing
    def index_document_text(
        self,
        collection_id: str,
        file_path: str,
        text_content: str,
        owner_scope: str = "scope:user",
        conversation_scope: str = "",
        privacy_scope: str = "scope:documents",
        trust_level: str = TrustLevel.DATA_ONLY.value,
        source_type: str = KnowledgeSourceType.RAG_CHUNK.value,
    ) -> int:
        """Chunks and indexes document text into collection with explicit scope tags."""
        chunks = self._chunk_text(
            text_content,
            file_path,
            collection_id,
            owner_scope=owner_scope,
            conversation_scope=conversation_scope,
            privacy_scope=privacy_scope,
            trust_level=trust_level,
        )

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            # Remove previous chunks (and their FTS rows / vectors) for this file.
            old_ids = [r[0] for r in cursor.execute(
                "SELECT chunk_id FROM rag_chunks WHERE collection_id = ? AND file_path = ?", (collection_id, file_path)
            ).fetchall()]
            if old_ids:
                marks = ",".join("?" * len(old_ids))
                cursor.execute(f"DELETE FROM rag_chunks_fts WHERE chunk_id IN ({marks})", old_ids)
                cursor.execute(f"DELETE FROM rag_vectors WHERE chunk_id IN ({marks})", old_ids)
                cursor.execute("DELETE FROM rag_chunks WHERE collection_id = ? AND file_path = ?", (collection_id, file_path))
            for c in chunks:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO rag_chunks (
                        chunk_id, collection_id, file_path, section_title,
                        line_start, line_end, content, content_hash,
                        owner_scope, conversation_scope, privacy_scope, trust_level, source_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        c.chunk_id, c.collection_id, c.file_path, c.section_title,
                        c.line_start, c.line_end, c.content, c.content_hash,
                        c.owner_scope, c.conversation_scope, c.privacy_scope, c.trust_level, source_type,
                    ),
                )
                cursor.execute(
                    "INSERT INTO rag_chunks_fts (chunk_id, collection_id, section_title, content) VALUES (?, ?, ?, ?)",
                    (c.chunk_id, c.collection_id, c.section_title, c.content),
                )
            conn.commit()
            self._write_version += 1
        return len(chunks)

    def remove_file(self, file_path: str) -> int:
        with self._lock, self._get_connection() as conn:
            ids = [r[0] for r in conn.execute("SELECT chunk_id FROM rag_chunks WHERE file_path = ?", (file_path,)).fetchall()]
            if ids:
                marks = ",".join("?" * len(ids))
                conn.execute(f"DELETE FROM rag_chunks_fts WHERE chunk_id IN ({marks})", ids)
                conn.execute(f"DELETE FROM rag_vectors WHERE chunk_id IN ({marks})", ids)
                conn.execute("DELETE FROM rag_chunks WHERE file_path = ?", (file_path,))
                conn.commit()
                self._write_version += 1
            return len(ids)

    def ingest_path(
        self,
        path: str | Path,
        collection_name: str = "My Documents",
        recursive: bool = True,
        max_files: int = 400,
        max_file_mb: float = 25.0,
    ) -> dict[str, Any]:
        """Index a file or folder (text, code, markdown, PDF, DOCX) into a named collection."""
        from jarvis.memory.search.extractor import extract_file_content

        root = Path(path).expanduser()
        if not root.exists():
            raise FileNotFoundError(f"Path not found: {root}")
        col = self.get_or_create_collection(collection_name, [str(root)])
        if root.is_file():
            candidates: Iterable[Path] = [root]
        else:
            pattern = "**/*" if recursive else "*"
            skip_parts = {".git", "node_modules", ".venv", "venv", "__pycache__", "AppData", "$Recycle.Bin"}
            candidates = (
                p for p in root.glob(pattern)
                if p.is_file() and p.suffix.lower() in INDEXABLE_EXTENSIONS and not (set(p.parts) & skip_parts)
            )
        stats = {"collection": collection_name, "files_indexed": 0, "chunks": 0, "skipped": 0, "errors": []}
        for idx, file in enumerate(candidates):
            if idx >= max_files:
                stats["truncated"] = True
                break
            text, _excerpt, status, error = extract_file_content(str(file), max_file_size_mb=max_file_mb)
            if status != "SUCCESS" or not text.strip():
                stats["skipped"] += 1
                if error and len(stats["errors"]) < 5:
                    stats["errors"].append(f"{file.name}: {error}")
                continue
            stats["chunks"] += self.index_document_text(col.collection_id, str(file), text)
            stats["files_indexed"] += 1
        return stats

    # ------------------------------------------------------------------ vectors
    def chunks_missing_vectors(self, model: str, limit: int = 64) -> list[tuple[str, str]]:
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT c.chunk_id, c.section_title, c.content FROM rag_chunks c
                LEFT JOIN rag_vectors v ON v.chunk_id = c.chunk_id AND v.model = ?
                WHERE v.chunk_id IS NULL LIMIT ?
                """,
                (model, limit),
            ).fetchall()
        return [(r["chunk_id"], f"{r['section_title'] or ''}\n{r['content']}".strip()) for r in rows]

    def store_vectors(self, model: str, items: Sequence[tuple[str, Sequence[float]]]) -> int:
        stored = 0
        with self._lock, self._get_connection() as conn:
            for chunk_id, vector in items:
                arr = np.asarray(vector, dtype=np.float32)
                if arr.size == 0:
                    continue
                norm = float(np.linalg.norm(arr)) or 1.0
                arr = arr / norm
                conn.execute(
                    "INSERT OR REPLACE INTO rag_vectors (chunk_id, model, dim, vector) VALUES (?, ?, ?, ?)",
                    (chunk_id, model, int(arr.size), arr.tobytes()),
                )
                stored += 1
            conn.commit()
            self._write_version += 1
        return stored

    def vector_count(self, model: str | None = None) -> int:
        with self._get_connection() as conn:
            if model:
                return conn.execute("SELECT COUNT(*) FROM rag_vectors WHERE model = ?", (model,)).fetchone()[0]
            return conn.execute("SELECT COUNT(*) FROM rag_vectors").fetchone()[0]

    def vector_models(self) -> list[str]:
        return list(self.stats()[1])

    def stats(self, max_age_s: float = 30.0) -> tuple[int, tuple[str, ...]]:
        """(chunk count, embedding models) - cached so the hot query path skips two table scans.

        Refreshed after every local write and at least every ``max_age_s`` (another process may index).
        """
        cached = self._stats_cache
        now = time.monotonic()
        if cached and cached[0] == self._write_version and now - cached[1] < max_age_s:
            return cached[2]
        with self._get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM rag_chunks").fetchone()[0]
            models = tuple(r[0] for r in conn.execute("SELECT DISTINCT model FROM rag_vectors").fetchall())
        self._stats_cache = (self._write_version, now, (int(count), models))
        return int(count), models

    async def embed_pending(self, client: Any, model: str | None = None, batch_size: int = 32, max_batches: int = 50) -> int:
        """Embed chunks that have no vector yet (runs in the background after ingestion)."""
        import asyncio

        model = model or await client.resolve("embed")
        total = 0
        for _ in range(max_batches):
            pending = await asyncio.to_thread(self.chunks_missing_vectors, model, batch_size)
            if not pending:
                break
            vectors = await client.embed([text[:4000] for _, text in pending], model=model)
            total += await asyncio.to_thread(self.store_vectors, model, [(cid, vec) for (cid, _), vec in zip(pending, vectors)])
        return total

    def _vector_matrix(self, model: str) -> tuple[list[str], np.ndarray]:
        cached = self._vector_cache.get(model)
        if cached and cached[0] == self._write_version:
            return cached[1], cached[2]
        with self._get_connection() as conn:
            rows = conn.execute("SELECT chunk_id, dim, vector FROM rag_vectors WHERE model = ?", (model,)).fetchall()
        if not rows:
            ids, matrix = [], np.zeros((0, 0), dtype=np.float32)
        else:
            dim = rows[0]["dim"]
            usable = [r for r in rows if r["dim"] == dim]
            ids = [r["chunk_id"] for r in usable]
            matrix = np.vstack([np.frombuffer(r["vector"], dtype=np.float32) for r in usable])
        self._vector_cache[model] = (self._write_version, ids, matrix)
        return ids, matrix

    # ------------------------------------------------------------------ search
    def _row_to_item(self, row: sqlite3.Row, score: float) -> KnowledgeItem:
        content_str = row["content"] or ""
        snippet = content_str[:400] + "..." if len(content_str) > 400 else content_str
        file_name = Path(row["file_path"]).name if row["file_path"] else "Document"
        return KnowledgeItem(
            source_type=row["source_type"] or KnowledgeSourceType.RAG_CHUNK.value,
            resource_id=row["chunk_id"],
            title=f"{file_name} ({row['section_title'] or 'Section'})",
            snippet=snippet,
            relevance=score,
            trust=row["trust_level"] or TrustLevel.DATA_ONLY.value,
            owner_scope=row["owner_scope"] or "scope:user",
            conversation_scope=row["conversation_scope"] or "",
            privacy_scope=row["privacy_scope"] or "scope:documents",
            citation_metadata={"file_path": row["file_path"], "lines": f"{row['line_start']}-{row['line_end']}"},
        )

    @staticmethod
    def _accessible(row: sqlite3.Row, scope_filter: Optional[KnowledgeScopeFilter]) -> bool:
        if not scope_filter:
            return True
        scopes = [s for s in (row["owner_scope"] or "scope:user", row["conversation_scope"] or "", row["privacy_scope"] or "scope:documents") if s]
        return scope_filter.is_accessible(scopes)

    def _collection_id(self, conn: sqlite3.Connection, collection_name: Optional[str]) -> Optional[str]:
        if not collection_name:
            return None
        row = conn.execute("SELECT collection_id FROM rag_collections WHERE name = ?", (collection_name,)).fetchone()
        return row["collection_id"] if row else "__missing__"

    def search(
        self,
        query_text: str,
        collection_name: Optional[str] = None,
        scope_filter: Optional[KnowledgeScopeFilter] = None,
        limit: int = 5,
    ) -> List[KnowledgeItem]:
        """Lexical BM25 search with pre-ranking scope filtering."""
        fts_query = build_fts_query(query_text)
        if not fts_query:
            return []
        results: List[KnowledgeItem] = []
        with self._get_connection() as conn:
            params: List[Any] = [fts_query]
            sql = """
                SELECT c.*, bm25(rag_chunks_fts) AS rank
                FROM rag_chunks_fts f
                JOIN rag_chunks c ON f.chunk_id = c.chunk_id
                WHERE rag_chunks_fts MATCH ?
            """
            col_id = self._collection_id(conn, collection_name)
            if col_id:
                sql += " AND c.collection_id = ?"
                params.append(col_id)
            sql += " ORDER BY rank LIMIT ?"
            params.append(max(limit * 6, 30))
            try:
                rows = conn.execute(sql, params).fetchall()
            except sqlite3.OperationalError as exc:
                logger.debug("FTS query failed (%s): %s", fts_query, exc)
                return []
            for r in rows:
                if not self._accessible(r, scope_filter):
                    continue
                score = max(0.1, min(1.0, 1.0 / (1.0 + abs(float(r["rank"])))))
                results.append(self._row_to_item(r, score))
                if len(results) >= limit:
                    break
        return results

    def vector_search(
        self,
        query_vector: Sequence[float],
        model: str,
        collection_name: Optional[str] = None,
        scope_filter: Optional[KnowledgeScopeFilter] = None,
        limit: int = 5,
        min_similarity: float = 0.25,
    ) -> List[KnowledgeItem]:
        ids, matrix = self._vector_matrix(model)
        if not ids:
            return []
        q = np.asarray(query_vector, dtype=np.float32)
        if q.size != matrix.shape[1]:
            return []
        q = q / (float(np.linalg.norm(q)) or 1.0)
        sims = matrix @ q
        order = np.argsort(-sims)[: max(limit * 8, 40)]
        chosen = [(ids[i], float(sims[i])) for i in order if sims[i] >= min_similarity]
        if not chosen:
            return []
        results: List[KnowledgeItem] = []
        with self._get_connection() as conn:
            col_id = self._collection_id(conn, collection_name)
            marks = ",".join("?" * len(chosen))
            rows = {r["chunk_id"]: r for r in conn.execute(f"SELECT * FROM rag_chunks WHERE chunk_id IN ({marks})", [c for c, _ in chosen])}
            for chunk_id, sim in chosen:
                row = rows.get(chunk_id)
                if row is None or (col_id and row["collection_id"] != col_id) or not self._accessible(row, scope_filter):
                    continue
                item = self._row_to_item(row, max(0.0, min(1.0, sim)))
                item.citation_metadata["dense_sim"] = round(sim, 4)  # kept through fusion for the reranker
                results.append(item)
                if len(results) >= limit:
                    break
        return results

    def search_hybrid(
        self,
        query_text: str,
        query_vector: Optional[Sequence[float]] = None,
        model: Optional[str] = None,
        collection_name: Optional[str] = None,
        scope_filter: Optional[KnowledgeScopeFilter] = None,
        limit: int = 5,
    ) -> List[KnowledgeItem]:
        """Reciprocal Rank Fusion of lexical and dense retrieval (dense optional)."""
        lexical = self.search(query_text, collection_name, scope_filter, max(limit * 4, 12))
        dense = (
            self.vector_search(query_vector, model, collection_name, scope_filter, limit * 2)
            if query_vector is not None and model else []
        )
        if not dense:
            return rerank(query_text, lexical, limit=limit)
        scores: Dict[str, float] = {}
        items: Dict[str, KnowledgeItem] = {}
        for ranked in (lexical, dense):
            for rank, item in enumerate(ranked, start=1):
                scores[item.resource_id] = scores.get(item.resource_id, 0.0) + 1.0 / (RRF_K + rank)
                items.setdefault(item.resource_id, item)
        ordered = sorted(scores, key=scores.get, reverse=True)
        fused = []
        for rid in ordered:
            item = items[rid]
            item.relevance = min(1.0, scores[rid] * 30.0)
            fused.append(item)
        # precision layer: rerank against the query and drop candidates that do not answer it
        return rerank(query_text, fused, limit=limit)

    # ------------------------------------------------------------------ chunking
    @staticmethod
    def _chunk_text(
        text: str,
        file_path: str,
        collection_id: str,
        max_chunk_chars: int = 1000,
        owner_scope: str = "scope:user",
        conversation_scope: str = "",
        privacy_scope: str = "scope:documents",
        trust_level: str = TrustLevel.DATA_ONLY.value,
    ) -> List[KnowledgeChunk]:
        paragraphs = re.split(r"\n\s*\n", text or "")
        chunks: List[KnowledgeChunk] = []
        current_chunk: List[str] = []
        current_len = 0
        line_num = 1
        chunk_line_start = 1
        curr_title = ""
        chunk_title = ""

        def emit(end_line: int) -> None:
            content_str = "\n\n".join(current_chunk)
            chash = hashlib.sha256(content_str.encode("utf-8")).hexdigest()[:12]
            uid = hashlib.sha256(f"{collection_id}|{file_path}|{len(chunks)}|{chash}".encode("utf-8")).hexdigest()[:16]
            chunks.append(
                KnowledgeChunk(
                    chunk_id=f"chk_{uid}",
                    collection_id=collection_id,
                    file_path=file_path,
                    section_title=chunk_title,
                    line_start=chunk_line_start,
                    line_end=end_line,
                    content=content_str,
                    content_hash=chash,
                    owner_scope=owner_scope,
                    conversation_scope=conversation_scope,
                    privacy_scope=privacy_scope,
                    trust_level=trust_level,
                )
            )

        for p in paragraphs:
            p_clean = p.strip()
            if not p_clean:
                line_num += p.count("\n") + 2
                continue

            # Markdown headings start a new section (and a new chunk): precise hits, correct titles.
            if p_clean.startswith("#"):
                curr_title = p_clean.split("\n")[0].lstrip("#").strip()
                if current_chunk:
                    emit(line_num)
                    current_chunk = []
                    current_len = 0
                    chunk_line_start = line_num

            # Very long paragraphs (PDF pages, minified text) are split on sentence boundaries.
            pieces = [p_clean]
            if len(p_clean) > max_chunk_chars * 1.5:
                pieces, buf = [], ""
                for sentence in re.split(r"(?<=[.!?])\s+", p_clean):
                    if len(buf) + len(sentence) > max_chunk_chars and buf:
                        pieces.append(buf.strip())
                        buf = ""
                    buf += sentence + " "
                if buf.strip():
                    pieces.append(buf.strip())

            for piece in pieces:
                if current_len + len(piece) > max_chunk_chars and current_chunk:
                    emit(line_num)
                    current_chunk = []
                    current_len = 0
                    chunk_line_start = line_num
                if not current_chunk:
                    chunk_title = curr_title
                current_chunk.append(piece)
                current_len += len(piece)

            line_num += p.count("\n") + 2

        if current_chunk:
            emit(line_num)

        return chunks
