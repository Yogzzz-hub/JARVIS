"""Audit Stage-2 split isolation without publishing locked examples."""

import gzip
import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path

from scripts.build_tanglish_semantic_stage2 import BASE, FIELDS, NAMES, OBJECT_VARIANTS, ONTOLOGY, OUT, PROJECTS, SPLITS, normalized


def rows(split):
    with gzip.open(OUT / f"{split}.jsonl.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


_REPLACEMENTS = set(NAMES) | set(PROJECTS)
_REPLACEMENTS.update(x for options in OBJECT_VARIANTS.values() for x in options)
_REPLACEMENTS.update(x for _, typ, en, ta, alt in ONTOLOGY.values() for x in (typ, en, ta, alt))
_SKELETON_RE = re.compile(r"\b(?:" + "|".join(re.escape(x.casefold()) for x in sorted(_REPLACEMENTS, key=len, reverse=True)) + r")\b|\b\d+\b")


def skeleton(value):
    def replace(match):
        token = match.group()
        if token.isdigit():
            return "NUM"
        if token in {name.casefold() for name in NAMES}:
            return "PERSON"
        return "SLOT"
    return _SKELETON_RE.sub(replace, normalized(value))


def main():
    exact = {}
    structures = {}
    families = {}
    samples = {}
    counts = {}
    errors = Counter()
    rng = random.Random(1142)
    for split in SPLITS:
        ids, templates, fam, sample = set(), set(), set(), []
        stats = Counter()
        for index, row in enumerate(rows(split), 1):
            full = " ".join(row["previous_turns"] + [row["text"]])
            digest = hashlib.sha256(normalized(full).encode()).hexdigest()
            ids.add(digest)
            templates.add(skeleton(full))
            fam.add(row["construction_family"])
            stats["rows"] += 1
            stats["contextual"] += bool(row["previous_turns"])
            stats["no_action"] += not row["semantic_frame"]["should_act"]
            stats["asr_noise"] += row["category"] == "asr_noise"
            stats["negation"] += row["category"] == "negation"
            stats["correction"] += row["category"] == "correction"
            if set(row["semantic_frame"]) != set(FIELDS):
                errors["frame_schema"] += 1
            if row["semantic_frame"]["action_concept"] not in ONTOLOGY:
                errors["unknown_action"] += 1
            if row["public_text_copied"]:
                errors["public_text_copied"] += 1
            if split == "train":
                if len(sample) < 2000:
                    sample.append(set(normalized(full).split()))
                else:
                    chosen = rng.randrange(index)
                    if chosen < len(sample):
                        sample[chosen] = set(normalized(full).split())
            elif len(sample) < 300:
                sample.append(set(normalized(full).split()))
        exact[split], structures[split], families[split], samples[split], counts[split] = ids, templates, fam, sample, dict(stats)
    pairwise = {}
    keys = list(SPLITS)
    for i, left in enumerate(keys):
        for right in keys[i+1:]:
            pairwise[f"{left}:{right}"] = {"normalized_exact": len(exact[left] & exact[right]),
                                            "structural_skeleton": len(structures[left] & structures[right]),
                                            "construction_family": len(families[left] & families[right])}
    nearest = {}
    for split in ("dev", "test", "locked_holdout"):
        sims = sorted(max((len(a & b) / max(1, len(a | b)) for b in samples["train"]), default=0) for a in samples[split])
        nearest[split] = {"sample_rows": len(sims), "train_sample": len(samples["train"]),
                          "median": sims[len(sims)//2], "p95": sims[int(.95*len(sims))],
                          "ge_0_8": sum(x >= .8 for x in sims)}
    report = {"counts": counts, "unique_normalized": {s: len(exact[s]) for s in SPLITS},
              "unique_skeletons": {s: len(structures[s]) for s in SPLITS},
              "pairwise_overlap": pairwise, "sampled_nearest_token_jaccard": nearest,
              "label_integrity_errors": dict(errors),
              "caveat": "Structural and sampled lexical checks cannot prove semantic independence; this corpus is synthetic and lacks human adjudication."}
    path = BASE / "manifests/semantic_stage2_leakage.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    assert not errors, errors
    assert all(not any(pair.values()) for pair in pairwise.values()), pairwise
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
