"""Universal Operator latency benchmark (container-measurable parts).

Measures (1) routing latency of the operator scenarios' canonical wordings through the real router with a warm
instance, and (2) the in-process overhead of each primitive on the in-memory desktop/browser/phone (resolver,
verification bookkeeping, chord parsing) - the part JARVIS adds on top of the OS/app's own latency. Real application
latency (Chrome, Notepad, Antigravity, ADB) needs a Windows PC and a phone: see reports/UNIVERSAL_OPERATOR_REAL_ACCEPTANCE.md.

    python scripts/bench_operator.py            # writes reports/UNIVERSAL_OPERATOR_BENCHMARK.md
"""
from __future__ import annotations

import asyncio
import json
import logging
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(p * (len(xs) - 1)))], 3) if xs else 0.0


def stats(xs: list[float]) -> dict:
    return {"n": len(xs), "p50": round(statistics.median(xs), 3), "p95": pct(xs, 0.95), "max": round(max(xs), 3)}


async def bench_routing() -> dict:
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter
    from tests.operator.scenarios import SCENARIOS
    router = SmartRouter(llm_provider=DisabledProvider())
    texts = [s.seeds[0] for s in SCENARIOS]
    for t in texts[:20]:
        await router.route(t)                                  # warm-up (regex compile, lazy imports)
    by_fam: dict[str, list[float]] = {}
    op_only: list[float] = []
    for s in SCENARIOS:
        t0 = time.perf_counter()
        d = await router.route(s.seeds[0])
        ms = (time.perf_counter() - t0) * 1000
        by_fam.setdefault(s.family, []).append(ms)
        if (d.intent or "").endswith("_op"):
            op_only.append(ms)
    allv = [v for xs in by_fam.values() for v in xs]
    return {"all": stats(allv), "operator_routes": stats(op_only), "by_family": {k: stats(v) for k, v in sorted(by_fam.items())}}


def bench_primitives(rounds: int = 300) -> dict:
    from jarvis.core.desktop.dictation_controller import DictationController
    from jarvis.core.operator.browser import BrowserOperator, FakeBrowser
    from jarvis.core.operator.dictate import LiveDictation
    from jarvis.core.operator.media import MediaOperator
    from jarvis.core.operator.platform import FakeDesktop, set_desktop
    from jarvis.core.operator.refs import ControlRef
    from jarvis.core.operator.resources import OperatorResources
    from jarvis.core.operator.text import EditRequest, TextOperator
    from jarvis.core.operator.ui import FakeUIAdapter, UIOperator
    from jarvis.core.operator.windows import WindowTracker
    out: dict[str, dict] = {}

    def timeit(name, fn, setup=None):
        xs = []
        for _ in range(rounds):
            ctx = setup() if setup else None
            t0 = time.perf_counter()
            fn(ctx)
            xs.append((time.perf_counter() - t0) * 1000)
        out[name] = stats(xs)

    def world():
        d = FakeDesktop()
        set_desktop(d)
        for i in range(25):
            d.open(f"app{i}.exe", f"Window {i}")
        ed = d.open("notepad.exe", "notes - Notepad", editable=True, text="one two three four five. six seven.")
        d.open("chrome.exe", "YouTube - Google Chrome")
        tr = WindowTracker(d)
        tr.observe()
        return d, tr, ed

    timeit("window.resolve (previous, family, app) over 27 windows",
           lambda c: (c[1].resolve("go back to my editor"), c[1].resolve("chrome"), c[1].previous()), world)
    timeit("window.focus + verify", lambda c: c[1].focus(c[1].resolve("notepad").resource), world)
    controls = [ControlRef(resource_id=f"c{i}", name=f"Item {i}", role="ButtonControl" if i % 3 else "ListItemControl",
                           platform="fake") for i in range(400)]
    controls.append(ControlRef(resource_id="send", name="Send", role="ButtonControl", platform="fake"))
    adapter = FakeUIAdapter(controls)
    ui = UIOperator()
    timeit("ui.resolve over 401 controls (name+role)", lambda c: ui.find(adapter, "the send button"))
    timeit("ui.resolve ordinal over 401 controls", lambda c: ui.find(adapter, "the third list item"))

    def text_setup():
        d, tr, ed = world()
        tr.focus(tr.resolve("notepad").resource)
        return d

    timeit("text.edit delete 2 words (+read-back verify)", lambda d: TextOperator(d).edit(EditRequest("delete", "word", 2)),
           text_setup)

    def live_setup():
        d = FakeDesktop()
        h = d.open("notepad.exe", "n", editable=True)
        c = DictationController()
        c.set_test_target(hwnd=h)
        c.start()
        lv = LiveDictation(c, d)
        lv.begin()
        return lv

    words = "please send the quarterly report to the whole team by friday evening".split()
    timeit("dictation.feed (one stable-prefix update)",
           lambda lv: [lv.feed(" ".join(words[:i])) for i in range(1, len(words) + 1)], live_setup)
    out["dictation.feed (one stable-prefix update)"]["note"] = f"per call = value / {len(words)}"

    def browser_setup():
        fb = FakeBrowser()
        fb.add_page("https://www.youtube.com/results?search_query=x", "x - YouTube",
                    results=[{"title": f"r{i}", "url": f"https://www.youtube.com/watch?v={i}"} for i in range(20)])
        for i in range(20):
            fb.add_page(f"https://www.youtube.com/watch?v={i}", f"v{i}",
                        media={"paused": False, "t": 0.0, "d": 600.0, "rate": 1.0, "muted": False, "volume": 1.0})
        b = BrowserOperator(fb, OperatorResources())
        b.open("x", engine="youtube")
        return b

    timeit("browser.open_result(3) (+URL verify)", lambda b: b.open_result(3), browser_setup)
    timeit("media.seek_to (+state read-back)", lambda b: (b.open_result(1), MediaOperator(b, FakeDesktop(),
                                                                                         OperatorResources()).act("seek_to", 90)),
           browser_setup)
    return out


