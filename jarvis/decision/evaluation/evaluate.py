"""Offline JDE benchmark -> reports/JDE_BENCHMARK.md (+ JSON).

    python -m jarvis.decision.evaluation.evaluate [--model DIR] [--encoders hash,minilm+hash,bge-small+hash] [--latency 10000]

Measures, on DEVELOPMENT / FINAL_HOLDOUT / ADVERSARIAL suites (never trained on):
route accuracy, Top-K family recall, per-head accuracy (actionability, needs_llm, planner P/R, web,
context, external effect, destructive, ambiguity, unknown), ECE / Brier / reliability, confusion
between the critical family pairs, gate outcomes (auto-execute rate, wrong executions,
wrong *consequential* executions), and routing latency (cold / warm / cache hit, p50/p95/p99).
Also compares the CURRENT router against CURRENT router + JDE (JDE only where L0 did not decide).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import resource
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Optional

import numpy as np

from jarvis.decision.calibration import brier_binary, brier_multiclass, ece, reliability_table
from jarvis.decision.catalog import default_catalog, family_for_tool
from jarvis.decision.dataset import load_suite
from jarvis.decision.engine import LocalJDE, latest_model_dir
from jarvis.decision.schemas import BINARY_HEADS, ROUTE_FAMILIES, DecisionState, LabeledExample

ROOT = Path(__file__).resolve().parents[3]
CONSEQUENTIAL = ("EXTERNAL_EFFECT", "DESTRUCTIVE", "PRIVILEGED")
CRITICAL_PAIRS = [("KNOWLEDGE", "APP"), ("KNOWLEDGE", "WHATSAPP"), ("KNOWLEDGE", "PACKAGE"), ("RAG", "WEB"),
                  ("BROWSER", "DESKTOP"), ("PHONE", "TRANSFER"), ("PLANNER", "WHATSAPP"), ("CLARIFY", "WHATSAPP"),
                  ("CLARIFY", "TRANSFER"), ("KNOWLEDGE", "WEB"), ("FILE", "RAG")]


def evaluate_split(engine: LocalJDE, examples: list[LabeledExample]) -> dict[str, Any]:
    states = [e.state() for e in examples]
    X, E = engine.featurize(states)
    out = engine.raw_outputs(X, E)
    fam = {f: i for i, f in enumerate(engine.families)}
    y = np.array([fam[e.route] for e in examples])
    route = out["route"]
    pred = route.argmax(axis=1)
    conf = route.max(axis=1)
    correct = (pred == y).astype(float)
    top3 = np.argsort(-route, axis=1)[:, :3]
    res: dict[str, Any] = {"n": len(examples), "route_acc": float(correct.mean()),
                           "route_top3": float(np.mean([y[i] in top3[i] for i in range(len(y))])),
                           "route_ece": ece(conf, correct), "route_brier": brier_multiclass(route, y),
                           "reliability": reliability_table(conf, correct)}
    heads = {}
    for h in BINARY_HEADS:
        p = out[h]
        t = np.array([e.binary(h) for e in examples])
        pr = (p >= 0.5).astype(int)
        tp, fp, fn = int(((pr == 1) & (t == 1)).sum()), int(((pr == 1) & (t == 0)).sum()), int(((pr == 0) & (t == 1)).sum())
        heads[h] = {"acc": float((pr == t).mean()), "precision": tp / (tp + fp) if tp + fp else 1.0,
                    "recall": tp / (tp + fn) if tp + fn else 1.0, "ece": ece(np.where(pr == 1, p, 1 - p), (pr == t).astype(float)),
                    "brier": brier_binary(p, t), "positives": int(t.sum())}
    res["heads"] = heads

    # coverage of all required families in the top-5 decision families
    cover = []
    decisions = [engine._interpret(states[i], {k: v[i] for k, v in out.items()}) for i in range(len(examples))]
    for ex, d in zip(examples, decisions):
        got = {f for f, _ in d.families} | {f for f, _ in d.route.top_k}
        need = set(ex.families or [ex.route])
        cover.append(need <= got)
    res["family_coverage_at5"] = float(np.mean(cover))

    # gate outcomes
    gates = Counter(d.gate.action for d in decisions)
    wrong_exec, wrong_conseq, exec_n = [], [], 0
    for ex, d in zip(examples, decisions):
        if d.gate.action != "EXECUTE":
            continue
        exec_n += 1
        ok = d.route.value == ex.route and (ex.is_action or ex.route in ("KNOWLEDGE", "RAG", "WEB"))
        if not ok:
            wrong_exec.append((ex.text, ex.route, d.route.value, round(d.route.confidence, 3)))
            if ex.external_effect or ex.destructive or d.gate.risk_class in CONSEQUENTIAL:
                if d.p("is_action") >= 0.5:
                    wrong_conseq.append((ex.text, ex.route, d.route.value, round(d.route.confidence, 3)))
    res["gates"] = dict(gates)
    res["auto_execute_rate"] = exec_n / len(examples)
    res["execute_precision"] = 1 - len(wrong_exec) / exec_n if exec_n else 1.0
    res["wrong_executions"] = wrong_exec
    res["wrong_consequential_executions"] = wrong_conseq
    # abstention quality: CLARIFY/UNKNOWN cases handled by a non-execute gate
    clar = [(ex, d) for ex, d in zip(examples, decisions) if ex.route in ("CLARIFY", "UNKNOWN")]
    res["unknown_clarify_detection"] = float(np.mean([d.gate.action in ("CLARIFY", "UNSUPPORTED", "ABSTAIN") or d.route.value in ("CLARIFY", "UNKNOWN")
                                                      for _, d in clar])) if clar else None
    conf_m = defaultdict(Counter)
    for ex, d in zip(examples, decisions):
        conf_m[ex.route][d.route.value] += 1
    res["confusion"] = {k: dict(v) for k, v in conf_m.items()}
    res["errors"] = [(ex.text, ex.route, d.route.value, round(d.route.confidence, 3)) for ex, d in zip(examples, decisions)
                     if d.route.value != ex.route][:40]
    return res


# ------------------------------------------------------------------ current router comparison
def router_family(dec) -> str:
    """Map an existing RouteDecision to a JDE family (for an apples-to-apples comparison)."""
    lane = getattr(dec.lane, "value", str(dec.lane))
    reason = str(getattr(dec, "reason_code", ""))
    trace = dec.context_trace or {}
    if lane == "CLARIFY":
        return "CLARIFY" if dec.intent in (None, "clarify") or dec.missing_slots else family_for_tool(dec.intent)
    if lane == "REJECT":
        return "NEGATED"
    if lane == "CONTROL":
        return "SYSTEM"
    if dec.intent == "ollama_chat" and trace.get("fallback") == "unknown_command":
        return "PLANNER"   # agent fallback
    if dec.intent in ("ollama_chat",):
        return "KNOWLEDGE"
    if lane == "LANE_2":
        return "KNOWLEDGE" if "QUESTION" in reason else "PLANNER"
    if dec.intent:
        if dec.intent in ("search_web", "search_news"):
            return "WEB"
        return family_for_tool(dec.intent)
    return "UNKNOWN"


def router_is_l0(dec) -> bool:
    """Did the deterministic layers decide (i.e. JDE would not run in the combined system)?"""
    lane = getattr(dec.lane, "value", str(dec.lane))
    trace = dec.context_trace or {}
    src = str(getattr(dec.source, "value", dec.source))
    if trace.get("fallback") == "unknown_command":
        return False
    if lane in ("CONTROL", "REJECT"):
        return True
    if lane == "LANE_0" and src in ("EXACT", "GRAMMAR", "FUZZY", "CACHE", "RULE", "DIRECT") and dec.intent:
        return True
    return False


def compare_with_router(engine: LocalJDE, examples: list[LabeledExample]) -> dict[str, Any]:
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter
    from jarvis.memory.working_memory import WorkingMemory

    async def route_all():
        router = SmartRouter(llm_provider=DisabledProvider(), working_memory=WorkingMemory())
        out = []
        for ex in examples:
            out.append(await router.route(ex.text))
        return out

    decisions = asyncio.run(route_all())
    cur_ok, comb_ok, l0_n, planner_calls_cur, planner_calls_comb, llm_calls_cur, llm_calls_comb = 0, 0, 0, 0, 0, 0, 0
    wrong_conseq_cur, wrong_conseq_comb = 0, 0
    stage_b = {"agent_fallbacks": 0, "diverted_to_chat": 0, "diverted_correct": 0, "diverted_wrong_action": 0}
    for ex, dec in zip(examples, decisions):
        fam_cur = router_family(dec)
        ok_cur = fam_cur == ex.route or (fam_cur == "NEGATED" and not ex.is_action)
        cur_ok += ok_cur
        consequential = ex.external_effect or ex.destructive
        lane = getattr(dec.lane, "value", str(dec.lane))
        executes_cur = lane in ("LANE_0", "LANE_1") and dec.intent not in (None, "ollama_chat", "clarify")
        if executes_cur and not ok_cur and (consequential or family_for_tool(dec.intent or "") in ("WHATSAPP", "GOOGLE")):
            wrong_conseq_cur += 1
        planner_calls_cur += fam_cur == "PLANNER"
        llm_calls_cur += fam_cur in ("PLANNER", "KNOWLEDGE", "WEB", "RAG") or (lane == "LANE_1")
        if router_is_l0(dec):
            l0_n += 1
            comb_ok += ok_cur
            planner_calls_comb += fam_cur == "PLANNER"
            llm_calls_comb += fam_cur in ("PLANNER", "KNOWLEDGE", "WEB", "RAG")
            if executes_cur and not ok_cur and consequential:
                wrong_conseq_comb += 1
            continue
        d = engine.decide(ex.state())
        fam = d.route.value
        lane_v = getattr(dec.lane, "value", str(dec.lane))
        # With no LLM, an unmatched request ends as CLARIFY without an intent; with Ollama running the router turns
        # exactly those into the unknown_command agent fallback (router.py), so both count as eligible.
        if (dec.context_trace or {}).get("fallback") == "unknown_command" or (lane_v == "CLARIFY" and not dec.intent and not dec.missing_slots):
            # stage B (read_only): exactly the rule in jarvis.decision.runtime.JDERuntime.answer_as_knowledge
            stage_b["agent_fallbacks"] += 1
            if fam == "KNOWLEDGE" and d.gate.action == "EXECUTE" and d.p("external_effect") < 0.2 and d.p("destructive") < 0.1:
                stage_b["diverted_to_chat"] += 1
                stage_b["diverted_correct"] += ex.route in ("KNOWLEDGE", "RAG") and not (ex.external_effect or ex.destructive)
                stage_b["diverted_wrong_action"] += ex.is_action and ex.route not in ("KNOWLEDGE", "WEB", "RAG")
        if d.gate.action == "EXECUTE":
            ok = fam == ex.route and (d.p("is_action") >= 0.5) == ex.is_action
            if not ok and consequential:
                wrong_conseq_comb += 1
        elif d.gate.action in ("CLARIFY", "UNSUPPORTED", "ABSTAIN"):
            ok = ex.route in ("CLARIFY", "UNKNOWN") or not ex.is_action and fam == ex.route
        else:  # FALLBACK -> existing router behaviour
            ok = ok_cur
            fam = fam_cur
        comb_ok += ok
        planner_calls_comb += (fam == "PLANNER") or (d.model_class == "PLANNER")
        llm_calls_comb += d.model_class in ("SMALL", "PLANNER", "VISION", "TINY")
    n = len(examples)
    return {"n": n, "current_route_acc": cur_ok / n, "combined_route_acc": comb_ok / n, "l0_decided": l0_n / n,
            "planner_calls_current": planner_calls_cur, "planner_calls_combined": planner_calls_comb,
            "llm_calls_current": llm_calls_cur, "llm_calls_combined": llm_calls_comb,
            "wrong_consequential_current": wrong_conseq_cur, "wrong_consequential_combined": wrong_conseq_comb,
            "stage_b": stage_b}


# ------------------------------------------------------------------ latency
_WORDS = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike november oscar papa quebec romeo sierra tango uniform victor whiskey xray yankee zulu".split()


def latency(engine: LocalJDE, texts: list[str], n: int = 10000) -> dict[str, float]:
    engine.cache.clear()
    t = time.perf_counter()
    engine.decide(DecisionState(text="warm up the encoder"))
    first = (time.perf_counter() - t) * 1000
    miss, hit = [], []
    for i in range(n):
        text = texts[i % len(texts)] + ("" if i < len(texts) else " " + " ".join(_WORDS[(i * k) % len(_WORDS)] for k in (1, 7, 13)))
        s = time.perf_counter()
        engine.decide(DecisionState(text=text))
        miss.append((time.perf_counter() - s) * 1000)
    for text in texts[:500]:
        engine.decide(DecisionState(text=text))  # ensure it is cached (the 10k miss loop evicts old entries)
        s = time.perf_counter()
        engine.decide(DecisionState(text=text))
        hit.append((time.perf_counter() - s) * 1000)
    miss.sort()
    q = lambda xs, p: xs[min(len(xs) - 1, int(p * len(xs)))]  # noqa: E731
    return {"first_call_ms": first, "miss_p50_ms": q(miss, 0.5), "miss_p95_ms": q(miss, 0.95), "miss_p99_ms": q(miss, 0.99),
            "hit_p50_ms": statistics.median(hit), "throughput_per_s": 1000 / statistics.mean(miss),
            "max_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024}


# ------------------------------------------------------------------ report
def _pct(x: Optional[float]) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def write_report(results: dict[str, Any], path: Path) -> None:
    lines = ["# JDE benchmark", "", f"Model `{results['model']}` · encoder `{results['encoder']}` · catalog `{results['catalog']}`",
             f"Generated {results['generated']} on {results['machine']}.", "",
             "Splits are never used for training, calibration, fusion weights or thresholds.", ""]
    S = results["splits"]
    wrong = sum(len(S[s]["wrong_consequential_executions"]) for s in S)
    route_ok = all(S[s]["route_acc"] >= 0.98 for s in S)
    lines += ["## Verdict", ""]
    if wrong == 0 and route_ok:
        lines.append("All splits meet the route target with zero wrong consequential executions: eligible for stage B review.")
    else:
        why = []
        if wrong:
            why.append(f"{wrong} wrong consequential execution(s) across splits (target 0)")
        if not route_ok:
            why.append("route accuracy below the 98% target on at least one split")
        lines.append("**JDE stays in SHADOW mode** (`[decision] stage = \"shadow\"`): " + "; ".join(why) + ". The existing router "
                     "remains the only thing that routes; JDE only logs its decision next to the router's.")
    lines += [""]
    lines += ["## Headline", "", "| Metric | Development | Final holdout | Adversarial | Target |", "|---|---|---|---|---|"]

    def row(label, f, target=""):
        lines.append(f"| {label} | " + " | ".join(f(S[s]) for s in ("dev", "holdout", "adversarial")) + f" | {target} |")

    row("Route family accuracy", lambda r: _pct(r["route_acc"]), "≥ 98%")
    row("Route top-3 recall", lambda r: _pct(r["route_top3"]))
    row("Required family coverage@5", lambda r: _pct(r["family_coverage_at5"]), "≥ 99%")
    row("Actionability accuracy", lambda r: _pct(r["heads"]["is_action"]["acc"]), "≥ 99%")
    row("Needs-LLM accuracy", lambda r: _pct(r["heads"]["needs_llm"]["acc"]), "≥ 98%")
    row("Needs-planner precision / recall", lambda r: f"{_pct(r['heads']['needs_planner']['precision'])} / {_pct(r['heads']['needs_planner']['recall'])}", "≥ 97%")
    row("Needs-web accuracy", lambda r: _pct(r["heads"]["needs_web"]["acc"]))
    row("Needs-context accuracy", lambda r: _pct(r["heads"]["needs_context"]["acc"]))
    row("External-effect accuracy", lambda r: _pct(r["heads"]["external_effect"]["acc"]))
    row("Destructive accuracy", lambda r: _pct(r["heads"]["destructive"]["acc"]))
    row("Ambiguity accuracy", lambda r: _pct(r["heads"]["ambiguous"]["acc"]))
    row("Unknown / clarify detection", lambda r: _pct(r["unknown_clarify_detection"]), "≥ 98%")
    row("Route ECE / Brier", lambda r: f"{r['route_ece']:.3f} / {r['route_brier']:.3f}")
    row("Auto-execute rate (gate)", lambda r: _pct(r["auto_execute_rate"]))
    row("Precision of auto-executed routes", lambda r: _pct(r["execute_precision"]))
    row("Wrong consequential executions", lambda r: str(len(r["wrong_consequential_executions"])), "0")
    lines += ["", "## Current router vs current router + JDE (same unseen cases, no LLM in either)", "",
              "| Split | L0 decided | Current router accuracy | Router + JDE accuracy | Planner/agent calls (cur → +JDE) | LLM calls (cur → +JDE) | Wrong consequential (cur → +JDE) |",
              "|---|---|---|---|---|---|---|"]
    for s, c in results["comparison"].items():
        lines.append(f"| {s} | {_pct(c['l0_decided'])} | {_pct(c['current_route_acc'])} | {_pct(c['combined_route_acc'])} | "
                     f"{c['planner_calls_current']} → {c['planner_calls_combined']} | {c['llm_calls_current']} → {c['llm_calls_combined']} | "
                     f"{c['wrong_consequential_current']} → {c['wrong_consequential_combined']} |")
    lines += ["", "## Stage B (read_only) effect", "",
              "Only requests the router cannot match (the `unknown_command` agent fallback) are eligible; JDE may send a",
              "calibrated KNOWLEDGE question to the read-only chat model instead of the tool-using agent.", "",
              "| Split | Agent fallbacks | Diverted to chat | Diverted & really a question | Diverted but really an action |", "|---|---|---|---|---|"]
    for s, c in results["comparison"].items():
        b = c.get("stage_b", {})
        lines.append(f"| {s} | {b.get('agent_fallbacks', 0)} | {b.get('diverted_to_chat', 0)} | {b.get('diverted_correct', 0)} | {b.get('diverted_wrong_action', 0)} |")
    lines += ["", "## Calibration (final holdout)", "", "Route family reliability (confidence bin → mean confidence vs accuracy):", "",
              "| Bin | n | Mean confidence | Accuracy |", "|---|---|---|---|"]
    for b, n, c, a in S["holdout"]["reliability"]:
        lines.append(f"| {b} | {n} | {c:.3f} | {a:.3f} |")
    lines += ["", "| Head | Accuracy | Precision | Recall | ECE | Brier |", "|---|---|---|---|---|---|"]
    for h, m in S["holdout"]["heads"].items():
        lines.append(f"| {h} | {_pct(m['acc'])} | {_pct(m['precision'])} | {_pct(m['recall'])} | {m['ece']:.3f} | {m['brier']:.3f} |")
    lines += ["", "## Critical confusions (holdout + adversarial + dev)", "", "| True → predicted | count |", "|---|---|"]
    for a, b in CRITICAL_PAIRS:
        n = sum(S[s]["confusion"].get(a, {}).get(b, 0) + S[s]["confusion"].get(b, {}).get(a, 0) for s in S)
        lines.append(f"| {a} ↔ {b} | {n} |")
    lines += ["", "## Latency (routing only, no execution)", ""]
    L = results["latency"]
    lines += [f"* first call (model already loaded): {L['first_call_ms']:.2f} ms",
              f"* cache miss p50 / p95 / p99: {L['miss_p50_ms']:.2f} / {L['miss_p95_ms']:.2f} / {L['miss_p99_ms']:.2f} ms over {results['latency_n']} requests",
              f"* cache hit p50: {L['hit_p50_ms']:.3f} ms · throughput {L['throughput_per_s']:.0f} decisions/s · process max RSS {L['max_rss_mb']:.0f} MB",
              f"* engine load (cold start): {results['load_ms']:.0f} ms"]
    if results.get("backbones"):
        lines += ["", "## Encoder backbones", "", "| Encoder | Holdout route acc | Adversarial route acc | Dev route acc | Miss p50 ms |", "|---|---|---|---|---|"]
        for name, b in results["backbones"].items():
            lines.append(f"| {name} | {b.get('holdout', 'n/a')} | {b.get('adversarial', 'n/a')} | {b.get('dev', 'n/a')} | {b.get('p50', 'n/a')} |")
        missing = [m for m in ("minilm+hash", "bge-small+hash") if m not in results["backbones"]]
        if missing:
            lines += ["", f"Not measured here: {', '.join(missing)} (FastEmbed models download from huggingface.co, which this build "
                      "environment could not reach). Run `pip install fastembed` and then `python scripts/bench_jde_backbones.py` on a machine that can."]
    lines += ["", "## Remaining errors (holdout)", "", "| Text | Expected | Predicted | Confidence |", "|---|---|---|---|"]
    for t, e, p, c in S["holdout"]["errors"]:
        lines.append(f"| {t} | {e} | {p} | {c} |")
    lines += ["", "## Wrong auto-executions (all splits)", ""]
    any_wrong = False
    for s in S:
        for t, e, p, c in S[s]["wrong_executions"]:
            any_wrong = True
            lines.append(f"* [{s}] \"{t}\" expected {e}, gated EXECUTE as {p} ({c})")
    if not any_wrong:
        lines.append("None.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="")
    ap.add_argument("--latency", type=int, default=10000)
    ap.add_argument("--out", default=str(ROOT / "reports" / "JDE_BENCHMARK.md"))
    args = ap.parse_args(argv)
    t = time.perf_counter()
    engine = LocalJDE.load(Path(args.model) if args.model else latest_model_dir(), catalog=default_catalog())
    load_ms = (time.perf_counter() - t) * 1000
    splits = {s: load_suite(s) for s in ("dev", "holdout", "adversarial")}
    results = {"model": engine.meta.decision_model_version, "encoder": engine.meta.encoder_version,
               "catalog": engine.meta.route_catalog_version, "generated": time.strftime("%Y-%m-%d %H:%M"),
               "machine": f"{os.cpu_count()} CPU threads", "load_ms": load_ms,
               "splits": {s: evaluate_split(engine, ex) for s, ex in splits.items()},
               "comparison": {s: compare_with_router(engine, ex) for s, ex in splits.items()}}
    texts = [e.text for ex in splits.values() for e in ex]
    results["latency"] = latency(engine, texts, args.latency)
    results["latency_n"] = args.latency
    bb_path = ROOT / "reports" / "jde_backbones.json"
    if bb_path.exists():
        results["backbones"] = json.loads(bb_path.read_text(encoding="utf-8"))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_report(results, out)
    out.with_suffix(".json").write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
    for s, r in results["splits"].items():
        print(f"{s:12s} route={r['route_acc']:.3f} top3={r['route_top3']:.3f} action={r['heads']['is_action']['acc']:.3f} "
              f"exec_rate={r['auto_execute_rate']:.2f} exec_prec={r['execute_precision']:.3f} wrong_conseq={len(r['wrong_consequential_executions'])}")
    for s, c in results["comparison"].items():
        print(f"{s:12s} current={c['current_route_acc']:.3f} combined={c['combined_route_acc']:.3f} L0={c['l0_decided']:.2f} stage_b={c['stage_b']}")
    print("latency", {k: round(v, 3) for k, v in results["latency"].items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
