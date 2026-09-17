"""Measured microbenchmarks and localhost round trips. No model/GPU needed.

Run with a service already listening: python -m jarvis.scripts.bench_core
"""
import argparse
import asyncio
import http.client
import json
from pathlib import Path
import statistics
import tempfile
from time import perf_counter_ns
import uuid
import psutil
from websockets.asyncio.client import connect
from jarvis.config import Config, ROOT
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.commands.resolver import resolve
from jarvis.core.runtime import Runtime
from jarvis.tools.system.native import Empty, TimeOutput, SystemTool
from jarvis.tools.system.native import create_tools
from jarvis.tools.system.app_resolver import LaunchTarget

def summarize(values):
    values = sorted(values)
    def percentile(p):
        return values[min(len(values) - 1, round((len(values) - 1) * p))]
    return {"n": len(values), "p50": percentile(.5), "p95": percentile(.95), "p99": percentile(.99),
            "mean": statistics.mean(values), "max": max(values)}

def measure(function, count):
    values = []
    for _ in range(count):
        start = perf_counter_ns()
        function()
        values.append((perf_counter_ns() - start) / 1e6)
    return summarize(values)

async def benchmark(count, url, output):
    results = {}
    with tempfile.TemporaryDirectory() as directory:
        def benchmark_tools(resolver, hardware):
            return [SystemTool("get_time", Empty, TimeOutput, lambda _: {"iso": "benchmark"}),
                    create_tools(resolver, hardware, launcher=lambda _: 123)[0]]
        runtime = Runtime(Config(), root=Path(directory), tools_factory=benchmark_tools)
        await runtime.start()
        try:
            results["command_validation"] = measure(lambda: CommandRequest.model_validate({"text": "time"}), count)
            results["registry_lookup"] = measure(lambda: runtime.registry.get("get_time"), count)
            results["command_resolution"] = measure(lambda: resolve("open notepad"), count)
            async def observer(event):
                return None
            runtime.bus.subscribe(observer)
            results["event_emission"] = measure(lambda: runtime.bus.emit("bench", "bench"), count)
            await asyncio.sleep(0)
            results["persistence_enqueue"] = measure(lambda: runtime.writer.enqueue("metrics", "bench", {"value": 1}), count)
            # Includes bounded task history, native worker hop, output validation and verification.
            totals, first = [], []
            for _ in range(count):
                start = perf_counter_ns()
                result = await runtime.service.handle(CommandRequest(text="time", source="benchmark"))
                if result.state != "SUCCESS":
                    raise RuntimeError(result.message)
                totals.append((perf_counter_ns() - start) / 1e6)
                first.append(result.metrics["first_action_ms"])
            results["text_command_dispatch"] = summarize(totals)
            results["first_action_in_process"] = summarize(first)
            runtime.resolver.cache["notepad"] = LaunchTarget("mock-notepad.exe", ("notepad.exe",))
            runtime.verifier.probe = lambda _: {"pid": 123, "mock": True}
            first, verification, totals = [], [], []
            for _ in range(count):
                result = await runtime.service.handle(CommandRequest(text="open notepad", source="benchmark"))
                assert result.state == "SUCCESS"
                first.append(result.metrics["first_action_ms"])
                verification.append(result.metrics["verification_ms"])
                totals.append(result.metrics["total_ms"])
            results["mock_notepad_first_action"] = summarize(first)
            results["mock_notepad_verification"] = summarize(verification)
            results["mock_notepad_total"] = summarize(totals)
            results["microbench_drops"] = {"events": runtime.bus.dropped, "persistence": runtime.writer.dropped,
                                            "metrics": runtime.metrics.dropped, "logs": runtime.logs.handler.dropped}
        finally:
            await runtime.close()
    print("Microbenchmarks complete", flush=True)

    server_process = None
    host, port = url.split(":")
    try:
        try:
            check_conn = http.client.HTTPConnection(host, int(port), timeout=1)
            check_conn.request("GET", "/health")
            if check_conn.getresponse().status != 200:
                raise RuntimeError("Service returned non-200")
            check_conn.close()
        except Exception:
            import subprocess, sys, time
            print(f"Service not detected on {url}, starting background jarvis service...", flush=True)
            server_process = subprocess.Popen([sys.executable, "-m", "jarvis"], cwd=str(ROOT.parent))
            started = False
            for _ in range(50):
                time.sleep(0.2)
                try:
                    check_conn = http.client.HTTPConnection(host, int(port), timeout=1)
                    check_conn.request("GET", "/health")
                    if check_conn.getresponse().status == 200:
                        started = True
                        check_conn.close()
                        break
                    check_conn.close()
                except Exception:
                    pass
            if not started:
                raise RuntimeError(f"Failed to start jarvis service on {url}")

        connection = http.client.HTTPConnection(host, int(port), timeout=10)
        def request(method, path, data=None):
            connection.request(method, path, body=json.dumps(data) if data else None,
                               headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            payload = json.loads(response.read())
            if response.status != 200:
                raise RuntimeError(payload)
            return payload
        results["health_round_trip"] = measure(lambda: request("GET", "/health"), count)
        print("HTTP health benchmark complete", flush=True)
        first, verification, total, roundtrip = [], [], [], []
        for _ in range(count):
            start = perf_counter_ns()
            result = request("POST", "/command", {"text": "time", "source": "benchmark"})
            roundtrip.append((perf_counter_ns() - start) / 1e6)
            if result["state"] != "SUCCESS":
                raise RuntimeError(result)
            first.append(result["metrics"]["first_action_ms"])
            verification.append(result["metrics"]["verification_ms"])
            total.append(result["metrics"]["total_ms"])
        results["http_command_round_trip"] = summarize(roundtrip)
        results["first_action_http"] = summarize(first)
        results["verification_http"] = summarize(verification)
        results["total_http"] = summarize(total)
        print("HTTP commands complete", flush=True)

        async with connect(f"ws://{url}/ws", compression="deflate", max_queue=16) as socket:
            results["ws_extensions"] = socket.response.headers.get("Sec-WebSocket-Extensions")
            samples = []
            for i in range(count):
                message = json.dumps({"version": 1, "type": "ping", "request_id": f"p{i}"})
                start = perf_counter_ns()
                await socket.send(message)
                assert json.loads(await socket.recv())["type"] == "pong"
                samples.append((perf_counter_ns() - start) / 1e6)
            results["websocket_ping_round_trip"] = summarize(samples)
            samples, first = [], []
            for i in range(count):
                message = json.dumps({"version": 1, "type": "command", "request_id": f"b{uuid.uuid4().hex}", "text": "time"})
                start = perf_counter_ns()
                await socket.send(message)
                assert json.loads(await socket.recv())["type"] == "task_state"
                response = json.loads(await socket.recv())
                assert response["state"] == "SUCCESS"
                samples.append((perf_counter_ns() - start) / 1e6)
                first.append(response["metrics"]["first_action_ms"])
            results["websocket_command_round_trip"] = summarize(samples)
            results["first_action_websocket"] = summarize(first)
        results["health_after"] = request("GET", "/health")
        connection.close()
    finally:
        if server_process:
            print("Stopping background jarvis service...", flush=True)
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except Exception:
                server_process.kill()

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    root_output = ROOT.parent / "docs/benchmark.json"
    if root_output.resolve() != output.resolve():
        root_output.parent.mkdir(parents=True, exist_ok=True)
        root_output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--address", default="127.0.0.1:8765")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/benchmark.json")
    args = parser.parse_args()
    if args.iterations < 1000:
        parser.error("at least 1000 iterations required")
    asyncio.run(benchmark(args.iterations, args.address, args.output))

if __name__ == "__main__":
    main()
