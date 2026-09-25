import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.generalization.benchmark_runner import GeneralizationBenchmarkRunner

async def main():
    runner = GeneralizationBenchmarkRunner(Path("tests/generalization"))
    await runner.run_all("tests/generalization/canonical.jsonl")
    print(f"\n--- CANONICAL FAILURES ({len(runner.failures)}) ---")
    for f in runner.failures:
        print(f"[{f['test_id']}] '{f['input']}' -> expected: {f['expected_intent']} | actual: {f['actual_intent']} | detail: {f['detail']}")

if __name__ == "__main__":
    asyncio.run(main())
