import sys
sys.path.insert(0, ".")
import json
import asyncio
from pathlib import Path
from tests.generalization.benchmark_runner import GeneralizationBenchmarkRunner

async def main():
    runner = GeneralizationBenchmarkRunner(Path("tests/generalization"))
    path = Path("tests/generalization/unknown.jsonl")
    records = [json.loads(line) for line in open(path, "r", encoding="utf-8") if line.strip()]
    passed_cnt = 0
    fails = []
    for rec in records:
        ok = await runner._evaluate_record(rec)
        if ok:
            passed_cnt += 1
        else:
            fails.append((rec, runner.failures[-1] if runner.failures else None))
    print(f"Unknown result: {passed_cnt}/{len(records)} ({passed_cnt/len(records)*100:.1f}%)")
    print(f"Failed count: {len(fails)}")
    for rec, f_item in fails:
        print(f"FAILED: {rec.get('id')} - {rec.get('input')}")

if __name__ == "__main__":
    asyncio.run(main())
