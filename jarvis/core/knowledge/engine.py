"""KnowledgeEngine providing explicit RAG collections, document chunking, scoped hybrid search."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from jarvis.core.knowledge.models import (
    AccessPolicy,
    KnowledgeChunk,
    KnowledgeCollection,
    KnowledgeItem,
    KnowledgeScopeFilter,
    KnowledgeSourceType,
    TrustLevel,
)


class KnowledgeEngine:
    """
    Manages user-selected local RAG collections with structural document chunking,
    FTS5 lexical search, namespace scopes, and strict untrusted-content boundaries.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
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
                conn.commit()
            except Exception:
                pass

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
        if not chunks:
            return 0

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Remove old chunks for this file
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
                        c.chunk_id,
                        c.collection_id,
                        c.file_path,
                        c.section_title,
                        c.line_start,
                        c.line_end,
                        c.content,
                        c.content_hash,
                        c.owner_scope,
                        c.conversation_scope,
                        c.privacy_scope,
                        c.trust_level,
                        source_type,
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO rag_chunks_fts (chunk_id, collection_id, section_title, content)
                    VALUES (?, ?, ?, ?)
                    """,
                    (c.chunk_id, c.collection_id, c.section_title, c.content),
                )
            conn.commit()
        return len(chunks)

    def search(
        self,
        query_text: str,
        collection_name: Optional[str] = None,
        scope_filter: Optional[KnowledgeScopeFilter] = None,
        limit: int = 5,
    ) -> List[KnowledgeItem]:
        """Hybrid search across indexed RAG collections with pre-ranking scope filtering."""
        clean_query = "".join(c if c.isalnum() or c in " *_" else " " for c in query_text).strip()
        if not clean_query:
            return []

        results: List[KnowledgeItem] = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            params: List[Any] = [clean_query]
            sql = """
                SELECT c.*, f.rank
                FROM rag_chunks_fts f
                JOIN rag_chunks c ON f.chunk_id = c.chunk_id
                WHERE rag_chunks_fts MATCH ?
            """
            if collection_name:
                cursor.execute("SELECT collection_id FROM rag_collections WHERE name = ?", (collection_name,))
                row = cursor.fetchone()
                if row:
                    sql += " AND c.collection_id = ?"
                    params.append(row["collection_id"])

            # Retrieve broader candidate set to filter by scope before ranking
            sql += " ORDER BY rank LIMIT ?"
            fetch_limit = max(limit * 4, 20)
            params.append(fetch_limit)

            try:
                cursor.execute(sql, params)
                raw_rows = cursor.fetchall()

                for r in raw_rows:
                    row_dict = dict(r)
                    owner_scope = row_dict.get("owner_scope") or "scope:user"
                    conv_scope = row_dict.get("conversation_scope") or ""
                    priv_scope = row_dict.get("privacy_scope") or "scope:documents"
                    trust = row_dict.get("trust_level") or TrustLevel.DATA_ONLY.value
                    src_type = row_dict.get("source_type") or KnowledgeSourceType.RAG_CHUNK.value

                    # Pre-ranking Scope Isolation Check
                    if scope_filter:
                        item_scopes = [s for s in (owner_scope, conv_scope, priv_scope) if s]
                        if not scope_filter.is_accessible(item_scopes):
                            continue

                    score = max(0.1, min(1.0, 1.0 / (1.0 + abs(float(r["rank"])))))
                    content_str = r["content"] or ""
                    snippet = content_str[:200] + "..." if len(content_str) > 200 else content_str
                    file_name = Path(r["file_path"]).name if r["file_path"] else "Document"

                    results.append(
                        KnowledgeItem(
                            source_type=src_type,
                            resource_id=r["chunk_id"],
                            title=f"{file_name} ({r['section_title'] or 'Section'})",
                            snippet=snippet,
                            relevance=score,
                            trust=trust,
                            owner_scope=owner_scope,
                            conversation_scope=conv_scope,
                            privacy_scope=priv_scope,
                            citation_metadata={
                                "file_path": r["file_path"],
                                "lines": f"{r['line_start']}-{r['line_end']}",
                            },
                        )
                    )
                    if len(results) >= limit:
                        break
            except sqlite3.OperationalError:
                pass
        return results

    def _chunk_text(
        self,
        text: str,
        file_path: str,
        collection_id: str,
        max_chunk_chars: int = 1000,
        owner_scope: str = "scope:user",
        conversation_scope: str = "",
        privacy_scope: str = "scope:documents",
        trust_level: str = TrustLevel.DATA_ONLY.value,
    ) -> List[KnowledgeChunk]:
        paragraphs = text.split("\n\n")
        chunks: List[KnowledgeChunk] = []
        current_chunk: List[str] = []
        current_len = 0
        line_num = 1
        chunk_line_start = 1
        curr_title = ""

        for p in paragraphs:
            p_clean = p.strip()
            if not p_clean:
                line_num += p.count("\n") + 2
                continue

            # Detect markdown section headings
            if p_clean.startswith("#"):
                curr_title = p_clean.split("\n")[0].lstrip("#").strip()

            if current_len + len(p_clean) > max_chunk_chars and current_chunk:
                content_str = "\n\n".join(current_chunk)
                chash = hashlib.sha256(content_str.encode("utf-8")).hexdigest()[:12]
                chunks.append(
                    KnowledgeChunk(
                        chunk_id=f"chk_{chash}",
                        collection_id=collection_id,
                        file_path=file_path,
                        section_title=curr_title,
                        line_start=chunk_line_start,
                        line_end=line_num,
                        content=content_str,
                        content_hash=chash,
                        owner_scope=owner_scope,
                        conversation_scope=conversation_scope,
                        privacy_scope=privacy_scope,
                        trust_level=trust_level,
                    )
                )
                current_chunk = [p_clean]
                current_len = len(p_clean)
                chunk_line_start = line_num
            else:
                current_chunk.append(p_clean)
                current_len += len(p_clean)

            line_num += p.count("\n") + 2

        if current_chunk:
            content_str = "\n\n".join(current_chunk)
            chash = hashlib.sha256(content_str.encode("utf-8")).hexdigest()[:12]
            chunks.append(
                KnowledgeChunk(
                    chunk_id=f"chk_{chash}",
                    collection_id=collection_id,
                    file_path=file_path,
                    section_title=curr_title,
                    line_start=chunk_line_start,
                    line_end=line_num,
                    content=content_str,
                    content_hash=chash,
                    owner_scope=owner_scope,
                    conversation_scope=conversation_scope,
                    privacy_scope=privacy_scope,
                    trust_level=trust_level,
                )
            )

        return chunks
