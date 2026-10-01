"""Route every operator scenario's surface forms through the real router (no AI model) and judge them.

    python -m tests.operator.runner              # dev forms
    python -m tests.operator.runner --holdout    # holdout forms (never used for tuning)
    python -m tests.operator.runner --json out.json --fails

Judging: the decision must pick the scenario's capability (or one of its listed alternatives) with the required
slots; '*REJECT' must not run anything, '*CLARIFY' must ask, '*PLANNER' must plan or split into steps. Negated
forms of every action scenario must be rejected (zero tolerance). Latency is the router's own measured time.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.operator.scenarios import ANY, SCENARIOS, Scenario  # noqa: E402
from tests.operator.surface import dev_forms, holdout_forms, negated  # noqa: E402

# Forms whose *expected outcome* is the scenario's; negation is judged separately.
_RUNNABLE = {"window_op", "ui_op", "text_op", "deliver_op", "browser_op", "video_op", "watch_op", "ide_op", "phone_op",
             "clipboard_op", "screen_op"}


def _lane(d) -> str:
    return getattr(d.lane, "value", str(d.lane))


def judge(sc: Scenario, d) -> tuple[bool, str]:
    lane = _lane(d)
    intents = (sc.intent,) + sc.alt_intents
    if sc.intent == "*REJECT":
        ok = lane == "REJECT" or d.intent in ("standing_rule",) or (lane == "CLARIFY" and "*CLARIFY" in intents)
        return ok, "" if ok else f"expected REJECT, got {lane}/{d.intent}"
    if sc.intent == "*CLARIFY":
        ok = lane in ("CLARIFY", "REJECT") or d.intent == "clarify" or d.intent in intents
        return ok, "" if ok else f"expected CLARIFY, got {lane}/{d.intent}"
    if sc.intent == "*PLANNER":
        ok = bool(d.needs_planner) or lane == "LANE_2" or len(getattr(d, "subcommands", []) or []) > 1 or d.intent in intents
        return ok, "" if ok else f"expected a plan, got {lane}/{d.intent}"
    if d.intent not in intents and not ("*PLANNER" in intents and (d.needs_planner or lane == "LANE_2")) \
            and not ("*CLARIFY" in intents and lane == "CLARIFY"):
        return False, f"intent {d.intent} ({lane}) not in {intents}"
    if d.intent == sc.intent:
        for k, v in sc.slots.items():
            have = (d.slots or {}).get(k, None)
            if v is ANY:
                if have in (None, "", []):
                    return False, f"slot {k} missing"
            elif isinstance(v, float):
                if not isinstance(have, (int, float)) or abs(float(have) - v) > 1e-6:
                    return False, f"slot {k}={have!r} want {v!r}"
            elif have != v:
                return False, f"slot {k}={have!r} want {v!r}"
    return True, ""


async def run(holdout: bool = False, seed: int = 7) -> dict:
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter
    rng = random.Random(seed + (1000 if holdout else 0))
    rows, neg_rows = [], []
    for sc in SCENARIOS:
        forms = []
        for s in sc.seeds:
            forms += holdout_forms(s, rng) if holdout else dev_forms(s, rng)
        for kind, text in forms:
            router = SmartRouter(llm_provider=DisabledProvider())      # no context carried between scenarios
            t0 = time.perf_counter()
            d = await router.route(text)
            ms = (time.perf_counter() - t0) * 1000
            ok, why = judge(sc, d)
            rows.append({"id": sc.id, "family": sc.family, "form": kind, "text": text, "ok": ok, "why": why,
                         "intent": d.intent, "lane": _lane(d), "slots": d.slots, "ms": ms, "risk": sc.risk})
        if sc.intent in _RUNNABLE or (sc.intent and not sc.intent.startswith("*")):
            router = SmartRouter(llm_provider=DisabledProvider())
            text = negated(sc.seeds[0])
            d = await router.route(text)
            ran = _lane(d) not in ("REJECT", "CLARIFY") and d.intent not in (None, "clarify", "standing_rule")
            neg_rows.append({"id": sc.id, "text": text, "ok": not ran, "intent": d.intent, "lane": _lane(d)})
    return summarize(rows, neg_rows)


def summarize(rows, neg_rows) -> dict:
    fam = defaultdict(lambda: [0, 0])
    forms = defaultdict(lambda: [0, 0])
    for r in rows:
        fam[r["family"]][0] += r["ok"]
        fam[r["family"]][1] += 1
        forms[r["form"]][0] += r["ok"]
        forms[r["form"]][1] += 1
    scen_ok = defaultdict(list)
    for r in rows:
        scen_ok[r["id"]].append(r["ok"])
    ms = sorted(r["ms"] for r in rows)
    wrong_action = [r for r in rows if not r["ok"] and r["lane"] not in ("CLARIFY", "REJECT", "LANE_2")
                    and r["intent"] not in (None, "clarify")]
    security = [r for r in rows if r["risk"] == "SECURITY" and not r["ok"]]
    return {
        "scenarios": len(scen_ok), "forms": len(rows),
        "form_accuracy": round(100 * sum(r["ok"] for r in rows) / max(1, len(rows)), 2),
        "scenario_all_forms_pass": sum(all(v) for v in scen_ok.values()),
        "by_family": {k: {"passed": v[0], "total": v[1], "accuracy": round(100 * v[0] / v[1], 2)} for k, v in sorted(fam.items())},
        "by_form": {k: {"passed": v[0], "total": v[1], "accuracy": round(100 * v[0] / v[1], 2)} for k, v in sorted(forms.items())},
        "negation": {"total": len(neg_rows), "executed": sum(not r["ok"] for r in neg_rows)},
        "zero_fail": {"negated_action_executed": sum(not r["ok"] for r in neg_rows),
                      "security_bypass_routes": len(security),
                      "wrong_capability_executed": len(wrong_action)},
        "routing_ms": {"p50": round(statistics.median(ms), 2) if ms else 0,
                       "p95": round(ms[int(0.95 * (len(ms) - 1))], 2) if ms else 0, "max": round(ms[-1], 2) if ms else 0},
        "failures": [r for r in rows if not r["ok"]], "negation_failures": [r for r in neg_rows if not r["ok"]],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true")
    ap.add_argument("--fails", action="store_true")
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    import logging
    logging.disable(logging.WARNING)
    res = asyncio.run(run(holdout=args.holdout))
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=2, default=str))
    view = {k: v for k, v in res.items() if k not in ("failures", "negation_failures")}
    print(json.dumps(view, indent=2))
    if args.fails:
        for r in res["failures"]:
            print(f"FAIL {r['id']} [{r['family']}/{r['form']}] {r['text']!r} -> {r['why']}")
        for r in res["negation_failures"]:
            print(f"NEGFAIL {r['id']} {r['text']!r} -> {r['lane']}/{r['intent']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
