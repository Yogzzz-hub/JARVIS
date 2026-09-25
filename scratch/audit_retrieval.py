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
from tests.generalization.benchmark_runner import INTENT_ALIASES

# Canonical mapping extending INTENT_ALIASES
CANONICAL_CAPABILITY_MAP = dict(INTENT_ALIASES)
CANONICAL_CAPABILITY_MAP.update({
    "file.search": "file.find",
    "file.list": "file.list_directory",
    "system.volume_set": "windows.volume_set",
    "system.volume_get": "windows.volume_get",
    "system.volume_mute": "windows.volume_mute",
    "system.volume_unmute": "windows.volume_unmute",
    "system.screenshot": "windows.screenshot",
    "system.time": "system.time",
    "system.diagnostics": "system.diagnostics",
    "system.info": "system.info",
    "system.battery": "system.diagnostics",
    "system.brightness": "windows.brightness_set",
    "system.processes": "windows.top_memory_processes",
    "system.cpu": "system.diagnostics",
    "system.clipboard": "terminal.powershell",
    "system.notify": "system.dashboard",
    "system.set_wallpaper": "windows.desktop_ui_click",
    "phone.transfer": "phone.send_file",
    "phone.get_photo": "phone.mirror_open",
    "news.search": "rag.search_news",
    "rss.latest": "rag.rss_latest",
    "knowledge.summarize": "rag.document_qa",
    "knowledge.extract": "rag.document_qa",
    "knowledge.qa": "rag.document_qa",
    "knowledge.note": "rag.capture_note",
    "knowledge.format": "rag.document_qa",
    "knowledge.compare": "rag.document_qa",
    "knowledge.recommend": "rag.document_qa",
    "app.location": "app.get_location",
    "app.list": "app.list_installed",
    "app.refresh": "app.refresh_catalog",
    "app.paste": "terminal.powershell",
    "browser.search": "rag.search_web",
    "browser.open_url": "browser.open_url",
    "browser.maps": "browser.open_url",
    "whatsapp.read": "whatsapp.read",
    "whatsapp.draft": "whatsapp.action",
    "whatsapp.send": "whatsapp.send",
    "email.draft": "google.gmail_send",
    "email.search": "rag.document_qa",
    "calendar.read": "google.calendar_list",
    "drive.search": "google.drive_search",
    "workflow.git_status": "workflow.git_status",
    "workflow.trim_audio": "workflow.trim_clip",
    "workflow.lint": "workflow.diagnose_error",
    "workflow.run_tests": "workflow.run_tests",
    "workflow.coverage": "workflow.run_tests",
    "file.save": "file.create_folder",
    "file.checksum": "file.read_metadata",
    "file.hash": "file.read_metadata",
    "file.group": "file.organize_downloads",
    "file.compress": "file.batch_rename",
    "file.extract": "file.batch_rename",
    "file.convert": "workflow.extract_audio",
    "file.export": "file.copy",
    "image.optimize": "windows.desktop_ui_click",
    "screen.record": "windows.screenshot",
    "media.convert": "workflow.extract_audio",
    "user.confirm": "system.dashboard",
    "rag.memos_create": "rag.memos_create",
    "rag.search_notes": "rag.search_notes",
    "rag.search_web": "rag.search_web",
})

def canonicalize(cap_id: str) -> str:
    if not cap_id:
        return ""
    c = cap_id.strip()
    return CANONICAL_CAPABILITY_MAP.get(c, c)

