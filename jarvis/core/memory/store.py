"""SQLite layered memory store with FTS5 lexical search and optional VectorStore support."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple

from jarvis.core.memory.models import (
    EpisodeRecord,
    MemoryConfidence,
    MemoryItem,
    MemoryLayer,
    MemoryProvenance,
    MemoryQuery,
    MemoryQueryResult,
    MemorySourceType,
    MemoryStatus,
)


class VectorStoreProtocol(Protocol):
    """Protocol for optional vector search backend."""
    def embed_and_store(self, item_id: str, text: str) -> None: ...
    def search(self, query_text: str, top_k: int = 5) -> List[Tuple[str, float]]: ...
    def delete(self, item_id: str) -> None: ...


class MemoryStoreProtocol(Protocol):
    """Protocol for memory store implementations."""
    def store(self, item: MemoryItem, resolve_conflicts: bool = True) -> str: ...
    def get_by_id(self, memory_id: str) -> Optional[MemoryItem]: ...
    def get_exact(self, key: str, kind: Optional[str] = None) -> Optional[MemoryItem]: ...
    def search_fts(self, query_text: str, limit: int = 10) -> List[MemoryQueryResult]: ...
    def query(self, query: MemoryQuery) -> List[MemoryQueryResult]: ...
    def delete(self, memory_id: str) -> bool: ...



class SQLiteMemoryStore:
    """
    Robust SQLite-backed memory store providing:
    - Structured key-value lookups (p95 < 3 ms)
    - Full-text search over keys and values using FTS5 (p95 < 10 ms)
    - Conflict resolution with superseding provenance tracking
    - TTL expiry enforcement and decay classes
    - Optional vector search backend with graceful lexical fallback
    """

    def __init__(
        self,
        db_path: str | Path,
        vector_store: Optional[VectorStoreProtocol] = None,
    ):
        self.db_path = str(db_path)
        self.vector_store = vector_store
        self._ensure_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_tables(self):
        with self._get_connection() as conn:
            # Apply migration 006 if not already present
            migration_file = Path(__file__).resolve().parent.parent.parent / "db/migrations/006_phase12_intelligence.sql"
            if migration_file.exists():
                try:
                    conn.executescript(migration_file.read_text(encoding="utf-8"))
                except sqlite3.OperationalError:
                    pass  # already created

    def store(
        self,
        item: MemoryItem,
        resolve_conflicts: bool = True,
    ) -> str:
        """Stores a memory item, handling superseding and updating FTS5 index."""
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check for existing active items with same key and kind to resolve conflicts
            if resolve_conflicts:
                cursor.execute(
                    """
                    SELECT memory_id FROM memory_items
                    WHERE key = ? AND kind = ? AND status = 'ACTIVE'
                    """,
                    (item.key, item.kind),
                )
                existing_rows = cursor.fetchall()
                for row in existing_rows:
                    old_id = row["memory_id"]
                    if old_id != item.memory_id:
                        cursor.execute(
                            "UPDATE memory_items SET status = 'SUPERSEDED' WHERE memory_id = ?",
                            (old_id,),
                        )
                        item.provenance.supersedes_id = old_id

            val_json = json.dumps(item.value)
            cursor.execute(
                """
                INSERT OR REPLACE INTO memory_items (
                    memory_id, layer, kind, key, value_json, source_type,
                    source_reference, confidence, created_at, last_used,
                    last_verified, use_count, successful_use_count,
                    correction_count, expires_at, supersedes_id, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.memory_id,
                    item.layer.value,
                    item.kind,
                    item.key,
                    val_json,
                    item.provenance.source_type.value,
                    item.provenance.source_reference,
                    item.confidence.value,
                    item.created_at,
                    item.last_used,
                    item.provenance.last_verified,
                    item.use_count,
                    item.successful_use_count,
                    item.correction_count,
                    item.expires_at,
                    item.provenance.supersedes_id,
                    item.status.value,
                ),
            )

            # Update FTS5 index
            cursor.execute("DELETE FROM memory_items_fts WHERE memory_id = ?", (item.memory_id,))
            cursor.execute(
                """
                INSERT INTO memory_items_fts (memory_id, key, value_text, kind, source_type)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    item.memory_id,
                    item.key,
                    item.to_text_for_search(),
                    item.kind,
                    item.provenance.source_type.value,
                ),
            )
            conn.commit()

        # Optional vector embedding in background
        if self.vector_store is not None:
            try:
                self.vector_store.embed_and_store(item.memory_id, item.to_text_for_search())
            except Exception:
                pass  # Vector store error never blocks core store

        return item.memory_id

    def get_by_id(self, memory_id: str) -> Optional[MemoryItem]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memory_items WHERE memory_id = ?", (memory_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_item(row)

    def get_exact(self, key: str, kind: Optional[str] = None) -> Optional[MemoryItem]:
        """Ultra-fast exact structured lookup by key and optional kind."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM memory_items WHERE key = ? AND status = 'ACTIVE'"
            params = [key]
            if kind:
                query += " AND kind = ?"
                params.append(kind)
            query += " ORDER BY created_at DESC LIMIT 1"
            cursor.execute(query, params)
            row = cursor.fetchone()
            if not row:
                return None
            item = self._row_to_item(row)
            if item.is_expired():
                return None
            return item

    def search_fts(self, query_text: str, limit: int = 10) -> List[MemoryQueryResult]:
        """FTS5 lexical search over memory items."""
        clean_query = "".join(c if c.isalnum() or c in " *_" else " " for c in query_text).strip()
        if not clean_query:
            return []

        results: List[MemoryQueryResult] = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    SELECT m.*, rank
                    FROM memory_items_fts f
                    JOIN memory_items m ON f.memory_id = m.memory_id
                    WHERE memory_items_fts MATCH ? AND m.status = 'ACTIVE'
                    ORDER BY rank LIMIT ?
                    """,
                    (clean_query, limit),
                )
                now = time.time()
                for row in cursor.fetchall():
                    item = self._row_to_item(row)
                    if not item.is_expired(now):
                        # FTS5 rank is lower (more negative) for better matches
                        score = max(0.1, min(1.0, 1.0 / (1.0 + abs(float(row["rank"])))))
                        results.append(MemoryQueryResult(item=item, relevance_score=score, match_method="FTS"))
            except sqlite3.OperationalError:
                pass  # Fallback gracefully
        return results

    def query(self, query: MemoryQuery) -> List[MemoryQueryResult]:
        """Cascade retrieval: Structured/exact -> FTS -> optional Vector."""
        results: List[MemoryQueryResult] = []
        seen_ids = set()

        # 1. Exact key match if key provided
        if query.key:
            exact = self.get_exact(query.key, kind=query.kind)
            if exact:
                results.append(MemoryQueryResult(item=exact, relevance_score=1.0, match_method="EXACT"))
                seen_ids.add(exact.memory_id)

        # 2. FTS search if text query provided
        if query.query_text:
            fts_results = self.search_fts(query.query_text, limit=query.limit)
            for r in fts_results:
                if r.item.memory_id not in seen_ids:
                    results.append(r)
                    seen_ids.add(r.item.memory_id)

        # 3. Optional Vector search fallback if FTS yielded few results
        if len(results) < query.limit and self.vector_store is not None and query.query_text:
            try:
                vec_hits = self.vector_store.search(query.query_text, top_k=query.limit)
                for item_id, sim_score in vec_hits:
                    if item_id not in seen_ids:
                        item = self.get_by_id(item_id)
                        if item and item.status == MemoryStatus.ACTIVE and not item.is_expired():
                            results.append(MemoryQueryResult(item=item, relevance_score=sim_score, match_method="SEMANTIC"))
                            seen_ids.add(item_id)
            except Exception:
                pass  # Vector failure never breaks search

        return results[:query.limit]

    def record_usage(self, memory_id: str, success: bool = True):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if success:
                cursor.execute(
                    """
                    UPDATE memory_items
                    SET last_used = ?, use_count = use_count + 1, successful_use_count = successful_use_count + 1
                    WHERE memory_id = ?
                    """,
                    (time.time(), memory_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE memory_items
                    SET last_used = ?, use_count = use_count + 1, correction_count = correction_count + 1
                    WHERE memory_id = ?
                    """,
                    (time.time(), memory_id),
                )
            conn.commit()

    def record_episode(self, episode: EpisodeRecord):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO episodes (
                    episode_id, timestamp, request_id, normalized_goal,
                    tools_used_json, resources_json, outcome, verified,
                    duration_ms, user_correction, tags_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    episode.episode_id,
                    episode.timestamp,
                    episode.request_id,
                    episode.normalized_goal,
                    json.dumps(episode.tools_used),
                    json.dumps(episode.resources),
                    episode.outcome,
                    1 if episode.verified else 0,
                    episode.duration_ms,
                    episode.user_correction,
                    json.dumps(episode.tags),
                ),
            )
            cursor.execute("DELETE FROM episodes_fts WHERE episode_id = ?", (episode.episode_id,))
            cursor.execute(
                """
                INSERT INTO episodes_fts (episode_id, normalized_goal, user_correction, tags)
                VALUES (?, ?, ?, ?)
                """,
                (
                    episode.episode_id,
                    episode.normalized_goal,
                    episode.user_correction or "",
                    " ".join(episode.tags),
                ),
            )
            conn.commit()

    def cleanup_expired(self) -> int:
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE memory_items SET status = 'EXPIRED' WHERE status = 'ACTIVE' AND expires_at IS NOT NULL AND expires_at <= ?",
                (now,),
            )
            count = cursor.rowcount
            conn.commit()
            return count

    def delete(self, memory_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memory_items WHERE memory_id = ?", (memory_id,))
            cursor.execute("DELETE FROM memory_items_fts WHERE memory_id = ?", (memory_id,))
            conn.commit()
        if self.vector_store is not None:
            try:
                self.vector_store.delete(memory_id)
            except Exception:
                pass
        return True

    def list_active(self, layer: Optional[MemoryLayer] = None, limit: int = 100) -> List[MemoryItem]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM memory_items WHERE status = 'ACTIVE'"
            params = []
            if layer:
                query += " AND layer = ?"
                params.append(layer.value)
            query += " ORDER BY last_used DESC LIMIT ?"
            params.append(limit)
            cursor.execute(query, params)
            return [self._row_to_item(r) for r in cursor.fetchall()]

    def get_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM memory_items WHERE status = 'ACTIVE'")
            active_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM memory_items WHERE status = 'SUPERSEDED'")
            superseded_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM memory_items WHERE status = 'EXPIRED'")
            expired_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM episodes")
            episode_count = cursor.fetchone()[0]
            return {
                "active_memories": active_count,
                "superseded_memories": superseded_count,
                "expired_memories": expired_count,
                "episodes": episode_count,
            }

    def _row_to_item(self, row: sqlite3.Row) -> MemoryItem:
        val = json.loads(row["value_json"])
        provenance = MemoryProvenance(
            source_type=MemorySourceType(row["source_type"]),
            source_reference=row["source_reference"],
            created_at=row["created_at"] if isinstance(row["created_at"], (int, float)) else time.time(),
            last_verified=row["last_verified"],
            supersedes_id=row["supersedes_id"],
        )
        return MemoryItem(
            memory_id=row["memory_id"],
            layer=MemoryLayer(row["layer"]),
            kind=row["kind"],
            key=row["key"],
            value=val,
            provenance=provenance,
            confidence=MemoryConfidence(row["confidence"]),
            created_at=row["created_at"] if isinstance(row["created_at"], (int, float)) else time.time(),
            last_used=row["last_used"] if isinstance(row["last_used"], (int, float)) else time.time(),
            use_count=row["use_count"],
            successful_use_count=row["successful_use_count"],
            correction_count=row["correction_count"],
            expires_at=row["expires_at"],
            status=MemoryStatus(row["status"]),
        )
