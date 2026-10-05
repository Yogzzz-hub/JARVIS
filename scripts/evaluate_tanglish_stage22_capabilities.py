"""Offline capability ranking on independently specified confusion cases."""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

from jarvis.core.capabilities.registry import CapabilityRegistry
from jarvis.core.capabilities.retrieval import CapabilityRetriever

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/tanglish/generated/stage22"

# Gold IDs were specified from task meaning, before ranking. No tool is called.
CASES = [
    ("Find the Atlas PDF in my files", "FIND", "file", "pdf", {"query":"Atlas"}, "file.find"),
    ("Search the web for Atlas project", "SEARCH", "web", "web", {"query":"Atlas project"}, "rag.search_web"),
    ("Find duplicate PDFs in Downloads", "FIND", "file", "pdf", {"folder":"Downloads"}, "file.find_duplicates"),
    ("Send the PDF to Naveen on WhatsApp", "SEND", "whatsapp", "pdf", {"recipient":"Naveen","file":"report.pdf"}, "whatsapp.send"),
    ("Email the PDF to Naveen", "SEND", "google", "pdf", {"recipient":"Naveen","file":"report.pdf"}, "google.gmail_send"),
    ("Mute PC audio", "MUTE", "windows", "audio", {}, "windows.volume_mute"),
    ("Delete report.pdf", "DELETE", "file", "file", {"file":"report.pdf"}, "file.delete"),
    ("Delete the Atlas shortcut", "DELETE", "automation", "shortcut", {"name":"Atlas"}, "automation.shortcut_delete"),
    ("Open Chrome", "OPEN", "app", "app", {"application":"Chrome"}, "app.open"),
    ("Open https://example.com", "OPEN", "browser", "url", {"url":"https://example.com"}, "browser.open_url"),
    ("Open report.pdf", "OPEN", "file", "file", {"file":"report.pdf"}, "file.open"),
    ("Show git status", "STATUS", "workflow", "git", {}, "workflow.git_status"),
    ("Show system status", "STATUS", "system", "system", {}, "system.info"),
    ("Show phone status", "STATUS", "phone", "phone", {}, "phone.status"),
    ("Read latest WhatsApp messages", "READ", "whatsapp", "message", {}, "whatsapp.read"),
    ("Read unread Gmail messages", "READ", "google", "email", {}, "google.read_emails"),
    ("Search my saved notes for Atlas", "SEARCH", "rag", "note", {"query":"Atlas"}, "rag.search_notes"),
    ("Create a calendar event tomorrow", "CREATE", "google", "calendar", {"date":"tomorrow"}, "google.calendar_create"),
]


def rank(case, registry, retriever):
    query, action, domain, resource, slots, gold = case
    baseline = retriever.retrieve(query, top_k=150, min_score=0)
    lexical = {cap.id: score for cap, score in baseline}
    caps = registry.list_all()
    candidates = []
    for cap in caps:
        parts = set(cap.id.replace(".", "_").split("_"))
        description = (cap.description + " " + " ".join(cap.keywords)).casefold()
        category = cap.category.value.casefold()
        family = cap.get_family().casefold()
        domain_match = domain in {category, family, cap.id.split(".")[0]}
        action_match = action.casefold() in parts or action.casefold() in description.split()
        resource_match = resource.casefold() in description or resource.casefold() in parts
        # The frame narrows candidates; the registry description and schema provide independent evidence.
        score = math.log1p(max(0.0, lexical.get(cap.id, 0.0)))
        score += 4.0 if domain_match else -2.0
        score += 2.5 if action_match else 0.0
        score += 1.0 if resource_match else 0.0
        available = set(k.casefold() for k in slots)
        required = set(k.casefold() for k in cap.required_slots)
        aliases = {"application":"name", "recipient":"to", "file":"path", "url":"url", "query":"query"}
        available |= {aliases[k] for k in available if k in aliases}
        if required:
            score += .5 * len(required & available)
            score -= 1.0 * len(required - available)
        # Availability is unknown offline; do not silently assume live integrations work.
        candidates.append((cap.id, score))
    candidates.sort(key=lambda item: (-item[1], item[0]))
    return [cap_id for cap_id, _ in candidates], [cap.id for cap, _ in baseline]


def metrics(ranks, gold):
    positions = [ids.index(target)+1 if target in ids else None for ids, target in zip(ranks, gold)]
    return {"cases": len(gold), **{f"recall_at_{k}": sum(pos is not None and pos <= k for pos in positions)/len(gold)
                                     for k in (1,3,5,10)},
            "mrr": sum(1/pos if pos else 0 for pos in positions)/len(gold),
            "positions": positions}


def main():
    started = time.perf_counter()
    registry = CapabilityRegistry()
    retriever = CapabilityRetriever(registry)
    rankings = [rank(case, registry, retriever) for case in CASES]
    gold = [case[-1] for case in CASES]
    if any(registry.get(item) is None for item in gold):
        raise RuntimeError("Gold capability missing from current registry")
    hybrid = [x[0] for x in rankings]
    lexical = [x[1] for x in rankings]
    result = {"registry_capabilities": len(registry.list_all()),
              "scope": "18 hand-specified offline confusion cases; not representative natural-language accuracy",
              "lexical_baseline": metrics(lexical, gold), "frame_aware": metrics(hybrid, gold),
              "cases": [{"text": c[0], "action": c[1], "domain": c[2], "gold": c[-1],
                         "baseline_top1": b[0] if b else None, "hybrid_top1": h[0]}
                        for c, h, b in zip(CASES, hybrid, lexical)],
              "latency_ms_per_case": (time.perf_counter()-started)*1000/len(CASES),
              "live_availability_checked": False, "executed_tools": False}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "capability_dev.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"lexical": result["lexical_baseline"], "frame_aware": result["frame_aware"]}, indent=2))


if __name__ == "__main__":
    main()
