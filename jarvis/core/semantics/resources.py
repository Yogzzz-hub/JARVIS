"""Typed resources: a file or folder the owner named is never collapsed into a generic string.

Blind-11: "delete temp_test.txt from my desktop" became ``delete_file(path=<the Desktop folder>)`` because every ``path``
slot was parsed as a folder and a value *ending* in a known folder name became that folder. And "delete the march
invoice" (after opening Downloads) became a non-existent ``Desktop/march invoice``.

Here a path phrase is parsed into a :class:`PathRef` - what kind of thing (file / folder / item), its name, and its parent
folder ("temp_test.txt from my desktop" -> file ``temp_test.txt`` in ``Desktop``). A user root (Desktop, Documents, a drive)
is its own kind, :data:`ROOT`, which no destructive tool may target. Names are resolved against what exists, never against
a guessed default location, and an exclusion ("not the 13th one") removes candidates instead of being ignored.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

FILE, FOLDER, ITEM, ROOT = "file", "folder", "item", "root"

KNOWN = {
    "desktop": "Desktop", "desk top": "Desktop", "downloads": "Downloads", "download": "Downloads", "down loads": "Downloads",
    "documents": "Documents", "document folder": "Documents", "docs": "Documents", "my documents": "Documents",
    "pictures": "Pictures", "photos folder": "Pictures", "pics": "Pictures", "music": "Music", "videos": "Videos",
    "video folder": "Videos",
}
_KNOWN_RE = r"(?:desk\s*top|downloads?|down\s+loads|documents|docs|pictures|pics|music|videos)"
_DET = r"(?:the|my|this|that|our)\s+"
_FILE_WORDS = r"(?:file|document|doc|pdf|image|photo|picture|screenshot|screen\s*shot|video|clip|song|track|spreadsheet|sheet|" \
              r"presentation|deck|installer|setup|archive|zip|log|invoice|receipt|report|resume|cv|note|notes)"
_EXT = re.compile(r"\.[a-z0-9]{1,5}$", re.I)
_DRIVE = re.compile(r"^(?:[a-z]\s*:\\?|[a-z]\s+drive|(?:the\s+)?(?:c|d|e)\s*drive|drive\s+[a-z]|whole\s+(?:drive|disk|computer|pc)|"
                    r"system32|windows(?:\s+folder)?|program\s+files)$", re.I)
_MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september",
                                       "october", "november", "december"], 1)}
_MONTHS.update({m[:3]: i for m, i in list(_MONTHS.items())})
_STOP = {"the", "my", "a", "an", "this", "that", "file", "one", "of", "from", "in", "on", "folder", "called", "named", "and",
         "st", "nd", "rd", "th", "not", "but", "only", "just"}


@dataclass
class PathRef:
    kind: str                     # FILE / FOLDER / ITEM / ROOT
    name: str                     # the item's own name ("temp_test.txt", "march invoice"); the root's name for ROOT
    parent: Optional[str] = None  # a known folder ("Desktop") or None when unsaid
    raw: str = ""

    @property
    def slot(self) -> str:
        """The value for a ``path`` slot: "Desktop/temp_test.txt", "march invoice", or the root folder itself."""
        if self.kind == ROOT:
            return self.name
        return f"{self.parent}/{self.name}" if self.parent else self.name


def _known(word: str) -> Optional[str]:
    w = " ".join(word.lower().split())
    w = re.sub(r"\s+(?:folder|directory|dir)$", "", w)
    w = re.sub(r"^(?:the|my|our)\s+", "", w)
    return KNOWN.get(w) or KNOWN.get(w.replace(" ", ""))


def parse_path_ref(value: str) -> PathRef:
    raw = " ".join(str(value or "").strip().strip("'\"").split())
    v = re.sub(rf"^{_DET}", "", raw, flags=re.I)
    low = v.lower()
    if _DRIVE.match(low) or _known(low):
        return PathRef(ROOT, _known(low) or v, None, raw)
    m = re.match(rf"^(?P<k>{_KNOWN_RE})\s*[\\/]+\s*(?P<rest>.+)$", v, re.I)
    if m:
        return _item(m.group("rest"), _known(m.group("k")), raw)
    m = re.match(rf"^(?P<x>.+?)\s+(?:from|in|on|inside|under|at|of|within)\s+(?:{_DET})?(?P<k>{_KNOWN_RE})(?:\s+(?:folder|directory))?$", v, re.I)
    if m:
        return _item(m.group("x"), _known(m.group("k")), raw)
    m = re.match(rf"^(?P<k>{_KNOWN_RE})\s+(?P<x>\S.*)$", v, re.I)
    if m and (_EXT.search(m.group("x")) or re.search(rf"\b{_FILE_WORDS}\b", m.group("x"), re.I)):
        return _item(m.group("x"), _known(m.group("k")), raw)   # "desktop notes.txt", "downloads invoice pdf"
    return _item(v, None, raw)


def _item(name: str, parent: Optional[str], raw: str) -> PathRef:
    n = re.sub(rf"^{_DET}", "", " ".join(name.split()), flags=re.I).strip(" .,")
    if re.search(r"\b(?:folder|directory)\s*$", n, re.I):
        return PathRef(FOLDER, re.sub(r"\s*\b(?:folder|directory)\s*$", "", n, flags=re.I), parent, raw)
    if _EXT.search(n) or re.search(rf"\b{_FILE_WORDS}s?\b", n, re.I):
        return PathRef(FILE, re.sub(r"\s+file$", "", n, flags=re.I), parent, raw)
    return PathRef(ITEM, n, parent, raw)


# ------------------------------------------------------------------------------------------------------------ resolving
def known_folder(name: str) -> Path:
    from jarvis.security.paths import get_known_folder
    return get_known_folder(name.lower())


def user_roots() -> list[Path]:
    out = []
    for k in ("Desktop", "Downloads", "Documents", "Pictures", "Music", "Videos"):
        try:
            p = known_folder(k)
            if p.exists():
                out.append(p)
        except Exception:
            pass
    return out


def is_root(path: Path) -> bool:
    """A user root, the home folder or a drive / system root: never the target of a destructive file tool."""
    try:
        p = Path(path).resolve(strict=False)
    except Exception:
        return True
    if p == p.parent:                      # "/" or "C:\\"
        return True
    home = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())).resolve(strict=False)
    roots = {home, home / "OneDrive", *[r.resolve(strict=False) for r in user_roots()]}
    if p in roots:
        return True
    names = {"desktop", "downloads", "documents", "pictures", "music", "videos", "onedrive"}
    if p.name.lower() in names and (p.parent in (home, home / "OneDrive") or p.parent.name.lower() in ("onedrive", home.name.lower())):
        return True   # the user's own Desktop / Documents ... wherever this machine keeps them
    low = str(p).lower().replace("\\", "/")
    return bool(re.search(r"/(?:windows|program files(?: \(x86\))?|programdata|system32)$", low))


def _tokens(text: str) -> set[str]:
    t = text.lower()
    # "april 12" / "12 april" -> "0412"; file names often carry dates as MMDD
    def md(m):
        a, b = m.group(1), m.group(2)
        month, day = (_MONTHS.get(a[:3]), b) if a[:3] in _MONTHS else (_MONTHS.get(b[:3]), a)
        return f" {month:02d}{int(day):02d} " if month and day.isdigit() and 0 < int(day) <= 31 else m.group(0)
    t = re.sub(r"\b([a-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?\b", md, t)
    t = re.sub(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3,9})\b", md, t)
    t = re.sub(r"\.([a-z0-9]{1,5})$", r" \1", t)
    t = re.sub(r"\b(\d+)(?:st|nd|rd|th)\b", r"\1", t)
    words = set(re.findall(r"[a-z]+|\d+", t))
    month_nums = {f"{v:02d}" for k, v in _MONTHS.items() if k in words}
    return {w for w in words if w not in _STOP} | month_nums


def _excl_hit(word: str, cand: set[str]) -> bool:
    """An excluded word names this candidate: equal, or a number that ends a date-coded token ("13" -> "0413")."""
    if word in cand:
        return True
    return word.isdigit() and any(c.isdigit() and len(c) > len(word) and c.endswith(word.zfill(2)) for c in cand)


@dataclass
class Resolution:
    status: str                          # "found" / "not_found" / "ambiguous" / "root"
    path: Optional[Path] = None
    candidates: list[Path] = field(default_factory=list)


def resolve_target(ref: PathRef, exclude: Iterable[str] = (), prefer: Optional[str] = None, max_files: int = 4000) -> Resolution:
    """Find the one existing file or folder the owner meant. Exact names first, then every query word (dates normalised)
    present in a candidate's name. Excluded words remove candidates; a context folder breaks ties. Never invents a path."""
    if ref.kind == ROOT:
        try:
            return Resolution("root", known_folder(ref.name))
        except Exception:
            return Resolution("root")
    bases = [known_folder(ref.parent)] if ref.parent else user_roots()
    bases = [b for b in bases if b and b.exists()]
    name = ref.name.strip()
    # exact
    for b in bases:
        c = b / name
        if c.exists():
            return Resolution("found", c)
    q = _tokens(name)
    if not q:
        return Resolution("not_found")
    ex = [_tokens(e) for e in exclude if e]
    found: list[Path] = []
    seen = 0
    for b in bases:
        for root, dirs, files in os.walk(b):
            depth = len(Path(root).relative_to(b).parts)
            if depth >= 2:
                dirs[:] = []
            for n in files + dirs:
                seen += 1
                if seen > max_files:
                    break
                ct = _tokens(Path(n).stem if n in files else n) | ({Path(n).suffix[1:].lower()} if n in files else set())
                if q <= ct:
                    if any(e and all(_excl_hit(w, ct) for w in e) for e in ex):
                        continue
                    found.append(Path(root) / n)
    if not found:
        return Resolution("not_found")
    if len(found) > 1 and prefer:
        try:
            pf = known_folder(prefer)
            pref = [f for f in found if pf in f.parents]
            if len(pref) == 1:
                return Resolution("found", pref[0], found)
        except Exception:
            pass
    if len(found) == 1:
        return Resolution("found", found[0], found)
    return Resolution("ambiguous", None, found)
