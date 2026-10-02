"""Structural oracle validation for the locked Blind-11 set (run once, before the first execution).

It never judges whether an expectation is *right* - only whether it is well formed against the real system:
every capability and slot name exists in the live tool registry, outcome / confirmation / criticality values are known,
postconditions use the checks the runner implements, and the per-phase counts are exactly 50.

    python -m tests.blind11.oracle_check [--cases tests/blind11/cases.jsonl]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.blind11.runner import CASES, load_cases  # noqa: E402

OUTCOMES = {"action", "clarify", "chat", "refuse", "control", "plan"}
CONFIRMATION = {"required", "none", "n/a", None}
CRITICALITY = {"C0", "C1", "C2", "C3", "C4"}
FILE_POST = {"exists", "missing", "file_contains"}
BROWSER_POST = {"js", "url_endswith", "url_contains", "download_name_contains", "any_page_url_endswith", "page_count_at_least",
                "url_changed"}


def registry_schema() -> dict[str, set[str]]:
    from jarvis.tests.ai_harness import HARDWARE
    from jarvis.tools.registry import ToolRegistry
    from jarvis.tools.system.app_resolver import AppResolver
    from jarvis.tools.system.native import create_tools
    reg = ToolRegistry()
    reg.discover(create_tools(AppResolver({}), HARDWARE))
    reg.finalize()
    out = {}
    for t in reg.list():
        model = getattr(t.definition, "input_model", None)
        out[t.definition.name] = set(getattr(model, "model_fields", {}) or {})
    return out


def runtime_capabilities() -> dict[str, set[str]]:
    """Router-level capabilities that are not registry tools (control lane, runtime handlers, volume keys, compound),
    from the catalogue the generator was given - each kept only if the router really emits that name."""
    import re
    catalogue = json.loads((Path(__file__).with_name("generation") / "capabilities.json").read_text())
    source = "\n".join(p.read_text(errors="ignore") for d in ("jarvis/core/router", "jarvis/core/commands")
                       for p in (ROOT / d).glob("*.py"))
    out = {}
    for entry in catalogue.get("runtime_and_control", []):
        name = entry["tool"]
        bare = name.split(":", 1)[-1]
        if name == "compound" or re.search(rf"[\"']{re.escape(bare)}[\"']", source):
            out[name] = set((entry.get("args") or {}).keys())
    return out


def check(cases: list[dict], schema: dict[str, set[str]]) -> list[str]:
    errors: list[str] = []
    ids = Counter(c.get("id") for c in cases)
    errors += [f"duplicate id {i}" for i, n in ids.items() if n > 1]
    for c in cases:
        cid = c.get("id")
        for key in ("id", "phase", "utterance", "outcome", "should_act"):
            if key not in c:
                errors.append(f"{cid}: missing {key}")
        if c.get("outcome") not in OUTCOMES:
            errors.append(f"{cid}: unknown outcome {c.get('outcome')!r}")
        if c.get("confirmation") not in CONFIRMATION:
            errors.append(f"{cid}: unknown confirmation {c.get('confirmation')!r}")
        if c.get("criticality") not in CRITICALITY:
            errors.append(f"{cid}: unknown criticality {c.get('criticality')!r}")
        if c.get("outcome") in ("action", "control") and not c.get("capabilities") and c.get("outcome") == "action":
            errors.append(f"{cid}: action without capabilities")
        if bool(c.get("should_act")) != (c.get("outcome") in ("action", "control", "plan")):
            errors.append(f"{cid}: should_act {c.get('should_act')} disagrees with outcome {c.get('outcome')}")
        for cap in (c.get("capabilities") or []) + (c.get("forbidden_capabilities") or []) + \
                [s for step in (c.get("steps") or []) for s in (step if isinstance(step, list) else [step])]:
            if cap not in schema:
                errors.append(f"{cid}: unknown capability {cap}")
        for tool, args in (c.get("slots") or {}).items():
            if tool not in schema:
                errors.append(f"{cid}: slots for unknown tool {tool}")
                continue
            for arg in args:
                if arg not in schema[tool]:
                    errors.append(f"{cid}: {tool} has no argument {arg!r} (has {sorted(schema[tool])})")
        ex = c.get("exec") or {}
        if ex:
            kind = ex.get("kind")
            allowed = FILE_POST if kind == "file" else BROWSER_POST if kind == "browser" else None
            if allowed is None:
                errors.append(f"{cid}: unknown exec kind {kind!r}")
            else:
                for post in ex.get("post") or []:
                    keys = set(post) - {"equals"}
                    if not keys or not keys <= allowed:
                        errors.append(f"{cid}: unknown postcondition {post}")
    phases = Counter(c.get("phase") for c in cases)
    errors += [f"phase {p} has {n} cases, not 50" for p, n in phases.items() if n != 50]
    if len(phases) != 22:
        errors.append(f"{len(phases)} phases, not 22")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=str(CASES))
    a = ap.parse_args()
    cases = load_cases(Path(a.cases))
    schema = {**registry_schema(), **runtime_capabilities()}
    errors = check(cases, schema)
    for e in errors:
        print("ERROR", e)
    print(f"{len(cases)} cases, {len(errors)} structural errors")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
