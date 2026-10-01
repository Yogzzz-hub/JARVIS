"""watch: scoped, temporary, cancelable condition -> action loops ("skip the ad whenever it lets you", "tell me when
the download finishes", "let me know when the IDE is done generating").

One daemon thread serves every watch; each has an interval, a deadline and a cap on actions, ends itself when its
scope ends (the video tab closes or changes, the download appears) and can be cancelled by kind or id. Nothing is
blocked or intercepted: a watch only observes and uses the same primitives the owner could ask for.
"""
from __future__ import annotations

import itertools
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from jarvis.core.operator.refs import DownloadResource, OperatorOutcome

logger = logging.getLogger("jarvis.operator.watch")
_ids = itertools.count(1)


@dataclass
class Watch:
    kind: str
    description: str
    check: Callable[[], Optional[str]]        # returns: None (keep going) | "act" | "done"
    act: Callable[[], Optional[str]] = lambda: None   # returns a message to announce, if any
    interval: float = 1.0
    deadline: float = 0.0
    max_actions: int = 50
    id: int = field(default_factory=lambda: next(_ids))
    actions: int = 0
    next_at: float = 0.0
    ended: str = ""
    messages: list[str] = field(default_factory=list)


class WatchManager:
    def __init__(self, notify: Optional[Callable[[str], None]] = None, clock=time.monotonic):
        self._w: dict[int, Watch] = {}
        self._lock = threading.Lock()
        self._notify = notify
        self._clock = clock
        self._thread: Optional[threading.Thread] = None
        self._wake = threading.Event()
        self._stop = False
        # Re-runs the owner's own deferred command ("when X, open it") through CommandService - fresh route,
        # fresh policy, fresh task-scope grant. Set by the runtime; None means "announce only".
        self.dispatch: Optional[Callable[[str], None]] = None

    def add(self, w: Watch, timeout_s: float = 1800.0) -> Watch:
        now = self._clock()
        w.deadline = w.deadline or now + timeout_s
        w.next_at = now
        with self._lock:
            # one watch per kind+description: asking twice extends instead of duplicating
            for old in self._w.values():
                if old.kind == w.kind and old.description == w.description and not old.ended:
                    old.deadline = w.deadline
                    return old
            self._w[w.id] = w
        self._ensure_thread()
        return w

    def cancel(self, kind: str = "", wid: int = 0) -> int:
        n = 0
        with self._lock:
            for w in list(self._w.values()):
                if (wid and w.id == wid) or (kind and w.kind == kind) or (not kind and not wid):
                    w.ended = "cancelled"
                    self._w.pop(w.id, None)
                    n += 1
        return n

    def active(self) -> list[Watch]:
        with self._lock:
            return [w for w in self._w.values() if not w.ended]

    def tick(self) -> list[str]:
        """Run every due watch once. The thread calls this; tests call it directly."""
        now = self._clock()
        said: list[str] = []
        for w in self.active():
            if now < w.next_at:
                continue
            w.next_at = now + w.interval
            if now >= w.deadline:
                self._end(w, "timeout")
                continue
            try:
                verdict = w.check()
                if verdict == "act":
                    msg = w.act()
                    w.actions += 1
                    if msg:
                        w.messages.append(msg)
                        said.append(msg)
                    if w.actions >= w.max_actions:
                        self._end(w, "max_actions")
                elif verdict == "done_silent":
                    self._end(w, "scope_ended")
                elif verdict == "done":
                    msg = w.act()
                    if msg:
                        w.messages.append(msg)
                        said.append(msg)
                    self._end(w, "done")
            except Exception as e:
                logger.debug("watch %s failed: %s", w.id, e)
                self._end(w, f"error: {e}")
        if self._notify:
            for m in said:
                try:
                    self._notify(m)
                except Exception:
                    pass
        return said

    def _end(self, w: Watch, why: str) -> None:
        w.ended = why
        with self._lock:
            self._w.pop(w.id, None)

    def _ensure_thread(self) -> None:
        if self._thread and self._thread.is_alive():
            self._wake.set()
            return
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return                       # tests drive tick() themselves

        def loop():
            while not self._stop:
                if not self.active():
                    self._wake.wait(30)
                    self._wake.clear()
                    continue
                self.tick()
                nxt = min((w.next_at for w in self.active()), default=self._clock() + 1)
                self._wake.wait(max(0.05, min(1.0, nxt - self._clock())))
                self._wake.clear()

        self._thread = threading.Thread(target=loop, name="operator-watch", daemon=True)
        self._thread.start()

    # -- ready-made watches -----------------------------------------------------------------------------------
    def skip_ads(self, browser, timeout_s: float = 3600.0) -> OperatorOutcome:
        """Click the player's own Skip button when it appears, for the video in the current tab only."""
        b = browser.backend
        if not b.dom:
            return OperatorOutcome(False, "I need page access to see the Skip button; open the video in the JARVIS "
                                          "browser profile.", needs="user")
        tab = b.active()
        if not tab:
            return OperatorOutcome(False, "No video tab is open.")
        scope_url = tab.url

        def alive_tab():
            return next((t for t in b.tabs() if t.metadata.get("id") == tab.metadata.get("id")), None)

        def check():
            t = alive_tab()
            if t is None or t.url.split("&")[0] != scope_url.split("&")[0]:
                return "stop"
            st = b.run(t, "media_state")
            return "act" if st and st.get("ad") else None

        skipped = {"n": 0}

        def act():
            r = b.run(alive_tab(), "skip_ad") or {}
            if r.get("skipped"):
                skipped["n"] += 1           # quiet: the owner asked for ads to go away, not for a commentary
            return None

        def wrapped_check():
            v = check()
            if v == "stop":
                raise StopIteration("scope ended")
            return v

        w = Watch(kind="skip_ad", description=scope_url, check=self._ends_quietly(wrapped_check), act=act,
                  interval=0.75, max_actions=200)
        self.add(w, timeout_s)
        return OperatorOutcome(True, "I'll skip ads on this video as soon as the Skip button shows.",
                               evidence={"watch_id": w.id, "scope": scope_url})

    def _ends_quietly(self, fn):
        def run():
            try:
                return fn()
            except StopIteration:
                return "done_silent"
        return run

    def download_done(self, folder: str, resources=None, timeout_s: float = 1800.0) -> OperatorOutcome:
        folder_p = Path(folder)
        start = {p.name for p in folder_p.glob("*")} if folder_p.exists() else set()
        found: dict = {}

        def check():
            if not folder_p.exists():
                return None
            partial = {".crdownload", ".part", ".tmp", ".download"}
            for p in folder_p.iterdir():
                if p.name not in start and p.suffix.lower() not in partial and p.is_file():
                    found["p"] = p
                    return "done"
            return None

        def act():
            p = found.get("p")
            if not p:
                return None
            ref = DownloadResource(resource_id=f"dl:{p}", path=str(p), filename=p.name)
            if resources is not None:
                resources.record(ref)
            return f"Download finished: {p.name}."

        w = Watch(kind="download", description=str(folder_p), check=check, act=act, interval=1.0, max_actions=1)
        self.add(w, timeout_s)
        return OperatorOutcome(True, "I'll tell you when the download finishes.", evidence={"watch_id": w.id})

    def until(self, kind: str, description: str, predicate: Callable[[], bool], message: str,
              interval: float = 1.0, timeout_s: float = 900.0) -> OperatorOutcome:
        w = Watch(kind=kind, description=description, check=lambda: "done" if predicate() else None,
                  act=lambda: message, interval=interval, max_actions=1)
        self.add(w, timeout_s)
        return OperatorOutcome(True, f"I'll let you know when {description}.", evidence={"watch_id": w.id})

    def when(self, kind: str, description: str, predicate: Callable[[], bool], then: str = "", message: str = "",
             interval: float = 2.0, timeout_s: float = 3600.0,
             also_notify: Optional[Callable[[str], None]] = None) -> OperatorOutcome:
        """Conditional follow-up: when ``predicate`` turns true, announce it and (if given) run ``then`` - the
        owner's own words captured when they asked - as a new command. Nothing runs early; on timeout nothing runs."""
        said = message or f"{description[:1].upper()}{description[1:]}."

        def act():
            if also_notify is not None:
                try:
                    also_notify(said)
                except Exception as e:
                    logger.info("watch notification failed: %s", e)
            if then and self.dispatch is not None:
                try:
                    self.dispatch(then)
                except Exception as e:
                    logger.info("watch follow-up %r failed: %s", then, e)
                    return f"{said} I couldn't start '{then}': {e}"
                return f"{said} Now: {then}."
            return said

        def check():
            v = predicate()                      # True -> fire; "done_silent" -> scope over, nothing to say
            return v if isinstance(v, str) else ("done" if v else None)

        w = Watch(kind=kind, description=description, check=check, act=act, interval=interval, max_actions=1)
        self.add(w, timeout_s)
        tail = f", then {then}" if then else ""
        return OperatorOutcome(True, f"Watching: when {description}{tail}.", evidence={"watch_id": w.id, "then": then})


_mgr: Optional[WatchManager] = None


def get_watch_manager() -> WatchManager:
    global _mgr
    if _mgr is None:
        _mgr = WatchManager()
    return _mgr


def set_watch_manager(m: Optional[WatchManager]) -> None:
    global _mgr
    _mgr = m
