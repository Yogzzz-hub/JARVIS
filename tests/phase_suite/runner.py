"""Run the phase command suite through the real router (no AI model: deterministic understanding only).

    python -m tests.phase_suite.runner              # dev split
    python -m tests.phase_suite.runner --blind      # the held-out blind split
    python -m tests.phase_suite.runner --all
    python -m tests.phase_suite.runner --blind2     # the second held-out set, written after the fixes
    python -m tests.phase_suite.runner --blind3     # the third held-out set (more easy commands)
    python -m tests.phase_suite.runner --blind4     # the fourth held-out set
    python -m tests.phase_suite.runner --blind5     # the fifth held-out set (conversational style)
    python -m tests.phase_suite.runner --blind6     # the sixth: long spoken rambles and mixed Thanglish + English

Writes reports/PHASE_SUITE_<split>.md / .json with accuracy per phase and per difficulty, and every failure.
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

from jarvis.core.router.models import ComplexityLevel, ReasonCode, RouteLane  # noqa: E402

HERE = Path(__file__).resolve().parent
CHAT_LIKE = {None, "chat", "general_chat", "ollama_chat", "quick_answer", "search_web", "search_news"}
ACTION_LANES = (RouteLane.LANE_0, RouteLane.LANE_1)
# names the runtime registers as aliases of one tool (jarvis/core/runtime.py register_alias): the same action
RUNTIME_ALIASES = {"wifi_status": "network_info", "web_search": "search_web"}


def _slot_ok(actual, expected: str) -> bool:
    a, e = (str(actual if actual is not None else "").lower().replace(" ", ""), expected.lower().replace(" ", ""))
    return bool(a) and (e in a or a in e)


def _is_chat(d) -> bool:
    """Answered by chat: the command service sends QUESTION_NOT_COMMAND to the chat model (never the planner)."""
    if d.reason_code == ReasonCode.QUESTION_NOT_COMMAND and d.lane == RouteLane.LANE_2:
        return True
    return (d.lane == RouteLane.LANE_2 and not d.needs_planner and d.intent in CHAT_LIKE) or \
        (d.lane in ACTION_LANES and d.intent in CHAT_LIKE - {None})


def judge(case: dict, d) -> tuple[bool, str]:
    reasons = []
    for option in case["expect"].split("|"):
        option = option.strip()
        if option == "CHAT":
            if _is_chat(d):
                return True, ""
        elif option == "MULTI":
            if d.complexity == ComplexityLevel.COMPOUND or d.intent == "compound" or \
                    (d.needs_planner and d.reason_code != ReasonCode.QUESTION_NOT_COMMAND):
                return True, ""
        elif option == "REJECT":
            if d.lane == RouteLane.REJECT:
                return True, ""
        elif option == "SAFE":
            if d.lane in (RouteLane.REJECT, RouteLane.CLARIFY) or _is_chat(d):
                return True, ""
        elif option == "CLARIFY":
            if d.lane == RouteLane.CLARIFY:
                return True, ""
        elif option.startswith("CONTROL:"):
            if d.lane == RouteLane.CONTROL and d.intent == option.split(":", 1)[1]:
                return True, ""
        else:
            allow_clarify = option.endswith("+clarify")
            intent = option.replace("+clarify", "")
            lane_ok = d.lane in ACTION_LANES or (allow_clarify and d.lane == RouteLane.CLARIFY)
            if (d.intent == intent or RUNTIME_ALIASES.get(d.intent or "") == intent) and lane_ok:
                bad = [k for k, v in (case.get("slots") or {}).items() if not _slot_ok((d.slots or {}).get(k), v)]
                if not bad:
                    return True, ""
                reasons.append(f"slots {bad}: {d.slots}")
    return False, "; ".join(reasons)


async def run_cases(cases: list[dict]) -> list[dict]:
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter
    results = []
    router, current_phase = None, None
    for c in cases:
        if c["phase"] != current_phase:  # a fresh router per phase: no context carried between areas
            router, current_phase = SmartRouter(llm_provider=DisabledProvider()), c["phase"]
        d = await router.route(c["text"])
        ok, why = judge(c, d)
        results.append({**c, "ok": ok, "got_intent": d.intent, "got_lane": d.lane.value, "got_slots": d.slots,
                        "planner": bool(d.needs_planner), "reason": str(getattr(d.reason_code, "value", d.reason_code)),
                        "why": why})
    return results


def summarize(results: list[dict]) -> dict:
    by_phase, by_tier = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for r in results:
        for bucket, key in ((by_phase, r["phase"]), (by_tier, r["tier"])):
            bucket[key][0] += r["ok"]
            bucket[key][1] += 1
    total = sum(r["ok"] for r in results)
    return {"total": len(results), "passed": total, "accuracy": round(100 * total / max(1, len(results)), 2),
            "by_phase": {k: {"passed": v[0], "total": v[1], "accuracy": round(100 * v[0] / v[1], 2)} for k, v in sorted(by_phase.items())},
            "by_tier": {k: {"passed": v[0], "total": v[1], "accuracy": round(100 * v[0] / v[1], 2)}
                        for k, v in sorted(by_tier.items(), key=lambda kv: ("easy", "medium", "hard", "very_hard").index(kv[0]))}}


def write_report(split: str, results: list[dict], summary: dict, seconds: float) -> Path:
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    (out / f"PHASE_SUITE_{split}.json").write_text(json.dumps({"summary": summary, "results": results}, indent=1,
                                                              ensure_ascii=False, default=str), encoding="utf-8")
    lines = [f"# Phase command suite - {split}", "",
             f"{summary['passed']}/{summary['total']} passed (**{summary['accuracy']}%**) in {seconds:.1f} s, router only "
             "(no AI model: deterministic understanding).", "", "| Phase | Passed | Accuracy |", "|---|---|---|"]
    lines += [f"| {k} | {v['passed']}/{v['total']} | {v['accuracy']}% |" for k, v in summary["by_phase"].items()]
    lines += ["", "| Difficulty | Passed | Accuracy |", "|---|---|---|"]
    lines += [f"| {k} | {v['passed']}/{v['total']} | {v['accuracy']}% |" for k, v in summary["by_tier"].items()]
    fails = [r for r in results if not r["ok"]]
    lines += ["", f"## Failures ({len(fails)})", ""]
    lines += [f"- `{r['phase']}` [{r['tier']}] \"{r['text']}\" expected `{r['expect']}` got `{r['got_intent']}` "
              f"({r['got_lane']}{', planner' if r['planner'] else ''}) {r['got_slots'] if r['got_slots'] else ''} {r['why']}"
              for r in fails]
    path = out / f"PHASE_SUITE_{split}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def load(split: str) -> list[dict]:
    if split == "blind6":
        from tests.phase_suite.blind6 import build6
        return build6()
    if split == "blind5":
        from tests.phase_suite.blind5 import build5
        return build5()
    if split == "blind4":
        from tests.phase_suite.blind4 import build4
        return build4()
    if split == "blind3":
        from tests.phase_suite.blind3 import build3
        return build3()
    if split == "blind2":
        from tests.phase_suite.blind2 import build2
        return build2()
    from tests.phase_suite.build import build
    return build()[split]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blind", action="store_true")
    ap.add_argument("--blind2", action="store_true")
    ap.add_argument("--blind3", action="store_true")
    ap.add_argument("--blind4", action="store_true")
    ap.add_argument("--blind5", action="store_true")
    ap.add_argument("--blind6", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--phase", default="")
    ap.add_argument("--fails", action="store_true", help="print failures")
    args = ap.parse_args()
    splits = ["dev", "blind", "blind2", "blind3", "blind4", "blind5", "blind6"] if args.all else \
        ["blind6" if args.blind6 else "blind5" if args.blind5 else "blind4" if args.blind4 else "blind3" if args.blind3 else "blind2" if args.blind2 else "blind" if args.blind else "dev"]
    for split in splits:
        cases = [c for c in load(split) if not args.phase or c["phase"].startswith(args.phase)]
        t0 = time.time()
        results = asyncio.run(run_cases(cases))
        summary = summarize(results)
        path = write_report(split, results, summary, time.time() - t0)
        print(f"[{split}] {summary['passed']}/{summary['total']} = {summary['accuracy']}%   report: {path.relative_to(ROOT)}")
        for k, v in summary["by_phase"].items():
            print(f"   {k:18} {v['passed']:4}/{v['total']:<4} {v['accuracy']:6.2f}%")
        print("   " + "  ".join(f"{k}={v['accuracy']}%" for k, v in summary["by_tier"].items()))
        if args.fails:
            for r in results:
                if not r["ok"]:
                    print(f"FAIL {r['phase']:16} {r['text']!r:60} exp={r['expect']:34} got={r['got_intent']} {r['got_lane']} {r['got_slots']} {r['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
