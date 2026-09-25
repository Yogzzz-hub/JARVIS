import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.generalization.benchmark_runner import GeneralizationBenchmarkRunner

async def analyze():
    runner = GeneralizationBenchmarkRunner(dataset_dir=Path('tests/generalization'))
    for fpath in sorted(runner.dataset_dir.glob('*.jsonl')):
        runner.failures = []
        await runner._run_dataset_file(fpath)
        if runner.failures:
            print(f"\n=== Failures in {fpath.stem} (Total {len(runner.failures)}) ===")
            for f in runner.failures[:4]:
                print(f"  ID: {f.get('test_id')}, Input: '{f.get('input')}'")
                print(f"    Expected: behavior={f.get('expected_behavior')}, intent={f.get('expected_intent')}, caps={f.get('expected_capabilities')}")
                print(f"    Actual: intent={f.get('actual_intent')}, lane={f.get('actual_lane')}, retrieved={f.get('retrieved_capabilities')}")
                print(f"    Detail: {f.get('detail')}")

if __name__ == "__main__":
    asyncio.run(analyze())
