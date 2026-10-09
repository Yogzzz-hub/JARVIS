"""Lock the Blind-12 set: copy it in once, record its hash and counts, refuse to overwrite a locked set.

    python -m tests.blind12.lock <generated cases.jsonl> --expect-sha <pre-lock sha256> --candidate <git sha>
    python -m tests.blind12.lock --verify          # the locked file still matches MANIFEST.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases.jsonl"
MANIFEST = HERE / "MANIFEST.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> int:
    m = json.loads(MANIFEST.read_text())
    got = sha256(CASES)
    print(("OK" if got == m["sha256"] else "MISMATCH") + f" {got}")
    return 0 if got == m["sha256"] else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", nargs="?")
    ap.add_argument("--expect-sha")
    ap.add_argument("--candidate", default="")
    ap.add_argument("--tag", default="jarvis-blind12-candidate")
    ap.add_argument("--generated-at", default="")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    if a.verify:
        return verify()
    if MANIFEST.exists() or CASES.exists():
        print("Blind-12 is already locked - it is never replaced or edited.")
        return 1
    src = Path(a.source)
    digest = sha256(src)
    if a.expect_sha and digest != a.expect_sha:
        print(f"hash {digest} is not the pre-lock hash {a.expect_sha} - refusing to lock")
        return 1
    shutil.copyfile(src, CASES)
    cases = [json.loads(line) for line in CASES.read_text().splitlines() if line.strip()]
    manifest = {
        "name": "Blind-12",
        "sha256": sha256(CASES),
        "locked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_at": a.generated_at,
        "cases": len(cases),
        "phases": dict(sorted(Counter(c["phase"] for c in cases).items())),
        "outcomes": dict(sorted(Counter(c["outcome"] for c in cases).items())),
        "categories": dict(sorted(Counter(c.get("category", "") for c in cases).items())),
        "criticality": dict(sorted(Counter(c.get("criticality", "") for c in cases).items())),
        "with_context": sum(1 for c in cases if c.get("context")),
        "executed_file": sum(1 for c in cases if (c.get("exec") or {}).get("kind") == "file"),
        "executed_browser": sum(1 for c in cases if (c.get("exec") or {}).get("kind") == "browser"),
        "candidate_commit": a.candidate,
        "candidate_tag": a.tag,
        "rules": [
            "Written by an independent generator session that never saw JARVIS's router code, tests or earlier blind sets; "
            "a novelty check against every existing test and doc phrase ran before the lock.",
            "No case is edited after the first run. Oracle mistakes go to docs/BLIND12_ORACLE_ERRATA.md and errata.json; "
            "strict and audited scores are both reported.",
            "JARVIS is not changed after the first run. Any later fix makes Blind-12 development data; the next unseen "
            "benchmark is Blind-12.",
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=1) + "\n")
    print(json.dumps(manifest, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
