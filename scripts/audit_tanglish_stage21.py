"""Audit Stage 2.1 train/dev exact overlap without opening test or holdout."""
from __future__ import annotations

import gzip
import json
import re
from collections import Counter

from scripts.build_tanglish_semantic_stage2 import BASE
from scripts.build_tanglish_stage21_repair import OUT


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        yield from (json.loads(line) for line in stream)


def normalized(row):
    return " ".join(re.findall(r"\w+", " [TURN] ".join(row["previous_turns"] + [row["text"]]).casefold()))


def main():
    old = BASE / "generated/semantic_stage2"
    train = list(rows(old / "train.jsonl.gz")) + list(rows(OUT / "train.jsonl.gz"))
    dev = list(rows(old / "dev.jsonl.gz")) + list(rows(OUT / "dev_no_action.jsonl.gz")) + list(rows(OUT / "dev_command.jsonl.gz"))
    train_set = {normalized(row) for row in train}
    dev_set = {normalized(row) for row in dev}
    report = {"train_rows": len(train), "train_unique_normalized": len(train_set),
              "dev_rows": len(dev), "dev_unique_normalized": len(dev_set),
              "normalized_train_dev_overlap": len(train_set & dev_set),
              "train_speech_distribution": dict(Counter(row.get("speech_act", row.get("semantic_frame", {}).get("speech_act")) for row in train)),
              "dev_speech_distribution": dict(Counter(row.get("speech_act", row.get("semantic_frame", {}).get("speech_act")) for row in dev)),
              "test_opened": False, "locked_holdout_opened": False}
    (OUT / "audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["normalized_train_dev_overlap"]:
        raise SystemExit("Normalized train/dev overlap found")


if __name__ == "__main__":
    main()
