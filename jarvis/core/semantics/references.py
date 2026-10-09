"""Typed reference expressions: "it", "that one", "the second of those", "search hit number two", "atha", "avan".

A reference expression points at something said or shown earlier. It is never the name of an app, file, contact or
site: "open the second of those" is not an app called "second of those". Context resolution (jarvis.core.context.
carryover) turns a reference into the thing it points at - by type (a file, an app, a person, a list item), from the
active task or the turn just before, never by raw recency across types. When nothing resolves it, the router asks.
"""
from __future__ import annotations

import re

# pronouns and demonstratives, English and Tanglish
PRONOUNS = {"it", "its", "that", "this", "those", "these", "them", "they", "him", "her", "one", "ones",
            "adhu", "athu", "atha", "adha", "athai", "adhai", "idhu", "ithu", "itha", "idha", "ithai", "idhai", "andha", "indha",
            "avan", "aval", "avanga", "avar", "avaru", "avangala", "avana", "avala"}
PERSON_PRONOUNS = {"him", "her", "them", "avan", "aval", "avanga", "avar", "avaru", "avangala", "avana", "avala"}
# words that pick an item out of something already shown ("the second of those", "the other one"). Words like "new",
# "current" or "next" only describe ("open a new tab", "close the current tab") unless a pronoun points back as well.
SELECTORS = {"first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth", "last", "latest",
             "previous", "other", "same", "former", "latter", "1st", "2nd", "3rd", "4th", "5th", "number", "aforementioned",
             "mentioned", "earlier"}
_DESCRIBERS = {"new", "old", "current", "next", "top", "bottom", "above", "below", "no", "#"}
# kinds an item can be ("the second mail", "that folder")
KINDS = {"app", "application", "program", "window", "tab", "file", "folder", "document", "doc", "pdf", "photo", "picture",
         "image", "video", "song", "track", "mail", "email", "message", "msg", "chat", "contact", "person", "result", "results",
         "hit", "hits", "link", "links", "item", "items", "entry", "entries", "option", "options", "match", "matches", "list",
         "search", "page", "site", "website", "event", "meeting", "reminder", "note", "line", "row", "button", "dialog", "popup",
         "device", "setting", "one", "ones", "thing", "things", "stuff"}
_FILLER = {"the", "a", "an", "of", "from", "in", "on", "at", "to", "up", "down", "out", "again", "back", "there", "here",
           "please", "now", "too", "also", "just", "only", "my", "your", "our", "and", "for", "with", "which", "you", "i"}
_ORD = {"first": 1, "1st": 1, "one": 1, "second": 2, "2nd": 2, "two": 2, "third": 3, "3rd": 3, "three": 3, "fourth": 4,
        "4th": 4, "four": 4, "fifth": 5, "5th": 5, "five": 5, "sixth": 6, "six": 6, "seventh": 7, "seven": 7, "eighth": 8,
        "eight": 8, "ninth": 9, "nine": 9, "tenth": 10, "ten": 10, "last": -1, "latest": -1}
_LIST_KINDS = {"result", "results", "hit", "hits", "link", "links", "item", "items", "entry", "entries", "option", "options",
               "match", "matches", "list", "search"}


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9#]+", (value or "").lower().replace("'s", ""))


def is_reference(value) -> bool:
    """True when a slot value only points back ("it", "that new one", "the second of those", "search hit number 2",
    "that folder up") and names nothing itself. "that youtube tab" names youtube: it is a description, not only a
    reference. A pronoun followed by a word or two that names nothing ("it installed") is still a reference."""
    if not isinstance(value, str) or not value.strip():
        return False
    toks = _tokens(value)
    if not toks:
        return False
    if toks[0] in ("it", "its", "them", "those", "these", "they") and len(toks) <= 3 and not any(t[0].isdigit() for t in toks[1:]):
        return True
    has_ref = any(t in PRONOUNS - {"one", "ones"} or t in SELECTORS for t in toks)
    rest = [t for t in toks if t not in PRONOUNS and t not in SELECTORS and t not in _DESCRIBERS and t not in KINDS
            and t not in _FILLER and t not in _ORD and not t.isdigit()]
    return has_ref and not rest


def ordinal(value: str) -> int | None:
    """1-based position picked by a reference ("the second of those" -> 2, "hit number two" -> 2, "the last one" -> -1)."""
    toks = _tokens(value)
    for i, t in enumerate(toks):
        if t in ("number", "no", "#") and i + 1 < len(toks):
            nxt = toks[i + 1]
            if nxt.isdigit():
                return int(nxt)
            if nxt in _ORD:
                return _ORD[nxt]
        if t in _ORD and t not in ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"):
            return _ORD[t]
        if re.fullmatch(r"#?\d{1,2}", t) and i > 0 and toks[i - 1] in ("number", "no", "#", "result", "hit", "link", "item"):
            return int(t.lstrip("#"))
    return None


def kind(value: str) -> str | None:
    """The kind of thing a reference points at ("the second mail from that list" -> "mail", "those" -> None). A kind of
    item (mail, file, tab) wins over the list it was in (list, results)."""
    kinds = [t for t in _tokens(value) if t in KINDS and t not in ("one", "ones", "thing", "things", "stuff")]
    specific = [t for t in kinds if t not in _LIST_KINDS]
    return (specific or kinds or [None])[0]


def is_list_reference(value: str) -> bool:
    """A position in a list of results ("search hit number two", "the third link", "the first result")."""
    return is_reference(value) and ordinal(value) is not None and (kind(value) or "") in _LIST_KINDS


# a remark after the command, about the owner ("quit it, I'm done listening"): not part of the command's object
REMARK_TAIL = re.compile(r"\s*[,;.]\s*(?:(?:i'?m|i\s+am|i\s+was|i'?ve|i\s+have|i'?ll|i\s+will|i\s+don'?t|i\s+do\s+not|i\s+just)\b"
                         r"|(?:that'?s|it'?s)\s+(?:enough|all|it|fine|annoying|boring|too\s+\w+|so\s+\w+)\b"
                         r"|(?:thanks?|thank\s+you|cheers)\b).*$", re.I)
