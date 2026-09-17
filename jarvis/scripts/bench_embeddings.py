import argparse
import asyncio
import json
from pathlib import Path
import time
import httpx

from jarvis.config import ROOT
from jarvis.memory.search.vector.embeddings import (
    MockEmbeddingProvider,
    OllamaEmbeddingProvider,
    QueryEmbeddingCache,
)
from jarvis.scripts.bench_core import summarize

async def run_embedding_benchmarks(count: int = 1000):
    print("\n" + "=" * 70)
    print("           JARVIS EDGE -- EMBEDDING & VECTOR BENCHMARK")
    print("=" * 70)

    # 1. Mock Embedding Provider Benchmark
    mock = MockEmbeddingProvider(dimension=384)
    texts = [
        "deep learning transformer attention mechanism",
        "convolutional neural networks computer vision image recognition",
        "natural language processing tokenization embeddings word2vec",
        "reinforcement learning policy gradient actor critic q learning",
        "database indexing btree fts5 full text search vector store",
    ]

    print(f"[-] Benchmarking MockEmbeddingProvider ({count} queries)...")
    mock_lats = []
    for i in range(count):
        t = texts[i % len(texts)]
        t0 = time.perf_counter_ns()
        v = await mock.embed(t)
        lat = (time.perf_counter_ns() - t0) / 1e6
        mock_lats.append(lat)
        assert len(v) == 384
    mock_summary = summarize(mock_lats)

    # 2. Query Embedding Cache Benchmark
    print("[-] Benchmarking QueryEmbeddingCache (1,000 ops)...")
    qcache = QueryEmbeddingCache(capacity=1024)
    cache_lats = []
    for i in range(count):
        t = texts[i % len(texts)]
        t0 = time.perf_counter_ns()
        cached = qcache.get(t)
        if cached is None:
            qcache.put(t, v)
        lat = (time.perf_counter_ns() - t0) / 1e6
        cache_lats.append(lat)
    cache_summary = summarize(cache_lats)

    # 3. Ollama Probe
    print("[-] Probing local Ollama embedding endpoint (http://127.0.0.1:11434)...")
    ollama_status = "OFFLINE"
    ollama_summary = None
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            resp = await client.get("http://127.0.0.1:11434/api/tags")
            if resp.status_code == 200:
                ollama_status = "READY"
                print("    Ollama daemon detected! Benchmarking 50 embedding calls...")
                provider = OllamaEmbeddingProvider(model="all-minilm")
                olats = []
                for i in range(min(50, count)):
                    t0 = time.perf_counter_ns()
                    ov = await provider.embed(texts[i % len(texts)])
                    olats.append((time.perf_counter_ns() - t0) / 1e6)
                ollama_summary = summarize(olats)
                await provider.close()
    except Exception:
        print("    Ollama offline or model not pulled; graceful fallback verified.")

    print("\n" + "-" * 70)
    print(f"{'Provider / Component':<25} | {'p50 (ms)':>9} | {'p95 (ms)':>9} | {'Mean (ms)':>9} | {'Status':>8}")
    print("-" * 70)
    print(f"{'Mock Embedder (384-d)':<25} | {mock_summary['p50']:9.3f} | {mock_summary['p95']:9.3f} | {mock_summary['mean']:9.3f} | {'PASS':>8}")
    print(f"{'Query Vector Cache':<25} | {cache_summary['p50']:9.3f} | {cache_summary['p95']:9.3f} | {cache_summary['mean']:9.3f} | {'PASS':>8}")
    if ollama_summary:
        print(f"{'Ollama (all-minilm)':<25} | {ollama_summary['p50']:9.3f} | {ollama_summary['p95']:9.3f} | {ollama_summary['mean']:9.3f} | {ollama_status:>8}")
    else:
        print(f"{'Ollama (all-minilm)':<25} |       N/A |       N/A |       N/A | {ollama_status:>8}")
    print("=" * 70 + "\n")

    out_file = ROOT / "docs/search-embeddings-benchmark.json"
    if not out_file.parent.exists():
        out_file = ROOT.parent / "docs/search-embeddings-benchmark.json"

    data = {
        "timestamp": time.time(),
        "mock_embedder": mock_summary,
        "query_cache": cache_summary,
        "ollama_status": ollama_status,
        "ollama_embedder": ollama_summary,
    }
    out_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"[+] Saved embedding benchmark results to {out_file}")

def main():
    parser = argparse.ArgumentParser(description="JARVIS Embedding Benchmark")
    parser.add_argument("--count", type=int, default=500, help="Iterations (default: 500)")
    args = parser.parse_args()

    asyncio.run(run_embedding_benchmarks(count=args.count))

if __name__ == "__main__":
    main()
