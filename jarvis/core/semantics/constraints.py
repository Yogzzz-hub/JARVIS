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
_MARKER = r"(?:no+\s*,?\s*wait|wait\s*,?\s*no+|no+|actually|sorry|i\s+mean|i\s+meant|rather|make\s+(?:that|it)|scratch\s+that|correction|oops|nah|not\s+that\s+one|change\s+(?:that|it)\s+to)"
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


def apply_correction(text: str) -> tuple[str, list[tuple[str, str]]]:
    """'X - no, Y' / 'X, actually Y' / 'X... no wait, Y' -> X with the corrected part replaced by Y (typed alignment).
    Returns the corrected text and the (old, new) pairs; unchanged text when nothing is corrected."""
    t = " ".join((text or "").split())
    m = _CORRECTION.search(t) or _LOOSE.search(t)
    if not m:
        return text, []
    a = t[:m.start()].strip(" ,;.-—–")
    b_full = m.group("b").strip()
    if len(a.split()) < 2 or not b_full:
        return text, []
    b, tail = _strip_tail(b_full)
    if not b:
        return text, []
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
    # 4. a short object: "open chrome, sorry edge" -> the last word(s) of the same length
    if len(bw) <= 3 and not re.match(r"^(?:i|it|that|this|we|you)\b", b, re.I):
        k = len(bw)
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


_PROHIBIT = re.compile(r"^\s*(?:(?:please|but|and|so|jarvis)\s*,?\s+)*(?:don'?t|do\s+not|never|no\s+need\s+to)\s+(?P<p>[^,;]+?)\s*"
                       r"(?:,|;|\.(?=\s|$)|\s+-\s+|\s+(?=just\b|only\b|instead\b))\s*(?:just|only|instead|but)?\s*,?\s*(?P<rest>\S.*)$", re.I)


def prohibitions(text: str) -> tuple[str, list[str]]:
    """'don't pay anything, just read me the cart total' -> ("read me the cart total", ["pay anything"])."""
    m = _PROHIBIT.match(text or "")
    if not m:
        return text, []
    rest = m.group("rest").strip()
    if len(rest.split()) < 2:
        return text, []
    prohibited = m.group("p").strip()
    # "don't delete temp_test.txt, just tell me where it is": 'it' is the thing named in the prohibited clause
    obj = re.sub(r"^\S+\s+(?:(?:it|that|this|the|my)\s+)?", "", prohibited, count=1).strip()
    if obj and len(obj.split()) <= 5 and not re.fullmatch(r"(?:it|that|this|anything|everything|something)", obj, re.I):
        rest = re.sub(r"\b(?:it|that)\b", obj, rest, count=1, flags=re.I)
    return rest, [prohibited]


def analyse(text: str) -> Constraints:
    t, sup = apply_correction(text)
    t, proh = prohibitions(t)
    t, exc = extract_exclusions(t)
    return Constraints(t, exc, proh, sup)
