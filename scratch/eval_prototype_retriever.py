import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from jarvis.core.capabilities.registry import get_default_capability_registry
from scratch.test_hybrid_retriever import PrototypeRetriever
from scratch.canonical_map import to_canonical as canonicalize

def run_eval():
    reg = get_default_capability_registry()
    retriever = PrototypeRetriever(reg)

    datasets = sorted(Path("tests/generalization").glob("*.jsonl"))

    total = 0
    c_r1 = 0
    c_r3 = 0
    c_r5 = 0
    c_r10 = 0

    cov_r3 = 0
    cov_r5 = 0
    cov_r10 = 0

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
                cat = rec.get("category", "")
                mem = None
                if cat in ("contextual", "pronoun", "ordinal"):
                    from jarvis.core.memory.working import BoundedWorkingMemory
                    mem = BoundedWorkingMemory()
                    mem.record_search_results([
                        {"path": "C:\\Users\\ashok\\Downloads\\contract_1.pdf", "name": "contract_1.pdf", "modified": "2026-09-20"},
                        {"path": "C:\\Users\\ashok\\Downloads\\contract_2.pdf", "name": "contract_2.pdf", "modified": "2026-09-22"},
                        {"path": "C:\\Users\\ashok\\Downloads\\contract_3.pdf", "name": "contract_3.pdf", "modified": "2026-09-21"},
                    ])
                    mem.record_file_opened("C:\\Users\\ashok\\Downloads\\contract_2.pdf")
                    mem.record_app_focused("notepad")

                retrieved = retriever.retrieve(inp, top_k=10, min_score=0.1, working_memory=mem)
                canon_ret_ids = [canonicalize(c.id) for c, _ in retrieved]
                primary_canon = canonicalize(expected_caps[0])

                if canon_ret_ids and primary_canon == canon_ret_ids[0]:
                    c_r1 += 1
                if primary_canon in canon_ret_ids[:3]:
                    c_r3 += 1
                if primary_canon in canon_ret_ids[:5]:
                    c_r5 += 1
                if primary_canon in canon_ret_ids[:10]:
                    c_r10 += 1

                expected_canon_set = set(canonicalize(c) for c in expected_caps)
                if expected_canon_set.issubset(set(canon_ret_ids[:3])):
                    cov_r3 += 1
                if expected_canon_set.issubset(set(canon_ret_ids[:5])):
                    cov_r5 += 1
                if expected_canon_set.issubset(set(canon_ret_ids[:10])):
                    cov_r10 += 1

    print("============================================================")
    print("PROTOTYPE HYBRID RETRIEVER BENCHMARK RESULTS")
    print("============================================================")
    print(f"Total Evaluated Items: {total}")
    print("------------------------------------------------------------")
    print(f"Primary Canonical Recall@1:  {c_r1 / total * 100:.2f}%  ({c_r1}/{total})")
    print(f"Primary Canonical Recall@3:  {c_r3 / total * 100:.2f}%  ({c_r3}/{total})")
    print(f"Primary Canonical Recall@5:  {c_r5 / total * 100:.2f}%  ({c_r5}/{total})")
    print(f"Primary Canonical Recall@10: {c_r10 / total * 100:.2f}%  ({c_r10}/{total})")
    print("------------------------------------------------------------")
    print(f"Required Capability Coverage@3:  {cov_r3 / total * 100:.2f}%  ({cov_r3}/{total})")
    print(f"Required Capability Coverage@5:  {cov_r5 / total * 100:.2f}%  ({cov_r5}/{total})")
    print(f"Required Capability Coverage@10: {cov_r10 / total * 100:.2f}%  ({cov_r10}/{total})")
    print("============================================================")

if __name__ == "__main__":
    run_eval()
