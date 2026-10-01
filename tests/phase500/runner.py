"""Phase-500 suite runner: every phase / area with 500+ commands, routed by the real router with no AI model.

    python -m tests.phase500.runner [--split dev|holdout|all] [--phase p03] [--fails] [--json out.json]

Same judge as tests/phase_suite (intent alternatives, CHAT / MULTI / REJECT / SAFE / CLARIFY / CONTROL:x). A "critical"
is a failed case routed to a consequential tool in an executing lane; the target is zero. Documented expectation fixes
from tests/phase500/corrections.py are applied and counted (the frozen cases are never edited).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.phase_suite.runner import ACTION_LANES, judge  # noqa: E402

CONSEQUENTIAL = {"delete_file", "empty_recycle_bin", "send_whatsapp_message", "send_whatsapp_bulk", "reply_whatsapp_all",
                 "reply_whatsapp_message", "install_software", "uninstall_software", "update_software", "system_power_control",
                 "move_file", "rename_file", "close_app", "close_window", "powershell_command", "localsend_file",
                 "localsend_text", "android_push_file", "project_run", "project_file_run", "code_edit", "whatsapp_auto_reply",
                 "batch_rename", "android_dial"}


async def run(cases: list[dict]) -> list[dict]:
    import logging
    logging.disable(logging.WARNING)
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter
    out, router, current = [], None, None
    for c in cases:
        if c["phase"] != current:
            router, current = SmartRouter(llm_provider=DisabledProvider()), c["phase"]
        t0 = time.perf_counter()
        d = await router.route(c["text"])
        ms = (time.perf_counter() - t0) * 1000
        ok, why = judge(c, d)
        critical = not ok and d.intent in CONSEQUENTIAL and d.lane in ACTION_LANES
        out.append({**c, "ok": ok, "critical": critical, "got_intent": d.intent, "got_lane": d.lane.value,
                    "got_slots": {k: v for k, v in (d.slots or {}).items() if k != "qualifiers"}, "ms": ms, "why": why})
    return out


def summarize(results: list[dict]) -> dict:
    agg = defaultdict(lambda: [0, 0])
    for r in results:
        for key in (f"split:{r['split']}", f"phase:{r['phase']}", f"phase:{r['split']}:{r['phase']}", f"form:{r['form']}",
                    f"tier:{r['tier']}"):
            agg[key][0] += r["ok"]
            agg[key][1] += 1
    ms = sorted(r["ms"] for r in results)
    return {"total": len(results), "passed": sum(r["ok"] for r in results),
            "accuracy": {k: {"passed": v[0], "total": v[1], "pct": round(100 * v[0] / v[1], 2)} for k, v in sorted(agg.items())},
            "critical": sum(r["critical"] for r in results),
            "routing_ms": {"p50": round(statistics.median(ms), 2), "p95": round(ms[int(0.95 * (len(ms) - 1))], 2)}}


def main() -> int:
    from tests.phase500.build import build
    from tests.phase500.corrections import apply
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=("dev", "holdout", "all"))
    ap.add_argument("--phase", default="")
    ap.add_argument("--fails", action="store_true")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    built = build()
    cases = [apply({**c, "split": s}) for s, rows in built.items() if a.split in (s, "all") for c in rows
             if not a.phase or c["phase"].startswith(a.phase)]
    results = asyncio.run(run(cases))
    summary = summarize(results)
    summary["corrected_cases"] = sum(bool(r.get("corrected")) for r in results)
    if a.json:
        Path(a.json).write_text(json.dumps({"summary": summary, "results": results}, indent=1, default=str))
    acc = summary["accuracy"]
    print(f"{summary['passed']}/{summary['total']} critical={summary['critical']} routing={summary['routing_ms']} "
          f"corrected_expectations={summary['corrected_cases']} (tests/phase500/corrections.py)")
    for k, v in acc.items():
        if k.startswith(("split:", "phase:")) and k.count(":") == 1:
            print(f"  {k:28} {v['passed']:5}/{v['total']:<5} {v['pct']:6.2f}%")
    if a.fails:
        for r in results:
            if not r["ok"]:
                tag = "CRIT" if r["critical"] else "FAIL"
                print(f"{tag} {r['phase']:16} [{r['split']}/{r['form']}] {r['text']!r} -> {r['got_lane']} {r['got_intent']} "
                      f"{str(r['got_slots'])[:90]} want {r['expect']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
