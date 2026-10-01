"""window.* primitives: resolve "the previous window", "my editor", "the YouTube tab's window", "the second Chrome
window" to one real window (or ask), then focus / set state / arrange / close it and verify the effect.

The tracker keeps a short foreground history (most recent first). JARVIS's own windows never enter it, so "go back
to my editor" means the editor the owner was using, not the assistant's panel.
"""
from __future__ import annotations

import os
import re
import threading
import time
from typing import Optional

from jarvis.core.operator.platform import Desktop, Monitor, get_desktop
from jarvis.core.operator.refs import BROWSER_PROCS, OperatorOutcome, WindowRef

# Spoken app names -> process names. Generic: one table, no per-sentence logic.
APP_PROCESSES: dict[str, tuple[str, ...]] = {
    "chrome": ("chrome.exe",), "google chrome": ("chrome.exe",), "edge": ("msedge.exe",),
    "microsoft edge": ("msedge.exe",), "firefox": ("firefox.exe",), "brave": ("brave.exe",), "opera": ("opera.exe",),
    "notepad": ("notepad.exe",), "notepad++": ("notepad++.exe",), "word": ("winword.exe",),
    "excel": ("excel.exe",), "powerpoint": ("powerpnt.exe",), "outlook": ("outlook.exe", "olk.exe"),
    "vs code": ("code.exe",), "vscode": ("code.exe",), "visual studio code": ("code.exe",), "code": ("code.exe",),
    "antigravity": ("antigravity.exe",), "cursor": ("cursor.exe",), "windsurf": ("windsurf.exe",),
    "pycharm": ("pycharm64.exe",), "intellij": ("idea64.exe",), "visual studio": ("devenv.exe",),
    "explorer": ("explorer.exe",), "file explorer": ("explorer.exe",), "files": ("explorer.exe",),
    "whatsapp": ("whatsapp.exe",), "telegram": ("telegram.exe",), "slack": ("slack.exe",),
    "teams": ("ms-teams.exe", "teams.exe"), "discord": ("discord.exe",), "spotify": ("spotify.exe",),
    "vlc": ("vlc.exe",), "terminal": ("windowsterminal.exe", "wt.exe"), "cmd": ("cmd.exe",),
    "command prompt": ("cmd.exe",), "powershell": ("powershell.exe", "pwsh.exe"), "settings": ("systemsettings.exe",),
    "task manager": ("taskmgr.exe",), "paint": ("mspaint.exe",), "calculator": ("calculatorapp.exe", "calc.exe"),
    "obsidian": ("obsidian.exe",), "sublime": ("sublime_text.exe",), "zoom": ("zoom.exe",),
}
# Words for a *kind* of window -> app family (see refs.app_family).
FAMILY_WORDS: dict[str, str] = {
    "browser": "browser", "web browser": "browser", "editor": "editor", "text editor": "editor",
    "code editor": "ide", "ide": "ide", "coding app": "ide", "code window": "ide", "media player": "media",
    "player": "media", "video": "media", "music": "media", "file manager": "files", "folder": "files",
    "chat": "chat", "messenger": "chat", "document": "editor", "doc": "editor", "notes": "editor",
}
_PREVIOUS = re.compile(r"\b(previous|last|other|back|prior|before|earlier|alt.?tab)\b")
_CURRENT = re.compile(r"^(this|current|active|the current|the active|this|it|focused|front)\b")
_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "1st": 1, "2nd": 2, "3rd": 3, "4th": 4,
             "last": -1, "other": 2}
_OWN_TITLES = ("jarvis edge", "jarvis hud", "jarvis dashboard", "jarvis console")
_FILLER = re.compile(r"\b(the|my|a|an|window|app|application|program|that|this|please|one|of|to|in)\b")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower().strip())


