"""Blind-9 runner: every command is unseen. python -m tests.blind9.runner [--fails] [--json out.json]

Expands the templates with the Phase-500 generator (same surface forms and typos, 3 fills per template) and scores them
with the Phase-500 judge. The first run after the fixes is the honest generalisation number.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.blind9.cases import PHASES, POOLS  # noqa: E402
from tests.phase500 import build as b  # noqa: E402
from tests.phase500.runner import run, summarize  # noqa: E402

FILLS = 3


def build() -> list[dict]:
    cases = []
    for phase, templates in PHASES.items():
        for t in templates:
            rng = random.Random(f"blind9|{phase}|{t.text}")
            keys = sorted(set(k.lower() for k in b._PH.findall(t.text)))
            seen: set[str] = set()
            for _ in range(FILLS if keys else 1):
                vals = {k: rng.choice(POOLS[k]) for k in keys}
                text = b._fill(t.text, vals)
                slots = {k: b._fill(str(v), vals) for k, v in t.slots.items()}
                for tier, form, variant in b.variants(t, text):
                    if variant.lower() in seen:
                        continue
                    seen.add(variant.lower())
                    cases.append({"id": f"b9-{hashlib.sha1(variant.encode()).hexdigest()[:8]}", "phase": phase, "tier": tier,
                                  "form": form, "text": variant, "expect": t.expect, "split": "blind",
                                  "slots": slots if form in ("plain", "wake", "polite", "please") else {},
                                  "template": t.text})
    return cases


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fails", action="store_true")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    results = asyncio.run(run(build()))
    s = summarize(results)
    if a.json:
        Path(a.json).write_text(json.dumps({"summary": s, "results": results}, indent=1, default=str))
    print(f"{s['passed']}/{s['total']} = {100 * s['passed'] / s['total']:.2f}% critical={s['critical']} routing={s['routing_ms']}")
    for k, v in s["accuracy"].items():
        if k.startswith("phase:") and k.count(":") == 1:
            print(f"  {k:24} {v['passed']:5}/{v['total']:<5} {v['pct']:6.2f}%")
    if a.fails:
        for r in results:
            if not r["ok"]:
                print(f"{'CRIT' if r['critical'] else 'FAIL'} {r['phase']:12} [{r['form']}] {r['text']!r} -> {r['got_lane']} "
                      f"{r['got_intent']} {str(r['got_slots'])[:80]} want {r['expect']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
