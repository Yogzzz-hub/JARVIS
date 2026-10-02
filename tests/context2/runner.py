"""Context-2 runner: python -m tests.context2.runner [--split dev|holdout|all] [--fails]

Fails are printed only for the dev split: the holdout stays unseen. Every tool is a recorder, verification passes.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import random
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.context.runner import CALLS, _match, _pending, _recorder  # noqa: E402
from tests.context2.cases import CONVERSATIONS, POOLS  # noqa: E402

FILLS = 2
FORMS = ("plain", "wake", "filler", "please", "okay", "typo")


def _fill(x, vals):
    if isinstance(x, str):
        return re.sub(r"\{(\w+)\}", lambda m: vals.get(m.group(1), m.group(0)), x)
    if isinstance(x, tuple):
        return tuple(_fill(v, vals) for v in x)
    if isinstance(x, dict):
        return {k: _fill(v, vals) for k, v in x.items()}
    return x


def _typo(text: str, rng: random.Random, protected: set[str]) -> str:
    words = text.split()
    cands = [i for i, w in enumerate(words) if len(w) >= 5 and w.isalpha() and w not in protected]
    if not cands:
        return text
    i = rng.choice(cands)
    w = words[i]
    j = rng.randrange(1, len(w) - 2)
    words[i] = w[:j] + w[j + 1] + w[j] + w[j + 2:]
    return " ".join(words)


def _form(text: str, form: str, rng: random.Random, protected: set[str]) -> str:
    return {"plain": text, "wake": f"jarvis, {text}", "filler": f"um {text}", "please": f"{text} please",
            "okay": f"okay {text}", "typo": _typo(text, rng, protected)}[form]


def split_of(conv) -> str:
    key = " | ".join(t for t, _ in conv)
    return "holdout" if int(hashlib.sha1(key.encode()).hexdigest(), 16) % 2 else "dev"


def build() -> list[dict]:
    out = []
    for conv in CONVERSATIONS:
        rng = random.Random("ctx2|" + " | ".join(t for t, _ in conv))
        keys = sorted({k for t, _ in conv for k in re.findall(r"\{(\w+)\}", t + repr(_)) if k in POOLS})
        seen = set()
        for _ in range(FILLS):
            vals = {k: rng.choice(POOLS[k]) for k in keys}
            protected = {w for v in vals.values() for w in v.split()}
            turns = [(_fill(t, vals), _fill(e, vals)) for t, e in conv]
            for form in FORMS:
                last_text = _form(turns[-1][0], form, rng, protected)
                if (tuple(t for t, _ in turns[:-1]), last_text) in seen:
                    continue
                seen.add((tuple(t for t, _ in turns[:-1]), last_text))
                out.append({"split": split_of(conv), "form": form, "template": conv[-1][0],
                            "turns": turns[:-1] + [(last_text, turns[-1][1])]})
    return out


def _judge(expect, calls, state) -> bool:
    if isinstance(expect, str) and expect.startswith("NOT:"):
        banned = expect[4:].split("|")
        return not any(c[0] in banned for c in calls)
    return _match(expect, calls, state)


async def run_all(cases) -> list[dict]:
    from jarvis.tests.ai_harness import AIHarness
    from jarvis.tools.base import VerificationResult

    rows = []
    for case in cases:
        with tempfile.TemporaryDirectory() as d:
            h = AIHarness(Path(d), responder=lambda p: {"message": "OK."}, reachable=False)
            for tool in h.registry.list():
                tool.run = _recorder(tool)

            async def _ok(tool_name, result, arguments, cancellation):
                return VerificationResult(verified=True, confidence=1.0, evidence={"stub": True})
            h.service.verifier.verify = _ok
            turns = case["turns"]
            for i, (text, expect) in enumerate(turns):
                CALLS.clear()
                res = await h.say(text)
                calls = list(CALLS) or _pending(h.service)
                if res.state == "WAITING_CONFIRMATION":
                    h.service._pending_execution = None
                if i == len(turns) - 1:
                    rows.append({**case, "text": text, "expect": expect, "calls": calls, "state": res.state,
                                 "message": res.message, "ok": _judge(expect, calls, res.state)})
            await h.close()
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="all", choices=("dev", "holdout", "all"))
    ap.add_argument("--fails", action="store_true")
    a = ap.parse_args()
    logging.disable(logging.WARNING)
    cases = [c for c in build() if a.split == "all" or c["split"] == a.split]
    rows = asyncio.run(run_all(cases))
    for split in ("dev", "holdout"):
        r = [x for x in rows if x["split"] == split]
        if r:
            ok = sum(x["ok"] for x in r)
            print(f"{split:8} follow-up turns {ok}/{len(r)} = {100 * ok / len(r):.1f}%")
            for form in FORMS:
                f = [x for x in r if x["form"] == form]
                if f:
                    print(f"   {form:7} {sum(x['ok'] for x in f)}/{len(f)}")
    if a.fails:
        for x in rows:
            if not x["ok"] and x["split"] == "dev":
                print(f"FAIL [{x['form']}] {' -> '.join(t for t, _ in x['turns'][:-1])} -> {x['text']!r}: "
                      f"{x['calls'][:2]} {x['state']} want {x['expect']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
