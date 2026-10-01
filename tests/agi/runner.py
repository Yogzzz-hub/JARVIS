"""520 AGI-like capability suite: every capability row of capabilities_520.md is routed through the real router
(no AI model) in three ways and judged against tests/agi/expectations.txt.

* dev       - the example command from the spec, plus generated dev surface forms (tests/operator/surface.py)
* holdout   - one paraphrase per capability written and frozen (FROZEN.sha256) *before* any router change for this
              suite, plus generated holdout surface forms of that paraphrase
* negated   - "don't <example>" must never run anything

Expectation tokens: ``tool`` (intent), ``tool.action`` (intent + slots action/scope), ``compound``,
``*CLARIFY`` (asks), ``*PLANNER`` / ``*CHAT`` (deferred to the planner / the model: LANE_2), ``*REJECT``.

    python -m tests.agi.runner [--split dev|holdout|all] [--fails] [--json out.json]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import re
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from tests.operator.surface import dev_forms, holdout_forms, negated  # noqa: E402

CONSEQUENTIAL = {"delete_file", "empty_recycle_bin", "send_whatsapp_message", "send_whatsapp_bulk", "reply_whatsapp_all",
                 "install_software", "uninstall_software", "update_software", "system_power_control", "move_file",
                 "rename_file", "close_app", "close_window", "powershell_command", "gmail_create_draft", "localsend_file",
                 "localsend_text", "android_push_file", "project_run", "project_file_run", "code_edit", "code_repair_loop",
                 "whatsapp_auto_reply", "whatsapp_action", "batch_rename", "deliver_op", "phone_op"}


def load() -> list[dict]:
    rows, sec = {}, ""
    for line in (HERE / "capabilities_520.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            sec = line[3:].strip()
        m = re.match(r"\|\s*(\d+)\s*\|\s*\*\*(.+?)\*\*\s*\|\s*“(.+?)”\s*\|", line)
        if m:
            rows[int(m.group(1))] = {"id": int(m.group(1)), "family": sec, "feature": m.group(2), "example": m.group(3)}
    for line in (HERE / "expectations.txt").read_text(encoding="utf-8").splitlines():
        parts = line.split("|")
        rid = int(parts[0])
        rows[rid]["expect"] = parts[1:-1]
        rows[rid]["holdout"] = parts[-1]
    return [rows[k] for k in sorted(rows)]


def _lane(d) -> str:
    return getattr(d.lane, "value", str(d.lane))


def judge(expect: list[str], d) -> bool:
    lane, intent, slots = _lane(d), d.intent or "", d.slots or {}
    subs = [s.tool for s in (d.subcommands or [])]
    for tok in expect:
        if tok == "*CLARIFY" and (lane == "CLARIFY" or intent == "clarify"):
            return True
        if tok in ("*PLANNER", "*CHAT") and lane == "LANE_2":
            return True
        if tok == "*REJECT" and lane == "REJECT":
            return True
        if tok == "compound" and (intent == "compound" or len(subs) > 1):
            return True
        tool, _, action = tok.partition(".")
        if tool == intent and lane not in ("CLARIFY", "REJECT"):
            if not action or slots.get("action") == action or slots.get("scope") == action or slots.get("op") == action:
                return True
        if tool in subs and not action:
            return True
    return False


async def run(split: str = "all", seed: int = 11) -> dict:
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter
    rows = load()
    rng = random.Random(seed)
    out = {"rows": len(rows), "results": [], "negation": []}

    async def route(text):
        t0 = time.perf_counter()
        d = await SmartRouter(llm_provider=DisabledProvider()).route(text)
        return d, (time.perf_counter() - t0) * 1000

    for r in rows:
        forms = []
        if split in ("dev", "all"):
            forms += [("dev", k, t) for k, t in dev_forms(r["example"], rng)]
        if split in ("holdout", "all"):
            forms += [("holdout", "paraphrase", r["holdout"])]
            forms += [("holdout", k, t) for k, t in holdout_forms(r["holdout"], rng)]
        for sp, kind, text in forms:
            d, ms = await route(text)
            ok = judge(r["expect"], d)
            critical = not ok and (d.intent in CONSEQUENTIAL) and _lane(d) in ("LANE_0", "LANE_1")
            out["results"].append({"id": r["id"], "family": r["family"], "split": sp, "form": kind, "text": text, "ok": ok,
                                   "critical": critical, "intent": d.intent, "lane": _lane(d),
                                   "slots": {k: v for k, v in (d.slots or {}).items() if k != "qualifiers"}, "ms": ms,
                                   "expect": r["expect"]})
        question = r["example"].rstrip().endswith("?") or re.match(r"^(?:i|i'm|i am)\b", r["example"], re.I)
        if not any(t.startswith("*") for t in r["expect"][:1]) and not question:
            d, _ = await route(negated(r["example"]))
            ran = _lane(d) not in ("REJECT", "CLARIFY") and d.intent not in (None, "clarify", "standing_rule",
                                                                              "reject_ticket")
            out["negation"].append({"id": r["id"], "text": negated(r["example"]), "ok": not ran, "intent": d.intent})
    return summarize(out)


def summarize(out: dict) -> dict:
    res = out["results"]
    agg = defaultdict(lambda: [0, 0])
    for r in res:
        for key in (f"split:{r['split']}", f"family:{r['split']}:{r['family']}", f"form:{r['split']}:{r['form']}"):
            agg[key][0] += r["ok"]
            agg[key][1] += 1
    canon = {}
    for r in res:
        if r["form"] in ("canonical", "paraphrase"):
            canon.setdefault(r["split"], []).append(r["ok"])
    ms = sorted(r["ms"] for r in res)
    return {
        "rows": out["rows"],
        "canonical": {k: f"{sum(v)}/{len(v)}" for k, v in canon.items()},
        "accuracy": {k: {"passed": v[0], "total": v[1], "pct": round(100 * v[0] / v[1], 2)} for k, v in sorted(agg.items())},
        "critical_wrong_consequential": sum(r["critical"] for r in res),
        "negation": {"checked": len(out["negation"]), "executed": sum(not n["ok"] for n in out["negation"])},
        "routing_ms": {"p50": round(statistics.median(ms), 2) if ms else 0, "p95": round(ms[int(.95 * (len(ms) - 1))], 2) if ms else 0},
        "failures": [r for r in res if not r["ok"]],
        "criticals": [r for r in res if r["critical"]],
        "negation_failures": [n for n in out["negation"] if not n["ok"]],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="all")
    ap.add_argument("--fails", action="store_true")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    logging.disable(logging.WARNING)
    res = asyncio.run(run(a.split))
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1, default=str))
    view = {k: v for k, v in res.items() if k not in ("failures", "criticals", "negation_failures")}
    view["accuracy"] = {k: v for k, v in view["accuracy"].items() if k.startswith(("split:", "family:"))}
    print(json.dumps(view, indent=1))
    if a.fails:
        for r in res["criticals"]:
            print(f"CRITICAL {r['id']} [{r['split']}/{r['form']}] {r['text']!r} -> {r['lane']} {r['intent']} {r['slots']}")
        for r in res["failures"]:
            if r["form"] in ("canonical", "paraphrase"):
                print(f"FAIL {r['id']} [{r['split']}] {r['text']!r} -> {r['lane']} {r['intent']} {str(r['slots'])[:80]} want {r['expect']}")
        for n in res["negation_failures"]:
            print(f"NEGFAIL {n['id']} {n['text']!r} -> {n['intent']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
