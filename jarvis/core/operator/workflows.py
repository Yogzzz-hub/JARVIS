"""Named, owner-authored workflows: an ordered list of the owner's own commands, run one after another.

A workflow is data, not code. Every step is re-dispatched through CommandService exactly as if the owner had said
it - its own route, policy check, confirmation and task-scope grant - so a workflow can never do anything the owner
could not have asked for directly. Steps run in order; the run stops at the first step that fails, waits for the
owner or ends UNCERTAIN (nothing is retried blindly). Schedules ("daily 09:00", "weekdays 08:30", "every 30
minutes") are checked by one background thread; a disabled workflow never runs.

    jarvis/db/workflows.json   {"morning": {"steps": ["open outlook", "show my calendar"], "enabled": true,
                                            "schedule": "weekdays 08:30", "last_run": 0}}
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from jarvis.core.operator.refs import OperatorOutcome

logger = logging.getLogger("jarvis.operator.workflows")

STOP_STATES = {"FAILED", "CANCELLED", "UNCERTAIN", "WAITING_CONFIRMATION", "WAITING_FOR_USER"}
_DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_MAX_STEPS = 20


def _default_path() -> Path:
    return Path(__file__).resolve().parents[2] / "db" / "workflows.json"


def parse_schedule(text: str) -> Optional[str]:
    """'every day at 9am' / 'weekdays at 8:30' / 'every 30 minutes' / 'mondays at 18:00' -> canonical string."""
    t = (text or "").lower().strip()
    m = re.search(r"every\s+(\d{1,3})\s*(min|minute|minutes|hour|hours|hr|hrs)\b", t)
    if m:
        n = int(m.group(1)) * (60 if m.group(2).startswith("h") else 1)
        return f"every {max(5, min(n, 1440))} minutes"
    tm = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", t)
    part = re.search(r"\b(morning|afternoon|evening|night)s?\b", t)
    if not tm and not part:
        return None
    if tm:
        h, mi = int(tm.group(1)), int(tm.group(2) or 0)
    else:                                   # "every morning": a fixed, stated default time for that part of the day
        h, mi = {"morning": 8, "afternoon": 14, "evening": 18, "night": 21}[part.group(1)], 0
    if tm and tm.group(3) == "pm" and h < 12:
        h += 12
    if tm and tm.group(3) == "am" and h == 12:
        h = 0
    if h > 23 or mi > 59:
        return None
    if re.search(r"week ?days?|except\s+(?:on\s+)?(?:the\s+)?week ?ends?|not\s+(?:on\s+)?week ?ends?", t):
        days = "weekdays"
    elif re.search(r"week ?ends?|except\s+(?:on\s+)?week ?days?", t):
        days = "weekends"
    else:
        named = [d for d in _DAYS if re.search(rf"\b{d}[a-z]*", t)]
        days = ",".join(named) if named else "daily"
    return f"{days} {h:02d}:{mi:02d}"


def due(schedule: str, now: datetime, last_run: float) -> bool:
    if not schedule:
        return False
    m = re.fullmatch(r"every (\d+) minutes", schedule)
    if m:
        return now.timestamp() - last_run >= int(m.group(1)) * 60
    days, _, hm = schedule.rpartition(" ")
    h, mi = (int(x) for x in hm.split(":"))
    wd = now.weekday()
    ok_day = (days == "daily" or (days == "weekdays" and wd < 5) or (days == "weekends" and wd >= 5)
              or wd in {_DAYS[d] for d in days.split(",") if d in _DAYS})
    if not ok_day or (now.hour, now.minute) < (h, mi):
        return False
    slot = now.replace(hour=h, minute=mi, second=0, microsecond=0).timestamp()
    return last_run < slot


class Workflows:
    def __init__(self, path: Optional[Path] = None, clock=time.time):
        self.path = Path(path) if path else _default_path()
        self._clock = clock
        self._lock = threading.Lock()
        self._dispatch: Optional[Callable] = None
        self._thread: Optional[threading.Thread] = None
        self._running: dict[str, threading.Event] = {}
        self._last = ""                   # the workflow "this" / "it" refers to

    # -- storage ---------------------------------------------------------------------------------------------
    def load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @staticmethod
    def key(name: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"\b(my|the|workflow|routine)\b", " ", (name or "").lower())).strip()

    def _get(self, name: str) -> tuple[dict, str, Optional[dict]]:
        data = self.load()
        k = self.key(name)
        if k in ("this", "it", "that", "") and (self._last in data or len(data) == 1):
            k = self._last if self._last in data else next(iter(data))
        if k in data:
            self._last = k
            return data, k, data[k]
        close = [n for n in data if k and (k in n or n in k)]
        return data, (close[0] if len(close) == 1 else k), (data[close[0]] if len(close) == 1 else None)

    def _missing(self, name: str) -> OperatorOutcome:
        names = ", ".join(sorted(self.load())) or "none yet"
        return OperatorOutcome(False, f"I don't have a workflow called '{name}'. Saved workflows: {names}. "
                                      "Tell me its steps and I'll save it.", needs="clarify")

    # -- operations --------------------------------------------------------------------------------------------
    def create(self, name: str, steps: list[str], replace: bool = False) -> OperatorOutcome:
        k = self.key(name)
        steps = [s.strip() for s in steps if s and s.strip()][:_MAX_STEPS]
        if not k or not steps:
            return OperatorOutcome(False, "A workflow needs a name and at least one step.", needs="clarify")
        with self._lock:
            data = self.load()
            if k in data and not replace:
                return OperatorOutcome(False, f"'{k}' already exists - say 'replace it' or pick another name.",
                                       needs="clarify")
            data[k] = {"steps": steps, "enabled": True, "schedule": "", "last_run": 0, "created": self._clock()}
            self._save(data)
            self._last = k
        return OperatorOutcome(True, f"Saved workflow '{k}' with {len(steps)} step{'s' if len(steps) != 1 else ''}: "
                                     + "; ".join(steps), evidence={"name": k, "steps": steps})

    def clone(self, name: str, new_name: str) -> OperatorOutcome:
        data, k, wf = self._get(name)
        if wf is None:
            return self._missing(name)
        nk = self.key(new_name) or f"{k} copy"
        if nk in data:
            return OperatorOutcome(False, f"'{nk}' already exists.", needs="clarify")
        with self._lock:
            data[nk] = dict(wf, schedule="", last_run=0, created=self._clock())
            self._save(data)
        return OperatorOutcome(True, f"Copied '{k}' to '{nk}'.", evidence={"name": nk})

    def preview(self, name: str) -> OperatorOutcome:
        _, k, wf = self._get(name)
        if wf is None:
            return self._missing(name)
        steps = "; ".join(f"{i}. {s}" for i, s in enumerate(wf["steps"], 1))
        state = "on" if wf.get("enabled", True) else "off"
        sched = f", runs {wf['schedule']}" if wf.get("schedule") else ""
        return OperatorOutcome(True, f"'{k}' ({state}{sched}) would: {steps}. Nothing was run.",
                               evidence={"name": k, "steps": wf["steps"], "dry_run": True})

    def set_enabled(self, name: str, enabled: bool) -> OperatorOutcome:
        with self._lock:
            data, k, wf = self._get(name)
            if wf is None:
                return self._missing(name)
            wf["enabled"] = enabled
            self._save(data)
        return OperatorOutcome(True, f"Workflow '{k}' is {'on' if enabled else 'off'}.")

    def schedule(self, name: str, when: str) -> OperatorOutcome:
        sched = parse_schedule(when)
        if not sched:
            return OperatorOutcome(False, "When should it run - for example 'weekdays at 9' or 'every 30 minutes'?",
                                   needs="clarify")
        with self._lock:
            data, k, wf = self._get(name)
            if wf is None:
                return self._missing(name)
            wf["schedule"] = sched
            wf["last_run"] = max(wf.get("last_run", 0), self._clock())   # first run is the next slot, not now
            self._save(data)
        return OperatorOutcome(True, f"'{k}' will run {sched}.", evidence={"schedule": sched})

    def cancel_schedule(self, name: str = "") -> OperatorOutcome:
        with self._lock:
            data = self.load()
            names = [self._get(name)[1]] if name else [n for n, w in data.items() if w.get("schedule")]
            names = [n for n in names if n in data and data[n].get("schedule")]
            for n in names:
                data[n]["schedule"] = ""
            self._save(data)
        for n in names:
            ev = self._running.get(n)
            if ev:
                ev.set()
        if not names:
            return OperatorOutcome(True, "No workflow schedule to cancel.")
        return OperatorOutcome(True, f"Cancelled the schedule for {', '.join(names)}.")

    def list(self) -> OperatorOutcome:
        data = self.load()
        if not data:
            return OperatorOutcome(True, "No workflows saved yet.")
        parts = [f"{n} ({len(w['steps'])} steps{', ' + w['schedule'] if w.get('schedule') else ''}"
                 f"{'' if w.get('enabled', True) else ', off'})" for n, w in sorted(data.items())]
        return OperatorOutcome(True, "; ".join(parts), evidence={"count": len(data)})

    def run(self, name: str, dispatch: Optional[Callable] = None, wait: bool = False, override: str = "") -> OperatorOutcome:
        data, k, wf = self._get(name)
        if wf is None:
            return self._missing(name)
        steps = list(wf["steps"])
        if override:
            # one parameter can be swapped for this run only: the folder its steps work in
            folders = r"\b(?:downloads|documents|desktop|pictures|videos|music)\b"
            if not any(re.search(folders, s_, re.I) for s_ in steps):
                return OperatorOutcome(False, f"None of '{k}''s steps names a folder, so there's nothing to swap for "
                                              f"{override}. Its steps: " + "; ".join(steps), needs="clarify")
            steps = [re.sub(folders, override, s_, flags=re.I) for s_ in steps]
        if not wf.get("enabled", True):
            return OperatorOutcome(False, f"'{k}' is turned off - turn it on first.")
        dispatch = dispatch or self._dispatch
        if dispatch is None:
            return OperatorOutcome(False, "Workflows can only run while JARVIS is running.")
        if k in self._running:
            return OperatorOutcome(False, f"'{k}' is already running.")
        with self._lock:
            data = self.load()
            if k in data:
                data[k]["last_run"] = self._clock()
                self._save(data)
        stop = threading.Event()
        self._running[k] = stop
        t = threading.Thread(target=self._run_steps, args=(k, steps, dispatch, stop),
                             name=f"workflow-{k}", daemon=True)
        t.start()
        if wait:
            t.join()
        return OperatorOutcome(True, f"Running '{k}'{' with ' + override if override else ''}: {len(steps)} steps, one "
                                     "at a time; I'll stop at the first one that fails or needs you.",
                               evidence={"name": k, "steps": steps, "verified": None})

    def _run_steps(self, k: str, steps: list[str], dispatch: Callable, stop: threading.Event) -> None:
        try:
            for i, step in enumerate(steps, 1):
                if stop.is_set():
                    return
                fut = dispatch(step)
                if fut is None:
                    continue
                try:
                    res = fut.result(timeout=600)
                except Exception as e:
                    logger.info("workflow %s step %d (%s) failed: %s", k, i, step, e)
                    return
                state = getattr(res, "state", "")
                if state in STOP_STATES:
                    logger.info("workflow %s stopped at step %d (%s): %s", k, i, step, state)
                    return
        finally:
            self._running.pop(k, None)

    def cancel_running(self) -> int:
        n = 0
        for ev in list(self._running.values()):
            ev.set()
            n += 1
        return n

    # -- schedule loop ---------------------------------------------------------------------------------------
    def start(self, dispatch: Callable) -> None:
        self._dispatch = dispatch
        if self._thread and self._thread.is_alive():
            return
        import os
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return

        def loop():
            while True:
                try:
                    self.tick()
                except Exception as e:
                    logger.debug("workflow schedule tick failed: %s", e)
                time.sleep(30)

        self._thread = threading.Thread(target=loop, name="workflow-schedule", daemon=True)
        self._thread.start()

    def tick(self, now: Optional[datetime] = None) -> list[str]:
        now = now or datetime.fromtimestamp(self._clock())
        started = []
        for name, wf in self.load().items():
            if wf.get("enabled", True) and due(wf.get("schedule", ""), now, wf.get("last_run", 0)):
                if self.run(name).ok:
                    started.append(name)
        return started


_wf: Optional[Workflows] = None


def get_workflows() -> Workflows:
    global _wf
    if _wf is None:
        _wf = Workflows()
    return _wf


def set_workflows(w: Optional[Workflows]) -> None:
    global _wf
    _wf = w
