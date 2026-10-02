"""Shared semantic constraints of one request: corrections (supersession), exclusions and prohibitions.

Blind-11 (development data) showed the constraint words surviving as plain text inside slots:
- "message Ramesh I'll be late - no, message Rajesh"  -> sent to Ramesh, the message "I'll be late, no, message Rajesh"
- "add lunch with Ramesh at 1 - no, at 2"            -> an event "at 1, no, at 2"
- "tell everyone who messaged me I'm busy, except Arun" -> "except Arun" inside the message to everyone
- "delete the april 12 screenshot, not the 13th one"  -> the exclusion ignored

One representation is computed for the whole request and used by routing, slot filling, planning and execution:
- ``apply_correction``: the superseded value is replaced, by type, and never stays executable;
- ``extract_exclusions``: "except X", "but not X", "not the 13th one" -> excluded values, removed from the text;
- ``prohibitions``: "don't pay anything, just ..." -> the prohibited clause, kept as a constraint, not routed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_DELIM = r"(?:\s*(?:,|;|—|–|\.\.\.|…)\s*|\s+-\s+)"
_MARKER = r"(?:no+\s*,?\s*wait|wait\s*,?\s*no+|no+|illa(?:\s+illa)?|illa\s+venam|venam|vendam|vendaam|actually|sorry|i\s+mean|i\s+meant|rather|make\s+(?:that|it)|scratch\s+that|correction|oops|nah|not\s+that\s+one|change\s+(?:that|it)\s+to)"
_CORRECTION = re.compile(rf"{_DELIM}(?:{_MARKER})(?:\s*,?\s*(?:{_MARKER}))*\s*,?\s+(?P<b>.+)$", re.I)
_LOOSE = re.compile(r"\s+(?:no\s+wait|scratch\s+that|i\s+mean|make\s+that)\s*,?\s+(?P<b>.+)$", re.I)

_VERBS = r"(?:open|close|launch|start|stop|quit|kill|send|message|text|whatsapp|call|ring|dial|email|mail|tell|reply|play|pause|set|turn|" \
         r"switch|restart|reboot|shut|shutdown|power|lock|sleep|hibernate|log|install|uninstall|update|delete|remove|move|copy|rename|" \
         r"schedule|add|create|book|make|remind|search|find|look|show|go|navigate|type|write|mute|unmute|increase|decrease|raise|lower)"
# content-bearing commands: the words after them are the owner's text, corrected only in recipient / time
_MSG_LEAD = re.compile(r"^\s*(?:please\s+)?(?:send|message|msg|text|whatsapp|tell|reply|email|mail|ping|inform|write|type|dictate|say|"
                       r"note|remember|add\s+a\s+note|post|tweet|caption)\b", re.I)
_WEEKDAY = r"(?:mon|tues?|wed(?:nes)?|thu(?:rs)?|fri|sat(?:ur)?|sun)(?:day)?|today|tomorrow|tonight"
_TIME = r"(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.|o'?clock)?|noon|midnight"
_NUMWORD = r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|" \
           r"eighteen|nineteen|twenty|thirty|forty|fourty|fifty|sixty|seventy|eighty|ninety|hundred)(?:[\s-](?:one|two|three|four|five|six|" \
           r"seven|eight|nine|hundred))?"
_NUMBER = rf"(?:\d+(?:\.\d+)?\s*%?|{_NUMWORD}(?:\s+percent)?)"


@dataclass
class Constraints:
    text: str
    excluded: list[str] = field(default_factory=list)
    prohibited: list[str] = field(default_factory=list)
    superseded: list[tuple[str, str]] = field(default_factory=list)   # (old, new)


def _strip_tail(b: str) -> tuple[str, str]:
    """The corrected value and whatever followed it: "tuesday, 10am" -> ("tuesday", ", 10am")."""
    b = re.sub(r"\s+(?:instead|then|please|pls)\s*[.!]*$", "", b.strip(), flags=re.I).strip(" .!")
    m = re.match(r"^(?P<v>[^,;]+?)(?P<rest>\s*[,;].*)?$", b)
    return (m.group("v").strip(), (m.group("rest") or "")) if m else (b, "")


def _replace_last(pattern: str, a: str, new: str) -> str | None:
    ms = list(re.finditer(pattern, a, re.I))
    if not ms:
        return None
    m = ms[-1]
    lead = re.match(r"(?:at|on|by|for)\s+", m.group(0), re.I)
    if lead and not re.match(r"(?:at|on|by|for)\s+", new, re.I):
        new = lead.group(0) + new          # "remind me at 5, make that 5:30" keeps "at"
    return a[:m.start()] + new + a[m.end():]


_CATEGORIES = [
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"],
    ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "today", "tomorrow", "tonight", "yesterday"],
    ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth", "last", "next", "previous"],
    ["male", "female", "man", "woman", "boy", "girl"],
    ["red", "blue", "green", "yellow", "black", "white", "orange", "purple", "pink", "grey", "gray", "dark", "light"],
    ["small", "medium", "large", "big", "tiny", "huge"],
    ["english", "tamil", "hindi", "thanglish", "tanglish", "telugu", "malayalam", "kannada", "french", "spanish", "german"],
    ["pc", "laptop", "computer", "phone", "mobile", "tablet"],
    ["wifi", "bluetooth", "hotspot", "data", "mobile data", "location", "nfc"],
]
_CANCEL = re.compile(r"^(?:just\s+)?(?:leave\s+it(?:\s+(?:as\s+it\s+is|alone|be))?|forget\s+(?:it|that|about\s+it)|never\s*mind|"
                     r"cancel\s+(?:that|it)|don'?t\s+(?:do\s+)?(?:it|that|anything)|skip\s+(?:it|that)|nothing|no\s+need|"
                     r"don'?t\s+\w+.*\bforget\s+it|keep\s+(?:it|that|them|this)\b(?:\s+and\s+don'?t\s+\w+)?)\b", re.I)
CANCELLED = "__cancelled__"
# kind nouns that follow a name ("VLC player", "chrome browser", "budget file")
_KIND_NOUNS = {"app", "application", "player", "browser", "program", "software", "file", "folder", "window", "tab", "document",
               "doc", "song", "video", "track", "playlist", "channel", "site", "website", "page", "game", "editor"}


def _category(word: str) -> list[str] | None:
    w = word.lower()
    return next((c for c in _CATEGORIES if w in c), None)


def _replace_same_category(a: str, word: str) -> str | None:
    """'copy the march invoice ... - no, the april one' -> march replaced by april (same category, last occurrence)."""
    cat = _category(word)
    if not cat:
        return None
    hits = [m for m in re.finditer(r"[a-z]+", a, re.I) if m.group(0).lower() in cat and m.group(0).lower() != word.lower()]
    if not hits:
        return None
    m = hits[-1]
    return a[:m.start()] + word + a[m.end():]


# an address or courtesy opening is not a clause that can be corrected: "hey jarvis, make it louder", "please make that uppercase"
_ADDRESS = re.compile(r"^(?:(?:hey|hi|hello|ok(?:ay)?|um+|uh+|hmm+|so|well|please|pls|jarvis|could\s+you(?:\s+please)?|"
                      r"can\s+you(?:\s+please)?|would\s+you(?:\s+please)?)\b\s*,?\s*)+", re.I)
# the typed values a "make that / make it" correction can carry ("set it to 30, make it 40"); "make it louder" is a command
_TYPED_VALUE = re.compile(rf"^(?:(?:at|on|to|for|by|in|from|with)\s+)?(?:{_TIME}|{_WEEKDAY}|{_NUMBER}(?:\s*\w+)?|['\"].+|[A-Z]\w*)\s*[.!]?$")


def apply_correction(text: str) -> tuple[str, list[tuple[str, str]]]:
    """'X - no, Y' / 'X, actually Y' / 'X... no wait, Y' -> X with the corrected part replaced by Y (typed alignment).
    Returns the corrected text and the (old, new) pairs; unchanged text when nothing is corrected."""
    t = " ".join((text or "").split())
    lead = _ADDRESS.match(t)
    if lead and lead.end():
        body = t[lead.end():]
        out, pairs = apply_correction(body)
        if not pairs or out == CANCELLED:
            return (out if pairs else text), pairs
        return t[:lead.end()] + out, pairs
    m = _CORRECTION.search(t) or _LOOSE.search(t)
    if not m:
        return text, []
    a = t[:m.start()].strip(" ,;.-—–")
    b_full = m.group("b").strip()
    if not a or not b_full:
        return text, []
    marker = t[m.start():m.start("b")].strip(" ,;.-—–…").lower()
    if re.fullmatch(r"make\s+(?:that|it)", marker) and not _TYPED_VALUE.match(b_full):
        return text, []      # "turn it up, make it louder": a restatement, not a corrected value
    if re.fullmatch(r"no+", marker) and not re.search(r"no+\s*[,;]", t[m.start():m.start("b")], re.I) \
            and re.match(r"\w+(?:[^s\W]s|ing)\b", b_full, re.I):
        return text, []      # "reply to everyone, no groups": "no" + a plural / gerund is a negative constraint
    if _CANCEL.match(b_full) and (not _MSG_LEAD.match(a)
                                  or re.search(r"\b(?:forget\s+(?:it|that)|never\s*mind|cancel\s+(?:that|it))\s*[.!]?$", b_full, re.I)):
        return CANCELLED, [(a, "")]          # "dark mode on... wait no, leave it as it is": nothing is to be done
    aw0, bw0 = a.split(), b_full.split()
    dropping = re.match(r"^(?:skip|drop|without|leave\s+out|not|no)\b", b_full, re.I)
    try:
        from jarvis.core.multilingual import _COMMAND_WORDS as _TVERBS
    except Exception:
        _TVERBS = frozenset()
    final_verb = aw0[-1].lower().strip("'\"") in _TVERBS
    if final_verb and not dropping and (len(bw0) >= 2 and aw0[-1].lower().strip("'\"") == bw0[-1].lower().strip("'\"") or
                                         (len(bw0) >= 3 and aw0[-1].lower() in [w.lower().strip("'\"") for w in bw0[1:]] and len(aw0) <= 4)):
        # verb-final restatement (Tanglish): "Arun ku anuppu, illa venam, Vignesh ku anuppu 'ready'" -> the second command
        return b_full, [(a, b_full)]
    b, tail = _strip_tail(b_full)
    if not b:
        return text, []
    # quoted text replaces quoted text: "type 'meeting at 4'... no, 'meeting at 5'"
    qa = list(re.finditer(r"(['\"])(?P<q>[^'\"]+)\1", a))
    qb = re.fullmatch(r"(['\"])?(?P<q>[^'\"]+)\1?", b_full.strip(" .")) if re.search(r"['\"]", b_full) else None
    if qa and qb:
        last = qa[-1]
        return a[:last.start("q")] + qb.group("q") + a[last.end("q"):], [(last.group("q"), qb.group("q"))]
    if len(a.split()) < 2:
        if len(b.split()) == 1 and len(a.split()) == 1:
            return b + tail, [(a, b)]        # "undo - no wait, redo"
        return text, []
    # a step is dropped: "mute and lock - actually skip the lock"
    sm = re.match(r"^(?:skip|drop|without|leave\s+out|not|no|don'?t\s+\w+)\s+(?:the\s+)?(?P<x>[\w ]{2,30})$", b, re.I)
    if sm:
        x = re.escape(sm.group("x").strip())
        out = re.sub(rf"\s*(?:,|\band\b|\bthen\b)\s*(?:\w+\s+)?{x}\b|\b{x}\s*(?:,|\band\b|\bthen\b)\s*", " ", a, count=1, flags=re.I)
        if out != a:
            return " ".join(out.split()) + tail, [(sm.group("x"), "")]
    # "the april one", "keep the male one", "just the third": a word of the same kind replaces its sibling
    cm = re.match(r"^(?:keep\s+|use\s+|just\s+|only\s+)?(?:the\s+|a\s+)?(?P<w>[a-z]+)(?:\s+(?:one|ones|item|instead))?$", b, re.I)
    if cm and _category(cm.group("w")):
        out = _replace_same_category(a, cm.group("w"))
        if out:
            return out + tail, [(a, cm.group("w"))]
    # "just 2", "50 minutes": a number (with its unit) replaces the number of the same unit
    nm = re.match(rf"^(?:just|only)?\s*(?P<n>{_NUMBER})\s*(?P<u>minutes?|mins?|hours?|hrs?|seconds?|secs?|percent|photos?|files?|items?|pages?|times?)?$", b, re.I)
    if nm and re.search(r"\d|" + _NUMWORD, nm.group("n"), re.I):
        unit = nm.group("u")
        bare = rf"(?:\d+(?:\.\d+)?|{_NUMWORD})"
        pat = rf"\b{bare}(?=\s*{unit[:3]})" if unit else rf"\b{_NUMBER}(?=\W*$|\s)"
        out = _replace_last(pat, a, nm.group("n").strip())
        if out:
            return out + tail, [(a, b)]
    message = bool(_MSG_LEAD.match(a))
    bw, aw = b.split(), a.split()
    # 1. the same command again with a new object: "message Ramesh ... - no, message Rajesh"
    if bw[0].lower() == aw[0].lower() and len(bw) >= 2:
        k = len(bw)
        new = " ".join(bw + aw[k:]) if (message and len(bw) <= 3) or len(aw) > k else " ".join(bw)
        return new + tail, [(" ".join(aw[:k]), b)]
    # 2. a different command: "shut down... no wait, restart instead" -> the new command on the same object
    if re.match(rf"^{_VERBS}\b", b, re.I) and not message:
        old_verb = re.match(rf"^(?:{_VERBS})(?:\s+(?:down|off|on|up|out))?\b", a, re.I)
        rest = a[old_verb.end():] if old_verb else ""
        new_verb = re.match(rf"^(?:{_VERBS})(?:\s+(?:down|off|on|up|out))?\b", b, re.I)
        b_rest = b[new_verb.end():].strip() if new_verb else ""
        if not b_rest and not rest.strip() and re.match(r"^(?:shut|power|turn|switch)\b", a, re.I) \
                and re.match(r"^(?:restart|reboot|sleep|hibernate|lock|log)\b", b, re.I):
            b = b + " the pc"     # "shut down... no wait, restart": still the computer
        return (b if b_rest or not rest.strip() else (b + rest)) + tail, [(a, b)]
    # 3. typed value: a preposition phrase, a time, a weekday, a number
    for pat in (rf"\b(?:at|on|to|with|for|in|from|by)\s+\S+(?:\s+(?:am|pm))?",):
        pm = re.match(r"^(?P<p>at|on|to|with|for|in|from|by)\s+(?P<v>.+)$", b, re.I)
        if pm:
            out = _replace_last(rf"\b{pm.group('p')}\s+(?:{_TIME}|{_WEEKDAY}|[\w'.-]+(?:\s+(?:am|pm))?)", a, b)
            if out:
                return out + tail, [(a, b)]
    if re.fullmatch(_WEEKDAY, b, re.I):
        out = _replace_last(rf"\b(?:{_WEEKDAY})\b", a, b)
        if out:
            return out + tail, [(a, b)]
    if re.fullmatch(rf"{_TIME}", b, re.I) and re.search(r"\d", b):
        out = _replace_last(rf"\b(?:{_TIME})\b", a, b)
        if out:
            return out + tail, [(a, b)]
    if re.fullmatch(_NUMBER, b, re.I):
        out = _replace_last(rf"\b{_NUMBER}(?=\W*$|\s)", a, b)
        if out:
            return out + tail, [(a, b)]
    if message:
        # inside a message only the recipient may be corrected ("text Arun hi, sorry, Naveen")
        if len(bw) <= 2 and bw[0][:1].isupper():
            rm = re.match(rf"^(?P<v>(?:please\s+)?(?:send|message|msg|text|whatsapp|tell|reply\s+to|email|mail|ping|inform|write\s+to))\s+(?P<n>\S+)", a, re.I)
            if rm:
                return a[:rm.start("n")] + b + a[rm.end("n"):] + tail, [(rm.group("n"), b)]
        return text, []
    # 4. a short object: "open chrome, sorry edge" -> the last word(s) of the same length; a name with its kind noun
    #    ("start VLC player - sorry, Spotify") is replaced whole
    if len(bw) <= 3 and not re.match(r"^(?:i|it|that|this|we|you)\b", b, re.I):
        k = len(bw)
        if len(aw) >= k + 2 and aw[-1].lower() in _KIND_NOUNS and bw[-1].lower() not in _KIND_NOUNS:
            k += 1
        return " ".join(aw[:-k] + bw) + tail, [(" ".join(aw[-k:]), b)]
    return text, []


_EXCLUDE = re.compile(r"(?:,\s*|\s+)(?:but\s+)?(?:except(?:\s+for)?|excluding|other\s+than|apart\s+from|but\s+not|not\s+including|"
                      r"leave\s+out|skip(?:ping)?|minus)\s+(?P<x>[^,;.]+)", re.I)
_NOT_THE = re.compile(r"(?:,\s*|\s+)(?:and\s+|but\s+)?not\s+(?:the\s+|that\s+|this\s+|my\s+)?(?P<x>[^,;.]+?)(?:\s+one)?\s*(?=$|[,;.])", re.I)


def extract_exclusions(text: str) -> tuple[str, list[str]]:
    """'tell everyone I'm busy, except Arun' -> ("tell everyone I'm busy", ["Arun"]);
    'delete the april 12 screenshot, not the 13th one' -> (..., ["13th"])."""
    t = text or ""
    out: list[str] = []
    for rx in (_EXCLUDE, _NOT_THE):
        m = rx.search(t)
        if m and len(t[:m.start()].split()) >= 2:
            x = re.sub(r"\s+(?:one|ones|please)$", "", m.group("x").strip(), flags=re.I)
            if x and len(x.split()) <= 4:
                out.append(x)
                t = (t[:m.start()] + t[m.end():]).strip()
    return t, out


# "do not disturb" / "do not track" name a mode or setting, they prohibit nothing ("turn on do not disturb on my phone")
_NOT_A_MODE = r"(?!disturb\b(?!\s+(?:me|us|him|her|them)\b)|track\b)"
_PROHIBIT = re.compile(rf"^\s*(?:(?:please|but|and|so|jarvis)\s*,?\s+)*(?:don'?t|do\s+not|never|no\s+need\s+to)\s+{_NOT_A_MODE}(?P<p>[^,;]+?)\s*"
                       r"(?:,|;|\.(?=\s|$)|\s+-\s+|\s+(?=just\b|only\b|instead\b))\s*(?:just|only|instead|but)?\s*,?\s*(?P<rest>\S.*)$", re.I)


def prohibitions(text: str) -> tuple[str, list[str]]:
    """'don't pay anything, just read me the cart total' -> ("read me the cart total", ["pay anything"])."""
    m = _PROHIBIT.match(text or "")
    if not m:
        return text, []
    rest = re.sub(r"\s+instead\s*[.!]?$", "", m.group("rest").strip(), flags=re.I)   # "..., open spotify instead"
    if len(rest.split()) < 2:
        return text, []
    prohibited = m.group("p").strip()
    # "don't delete temp_test.txt, just tell me where it is": 'it' is the thing named in the prohibited clause
    obj = re.sub(r"^\S+\s+(?:(?:it|that|this|the|my)\s+)?", "", prohibited, count=1).strip()
    if obj and len(obj.split()) <= 5 and not re.fullmatch(r"(?:it|that|this|anything|everything|something)", obj, re.I):
        if re.match(r"(?:call|ring|dial|text|message|email|mail|ping|tell|ask|remind|invite)\b", prohibited, re.I) and len(obj.split()) <= 2:
            rest = re.sub(r"\b(?:him|her|them)\b", obj, rest, count=1, flags=re.I)   # "don't call Arun, just text him"
        else:
            rest = re.sub(r"\b(?:it|that)\b", obj, rest, count=1, flags=re.I)
    return _carry_domain(prohibited, rest), [prohibited]


