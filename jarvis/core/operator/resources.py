"""Typed resource memory for the operator: "that screenshot", "the download", "this video", "it".

Every primitive that produces something (a screenshot, a copied text, a download, a page, a playing video, a
window) records it here and, when a working memory is attached, mirrors it into the session's working memory so the
rest of JARVIS sees the same "current resource". Resolution is by *type words* first, recency second; a phrase
naming a type that was never produced is a clarification, never a guess.
"""
from __future__ import annotations

import re
import threading
from typing import Optional

from jarvis.core.context.models import BaseResourceRef

TYPE_WORDS: dict[str, tuple[str, ...]] = {
    "SCREENSHOT": ("screenshot", "screen shot", "screengrab", "screen grab", "capture", "snip", "snapshot"),
    "DOWNLOAD": ("download", "downloaded file", "downloaded", "the pdf i downloaded"),
    "FILE": ("file", "document", "doc", "pdf", "report", "spreadsheet", "attachment"),
    "CLIPBOARD": ("clipboard", "what i copied", "copied text", "copied"),
    "MEDIA": ("video", "song", "track", "music", "podcast", "movie", "clip", "playback"),
    "BROWSER_TAB": ("page", "tab", "website", "site", "article", "url", "link to this"),
    "LINK": ("link", "result", "search result"),
    "WINDOW": ("window", "app"),
    "TEXT": ("text", "answer", "summary", "reply", "message", "draft"),
    "CONTROL": ("button", "field", "box"),
}
_GENERIC = re.compile(r"^(it|that|this|them|those|these|the same|that one|this one|the thing)$")


class OperatorResources:
    def __init__(self, working_memory=None, size: int = 40):
        self._wm = working_memory
        self._items: list[BaseResourceRef] = []
        self._size = size
        self._lock = threading.Lock()

    def attach(self, working_memory) -> None:
        self._wm = working_memory

    def record(self, ref: BaseResourceRef) -> BaseResourceRef:
        with self._lock:
            self._items = [ref] + [r for r in self._items if r is not ref and not (
                r.resource_type == ref.resource_type and r.canonical_identifier
                and r.canonical_identifier == ref.canonical_identifier)][: self._size - 1]
        if self._wm is not None and ref.resource_type not in ("CONTROL",):
            try:
                self._wm.set_current_resource(ref)
            except Exception:
                pass
        return ref

    def latest(self, rtype: str = "", exclude: tuple[str, ...] = ("CONTROL", "WINDOW")) -> Optional[BaseResourceRef]:
        with self._lock:
            for r in self._items:
                if (r.resource_type == rtype) if rtype else (r.resource_type not in exclude):
                    if r.is_valid:
                        return r
        if not rtype and self._wm is not None:
            try:
                return self._wm.get_current_resource()
            except Exception:
                return None
        return None

    def all(self, rtype: str = "") -> list[BaseResourceRef]:
        with self._lock:
            return [r for r in self._items if not rtype or r.resource_type == rtype]

    @staticmethod
    def type_of(phrase: str) -> str:
        p = (phrase or "").lower()
        best, best_len = "", 0
        for rtype, words in TYPE_WORDS.items():
            for w in words:
                if re.search(rf"\b{re.escape(w)}s?\b", p) and len(w) > best_len:
                    best, best_len = rtype, len(w)
        return best

    def resolve(self, phrase: str) -> tuple[Optional[BaseResourceRef], str]:
        """(resource, '') or (None, question)."""
        p = re.sub(r"\b(the|my|last|latest|recent|most recent|previous|just|that|this|i took|i made|you took)\b", " ",
                   (phrase or "").lower()).strip()
        rtype = self.type_of(phrase)
        if rtype:
            hit = self.latest(rtype)
            if not hit and rtype == "FILE":
                hit = self.latest("DOWNLOAD")
            if not hit and rtype == "SCREENSHOT":
                clip = self.latest("CLIPBOARD")
                hit = clip if clip is not None and getattr(clip, "kind", "") == "image" else None
            if hit:
                return hit, ""
            return None, f"I don't have a {rtype.lower().replace('_', ' ')} from this session yet. Which one do you mean?"
        if not p or _GENERIC.match((phrase or "").lower().strip()):
            hit = self.latest()
            return (hit, "") if hit else (None, "What should I use?")
        return None, f"Which {phrase.strip()} do you mean?"


_res: Optional[OperatorResources] = None


def get_resources() -> OperatorResources:
    global _res
    if _res is None:
        _res = OperatorResources()
    return _res


def set_resources(res: Optional[OperatorResources]) -> None:
    global _res
    _res = res
