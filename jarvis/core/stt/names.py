"""Personal vocabulary for speech recognition: your contacts, installed apps and JARVIS words.

Two uses:
* ``hotwords()`` - a short list handed to Whisper so it prefers these spellings while decoding;
* ``correct(text)`` - after decoding, a word (or two-word span) that is not a real English word but is very close
  to exactly one known name is replaced by it ("open spotfy" -> "open Spotify", "message akash ana" ->
  "message Akash Anna"). Real words and message content after "saying" are never touched.
"""
from __future__ import annotations

import difflib
import re
from typing import Iterable

JARVIS_WORDS = ("Jarvis", "WhatsApp", "YouTube", "Spotify", "Chrome", "screenshot", "volume", "brightness", "reminder",
                "Bluetooth", "Wi-Fi", "Tanglish", "incognito", "clipboard")


def _is_english(word: str) -> bool:
    try:
        from jarvis.integrations.whatsapp.personal_reply.language import english_words
        return word.lower() in english_words()
    except Exception:
        return False


class NameVocabulary:
    def __init__(self, names: Iterable[str] = ()):
        seen: dict[str, str] = {}
        for n in list(JARVIS_WORDS) + list(names):
            n = " ".join(str(n or "").split())
            if 3 <= len(n) <= 40 and not n.isdigit():
                seen.setdefault(n.lower(), n)
        self.names = list(seen.values())
        self._by_lower = seen
        self._single = [k for k in seen if " " not in k]
        self._double = [k for k in seen if k.count(" ") == 1]

    def hotwords(self, limit: int = 40) -> str:
        """Most useful names first (multi-word and unusual names benefit most), kept short for speed."""
        ranked = sorted(self.names, key=lambda n: (_is_english(n), -len(n.split()), n.lower()))
        return " ".join(ranked[:limit])

    def _match(self, span: str, pool: list[str]) -> str | None:
        low = span.lower()
        if low in self._by_lower:
            return self._by_lower[low]
        hits = [c for c in difflib.get_close_matches(low, pool, n=2, cutoff=0.82) if c[0] == low[0]]
        if len(hits) == 1 or (len(hits) == 2 and difflib.SequenceMatcher(None, low, hits[0]).ratio()
                              - difflib.SequenceMatcher(None, low, hits[1]).ratio() > 0.06):
            return self._by_lower[hits[0]]
        return None

    def correct(self, text: str) -> str:
        if not text or not self.names:
            return text
        parts = re.split(r"(\s+(?:saying|that says|with the message)\s+)", text, maxsplit=1, flags=re.I)
        head, sep, tail = (parts + ["", ""])[:3]
        words = head.split(" ")
        out: list[str] = []
        i = 0
        while i < len(words):
            w = words[i]
            core = re.sub(r"^\W+|\W+$", "", w)
            if i + 1 < len(words):
                nxt = re.sub(r"^\W+|\W+$", "", words[i + 1])
                pair = f"{core} {nxt}"
                if len(core) >= 3 and len(nxt) >= 2 and not (_is_english(core) and _is_english(nxt)):
                    hit = self._match(pair, self._double)
                    if hit and hit.lower() != pair.lower():
                        out.append(w.replace(core, hit.split(" ")[0]) if core else hit.split(" ")[0])
                        out.append(words[i + 1].replace(nxt, hit.split(" ")[1]) if nxt else hit.split(" ")[1])
                        i += 2
                        continue
            if len(core) >= 4 and core.isalpha() and not _is_english(core):
                hit = self._match(core, self._single)
                if hit and hit.lower() != core.lower():
                    w = w.replace(core, hit)
            out.append(w)
            i += 1
        return " ".join(out) + sep + tail