_CONTRAST_LEAD = re.compile(r"^\s*not\s+(?P<x>[^,;]{2,40}?)\s*[,;]\s*(?:(?:i|we)\s+(?:said|meant|want(?:ed)?|asked\s+for)\s+|but\s+|rather\s+|just\s+)?"
                            r"(?P<y>\S.*)$", re.I)
_CONTRAST_TAIL = re.compile(r"(?P<sep>\s*,\s*(?:(?:and|but)\s+)?(?:just\s+)?|\s+(?:but|just)\s+)not\s+(?:on\s+|in\s+|to\s+|with\s+|from\s+)?"
                            r"(?:the\s+|that\s+|this\s+|my\s+|a\s+)?(?P<x>[^,;.]{1,40}?)(?:\s+one)?\s*(?=$|[,;.])", re.I)


def contrast(text: str) -> tuple[str, list[str]]:
    """A rejected alternative said next to the chosen one is not part of the command:
    'click cancel, not ok' -> ('click cancel', ['ok']); 'not thanglish, plain english' -> ('plain english', ['thanglish']);
    'play something, just not on youtube' -> ('play something', ['youtube']). Never inside a message being sent."""
    t = " ".join((text or "").split())
    m = _CONTRAST_LEAD.match(t)
    if m and len(m.group("y").split()) >= 1 and not re.match(r"(?:now|yet|really|sure|bad|much|that)\b", m.group("x"), re.I):
        return m.group("y").strip(), [m.group("x").strip()]
    if _MSG_LEAD.match(t):
        return text, []
    m = _CONTRAST_TAIL.search(t)
    if m and len(t[:m.start()].split()) >= 2 and not re.search(r"\b(?:do|does|did|is|are|was|were|i'?m|it'?s|why|will|can|could)\s*$",
                                                               t[:m.start()], re.I):
        return " ".join((t[:m.start()] + " " + t[m.end():].lstrip(" ,")).split()).strip(" ,"), [m.group("x").strip()]
    return text, []


