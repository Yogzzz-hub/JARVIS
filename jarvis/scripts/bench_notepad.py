"""Real Windows launches; deliberately small sample to avoid 1000 GUI launches."""
import argparse
import http.client
import json
from time import perf_counter_ns
from jarvis.config import ROOT
from jarvis.scripts.bench_core import summarize

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=20)
    args = parser.parse_args()
    connection = http.client.HTTPConnection("127.0.0.1", 8765, timeout=15)
    records = []
    for _ in range(args.iterations):
        started = perf_counter_ns()
        connection.request("POST", "/command", body=json.dumps({"text": "open notepad", "source": "benchmark"}),
                           headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        result = json.loads(response.read())
        result["round_trip_ms"] = (perf_counter_ns() - started) / 1e6
        records.append(result)
        if result["state"] != "SUCCESS":
            break
    report = {"kind": "real native Windows launches; process-existence verification; may reuse existing process",
              "iterations": len(records), "successes": sum(r["state"] == "SUCCESS" for r in records),
              "metrics": {key: summarize([r["metrics"][key] for r in records if r["metrics"][key] is not None])
                          for key in records[0]["metrics"]}, "records": records}
    (ROOT / "docs/notepad-benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "records"}, indent=2))
    connection.close()

if __name__ == "__main__":
    main()
