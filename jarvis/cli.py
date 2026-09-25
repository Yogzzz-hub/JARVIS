import argparse
import asyncio
import json
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from jarvis.config import load
from jarvis.core.planner.adaptive_planner import AdaptivePlanner
from jarvis.core.planner.schema import format_ascii_dag
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.system.app_resolver import AppResolver
from jarvis.tools.system.native import create_tools


def handle_plan_only(command: str, json_output: bool = False):
    registry = ToolRegistry()
    registry.discover(create_tools(AppResolver(), {}))
    registry.finalize()
    planner = AdaptivePlanner(registry=registry)

    res = asyncio.run(planner.plan(command))
    if not res.graph:
        print(f"Planning failed: {res.error}", file=sys.stderr)
        return 1

    if json_output:
        print(res.graph.model_dump_json(indent=2))
    else:
        print(format_ascii_dag(res.graph))
    return 0


def main():
    parser = argparse.ArgumentParser(description="Send a command to JARVIS EDGE")
    parser.add_argument("command", help="Natural language command for JARVIS")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    parser.add_argument("--plan-only", action="store_true", help="Generate TaskGraph without executing")
    args = parser.parse_args()

    if args.plan_only:
        return handle_plan_only(args.command, json_output=args.json)

    config = load()
    request = Request(
        f"http://127.0.0.1:{config.server.port}/command",
        data=json.dumps({"text": args.command, "source": "cli"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            result = json.load(response)
    except HTTPError as exc:
        try:
            detail = json.load(exc).get("detail", str(exc))
        except (ValueError, AttributeError):
            detail = str(exc)
        print(f"Command rejected ({exc.code}): {detail}", file=sys.stderr)
        return 1
    except (URLError, TimeoutError) as exc:
        print(f"Gateway unavailable: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2) if args.json else result["message"])
    return 0 if result["state"] == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
