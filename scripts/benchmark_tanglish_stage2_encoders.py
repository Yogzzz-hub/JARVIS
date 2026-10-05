"""Read-only pretrained encoder retrieval baseline on Stage-2 development rows.

This compares action-neighbor retrieval, not command safety or capability routing.
The locked holdout is never read.
"""

import json
import random
import time

import numpy as np
import truststore

from scripts.build_tanglish_semantic_stage2 import BASE
from scripts.train_tanglish_semantic_stage2 import input_text, read


def sample(split, count, seed):
    rng = random.Random(seed)
    result = []
    for index, row in enumerate(read(split)):
        if len(result) < count:
            result.append(row)
        else:
            chosen = rng.randrange(index + 1)
            if chosen < count:
                result[chosen] = row
    return result


def evaluate(name, model, train, dev):
    t = time.perf_counter()
    vectors = np.asarray(list(model.embed([input_text(r) for r in train + dev], batch_size=64)), dtype=np.float32)
    seconds = time.perf_counter() - t
    vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)
    sims = vectors[len(train):] @ vectors[:len(train)].T
    top = np.argsort(-sims, axis=1)[:, :5]
    gold = [r["semantic_frame"]["action_concept"] for r in dev]
    labels = [r["semantic_frame"]["action_concept"] for r in train]
    return {"model": name, "train_neighbors": len(train), "dev_queries": len(dev),
            "recall_at_1": sum(labels[ids[0]] == y for ids, y in zip(top, gold)) / len(gold),
            "recall_at_3": sum(y in [labels[i] for i in ids[:3]] for ids, y in zip(top, gold)) / len(gold),
            "recall_at_5": sum(y in [labels[i] for i in ids] for ids, y in zip(top, gold)) / len(gold),
            "embed_seconds": seconds, "embed_ms_per_row_bulk": seconds * 1000 / len(vectors),
            "embedding_dim": vectors.shape[1]}


def main():
    truststore.inject_into_ssl()
    from fastembed import TextEmbedding
    from jarvis.decision.encoder import HashingEncoder
    train = sample("train", 1200, 913)
    dev = sample("dev", 300, 914)
    models = [
        ("sentence-transformers/all-MiniLM-L6-v2", "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"),
        ("BAAI/bge-small-en-v1.5", "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"),
    ]
    results = {"scope": "Untrained nearest-neighbor action retrieval; 1200 sampled train index / 300 dev queries, same samples across models",
               "locked_holdout_used": False, "models": []}
    class JDEEmbeddingAdapter:
        def __init__(self):
            self.encoder = HashingEncoder()

        def embed(self, texts, batch_size=64):
            yield from self.encoder.encode(texts)

    results["models"].append(evaluate("JDE hash-4096 encoder", JDEEmbeddingAdapter(), train, dev))
    for name, source_revision in models:
        try:
            model = TextEmbedding(model_name=name, cache_dir="models/tanglish_stage2/encoders", threads=4)
            entry = evaluate(name, model, train, dev)
            entry["source_hub_revision_checked"] = source_revision
            entry["revision_pin_note"] = "FastEmbed-managed model cache; Hub revision checked separately, cache contents not revision-pinned"
            results["models"].append(entry)
            print(name, entry["recall_at_1"], flush=True)
        except Exception as error:
            results["models"].append({"model": name, "error": f"{type(error).__name__}: {str(error)[:300]}"})
            print(name, "unavailable", flush=True)
    (BASE / "manifests/semantic_stage2_encoder_benchmark.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
