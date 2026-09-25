"""Audit Slot Failures Across All Generalization Datasets."""

import asyncio
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.capabilities.models import CapabilityDefinition
from jarvis.core.capabilities.registry import get_default_capability_registry
from jarvis.core.capabilities.retrieval import CapabilityRetriever
from jarvis.core.capabilities.slot_extractor import extract_slots
from jarvis.core.context.resolver import ReferenceResolver
from jarvis.core.memory.working import BoundedWorkingMemory
from jarvis.core.router.models import RouteDecision, RouteLane
from jarvis.core.router.ollama import DisabledProvider
from jarvis.core.router.router import SmartRouter
from jarvis.tools.system.app_resolver import AppResolver, LaunchTarget


def classify_slot_root_cause(slot_key: str, exp_val: Any, act_val: Any, utterance: str) -> str:
    ql = utterance.lower()
    if "actually" in ql or " no " in ql or "not " in ql or "instead" in ql:
        if "actually" in ql or " no " in ql or "—" in ql or "-" in ql:
            return "CORRECTED SLOT"
        return "NEGATED SLOT"
    if slot_key == "ordinal" or slot_key == "ordinals":
        return "ORDINAL"
    if slot_key == "folder":
        return "FOLDER"
    if slot_key == "percent":
        return "PERCENTAGE"
    if slot_key == "name":
        return "APP"
    if slot_key in ("query", "semantic_query"):
        return "SEARCH QUERY"
    if slot_key in ("extension", "file_type"):
        return "FILE TYPE"
    if slot_key in ("pronoun", "referent"):
        return "RESOURCE REF"
    if slot_key == "recipient":
        return "CONTACT"
    if "and" in ql or "then" in ql:
        return "MULTI-CLAUSE OWNERSHIP"
    return "CONSTRAINT"


async def main():
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

    failures: List[Dict[str, Any]] = []
    category_failures = defaultdict(list)
    tp = fp = fn = 0

    for p in sorted(Path('tests/generalization').glob('*.jsonl')):
        with open(p, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                exp_slots = rec.get('expected_slots', {})
                if not exp_slots:
                    continue
                inp = rec.get('input', '')
                cat = rec.get('category', '')

                # Context setup
                if cat in ('contextual', 'pronoun', 'ordinal'):
                    if not working_memory.get_recent_search_results():
                        working_memory.record_search_results([
                            {'path': 'C:\\Users\\ashok\\Downloads\\contract_1.pdf', 'name': 'contract_1.pdf', 'modified': '2026-09-20'},
                            {'path': 'C:\\Users\\ashok\\Downloads\\contract_2.pdf', 'name': 'contract_2.pdf', 'modified': '2026-09-22'},
                            {'path': 'C:\\Users\\ashok\\Downloads\\contract_3.pdf', 'name': 'contract_3.pdf', 'modified': '2026-09-21'},
                        ])
                        working_memory.record_file_opened('C:\\Users\\ashok\\Downloads\\contract_2.pdf')
                        working_memory.record_app_focused('notepad')

                dec = await router.route(CommandRequest(text=inp))
                act_slots = dict(dec.slots)

                # Fallback to extract_slots
                retrieved = retriever.retrieve(inp, top_k=5)
                if retrieved:
                    extracted, _ = extract_slots(retrieved[0][0], inp, working_memory, reference_resolver)
                    for k, v in extracted.items():
                        if k not in act_slots:
                            act_slots[k] = v

                item_failed = False
                missing = []
                extra = []
                wrong_val = []

                for k, v in exp_slots.items():
                    act_val = act_slots.get(k)
                    if act_val is None:
                        fn += 1
                        missing.append((k, v))
                        item_failed = True
                    elif str(act_val).lower() == str(v).lower():
                        tp += 1
                    else:
                        fp += 1
                        wrong_val.append((k, v, act_val))
                        item_failed = True

                for k, v in act_slots.items():
                    if k not in exp_slots:
                        extra.append((k, v))

                if item_failed:
                    # classify
                    root_cause = "UNKNOWN"
                    if missing:
                        root_cause = classify_slot_root_cause(missing[0][0], missing[0][1], None, inp)
                    elif wrong_val:
                        root_cause = classify_slot_root_cause(wrong_val[0][0], wrong_val[0][1], wrong_val[0][2], inp)

                    fail_item = {
                        'input': inp,
                        'category': cat,
                        'expected_slots': exp_slots,
                        'actual_slots': act_slots,
                        'missing': missing,
                        'wrong_val': wrong_val,
                        'extra': extra,
                        'root_cause': root_cause,
                    }
                    failures.append(fail_item)
                    category_failures[root_cause].append(fail_item)

    prec = tp / max(1, tp + fp)
    rec_val = tp / max(1, tp + fn)
    f1 = (2 * prec * rec_val) / max(1e-6, prec + rec_val)

    print(f"Slot Evaluation Summary:")
    print(f"  TP: {tp}, FP: {fp}, FN: {fn}")
    print(f"  Precision: {prec*100:.2f}%")
    print(f"  Recall:    {rec_val*100:.2f}%")
    print(f"  F1 Score:  {f1*100:.2f}%")
    print(f"  Total Failures: {len(failures)}")
    print(f"\nFailures by Root Cause:")
    for rc, items in sorted(category_failures.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"  {rc:25}: {len(items)}")

    # Generate reports/slot_failure_analysis.md
    out_path = Path("reports/slot_failure_analysis.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# JARVIS EDGE — Slot Extraction Failure Analysis Report\n\n")
        f.write(f"**Total Records Evaluated**: {tp + fn}\n")
        f.write(f"**Precision**: {prec*100:.2f}%\n")
        f.write(f"**Recall**: {rec_val*100:.2f}%\n")
        f.write(f"**F1 Score**: {f1*100:.2f}%\n")
        f.write(f"**Total Failure Cases**: {len(failures)}\n\n")
        f.write("## Root Cause Breakdown\n\n")
        for rc, items in sorted(category_failures.items(), key=lambda x: len(x[1]), reverse=True):
            f.write(f"- **{rc}**: {len(items)}\n")
        f.write("\n---\n\n## Detailed Failure Audit\n\n")

        for idx, fail in enumerate(failures, 1):
            f.write(f"### Failure {idx}: `{fail['input']}`\n\n")
            f.write(f"- **Category**: {fail['category']}\n")
            f.write(f"- **Root Cause**: {fail['root_cause']}\n")
            f.write(f"- **Expected Slots**: `{json.dumps(fail['expected_slots'])}`\n")
            f.write(f"- **Actual Slots**: `{json.dumps(fail['actual_slots'])}`\n")
            f.write(f"- **Missing**: `{fail['missing']}`\n")
            f.write(f"- **Wrong Value**: `{fail['wrong_val']}`\n")
            f.write(f"- **Extra**: `{fail['extra']}`\n\n")

    print(f"\nWritten detailed report to {out_path}")

if __name__ == "__main__":
    asyncio.run(main())
