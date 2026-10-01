"""Timed commands and event triggers: the owner's own commands, run later or whenever something happens.

    "in 10 minutes open spotify"                  -> one-shot at now + 10 min
    "at 7 pm set the volume to 30"                -> one-shot at the next 19:00
    "whenever I open VS Code, open Chrome too"    -> trigger: app_opened(vs code) -> "open chrome"
    "every time my phone connects, bring the new screenshots here"
    "whenever battery drops below 20 percent, lower the brightness"

Nothing here executes anything itself. When a command is due, its text is re-dispatched through CommandService
exactly as if the owner had said it again - fresh route, policy, confirmation tickets and task-scope grant - so a
consequential command (lock, delete, send) still asks before it runs. Triggers fire on the *edge* (closed -> open,
disconnected -> connected, above -> below), at most once per cooldown, so a condition that stays true does not
repeat its command. One-shots that were missed while JARVIS was off are reported, not run late.

    jarvis/db/automations.json
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from jarvis.core.operator.refs import OperatorOutcome

logger = logging.getLogger("jarvis.operator.automations")

TRIGGERS = ("app_opened", "app_closed", "phone_connected", "phone_disconnected", "battery_below", "battery_above",
            "download_done")
MISSED_GRACE_S = 600          # a one-shot more than 10 min overdue at startup is reported missed, not run
COOLDOWN_S = 60.0
_UNITS = {"second": 1, "sec": 1, "minute": 60, "min": 60, "hour": 3600, "hr": 3600}
_WORD_NUM = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "ten": 10, "fifteen": 15,
             "twenty": 20, "thirty": 30, "forty five": 45, "half an": 0.5, "a couple of": 2, "few": 3}


def _default_path() -> Path:
    return Path(__file__).resolve().parents[2] / "db" / "automations.json"


def parse_when(text: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """'in 10 minutes' / 'in half an hour' / 'at 7 pm' / 'at 18:30' / 'tomorrow at 9' -> a datetime in the future."""
    now = now or datetime.now()
    t = (text or "").lower().strip()
    m = re.search(r"\bin\s+(?P<n>\d+(?:\.\d+)?|" + "|".join(sorted(map(re.escape, _WORD_NUM), key=len, reverse=True)) +
                  r")\s*(?P<u>seconds?|secs?|minutes?|mins?|hours?|hrs?)\b", t)
    if m:
        n = m.group("n")
        val = float(n) if re.match(r"\d", n) else _WORD_NUM[n]
        unit = next(v for k, v in _UNITS.items() if m.group("u").startswith(k))
        secs = val * unit
        return now + timedelta(seconds=secs) if 0 < secs <= 7 * 86400 else None
    m = re.search(r"\b(?:at|by)\s+(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ap>am|pm|a\.m\.|p\.m\.)?(?!\s*(?:%|percent))\b", t)
    if not m:
        if re.search(r"\b(?:at\s+)?noon\b", t):
            h, mi = 12, 0
        elif re.search(r"\b(?:at\s+)?midnight\b", t):
            h, mi = 0, 0
        else:
            return None
    else:
        h, mi = int(m.group("h")), int(m.group("m") or 0)
        ap = (m.group("ap") or "").replace(".", "")
        if ap == "pm" and h < 12:
            h += 12
        elif ap == "am" and h == 12:
            h = 0
        elif not ap and h < 7 and not m.group("m"):
            h += 12                               # "at 5" said in the day means 5 pm, not 5 am
    if h > 23 or mi > 59:
        return None
    when = now.replace(hour=h, minute=mi, second=0, microsecond=0)
    if re.search(r"\btomorrow\b", t) or when <= now:
        when += timedelta(days=1)
    return when


class Automations:
    def __init__(self, path: Optional[Path] = None, clock=time.time, probes: Optional[dict] = None):
        self.path = Path(path) if path else _default_path()
        self._clock = clock
        self._lock = threading.Lock()
        self._dispatch: Optional[Callable] = None
        self._notify: Optional[Callable[[str], None]] = None
        self._thread: Optional[threading.Thread] = None
        self.probes: dict[str, Callable] = probes or {}
        self._state: dict[str, bool] = {}          # last observed truth per trigger (edge detection)

    # -- storage ---------------------------------------------------------------------------------------------
    def load(self) -> list[dict]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def _save(self, items: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(items, indent=1), encoding="utf-8")

    # -- create ----------------------------------------------------------------------------------------------
    def run_at(self, command: str, when_text: str) -> OperatorOutcome:
        command = (command or "").strip(" ,.")
        if not command:
            return OperatorOutcome(False, "What should I do then?", needs="clarify")
        when = parse_when(when_text, datetime.fromtimestamp(self._clock()))
        if when is None:
            return OperatorOutcome(False, "When? Say e.g. 'in 10 minutes' or 'at 7 pm'.", needs="clarify")
        item = {"id": uuid.uuid4().hex[:8], "kind": "at", "command": command, "due": when.timestamp(),
                "created": self._clock(), "enabled": True}
        with self._lock:
            items = self.load()
            items.append(item)
            self._save(items)
        return OperatorOutcome(True, f"At {when.strftime('%I:%M %p').lstrip('0')}"
                                     f"{' tomorrow' if when.date() > datetime.fromtimestamp(self._clock()).date() else ''}"
                                     f" I'll run \"{command}\" (anything that needs your OK will still ask).",
                               evidence={"id": item["id"], "due": item["due"]})

    def add_trigger(self, condition: str, command: str, subject: str = "", threshold: Optional[float] = None
                    ) -> OperatorOutcome:
        command = (command or "").strip(" ,.")
        if condition not in TRIGGERS:
            return OperatorOutcome(False, f"I can't watch for that yet - I can react to: {', '.join(TRIGGERS)}.",
                                   needs="clarify")
        if not command:
            return OperatorOutcome(False, "What should I do when it happens?", needs="clarify")
        if condition.startswith("battery") and threshold is None:
            return OperatorOutcome(False, "At what battery percentage?", needs="clarify")
        item = {"id": uuid.uuid4().hex[:8], "kind": "trigger", "condition": condition, "subject": subject.strip(),
                "threshold": threshold, "command": command, "created": self._clock(), "enabled": True,
                "fires": 0, "last_fired": 0}
        with self._lock:
            items = self.load()
            dup = next((i for i in items if i.get("kind") == "trigger" and i["condition"] == condition
                        and i.get("subject") == item["subject"] and i["command"].lower() == command.lower()), None)
            if dup:
                return OperatorOutcome(True, f"That automation already exists ({self.describe(dup)}).",
                                       evidence={"id": dup["id"]})
            items.append(item)
            self._save(items)
        return OperatorOutcome(True, f"Automation on: {self.describe(item)}. Say 'list my automations' to see them.",
                               evidence={"id": item["id"]})

    @staticmethod
    def describe(i: dict) -> str:
        if i.get("kind") == "at":
            return f"at {datetime.fromtimestamp(i['due']).strftime('%a %I:%M %p')} -> \"{i['command']}\""
        c, subj, thr = i["condition"], i.get("subject") or "the app", i.get("threshold")
        level = f"{thr:.0f}%" if thr is not None else "?"
        what = {"app_opened": f"when {subj} opens", "app_closed": f"when {subj} closes",
                "phone_connected": "when the phone connects", "phone_disconnected": "when the phone disconnects",
                "battery_below": f"when battery drops below {level}", "battery_above": f"when battery rises above {level}",
                "download_done": "when a download finishes"}.get(c, c.replace("_", " "))
        return f"{what} -> \"{i['command']}\""

    # -- list / cancel ---------------------------------------------------------------------------------------
    def list(self) -> OperatorOutcome:
        items = [i for i in self.load() if i.get("enabled", True)]
        if not items:
            return OperatorOutcome(True, "No automations or scheduled commands.")
        return OperatorOutcome(True, "; ".join(f"{n}. {self.describe(i)}" for n, i in enumerate(items, 1)),
                               evidence={"count": len(items)})

    def cancel(self, ref: str = "") -> OperatorOutcome:
        ref = re.sub(r"\b(?:the|my|automation|trigger|scheduled|command|rule|one)\b", " ", (ref or "").lower()).strip()
        with self._lock:
            items = self.load()
            if not items:
                return OperatorOutcome(True, "There's nothing scheduled.")
            if ref.isdigit() and 1 <= int(ref) <= len(items):
                hit = [items[int(ref) - 1]]
            elif ref in ("", "last", "latest"):
                hit = [max(items, key=lambda i: i.get("created", 0))] if (ref or len(items) == 1) else []
            else:
                hit = [i for i in items if ref in (i.get("command", "") + " " + i.get("subject", "")).lower()]
            if not hit:
                return OperatorOutcome(False, "Which one? " + self.list().message, needs="clarify")
            if len(hit) > 1:
                return OperatorOutcome(False, "More than one matches: " + "; ".join(self.describe(i) for i in hit),
                                       needs="clarify")
            items = [i for i in items if i["id"] != hit[0]["id"]]
            self._save(items)
        return OperatorOutcome(True, f"Removed: {self.describe(hit[0])}.")

    # -- running ---------------------------------------------------------------------------------------------
    def start(self, dispatch: Callable, notify: Optional[Callable[[str], None]] = None) -> None:
        self._dispatch, self._notify = dispatch, notify
        self._report_missed()
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
                    logger.debug("automation tick failed: %s", e)
                time.sleep(5)

        self._thread = threading.Thread(target=loop, name="automations", daemon=True)
        self._thread.start()

    def _report_missed(self) -> None:
        now = self._clock()
        with self._lock:
            items = self.load()
            missed = [i for i in items if i.get("kind") == "at" and i["due"] < now - MISSED_GRACE_S]
            if not missed:
                return
            self._save([i for i in items if i not in missed])
        if self._notify:
            self._notify("While I was off I missed: " + "; ".join(i["command"] for i in missed) + ". Nothing was run late.")

    def tick(self) -> list[str]:
        """Run due one-shots and edge-triggered automations once. Returns the commands dispatched."""
        now = self._clock()
        fired: list[str] = []
        with self._lock:
            items = self.load()
            due = [i for i in items if i.get("kind") == "at" and i.get("enabled", True) and i["due"] <= now]
            if due:
                self._save([i for i in items if i not in due])
        for i in due:
            fired.append(self._fire(i))
        for i in [i for i in self.load() if i.get("kind") == "trigger" and i.get("enabled", True)]:
            probe = self.probes.get(i["condition"])
            if probe is None:
                continue
            try:
                now_true = bool(probe(i.get("subject", ""), i.get("threshold")))
            except Exception as e:
                logger.debug("probe %s failed: %s", i["condition"], e)
                continue
            was = self._state.get(i["id"])
            self._state[i["id"]] = now_true
            if was is None:
                continue                                  # first observation is the baseline, never an event
            if now_true and not was and now - i.get("last_fired", 0) >= COOLDOWN_S:
                fired.append(self._fire(i))
                with self._lock:
                    items = self.load()
                    for j in items:
                        if j["id"] == i["id"]:
                            j["fires"] = j.get("fires", 0) + 1
                            j["last_fired"] = now
                    self._save(items)
        return [f for f in fired if f]

    def _fire(self, item: dict) -> str:
        if self._notify:
            try:
                self._notify(f"Running your automation: {item['command']}.")
            except Exception:
                pass
        if self._dispatch is None:
            return ""
        try:
            self._dispatch(item["command"])
        except Exception as e:
            logger.info("automation %s failed to start: %s", item["id"], e)
            return ""
        return item["command"]


def default_probes(tracker=None, device=None, downloads=None) -> dict[str, Callable]:
    """Observers for the live PC / phone. Each returns the current truth of its condition."""
    def app_open(subject, _t):
        from jarvis.core.operator.windows import get_window_tracker
        tr = tracker or get_window_tracker()
        return bool(subject) and tr.resolve(query=subject).ok

    def phone_ok(_s, _t):
        from jarvis.core.operator.device import get_device_operator
        return (device or get_device_operator()).ready().ok

    def battery(_s, _t):
        import psutil
        b = getattr(psutil, "sensors_battery", lambda: None)()
        return b.percent if b else None

    seen: dict[str, set] = {}

    def download_done(_s, _t):
        from jarvis.core.operator.files import downloads_dir
        folder = Path(downloads) if downloads else downloads_dir()
        partial = {".crdownload", ".part", ".tmp", ".download"}
        names = {p.name for p in folder.glob("*") if p.is_file() and p.suffix.lower() not in partial} if folder.exists() else set()
        prev = seen.setdefault("d", names)
        seen["d"] = names
        return bool(names - prev)

    return {"app_opened": app_open, "app_closed": lambda s, t: not app_open(s, t),
            "phone_connected": phone_ok, "phone_disconnected": lambda s, t: not phone_ok(s, t),
            "battery_below": lambda s, t: (lambda v: v is not None and t is not None and v < t)(battery(s, t)),
            "battery_above": lambda s, t: (lambda v: v is not None and t is not None and v > t)(battery(s, t)),
            "download_done": download_done}


_auto: Optional[Automations] = None


def get_automations() -> Automations:
    global _auto
    if _auto is None:
        _auto = Automations(probes=default_probes())
    return _auto


def set_automations(a: Optional[Automations]) -> None:
    global _auto
    _auto = a
