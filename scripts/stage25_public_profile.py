"""Read-only profile of already audited public Tamil/Tanglish sources.

The output is lexical/distributional evidence only, never command labels.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from scripts.stage25_gold_data import OUT, ROOT

SEED_FORMS = {"அனுப்பு", "மாற்று", "கொடு", "காட்டு", "எடு", "போடு", "பார்"}


def profile() -> dict:
    base = ROOT / "data" / "tanglish" / "processed"
    trans = base / "aksharantar_tamil" / "train.jsonl"
    codemix = base / "dravidiancodemix" / "tamil_unique.jsonl"
    origins = Counter()
    roman = defaultdict(Counter)
    eligible = 0
    total = 0
    with trans.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            total += 1
            if not row.get("training_eligible"):
                continue
            eligible += 1
            origins[row["source"]] += 1
            if row["native"] in SEED_FORMS:
                roman[row["native"]][row["roman"]] += 1
    scripts = Counter()
    code_rows = 0
    with codemix.open(encoding="utf-8") as stream:
        for line in stream:
            text = json.loads(line)["text"]
            code_rows += 1
            tamil = bool(re.search(r"[\u0b80-\u0bff]", text))
            latin = bool(re.search(r"[A-Za-z]", text))
            scripts["both" if tamil and latin else "tamil_only" if tamil else "latin_only" if latin else "neither"] += 1
    with trans.open("rb") as handle:
        trans_sha = hashlib.file_digest(handle, "sha256").hexdigest()
    with codemix.open("rb") as handle:
        codemix_sha = hashlib.file_digest(handle, "sha256").hexdigest()
    return {
        "purpose": "lexical and script-distribution profile only; no command labels",
        "aksharantar_processed_train_sha256": trans_sha,
        "aksharantar_train_rows_read": total,
        "aksharantar_training_eligible": eligible,
        "eligible_origins": dict(origins),
        "seed_form_romanizations": {k: dict(v) for k, v in roman.items()},
        "dravidiancodemix_processed_sha256": codemix_sha,
        "dravidiancodemix_rows_read": code_rows,
        "script_distribution": dict(scripts),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    result = profile()
    (OUT / "public_profile.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