def run_audit():
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

    total_with_expected = 0
    raw_r1 = 0
    raw_r3 = 0
    raw_r5 = 0
    raw_r10 = 0

    canon_r1 = 0
    canon_r3 = 0
    canon_r5 = 0
    canon_r10 = 0

    coverage_r3 = 0
    coverage_r5 = 0
    coverage_r10 = 0

    bypassed_count = 0
    root_causes = defaultdict(int)
    audit_records = []

    import asyncio
    async def process():
        nonlocal total_with_expected, raw_r1, raw_r3, raw_r5, raw_r10
        nonlocal canon_r1, canon_r3, canon_r5, canon_r10
        nonlocal coverage_r3, coverage_r5, coverage_r10, bypassed_count

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

                    total_with_expected += 1
                    inp = rec.get("input", "")

                    # 1. Check router route
                    decision = await router.route(CommandRequest(text=inp))
                    bypassed = decision.lane in (RouteLane.LANE_0, RouteLane.CONTROL, RouteLane.REJECT)
                    if bypassed:
                        bypassed_count += 1

                    # 2. Retrieve Top-10
                    retrieved = retriever.retrieve(inp, top_k=10, min_score=0.1)
                    ret_ids = [c.id for c, _ in retrieved]
                    scores = [s for _, s in retrieved]

                    primary_raw = expected_caps[0]
                    primary_canon = canonicalize(primary_raw)
                    canon_ret_ids = [canonicalize(rid) for rid in ret_ids]

                    # Raw Metric
                    if ret_ids and primary_raw == ret_ids[0]:
                        raw_r1 += 1
                    if primary_raw in ret_ids[:3]:
                        raw_r3 += 1
                    if primary_raw in ret_ids[:5]:
                        raw_r5 += 1
                    if primary_raw in ret_ids[:10]:
                        raw_r10 += 1

                    # Canonical Primary Metric
                    is_c_r1 = bool(canon_ret_ids and primary_canon == canon_ret_ids[0])
                    is_c_r3 = bool(primary_canon in canon_ret_ids[:3])
                    is_c_r5 = bool(primary_canon in canon_ret_ids[:5])
                    is_c_r10 = bool(primary_canon in canon_ret_ids[:10])

                    if is_c_r1: canon_r1 += 1
                    if is_c_r3: canon_r3 += 1
                    if is_c_r5: canon_r5 += 1
                    if is_c_r10: canon_r10 += 1

                    # Coverage Metric (for compositional / multi-cap requests)
                    expected_canon_set = set(canonicalize(c) for c in expected_caps)
                    if expected_canon_set.issubset(set(canon_ret_ids[:3])):
                        coverage_r3 += 1
                    if expected_canon_set.issubset(set(canon_ret_ids[:5])):
                        coverage_r5 += 1
                    if expected_canon_set.issubset(set(canon_ret_ids[:10])):
                        coverage_r10 += 1

                    # Determine rank of primary
                    rank = -1
                    if primary_canon in canon_ret_ids:
                        rank = canon_ret_ids.index(primary_canon) + 1

                    # Root cause classification
                    cause = "SUCCESS"
                    if not is_c_r1:
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

                    root_causes[cause] += 1

                    # Store sample for audit report if not perfect
                    if not is_c_r1 or len(audit_records) < 50:
                        top10_formatted = []
                        for i in range(min(10, len(retrieved))):
                            top10_formatted.append(f"{i+1}. {retrieved[i][0].id} (score: {scores[i]:.2f})")

                        audit_records.append({
                            "id": rec.get("id"),
                            "category": rec.get("category"),
                            "input": inp,
                            "expected_capabilities": expected_caps,
                            "canonical_expected": [canonicalize(c) for c in expected_caps],
                            "actual_route": f"{decision.intent} ({decision.lane.value})",
                            "did_bypass_retriever": "YES" if bypassed else "NO",
                            "top_10": top10_formatted,
                            "expected_rank": rank if rank != -1 else "NOT_IN_TOP_10",
                            "root_cause": cause,
                        })

    asyncio.run(process())

    print("============================================================")
    print("CAPABILITY RETRIEVAL AUDIT SUMMARY")
    print("============================================================")
    print(f"Total Evaluated Items with Expected Caps: {total_with_expected}")
    print(f"Bypassed by Lane 0 / Fast-Path:           {bypassed_count} ({bypassed_count/total_with_expected*100:.1f}%)")
    print("------------------------------------------------------------")
    print("OLD RAW METRIC (WITHOUT CANONICAL RESOLUTION):")
    print(f"  Recall@1:  {raw_r1 / total_with_expected * 100:.2f}%")
    print(f"  Recall@3:  {raw_r3 / total_with_expected * 100:.2f}%")
    print(f"  Recall@5:  {raw_r5 / total_with_expected * 100:.2f}%")
    print(f"  Recall@10: {raw_r10 / total_with_expected * 100:.2f}%")
    print("------------------------------------------------------------")
    print("CANONICAL PRIMARY CAPABILITY RECALL:")
    print(f"  Recall@1:  {canon_r1 / total_with_expected * 100:.2f}%")
    print(f"  Recall@3:  {canon_r3 / total_with_expected * 100:.2f}%")
    print(f"  Recall@5:  {canon_r5 / total_with_expected * 100:.2f}%")
    print(f"  Recall@10: {canon_r10 / total_with_expected * 100:.2f}%")
    print("------------------------------------------------------------")
    print("REQUIRED CAPABILITY COVERAGE (ALL REQUIRED CAPS IN TOP-K):")
    print(f"  Coverage@3:  {coverage_r3 / total_with_expected * 100:.2f}%")
    print(f"  Coverage@5:  {coverage_r5 / total_with_expected * 100:.2f}%")
    print(f"  Coverage@10: {coverage_r10 / total_with_expected * 100:.2f}%")
    print("------------------------------------------------------------")
    print("ROOT CAUSES BREAKDOWN:")
    for k, v in sorted(root_causes.items(), key=lambda x: x[1], reverse=True):
        print(f"  {k:35}: {v} ({v/total_with_expected*100:.1f}%)")
    print("============================================================")

    return audit_records, {
        "total": total_with_expected,
        "bypassed": bypassed_count,
        "raw": {"r1": raw_r1, "r3": raw_r3, "r5": raw_r5, "r10": raw_r10},
        "canonical": {"r1": canon_r1, "r3": canon_r3, "r5": canon_r5, "r10": canon_r10},
        "coverage": {"c3": coverage_r3, "c5": coverage_r5, "c10": coverage_r10},
        "root_causes": dict(root_causes),
    }

if __name__ == "__main__":
    run_audit()
