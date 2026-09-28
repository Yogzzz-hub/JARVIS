"""Route-family accuracy of the decision model (JDE) on the phase suite splits.

    python -m tests.phase_suite.jde_eval                      # current model, every split
    python -m tests.phase_suite.jde_eval --model models/jde/<version>
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def family_accuracy(engine, rows: list[dict]) -> tuple[float, int, Counter]:
    from jarvis.decision.dataset import phase_suite_family
    ok, n, misses = 0, 0, Counter()
    for r in rows:
        allowed = {phase_suite_family(opt) for opt in r["expect"].split("|")} - {None}
        if not allowed:
            continue
        n += 1
        got = engine.decide(r["text"]).route.value
        if got in allowed:
            ok += 1
        else:
            misses[(sorted(allowed)[0], got)] += 1
    return 100 * ok / max(1, n), n, misses


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="")
    args = ap.parse_args()
    from jarvis.decision.engine import LocalJDE
    from jarvis.decision.evaluation.evaluate import default_catalog, latest_model_dir
    from tests.phase_suite.runner import load
    engine = LocalJDE.load(Path(args.model) if args.model else latest_model_dir(), catalog=default_catalog())
    print("model", engine.meta.decision_model_version)
    for split in ("dev", "blind", "blind2", "blind3", "blind4", "blind5"):
        acc, n, misses = family_accuracy(engine, load(split))
        print(f"  {split:7} family accuracy {acc:6.2f}% over {n}   top misses: {misses.most_common(3)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
