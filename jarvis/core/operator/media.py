"""media.* primitives: play / pause / seek / speed / volume / mute / captions / next / skip-ad over the media the
owner means - the video in the browser tab (page media element, verified by reading its state back), else the
system media session (media keys; the effect can't be read back, and the outcome says so)."""
from __future__ import annotations

import re
from typing import Optional

from jarvis.core.operator.browser import BrowserOperator
from jarvis.core.operator.platform import Desktop, get_desktop, parse_chord
from jarvis.core.operator.refs import MediaResourceRef, OperatorOutcome
from jarvis.core.operator.resources import OperatorResources, get_resources

OPS = ("play", "pause", "toggle", "seek_to", "seek_by", "rate", "mute", "unmute", "volume", "restart", "next",
       "previous", "captions", "fullscreen", "skip_ad", "loop", "state")
_MEDIA_KEYS = {"play": "playpause", "pause": "playpause", "toggle": "playpause", "next": "nexttrack",
               "previous": "prevtrack", "mute": "volumemute", "unmute": "volumemute"}
# Page-level keys of the common players (YouTube and most HTML5 players follow them).
_PLAYER_KEYS = {"captions": "c", "fullscreen": "f", "next": "shift+n", "previous": "shift+p"}


def parse_seconds(text: str) -> Optional[float]:
    """'1:30' -> 90, '2 minutes' -> 120, '45 sec' -> 45, '1 hour 5 minutes' -> 3900, '10' -> 10."""
    t = (text or "").lower().strip()
    m = re.fullmatch(r"(?:(\d+):)?(\d{1,2}):(\d{2})", t)
    if m:
        h, mi, s = int(m.group(1) or 0), int(m.group(2)), int(m.group(3))
        return h * 3600 + mi * 60 + s
    total, found = 0.0, False
    for num, unit in re.findall(r"(\d+(?:\.\d+)?|a|an|half(?: a)?)\s*(hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)\b", t):
        n = {"a": 1.0, "an": 1.0, "half": 0.5, "half a": 0.5}.get(num) or float(num)
        total += n * (3600 if unit.startswith("h") else 60 if unit.startswith("m") else 1)
        found = True
    if found:
        return total
    m = re.fullmatch(r"(\d+(?:\.\d+)?)", t)
    return float(m.group(1)) if m else None


