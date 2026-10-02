"""Blind-11 runner: structured-oracle benchmark of the real router and the real command service.

    python -m tests.blind11.runner --run A --out /tmp/b11_A.json     # router / orchestration diagnostic
    python -m tests.blind11.runner --run B --out /tmp/b11_B.json     # command service end to end, real sandbox execution

Run A routes every case (and its context turns) through SmartRouter only.
Run B sends every turn through CommandService (router, policy, confirmation, executor, verifier):
- file tools run FOR REAL inside a throw-away sandbox home (tests/blind11/fixtures/sandbox.py); every path they touch is
  checked to be inside the sandbox first, and anything outside is blocked and recorded;
- browser tools that drive the managed Playwright browser run FOR REAL, headless, against the local test site;
- everything else (Windows desktop, phone, Google, WhatsApp transport, the local model) is not available in this Linux
  container: those tools are recorded (their arguments are scored) and their execution is DEPENDENCY_UNAVAILABLE.
"""
from __future__ import annotations

import argparse
import asyncio
import functools
import hashlib
import http.server
import json
import logging
import os
import re
import shutil
import socketserver
import sys
import tempfile
import threading
import time
import typing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases.jsonl"
SITE = HERE / "fixtures" / "site"

_SITE_SETUP = re.compile(r"\b(?:open|go\s+to|load|visit)\s+(?:the\s+)?(?P<page>[\w-]+\.html)\s+(?:on|in|from)\s+(?:the\s+)?test\s+site\b", re.I)
CHAT_INTENTS = {None, "", "chat", "general_chat", "ollama_chat", "quick_answer", "wake_greeting"}
REAL_FILE_TOOLS = {"create_folder", "copy_file", "move_file", "rename_file", "delete_file", "compress_files", "read_file_metadata",
                   "list_directory"}
# Draft tools: in production they return a draft plus a send step that the policy confirms (EXTERNAL_EFFECT). A recorder
# standing in for them returns no send step, so their confirmation is counted from the tool itself (harness correction
# after Blind-11, see docs/BLIND11_ORACLE_ERRATA.md).
DRAFT_THEN_CONFIRM = {"reply_whatsapp_message", "reply_whatsapp_all"}
CHAT_TOOLS = {"ollama_chat", "general_chat", "chat", "quick_answer"}
REAL_BROWSER_TOOLS = {"browser_navigate", "browser_click", "browser_type", "browser_snapshot", "browser_open_url"}


def load_cases(path: Path = CASES) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


# ------------------------------------------------------------------------------------------------ decision -> outcome
def norm(x) -> str:
    return " ".join(re.sub(r"[^\w.@:/+-]+", " ", str(x).lower()).replace("_", " ").split())


def outcome_of_decision(d) -> dict:
    """The semantic action a RouteDecision stands for."""
    from jarvis.core.router.models import ComplexityLevel, ReasonCode, RouteLane
    lane = d.lane
    calls = []
    if d.subcommands:
        calls = [(s.tool, dict(s.arguments or {})) for s in d.subcommands]
    if lane == RouteLane.REJECT:
        kind = "refuse"
    elif lane == RouteLane.CLARIFY and getattr(d, "state", "") == "NEEDS_CONFIRMATION" and d.intent:
        # the action and its target are decided; the router asks the owner's yes itself (NEEDS_CONFIRMATION is not
        # an ambiguity)
        kind, calls = "action", [(d.intent, {k: v for k, v in (d.slots or {}).items() if k != "qualifiers"})]
    elif lane == RouteLane.CLARIFY:
        kind = "clarify"
    elif lane == RouteLane.CONTROL:
        kind, calls = "control", [("CONTROL:" + str(d.intent), dict(d.slots or {}))]
    elif lane in (RouteLane.LANE_0, RouteLane.LANE_1):
        if d.intent == "compound" or d.complexity == ComplexityLevel.COMPOUND or d.subcommands:
            kind = "action"
            calls = calls or [("compound", dict(d.slots or {}))]
        elif d.intent in CHAT_INTENTS:
            kind = "chat"
        else:
            kind, calls = "action", [(d.intent, {k: v for k, v in (d.slots or {}).items() if k != "qualifiers"})]
    else:   # LANE_2
        kind = "chat" if (d.reason_code == ReasonCode.QUESTION_NOT_COMMAND or not d.needs_planner) else "plan"
    return {"kind": kind, "calls": calls, "lane": lane.value, "intent": d.intent, "state": getattr(d, "state", ""),
            "clarification": d.clarification or "", "compound": bool(d.subcommands)}