_PROHIBIT_TAIL = re.compile(rf"^(?P<rest>.+?)\s*,?\s+(?:but\s+|and\s+)?(?:don'?t|do\s+not|never)\s+{_NOT_A_MODE}(?P<p>[^,;]+?)\s*[.!]?$", re.I)
_TANGLISH_NOT = re.compile(r"^(?P<p>.+?)\s+(?:pannadha|pannaadha|pannadhe|pannatha|pannaadheenga|venam|vendam|vendaam|vendaa|koodadhu)\s*,\s*"
                           r"(?P<rest>\S.*)$", re.I)


_APP_DOMAIN = re.compile(r"\b(?P<app>whats\s*app|gmail|e-?mail|telegram|instagram|youtube|spotify|chrome|browser)\b", re.I)


def _carry_domain(prohibited: str, rest: str) -> str:
    """'don't open whatsapp, just tell me the unread': the unread are WhatsApp's - the app named in the prohibited clause is
    the domain of the positive one when that one names none."""
    m = _APP_DOMAIN.search(prohibited)
    if m and not _APP_DOMAIN.search(rest) and re.search(r"\b(?:unread|new|messages?|mails?|chats?|latest|newest|any(?:one|body))\b", rest, re.I):
        return f"{rest} on {m.group('app')}"
    return rest


