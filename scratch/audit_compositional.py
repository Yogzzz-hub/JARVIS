"""Audit compositional.jsonl failures and classify all failures by root cause."""

import asyncio
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.capabilities.canonical import to_canonical, to_canonical_list
from jarvis.core.capabilities.models import CapabilityDefinition
from jarvis.core.capabilities.registry import get_default_capability_registry
from jarvis.core.capabilities.retrieval import CapabilityRetriever
from jarvis.core.capabilities.slot_extractor import extract_slots
from jarvis.core.context.resolver import ReferenceResolver
from jarvis.core.memory.working import BoundedWorkingMemory
from jarvis.core.planner.adaptive_planner import AdaptivePlanner
from jarvis.core.planner.validator import GraphValidator
from jarvis.core.router.models import ComplexityLevel, RouteDecision, RouteLane
from jarvis.core.router.ollama import DisabledProvider
from jarvis.core.router.router import SmartRouter
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.system.app_resolver import AppResolver, LaunchTarget


async def audit_compositional():
    comp_file = Path("tests/generalization/compositional.jsonl")
    records = []
    with open(comp_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    working_memory = BoundedWorkingMemory()
    reference_resolver = ReferenceResolver(working_memory)
    app_resolver = AppResolver()
    app_resolver.cache = {
        'chrome': LaunchTarget('chrome.exe', ('chrome.exe',)),
        'notepad': LaunchTarget('notepad.exe', ('notepad.exe',)),
        'vlc': LaunchTarget('vlc.exe', ('vlc.exe',)),
        'calculator': LaunchTarget('calc.exe', ('calculatorapp.exe',)),
        'spotify': LaunchTarget('spotify.exe', ('spotify.exe',)),
        'vscode': LaunchTarget('code.exe', ('code.exe',)),
        'visual studio code': LaunchTarget('code.exe', ('code.exe',)),
        'explorer': LaunchTarget('explorer.exe', ('explorer.exe',)),
        'file explorer': LaunchTarget('explorer.exe', ('explorer.exe',)),
        'edge': LaunchTarget('msedge.exe', ('msedge.exe',)),
        'firefox': LaunchTarget('firefox.exe', ('firefox.exe',)),
    }
    registry = get_default_capability_registry()
    retriever = CapabilityRetriever(registry)
    router = SmartRouter(
        llm_provider=DisabledProvider(),
        app_resolver=app_resolver,
        working_memory=working_memory,
        reference_resolver=reference_resolver,
        capability_registry=registry,
        capability_retriever=retriever,
    )
    tool_registry = ToolRegistry()
    planner = AdaptivePlanner(registry=tool_registry)
    validator = GraphValidator(registry=tool_registry)

    passed_count = 0
    failures: List[Dict[str, Any]] = []
    category_counts = defaultdict(int)

    for rec in records:
        inp = rec.get("input", "")
        exp_caps = rec.get("expected_capabilities", [])
        canon_exp_caps = to_canonical_list(exp_caps)
        forbidden_caps = set(rec.get("forbidden_capabilities", []))

        # 1. Route
        decision = await router.route(CommandRequest(text=inp))

        # 2. Retrieve capabilities
        retrieved = retriever.retrieve(inp, top_k=10, min_score=0.5)
        retrieved_ids = [c.id for c, _ in retrieved]

        # 3. Check capability coverage
        missing_caps = [c for c in canon_exp_caps if c not in retrieved_ids]

        # Check DAG planning
        plan_failed = False
        fail_cause = "UNKNOWN"
        detail = ""

        # Did it route to Lane 2 or Compound?
        is_comp_route = (
            decision.lane == RouteLane.LANE_2
            or decision.complexity == ComplexityLevel.COMPOUND
            or len(decision.subcommands) >= 2
            or decision.intent in ("compound", "workflow")
        )

        if missing_caps:
            fail_cause = "CAPABILITY_NOT_RETRIEVED"
            detail = f"Missing capabilities in Top-10: {missing_caps}"
        elif not is_comp_route and len(canon_exp_caps) >= 2:
            fail_cause = "WRONG_CAPABILITY"
            detail = f"Lane {decision.lane.value} chosen instead of Lane 2 / Compound"
        else:
            # Let's attempt DAG generation if multi-capability
            # Check slot extraction
            exp_slots = rec.get("expected_slots", {})
            act_slots = dict(decision.slots)
            if retrieved:
                extracted, _ = extract_slots(retrieved[0][0], inp, working_memory, reference_resolver)
                for k, v in extracted.items():
                    if k not in act_slots:
                        act_slots[k] = v

            slot_mismatch = False
            for sk, sv in exp_slots.items():
                if sk not in act_slots:
                    slot_mismatch = True
                    break

            if slot_mismatch:
                fail_cause = "SLOT_FAILURE"
                detail = f"Slot mismatch: expected {exp_slots}, got {act_slots}"
            else:
                passed_count += 1
                continue

        failures.append({
            "id": rec.get("id"),
            "input": inp,
            "expected_capabilities": exp_caps,
            "canonical_expected": canon_exp_caps,
            "retrieved_ids": retrieved_ids[:5],
            "missing_caps": missing_caps,
            "actual_lane": decision.lane.value,
            "actual_intent": decision.intent,
            "root_cause": fail_cause,
            "detail": detail,
        })
        category_counts[fail_cause] += 1

    total = len(records)
    print(f"Compositional Audit: {passed_count}/{total} Passed ({(passed_count/total)*100:.2f}%)")
    print(f"Failures: {len(failures)}")
    print("\nRoot Cause Breakdown:")
    for cat, cnt in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {cat:25}: {cnt}")

    # Generate reports/compositional_failures_audit.md
    out_file = Path("reports/compositional_failures_audit.md")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("# JARVIS EDGE — 78 Compositional Failures Audit & Root-Cause Classification\n\n")
        f.write(f"**Total Records**: {total}\n")
        f.write(f"**Passed**: {passed_count}\n")
        f.write(f"**Failed**: {len(failures)}\n\n")
        f.write("## Root Cause Breakdown\n\n")
        for cat, cnt in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            f.write(f"- **{cat}**: {cnt}\n")
        f.write("\n---\n\n## Detailed Failure Breakdown\n\n")
        for idx, fail in enumerate(failures, 1):
            f.write(f"### Failure {idx}: `{fail['input']}`\n\n")
            f.write(f"- **Root Cause**: {fail['root_cause']}\n")
            f.write(f"- **Expected Capabilities**: `{fail['expected_capabilities']}`\n")
            f.write(f"- **Canonical Expected**: `{fail['canonical_expected']}`\n")
            f.write(f"- **Retrieved (Top 5)**: `{fail['retrieved_ids']}`\n")
            f.write(f"- **Missing in Top 10**: `{fail['missing_caps']}`\n")
            f.write(f"- **Actual Route**: Lane `{fail['actual_lane']}`, Intent `{fail['actual_intent']}`\n")
            f.write(f"- **Detail**: {fail['detail']}\n\n")

    print(f"\nWritten failure audit report to {out_file}")

if __name__ == "__main__":
    asyncio.run(audit_compositional())
