import math
from pathlib import Path
import sqlite3
import time
from typing import Any
from jarvis.memory.search.cache import SearchHotCache
from jarvis.memory.search.models import MatchReason, SearchQuery, SearchResponse, SearchResult
from jarvis.memory.search.query_parser import parse_search_query
from jarvis.memory.search.ranking import rerank_search_results
from jarvis.memory.search.vector.base import VectorStore
from jarvis.memory.search.vector.embeddings import EmbeddingProvider, MockEmbeddingProvider, QueryEmbeddingCache
from jarvis.memory.working_memory import WorkingMemory

class SearchEngine:
    """Ultra-fast, cascaded file search engine backed by SQLite FTS5 and optional VectorStore."""
    def __init__(
        self,
        db_path: Path | str,
        hot_cache: SearchHotCache | None = None,
        working_memory: WorkingMemory | None = None,
        vector_store: VectorStore | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ):
        self.db_path = str(db_path)
        self.cache = hot_cache or SearchHotCache()
        self.memory = working_memory or WorkingMemory()
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.query_embedding_cache = QueryEmbeddingCache()
        self.total_searches = 0
        self.lexical_latencies: list[float] = []
        self.semantic_latencies: list[float] = []
        self._conn: sqlite3.Connection | None = None

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            con = sqlite3.connect(self.db_path, check_same_thread=False)
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA busy_timeout=3000")
            con.execute("PRAGMA query_only=ON")
            try:
                con.execute("PRAGMA mmap_size=268435456")
                con.execute("PRAGMA cache_size=-64000")
                con.execute("PRAGMA temp_store=MEMORY")
            except Exception:
                pass
            self._conn = con
        return self._conn

    def close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    async def search(self, raw_or_query: str | SearchQuery) -> SearchResponse:
        t0 = time.perf_counter_ns()
        breakdown: dict[str, float] = {}

        # 1. Parse Query
        t_parse_0 = time.perf_counter_ns()
        if isinstance(raw_or_query, str):
            query = parse_search_query(raw_or_query)
        else:
            query = raw_or_query
        breakdown["query_parse_ms"] = (time.perf_counter_ns() - t_parse_0) / 1e6

        # 2. LEVEL 0: Hot Cache Lookup (< 0.5 ms)
        t_cache_0 = time.perf_counter_ns()
        cached = self.cache.get(query)
        breakdown["cache_lookup_ms"] = (time.perf_counter_ns() - t_cache_0) / 1e6
        if cached is not None:
            tot_ms = (time.perf_counter_ns() - t0) / 1e6
            self.total_searches += 1
            is_ambig = len(cached) >= 2 and (cached[0].score - cached[1].score) < 0.04
            clarify = None
            if is_ambig:
                clarify = f"Found {len(cached)} close matches: " + ", ".join(f"{r.name} ({r.path})" for r in cached[:3])
            return SearchResponse(
                results=cached,
                search_mode="HOT_CACHE",
                semantic_used=False,
                latency_ms=tot_ms,
                is_ambiguous=is_ambig,
                clarification=clarify,
                breakdown_ms=breakdown,
            )

        # 3. LEVEL 1: Context Reference Resolution (< 1 ms)
        t_ctx_0 = time.perf_counter_ns()
        if query.context_reference:
            resolved = self.memory.resolve_reference(query.raw_query)
            breakdown["context_lookup_ms"] = (time.perf_counter_ns() - t_ctx_0) / 1e6
            if resolved is not None:
                tot_ms = (time.perf_counter_ns() - t0) / 1e6
                self.total_searches += 1
                if isinstance(resolved, SearchResult):
                    return SearchResponse(
                        results=[resolved],
                        search_mode="CONTEXT",
                        latency_ms=tot_ms,
                        breakdown_ms=breakdown,
                    )
                # Resolved is a path string (e.g. folder or last opened file)
                p = Path(resolved)
                res = SearchResult(
                    file_id=0,
                    path=str(p),
                    name=p.name,
                    extension=p.suffix.casefold() if p.is_file() else "[directory]",
                    score=1.0,
                    confidence=1.0,
                    match_reasons=[MatchReason.CONTEXT_REFERENCE.value],
                )
                return SearchResponse(
                    results=[res],
                    search_mode="CONTEXT",
                    latency_ms=tot_ms,
                    breakdown_ms=breakdown,
                )

        con = self._get_connection()

        # 4. LEVEL 2: Exact Filename Metadata Lookup (< 2 ms)
        t_exact_0 = time.perf_counter_ns()
        exact_candidates = []
        clean_text = query.text.strip().casefold()
        raw_clean = query.raw_query.strip().casefold()
        if clean_text or raw_clean:
            try:
                cur = con.execute(
                    """
                    SELECT id, path, name, name_norm, stem, extension, size_bytes, modified_ns, open_count, last_opened_ns
                    FROM files INDEXED BY idx_files_name_norm WHERE name_norm = ? AND is_available = 1
                    UNION ALL
                    SELECT id, path, name, name_norm, stem, extension, size_bytes, modified_ns, open_count, last_opened_ns
                    FROM files INDEXED BY idx_files_stem WHERE stem = ? AND is_available = 1
                    LIMIT 5
                    """,
                    (raw_clean, clean_text),
                )
                for row in cur.fetchall():
                    exact_candidates.append(dict(row))
            except sqlite3.OperationalError:
                try:
                    cur = con.execute(
                        """
                        SELECT id, path, name, name_norm, stem, extension, size_bytes, modified_ns, open_count, last_opened_ns
                        FROM files WHERE name_norm = ? AND is_available = 1
                        UNION ALL
                        SELECT id, path, name, name_norm, stem, extension, size_bytes, modified_ns, open_count, last_opened_ns
                        FROM files WHERE stem = ? AND is_available = 1
                        LIMIT 5
                        """,
                        (raw_clean, clean_text),
                    )
                    for row in cur.fetchall():
                        exact_candidates.append(dict(row))
                except Exception:
                    pass
            except Exception:
                pass
        breakdown["exact_lookup_ms"] = (time.perf_counter_ns() - t_exact_0) / 1e6

        if exact_candidates and not query.semantic and not query.temporal_hint:
            # If type_hint requested, check if any matches
            if not query.type_hint or any(c.get("extension") == query.type_hint.casefold() for c in exact_candidates):
                reranked, is_ambig, clarify = rerank_search_results(
                    exact_candidates, query, context_file_ids=self.memory.get_context_file_ids()
                )
                tot_ms = (time.perf_counter_ns() - t0) / 1e6
                self.cache.put(query, reranked)
                self.memory.record_search(query, reranked)
                self.total_searches += 1
                return SearchResponse(
                    results=reranked,
                    search_mode="EXACT_METADATA",
                    latency_ms=tot_ms,
                    is_ambiguous=is_ambig,
                    clarification=clarify,
                    breakdown_ms=breakdown,
                )

        # 5. LEVEL 3: FTS5 Lexical Filename & Path Search (< 10 ms)
        t_fts_0 = time.perf_counter_ns()
        candidates: list[dict] = []
        tokens = query.tokens or ([clean_text] if clean_text else [])

        if not tokens and query.type_hint:
            # Type-only query (e.g. "show python scripts", "find pdfs")
            try:
                cur = con.execute(
                    """
                    SELECT id, path, name, name_norm, stem, extension, size_bytes,
                           modified_ns, open_count, last_opened_ns
                    FROM files
                    WHERE extension = ? AND is_available = 1
                    ORDER BY open_count DESC, modified_ns DESC
                    LIMIT 20
                    """,
                    (query.type_hint.casefold(),),
                )
                for row in cur.fetchall():
                    d = dict(row)
                    d["is_content_match"] = False
                    candidates.append(d)
            except Exception:
                pass
        elif not tokens and query.temporal_hint:
            # Pure recency query (e.g. "show recent files")
            try:
                cur = con.execute(
                    """
                    SELECT id, path, name, name_norm, stem, extension, size_bytes,
                           modified_ns, open_count, last_opened_ns
                    FROM files
                    WHERE is_available = 1
                    ORDER BY modified_ns DESC, open_count DESC
                    LIMIT 20
                    """
                )
                for row in cur.fetchall():
                    d = dict(row)
                    d["is_content_match"] = False
                    candidates.append(d)
            except Exception:
                pass
        elif tokens:
            fts_clauses = []
            for t in tokens:
                t_esc = t.replace('"', '""')
                fts_clauses.append(f'(name:"{t_esc}"* OR stem:"{t_esc}"* OR path_tokens:"{t_esc}"*)')
            fts_match_expr = " AND ".join(fts_clauses)

            try:
                # BM25 column weighting: name 10.0, stem 5.0, path_tokens 2.0, content 1.0
                cur = con.execute(
                    """
                    SELECT f.id, f.path, f.name, f.name_norm, f.stem, f.extension, f.size_bytes,
                           f.modified_ns, f.open_count, f.last_opened_ns,
                           bm25(files_fts, 10.0, 5.0, 2.0, 1.0) AS bm25_score
                    FROM files_fts
                    JOIN files f ON f.id = files_fts.file_id
                    WHERE files_fts MATCH ? AND f.is_available = 1
                    ORDER BY bm25_score ASC
                    LIMIT 20
                    """,
                    (fts_match_expr,),
                )
                for row in cur.fetchall():
                    d = dict(row)
                    d["is_content_match"] = False
                    candidates.append(d)
            except sqlite3.OperationalError:
                pass

        if not candidates and tokens:
            # Fuzzy / Typo Fallback on filename
            typo_clauses = []
            for t in tokens:
                t_esc = t.replace('"', '""')
                if len(t) > 3 and t[-1] == t[-2]:
                    # Doubled character at end: e.g. nlpp -> nlp
                    t_fix = t_esc[:-1]
                    typo_clauses.append(f'(name:"{t_fix}"* OR stem:"{t_fix}"*)')
                elif len(t) >= 6:
                    # Truncate end typos: e.g. calclator -> calc*, documnt -> docum*
                    t_prefix = t_esc[:4]
                    typo_clauses.append(f'(name:"{t_prefix}"* OR stem:"{t_prefix}"*)')
            if typo_clauses:
                typo_expr = " AND ".join(typo_clauses)
                try:
                    cur = con.execute(
                        """
                        SELECT f.id, f.path, f.name, f.name_norm, f.stem, f.extension, f.size_bytes,
                               f.modified_ns, f.open_count, f.last_opened_ns,
                               bm25(files_fts, 10.0, 5.0, 2.0, 1.0) AS bm25_score
                        FROM files_fts
                        JOIN files f ON f.id = files_fts.file_id
                        WHERE files_fts MATCH ? AND f.is_available = 1
                        ORDER BY bm25_score ASC
                        LIMIT 20
                        """,
                        (typo_expr,),
                    )
                    for row in cur.fetchall():
                        d = dict(row)
                        d["is_content_match"] = False
                        candidates.append(d)
                except sqlite3.OperationalError:
                    pass
        breakdown["fts_ms"] = (time.perf_counter_ns() - t_fts_0) / 1e6

        # 6. LEVEL 4: FTS5 Content Search (for semantic queries or descriptive queries)
        t_content_0 = time.perf_counter_ns()
        should_search_content = query.semantic or (not candidates and not query.type_hint and len(tokens) >= 1)
        if should_search_content and tokens:
            content_clauses = [f'content:"{t.replace(chr(34), chr(34)+chr(34))}"' for t in tokens]
            content_match_expr = " OR ".join(content_clauses)
            try:
                cur = con.execute(
                    """
                    SELECT f.id, f.path, f.name, f.name_norm, f.stem, f.extension, f.size_bytes,
                           f.modified_ns, f.open_count, f.last_opened_ns,
                           fc.content_excerpt,
                           bm25(files_fts, 1.0, 1.0, 1.0, 5.0) AS bm25_score
                    FROM files_fts
                    JOIN files f ON f.id = files_fts.file_id
                    LEFT JOIN file_content fc ON fc.file_id = f.id
                    WHERE files_fts MATCH ? AND f.is_available = 1
                    ORDER BY bm25_score ASC
                    LIMIT 10
                    """,
                    (content_match_expr,),
                )
                seen_cids = {c["id"] for c in candidates}
                for row in cur.fetchall():
                    d = dict(row)
                    if d["id"] not in seen_cids:
                        d["is_content_match"] = True
                        d["excerpt"] = row["content_excerpt"]
                        candidates.append(d)
            except sqlite3.OperationalError:
                pass
        breakdown["content_fts_ms"] = (time.perf_counter_ns() - t_content_0) / 1e6

        # 7. LEVEL 5: Semantic Search Gate
        semantic_used = False
        semantic_state = "READY"
        semantic_ranks: dict[int, int] = {}
        # Gate triggers only if query is descriptive or lexical results are empty/weak
        should_use_semantic = query.semantic or (len(candidates) == 0 and len(clean_text) > 3)

        if should_use_semantic:
            if self.vector_store is not None and self.embedding_provider is not None:
                t_sem_0 = time.perf_counter_ns()
                try:
                    # Check Query Embedding Cache
                    q_vec = self.query_embedding_cache.get(clean_text)
                    if q_vec is None:
                        t_emb_0 = time.perf_counter_ns()
                        q_vec = await self.embedding_provider.embed(clean_text)
                        breakdown["embedding_ms"] = (time.perf_counter_ns() - t_emb_0) / 1e6
                        self.query_embedding_cache.put(clean_text, q_vec)

                    t_vec_0 = time.perf_counter_ns()
                    vector_results = self.vector_store.search(q_vec, limit=10)
                    breakdown["vector_search_ms"] = (time.perf_counter_ns() - t_vec_0) / 1e6

                    for sem_rank, (fid, sim) in enumerate(vector_results, 1):
                        semantic_ranks[fid] = sem_rank

                    # Ingest missing semantic candidate metadata
                    missing_fids = [fid for fid, _ in vector_results if fid not in {c["id"] for c in candidates}]
                    if missing_fids:
                        placeholders = ",".join("?" * len(missing_fids))
                        with self._get_connection() as con:
                            cur = con.execute(
                                f"SELECT id, path, name, name_norm, stem, extension, size_bytes, modified_ns, open_count, last_opened_ns "
                                f"FROM files WHERE id IN ({placeholders}) AND is_available = 1",
                                missing_fids,
                            )
                            for row in cur.fetchall():
                                candidates.append(dict(row))

                    semantic_used = True
                    breakdown["semantic_total_ms"] = (time.perf_counter_ns() - t_sem_0) / 1e6
                    self.semantic_latencies.append(breakdown["semantic_total_ms"])
                except Exception:
                    semantic_used = False
                    semantic_state = "UNAVAILABLE"
            else:
                semantic_used = False
                semantic_state = "UNAVAILABLE"

        # 8. LEVEL 6: Hybrid Reranking & Ambiguity Gate
        t_rank_0 = time.perf_counter_ns()
        reranked, is_ambig, clarify = rerank_search_results(
            candidates,
            query,
            semantic_ranks=semantic_ranks,
            context_file_ids=self.memory.get_context_file_ids(),
        )
        breakdown["rerank_ms"] = (time.perf_counter_ns() - t_rank_0) / 1e6

        tot_ms = (time.perf_counter_ns() - t0) / 1e6
        self.lexical_latencies.append(tot_ms)
        self.total_searches += 1

        # Cache valid results
        if reranked:
            self.cache.put(query, reranked)
            self.memory.record_search(query, reranked)

        mode = "HYBRID" if semantic_used else ("CONTENT_FTS" if any(c.get("is_content_match") for c in candidates) else "LEXICAL_FTS")

        return SearchResponse(
            results=reranked,
            search_mode=mode,
            semantic_used=semantic_used,
            semantic_state=semantic_state,
            latency_ms=tot_ms,
            is_ambiguous=is_ambig,
            clarification=clarify,
            breakdown_ms=breakdown,
        )