# ------------------------------------------------------------------------------------------------ scoring
_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def value_matches(actual, acceptable: list) -> bool:
    if actual is None:
        return False
    a = norm(actual)
    if not a:
        return False
    for v in acceptable:
        e = norm(v)
        if not e:
            continue
        if _NUM.fullmatch(e):
            if any(float(n) == float(e) for n in _NUM.findall(a)):
                return True
            continue
        if a == e or re.search(r"(?<![\w])" + re.escape(e) + r"(?![\w])", a) or (len(a) >= 3 and re.search(r"(?<![\w])" + re.escape(a) + r"(?![\w])", e)):
            return True
        if e.replace(" ", "") and e.replace(" ", "") in a.replace(" ", ""):
            return True
    return False


def all_arg_text(calls) -> str:
    return " | ".join(norm(v) for _, args in calls for v in (args or {}).values() if v not in (None, "", [], {}))


def score_case(case: dict, out: dict, confirmation_seen: bool | None = None) -> dict:
    """Every dimension of the oracle, from the semantic outcome (and, in run B, what the service did)."""
    exp_kind = case["outcome"]
    caps = case.get("capabilities") or []
    got_kind = out["kind"]
    tools = [t for t, _ in out["calls"]]
    acted = got_kind in ("action", "control")
    r = {"exp_kind": exp_kind, "got_kind": got_kind, "tools": tools, "acted": acted}
    # outcome
    outcome_ok = got_kind == exp_kind
    if exp_kind == "action" and got_kind == "control" and any(c.startswith("CONTROL:") for c in caps):
        outcome_ok = True
    if exp_kind == "control" and got_kind == "action" and any(t.replace("CONTROL:", "") in [c.replace("CONTROL:", "") for c in caps] for t in tools):
        outcome_ok = True
    r["outcome_ok"] = outcome_ok
    # capability
    cap_ok = None
    chosen = None
    if exp_kind in ("action", "control"):
        norm_caps = {c.replace("CONTROL:", "") for c in caps}
        for t in tools:
            if t in caps or t.replace("CONTROL:", "") in norm_caps:
                chosen = t
                break
        if chosen is None and "compound" in caps and out.get("compound"):
            chosen = "compound"
        cap_ok = chosen is not None
    r["cap_ok"], r["chosen"] = cap_ok, chosen
    # forbidden capabilities
    forb = set(case.get("forbidden_capabilities") or [])
    r["forbidden_cap_hit"] = acted and any(t in forb or t.replace("CONTROL:", "") in forb for t in tools)
    # slots
    slot_results = []
    if chosen and chosen != "compound":
        spec = (case.get("slots") or {}).get(chosen) or (case.get("slots") or {}).get(chosen.replace("CONTROL:", "")) or {}
        args = next((a for t, a in out["calls"] if t == chosen), {})
        for name, acceptable in spec.items():
            acceptable = acceptable if isinstance(acceptable, list) else [acceptable]
            actual = args.get(name)
            ok = value_matches(actual, acceptable)
            slot_results.append({"slot": name, "expected": acceptable, "actual": actual, "ok": ok,
                                 "status": "match" if ok else ("missing" if actual in (None, "", [], {}) else "wrong")})
    elif chosen == "compound":
        spec_all = case.get("slots") or {}
        for tool, spec in spec_all.items():
            for name, acceptable in spec.items():
                acceptable = acceptable if isinstance(acceptable, list) else [acceptable]
                actual = next((a.get(name) for t, a in out["calls"] if t == tool), None)
                ok = value_matches(actual, acceptable)
                slot_results.append({"slot": name, "expected": acceptable, "actual": actual, "ok": ok,
                                     "status": "match" if ok else ("missing" if actual in (None, "") else "wrong")})
    r["slots"] = slot_results
    r["slots_ok"] = all(s["ok"] for s in slot_results)
    # forbidden values (negated / excluded / corrected-away targets) anywhere in the action's arguments
    text = all_arg_text(out["calls"]) if acted else ""
    bad_vals = [v for v in (case.get("forbidden_values") or []) if norm(v) and re.search(r"(?<![\w])" + re.escape(norm(v)) + r"(?![\w])", text)]
    r["forbidden_values_hit"] = bad_vals
    # plan steps (compound) order
    steps = case.get("steps") or []
    r["plan_ok"] = None
    if steps and out.get("compound"):
        got = [t for t, _ in out["calls"]]
        it = iter(got)
        r["plan_ok"] = all(any(g == s for g in it) for s in steps)
    # confirmation (run B only)
    r["confirmation_ok"] = None
    if confirmation_seen is not None and acted and case.get("confirmation") in ("required", "none"):
        r["confirmation_ok"] = (case["confirmation"] == "required") == bool(confirmation_seen)
    exact = outcome_ok and not r["forbidden_cap_hit"] and not bad_vals
    if exp_kind in ("action", "control"):
        exact = exact and bool(cap_ok) and r["slots_ok"] and (r["plan_ok"] is not False)
    if r["confirmation_ok"] is False:
        exact = False
    r["exact_semantic"] = exact
    r["intent_ok"] = outcome_ok and (cap_ok is not False)
    return r