class MediaOperator:
    def __init__(self, browser: Optional[BrowserOperator] = None, desktop: Optional[Desktop] = None,
                 resources: Optional[OperatorResources] = None):
        self.browser = browser or BrowserOperator()
        self._desktop = desktop
        self._res = resources

    @property
    def desktop(self) -> Desktop:
        return self._desktop or get_desktop()

    @property
    def resources(self) -> OperatorResources:
        return self._res or get_resources()

    def _page(self):
        b = self.browser.backend
        if not b.dom:
            return None, None
        tab = b.active()
        if not tab:
            return None, None
        try:
            state = b.run(tab, "media_state")
        except Exception:
            state = None
        if state is None:
            # the media may be in another tab ("pause the YouTube video" while reading docs)
            for t in b.tabs():
                try:
                    st = b.run(t, "media_state")
                except Exception:
                    st = None
                if st:
                    return t, st
            return None, None
        return tab, state

    def act(self, op: str, value: float | None = None) -> OperatorOutcome:
        if op not in OPS:
            return OperatorOutcome(False, f"I can't '{op}' media.", needs="clarify")
        tab, state = self._page()
        if tab is not None:
            return self._page_act(tab, state, op, value)
        return self._key_act(op, value)

    def _page_act(self, tab, state, op, value) -> OperatorOutcome:
        b = self.browser.backend
        if op == "state":
            return OperatorOutcome(True, self._describe(state), resource=self._record(tab, state), evidence=state)
        if op == "skip_ad":
            r = b.run(tab, "skip_ad") or {}
            if r.get("skipped"):
                return OperatorOutcome(True, "Skipped the ad.", evidence=r)
            return OperatorOutcome(False, "The ad can't be skipped yet." if r.get("ad") else "No ad is playing.",
                                   evidence=r)
        if op in ("captions", "fullscreen") or (op in ("next", "previous") and "youtube" in (tab.url or "")):
            b.activate(tab)
            return self._keys(_PLAYER_KEYS[op], f"{op.title()} toggled.")
        if op in ("next", "previous"):
            return self._key_act(op, value)
        arg = value
        if op == "volume" and value is not None and value > 1:
            arg = value / 100.0
        after = b.run(tab, "media", op, arg) if arg is not None else b.run(tab, "media", op)
        if after is None:
            return OperatorOutcome(False, "There's no video on this page.")
        ok = self._verify(op, arg, state, after)
        ref = self._record(tab, after)
        return OperatorOutcome(ok, self._message(op, arg, after) if ok else "The player didn't change.",
                               resource=ref, evidence={"before": state, "after": after})

    @staticmethod
    def _verify(op, val, before, after) -> bool:
        if op == "play" or op == "restart":
            return not after["paused"]
        if op == "pause":
            return after["paused"]
        if op == "toggle":
            return after["paused"] != before["paused"]
        if op == "seek_to":
            return abs(after["t"] - min(val, after.get("d") or val)) < 2.5
        if op == "seek_by":
            return abs(after["t"] - max(0, before["t"] + val)) < 2.5
        if op == "rate":
            return abs(after["rate"] - max(0.25, min(val, 4))) < 0.01
        if op == "mute":
            return after["muted"]
        if op == "unmute":
            return not after["muted"]
        if op == "volume":
            return abs(after["volume"] - max(0, min(val, 1))) < 0.02
        return True

    @staticmethod
    def _fmt(t: float) -> str:
        t = int(t or 0)
        return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"

    def _message(self, op, val, st) -> str:
        return {
            "play": "Playing.", "pause": "Paused.", "toggle": "Paused." if st["paused"] else "Playing.",
            "seek_to": f"Jumped to {self._fmt(st['t'])}.", "seek_by": f"Now at {self._fmt(st['t'])}.",
            "rate": f"Speed {st['rate']:g}x.", "mute": "Muted.", "unmute": "Unmuted.",
            "volume": f"Volume {round(st['volume'] * 100)}%.", "restart": "Playing from the start.",
            "loop": "Loop set.",
        }.get(op, "Done.")

    def _describe(self, st) -> str:
        if not st:
            return "Nothing is playing."
        where = f"{self._fmt(st['t'])} of {self._fmt(st['d'])}" if st.get("d") else self._fmt(st["t"])
        return f"{'Paused' if st['paused'] else 'Playing'} {st.get('title', '')} at {where}" + \
            (" (an ad is showing)" if st.get("ad") else "") + "."

    def _record(self, tab, st) -> MediaResourceRef:
        ref = MediaResourceRef(resource_id=f"media:{tab.url}", title=st.get("title") or tab.title, url=tab.url,
                               source="youtube" if "youtube" in (tab.url or "") else "web",
                               media_state="paused" if st.get("paused") else "playing",
                               position_s=float(st.get("t") or 0), duration_s=float(st.get("d") or 0))
        return self.resources.record(ref)

    def _keys(self, chord: str, message: str) -> OperatorOutcome:
        self.desktop.press(parse_chord(chord))
        return OperatorOutcome(True, message, evidence={"verified": None, "keys": chord})

    def _key_act(self, op, value) -> OperatorOutcome:
        if op in _MEDIA_KEYS:
            self.desktop.press(parse_chord(_MEDIA_KEYS[op]))
            return OperatorOutcome(True, {"play": "Sent play.", "pause": "Sent pause.", "toggle": "Sent play/pause.",
                                          "next": "Next track.", "previous": "Previous track.", "mute": "Toggled mute.",
                                          "unmute": "Toggled mute."}[op] + " (I can't read the player's state.)",
                                   evidence={"verified": None, "keys": _MEDIA_KEYS[op]})
        if op in ("volume",) and value is not None:
            return OperatorOutcome(False, "Set the system volume instead? Say 'set volume to "
                                          f"{int(value if value > 1 else value * 100)}'.", needs="clarify")
        return OperatorOutcome(False, "I can't control that player from here.", needs="clarify")
