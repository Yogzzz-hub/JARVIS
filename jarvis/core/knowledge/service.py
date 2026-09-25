"""Unified KnowledgeService for JARVIS EDGE.
Orchestrates file search, FTS document chunking, layered memory, and WhatsApp knowledge
under strict pre-ranking privacy scope filters and Reciprocal Rank Fusion (RRF).
"""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from jarvis.core.knowledge.engine import KnowledgeEngine
from jarvis.core.knowledge.models import (
    KnowledgeItem,
    KnowledgeScopeFilter,
    KnowledgeSourceType,
    TrustLevel,
)
from jarvis.memory.search.engine import SearchEngine
from jarvis.memory.working_memory import WorkingMemory

logger = logging.getLogger("jarvis.core.knowledge.service")


class KnowledgeService:
    """
    Conceptual ONE KnowledgeService.
    Unifies all retrieval sources (local files, project documents, RAG chunks,
    working memory, and WhatsApp multimodal material) under strict namespace scopes.
    """

    def __init__(
        self,
        knowledge_engine: KnowledgeEngine,
        search_engine: Optional[SearchEngine] = None,
        working_memory: Optional[WorkingMemory] = None,
        db_path: Optional[str | Path] = None,
        embedder: Any = None,
    ) -> None:
        self.knowledge_engine = knowledge_engine
        self.search_engine = search_engine
        self.working_memory = working_memory
        self.db_path = str(db_path) if db_path else knowledge_engine.db_path
        # Optional OllamaClient used for dense (embedding) retrieval; lexical search works without it.
        self.embedder = embedder
        self._embed_task: Optional[asyncio.Task] = None
        self._query_vectors: "OrderedDict[tuple[str, str], list[float]]" = OrderedDict()

    @property
    def engine(self) -> KnowledgeEngine:
        """Alias kept for integrations that refer to the engine by this name."""
        return self.knowledge_engine

    async def _query_vector(self, text: str) -> tuple[Optional[list[float]], Optional[str]]:
        """Embed the query when vectors exist for an available embedding model (bounded latency)."""
        if self.embedder is None:
            return None, None
        try:
            models = await asyncio.to_thread(self.knowledge_engine.vector_models)
            if not models:
                return None, None
            model = await asyncio.wait_for(self.embedder.resolve("embed"), 3.0)
            if model not in models:
                return None, None
            key = (model, " ".join(text.lower().split()))
            cached = self._query_vectors.get(key)
            if cached is not None:
                self._query_vectors.move_to_end(key)
                return cached, model
            vectors = await asyncio.wait_for(self.embedder.embed([text], model=model), 4.0)
            vector = vectors[0] if vectors else None
            if vector is not None:
                self._query_vectors[key] = vector
                while len(self._query_vectors) > 128:
                    self._query_vectors.popitem(last=False)
            return vector, model
        except Exception as exc:
            logger.debug("Query embedding unavailable: %s", exc)
            return None, None

    def schedule_embedding(self) -> None:
        """Embed newly indexed chunks in the background (no-op without an embedding model)."""
        if self.embedder is None or (self._embed_task and not self._embed_task.done()):
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        async def _run():
            try:
                count = await self.knowledge_engine.embed_pending(self.embedder)
                if count:
                    logger.info("Embedded %d knowledge chunks", count)
            except Exception as exc:
                logger.debug("Background embedding skipped: %s", exc)

        self._embed_task = loop.create_task(_run())

    async def ingest(self, path: str, collection_name: str = "My Documents") -> Dict[str, Any]:
        """Index a file or folder, then embed it in the background."""
        stats = await asyncio.to_thread(self.knowledge_engine.ingest_path, path, collection_name)
        self.schedule_embedding()
        return stats

    async def search_unified(
        self,
        query_text: str,
        scope_filter: KnowledgeScopeFilter,
        limit: int = 5,
        collection_name: Optional[str] = None,
    ) -> List[KnowledgeItem]:
        """
        Executes unified search across all eligible knowledge sources:
        1. Document chunks / RAG / WhatsApp indexed documents (via KnowledgeEngine)
        2. Local files / indexed filesystem (via SearchEngine)
        3. Working memory / recent interaction references
        Applies scope filtering strictly BEFORE ranking with Reciprocal Rank Fusion (RRF).
        """
        clean_query = query_text.strip()
        if not clean_query:
            return []

        candidates_by_source: Dict[str, List[KnowledgeItem]] = {
            "chunks": [],
            "files": [],
            "memory": [],
        }

        # 1. RAG Chunks and WhatsApp Ingested Documents (skipped outright while nothing is indexed)
        try:
            chunk_count = (await asyncio.to_thread(self.knowledge_engine.stats))[0]
        except Exception:
            chunk_count = 1
        try:
            if not chunk_count:
                raise LookupError("knowledge base is empty")
            query_vector, vector_model = await self._query_vector(clean_query)
            chunk_results = await asyncio.to_thread(
                self.knowledge_engine.search_hybrid,
                clean_query,
                query_vector,
                vector_model,
                collection_name,
                scope_filter,
                limit * 2,
            )
            candidates_by_source["chunks"] = chunk_results
        except Exception as e:
            logger.debug("Knowledge chunk search failed or empty: %s", e)

        # 2. Local Files & Projects Search (if scope permits scope:documents or scope:projects)
        can_access_files = any(s in scope_filter.allowed_scopes for s in ("scope:user", "scope:documents", "scope:projects"))
        if self.search_engine and can_access_files:
            try:
                search_res = await self.search_engine.search(clean_query)
                for r in search_res.results[: limit * 2]:
                    # Map to KnowledgeItem
                    p = Path(r.path)
                    is_project = any(marker in r.path.lower() for marker in ("github", "projects", "repo", "src"))
                    item_privacy = "scope:projects" if is_project else "scope:documents"
                    if item_privacy not in scope_filter.allowed_scopes and "scope:user" not in scope_filter.allowed_scopes:
                        continue

                    candidates_by_source["files"].append(
                        KnowledgeItem(
                            source_type=KnowledgeSourceType.LOCAL_FILES.value if not is_project else KnowledgeSourceType.PROJECTS.value,
                            resource_id=f"file_{r.file_id}",
                            title=r.name,
                            snippet=f"File: {r.path} (Match: {', '.join(r.match_reasons) if r.match_reasons else 'lexical'})",
                            relevance=float(r.score),
                            trust=TrustLevel.DATA_ONLY.value,
                            owner_scope="scope:user",
                            privacy_scope=item_privacy,
                            citation_metadata={"path": r.path, "extension": r.extension},
                        )
                    )
            except Exception as e:
                logger.debug("File search error: %s", e)

        # 3. Reciprocal Rank Fusion (RRF) Ranking
        rrf_scores: Dict[str, float] = {}
        item_lookup: Dict[str, KnowledgeItem] = {}
        k_const = 60.0

        for src_name, items in candidates_by_source.items():
            for rank, item in enumerate(items, start=1):
                # Extra safety check: Pre-ranking Scope Isolation Check
                item_scopes = item.get_all_scopes()
                if not scope_filter.is_accessible(item_scopes):
                    continue

                uid = f"{item.source_type}:{item.resource_id}"
                item_lookup[uid] = item
                rrf_scores[uid] = rrf_scores.get(uid, 0.0) + (1.0 / (k_const + rank))

        # Sort by fused score descending
        sorted_keys = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)
        final_results: List[KnowledgeItem] = []

        for k in sorted_keys[:limit]:
            it = item_lookup[k]
            # Normalize relevance to 0.0 - 1.0 based on relative rank
            it.relevance = min(1.0, max(0.1, rrf_scores[k] * 30.0))
            final_results.append(it)

        return final_results
