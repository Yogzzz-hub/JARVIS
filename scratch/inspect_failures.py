import json

with open("reports/generalization_torture_test.json", "r", encoding="utf-8") as f:
    data = json.load(f)

unk_fails = [x for x in data.get("failures_sample", []) if x.get("category") == "unknown"]
print(f"Unknown failures count in sample: {len(unk_fails)}")
for i, x in enumerate(unk_fails[:10]):
    print(f"[{x.get('test_id')}] input='{x.get('input')}'")
    print(f"    actual_intent={x.get('actual_intent')} actual_lane={x.get('actual_lane')}")
    print(f"    retrieved={x.get('retrieved_capabilities')}")
    print(f"    detail={x.get('detail')}")
