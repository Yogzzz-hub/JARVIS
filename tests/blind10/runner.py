"""Blind-10 runner: python -m tests.blind10.runner [--json out.json] [--md report.md]

Strict scoring - the right action with the right details, through the real router with no AI model:
  correct   the outcome matches one of the expected options; for an action, every `need` string is in its arguments
  acted     the command would execute something: a tool in an executing lane (not a chat answer), a compound, a control
  precision correct actions / all actions taken          (doing the wrong thing counts against it)
  recall    correct actions / commands that need an action (asking or chatting instead counts against it)
  false-action rate  actions taken on commands that must not act (refuse / ask / chat)
  critical  a wrong action that is consequential (send, delete, close, power, install, ...)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from jarvis.core.router.models import ComplexityLevel, RouteLane  # noqa: E402
from tests.blind10.cases import PHASES  # noqa: E402
from tests.phase500.runner import CONSEQUENTIAL  # noqa: E402
from tests.phase_suite.runner import ACTION_LANES, CHAT_LIKE, RUNTIME_ALIASES, _is_chat  # noqa: E402

NON_ACTION = ("CHAT", "SAFE", "REJECT", "CLARIFY")


def _norm(x) -> str:
    return " ".join(str(x).lower().replace("_", " ").split())


def _args_text(d) -> str:
    parts = [_norm(v) for v in (d.slots or {}).values() if v is not None]
    for s in d.subcommands or []:
        parts += [_norm(s.tool)] + [_norm(v) for v in (s.arguments or {}).values() if v is not None]
    return " | ".join(parts)


def _need_ok(need: list[str], d) -> bool:
    text = _args_text(d)
    squashed = text.replace(" ", "")
    return all(any(_norm(alt) in text or _norm(alt).replace(" ", "") in squashed for alt in n.split("|")) for n in need)


def _compound(d) -> bool:
    return d.intent == "compound" or d.complexity == ComplexityLevel.COMPOUND or bool(d.subcommands)


def acted(d) -> bool:
    if d.lane == RouteLane.CONTROL:
        return True
    if _compound(d) and d.lane in ACTION_LANES:
        return True
    return d.lane in ACTION_LANES and bool(d.intent) and d.intent not in CHAT_LIKE


def judge(case: dict, d) -> bool:
    for opt in case["expect"].split("|"):
        if opt == "CHAT" and _is_chat(d):
            return True
        if opt == "SAFE" and (d.lane in (RouteLane.REJECT, RouteLane.CLARIFY) or _is_chat(d) or d.intent == "standing_rule"):
            return True
        if opt == "REJECT" and (d.lane == RouteLane.REJECT or d.intent == "standing_rule"):
            return True
        if opt == "CLARIFY" and d.lane == RouteLane.CLARIFY:
            return True
        if opt == "MULTI" and (_compound(d) or (d.needs_planner and d.lane == RouteLane.LANE_2 and d.intent is None
                                                and str(getattr(d.reason_code, "value", "")) != "QUESTION_NOT_COMMAND")):
            return _need_ok(case["need"], d) or not _compound(d)
        if opt.startswith("CONTROL:") and d.lane == RouteLane.CONTROL and d.intent == opt.split(":", 1)[1]:
            return True
        if opt == "compound" and _compound(d) and d.lane in ACTION_LANES:
            return _need_ok(case["need"], d)
        tool = opt.replace("+clarify", "")
        if tool in NON_ACTION or tool in ("MULTI", "compound") or tool.startswith("CONTROL:"):
            continue
        lane_ok = d.lane in ACTION_LANES or d.lane == RouteLane.CONTROL or (opt.endswith("+clarify") and d.lane == RouteLane.CLARIFY)
        if lane_ok and (d.intent == tool or RUNTIME_ALIASES.get(d.intent or "") == tool) and _need_ok(case["need"], d):
            return True
    return False


def expected_class(case: dict) -> str:
    opts = case["expect"].split("|")
    none = [o for o in opts if o in NON_ACTION]
    if not none:
        return "act"
    return "none" if len(none) == len(opts) else "either"


async def run() -> list[dict]:
    import logging
    logging.disable(logging.WARNING)
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter
    rows = []
    for phase, cases in PHASES.items():
        router = SmartRouter(llm_provider=DisabledProvider())   # a fresh router per phase: no context between areas
        for c in cases:
            t0 = time.perf_counter()
            d = await router.route(c["text"])
            ms = (time.perf_counter() - t0) * 1000
            ok, a = judge(c, d), acted(d)
            rows.append({"phase": phase, "text": c["text"], "expect": c["expect"], "need": c["need"], "cls": expected_class(c),
                         "ok": ok, "acted": a, "critical": a and not ok and d.intent in CONSEQUENTIAL,
                         "got": f"{d.lane.value} {d.intent}", "args": _args_text(d)[:160], "ms": ms,
                         "intent": d.intent if a else None})
    return rows


def metrics(rows: list[dict]) -> dict:
    n = len(rows)
    act = [r for r in rows if r["cls"] == "act"]
    none = [r for r in rows if r["cls"] == "none"]
    taken = [r for r in rows if r["acted"]]
    right_taken = [r for r in taken if r["ok"]]
    p = len(right_taken) / len(taken) if taken else 1.0
    rc = sum(r["ok"] for r in act) / len(act) if act else 1.0
    return {"n": n, "accuracy": sum(r["ok"] for r in rows) / n, "precision": p, "recall": rc,
            "f1": 2 * p * rc / (p + rc) if p + rc else 0.0,
            "actions_taken": len(taken), "wrong_actions": len(taken) - len(right_taken),
            "missed": sum(1 for r in act if not r["acted"]), "act_cases": len(act),
            "none_cases": len(none), "none_correct": sum(r["ok"] for r in none),
            "false_actions": sum(1 for r in none if r["acted"]),
            "critical": sum(r["critical"] for r in rows)}


def per_tool(rows: list[dict]) -> dict:
    """Precision / recall per expected tool (first listed tool of each action case)."""
    tp, pred, gold = defaultdict(int), defaultdict(int), defaultdict(int)
    for r in rows:
        if r["cls"] == "act":
            g = r["expect"].split("|")[0]
            gold[g] += 1
            if r["ok"]:
                tp[g] += 1
        if r["acted"] and r["intent"]:
            pred[r["intent"]] += 1
    out = {}
    for t in sorted(set(gold) | set(pred)):
        p = tp[t] / pred[t] if pred[t] else None
        rc = tp[t] / gold[t] if gold[t] else None
        out[t] = {"gold": gold[t], "taken": pred[t], "correct": tp[t], "precision": p, "recall": rc}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    rows = asyncio.run(run())
    by = defaultdict(list)
    for r in rows:
        by[r["phase"]].append(r)
    allm = metrics(rows)
    print(f"{'phase':22} {'acc':>6} {'prec':>6} {'rec':>6} {'f1':>6} {'wrong':>5} {'miss':>4} {'falseAct':>8} {'crit':>4}")
    for ph, rs in by.items():
        m = metrics(rs)
        print(f"{ph:22} {100*m['accuracy']:6.1f} {100*m['precision']:6.1f} {100*m['recall']:6.1f} {100*m['f1']:6.1f} "
              f"{m['wrong_actions']:5} {m['missed']:4} {m['false_actions']:3}/{m['none_cases']:<4} {m['critical']:4}")
    m = allm
    print(f"{'ALL':22} {100*m['accuracy']:6.1f} {100*m['precision']:6.1f} {100*m['recall']:6.1f} {100*m['f1']:6.1f} "
          f"{m['wrong_actions']:5} {m['missed']:4} {m['false_actions']:3}/{m['none_cases']:<4} {m['critical']:4}")
    if a.json:
        Path(a.json).write_text(json.dumps({"overall": allm, "phases": {k: metrics(v) for k, v in by.items()},
                                            "tools": per_tool(rows), "rows": rows}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
