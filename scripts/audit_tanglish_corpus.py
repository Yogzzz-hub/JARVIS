"""Exact, normalized, family and sampled lexical-neighbor leakage audit."""
from __future__ import annotations

import gzip
import json
import random
from collections import Counter
from pathlib import Path

from scripts.build_tanglish_corpus import normalized, skeleton


def rows(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def audit(root: Path) -> dict:
    splits = ("train", "dev", "test", "holdout", "locked_holdout_v3", "locked_holdout_v4", "locked_holdout_v5", "locked_holdout_v6")
    ids = {}
    structures = {}
    counts = {}
    samples = {}
    rng = random.Random(38)
    for split in splits:
        sample = []
        seen_ids = set()
        seen_structures = set()
        stats = Counter()
        for index, row in enumerate(rows(root / f"{split}.jsonl.gz"), 1):
            text = " ".join(row.get("previous_turns", []) + [row["text"]])
            seen_ids.add(row["id"])
            seen_structures.add(skeleton(text))
            stats["rows"] += 1
            stats["multi_turn"] += bool(row.get("previous_turns"))
            stats["no_action"] += row["frame"]["action"] is None
            stats[row.get("noise", "none")] += 1
            if len(sample) < (3000 if split == "train" else 500):
                sample.append(set(normalized(text).split()))
            else:
                at = rng.randrange(index)
                if at < len(sample):
                    sample[at] = set(normalized(text).split())
        ids[split], structures[split], counts[split], samples[split] = seen_ids, seen_structures, dict(stats), sample
    locked = "locked_holdout_v6"
    prior = set().union(*(ids[s] for s in splits if s != locked))
    prior_structures = set().union(*(structures[s] for s in splits if s != locked))
    similarities = []
    for case in samples[locked]:
        similarities.append(max((len(case & old) / max(1, len(case | old)) for old in samples["train"]), default=0.0))
    similarities.sort()
    return {"counts": counts, "normalized_exact_overlap_locked_prior": len(ids[locked] & prior),
            "unique_skeletons": {s: len(structures[s]) for s in splits},
            "skeleton_overlap_locked_prior": len(structures[locked] & prior_structures),
            "sampled_jaccard_locked_vs_train": {"locked_sample": len(samples[locked]),
                "train_sample": len(samples["train"]), "median_nearest": similarities[len(similarities) // 2],
                "p95_nearest": similarities[int(len(similarities) * .95)],
                "near_0_8_count": sum(x >= .8 for x in similarities)},
            "limitations": "Lexical Jaccard sample is not semantic paraphrase leakage detection; the corpus is synthetic."}


if __name__ == "__main__":
    root = Path("jarvis/tests/fixtures/tanglish_corpus")
    report = audit(root)
    output = Path("reports/tanglish_corpus_audit.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
