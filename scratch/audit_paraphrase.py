"""Audit paraphrase failures and inspect root causes."""

import json
from pathlib import Path

with open("reports/generalization_torture_test.json", "r", encoding="utf-8") as f:
    d = json.load(f)

failures = d.get("failures_sample", [])
print(f"Total failures captured: {len(failures)}")

for idx, f in enumerate(failures, 1):
    print(f"[{idx}] Input: {f['input']}")
    print(f"    Expected Intent: {f['expected_intent']} | Expected Caps: {f['expected_capabilities']}")
    print(f"    Actual Intent:   {f['actual_intent']} | Actual Lane: {f['actual_lane']}")
    print(f"    Retrieved Top 3: {f['retrieved_capabilities'][:3]}")
    print(f"    Detail: {f['detail']}")