def auto_confirm_gate(case: dict, exec_spec: dict, last_turn: bool, pending: list, executed: list,
                      earlier_confirmations: int) -> tuple[bool, dict]:
    """May the harness say "yes" for the owner? Only to let an already-correct, sandboxed action really run so its
    postcondition can be checked. A confirmation never rescues a wrong reading: the pending action is scored against
    the oracle first, and any mismatch (tool, target, slots, scope, negation, forbidden action) is refused here."""
    pend = [(t, a) for t, a, _how in pending]
    pre = score_case(case, {"kind": "action", "calls": pend, "compound": len(pend) > 1}) if pend else None
    checks = {
        "1_oracle_expects_this_action": bool(case.get("should_act")) and case.get("outcome") == "action" and last_turn,
        "2_tool_target_slots_already_match": bool(pre and pre["exact_semantic"] and pre["cap_ok"] and pre["slots_ok"]
                                                  and not pre["forbidden_values_hit"]),
        "3_oracle_requires_confirmation": case.get("confirmation") == "required",
        "4_entirely_sandboxed": bool(pend) and (exec_spec or {}).get("kind") in ("file", "browser") and bool((exec_spec or {}).get("post"))
                                and all(t in (REAL_FILE_TOOLS | REAL_BROWSER_TOOLS) for t, _a in pend),
        "5_no_forbidden_capability": not (pre and pre["forbidden_cap_hit"])
                                    and not any(t in (case.get("forbidden_capabilities") or []) for t, _a, *_ in executed),
        "6_exactly_one_pending_confirmation": len(pend) == 1 and earlier_confirmations == 0,
    }
    ok = all(checks.values())
    return ok, {"approved": ok, "checks": checks, "refused": [k for k, v in checks.items() if not v]}


# ------------------------------------------------------------------------------------------------ run A
async def run_a(cases: list[dict]) -> list[dict]:
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter
    rows = []
    for c in cases:
        router = SmartRouter(llm_provider=DisabledProvider())
        for prior in c.get("context") or []:
            await router.route(prior)
        t0 = time.perf_counter()
        d = await router.route(c["utterance"])
        ms = (time.perf_counter() - t0) * 1000
        out = outcome_of_decision(d)
        rows.append({"id": c["id"], "phase": c["phase"], "run": "A", "out": out, "score": score_case(c, out), "routing_ms": ms})
    return rows


# ------------------------------------------------------------------------------------------------ run B
class _Site:
    def __init__(self) -> None:
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
        handler.log_message = lambda *a, **k: None
        self.httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def url(self, page: str) -> str:
        return f"http://127.0.0.1:{self.port}/{page}"


