import sys
sys.path.insert(0, ".")
import asyncio
from pathlib import Path
from tests.generalization.benchmark_runner import GeneralizationBenchmarkRunner

async def main():
    runner = GeneralizationBenchmarkRunner(Path("tests/generalization_holdout"), output_dir=Path("reports/holdout"))
    summary = await runner.run_all()
    print("Holdout Summary:")
    print(f"Total Evaluated: {summary['total_evaluated']}")
    print(f"Total Passed: {summary['total_passed']}")
    print(f"Accuracy: {summary['overall_accuracy']:.2f}%")
    print("Safety:")
    print(summary['safety'])
    print("\nSample failures:")
    for x in summary.get('failures_sample', [])[:15]:
        print(f"[{x.get('category')}] {x.get('test_id')}: {x.get('input')} -> act={x.get('actual_intent')} detail={x.get('detail')}")

if __name__ == "__main__":
    asyncio.run(main())
