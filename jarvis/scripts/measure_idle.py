import argparse
import json
from pathlib import Path
import time
import psutil
from jarvis.config import ROOT

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pid", type=int)
    args = parser.parse_args()
    process = psutil.Process(args.pid)
    before = process.cpu_times()
    start = time.perf_counter()
    time.sleep(10)  # Measurement window, not a service polling loop.
    after = process.cpu_times()
    elapsed = time.perf_counter() - start
    result = {"pid": args.pid, "seconds": elapsed,
              "rss_mb": process.memory_info().rss / 2**20,
              "cpu_percent_one_core": (after.user + after.system - before.user - before.system) / elapsed * 100,
              "threads": process.num_threads(),
              "children": [child.pid for child in process.children()],
              "command": process.cmdline()}
    (ROOT / "docs/idle.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
