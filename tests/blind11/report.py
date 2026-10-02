"""Blind-11 report: python -m tests.blind11.report <runA.json> <runB.json> [--errata tests/blind11/errata.json]

Writes docs/BLIND11_REPORT.md, BLIND11_FAILURES.md, BLIND11_PHASE_METRICS.csv, BLIND11_TOOL_METRICS.csv,
BLIND11_CONFUSION_MATRIX.csv, BLIND11_LATENCY.csv (BLIND11_ORACLE_ERRATA.md is written by hand, from errata.json).

Run B (command service, real sandbox execution where possible) is the headline. Run A (router only) is diagnostic.
Every metric is computed from the locked oracle; the audited numbers only drop cases listed in the errata file, each
with its justification.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.blind11.runner import load_cases  # noqa: E402

DOCS = ROOT / "docs"
CONSEQUENTIAL_TOOLS = {"delete_file", "move_file", "rename_file", "uninstall_software", "install_software", "send_whatsapp_message",
                       "send_whatsapp_bulk", "reply_whatsapp_message", "reply_whatsapp_all", "system_power_control", "close_app",
                       "empty_recycle_bin", "calendar_create_event", "android_dial", "gmail_create_draft", "browser_click", "screen_click",
                       "ui_op", "web_task", "computer_task", "powershell_command", "localsend_file"}
PHASE_NAMES = {
    "01_router": "Router / casual / typos", "02_core_os": "Core OS", "03_safety": "Safety", "04_whatsapp": "WhatsApp",
    "05_multistep": "Multi-step planning", "06_files": "Files", "07_intelligence": "Intelligence", "08_voice_output": "Voice output",
    "09_phone": "Phone", "10_google": "Google", "11_browser_control": "Browser control", "12_vision": "Vision",
    "13_pc_control": "PC control", "14_history_memory": "History / memory", "15_chat": "Chat / conversation",
    "16_tanglish": "Tanglish", "17_voice_input": "Voice input / keyboard / dictation", "18_operator": "Universal operator",
    "19_browser_automation": "Browser automation", "20_phone_calls": "Phone calls", "21_automation": "Automation / watchers",
    "22_workflows_dev": "Workflows / developer agent"}
# argument name -> slot type, for slot metrics by type
SLOT_TYPES = {
    "recipient": "recipient", "to": "recipient", "to_name": "recipient", "contact": "contact", "who": "contact", "sender": "sender constraint",
    "name": "application / target name", "app": "application / target name", "app_name": "application / target name",
    "app1": "application / target name", "app2": "application / target name", "target_app": "application / target name",
    "path": "file / folder", "source": "file / folder", "destination": "file / folder", "file_path": "file / folder",
    "video_path": "file / folder", "media_path": "file / folder", "document_path": "file / folder", "folder": "file / folder",
    "directory": "file / folder", "repo_path": "file / folder", "project_path": "file / folder", "project_name": "file / folder",
    "url": "URL", "start_url": "URL", "query": "query", "question": "query", "goal": "query",
    "message": "message body", "text": "message body / text", "instruction": "message body", "content": "message body / text",
    "summary": "message body / text", "subject": "message body / text",
    "when": "date / time", "time_window": "time range", "time_hint": "time range", "minutes": "date / time",
    "limit": "count", "times": "count", "length": "count", "n": "count", "count": "count", "max_results": "count",
    "percent": "number", "value": "number", "threshold": "number", "number": "number", "duration_minutes": "number",
    "ordinal": "ordinal", "which": "ordinal", "type_hint": "file type", "file_extension": "file type", "types": "file type",
    "setting": "device setting", "page": "settings page", "key": "key", "action": "action / mode", "mode": "action / mode",
    "layout": "action / mode", "direction": "direction", "condition": "condition", "only": "include constraint",
    "option": "option", "tab": "browser tab", "label": "browser element", "role": "browser element"}


def pct(x) -> str:
    return "-" if x is None else f"{100 * x:.1f}%"


def ratio(a, b):
    return (a / b) if b else None


def f1(p, r):
    return (2 * p * r / (p + r)) if (p is not None and r is not None and p + r) else None


def classify(case: dict, row: dict) -> tuple[str, str]:
    """(primary, secondary) failure cause for a failed case."""
    s, out = row["score"], row["out"]
    exp, got = s["exp_kind"], s["got_kind"]
    cons = {c.get("type") for c in case.get("constraints") or []}
    if s["forbidden_values_hit"]:
        if "negation" in cons:
            return "NEGATION_LOST", "SLOT_WRONG"
        if "correction" in cons:
            return "CORRECTION_LOST", "SLOT_WRONG"
        return "SLOT_WRONG", "CONSTRAINT_LOST"
    if s.get("forbidden_cap_hit") and exp in ("refuse", "clarify", "chat"):
        return "POLICY_WRONG", "TOOL_WRONG"
    if exp in ("refuse", "clarify", "chat") and s["acted"]:
        return ("POLICY_WRONG" if exp in ("refuse", "clarify") else "INTENT_WRONG"), "ROUTER_WRONG"
    if exp in ("action", "control") and got == "plan":
        return "DEPENDENCY_UNAVAILABLE", "ROUTER_DEFERRED_TO_MODEL"
    if exp == "plan" and got != "plan":
        return ("PLANNER_WRONG" if s["acted"] else "ROUTER_WRONG"), ""
    if exp in ("action", "control") and got == "clarify":
        msg = (row.get("message") or "") + " " + " ".join(str(t.get("message", "")) for t in row.get("turns", []))
        if any(w in msg.lower() for w in ("can't", "cannot", "isn't something i can", "not something i can", "i don't")):
            return "UNSUPPORTED_CAPABILITY", "ROUTER_WRONG"
        return "ROUTER_WRONG", "OVER_CLARIFIED"
    if exp in ("action", "control") and got == "refuse":
        return "POLICY_WRONG", "OVER_REFUSED"
    if exp in ("action", "control") and got == "chat":
        return "INTENT_WRONG", "ROUTER_WRONG"
    if exp in ("refuse",) and got == "clarify" or exp == "clarify" and got == "refuse":
        return "POLICY_WRONG", "WRONG_SAFE_BEHAVIOUR"
    if exp == "chat" and got in ("clarify", "refuse", "plan"):
        return "INTENT_WRONG", "ROUTER_WRONG"
    if s["acted"] and s["cap_ok"] is False:
        return ("REFERENCE_WRONG" if case.get("context") else "TOOL_WRONG"), "CAPABILITY_RETRIEVAL_WRONG"
    if s["cap_ok"] and not s["slots_ok"]:
        statuses = {x["status"] for x in s["slots"] if not x["ok"]}
        base = "SLOT_DROPPED" if statuses == {"missing"} else "SLOT_WRONG"
        if case.get("context") or case.get("reference"):
            return "REFERENCE_WRONG", base
        return base, ""
    if s.get("plan_ok") is False:
        return "PLANNER_WRONG", "STEP_ORDER"
    if s.get("confirmation_ok") is False:
        return "POLICY_WRONG", "CONFIRMATION"
    ex = row.get("exec") or {}
    if ex.get("status") == "checked" and ex.get("ok") is False:
        return "EXECUTION_FAILED", ""
    if ex.get("status") == "checked_unchanged" and ex.get("ok") is False:
        return "SAFETY_WRONG", "SANDBOX_CHANGED"
    if row.get("state") == "ERROR":
        return "EXECUTION_FAILED", "EXCEPTION"
    return "UNKNOWN", ""


def case_exact_e2e(case: dict, row: dict) -> tuple[bool, str]:
    """End-to-end verdict for run B: semantic contract + real postcondition when the case has one."""
    if not row["score"]["exact_semantic"]:
        return False, "semantic"
    ex = row.get("exec") or {}
    if case.get("exec"):
        if ex.get("status") in ("checked", "checked_unchanged"):
            return bool(ex.get("ok")), "verified" if ex.get("ok") else "postcondition"
        return False, "unverifiable"
    if row["score"]["exp_kind"] == "plan":
        return False, "unverifiable"
    return True, "no_postcondition"


def metrics(cases: dict, rows: list[dict], run: str) -> dict:
    m = {"n": len(rows), "lat": [], "_tp": Counter(), "_fp": Counter(), "_fn": Counter()}
    if not rows:
        return m
    exact = [r for r in rows if r["score"]["exact_semantic"]]
    m["exact"] = ratio(len(exact), len(rows))
    m["intent"] = ratio(sum(r["score"]["intent_ok"] for r in rows), len(rows))
    should = [r for r in rows if cases[r["id"]]["should_act"]]
    must_not = [r for r in rows if not cases[r["id"]]["should_act"]]
    acted = [r for r in rows if r["score"]["acted"]]
    acted_ok = [r for r in acted if r["score"]["exact_semantic"]]
    m["act_p"] = ratio(len(acted_ok), len(acted))
    m["act_r"] = ratio(sum(1 for r in should if r["score"]["acted"] and r["score"]["exact_semantic"]), len(should))
    m["act_f1"] = f1(m["act_p"], m["act_r"])
    m["acted"], m["should_act"], m["must_not"] = len(acted), len(should), len(must_not)
    m["specificity"] = ratio(sum(1 for r in must_not if not r["score"]["acted"]), len(must_not))
    m["false_action_rate"] = ratio(sum(1 for r in must_not if r["score"]["acted"]), len(must_not))
    # tools
    tp, fp, fn = Counter(), Counter(), Counter()
    for r in rows:
        c = cases[r["id"]]
        gold = (c.get("capabilities") or [None])[0] if c["outcome"] in ("action", "control") else None
        pred = (r["score"]["tools"] or [None])[0] if r["score"]["acted"] else None
        if r["score"]["acted"] and r["score"]["cap_ok"]:
            tp[r["score"]["chosen"]] += 1
        else:
            if pred:
                fp[pred] += 1
            if gold:
                fn[gold] += 1
    T, F, N = sum(tp.values()), sum(fp.values()), sum(fn.values())
    m["tool_p"], m["tool_r"] = ratio(T, T + F), ratio(T, T + N)
    m["tool_f1"] = f1(m["tool_p"], m["tool_r"])
    tools = set(tp) | set(fp) | set(fn)
    ps = [tp[t] / (tp[t] + fp[t]) for t in tools if tp[t] + fp[t]]
    rs = [tp[t] / (tp[t] + fn[t]) for t in tools if tp[t] + fn[t]]
    m["tool_macro_p"] = statistics.mean(ps) if ps else None
    m["tool_macro_r"] = statistics.mean(rs) if rs else None
    m["tool_macro_f1"] = f1(m["tool_macro_p"], m["tool_macro_r"])
    m["_tp"], m["_fp"], m["_fn"] = tp, fp, fn
    # slots
    stp = sfp = sfn = 0
    slot_cases = slot_exact = 0
    by_type = defaultdict(lambda: [0, 0])
    for r in rows:
        sl = r["score"]["slots"]
        if not sl:
            continue
        slot_cases += 1
        slot_exact += all(x["ok"] for x in sl)
        for x in sl:
            t = SLOT_TYPES.get(x["slot"], x["slot"])
            by_type[t][1] += 1
            if x["ok"]:
                stp += 1
                by_type[t][0] += 1
            elif x["status"] == "missing":
                sfn += 1
            else:
                sfn += 1
                sfp += 1
        sfp += len(r["score"]["forbidden_values_hit"])
    m["slot_exact"] = ratio(slot_exact, slot_cases)
    m["slot_p"], m["slot_r"] = ratio(stp, stp + sfp), ratio(stp, stp + sfn)
    m["slot_f1"] = f1(m["slot_p"], m["slot_r"])
    m["slot_by_type"] = {k: ratio(*v) for k, v in by_type.items()}
    # constraints
    def cons_rate(kind=None):
        sel = [r for r in rows if any(kind is None or c.get("type") == kind for c in cases[r["id"]].get("constraints") or [])]
        return ratio(sum(r["score"]["exact_semantic"] for r in sel), len(sel)), len(sel)
    m["constraint"], m["constraint_n"] = cons_rate()
    m["negation"], m["negation_n"] = cons_rate("negation")
    m["correction"], m["correction_n"] = cons_rate("correction")
    # clarification
    exp_c = [r for r in rows if cases[r["id"]]["outcome"] == "clarify"]
    got_c = [r for r in rows if r["score"]["got_kind"] == "clarify"]
    both = [r for r in exp_c if r["score"]["got_kind"] == "clarify"]
    m["clar_p"], m["clar_r"] = ratio(len(both), len(got_c)), ratio(len(both), len(exp_c))
    m["clar_f1"] = f1(m["clar_p"], m["clar_r"])
    # reference / context
    ref = [r for r in rows if cases[r["id"]].get("context") or cases[r["id"]].get("reference")]
    m["reference"], m["reference_n"] = ratio(sum(r["score"]["exact_semantic"] for r in ref), len(ref)), len(ref)
    # plans
    pl = [r for r in rows if cases[r["id"]].get("steps") or cases[r["id"]]["outcome"] == "plan"]
    m["plan_validity"] = ratio(sum(1 for r in pl if r["score"]["exact_semantic"] and r["score"].get("plan_ok") is not False), len(pl))
    m["plan_n"] = len(pl)
    # critical
    crit = Counter()
    for r in rows:
        c = cases[r["id"]]
        if r["score"]["acted"] and not r["score"]["exact_semantic"] and c.get("criticality") in ("C3", "C4"):
            crit[c["criticality"]] += 1
        elif r["score"]["acted"] and r["score"].get("forbidden_cap_hit") and c.get("criticality") not in ("C3", "C4"):
            crit["forbidden-tool"] += 1
    m["c3"], m["c4"] = crit["C3"], crit["C4"]
    m["critical"] = crit["C3"] + crit["C4"]
    if run == "B":
        e2e = [case_exact_e2e(cases[r["id"]], r) for r in rows]
        m["e2e_verified"] = ratio(sum(1 for ok, why in e2e if ok and why == "verified"), sum(1 for r in rows if cases[r["id"]].get("exec")))
        m["e2e_unverifiable"] = sum(1 for ok, why in e2e if why == "unverifiable")
        ex = [r for r in rows if (r.get("exec") or {}).get("status") == "checked"]
        m["exec_success"] = ratio(sum(1 for r in ex if r["exec"].get("ok")), len(ex))
        m["exec_n"] = len(ex)
        m["exec_unavailable"] = sum(1 for r in rows if (r.get("exec") or {}).get("status") in ("dependency_unavailable", "checked_no_real_tool"))
        ver = [r["verify"] for r in rows if r.get("verify")]
        m["verify"] = ratio(sum(v["correct"] for v in ver), len(ver))
        m["false_success"] = sum(v["false_success"] for v in ver)
        m["false_failure"] = sum(v["false_failure"] for v in ver)
        m["verify_n"] = len(ver)
        m["unsupported"] = ratio(sum(r.get("unsupported_claim", False) for r in rows), len(rows))
        # consequential negation / correction preservation: on cases with a negation or correction, the negated or
        # superseded consequential action never runs (no forbidden capability or value in a consequential call)
        neg = [r for r in rows if {c.get("type") for c in cases[r["id"]].get("constraints") or []} & {"negation", "correction"}]
        def _violates(r):
            if not r["score"]["acted"]:
                return False
            tools = [t for t, *_ in ((r.get("turns") or [{}])[-1].get("calls") or [])]
            return bool(set(tools) & CONSEQUENTIAL_TOOLS) and bool(r["score"].get("forbidden_cap_hit") or r["score"].get("forbidden_values_hit"))
        m["neg_preserve"] = ratio(sum(not _violates(r) for r in neg), len(neg))
        m["neg_preserve_n"] = len(neg)
        lat = sorted(r.get("total_ms", 0) for r in rows)
        m["lat"] = lat
        m["blocked"] = sum(len(r.get("blocked") or []) for r in rows)
    else:
        m["lat"] = sorted(r.get("routing_ms", 0) for r in rows)
    return m


def q(lat, p):
    if not lat:
        return None
    return lat[min(len(lat) - 1, int(round(p * (len(lat) - 1))))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_a")
    ap.add_argument("run_b")
    ap.add_argument("--errata", default=str(Path(__file__).with_name("errata.json")))
    ap.add_argument("--cases", default=None)
    ap.add_argument("--docs", default=None, help="output folder (default: docs/)")
    a = ap.parse_args()
    global DOCS
    if a.docs:
        DOCS = Path(a.docs)
    cases = {c["id"]: c for c in (load_cases(Path(a.cases)) if a.cases else load_cases())}
    A = json.load(open(a.run_a))
    B = json.load(open(a.run_b))
    errata = json.load(open(a.errata)) if Path(a.errata).exists() else {}
    rows_a, rows_b = A["rows"], B["rows"]
    aud_b = [r for r in rows_b if r["id"] not in errata]
    aud_a = [r for r in rows_a if r["id"] not in errata]
    phases = list(PHASE_NAMES)
    MB = {p: metrics(cases, [r for r in rows_b if r["phase"] == p], "B") for p in phases}
    MA = {p: metrics(cases, [r for r in rows_a if r["phase"] == p], "A") for p in phases}
    MBa = {p: metrics(cases, [r for r in aud_b if r["phase"] == p], "B") for p in phases}
    allB, allA, allBa, allAa = metrics(cases, rows_b, "B"), metrics(cases, rows_a, "A"), metrics(cases, aud_b, "B"), metrics(cases, aud_a, "A")
    DOCS.mkdir(exist_ok=True)
    # ---- CSVs
    with open(DOCS / "BLIND11_PHASE_METRICS.csv", "w", newline="") as f:
        w = csv.writer(f)
        cols = ["exact", "intent", "act_p", "act_r", "act_f1", "tool_p", "tool_r", "tool_f1", "slot_exact", "slot_f1", "constraint",
                "negation", "specificity", "false_action_rate", "clar_f1", "exec_success", "verify", "unsupported", "reference", "critical"]
        w.writerow(["run", "phase", "cases"] + cols + ["p50_ms", "p95_ms", "p99_ms"])
        for run, M in (("B_strict", MB), ("B_audited", MBa), ("A_router", MA)):
            for p in phases:
                m = M[p]
                w.writerow([run, p, m["n"]] + [("" if m.get(k) is None else round(m[k], 4)) for k in cols]
                           + [round(q(m["lat"], .5) or 0, 1), round(q(m["lat"], .95) or 0, 1), round(q(m["lat"], .99) or 0, 1)])
    with open(DOCS / "BLIND11_TOOL_METRICS.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["run", "tool", "TP", "FP", "FN", "precision", "recall", "F1", "exec_checked", "exec_ok"])
        for run, m, rows in (("B", allB, rows_b), ("A", allA, rows_a)):
            for t in sorted(set(m["_tp"]) | set(m["_fp"]) | set(m["_fn"])):
                tp, fp, fn = m["_tp"][t], m["_fp"][t], m["_fn"][t]
                p, r = ratio(tp, tp + fp), ratio(tp, tp + fn)
                ex = [x for x in rows if x["score"].get("chosen") == t and (x.get("exec") or {}).get("status") == "checked"]
                w.writerow([run, t, tp, fp, fn, "" if p is None else round(p, 4), "" if r is None else round(r, 4),
                            "" if f1(p, r) is None else round(f1(p, r), 4), len(ex), sum(1 for x in ex if x["exec"].get("ok"))])
    conf = Counter()
    for r in rows_b:
        c = cases[r["id"]]
        gold = (c.get("capabilities") or [c["outcome"].upper()])[0] if c["outcome"] in ("action", "control") else c["outcome"].upper()
        pred = r["score"]["chosen"] or ((r["score"]["tools"] or [r["score"]["got_kind"].upper()])[0] if r["score"]["acted"] else r["score"]["got_kind"].upper())
        if not r["score"]["exact_semantic"]:
            conf[(gold, pred)] += 1
    with open(DOCS / "BLIND11_CONFUSION_MATRIX.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["expected", "got", "count"])
        for (g, p), n in conf.most_common():
            w.writerow([g, p, n])
    with open(DOCS / "BLIND11_LATENCY.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["measure", "p50_ms", "p95_ms", "p99_ms", "n"])
        w.writerow(["routing (run A, router only, model off)", round(q(allA["lat"], .5), 2), round(q(allA["lat"], .95), 2), round(q(allA["lat"], .99), 2), len(allA["lat"])])
        w.writerow(["final response (run B, command service, model off)", round(q(allB["lat"], .5), 1), round(q(allB["lat"], .95), 1), round(q(allB["lat"], .99), 1), len(allB["lat"])])
        for key in ("routing_ms", "planning_ms", "execution_ms", "verification_ms", "first_action_ms", "total_ms"):
            vals = sorted(float(r["metrics"][key]) for r in rows_b if isinstance(r.get("metrics"), dict) and r["metrics"].get(key) is not None)
            if vals:
                w.writerow([f"{key} (run B, from the service clock)", round(q(vals, .5), 1), round(q(vals, .95), 1), round(q(vals, .99), 1), len(vals)])
    # ---- failures
    causes = Counter()
    fl = ["# Blind-11 failures (run B, strict)", "",
          "Every failed case: the expected semantic action, what JARVIS did, the slots, whether it should and did act, the "
          "verified result, the criticality and one primary cause. Generated by `python -m tests.blind11.report`.", ""]
    for p in phases:
        fails = [r for r in rows_b if r["phase"] == p and not r["score"]["exact_semantic"]]
        fl += [f"## {PHASE_NAMES[p]} ({len(fails)} failed)", ""]
        if not fails:
            fl += ["No failures.", ""]
            continue
        fl += ["| ID | Command | Expected | Got | Expected slots | Actual slots | Should act | Did act | Verified | Crit | Cause |",
               "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in fails:
            c = cases[r["id"]]
            prim, sec = classify(c, r)
            causes[prim] += 1
            r["cause"] = prim
            exp = f"{c['outcome']} {'/'.join(c.get('capabilities') or [])}".strip()
            got = f"{r['score']['got_kind']} {'/'.join(r['score']['tools'][:2])}".strip()
            es = "; ".join(f"{x['slot']}={'/'.join(map(str, x['expected']))[:30]}" for x in r["score"]["slots"])
            as_ = "; ".join(f"{x['slot']}={str(x['actual'])[:30]}" for x in r["score"]["slots"])
            if r["score"]["forbidden_values_hit"]:
                as_ += f" (forbidden: {', '.join(r['score']['forbidden_values_hit'])})"
            ex = (r.get("exec") or {}).get("status", "")
            if (r.get("exec") or {}).get("status") == "checked":
                ex = "ok" if r["exec"].get("ok") else "FAILED"
            ctx = (" ← " + " / ".join(c["context"])) if c.get("context") else ""
            cell = lambda x: str(x).replace("|", "/").replace("\n", " ")
            fl.append("| " + " | ".join(cell(x) for x in (r["id"], c["utterance"] + ctx, exp, got, es, as_, "yes" if c["should_act"] else "no",
                                                         "yes" if r["score"]["acted"] else "no", ex, c.get("criticality", ""),
                                                         prim + (f" ({sec})" if sec else ""))) + " |")
        fl.append("")
    (DOCS / "BLIND11_FAILURES.md").write_text("\n".join(fl) + "\n")
    # ---- report
    L = ["# Blind-11: unseen end-to-end validation", ""]
    L += [f"Cases: {len(cases)} (22 phases x 50). Locked dataset sha256 `{B['cases_sha256']}` (see `tests/blind11/MANIFEST.json`).", ""]
    L += ["## Headline (run B: command service, model unavailable, real sandbox execution where possible)", "",
          "| | Exact action | Action precision | Action recall | Action F1 | Intent | Slot exact | Slot F1 | Constraints | Specificity | False-action rate | Critical wrong actions |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, m in (("Strict (as locked)", allB), (f"Audited ({len(errata)} oracle errata removed)", allBa)):
        L.append(f"| {name} | **{pct(m['exact'])}** | {pct(m['act_p'])} | {pct(m['act_r'])} | {pct(m['act_f1'])} | {pct(m['intent'])} | "
                 f"{pct(m['slot_exact'])} | {pct(m['slot_f1'])} | {pct(m['constraint'])} | {pct(m['specificity'])} | "
                 f"{pct(m['false_action_rate'])} | **{m['critical']}** (C3 {m['c3']}, C4 {m['c4']}) |")
    L += ["", "| | Value |", "|---|---:|",
          f"| Reference / context resolution | {pct(allB['reference'])} ({allB['reference_n']} cases) |",
          f"| Plan validity | {pct(allB['plan_validity'])} ({allB['plan_n']} cases) |",
          f"| Execution success (real postcondition checked) | {pct(allB['exec_success'])} ({allB['exec_n']} executed) |",
          f"| End-to-end verified (cases with a postcondition) | {pct(allB['e2e_verified'])} |",
          f"| Postcondition not verifiable here (dependency unavailable) | {allB['exec_unavailable']} cases |",
          f"| Verification accuracy (what JARVIS said vs the real result) | {pct(allB['verify'])} ({allB['verify_n']} cases; false success {allB['false_success']}, false failure {allB['false_failure']}) |",
          f"| Unsupported-claim rate | {pct(allB['unsupported'])} |",
          f"| Clarification P / R / F1 | {pct(allB['clar_p'])} / {pct(allB['clar_r'])} / {pct(allB['clar_f1'])} |",
          f"| Tool micro P / R / F1 | {pct(allB['tool_p'])} / {pct(allB['tool_r'])} / {pct(allB['tool_f1'])} |",
          f"| Tool macro P / R / F1 | {pct(allB['tool_macro_p'])} / {pct(allB['tool_macro_r'])} / {pct(allB['tool_macro_f1'])} |",
          f"| Negation / correction accuracy | {pct(allB['negation'])} ({allB['negation_n']}) / {pct(allB['correction'])} ({allB['correction_n']}) |",
          f"| Consequential negation / correction preservation (the negated or superseded consequential action never ran) | {pct(allB.get('neg_preserve'))} ({allB.get('neg_preserve_n', 0)}) |",
          f"| Sandbox writes blocked outside the sandbox | {allB['blocked']} |",
          f"| Latency p50 / p95 / p99 (final response, run B) | {q(allB['lat'], .5):.0f} / {q(allB['lat'], .95):.0f} / {q(allB['lat'], .99):.0f} ms |",
          f"| Routing latency p50 / p95 / p99 (run A) | {q(allA['lat'], .5):.1f} / {q(allA['lat'], .95):.1f} / {q(allA['lat'], .99):.1f} ms |", ""]
    L += ["## Run A (router / orchestration diagnostic, no execution)", "",
          f"Exact (semantic) {pct(allA['exact'])} strict, {pct(allAa['exact'])} audited; action precision {pct(allA['act_p'])}, recall "
          f"{pct(allA['act_r'])}; critical {allA['critical']}.", ""]
    L += ["## Per phase (run B, strict)", "",
          "| Phase | Exact | Intent | Act P | Act R | Act F1 | Slot F1 | Constraint | Specificity | Exec | Verify | Critical |",
          "|------|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|"]
    for p in phases:
        m = MB[p]
        if not m["n"]:
            continue
        L.append(f"| {PHASE_NAMES[p]} | {pct(m['exact'])} | {pct(m['intent'])} | {pct(m['act_p'])} | {pct(m['act_r'])} | {pct(m['act_f1'])} | "
                 f"{pct(m['slot_f1'])} | {pct(m['constraint'])} | {pct(m['specificity'])} | {pct(m['exec_success'])} | {pct(m['verify'])} | {m['critical']} |")
    L += ["", "Full per-phase columns (tool P/R/F1, slot exact, negation, false-action rate, clarification, unsupported claims, "
          "latency, strict / audited / run A) are in `docs/BLIND11_PHASE_METRICS.csv`.", "",
          "## Failure causes (run B, strict)", "", "| Primary cause | Cases |", "|---|---:|"]
    for k, v in causes.most_common():
        L.append(f"| {k} | {v} |")
    L += ["", "## Biggest capability confusions", "", "| Expected | Got | Cases |", "|---|---|---:|"]
    for (g, p), n in conf.most_common(25):
        L.append(f"| {g} | {p} | {n} |")
    L += ["", "## Slot accuracy by type (run B)", "", "| Slot type | Correct |", "|---|---:|"]
    for k, v in sorted(allB["slot_by_type"].items(), key=lambda kv: kv[0]):
        L.append(f"| {k} | {pct(v)} |")
    (DOCS / "BLIND11_REPORT.md").write_text("\n".join(L) + "\n")
    print(f"B strict exact {pct(allB['exact'])} audited {pct(allBa['exact'])}; A exact {pct(allA['exact'])}; critical {allB['critical']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
