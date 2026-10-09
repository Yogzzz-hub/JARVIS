"""General paraphrase understanding for device settings, power and status requests.

People express the same request through synonym verbs ("crank", "dim", "pop open"), number words ("fourty", "one fifty",
"a quarter"), misspelt or split nouns ("volum", "brite ness"), and indirect complaints ("this screen is blinding me").
This module recognises those *shapes* and rewrites them to the one canonical wording the deterministic router already
understands. It rewrites constructions, never particular sentences, and never touches a command that carries the owner's
own words (a message, a note, typed text).
"""
from __future__ import annotations

import re

_UNITS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
          "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
          "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fourty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_FRACTIONS = {"half": 50, "a half": 50, "quarter": 25, "a quarter": 25, "one quarter": 25, "three quarters": 75, "three quarter": 75,
              "a third": 33, "one third": 33, "two thirds": 67, "full": 100, "max": 100, "maximum": 100, "all the way": 100,
              "min": 0, "minimum": 0, "zero": 0}
_NUMWORD = r"(?:" + "|".join(sorted(list(_UNITS) + list(_TENS) + ["hundred"], key=len, reverse=True)) + r")"


def fix_number_typos(text: str) -> str:
    """"sixy" -> "sixty", "fiftyy" -> "fifty", "twnty" -> "twenty": a mistyped number word (never a real English word)."""
    from jarvis.core.router.normalize import _edit_distance, _english_word
    known = list(_UNITS) + list(_TENS) + ["hundred"]
    out = []
    for w in (text or "").split():
        core = w.strip(".,!?;:'\"%").lower()
        if len(core) >= 4 and core.isalpha() and core not in known and not _english_word(core):
            hits = [k for k in known if len(k) >= 4 and abs(len(k) - len(core)) <= 1 and k[0] == core[0] and _edit_distance(core, k) <= 1]
            if len(hits) == 1:
                w = w.lower().replace(core, hits[0])
        out.append(w)
    return " ".join(out)


def words_to_int(text: str) -> int | None:
    """"fourty" -> 40, "one fifty" -> 150, "hundred" -> 100, "twenty five" -> 25, "a quarter" -> 25, "7" -> 7."""
    t = re.sub(r"[-,]", " ", (text or "").lower()).strip()
    t = re.sub(r"\b(?:percent|per\s*cent|%|around|about|roughly|approximately|nearly|like)\b", " ", t)
    t = " ".join(t.split())
    if not t:
        return None
    if re.fullmatch(r"\d{1,3}", t):
        return int(t)
    if t in _FRACTIONS:
        return _FRACTIONS[t]
    toks = t.split()
    if not all(w in _UNITS or w in _TENS or w in ("hundred", "and", "a") for w in toks):
        return None
    toks = [w for w in toks if w not in ("and", "a")]
    if not toks:
        return None
    if toks == ["hundred"]:
        return 100
    if len(toks) == 2 and toks[0] in _UNITS and toks[1] in _TENS:           # "one fifty" = 150, "two forty" = 240
        return _UNITS[toks[0]] * 100 + _TENS[toks[1]]
    if len(toks) == 2 and toks[0] in _TENS and toks[1] in _UNITS and _UNITS[toks[1]] < 10:
        return _TENS[toks[0]] + _UNITS[toks[1]]
    if len(toks) == 2 and toks[1] == "hundred" and toks[0] in _UNITS:
        return _UNITS[toks[0]] * 100
    if len(toks) == 1:
        return _UNITS.get(toks[0], _TENS.get(toks[0]))
    return None


def _fuzzy_has(word: str, targets: tuple[str, ...]) -> str | None:
    from jarvis.core.router.normalize import _edit_distance
    w = word.lower()
    for t in targets:
        if w == t:
            return t
        if len(w) >= 5 and len(t) >= 5 and w[0] == t[0] and _edit_distance(w, t) <= (2 if len(t) >= 7 else 1):
            return t
    return None


# --- the settings that have a level
_VOLUME = ("volume", "sound", "audio", "loudness", "speaker", "speakers")
_BRIGHT = ("brightness", "screen light", "display light")
_LEVEL_VERB_UP = r"(?:raise|increase|boost|bump\s+up|turn\s+up|crank(?:\s+up)?|pump(?:\s+up)?|blast|max(?:\s+out)?|push\s+up|up)"
_LEVEL_VERB_DOWN = r"(?:lower|decrease|reduce|drop|turn\s+down|dim|dial\s+down|bring\s+down|take\s+down|cut|tone\s+down|soften)"
_NOT_CONTENT = re.compile(r"\b(?:send|text|message|msg|tell|type|write|dictate|note|remind|reply|email|mail|say|saying)\b")