def trailing_prohibition(text: str) -> tuple[str, list[str]]:
    """'open chrome and youtube, but don't play anything' -> ('open chrome and youtube', ['play anything']);
    Tanglish 'shutdown venam, sleep la podu' -> ('sleep la podu', ['shutdown'])."""
    t = " ".join((text or "").split())
    m = _TANGLISH_NOT.match(t)
    if m:
        return _carry_domain(m.group("p"), m.group("rest")), [m.group("p")]
    if _MSG_LEAD.match(t):
        return text, []
    m = _PROHIBIT_TAIL.match(t)
    if m and re.match(rf"^{_VERBS}\b", m.group("rest"), re.I) and len(m.group("rest").split()) >= 2:
        return m.group("rest").strip(" ,"), [m.group("p").strip()]
    return text, []


def analyse(text: str) -> Constraints:
    t, sup = apply_correction(text)
    t, proh = prohibitions(t)
    t, exc = extract_exclusions(t)
    return Constraints(t, exc, proh, sup)


_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_DUR_NUM = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "ten": 10, "fifteen": 15, "twenty": 20,
            "thirty": 30, "forty": 40, "forty five": 45, "fortyfive": 45, "ninety": 90, "half": 0.5, "half an": 0.5}


def _edit1(a: str, b: str) -> int:
    """Small Levenshtein distance (enough for spoken / typed weekday slips)."""
    if abs(len(a) - len(b)) > 2:
        return 3
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def normalize_event_time(when: str) -> tuple[str, int | None]:
    """'on friday at 11 for 30 minutes' -> ('on friday at 11', 30); 'at 3 pm wenesday' -> ('at 3 pm wednesday', None)."""
    w = " ".join((when or "").split())
    minutes = None
    m = re.search(r"\s*,?\s*\bfor\s+(?P<n>\d+(?:\.\d+)?|an?|one|two|three|four|five|six|ten|fifteen|twenty|thirty|forty(?:\s+five)?|"
                  r"ninety|half(?:\s+an)?)\s*(?P<u>minutes?|mins?|hours?|hrs?|h)\b(?:\s+long)?", w, re.I)
    if m:
        n = m.group("n").lower()
        val = float(n) if re.match(r"\d", n) else float(_DUR_NUM.get(n, 0))
        unit = m.group("u").lower()
        minutes = int(round(val * 60)) if unit.startswith(("h", "hr")) else int(round(val))
        w = (w[:m.start()] + w[m.end():]).strip(" ,")
    else:
        m = re.search(r"\s*,?\s*\bfor\s+half\s+an\s+hour\b", w, re.I)
        if m:
            minutes, w = 30, (w[:m.start()] + w[m.end():]).strip(" ,")

    def fix(mm):
        word = mm.group(0)
        if word.lower() in _WEEKDAYS:
            return word
        best = min(_WEEKDAYS, key=lambda d: _edit1(word.lower(), d))
        return best if _edit1(word.lower(), best) <= 2 and word[:2].lower() == best[:2] else word
    w = re.sub(r"\b[a-z]{5,10}day\b|\b(?:wenesday|wensday|wednsday|thrusday|thurday|tusday|teusday|saterday|satuday|fryday)\b", fix, w, flags=re.I)
    return w, (minutes if minutes and minutes > 0 else None)
