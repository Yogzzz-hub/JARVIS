import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from collections import defaultdict
from typing import Dict, List, Any

from jarvis.core.capabilities.registry import get_default_capability_registry
from jarvis.core.capabilities.retrieval import CapabilityRetriever
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.memory.working import BoundedWorkingMemory
from jarvis.core.context.resolver import ReferenceResolver
from jarvis.core.router.models import RouteLane
from jarvis.core.router.router import SmartRouter
from jarvis.core.router.ollama import DisabledProvider
from jarvis.tools.system.app_resolver import AppResolver, LaunchTarget
from scratch.audit_retrieval import CANONICAL_CAPABILITY_MAP, canonicalize

def infer_resource_type(query: str, expected_caps: List[str]) -> str:
    ql = query.lower()
    if any(k in ql for k in ("pdf", "file", "document", "zip", "mp3", "folder", "downloads", "documents", "txt")):
        return "FileResource"
    if any(k in ql for k in ("phone", "android", "device", "mobile")):
        return "DeviceResource"
    if any(k in ql for k in ("chrome", "notepad", "calculator", "app", "vlc", "spotify", "word", "excel", "browser")):
        return "ApplicationResource"
    if any(k in ql for k in ("volume", "brightness", "screenshot", "screen", "window", "battery", "cpu", "ram", "task")):
        return "SystemResource"
    if any(k in ql for k in ("whatsapp", "message", "contact", "chat")):
        return "MessageResource"
    if any(k in ql for k in ("news", "rss", "headline", "note", "memo", "calendar")):
        return "KnowledgeResource"
    return "GenericResource"

def infer_intent_family(expected_caps: List[str]) -> str:
    if not expected_caps:
        return "UNKNOWN"
    c = canonicalize(expected_caps[0])
    parts = c.split(".")
    if len(parts) >= 2:
        return parts[0].upper()
    return "GENERAL"

def infer_entity_resolution(query: str) -> str:
    ql = query.lower()
    entities = []
    for app in ("chrome", "notepad", "calculator", "vlc", "spotify", "vscode", "explorer", "paint", "edge"):
        if app in ql:
            entities.append(f"app:{app}")
    for folder in ("downloads", "documents", "desktop", "music", "pictures", "videos"):
        if folder in ql:
            entities.append(f"folder:{folder}")
    for ext in ("pdf", "txt", "docx", "mp3", "zip", "png", "jpg"):
        if ext in ql:
            entities.append(f"ext:{ext}")
    return ", ".join(entities) if entities else "None detected"