def _setting_of(t: str) -> str | None:
    """volume / brightness, tolerant of one-two letter slips and a split word ("brite ness")."""
    t2 = re.sub(r"\b(br[a-z]{1,3})\s+(ness|nes)\b", "brightness", t)
    words = re.findall(r"[a-z]+", t2)
    if "phone" in words or "mobile" in words:
        return None
    for w in words:
        if w in ("speaker", "speakers") or (w not in ("speak", "speaking", "spoke") and _fuzzy_has(w, ("volume", "sound", "audio", "loudness"))):
            return "volume"
        if _fuzzy_has(w, ("brightness", "brighter", "bright")) or w in ("dimmer", "dim", "dimmed"):
            return "brightness"
    if "screen" in words and re.search(r"\b(?:dim|brighten|darken)\b", t2):
        return "brightness"
    return None


def settings_command(t: str) -> str | None:
    """"crank the sound all the way up" -> "set volume to 100"; "dim the screen down to a quarter" -> "set brightness to 25";
    "set volum to fourty" -> "set volume to 40". None when the text is not a level command."""
    t = " ".join(t.lower().split())
    t = fix_number_typos(t)
    if _NOT_CONTENT.search(t) or len(t.split()) > 14:
        return None
    if re.search(r"\b(?:every|whenever|when|once|after|before|tomorrow|tonight|daily|weekdays?|mornings?|evenings?|if|until|till|while|schedule\w*)\b|"
                 r"\bat\s+\d{1,2}(?::\d\d)?\s*(?:am|pm|a\.m\.|p\.m\.)|\bin\s+\d+\s*(?:min|sec|hour|hr)", t):
        return None      # a scheduled or conditional command is the scheduler's
    if re.search(r"\b(?:and|then|also|plus|after\s+that|but|open|launch|start|play|close)\b|,", t):
        return None      # one level command, not part of a longer plan
    if re.search(r"\bcall\b|\bor\b|^(?:volume|brightness|sound)\s+(?:is|was)\b|\bby\s+\S+\s*(?:%|percent|per\s*cent)?\s*$|(?<![\w])-\d|\d\.\d|\bwhat\b|\d:\d\d|\bfrom\b|\bfor\s+\w+\s+(?:sec|secs|seconds?|min|mins|minutes?)\b", t):
        return None      # call volume is the phone's; "or" asks a question; statements, relative changes and malformed values are not level commands
    setting = _setting_of(t)
    if setting is None and re.search(r"\b(?:dim|brighten|darken)\b", t) and re.search(r"\b(?:screen|display|monitor)\b", t):
        setting = "brightness"
    if setting is None:
        return None
    # an explicit target value: digits, number words, fractions
    m = re.search(rf"\b(?:to|at|=|around|about|of)?\s*((?:\d{{1,3}})|(?:(?:a\s+|one\s+|three\s+|two\s+)?(?:half|quarter|quarters|third|thirds))|"
                  rf"(?:{_NUMWORD}(?:[\s-]+(?:and\s+)?{_NUMWORD}){{0,2}}))\s*(?:%|percent|per\s*cent)?\s*$", t)
    if m:
        v = words_to_int(m.group(1))
        if v is not None and v > 100:
            return None
        if v is not None:
            return f"set {setting} to {max(0, min(100, v))}"
    # "all the way up", "to the max", "full blast", "to the minimum"
    if re.search(r"\b(?:all\s+the\s+way\s+up|to\s+the\s+max(?:imum)?|(?:at\s+)?(?:max|maximum|full)(?:\s+(?:blast|volume|brightness))?|full\s+blast|as\s+(?:loud|bright|high)\s+as\s+(?:it\s+)?(?:goes|can))\b", t):
        return f"set {setting} to 100"
    if re.search(r"\b(?:all\s+the\s+way\s+down|to\s+the\s+min(?:imum)?|(?:at\s+)?(?:min|minimum|lowest)|as\s+(?:low|quiet|dark)\s+as\s+(?:it\s+)?(?:goes|can))\b", t):
        return f"set {setting} to 0"
    if re.search(rf"\b{_LEVEL_VERB_UP}\b", t) and not re.search(r"\b(?:to|at)\s+\d", t):
        return f"increase the {setting}"
    if re.search(rf"\b{_LEVEL_VERB_DOWN}\b", t) and not re.search(r"\b(?:to|at)\s+\d", t):
        return f"decrease the {setting}"
    return None


# ---------------------------------------------------------------------------------------------------------------------
# status, power, capture and open-synonym shapes
def _tok_fuzzy(t: str, word: str) -> bool:
    return any(_fuzzy_has(w, (word,)) for w in re.findall(r"[a-z]+", t))


_DEVICE = r"(?:laptop|pc|computer|machine|system|device|desktop|windows|it)"


