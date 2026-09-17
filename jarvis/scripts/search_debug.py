import argparse
import asyncio
from pathlib import Path
import sys
import time

from jarvis.config import ROOT, Config, load
from jarvis.memory.search.cache import SearchHotCache
from jarvis.memory.search.engine import SearchEngine
from jarvis.memory.search.query_parser import parse_search_query
from jarvis.memory.search.vector.embeddings import MockEmbeddingProvider, OllamaEmbeddingProvider
from jarvis.memory.search.vector.sqlite_vec import SQLiteVecStore
from jarvis.memory.working_memory import WorkingMemory

async def debug_search(query_str: str, db_path: Path | None = None):
    db_file = db_path or (ROOT / "db/jarvis.db")
    print(f"\n[QUERY] '{query_str}'")
    
    # 1. Parse Query
    t0 = time.perf_counter_ns()
    parsed = parse_search_query(query_str)
    parse_ms = (time.perf_counter_ns() - t0) / 1e6
    print("\n--- Parsed Representation ---")
    print(f"  raw_query:         {parsed.raw_query}")
    print(f"  clean_text:        {parsed.text}")
    print(f"  type_hint:         {parsed.type_hint}")
    print(f"  temporal_hint:     {parsed.temporal_hint}")
    print(f"  latest:            {parsed.latest}")
    print(f"  context_reference: {parsed.context_reference}")
    print(f"  semantic:          {parsed.semantic}")
    print(f"  tokens:            {parsed.tokens}")
    print(f"  parse latency:     {parse_ms:.3f} ms")

    # 2. Initialize Engine
    cache = SearchHotCache()
    wm = WorkingMemory()
    vec_store = SQLiteVecStore(str(db_file))
    embedder = MockEmbeddingProvider()
    engine = SearchEngine(
        db_path=db_file,
        hot_cache=cache,
        working_memory=wm,
        vector_store=vec_store,
        embedding_provider=embedder,
    )

    # 3. Execute Search
    resp = await engine.search(parsed)

    print("\n--- Search Execution ---")
    print(f"  search_mode:       {resp.search_mode}")
    print(f"  semantic_used:     {resp.semantic_used}")
    print(f"  semantic_state:    {resp.semantic_state}")
    print(f"  total_latency:     {resp.latency_ms:.3f} ms")
    print(f"  is_ambiguous:      {resp.is_ambiguous}")
    if resp.clarification:
        print(f"  clarification:     {resp.clarification}")

    print("\n--- Latency Breakdown ---")
    for stage, ms in resp.breakdown_ms.items():
        print(f"  {stage:<20} {ms:7.3f} ms")

    print(f"\n--- Results ({len(resp.results)} candidates) ---")
    for i, r in enumerate(resp.results, 1):
        reasons = ", ".join(r.match_reasons)
        print(f"  [{i}] {r.name}")
        print(f"      path:        {r.path}")
        print(f"      score:       {r.score:.4f}  (confidence: {r.confidence:.2f})")
        print(f"      reasons:     {reasons}")
        if r.excerpt:
            print(f"      excerpt:     {r.excerpt[:80]}...")
    print()

def main():
    parser = argparse.ArgumentParser(description="JARVIS Search Debugger")
    parser.add_argument("query", help="Search query to inspect")
    parser.add_argument("--db", type=Path, default=None, help="Path to jarvis.db")
    args = parser.parse_args()

    asyncio.run(debug_search(args.query, args.db))

if __name__ == "__main__":
    main()
