"""RAG retrieval benchmark: precision, recall and abstention on a synthetic personal knowledge base.

    python -m tests.rag.benchmark            # lexical path (no embedding model needed)

Answerable questions must retrieve their source document (recall) without unrelated documents (precision).
Unanswerable questions must retrieve nothing (abstention) - that is what keeps the chat model from grounding an
answer on unrelated text. ``--baseline`` measures plain fused top-k (the behaviour before the reranker).
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DOCS = {
    "refund_policy.md": "# Refund policy\n\nCustomers can request a full refund within 30 days of purchase. After 30 days only store credit is "
                        "offered. Refunds are paid back to the original payment method within 7 working days.\n\n"
                        "# Damaged items\n\nDamaged items must be reported with photos within 48 hours of delivery.",
    "wifi_setup.txt": "Home wifi setup\n\nThe router admin page is at 192.168.0.1. The network name is Skynet-5G and the guest network "
                      "is Skynet-Guest. Restart the router by holding the reset button for 10 seconds.",
    "car_notes.md": "# Car service\n\nThe car was serviced at Sri Motors on 12 March. Next oil change is due at 45,000 km. "
                    "Tyre pressure should be 32 psi front and 30 psi rear.\n\n# Insurance\n\nInsurance renewal is due every August with ICICI Lombard.",
    "exam_timetable.txt": "Semester exam timetable\n\nData Structures exam on 4 December at 10 AM in Hall B. Operating Systems exam on 7 "
                          "December at 2 PM. Computer Networks lab exam on 10 December.",
    "project_jarvis.md": "# JARVIS project\n\nThe project deadline is 20 November. The demo will be presented to Dr. Nisha. "
                         "Team 62 members: Yogesh, Devi, Arun and Karthik.\n\n# Tasks\n\nYogesh handles the voice pipeline, Devi the UI.",
    "recipes.md": "# Chettinad chicken\n\nRoast fennel, pepper and dry red chillies, grind with coconut. Cook chicken with onions for "
                  "20 minutes.\n\n# Filter coffee\n\nUse 3 spoons of coffee powder per decoction; mix one part decoction with three parts milk.",
    "gym_plan.txt": "Weekly gym plan\n\nMonday chest and triceps, Wednesday back and biceps, Friday legs. Run 3 km on Sunday. "
                    "Protein target is 110 grams per day.",
    "rent_agreement.txt": "Rent agreement\n\nMonthly rent is 15,000 rupees due on the 5th of each month. The security deposit is 45,000 "
                          "rupees. Notice period for leaving is two months. Landlord: Mr. Raghavan.",
    "laptop_warranty.txt": "Laptop warranty\n\nThe Dell Inspiron laptop was bought on 2 January 2025 with a two year warranty. "
                           "Service centre: Dell Care, Anna Nagar. Battery is covered for one year only.",
    "travel_madurai.md": "# Madurai trip\n\nTrain Vaigai Express leaves Chennai Egmore at 1:40 PM. Hotel booked at Madurai Residency "
                         "for two nights. Visit Meenakshi temple on Saturday morning.",
}

ANSWERABLE = [
    ("how many days do I have to get a refund", "refund_policy.md"),
    ("what is the refund window", "refund_policy.md"),
    ("how do I report a damaged item", "refund_policy.md"),
    ("what is the wifi network name", "wifi_setup.txt"),
    ("router admin page address", "wifi_setup.txt"),
    ("how to reset the router", "wifi_setup.txt"),
    ("when is the next oil change", "car_notes.md"),
    ("what tyre pressure should I use", "car_notes.md"),
    ("when is car insurance renewal", "car_notes.md"),
    ("when is the data structures exam", "exam_timetable.txt"),
    ("which hall is the exam in", "exam_timetable.txt"),
    ("operating systems exam time", "exam_timetable.txt"),
    ("what is the jarvis project deadline", "project_jarvis.md"),
    ("who are the team 62 members", "project_jarvis.md"),
    ("who handles the voice pipeline", "project_jarvis.md"),
    ("how do I make filter coffee", "recipes.md"),
    ("chettinad chicken masala ingredients", "recipes.md"),
    ("what is my protein target", "gym_plan.txt"),
    ("what do I train on wednesday at the gym", "gym_plan.txt"),
    ("how much is the monthly rent", "rent_agreement.txt"),
    ("what is the security deposit", "rent_agreement.txt"),
    ("notice period for leaving the house", "rent_agreement.txt"),
    ("when does my laptop warranty end", "laptop_warranty.txt"),
    ("where is the dell service centre", "laptop_warranty.txt"),
    ("what time does the vaigai express leave", "travel_madurai.md"),
    ("which hotel did I book in madurai", "travel_madurai.md"),
    ("when is the meenakshi temple visit", "travel_madurai.md"),
    ("how long does a refund take to reach my account", "refund_policy.md"),
    ("who is my landlord", "rent_agreement.txt"),
    ("is the laptop battery covered", "laptop_warranty.txt"),
]

UNANSWERABLE = [
    "what is the capital of australia",
    "what is my passport number",
    "when is my dentist appointment",
    "how do I bake sourdough bread",
    "what is the password for my bank account",
    "who won the cricket match yesterday",
    "what is my blood group",
    "when does the electricity bill come",
    "what is the name of my manager",
    "how do I learn guitar chords",
    "what did the doctor prescribe",
    "which movie should I watch tonight",
]


def run(baseline: bool = False, limit: int = 3) -> dict:
    from jarvis.core.knowledge import engine as eng
    with tempfile.TemporaryDirectory() as td:
        docs = Path(td) / "docs"
        docs.mkdir()
        for name, text in DOCS.items():
            (docs / name).write_text(text, encoding="utf-8")
        ke = eng.KnowledgeEngine(Path(td) / "kb.db")
        ke.ingest_path(docs, "Bench")
        if baseline:  # fused top-k without the precision layer
            original = eng.rerank
            eng.rerank = lambda q, items, limit=5, **k: list(items)[:limit]
        try:
            hit = prec_num = prec_den = abstain = 0
            misses = []
            for q, src in ANSWERABLE:
                res = ke.search_hybrid(q, limit=limit)
                files = [Path(r.citation_metadata.get("file_path", "")).name for r in res]
                if src in files:
                    hit += 1
                else:
                    misses.append((q, files))
                prec_num += sum(f == src for f in files)
                prec_den += len(files)
            false_hits = []
            for q in UNANSWERABLE:
                res = ke.search_hybrid(q, limit=limit)
                if not res:
                    abstain += 1
                else:
                    false_hits.append((q, [Path(r.citation_metadata.get("file_path", "")).name for r in res]))
        finally:
            if baseline:
                eng.rerank = original
    return {"recall": hit / len(ANSWERABLE), "precision": prec_num / max(1, prec_den),
            "abstention": abstain / len(UNANSWERABLE), "misses": misses, "false_hits": false_hits}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true")
    args = ap.parse_args()
    r = run(args.baseline)
    print(f"recall@3 {r['recall']:.1%}  precision {r['precision']:.1%}  abstention on unanswerable {r['abstention']:.1%}")
    for q, f in r["misses"]:
        print("  MISS", q, f)
    for q, f in r["false_hits"]:
        print("  FALSE", q, f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