class WindowTracker:
    """Foreground history plus resolution and the window primitives."""

    def __init__(self, desktop: Optional[Desktop] = None, own_titles: tuple[str, ...] = _OWN_TITLES,
                 history_size: int = 30):
        self._desktop = desktop
        self._own = tuple(t.lower() for t in own_titles)
        self._size = history_size
        self.history: list[WindowRef] = []                # most recent first
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    @property
    def desktop(self) -> Desktop:
        return self._desktop or get_desktop()

    # -- history -------------------------------------------------------------------------------------------
    def is_own(self, ref: Optional[WindowRef]) -> bool:
        if not ref:
            return True
        if ref.pid and ref.pid == os.getpid():
            return True                                   # the HUD/panel lives in this process
        t = ref.title.lower()
        return any(t.startswith(o) for o in self._own)

    def observe(self) -> Optional[WindowRef]:
        """Record the current foreground window. Cheap; called per command and by the background poll."""
        try:
            fg = self.desktop.foreground()
        except Exception:
            return None
        if fg and not self.is_own(fg):
            with self._lock:
                if not self.history or self.history[0].hwnd != fg.hwnd or self.history[0].title != fg.title:
                    self.history = [fg] + [w for w in self.history if w.hwnd != fg.hwnd][: self._size - 1]
                else:
                    self.history[0].seen_at = time.time()
        return fg

    def start(self, interval: float = 0.35) -> None:
        """Background foreground poll (one Win32 call per tick; no screenshots, no UIA)."""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()

        def loop():
            while not self._stop.wait(interval):
                self.observe()

        self._thread = threading.Thread(target=loop, name="window-history", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def current(self) -> Optional[WindowRef]:
        """The window the owner is working in: the foreground one, or the last non-JARVIS one if JARVIS is in front."""
        fg = self.observe()
        if fg and not self.is_own(fg):
            return fg
        return self._alive(self.history[0]) if self.history else None

    def previous(self) -> Optional[WindowRef]:
        cur = self.current()
        for w in self.history:
            if cur and w.hwnd == cur.hwnd:
                continue
            if self._alive(w):
                return w
        return None

    def _alive(self, w: WindowRef) -> Optional[WindowRef]:
        live = {x.hwnd: x for x in self.desktop.list_windows()}
        x = live.get(w.hwnd)
        return x if x and x.process == w.process else None

    # -- resolution ----------------------------------------------------------------------------------------
    def resolve(self, query: str = "", app: str = "", title: str = "", family: str = "") -> OperatorOutcome:
        """One window for a description, or a clarify outcome with the candidates. Never a guess between equals."""
        q = _norm(query)
        if not (q or app or title or family) or _CURRENT.match(q):
            cur = self.current()
            return OperatorOutcome(bool(cur), cur.display_name if cur else "No window is open.", resource=cur)
        if q and _PREVIOUS.search(q) and not app and not title and not self._mentions_app(q):
            prev = self.previous()
            return OperatorOutcome(bool(prev), prev.display_name if prev else "I don't have an earlier window to go back to.",
                                   resource=prev, needs="" if prev else "clarify")
        windows = [w for w in self.desktop.list_windows() if not self.is_own(w)]
        ordinal = 0
        for word, n in _ORDINALS.items():
            if re.search(rf"\b{re.escape(word)}\b", q):
                ordinal = n
                q = re.sub(rf"\b{re.escape(word)}\b", " ", q)
        procs = self._processes(app or q)
        fam = family or self._family(q)
        if procs:
            pool = [w for w in windows if w.process in procs]
            if title or self._title_words(q, app or q):
                tw = title or self._title_words(q, app or q)
                narrowed = [w for w in pool if tw in w.title.lower()]
                pool = narrowed or pool
        elif title:
            pool = [w for w in windows if title.lower() in w.title.lower()]
        elif fam:
            pool = [w for w in windows if w.family == fam or (fam == "browser" and w.process in BROWSER_PROCS)]
            if not pool and fam == "editor":
                pool = [w for w in windows if w.family == "ide"]     # "my editor" with only an IDE open
        else:
            words = _norm(_FILLER.sub(" ", q))
            pool = [w for w in windows if words and words in w.title.lower()] if len(words) >= 3 else []
            if not pool and words:
                pool = [w for w in windows if words.split()[0] in w.process] if words.split() else []
        if not pool:
            what = app or title or query or family
            return OperatorOutcome(False, f"I can't see a {what} window open.", needs="", evidence={"query": what})
        ranked = self._by_recency(pool)
        if ordinal:
            idx = ordinal - 1 if ordinal > 0 else len(ranked) - 1
            if 0 <= idx < len(ranked):
                return OperatorOutcome(True, ranked[idx].display_name, resource=ranked[idx])
            return OperatorOutcome(False, f"There are only {len(ranked)} such windows.", needs="clarify",
                                   candidates=ranked)
        recent = [w for w in ranked if any(h.hwnd == w.hwnd for h in self.history)]
        if len(ranked) == 1 or recent:
            pick = recent[0] if recent else ranked[0]
            return OperatorOutcome(True, pick.display_name, resource=pick)
        return OperatorOutcome(False, "Which one? " + "; ".join(f"{i + 1}. {w.title}" for i, w in enumerate(ranked[:5])),
                               needs="clarify", candidates=ranked)

    def _mentions_app(self, q: str) -> bool:
        return bool(self._processes(q)) or bool(self._family(q))

    @staticmethod
    def _processes(text: str) -> tuple[str, ...]:
        t = _norm(text)
        if t.endswith(".exe"):
            return (t,)
        best = ""
        for name in APP_PROCESSES:
            if re.search(rf"(?<![\w+]){re.escape(name)}(?![\w+])", t) and len(name) > len(best):
                best = name
        return APP_PROCESSES.get(best, ())

    @staticmethod
    def _family(text: str) -> str:
        t = _norm(text)
        best = ""
        for word in FAMILY_WORDS:
            if re.search(rf"\b{re.escape(word)}s?\b", t) and len(word) > len(best):
                best = word
        return FAMILY_WORDS.get(best, "")

    @staticmethod
    def _title_words(q: str, app_text: str) -> str:
        """'the chrome window with youtube' -> 'youtube' (what the title should contain)."""
        m = re.search(r"\b(?:with|showing|containing|that has|named|called|titled|for|on)\s+(.+)$", q)
        return _norm(_FILLER.sub(" ", m.group(1))) if m else ""

    def _by_recency(self, pool: list[WindowRef]) -> list[WindowRef]:
        rank = {w.hwnd: i for i, w in enumerate(self.history)}
        return sorted(pool, key=lambda w: rank.get(w.hwnd, 10_000))

    # -- primitives ----------------------------------------------------------------------------------------
    def focus(self, target: WindowRef) -> OperatorOutcome:
        d = self.desktop
        if not d.focus(target.hwnd):
            return OperatorOutcome(False, f"I couldn't bring {target.display_name} to the front.", resource=target)
        ok = d.wait_until(lambda: (d.foreground() or WindowRef(resource_id="", resource_type="", display_name="",
                                                              canonical_identifier="")).hwnd == target.hwnd)
        self.observe()
        return OperatorOutcome(ok, f"Switched to {target.display_name}." if ok else
                               f"{target.display_name} didn't come to the front.", resource=target,
                               evidence={"foreground_verified": ok})

    def set_state(self, target: WindowRef, state: str) -> OperatorOutcome:
        state = {"maximize": "maximized", "max": "maximized", "full": "maximized", "minimise": "minimized",
                 "minimize": "minimized", "min": "minimized", "restore": "normal", "unminimize": "normal",
                 "normal": "normal", "fullscreen": "fullscreen", "full screen": "fullscreen"}.get(state, state)
        d = self.desktop
        d.set_window_state(target.hwnd, state)
        ok = state == "fullscreen" or d.wait_until(lambda: d.window_state(target.hwnd) == state)
        verb = {"maximized": "Maximised", "minimized": "Minimised", "normal": "Restored",
                "fullscreen": "Full screen:"}.get(state, state)
        return OperatorOutcome(ok, f"{verb} {target.display_name}." if ok else
                               f"{target.display_name} didn't change to {state}.", resource=target,
                               evidence={"state": d.window_state(target.hwnd)})

    def close(self, target: WindowRef) -> OperatorOutcome:
        d = self.desktop
        d.close_window(target.hwnd)
        gone = d.wait_until(lambda: all(w.hwnd != target.hwnd for w in d.list_windows()), timeout=1.5)
        return OperatorOutcome(gone, f"Closed {target.display_name}." if gone else
                               f"{target.display_name} is asking something before it closes.", resource=target,
                               needs="" if gone else "user")

    def arrange(self, targets: list[WindowRef], layout: str) -> OperatorOutcome:
        """left / right / top / bottom / side_by_side / stack / quadrants / center / next_monitor / previous_monitor."""
        d = self.desktop
        mons = d.monitors()
        if not targets:
            return OperatorOutcome(False, "Which window?", needs="clarify")
        layout = layout.replace(" ", "_").replace("-", "_")
        if layout in ("next_monitor", "other_monitor", "previous_monitor", "second_monitor"):
            if len(mons) < 2:
                return OperatorOutcome(False, "Only one monitor is connected.")
            w = targets[0]
            cur = self._monitor_of(w, mons)
            step = -1 if layout == "previous_monitor" else 1
            dst = mons[(cur.index + step) % len(mons)]
            l, t, r, b = d.window_rect(w.hwnd)
            nl, nt = dst.left + max(0, l - cur.left), dst.top + max(0, t - cur.top)
            rect = (nl, nt, min(dst.right, nl + (r - l)), min(dst.bottom, nt + (b - t)))
            d.move_window(w.hwnd, rect)
            return self._verify_rects([(w, rect)], f"Moved {w.display_name} to monitor {dst.index + 1}.")
        mon = self._monitor_of(targets[0], mons)
        L, T, W, H = mon.left, mon.top, mon.width, mon.height
        halves = {
            "left": (L, T, L + W // 2, T + H), "right": (L + W // 2, T, L + W, T + H),
            "top": (L, T, L + W, T + H // 2), "bottom": (L, T + H // 2, L + W, T + H),
            "top_left": (L, T, L + W // 2, T + H // 2), "top_right": (L + W // 2, T, L + W, T + H // 2),
            "bottom_left": (L, T + H // 2, L + W // 2, T + H), "bottom_right": (L + W // 2, T + H // 2, L + W, T + H),
            "center": (L + W // 6, T + H // 8, L + W - W // 6, T + H - H // 8),
        }
        plan: list[tuple[WindowRef, tuple[int, int, int, int]]] = []
        if layout in halves:
            plan = [(targets[0], halves[layout])]
        elif layout in ("side_by_side", "split", "columns"):
            n = len(targets)
            plan = [(w, (L + i * W // n, T, L + (i + 1) * W // n, T + H)) for i, w in enumerate(targets)]
        elif layout in ("stack", "rows", "top_and_bottom"):
            n = len(targets)
            plan = [(w, (L, T + i * H // n, L + W, T + (i + 1) * H // n)) for i, w in enumerate(targets)]
        elif layout in ("quadrants", "grid", "four"):
            keys = ("top_left", "top_right", "bottom_left", "bottom_right")
            plan = [(w, halves[k]) for w, k in zip(targets, keys)]
        else:
            return OperatorOutcome(False, f"I don't know the layout '{layout}'.", needs="clarify")
        for w, rect in plan:
            d.move_window(w.hwnd, rect)
        names = " and ".join(w.display_name for w, _ in plan)
        return self._verify_rects(plan, f"Arranged {names} ({layout.replace('_', ' ')}).")

    def _verify_rects(self, plan, message: str) -> OperatorOutcome:
        d = self.desktop
        off = []
        for w, rect in plan:
            got = d.window_rect(w.hwnd)
            # Windows adds invisible resize borders (~8px); a placement within tolerance is the placement asked for.
            if any(abs(a - b) > 16 for a, b in zip(got, rect)):
                off.append(w.display_name)
        ok = not off
        return OperatorOutcome(ok, message if ok else f"{', '.join(off)} didn't move where asked.",
                               resource=plan[0][0], evidence={"placed": len(plan) - len(off)})

    def _monitor_of(self, w: WindowRef, mons: list[Monitor]) -> Monitor:
        l, t, r, b = self.desktop.window_rect(w.hwnd)
        cx, cy = (l + r) // 2, (t + b) // 2
        for m in mons:
            if m.left <= cx < m.right and m.top <= cy < m.bottom:
                return m
        return next((m for m in mons if m.primary), mons[0])

    def list(self) -> list[WindowRef]:
        return [w for w in self.desktop.list_windows() if not self.is_own(w)]


_tracker: Optional[WindowTracker] = None


def get_window_tracker() -> WindowTracker:
    global _tracker
    if _tracker is None:
        _tracker = WindowTracker()
    return _tracker


def set_window_tracker(tracker: Optional[WindowTracker]) -> None:
    global _tracker
    _tracker = tracker
