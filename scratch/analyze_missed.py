import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from collections import Counter
from jarvis.core.capabilities.registry import get_default_capability_registry
from scratch.test_hybrid_retriever import PrototypeRetriever
from scratch.audit_retrieval import canonicalize

reg = get_default_capability_registry()
retriever = PrototypeRetriever(reg)

datasets = sorted(Path('tests/generalization').glob('*.jsonl'))
missed = []
missed_by_cat = Counter()
missed_by_expected = Counter()

for dpath in datasets:
    with open(dpath, encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            rec = json.loads(line)
            expected = rec.get('expected_capabilities', [])
            if not expected or '*' in rec.get('forbidden_capabilities', []): continue
            primary_canon = canonicalize(expected[0])
            inp = rec.get('input', '')
            res = retriever.retrieve(inp, top_k=5)
            ret_canon = [canonicalize(c.id) for c, _ in res]
            if not ret_canon or primary_canon != ret_canon[0]:
                cat = rec.get('category', 'unknown')
                missed_by_cat[cat] += 1
                missed_by_expected[primary_canon] += 1
                missed.append({
                    'id': rec.get('id'),
                    'category': cat,
                    'input': inp,
                    'primary_expected': primary_canon,
                    'top_retrieved': ret_canon[:3]
                })

print(f"Total missed at Rank 1: {len(missed)}")
print("\nMissed by Category:")
for cat, count in missed_by_cat.most_common(10):
    print(f"  {cat:25}: {count}")

print("\nMissed by Expected Capability:")
for cap, count in missed_by_expected.most_common(15):
    print(f"  {cap:30}: {count}")

print("\nSample Missed Examples:")
for m in missed[:20]:
    print(f"  [{m['category']}/{m['id']}] '{m['input']}'")
    print(f"    Expected: {m['primary_expected']}")
    print(f"    Got:      {m['top_retrieved']}")
