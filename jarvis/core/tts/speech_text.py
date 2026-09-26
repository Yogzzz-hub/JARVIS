"""Make any reply pleasant to hear: the single clean-up step in front of every voice engine.

Links become "a link from dribbble.com", long Windows/Unix paths become their file or folder name, emojis and
markdown symbols are dropped, and repeated punctuation is collapsed. The on-screen text is not changed.
"""
from __future__ import annotations

import re

_URL = re.compile(r"(?:https?://|www\.)[^\s\"')\]]+", re.I)
_WIN_PATH = re.compile(r"\b[A-Za-z]:[\\/](?:[^\s\\/:*?\"<>|]+[\\/])*([^\s\\/:*?\"<>|]+)")
_NIX_PATH = re.compile(r"(?<![\w.])/(?:[\w.-]+/){2,}([\w.-]+)")
_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]")


def _link(m: re.Match) -> str:
    host = re.sub(r"^(?:https?://)?(?:www\.)?", "", m.group(0), flags=re.I).split("/")[0].split("?")[0].lower()
    return f"a link from {host}" if host else "a link"


def speech_text(text: str) -> str:
    t = text or ""
    t = _URL.sub(_link, t)
    t = _WIN_PATH.sub(lambda m: m.group(1), t)
    t = _NIX_PATH.sub(lambda m: m.group(1), t)
    t = _EMOJI.sub("", t)
    t = re.sub(r"[*_#`~|<>\[\]{}]+", " ", t)
    t = re.sub(r"([!?.])\1{1,}", r"\1", t)
    return " ".join(t.split())