def _fake_output(out_model, args: dict) -> dict:
    out = {}
    for fname, field in out_model.model_fields.items():
        if not field.is_required() and fname not in args:
            continue
        if fname in args:
            out[fname] = args[fname]
            continue
        ann = field.annotation
        origin = typing.get_origin(ann)
        if origin in (typing.Union, getattr(__import__("types"), "UnionType", None)):
            ann = next((a for a in typing.get_args(ann) if a is not type(None)), str)
            origin = typing.get_origin(ann)
        if ann is bool:
            out[fname] = True
        elif ann in (int, float):
            out[fname] = 1
        elif origin is tuple or ann is tuple:
            out[fname] = ()
        elif origin is list or ann is list:
            out[fname] = []
        elif origin is dict or ann is dict:
            out[fname] = {}
        elif origin is typing.Literal:
            out[fname] = typing.get_args(ann)[0]
        else:
            out[fname] = str(args.get("name") or args.get("query") or fname)
    return out


def _inside(path: Path, home: Path) -> bool:
    try:
        path.resolve().relative_to(home.resolve())
        return True
    except Exception:
        return False


async def run_b(cases: list[dict], with_browser: bool = True) -> list[dict]:
    from jarvis.tests.ai_harness import AIHarness
    from jarvis.tools.system import file_tools
    rows = []
    site = _Site()
    base = Path(tempfile.mkdtemp(prefix="b11_"))
    browser_mgr = None
    if with_browser:
        try:
            from jarvis.core.computer.browser.manager import BrowserManager
            from jarvis.tools.system import computer_tools
            browser_mgr = BrowserManager(profile_dir=base / "browser_profile", headless=True)
            computer_tools._browser_manager = browser_mgr
        except Exception as e:   # pragma: no cover
            print("browser unavailable:", e)
            browser_mgr = None
    from jarvis.core.computer.browser.loop import run_browser

    for c in cases:
        sandbox_root = base / c["id"]
        from tests.blind11.fixtures.sandbox import build
        home = build(sandbox_root)
        os.environ["USERPROFILE"] = str(home)
        os.environ["HOME"] = str(home)
        os.environ["XDG_DATA_HOME"] = str(home / ".local" / "share")
        original_find = file_tools._find_existing_item

        def _sandboxed_find(name_or_path: str, _home=home):
            p = Path(str(name_or_path).strip().strip("'\""))
            cands = [p] if p.is_absolute() else [_home / p] + [d / p for d in (_home / "Desktop", _home / "Documents", _home / "Downloads",
                                                                               _home / "Pictures", _home / "Music", _home / "Videos")]
            for q in cands:
                if q.exists() and _inside(q, _home):
                    return q
            hits = [q for q in _home.rglob(p.name) if q.exists()] if p.name else []
            return hits[0] if hits else None
        file_tools._find_existing_item = _sandboxed_find

        calls, blocked = [], []
        h = AIHarness(sandbox_root, responder=lambda p: {"message": "OK."}, reachable=False)
        for tool in h.registry.list():
            name = tool.definition.name
            if name in REAL_FILE_TOOLS:
                real = tool.run

                def run_real(arguments, _n=name, _real=real, _home=home):
                    a = arguments if isinstance(arguments, dict) else arguments.model_dump()
                    calls.append((_n, a, "real"))
                    for k in ("path", "source", "destination", "directory"):
                        v = a.get(k)
                        if v and Path(str(v)).is_absolute() and not _inside(Path(str(v)), _home):
                            blocked.append((_n, k, v))
                            raise PermissionError(f"sandbox: {v} is outside the benchmark sandbox")
                    return _real(arguments)
                tool.run = run_real
            elif name in REAL_BROWSER_TOOLS and browser_mgr is not None:
                real = tool.run

                def run_real_b(arguments, _n=name, _real=real):
                    a = arguments if isinstance(arguments, dict) else arguments.model_dump()
                    calls.append((_n, a, "real"))
                    return _real(arguments)
                tool.run = run_real_b
            else:
                out_model = tool.definition.output_model

                def run_rec(arguments, _n=name, _om=out_model):
                    a = arguments if isinstance(arguments, dict) else arguments.model_dump()
                    calls.append((_n, a, "recorded"))
                    return _fake_output(_om, a)
                tool.run = run_rec
                if hasattr(tool, "run_async"):
                    async def run_rec_async(arguments, _n=name, _om=out_model):
                        a = arguments if isinstance(arguments, dict) else arguments.model_dump()
                        calls.append((_n, a, "recorded"))
                        return _fake_output(_om, a)
                    tool.run_async = run_rec_async
        decisions = []
        real_route = h.service.router.route

        async def _route_rec(request, _real=real_route):
            d = await _real(request)
            decisions.append(d)
            return d
        h.service.router.route = _route_rec
        # the real verifier is kept for real tools; recorded tools have nothing real to verify
        real_verify = h.service.verifier.verify

        async def _verify(tool_name, result, arguments, cancellation, _real=real_verify):
            from jarvis.tools.base import VerificationResult
            if calls and calls[-1][2] == "real":
                return await _real(tool_name, result, arguments, cancellation)
            return VerificationResult(verified=True, confidence=1.0, evidence={"recorded": True, "dependency": "unavailable"})
        h.service.verifier.verify = _verify

        exec_spec = c.get("exec") or {}
        if exec_spec.get("kind") == "browser" and browser_mgr is not None:
            try:
                async def _goto(url=site.url(exec_spec.get("start", "index.html"))):
                    page = await browser_mgr.get_active_page()
                    await page.goto(url, wait_until="domcontentloaded")
                run_browser(_goto(), timeout=20)
            except Exception as e:
                exec_spec = {**exec_spec, "setup_error": str(e)}

        turn_rows = []
        start_url = None
        if browser_mgr is not None and exec_spec.get("kind") == "browser":
            start_url = site.url(exec_spec.get("start", "index.html"))
        for i, text in enumerate((c.get("context") or []) + [c["utterance"]]):
            calls.clear()
            setup = _SITE_SETUP.search(text) if i < len(c.get("context") or []) else None
            if setup and browser_mgr is not None:
                # benchmark setup turn ("open shop.html on the test site"): the harness loads the page, JARVIS is not asked
                try:
                    async def _goto2(url=site.url(setup.group("page"))):
                        page = await browser_mgr.get_active_page()
                        await page.goto(url, wait_until="domcontentloaded")
                    run_browser(_goto2(), timeout=20)
                    start_url = site.url(setup.group("page"))
                except Exception as e:
                    exec_spec = {**exec_spec, "setup_error": str(e)}
                turn_rows.append({"text": text, "state": "SETUP", "message": "", "calls": [], "confirm": False, "total_ms": 0.0,
                                  "metrics": {}, "decision": None})
                continue
            t0 = time.perf_counter()
            try:
                res = await asyncio.wait_for(h.say(text), timeout=60)
                state, message, metrics = res.state, res.message, res.metrics
            except Exception as e:
                state, message, metrics = "ERROR", f"{type(e).__name__}: {e}", {}
            total_ms = (time.perf_counter() - t0) * 1000
            pending = getattr(h.service, "_pending_execution", None) or {}
            dec_now = decisions[-1] if decisions else None
            router_confirm = dec_now is not None and getattr(dec_now, "state", "") == "NEEDS_CONFIRMATION"
            confirm = state == "WAITING_CONFIRMATION" or router_confirm \
                or any(t in DRAFT_THEN_CONFIRM and how == "recorded" for t, _a, how in calls)
            pend_calls = []
            if router_confirm and dec_now.intent:
                pend_calls = [(dec_now.intent, dict(dec_now.slots or {}), "pending")]
            if confirm and pending.get("tool") is not None:
                pend_calls = [(pending["tool"].definition.name, dict(pending.get("arguments") or {}), "pending")]
            elif confirm and pending.get("graph") is not None:
                pend_calls = [(n.tool, dict(n.arguments or {}), "pending") for n in getattr(pending["graph"], "nodes", []) if getattr(n, "tool", None)]
            dec = decisions[-1] if decisions else None
            decisions.clear()
            last = i == len(c.get("context") or [])
            approve, gate = False, None
            if confirm:
                approve, gate = auto_confirm_gate(c, exec_spec, last, pend_calls, list(calls),
                                                  sum(1 for t in turn_rows if t.get("confirm")))
            approved = None
            if approve:
                # the owner says "yes" so the sandboxed action really runs and its postcondition can be checked;
                # the confirmation was still required and is scored from the turn above
                calls.clear()
                try:
                    res2 = await asyncio.wait_for(h.say("yes"), timeout=60)
                    approved = {"state": res2.state, "message": res2.message, "calls": list(calls)}
                    state, message = res2.state, res2.message
                except Exception as e:
                    approved = {"state": "ERROR", "message": f"{type(e).__name__}: {e}", "calls": list(calls)}
                decisions.clear()
            elif confirm:
                h.service._pending_execution = None
            turn_rows.append({"text": text, "state": state, "message": message,
                              "calls": (list(approved["calls"]) if approved else list(calls) + pend_calls),
                              "confirm": confirm, "approved_by_harness": approved is not None, "approved": approved,
                              "auto_confirm_gate": gate,
                              "total_ms": total_ms, "metrics": metrics,
                              "decision": outcome_of_decision(dec) if dec is not None else None})
        final = turn_rows[-1]
        # outcome from what the service actually did
        # an answer from the assistant (chat model, web answer) is a reply, not an action on the owner's things
        executed = [(t, a) for t, a, how in final["calls"] if t not in CHAT_TOOLS]
        dec_out = final["decision"] or {"kind": "chat", "calls": [], "compound": False}
        if executed:
            out = {"kind": "control" if dec_out["kind"] == "control" else "action", "calls": executed,
                   "compound": len(executed) > 1 or dec_out.get("compound", False)}
            if dec_out.get("compound") and dec_out["calls"]:
                out["calls"] = dec_out["calls"]
        elif dec_out["kind"] == "action" and final["state"] in ("FAILED", "ERROR", "UNCERTAIN"):
            out = {**dec_out, "kind": "action_failed"}
        else:
            out = dec_out
        score = score_case(c, out if out["kind"] != "action_failed" else {**out, "kind": "action"}, confirmation_seen=final["confirm"])
        if out["kind"] == "action_failed":
            score["execution_failed_before_tool"] = True
        # real execution and its postcondition
        ex = {"status": "not_applicable"}
        real_tools = [t for t, a, how in final["calls"] if how == "real"]
        if exec_spec.get("kind") == "file":
            if real_tools or not c.get("should_act"):
                # an action that ran, or a case that must change nothing: the sandbox state is checked either way
                ex = {"status": "checked" if real_tools else "checked_unchanged", "checks": []}
                for chk in exec_spec.get("post", []):
                    if "exists" in chk:
                        ok = (home / chk["exists"]).exists()
                    elif "missing" in chk:
                        ok = not (home / chk["missing"]).exists()
                    elif "file_contains" in chk:
                        p, txt = chk["file_contains"]
                        ok = (home / p).exists() and txt.lower() in (home / p).read_text(errors="ignore").lower()
                    else:
                        ok = None
                    ex["checks"].append({"check": chk, "ok": ok})
                ex["ok"] = all(x["ok"] for x in ex["checks"] if x["ok"] is not None)
            else:
                ex = {"status": "not_executed" if score["exact_semantic"] is False else "dependency_unavailable"}
        elif exec_spec.get("kind") == "browser":
            if browser_mgr is None or exec_spec.get("setup_error"):
                ex = {"status": "dependency_unavailable", "why": exec_spec.get("setup_error", "no browser")}
            else:
                ex = {"status": "checked", "checks": [], "real_tools": real_tools}

                async def _state():
                    page = await browser_mgr.get_active_page()
                    results = []
                    pages = list(browser_mgr._context.pages) if getattr(browser_mgr, "_context", None) else [page]
                    for chk in exec_spec.get("post", []):
                        if "download_name_contains" in chk:
                            want = str(chk["download_name_contains"]).lower()
                            found = [str(q) for q in base.rglob("*") if q.is_file() and want in q.name.lower()
                                     and "browser_profile" not in str(q)]
                            results.append({"check": chk, "value": found[:3], "ok": bool(found)})
                        elif "any_page_url_endswith" in chk:
                            urls = [pg.url for pg in pages]
                            results.append({"check": chk, "value": urls, "ok": any(u.endswith(chk["any_page_url_endswith"]) for u in urls)})
                        elif "page_count_at_least" in chk:
                            results.append({"check": chk, "value": len(pages), "ok": len(pages) >= int(chk["page_count_at_least"])})
                        elif "url_changed" in chk:
                            changed = page.url != start_url
                            results.append({"check": chk, "value": page.url, "ok": changed == bool(chk["url_changed"])})
                        elif "js" in chk:
                            try:
                                v = await page.evaluate(chk["js"])
                            except Exception as e:
                                v = f"error: {e}"
                            results.append({"check": chk, "value": v, "ok": v == chk.get("equals") if "equals" in chk else bool(v)})
                        elif "url_endswith" in chk:
                            results.append({"check": chk, "value": page.url, "ok": page.url.endswith(chk["url_endswith"])})
                        elif "url_contains" in chk:
                            results.append({"check": chk, "value": page.url, "ok": chk["url_contains"] in page.url})
                        else:
                            results.append({"check": chk, "ok": None})
                    return results
                try:
                    ex["checks"] = run_browser(_state(), timeout=20)
                    ex["ok"] = all(x["ok"] for x in ex["checks"] if x["ok"] is not None)
                    if not real_tools:
                        ex["status"] = "checked_no_real_tool"
                except Exception as e:
                    ex = {"status": "dependency_unavailable", "why": str(e)}
        # verification accuracy on real execution: what JARVIS said vs what is true
        verify = None
        if ex.get("status") == "checked" and real_tools:
            said_success = final["state"] in ("SUCCESS", "COMPLETED", "PARTIAL_SUCCESS")
            said_uncertain = final["state"] == "UNCERTAIN"
            verify = {"said": final["state"], "truth": ex["ok"],
                      "correct": (said_success and ex["ok"]) or (not said_success and not said_uncertain and not ex["ok"]) or said_uncertain and not ex["ok"],
                      "false_success": said_success and not ex["ok"], "false_failure": (not said_success and not said_uncertain) and ex["ok"]}
        claim = bool(re.search(r"\b(?:i\s+(?:sent|opened|deleted|created|moved|renamed|set|turned|closed|played|scheduled|saved|copied)|"
                               r"(?:is|are)\s+(?:open|closed|deleted|sent|done)|done\b)", final["message"] or "", re.I))
        unsupported = claim and not final["calls"] and final["state"] not in ("WAITING_CONFIRMATION",)
        file_tools._find_existing_item = original_find
        rows.append({"id": c["id"], "phase": c["phase"], "run": "B", "out": out, "score": score, "exec": ex, "verify": verify,
                     "state": final["state"], "message": (final["message"] or "")[:300], "blocked": blocked,
                     "turns": [{k: v for k, v in t.items() if k != "metrics"} for t in turn_rows], "total_ms": final["total_ms"],
                     "metrics": final["metrics"], "unsupported_claim": unsupported,
                     "dependency": sorted(({"model"} if (out.get("kind") == "plan") else set())
                                          | ({"desktop/phone/google"} if any(how == "recorded" for _, _, how in final["calls"]) else set()))})
        await h.close()
        shutil.rmtree(sandbox_root, ignore_errors=True)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", choices=("A", "B"), required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--cases", default=str(CASES))
    a = ap.parse_args()
    logging.disable(logging.WARNING)
    cases = load_cases(Path(a.cases))
    if a.limit:
        cases = cases[: a.limit]
    t0 = time.time()
    rows = asyncio.run(run_a(cases)) if a.run == "A" else asyncio.run(run_b(cases, with_browser=not a.no_browser))
    Path(a.out).write_text(json.dumps({"run": a.run, "cases_sha256": hashlib.sha256(Path(a.cases).read_bytes()).hexdigest(),
                                       "seconds": round(time.time() - t0, 1), "rows": rows}, indent=1, default=str))
    ok = sum(r["score"]["exact_semantic"] for r in rows)
    print(f"run {a.run}: {ok}/{len(rows)} exact (semantic) in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