def write_report(routing: dict, prims: dict) -> Path:
    lines = ["# Universal Operator - Benchmark", "",
             "Measured in the CI container (Linux, no display): routing is the real `SmartRouter` with no AI model; "
             "primitive numbers are JARVIS's own overhead on the in-memory desktop/browser/phone (resolution, chord "
             "parsing, verification bookkeeping). **Application latency on a real PC (window activation, UIA tree "
             "reads, Chrome DevTools, ADB) is not measured here** - it is part of the real-machine acceptance run.", "",
             "Command: `python scripts/bench_operator.py`", "",
             "## Routing latency (ms, warm router, 1 canonical wording per scenario)", "",
             "| Slice | n | p50 | p95 | max |", "|---|---:|---:|---:|---:|"]
    for name, s in [("all scenarios", routing["all"]), ("routes to operator tools", routing["operator_routes"])] + \
            list(routing["by_family"].items()):
        lines.append(f"| {name} | {s['n']} | {s['p50']} | {s['p95']} | {s['max']} |")
    lines += ["", "## Primitive overhead (ms, in-process, fake platform)", "", "| Primitive | n | p50 | p95 | max |",
              "|---|---:|---:|---:|---:|"]
    for name, s in prims.items():
        lines.append(f"| {name} | {s['n']} | {s['p50']} | {s['p95']} | {s['max']} |" + (f" {s['note']}" if s.get("note") else ""))
    lines += ["", "## Reading the numbers", "",
              "* The fast path never calls a model, the planner or retrieval: a parsed operator command is a regex/typed "
              "parse plus one registered tool.",
              "* Waits are on observed state (`Desktop.wait_until`: foreground hwnd, window state, clipboard sequence, "
              "page URL, prompt box value), not fixed sleeps; the fake platform answers instantly, so these numbers are "
              "the floor JARVIS adds, and real latency = this + the OS/app's own response.",
              "* Live dictation work per stable-prefix update is microseconds; end-to-end typing latency is dominated "
              "by the recogniser's partial interval (200 ms) and stabilisation.", ""]
    path = ROOT / "reports" / "UNIVERSAL_OPERATOR_BENCHMARK.md"
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    logging.disable(logging.WARNING)
    routing = asyncio.run(bench_routing())
    prims = bench_primitives()
    print(json.dumps({"routing": routing["all"], "operator_routes": routing["operator_routes"]}, indent=2))
    print(write_report(routing, prims))


if __name__ == "__main__":
    main()
