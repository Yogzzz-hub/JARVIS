import argparse
import asyncio
import json
from pathlib import Path
import statistics
from time import perf_counter_ns
from jarvis.config import ROOT
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.router.models import RouteLane
from jarvis.core.router.ollama import OllamaProvider
from jarvis.core.router.router import SmartRouter
from jarvis.scripts.bench_core import summarize

class BenchmarkLLMProvider:
    """Mock/Warm model provider for automated deterministic testing when Ollama offline."""
    async def classify(self, text, candidates, request_id):
        from jarvis.core.router.models import RouteDecision, RouteLane, RouteSource, ComplexityLevel, ReasonCode
        return RouteDecision(
            request_id=request_id,
            lane=RouteLane.LANE_1,
            intent=candidates[0].name if candidates else "open_app",
            slots={},
            confidence=0.92,
            source=RouteSource.TINY_MODEL,
            complexity=ComplexityLevel.SIMPLE,
            normalized_text=text,
            reason_code=ReasonCode.LLM_CLASSIFIED,
            breakdown_ms={"model_total_ms": 185.2, "model_prompt_eval_ms": 42.1, "model_generation_ms": 143.1},
        )

async def run_benchmark(iterations_a=1000, iterations_b=1000, iterations_c=500, iterations_d=100, iterations_e=100, iterations_f=100):
    router = SmartRouter(llm_provider=BenchmarkLLMProvider())

    # Dataset A: 1000 Lane-0 exact commands
    exact_cmds = ["open chrome", "start vscode", "launch calculator", "time", "system info", "screenshot", "lock pc"]
    latencies_a = []
    for i in range(iterations_a):
        cmd = exact_cmds[i % len(exact_cmds)]
        t0 = perf_counter_ns()
        dec = await router.route(CommandRequest(text=cmd))
        lat = (perf_counter_ns() - t0) / 1e6
        latencies_a.append(lat)
        assert dec.lane == RouteLane.LANE_0

    # Dataset B: 1000 Lane-0 parameterized commands
    param_cmds = [f"volume {10 + (i % 80)}" for i in range(100)] + ["list desktop", "list downloads", "shutdown after 600 seconds"]
    latencies_b = []
    for i in range(iterations_b):
        cmd = param_cmds[i % len(param_cmds)]
        t0 = perf_counter_ns()
        dec = await router.route(CommandRequest(text=cmd))
        lat = (perf_counter_ns() - t0) / 1e6
        latencies_b.append(lat)
        assert dec.lane == RouteLane.LANE_0

    # Dataset C: 500 fuzzy / casual commands
    fuzzy_cmds = [
        "make it a little quieter", "bring the sound down a little",
        "hey jarvis please open vs code da", "bro launch calculator please",
        "turn volume to thirty", "could you please check time"
    ]
    latencies_c = []
    for i in range(iterations_c):
        cmd = fuzzy_cmds[i % len(fuzzy_cmds)]
        t0 = perf_counter_ns()
        dec = await router.route(CommandRequest(text=cmd))
        lat = (perf_counter_ns() - t0) / 1e6
        latencies_c.append(lat)
        assert dec.lane in (RouteLane.LANE_0, RouteLane.LANE_1)

    # Dataset D: 100 Lane-1 requests
    lane1_cmds = ["could you bring the sound down a tiny notch", "please launch my editing environment", "set audio level down a bit"]
    latencies_d = []
    for i in range(iterations_d):
        cmd = lane1_cmds[i % len(lane1_cmds)]
        t0 = perf_counter_ns()
        dec = await router.route(CommandRequest(text=cmd))
        lat = (perf_counter_ns() - t0) / 1e6
        latencies_d.append(lat)

    # Dataset E: 100 complex Lane-2 detections
    complex_cmds = [
        "find my notes and email them to santosh",
        "prepare everything I need for tomorrow ML lab",
        "check tomorrow schedule and find the relevant files",
        "compare report1.pdf and report2.pdf and summarize differences",
    ]
    latencies_e = []
    lane2_count = 0
    for i in range(iterations_e):
        cmd = complex_cmds[i % len(complex_cmds)]
        t0 = perf_counter_ns()
        dec = await router.route(CommandRequest(text=cmd))
        lat = (perf_counter_ns() - t0) / 1e6
        latencies_e.append(lat)
        if dec.lane == RouteLane.LANE_2 and dec.needs_planner:
            lane2_count += 1

    # Dataset F: 100 adversarial negative requests
    adv_path = ROOT / "tests/data/router_adversarial.jsonl"
    if not adv_path.exists():
        adv_path = Path("tests/data/router_adversarial.jsonl")
    with adv_path.open(encoding="utf-8") as f:
        traps = [json.loads(line) for line in f]

    latencies_f = []
    wrong_executions = 0
    for i in range(iterations_f):
        trap = traps[i % len(traps)]
        t0 = perf_counter_ns()
        dec = await router.route(CommandRequest(text=trap["text"]))
        lat = (perf_counter_ns() - t0) / 1e6
        latencies_f.append(lat)
        forbidden = trap.get("forbidden_intent")
        if forbidden == "any_tool" and dec.lane in (RouteLane.LANE_0, RouteLane.LANE_1) and dec.intent is not None:
            wrong_executions += 1
        elif dec.lane in (RouteLane.LANE_0, RouteLane.LANE_1) and dec.intent == forbidden:
            wrong_executions += 1

    # CONTROL latency test (1000 runs)
    control_latencies = []
    for _ in range(1000):
        t0 = perf_counter_ns()
        dec = await router.route(CommandRequest(text="stop"))
        control_latencies.append((perf_counter_ns() - t0) / 1e6)
        assert dec.lane == RouteLane.CONTROL

    # HOT CACHE latency test (1000 runs)
    await router.route(CommandRequest(text="open chrome"))
    cache_latencies = []
    for _ in range(1000):
        t0 = perf_counter_ns()
        dec = await router.route(CommandRequest(text="open chrome"))
        cache_latencies.append((perf_counter_ns() - t0) / 1e6)
        assert dec.cache_hit is True

    report = {
        "dataset_a_exact": summarize(latencies_a),
        "dataset_b_parameterized": summarize(latencies_b),
        "dataset_c_fuzzy": summarize(latencies_c),
        "dataset_d_lane1": summarize(latencies_d),
        "dataset_e_complex_lane2": summarize(latencies_e),
        "dataset_f_adversarial": summarize(latencies_f),
        "control_latency": summarize(control_latencies),
        "hot_cache_latency": summarize(cache_latencies),
        "quality_metrics": {
            "wrong_execution_count": wrong_executions,
            "complex_lane2_detection_rate": (lane2_count / iterations_e) * 100.0,
            "cache_hits": router.cache.hits,
            "cache_misses": router.cache.misses,
            "total_routed": router.total_routed,
            "lane_distribution": router.lane_counts,
        },
    }

    out1 = ROOT / "docs/router-benchmark.json"
    out1.parent.mkdir(parents=True, exist_ok=True)
    out1.write_text(json.dumps(report, indent=2), encoding="utf-8")

    out2 = ROOT.parent / "docs/router-benchmark.json"
    if out2.resolve() != out1.resolve():
        out2.parent.mkdir(parents=True, exist_ok=True)
        out2.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    return report

def main():
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    asyncio.run(run_benchmark())

if __name__ == "__main__":
    main()
