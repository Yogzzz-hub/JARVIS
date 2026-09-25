"""Benchmark JDE encoder backbones on JARVIS data (same training pool, same suites, same heads).

    python scripts/bench_jde_backbones.py                          # every encoder that loads here
    python scripts/bench_jde_backbones.py hash glove+hash minilm+hash bge-small+hash

MiniLM / BGE-small need `pip install fastembed` and a one-time model download from huggingface.co
(cached in models/jde/encoders). GloVe needs `python scripts/setup_models.py --jde`.
Results go to reports/jde_backbones.json and appear in reports/JDE_BENCHMARK.md on the next evaluation.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis.decision.catalog import default_catalog  # noqa: E402
from jarvis.decision.dataset import load_suite  # noqa: E402
from jarvis.decision.encoder import available_encoders  # noqa: E402
from jarvis.decision.evaluation.evaluate import evaluate_split  # noqa: E402
from jarvis.decision.schemas import DecisionState  # noqa: E402
from jarvis.decision.train import train  # noqa: E402

OUT = ROOT / "reports" / "jde_backbones.json"


def main(argv: list[str]) -> int:
    specs = argv or ["hash", "glove+hash", "minilm+hash", "bge-small+hash"]
    usable = available_encoders(specs)
    for spec in specs:
        if spec not in usable:
            print(f"skip {spec}: encoder not available on this machine")
    results = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    suites = {s: load_suite(s) for s in ("dev", "holdout", "adversarial")}
    for spec in usable:
        t = time.perf_counter()
        engine, _ = train(spec)
        train_s = time.perf_counter() - t
        engine.catalog = default_catalog()
        row = {"train_s": round(train_s, 1)}
        for split, examples in suites.items():
            r = evaluate_split(engine, examples)
            row[split] = f"{100 * r['route_acc']:.1f}%"
            row[f"{split}_wrong_consequential"] = len(r["wrong_consequential_executions"])
        engine.cache.clear()
        lat = []
        for i, ex in enumerate(suites["dev"][:300]):
            s = time.perf_counter()
            engine.decide(DecisionState(text=f"{ex.text} {i}x"))
            lat.append((time.perf_counter() - s) * 1000)
        row["p50"] = f"{statistics.median(lat):.2f}"
        results[spec] = row
        print(spec, row)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