def rewrite(t: str) -> str | None:
    """Canonical wording for a recognised paraphrase shape, else None."""
    t = " ".join(t.lower().split()).strip(" .!?")
    if not t or len(t.split()) > 16 or _NOT_CONTENT.search(t):
        return None
    # --- levels
    if not re.match(r"^(?:how|what|which|is|are|does|do)\b", t):
        s = settings_command(t)
        if s:
            return s
    # --- reading a level / the battery
    if re.fullmatch(r"how\s+(?:bright|dim)\s+is\s+(?:my\s+|the\s+)?(?:display|screen|monitor)(?:\s+(?:currently|right\s+now|now|at\s+the\s+moment))?", t):
        return "what is the brightness"
    if re.fullmatch(r"how\s+loud\s+is\s+(?:it|my\s+(?:sound|speakers?)|the\s+(?:sound|speakers?))(?:\s+(?:currently|right\s+now|now))?", t):
        return "what is the volume"
    if re.fullmatch(rf"how\s+(?:much\s+)?(?:charge|battery|power|juice|life|percent(?:age)?)\s+(?:does\s+)?(?:the\s+|my\s+)?{_DEVICE}?\s*"
                    rf"(?:have\s+)?(?:left|remaining|remains?)(?:\s+(?:now|currently|right\s+now))?", t) \
            or re.fullmatch(rf"how\s+(?:long|much\s+time)\s+(?:until|till|before|will)\s+(?:my\s+|the\s+)?{_DEVICE}\s+(?:dies|die|shuts?\s*down|"
                            rf"runs?\s+out|is\s+(?:dead|empty)|lasts?)", t) \
            or re.fullmatch(rf"how\s+(?:long|much)\s+(?:will|does|can)\s+(?:my\s+|the\s+)?(?:battery|charge)\s+(?:last|hold|go)", t) \
            or re.fullmatch(r"(?:battery|charge)\s+(?:left|remaining|level|percent(?:age)?)", t):
        return "what's my battery level"
    # --- screenshot with typos / split words / synonyms
    words = re.findall(r"[a-z]+", t)
    joined = re.sub(r"\bscreen\s+(?=sh|sn|ca|gr)", "screen", t)
    if re.search(r"\b(?:phone|mobile|android|fone)\b", t):
        pass
    elif (re.search(r"\bscreen\s*(?:shot|shoot|snap|sho+t|capture|grab|cap)s?\b", t) or
            (_tok_fuzzy(t, "screenshot") and len(words) <= 5) or re.fullmatch(r"(?:capture|grab|snap|take|tek)\s+(?:a\s+|my\s+|the\s+)?screen(?:\s+(?:now|please))?", t)) \
            and not re.search(r"\b(?:and|then|to|into|in|paste|send|save|record|recording|attach\w*|remove|delete|show|view|open|upload|find|where|rename|just|already|previous|last|latest|recent|saved|from|current|that|those|these|folder|pull|fetch|copy|share|size|read|ocr|trash|old|older|erase|wipe|clear|junk|work|works|utilities|utility)\b", t):
        return "take a screenshot"
    # --- power synonyms (fuzzy verbs): only a whole request about the computer itself
    dev = r"(?:the\s+|my\s+|this\s+)?(?:pc|computer|laptop|machine|system)"
    tailnow = r"(?:\s+(?:right\s+)?(?:now|rite\s+now|immediately))?"
    if re.fullmatch(rf"(?:lock|secure){tailnow}\s*(?:{dev})?\s*(?:up|down)?{tailnow}|(?:lock|secure)\s+(?:{dev}|the\s+display|the\s+screen|it)(?:\s+up)?{tailnow}", t) \
            and t not in ("lock", "secure"):
        return "lock the pc"
    if re.fullmatch(rf"(?:send|put|set|switch|move|take|drop)\s+(?:{dev})\s+(?:in)?to\s+(?:sleep|standby|hibernate)(?:\s+mode)?{tailnow}|"
                    rf"(?:sleep|hibernate)\s+(?:{dev}){tailnow}", t):
        return "put the pc to sleep"
    m = re.fullmatch(rf"(?P<v>[a-z]+)\s+(?:down\s+)?(?:{dev}){tailnow}", t)
    if m and _fuzzy_has(m.group("v"), ("shutdown", "shut")) and m.group("v") not in ("shut", "shutdown"):
        return "shut down the pc"
    if m and _fuzzy_has(m.group("v"), ("restart", "reboot")) and m.group("v") not in ("restart", "reboot"):
        return "restart the pc"
    # --- open synonyms
    m = re.fullmatch(r"(?:pop|bring|fire|crack|spin|start)\s+(?:open|up)\s+(?:the\s+)?(?P<x>[a-z][\w .+-]{1,30}?)(?:\s+for\s+me)?", t)
    if m:
        x = re.sub(r"^windows\s+", "", m.group("x"))
        return f"open {x}"
    # --- news
    m = re.fullmatch(r"(?:give\s+me|show\s+me|get\s+me|tell\s+me|pull\s+up|what(?:'s|\s+is|\s+are))\s+(?:the\s+)?(?:today'?s\s+|latest\s+|top\s+|breaking\s+)*"
                     r"(?:(?P<k>[a-z]+)\s+)?(?:headlines|news)(?:\s+(?:today|now|for\s+today|please))?", t)
    if m:
        k = m.group("k")
        return f"latest {k} news" if k and k not in ("the", "all", "top", "latest", "todays", "today") else "latest news headlines"
    m = re.fullmatch(r"(?:search|serch|find|look\s*up|get)\s+(?:for\s+)?(?:the\s+)?(?:latest|recent|breaking)\s+news\s+(?:about|abt|on|regarding|for)\s+(?P<q>.+)", t)
    if m:
        return f"latest news about {m.group('q')}"
    return None
