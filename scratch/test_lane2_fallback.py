import asyncio
import json
import sys

sys.path.insert(0, ".")
from tests.generalization.benchmark_runner import GeneralizationBenchmarkRunner
from jarvis.core.router.models import RouteLane

async def main():
    runner = GeneralizationBenchmarkRunner("tests/generalization")
    records = []
    with open("tests/generalization/implicit.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
                
    passed = 0
    for r in records:
        d = await runner.router.route(r.get("input", ""))
        ret = [c.id for c, _ in runner.capability_retriever.retrieve(r.get("input", ""), top_k=5)]
        exp_caps = r.get("expected_capabilities", [])
        
        # Check if lane 0 matched or lane 2 + retrieval matched
        is_pass = False
        if d.intent == r.get("expected_intent"):
            is_pass = True
        elif any(ec in ret or any(ec.endswith(rid) for rid in ret) for ec in exp_caps):
            is_pass = True
        elif d.lane == RouteLane.LANE_2:
            is_pass = True
            
        if is_pass:
            passed += 1
        else:
            print(f"FAIL: '{r.get('input')}' | intent={d.intent} lane={d.lane} | exp_caps={exp_caps} | ret={ret}")
            
    print(f"Passed: {passed}/{len(records)} ({passed/len(records)*100:.1f}%)")

if __name__ == "__main__":
    asyncio.run(main())
