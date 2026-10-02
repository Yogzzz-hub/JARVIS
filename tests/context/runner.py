"""Context suite runner: python -m tests.context.runner [--fails]

Every tool is replaced by a recorder (no real app, window or message is touched) and verification always passes, so
the suite measures understanding only: which tool each turn reaches and with which arguments.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import tempfile
import typing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.context.cases import CONVERSATIONS  # noqa: E402

CALLS: list[tuple[str, dict]] = []


def _fake_value(annotation, name: str, args: dict):
    if name in args:
        return args[name]
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, getattr(__import__("types"), "UnionType", None)):
        annotation = next((a for a in typing.get_args(annotation) if a is not type(None)), str)
        origin = typing.get_origin(annotation)
    if annotation is bool:
        return True
    if annotation in (int, float):
        return 1
    if origin is tuple or annotation is tuple:
        return ()
    if origin is list or annotation is list:
        return []
    if origin is dict or annotation is dict:
        return {}
    if origin is typing.Literal:
        return typing.get_args(annotation)[0]
    return str(args.get("name") or args.get("query") or name)


def _recorder(tool):
    out_model = tool.definition.output_model

    def run(arguments, _name=tool.definition.name):
        args = arguments if isinstance(arguments, dict) else arguments.model_dump()
        CALLS.append((_name, args))
        out = {}
        for fname, field in out_model.model_fields.items():
            if field.is_required() or fname in args:
                out[fname] = _fake_value(field.annotation, fname, args)
        return out
    return run


def _pending(service) -> list[tuple[str, dict]]:
    p = getattr(service, "_pending_execution", None) or {}
    if p.get("type") == "single" and p.get("tool") is not None:
        return [(p["tool"].definition.name, dict(p.get("arguments") or {}))]
    graph = p.get("graph")
    if graph is not None:
        nodes = getattr(graph, "nodes", None) or []
        return [(n.tool, dict(n.arguments or {})) for n in nodes if getattr(n, "tool", None)]
    return []


def _match(expect, calls, state) -> bool:
    if expect == "ANY":
        return True
    if expect == "CLARIFY":
        return not calls and state in ("WAITING_FOR_USER", "COMPLETED", "FAILED", "UNCERTAIN")
    tool, want = (expect, {}) if isinstance(expect, str) else expect
    names = tool.split("|")
    if "CLARIFY" in names and not calls:
        return True
    if "CHAT" in names and state in ("COMPLETED", "SUCCESS") and all(c[0] == "ollama_chat" for c in calls):
        return True   # a chat answer (the local model is stubbed, so the chat tool is recorded like any other)
    for name, args in calls:
        if name not in names:
            continue
        flat = {k: str(v).lower() for k, v in args.items()}
        if all(any(str(v).lower() in fv for fk, fv in flat.items() if fk == k or k not in flat) for k, v in want.items()):
            return True
    return False


async def run_all() -> list[dict]:
    from jarvis.tests.ai_harness import AIHarness
    from jarvis.tools.base import VerificationResult

    rows = []
    for conv in CONVERSATIONS:
        with tempfile.TemporaryDirectory() as d:
            h = AIHarness(Path(d), responder=lambda p: {"message": "OK."}, reachable=False)
            for tool in h.registry.list():
                tool.run = _recorder(tool)

            async def _ok(tool_name, result, arguments, cancellation):
                return VerificationResult(verified=True, confidence=1.0, evidence={"stub": True})
            h.service.verifier.verify = _ok
            for i, (text, expect) in enumerate(conv):
                CALLS.clear()
                res = await h.say(text)
                calls = list(CALLS) or _pending(h.service)
                ok = _match(expect, calls, res.state)
                rows.append({"conv": conv[0][0], "turn": i, "text": text, "expect": expect, "calls": calls,
                             "state": res.state, "message": res.message, "ok": ok, "scored": expect != "ANY"})
                if res.state == "WAITING_CONFIRMATION":
                    h.service._pending_execution = None
            await h.close()
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fails", action="store_true")
    a = ap.parse_args()
    logging.disable(logging.WARNING)
    rows = asyncio.run(run_all())
    scored = [r for r in rows if r["scored"]]
    follow = [r for r in scored if r["turn"] > 0]
    ok = sum(r["ok"] for r in scored)
    fok = sum(r["ok"] for r in follow)
    print(f"turns {ok}/{len(scored)} = {100 * ok / len(scored):.1f}%   follow-up turns {fok}/{len(follow)} = "
          f"{100 * fok / max(1, len(follow)):.1f}%")
    if a.fails:
        for r in rows:
            if r["scored"] and not r["ok"]:
                print(f"FAIL [{r['conv']}] {r['text']!r} -> {r['calls'][:2]} {r['state']} {r['message'][:90]!r} want {r['expect']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