async def generate_audit():
    reg = get_default_capability_registry()
    retriever = CapabilityRetriever(reg)
    memory = BoundedWorkingMemory()
    resolver = ReferenceResolver(memory)
    app_res = AppResolver()
    app_res.cache = {
        "chrome": LaunchTarget("chrome.exe", ("chrome.exe",)),
        "notepad": LaunchTarget("notepad.exe", ("notepad.exe",)),
        "vlc": LaunchTarget("vlc.exe", ("vlc.exe",)),
        "calculator": LaunchTarget("calc.exe", ("calculatorapp.exe",)),
        "spotify": LaunchTarget("spotify.exe", ("spotify.exe",)),
        "vscode": LaunchTarget("code.exe", ("code.exe",)),
        "explorer": LaunchTarget("explorer.exe", ("explorer.exe",)),
    }
    router = SmartRouter(
        llm_provider=DisabledProvider(),
        app_resolver=app_res,
        working_memory=memory,
        reference_resolver=resolver,
        capability_registry=reg,
        capability_retriever=retriever,
    )

    datasets = sorted(Path("tests/generalization").glob("*.jsonl"))
    
    total = 0
    raw_r1 = 0
    raw_r10 = 0
    canon_r1 = 0
    canon_r10 = 0
    bypassed_total = 0
    failures = []
    root_cause_counts = defaultdict(int)

    for dpath in datasets:
        with open(dpath, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                expected_caps = rec.get("expected_capabilities", [])
                forbidden = set(rec.get("forbidden_capabilities", []))
                if not expected_caps or "*" in forbidden:
                    continue

                total += 1
                inp = rec.get("input", "")

                decision = await router.route(CommandRequest(text=inp))
                bypassed = decision.lane in (RouteLane.LANE_0, RouteLane.CONTROL, RouteLane.REJECT)
                if bypassed:
                    bypassed_total += 1

                retrieved = retriever.retrieve(inp, top_k=10, min_score=0.1)
                ret_ids = [c.id for c, _ in retrieved]
                scores = [s for _, s in retrieved]

                primary_raw = expected_caps[0]
                primary_canon = canonicalize(primary_raw)
                canon_ret_ids = [canonicalize(rid) for rid in ret_ids]

                if ret_ids and primary_raw == ret_ids[0]:
                    raw_r1 += 1
                if primary_raw in ret_ids[:10]:
                    raw_r10 += 1

                is_canon_hit = bool(canon_ret_ids and primary_canon == canon_ret_ids[0])
                if is_canon_hit:
                    canon_r1 += 1
                if primary_canon in canon_ret_ids[:10]:
                    canon_r10 += 1

                rank = -1
                if primary_canon in canon_ret_ids:
                    rank = canon_ret_ids.index(primary_canon) + 1

                # Classify root cause
                cause = "SUCCESS"
                if not is_canon_hit:
                    if primary_raw != primary_canon and primary_raw not in ret_ids and primary_canon in canon_ret_ids:
                        cause = "ALIAS_LABEL_MISMATCH"
                    elif bypassed:
                        cause = "DETERMINISTIC_LANE0_BYPASS"
                    elif len(expected_caps) > 1 and primary_canon in canon_ret_ids:
                        cause = "MULTI_CAPABILITY_RANK_ORDER"
                    elif not retrieved:
                        cause = "RETRIEVER_ZERO_RESULTS"
                    elif primary_canon not in canon_ret_ids:
                        cause = "LEXICAL_SEMANTIC_GAP"
                    else:
                        cause = "RANK_SUPPRESSED_BY_OTHER_CANDIDATE"

                    root_cause_counts[cause] += 1

                    top10_lines = []
                    for i in range(min(10, len(retrieved))):
                        top10_lines.append(f"{i+1} {retrieved[i][0].id} {scores[i]:.2f}")
                    while len(top10_lines) < 10:
                        top10_lines.append(f"{len(top10_lines)+1} [NONE] 0.00")

                    failures.append({
                        "id": rec.get("id"),
                        "category": rec.get("category"),
                        "input": inp,
                        "expected_capabilities": expected_caps,
                        "actual_route": f"{decision.intent} ({decision.lane.value})",
                        "bypassed": "YES" if bypassed else "NO",
                        "top10": top10_lines,
                        "expected_rank": rank if rank != -1 else "NOT_IN_TOP_10",
                        "entity_resolution": infer_entity_resolution(inp),
                        "resource_type": infer_resource_type(inp, expected_caps),
                        "active_context": f"Session memory initialized; category={rec.get('category')}",
                        "intent_family": infer_intent_family(expected_caps),
                        "root_cause": cause,
                    })

    # Write Markdown Report
    out_path = Path("reports/capability_retrieval_audit.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Capability Retrieval Audit & Root Cause Analysis\n\n")
        f.write("## 1. Executive Summary\n\n")
        f.write(f"- **Total Evaluated Benchmark Items with Expected Capabilities**: `{total}`\n")
        f.write(f"- **Total Fast-Path / Lane 0 Bypasses**: `{bypassed_total}` ({bypassed_total/total*100:.1f}%)\n")
        f.write(f"- **Original Raw Metric Recall@1**: `{raw_r1 / total * 100:.2f}%`\n")
        f.write(f"- **Original Raw Metric Recall@10**: `{raw_r10 / total * 100:.2f}%`\n")
        f.write(f"- **Canonical Primary Capability Recall@1**: `{canon_r1 / total * 100:.2f}%`\n")
        f.write(f"- **Canonical Primary Capability Recall@10**: `{canon_r10 / total * 100:.2f}%`\n\n")
        
        f.write("### Root Causes of Metric Underreporting & Retrieval Gaps\n\n")
        f.write("| Root Cause Category | Count | Percentage | Explanation |\n")
        f.write("|---|---|---|---|\n")
        for k, v in sorted(root_cause_counts.items(), key=lambda x: x[1], reverse=True):
            f.write(f"| **{k}** | {v} | {v/total*100:.1f}% | ")
            if k == "DETERMINISTIC_LANE0_BYPASS":
                f.write("Command routes deterministically via Lane 0 in <1ms; capability retriever is bypassed by design, yet test penalizes it as retrieval failure.\n")
            elif k == "LEXICAL_SEMANTIC_GAP":
                f.write("Paraphrased phrasing or indirect verbs have no keyword overlap with BM25 indexed examples, requiring hybrid semantic expansion.\n")
            elif k == "RETRIEVER_ZERO_RESULTS":
                f.write("BM25 score fell below min_score threshold because query words were not in capability keywords/examples.\n")
            elif k == "ALIAS_LABEL_MISMATCH":
                f.write("Dataset uses abstract names ('file.search', 'system.volume_set') while registry uses canonical IDs ('file.find', 'windows.volume_set').\n")
            elif k == "MULTI_CAPABILITY_RANK_ORDER":
                f.write("Multi-capability compositional query retrieved valid secondary capability at rank 1 instead of primary capability.\n")
            elif k == "RANK_SUPPRESSED_BY_OTHER_CANDIDATE":
                f.write("Another related capability scored slightly higher due to common stopword/verb overlap.\n")
            else:
                f.write("Other causes.\n")

        f.write("\n---\n\n## 2. Failed Retrieval Examples Audit (Detailed Log)\n\n")
        for item in failures:
            f.write(f"### Test ID: `{item['id']}` ({item['category']})\n\n")
            f.write(f"**USER QUERY**:\n`{item['input']}`\n\n")
            f.write(f"**EXPECTED CAPABILITY/CAPABILITIES**:\n`{item['expected_capabilities']}`\n\n")
            f.write(f"**ACTUAL ROUTE**:\n`{item['actual_route']}`\n\n")
            f.write(f"**DID IT BYPASS RETRIEVER?**:\n`{item['bypassed']}`\n\n")
            f.write(f"**TOP 10 RETRIEVED**:\n```text\n")
            for t10 in item['top10']:
                f.write(f"{t10}\n")
            f.write("```\n\n")
            f.write(f"**EXPECTED CAPABILITY RANK**:\n`{item['expected_rank']}`\n\n")
            f.write(f"**ENTITY RESOLUTION**:\n`{item['entity_resolution']}`\n\n")
            f.write(f"**RESOURCE TYPE**:\n`{item['resource_type']}`\n\n")
            f.write(f"**ACTIVE CONTEXT**:\n`{item['active_context']}`\n\n")
            f.write(f"**INTENT FAMILY**:\n`{item['intent_family']}`\n\n")
            f.write(f"**ROOT CAUSE**:\n`{item['root_cause']}`\n\n")
            f.write("---\n\n")

    print(f"Generated {out_path} with {len(failures)} failure audit records successfully.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(generate_audit())
