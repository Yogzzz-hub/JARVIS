"""Lexicon-driven paraphrase understanding: concepts and shapes, not sentences.

``canonicalize`` (canonical.py) rewrites constructions the router's rules already know. This module adds the broader
layer: noisy spelling of command vocabulary, synonym verbs, indirect phrasings and device words, mapped by *concept*
(a setting, a device, an action, a kind of thing) onto the canonical wording of the matching capability.

Pipeline: ``repair`` fixes misspelt / split / ASR-garbled command words anywhere in a command (never inside the owner's
own words), ``concepts`` reads what the request is about, ``rewrite`` returns the canonical command or None.

Safety: it never runs on a command that carries content (send / write / note ...), and a request with a negation,
correction or exception is left to the constraint layer first (which calls canonicalize again on the positive part).
"""
from __future__ import annotations

import re

from jarvis.core.router.paraphrase import rewrite as _levels_status, words_to_int

# ------------------------------------------------------------------------------------------------------- spelling
# canonical command vocabulary: a token one or two slips from one of these (and not an ordinary English word) is repaired
_VOCAB = """
phone mobile android wifi bluetooth hotspot airplane torch flashlight screenshot clipboard volume brightness battery calendar
tomorrow today yesterday email emails inbox unread notes memos memo reminders reminder history uninstall install restart shutdown
lock sleep zoom refresh reload scroll window windows snap left right dictation password generate remember forget copy paste undo
redo select backspace delete minimize maximize news headlines weather search download open close speak slower louder quieter
faster music song video play pause resume stop screenshot screen notepad calculator explorer settings display dark light mode
folder file files document documents desktop downloads pictures recycle keyboard microphone speaker speakers typing type
escape enter tab tabs page browser chrome whatsapp gmail drive youtube spotify network internet address processor memory storage
contacts contact message messages reply group groups birthday meeting meetings schedule events event todo tasks task notification
notifications popup dialog button click press double tap swipe call dial ring camera photo photos record recording capture
transfer upload share print rename move duplicate compress extract zip folder workflow workflows project projects logs test tests
whenever every after before once until while schedule weekday weekdays morning evening night daily minutes hours seconds speaking talking reading writing opening closing playing running testing sending messages tests projects
""".split()
_ALIASES = {
    "fone": "phone", "phne": "phone", "fon": "phone", "cellphone": "phone", "cell": "phone", "mob": "mobile",
    "blutooth": "bluetooth", "bluetoth": "bluetooth", "bluethooth": "bluetooth", "bt": "bluetooth", "wi-fi": "wifi", "wify": "wifi",
    "aaf": "off", "ofd": "off", "shot": "shot", "scrn": "screen", "screnshot": "screenshot", "scrnshot": "screenshot",
    "pasword": "password", "passwrd": "password", "pwd": "password", "recyclebin": "recycle", "calender": "calendar",
    "calander": "calendar", "tomoro": "tomorrow", "tomorow": "tomorrow", "tmrw": "tomorrow", "yestrday": "yesterday",
    "msg": "message", "msgs": "messages", "mails": "emails", "mail": "email", "unred": "unread", "unreed": "unread",
    "notifs": "notifications", "notif": "notification", "tipe": "type", "tyoe": "type", "opn": "open", "opne": "open",
    "clos": "close", "colse": "close", "shutdwn": "shutdown", "rite": "right", "pres": "press", "escap": "escape",
    "delet": "delete", "rember": "remember", "remeber": "remember", "genrate": "generate", "generat": "generate",
    "dictashun": "dictation", "dictaion": "dictation", "strat": "start", "srart": "start", "histry": "history", "clipbord": "clipboard",
    "windo": "window", "refersh": "refresh", "refesh": "refresh", "zum": "zoom", "volum": "volume", "volumn": "volume",
    "britness": "brightness", "brigthness": "brightness", "tek": "take", "taek": "take", "scren": "screen",
    "sceen": "screen", "serch": "search", "searh": "search", "abt": "about", "wether": "weather", "wheather": "weather",
    "recipie": "recipe", "instal": "install", "unistal": "uninstall", "uninstal": "uninstall", "spotfy": "spotify",
    "crome": "chrome", "chorme": "chrome", "whatsap": "whatsapp", "whatapp": "whatsapp", "gmial": "gmail", "youtub": "youtube",
}
_JOINS = [(r"\bscreen\s+(shot|shoot|sho+t|snap|capture)s?\b", "screenshot"), (r"\bbr[a-z]{1,3}\s+nes+\b", "brightness"),
          (r"\bwi\s+fi\b", "wifi"), (r"\bblue\s+tooth\b", "bluetooth"), (r"\bhot\s+spot\b", "hotspot"),
          (r"\bflash\s+light\b", "flashlight"), (r"\bclip\s+board\b", "clipboard"), (r"\bback\s+space\b", "backspace"),
          (r"\bnote\s+pad\b", "notepad"), (r"\bdesk\s+top\b", "desktop"), (r"\bair\s*plane\b", "airplane"),
          (r"\bwat\s+is\b", "what is"), (r"\bwats\b", "what's"), (r"\bn\s+(?=[a-z])", "and ")]
_SKIP_REPAIR = frozenset("a an the of on in to is it at as by or if no so do we he me my us up docs doc tidy backend frontend fullstack localhost sharex".split())


def repair(text: str) -> str:
    """Fix spelling of command vocabulary anywhere in a command; leaves ordinary English and names alone."""
    from jarvis.core.router.normalize import _edit_distance, _english_word
    t = " ".join(text.lower().split())
    for pat, rep in _JOINS:
        t = re.sub(pat, rep, t)
    words = t.split()
    out = []
    for w in words:
        core = w.strip(".,!?;:")
        tail = w[len(core):]
        if core in _ALIASES:
            out.append(_ALIASES[core] + tail)
            continue
        if len(core) < 4 or not core.isalpha() or core in _SKIP_REPAIR or core in _VOCAB or _english_word(core):
            out.append(w)
            continue
        best = None
        for v in _VOCAB:
            if v[0] != core[0] or abs(len(v) - len(core)) > 2:
                continue
            d = _edit_distance(core, v)
            if d <= (1 if len(v) <= 6 else 2) and (best is None or d < best[0]):
                best = (d, v)
        out.append((best[1] if best else core) + tail)
    return " ".join(out)


# ------------------------------------------------------------------------------------------------------- concepts
_NEG = re.compile(r"\b(?:don'?t|do\s+not|never|not|no|without|except|but|instead|rather|sorry|actually|wait|scratch|nevermind|never\s*mind|illa|venam|"
                  r"vendam|unless|only\s+if|if)\b")
_CV = r"(?:send|text|message|msg|tell|type|write|dictate|note|remind|reply|email|mail|say|ask|draft|compose|caption|post|forward|share)"
# the owner's own words: a content verb that starts a clause ("text divya ...", "... and tell him ..."), or "saying" / quotes anywhere
_CONTENT = re.compile(rf"(?:^|\b(?:and|then|also|plus|after\s+that|,)\s*|\b(?:please|pls|can\s+you|could\s+you|just)\s+){_CV}\b|\bsaying\b|[\"“”]|\bthat\s+says\b")


def _has(t: str, pat: str) -> bool:
    return re.search(pat, t) is not None


_PHONE = r"(?:phone|mobile|android|cellphone)"
_PC = r"(?:pc|laptop|computer|desktop|system|machine|windows)"
_ON = r"(?:on|enable|enabled|activate|start|open|switch\s+on|turn\s+on|connect|join|light\s+up)"
_OFF = r"(?:off|disable|disabled|deactivate|kill|cut|stop|disconnect|shut|silence|of)"
_SETTINGS = [
    ("wifi", r"\bwi-?fi\b|\bwlan\b"), ("bluetooth", r"\bbluetooth\b"), ("mobile data", r"\bmobile\s+data\b|\bcellular\b|\bdata\b|\binternet\b"),
    ("airplane mode", r"\b(?:airplane|aeroplane|flight)\s+mode\b|\bflight\b|\bairplane\b"), ("hotspot", r"\bhotspot\b|\btethering\b"),
    ("flashlight", r"\btorch\b|\bflash\s*light\b"), ("do not disturb", r"\bdo\s+not\s+disturb\b|\bdnd\b|\bsilent\s+mode\b"),
    ("location", r"\blocation\b|\bgps\b"), ("auto rotate", r"\bauto[\s-]?rotat\w*\b|\bscreen\s+rotation\b"),
]


def _phone_toggle(t: str) -> str | None:
    """"kill the phone's wifi", "put my phone in flight mode", "torch on", "blutooth of in mobile" -> turn on|off X on my phone."""
    on_phone = _has(t, rf"\b{_PHONE}\b")
    found = [name for name, pat in _SETTINGS if _has(t, pat)]
    if "mobile data" in found and ("wifi" in found or "hotspot" in found) and not _has(t, r"\bmobile\s+data\b|\bcellular\b"):
        found.remove("mobile data")
    if not found:
        return None
    pc = _has(t, rf"\b{_PC}\b")
    if pc and not on_phone:
        return None
    if _has(t, r"\b(?:keep|but|except|instead|laptop|pc|computer|tap|press|click|swipe|install\w*|where|find|path|located|folder|studio)\b|\bconnect\s+to\b|\bover\s+wi-?fi\b|\bdoes\b"):
        return None
    if not on_phone and found != ["flashlight"]:
        return None
    if _has(t, r"\b(?:status|is|are|what|which|check|show|list)\b") and not _has(t, rf"\b{_OFF}\b|\b{_ON}\b"):
        return None
    if _has(t, r"\b(?:setting|settings|page|menu|screen)\b"):
        return None
    off = _has(t, rf"\b(?:off|disable|disabled|deactivate|kill|cut|stop|disconnect|shut\s+off|turn\s+off|of)\b")
    on = _has(t, r"\b(?:on|enable|enabled|activate|start|switch\s+on|turn\s+on|connect|join|light\s+up|put)\b")
    if off and not on or (off and _has(t, r"\b(?:turn|switch|put)\s+off\b|\boff\b|\bof\b")):
        state = "off"
    elif on:
        state = "on"
    else:
        return None
    if len(found) == 1:
        return f"turn {state} {found[0]} on my phone"
    return " and ".join(f"turn {state} {n} on my phone" for n in found)


def _call(t: str) -> str | None:
    """"ring up my sister Divya", "cal amma", "buzz Kumar", "give Raj a call" -> call X on my phone."""
    m = re.fullmatch(r"(?:please\s+)?(?:(?:ring|buzz)(?:\s+up)?|call|dial|(?:give|make)\s+(?:a\s+)?call\s+(?:to\s+)?)\s+"
                     r"(?:up\s+)?(?:my\s+)?(?P<p>[a-z][a-z' ]{1,24}?)(?:\s+(?:on|from|using|via)\s+(?:my\s+)?(?:phone|mobile))?", t) \
        or re.fullmatch(r"(?:give|make)\s+(?P<p>[a-z][a-z' ]{1,24}?)\s+a\s+(?:call|ring|buzz)", t)
    if not m:
        return None
    p = m.group("p").strip()
    if re.match(r"(?:please\s+)?(?:call|dial)\s", t) and not re.search(r"\bon\s+(?:my\s+)?(?:phone|mobile)\b", t):
        return None          # a plain "call X" is the router's own: names stay exactly as spoken
    if p.split()[0] in ("me", "us", "you", "u", "it", "them", "him", "her", "this", "that", "later", "phone") or p.split()[-1] in ("back", "later", "urgent", "final", "off"):
        return None
    if p in ("it", "this", "that", "him", "her", "them", "back", "me", "up", "my phone", "the second one", "the first one", "the last one") \
            or re.match(r"(?:the|a|an|that|this|those|these)\b", p) or _has(p, r"\b(?:wifi|bluetooth|data|on|off|mode)\b"):
        return None
    return f"call {p} on my phone"


def _clipboard(t: str) -> str | None:
    if not _has(t, r"\bclipboard\b|\bcopied\b|\bcopy\s+history\b|\bpasted\s+history\b"):
        return None
    if _has(t, r"\b(?:clear|wipe|empty|erase|clean|delete|purge)\b") and _has(t, r"\bhistory\b|\bclipboard\b"):
        return "clear clipboard history"
    if _has(t, r"\b(?:history|panel|list|earlier|before|ago|previous)\b") and _has(t, r"\b(?:open|show|see|view|display|bring|pull|list)\b"):
        return None          # the router's own wording for the history panel
    if _has(t, r"\b(?:what|read|show|tell|see|check|display|whatever|anything)\b") and not _has(t, r"\b(?:put|set|copy|place|save|store|write|saved|items?|history)\b"):
        return "what is on my clipboard"
    return None


def _speech(t: str) -> str | None:
    """Controls of JARVIS's own voice: "raise your speaking voice a bit", "you're rushing, take it easy" -> speak louder|slower."""
    if _has(t, r"\b(?:while|when|whenever|if|during|runs?|running)\b"):
        return None
    me = _has(t, r"\b(?:voice|speak\w*|talk\w*|pace|rushing|spoken)\b|\byou(?:'re|\s+are)\s+(?:too\s+)?(?:loud|fast|slow|quiet|soft)\b")
    if not me or _has(t, r"\b(?:volume|brightness|music|song|video|phone|screen|open|launch|start|close|fire|pull|bring)\b"):
        return None
    if _has(t, r"\b(?:rush|rushing|fast|hurry)\w*\b") and _has(t, r"\b(?:slow|ease|calm|down|relax|pace)\b|\btake\s+it\s+easy\b"):
        return "speak slower"
    if _has(t, r"\b(?:slow|slower|slowly|easy|calm)\b") and _has(t, r"\b(?:speak\w*|talk\w*|pace|voice|reading)\b"):
        return "speak slower"
    if _has(t, r"\b(?:faster|quicker|speed\s+up|hurry)\b") and _has(t, r"\b(?:speak\w*|talk\w*|pace|voice|reading)\b"):
        return "speak faster"
    if _has(t, r"\b(?:raise|louder|increase|boost|up|higher|more\s+loudly|bigger)\b") and _has(t, r"\b(?:voice|speak\w*|talk\w*)\b"):
        return "speak louder"
    if _has(t, r"\b(?:keep|lower|quieter|softer|reduce|decrease|down|lower)\b") and _has(t, r"\b(?:voice|speak\w*|talk\w*)\b") \
            and not _has(t, r"\bstop\b"):
        return "speak quieter"
    return None


def _browser(t: str) -> str | None:
    """Browser quick actions by intent: back, forward, reopen closed tab, zoom, new tab, reload, top / bottom."""
    if _has(t, r"\b(?:phone|mobile|android)\b"):
        return None
    if _has(t, r"\b(?:bring|get|restore|reopen|undo)\b.*\b(?:closed|tab)\b.*\b(?:mistake|accident|closed)\b|\b(?:reopen|restore|bring\s+back|undo)\b.*\b(?:closed|last)\b.*\btab\b|"
              r"\b(?:didn'?t|did\s+not)\s+mean\s+to\s+close\b|\bclosed\s+(?:that|the)\s+tab\b.*\bby\s+mistake\b|\boops\b.*\bclose"):
        return "reopen the closed tab"
    if _has(t, r"\b(?:head|go|get|take\s+me|navigate)\s+back\b|\bprevious\s+page\b|\bback\s+(?:one\s+)?page\b|\bpage\s+back\b") \
            and not _has(t, r"\b(?:window|windows|desktop|app|application|program|previous\s+(?:window|app)|spreadsheet|document|file|folder|tab|editor|ide|code|chat|topic|conversation|subject|video|song|track|audio|playlist)\b") \
            and not _has(t, r"\bback\s+(?:to|into|in|at|on)\b|\bback\s+\d|\b\d+\s*(?:sec|secs|seconds?|min|mins|minutes?|hours?|steps?|lines?|pages)\b|\bme\s+back\s+to\b"):
        return "go back a page"
    if _has(t, r"\b(?:go|head|move|navigate|forward)\b.*\bforward\b|\bnext\s+page\b|\bpage\s+forward\b") and not _has(t, r"\bof\s+(?:the\s+)?(?:results|search|list)\b"):
        return "go forward"
    if _has(t, r"\b(?:make|set|increase|enlarge|bigger|larger|zoom)\b.*\b(?:text|font|page|letters|words|writing)\b.*\b(?:bigger|larger|big|large|more)\b|\b(?:text|font|writing)\s+(?:is\s+)?(?:too\s+)?(?:tiny|small)\b|"
              r"\bcan'?t\s+read\b.*\b(?:tiny|small|font)\b|\bzoom\s+in\b|\bmake\s+(?:the\s+)?(?:page|text)\s+(?:bigger|larger)\b"):
        return "zoom in"
    if _has(t, r"\bzoom\s+out\b|\bzoom\b.*\b(?:out|less|smaller)\b|\bmake\s+(?:the\s+)?(?:page|text)\s+smaller\b|\bshrink\s+(?:the\s+)?(?:page|text)\b"):
        return "zoom out"
    if _has(t, r"\b(?:zoom|text\s+size|page\s+size)\b.*\b(?:normal|default|reset|100|back|original)\b|\b(?:reset|normal)\s+zoom\b"):
        return "reset zoom"
    if _has(t, r"\b(?:new|fresh|another|blank)\s+tab\b|\bopen\s+(?:a\s+)?tab\b") and not _has(t, r"\b(?:in|into|on)\s+(?:a\s+|an\s+)?(?:new|another|fresh|blank|separate)\s+tab\b"):
        return "open a new tab"
    if _has(t, r"\b(?:refresh|reload|renew)\b.*\b(?:page|site|tab)\b|\b(?:refresh|reload)\s+(?:this|it)\b|\b(?:page|site)\b.*\b(?:stuck|frozen|not\s+loading|hung)\b|\bstuck\s+(?:loading|on\s+loading)\b"):
        return "refresh the page"
    if _has(t, r"\b(?:bottom|end|last\s+part)\b.*\b(?:page|site)\b|\bscroll\b.*\b(?:bottom|end)\b|\b(?:take|go|jump|get)\s+(?:me\s+)?(?:to\s+)?(?:the\s+)?bottom\b"):
        return "scroll to the bottom"
    if _has(t, r"\b(?:top)\b.*\b(?:page|site)\b|\bscroll\b.*\btop\b|\b(?:go|jump|get|take\s+me)\s+(?:to\s+)?(?:the\s+)?top\b"):
        return "scroll to the top"
    if _has(t, r"\b(?:close|shut|kill|dismiss)\s+(?:this|the\s+current|current|that|the)\s+(?:browser\s+)?tab\b|\bclose\s+(?:the\s+)?tab\b") \
            and not _has(t, r"\b(?:file|editor|ide|code|document|doc|terminal|notebook|source|vs|other|another|rest|all|others)\b"):
        return "close this tab"
    return None


def _snap(t: str) -> str | None:
    """"put this window on the right half", "snap windo top rite" -> snap the window to the <direction>."""
    if not _has(t, r"\bsnap\b|\bdock\b|\b(?:put|move|push|send|place|pin)\b.*\bwindow\b|\bwindow\b.*\b(?:left|right|top|bottom|half|corner|side)\b"):
        return None
    if not _has(t, r"\bwindow\b|\bwindo\b|^snap\s+(?:it|this|that)\b|^snap\s+(?:to|top|bottom|left|right)\b"):
        return None      # "snap chrome to the right" names an app: the window rules know it
    if _has(t, r"\b(?:and|then)\b|\bphone\b"):
        return None
    vert = "top" if _has(t, r"\b(?:top|upper)\b") else "bottom" if _has(t, r"\b(?:bottom|lower)\b") else ""
    horiz = "left" if _has(t, r"\bleft\b") else "right" if _has(t, r"\b(?:right|rite)\b") else ""
    if vert and horiz:
        return f"snap this window to the {vert} {horiz}"
    if horiz:
        return f"snap this window to the {horiz}"
    return None


def _text_edit(t: str) -> str | None:
    """Keyboard / text editing in the focused field: "backspace three times", "undo that last change", "redo what you just undid"."""
    m = re.fullmatch(r"(?:press\s+)?backspace\s+(?P<n>\w+)\s+times?", t)
    if m:
        n = words_to_int(m.group("n"))
        if n:
            return f"press backspace {n} times"
    if _has(t, r"^(?:please\s+)?undo\b(?!\s+(?:the\s+)?(?:delete|move|rename|install))") and len(t.split()) <= 6:
        return "undo"
    if _has(t, r"^(?:please\s+)?redo\b") or _has(t, r"\bredo\s+what\b|\bput\s+back\s+what\s+i\s+undid\b"):
        return "redo"
    if re.fullmatch(r"(?:please\s+)?paste(?:\s+(?:it|that|this))?(?:\s+(?:here|there|in\s+here))?", t):
        return "paste"
    m = re.fullmatch(r"(?:make|convert|change|turn)\s+(?:all\s+of\s+it|everything|it|that|this|the\s+text|all\s+of\s+(?:this|that))\s+(?:into\s+|to\s+)?(?P<c>upper\s*case|lower\s*case|capital\w*|caps)", t)
    if m:
        return "make that uppercase" if _has(m.group("c"), "upper|capital|caps") else "make that lowercase"
    if _has(t, r"^(?:please\s+)?select\s+(?:all|everything)\b"):
        return "select all"
    return None


_WHEN = r"(?:today|tomorrow|tonight|yesterday|this\s+week|next\s+week|this\s+weekend|this\s+month|next\s+month|monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
_WHO = r"(?P<w>[a-z][a-z0-9&.' -]{1,24}?)"


def _strip_det(x: str) -> str:
    return re.sub(r"^(?:the|my|our|a|an)\s+", "", x.strip())


def _mail(t: str) -> str | None:
    if not _has(t, r"\b(?:emails?|inbox|gmail|mail|mails)\b|\bsent\s+me\b|\bexpecting\b"):
        return None
    if _has(t, r"\b(?:compose|draft|write|reply|forward|delete|archive|spam|password|account|event|create|calendar|is\s+open|opened)\b|\.\w{2,4}\b"):
        return None
    m = re.search(rf"\bfrom\s+{_WHO}(?:\s+(?:yet|today|please|now|since\s+\w+)|$)", t)
    who = _strip_det(m.group("w")) if m else ""
    m2 = re.fullmatch(rf"(?:has|did|have)\s+(?:the\s+)?{_WHO}\s+(?:sent|send|emailed|mailed|written)\s+(?:me\s+)?(?:anything|any\s+\w+|the\s+[a-z ]+?)(?:\s+yet|\s+today)?", t)
    if m2 and not who:
        who = _strip_det(m2.group("w"))
    if not who:
        m3 = re.search(rf"\bexpecting\s+(?:an?\s+|the\s+)?[a-z ]+?\s+from\s+{_WHO}$", t)
        who = _strip_det(m3.group("w")) if m3 else ""
    unread = _has(t, r"\b(?:unread|new|unseen|fresh)\b|\bhow\s+many\b|\bsince\b|\bany(?:thing)?\s+new\b")
    if who and not _has(who, r"\b(?:inbox|gmail|my|me)\b"):
        return f"show unread emails from {who}" if unread else f"any emails from {who}"
    if _has(t, r"\b(?:pull\s+up|open|show|check|see|go\s+to|bring\s+up)\b.*\binbox\b|\binbox\b.*\b(?:open|show)\b") and not _has(t, r"\bunread\b"):
        return "show my latest emails"
    if unread and _has(t, r"\b(?:emails?|mails?|gmail|inbox)\b"):
        return "show my unread emails"
    if _has(t, r"\b(?:latest|recent|newest|last)\b") and _has(t, r"\b(?:emails?|mails?)\b"):
        return "show my latest emails"
    return None


def _calendar(t: str) -> str | None:
    if not _has(t, r"\b(?:calendar|calender|schedule|agenda|meetings?|appointments?|events?)\b|\bmy\s+(?:week|day)\s+look\b"):
        return None
    if _has(t, r"\b(?:add|create|schedule\s+a|book|set\s+up|put|new|cancel|delete|move|reschedule|invite|that|write|wirte|whatsapp|here|scheduled|shceduled|schedul\w*|jobs|tasks|every|project|projects|file|files|folder|doc|document|link|app|related|relevant)\b"):
        return None
    if _has(t, r"\bto\s+(?:my\s+)?(?:calendar|calender)\b|\bat\s+\d|\|"):
        return None
    if not _has(t, r"^(?:what|which|show|list|any|do\s+i|have\s+i|how\s+(?:does|do\s+i\s+look|is|busy)|tell\s+me\s+(?:what|my)|read|check|see|open|calendar|calender|my|today|tomorrow|get)\b|\bon\s+(?:my|the|today'?s)\b") \
            or _has(t, r"\b(?:say|translate|mean|hindi|tamil|english|word|spell)\b"):
        return None
    if _has(t, r"\bweek\b") and _has(t, r"\bnext\b"):
        w = "next week"
    elif _has(t, r"\b(?:this\s+)?week\b"):
        w = "this week"
    else:
        m = re.search(rf"\b({_WHEN})\b", t)
        w = m.group(1) if m else "today"
    if _has(t, r"\b(?:meetings?|events?|appointments?|calendar|schedule|agenda)\b|\bweek\s+look\b|\bday\s+look\b"):
        return f"what's on my calendar {w}"
    return None


def _whatsapp_read(t: str) -> str | None:
    if _has(t, r"\b(?:send|reply|tell|text|message\s+\w+\s+(?:that|saying)|forward|delete|mute|auto)\b") and not _has(t, r"\bdid\b"):
        return None
    m = re.fullmatch(rf"(?:did|has|have)\s+{_WHO}\s+(?:message|messaged|text|texted|write|wrote|ping|pinged|reply|replied|call|called)\s*(?:me|us)?(?:\s+(?:today|yet|lately|recently|already|this\s+morning))?", t)
    if m and _has(m.group("w"), r"^(?:amma|appa|[a-z]{3,})$") and m.group("w") not in ("anyone", "anybody", "someone", "everyone", "any", "you"):
        return f"read whatsapp messages from {_strip_det(m.group('w'))}"
    if _has(t, r"\b(?:anyone|anybody|someone|people)\b") and _has(t, r"\b(?:waiting|urgent|new|unread|pending|messaged|texted|need\s+to\s+(?:answer|reply)|still\s+need)\b") \
            and _has(t, r"\b(?:whatsapp|messages?|texts?|chats?|me)\b") and not _has(t, r"\b(?:email|mail|calendar|call|file)\b"):
        return "read my unread whatsapp messages"
    if _has(t, r"\bany\s+messages?\b.*\b(?:answer|reply|respond)\b|\bwho\s+is\s+waiting\b"):
        return "read my unread whatsapp messages"
    if _has(t, r"\b(?:catch\s+me\s+up|fill\s+me\s+in|summar\w+|what'?s\s+(?:going\s+on|happening))\b") and _has(t, r"\b(?:whatsapp|group|chat|messages?)\b|\bkeeps\s+texting\b") \
            and not _has(t, r"\b(?:save|store|put|add|write|into|notes?|memo|file|doc|document|email|mail|pdf)\b") \
            and not _has(t, r"\b(?:that|this|the)\s+(?:message|text)\b|\bthat\b|\bgroups?\b"):
        return "summarize my whatsapp messages"
    if _has(t, r"\bhow\s+many\s+messages\b.*\b(?:each|every|per)\b"):
        return "summarize my whatsapp messages"
    return None


def _lists(t: str) -> str | None:
    if _has(t, r"\.\w{2,4}\b|^(?:open|launch|start|close)\b|\bmanager\b|\bmnaager\b|\b(?:duplicate|copy|move|rename|desktop|folder|file|files)\b|"
              r"\b(?:running|progress|skipped|result|current|previous|last|cancel\w*)\b.*\btask\b|\btask\b.*\b(?:running|progress|skipped|result)\b|^what\s+(?:does|do)\b"):
        return None
    if _has(t, r"\b(?:to-?do|todo)\b|\b(?:my|the)\s+tasks?\b(?!\s+manager)|\btasks?\s+list\b|\blaundry\s+task\b|\b[a-z]+\s+task\b(?<!manager task)") \
            and not _has(t, r"\b(?:add|create|new|remind|manager)\b"):
        if _has(t, r"\b(?:left|pending|remaining|outstanding|open|due|what|show|list|read|see)\b") and not _has(t, r"\b(?:done|finished|complete\w*)\b"):
            return "show my todo list"
        m = re.search(r"\b(?:finished|completed|done\s+with|did)\s+(?:the\s+)?(?P<x>[a-z ]{2,30}?)(?:\s+task)?$", t)
        if m and _has(t, r"\b(?:already|just|i)\b"):
            return f"mark the {m.group('x').strip()} task as done"
        if _has(t, r"\b(?:clear|remove|delete|clean)\b.*\b(?:completed|done|finished)\b"):
            return "clear completed tasks"
    if _has(t, r"\breminders?\b") and _has(t, r"\b(?:pending|left|upcoming|still|active|which|what|show|list)\b") and not _has(t, r"\b(?:set|add|create|new|remind\s+me)\b"):
        return "show my reminders"
    if _has(t, r"\bmemos?\b") and _has(t, r"\b(?:show|list|see|recent|latest|open|my)\b") and not _has(t, r"\b(?:create|add|new|search|find)\b"):
        return "recent memos"
    return None


def _history(t: str) -> str | None:
    if _has(t, r"\b(?:forget|delete|erase|remove|clear|remember)\b"):
        return None
    if _has(t, r"\b(?:what|which|show|list)\b.*\b(?:asking|asked|told|commands?|requests?|said|gave|did\s+i\s+(?:ask|tell|say))\b.*\b(?:today|earlier|lately|so\s+far|you|last|recent\w*)\b") \
            or _has(t, r"\bwhat\s+(?:have\s+i|did\s+i)\s+(?:been\s+)?(?:asking|ask|tell|told)\b"):
        return "what did i ask you today"
    if _has(t, r"\bwhat\s+(?:did|have)\s+(?:you|u)\s+(?:do|done|been\s+doing)\b|\bwhat\s+was\s+(?:your|the)\s+last\s+(?:action|thing)\b|\bwhat\s+did\s+(?:you|u)\s+do\s+last\b|\bwat\s+did\s+u\s+do\b"):
        return "what did you do last"
    if _has(t, r"^(?:did|has|was)\s+(?:that|it|the\s+last\s+(?:thing|one|command|action))\s+(?:last\s+)?(?:thing\s+)?(?:work|go\s+through|succeed|worked|succeeded|fail|failed|happen)(?:ed)?$"):
        return "did that work"
    if _has(t, r"\bwho\b.*\b(?:got|received|gets|has)\b.*\b(?:that|the\s+last|my\s+last)\s+(?:message|text|one)\b"):
        return "who did you send that to"
    if _has(t, r"\bwho\b.*\b(?:did|was)\b.*\b(?:that|the\s+last)\b.*\b(?:go\s+to|sent\s+to|message)\b"):
        return "who did you send that to"
    return None


_FOLDERS = r"(?P<f>desktop|downloads?|documents?|pictures?|music|videos?)"


def _files(t: str) -> str | None:
    m = re.fullmatch(rf"(?:what|which)\s*(?:files|stuff|things|items|folders)?\s*(?:are\s+)?(?:sitting\s+|lying\s+|present\s+|stored\s+)?(?:in|on|inside|under)\s+(?:my\s+|the\s+){_FOLDERS}(?:\s+folder)?", t) \
        or re.fullmatch(rf"(?:list|show|display|see)\s+(?:me\s+)?(?:all\s+)?(?:the\s+)?(?:files|stuff|things|items)\s+(?:in|on|inside)\s+(?:my\s+|the\s+){_FOLDERS}(?:\s+folder)?", t)
    if m:
        f = m.group("f").rstrip("s").capitalize() + ("s" if m.group("f").startswith(("download", "document", "picture", "video")) else "")
        return f"show what is on my {m.group('f')}"
    if _has(t, r"\b(?:focus|cursor|mouse|pointer|selection|slider|window|tab|cell|row|column|line|paragraph)\b"):
        return None
    m = re.fullmatch(r"(?:move|shift|transfer|relocate|put|send)\s+(?:the\s+|my\s+)?(?P<x>[\w .()-]+?(?:\.\w{2,4}|\s(?:photo|pic|picture|image|pdf|file|invoice|report|doc|document|screenshot|resume|video|song|folder))\b)\s+(?:from\s+(?:my\s+|the\s+)?\w+\s+)?(?:over\s+)?(?:in)?to\s+(?:my\s+|the\s+)?(?P<d>[\w ]+?)(?:\s+folder)?", t)
    if m and _has(m.group("d"), r"^(?:desktop|downloads?|documents?|pictures?|music|videos?|\w+\s*\w*)$") and not _has(m.group("x"), r"\b(?:phone|mobile)\b|\bme\b") \
            and not _has(m.group("d"), r"\b(?:phone|mobile|trash|bin|cloud|drive|me|whatsapp)\b"):
        return f"move {m.group('x').strip()} to {m.group('d').strip()}"
    return None


_REM_HEAD = re.compile(r"^(?:rember|remeber|remmber|remembr|remember)\b\s+(?P<x>.+)$")


def _memory(t: str) -> str | None:
    m = re.match(r"^(?:jot|write|note|put)\s+(?:this\s+|that\s+)?(?:idea\s+|thought\s+)?down\b\s*[:,-]?\s*(?P<x>.+)$", t) \
        or re.match(r"^(?:not|note|noat)\s+down\s*[:,-]?\s*(?P<x>.+)$", t)
    if m:
        return f"note down {m.group('x')}"
    m = _REM_HEAD.match(t)
    if m:
        return f"remember {m.group('x')}"
    m = re.match(r"^i\s+(?:always\s+|keep\s+)?forget\s+(?P<k>[a-z' ]{3,40}?)\s*,\s*(?:it'?s|it\s+is|its)\s+(?P<v>.+)$", t)
    if m:
        k = re.sub(r"^my\s+", "", m.group("k"))
        return f"remember my {k} is {m.group('v')}"
    if _has(t, r"\b(?:wipe|erase|drop|remove|delete)\b.*\b(?:fact|memory|remembered)\b.*\b(?:about|of)\b|\bforget\s+(?:the\s+)?fact\b"):
        x = re.sub(r"^.*?\b(?:about|of)\s+", "", t)
        return f"forget {re.sub(r'\s*from\s+memory$', '', x)}"
    if _has(t, r"^(?:wer|where|wher)\s+did\s+i\s+(?:keep|put|leave|store)\b"):
        return re.sub(r"^(?:wer|wher)\b", "where", t)
    return None


def _batch2(t: str) -> str | None:
    for fn in (_mail, _calendar, _whatsapp_read, _lists, _history, _files, _memory):
        out = fn(t)
        if out:
            return out
    return None


_SCHEDULED = re.compile(r"^(?:in|after|at|every|on|run\s+at|run)\s+\w*\s*\d|\||^in\s+(?:an?|one|two|three|five|ten|half)\b|\b(?:in|after)\s+\d+\s+(?:minutes?|mins?|hours?|seconds?|days?)\b")
_META = re.compile(r"^(?:how\s+(?:do|does|can|would)\b.*\bwork|(?:does|do|is|are)\b.*\b(?:let|allow|support|work|works|possible|able)\b|can\s+(?:you\s+)?remember\s+things|what\s+(?:does|do|is)\b.*\b(?:do|mean|means)\b)")


def rewrite(text: str) -> str | None:
    t = " ".join((text or "").lower().split()).strip(" .!?")
    for _ in range(3):
        t = re.sub(r"^(?:(?:hey|hi|ok|okay)\s+)?jarvis\s*[,.!:]?\s+|^(?:um+|uh+|hmm+|so|well|alright|quick\s+question)\s*,?\s+|"
                   r"^(?:(?:can|could|would|will)\s+(?:you|u)\s+(?:please\s+|kindly\s+)?|please\s+|kindly\s+)", "", t)
        t = re.sub(r"\s*,?\s+(?:jarvis|please|pls|thanks|thank\s+you|for\s+me|now|right\s+now|quickly|real\s+quick)$", "", t)
    if not t or len(t.split()) > 14 or _NEG.search(t):
        return None
    if _SCHEDULED.search(t) or _META.search(t):
        return None
    if (text or "").strip().endswith("?") and re.match(r"^(?:(?:can|could|would|will)\s+(?:you|u)\s+)?(?:remember|forget|save|store|keep)\b", " ".join((text or "").lower().split())):
        return None      # a question about the assistant's abilities is not an instruction
    if _CONTENT.search(t):
        r0 = repair(t)
        return _whatsapp_read(r0) if re.match(r"^(?:did|has|have)\b", r0) else None
    r = repair(t)
    fns = (_levels_status, _phone_toggle, _call, _clipboard, _speech, _browser, _snap, _text_edit, _batch2)
    if re.search(r"\b(?:and|then|after\s+that|also|plus)\b|,", r):
        fns = (_phone_toggle,)       # a longer plan is the planner's; only "turn on wifi and bluetooth on the phone" is one shape
    for fn in fns:
        try:
            out = fn(r)
        except Exception:
            out = None
        if out:
            return out
    return None


# ------------------------------------------------------------------------------------------------------- global repair
_GLOBAL: dict | None = None


def _skeleton(w: str) -> str:
    return w[0] + re.sub(r"[aeiou]", "", w[1:]) if w else w


def _global_vocab() -> dict:
    """Command vocabulary with a rough frequency: router words, capability keywords and ids, this module's vocabulary."""
    global _GLOBAL
    if _GLOBAL is not None:
        return _GLOBAL
    from collections import Counter
    c: Counter = Counter()
    try:
        from jarvis.core.router.normalize import COMMAND_VOCAB
        for w in COMMAND_VOCAB:
            c[w] += 3
    except Exception:
        pass
    for w in _VOCAB:
        c[w] += 3
    try:
        from jarvis.core.capabilities.registry import get_default_capability_registry
        reg = get_default_capability_registry()
        for cap in getattr(reg, "_capabilities", {}).values():
            for k in list(cap.keywords) + [cap.id.replace(".", " ").replace("_", " ")]:
                for w in re.findall(r"[a-z]{3,}", k.lower()):
                    c[w] += 1
    except Exception:
        pass
    try:
        import yaml
        from pathlib import Path
        data = yaml.safe_load((Path(__file__).with_name("intents.yaml")).read_text(encoding="utf-8")) or {}
        for it in (data.get("intents") if isinstance(data, dict) else data) or []:
            for k in (it.get("examples") or []) + (it.get("keywords") or []):
                for w in re.findall(r"[a-z]{3,}", str(k).lower()):
                    c[w] += 1
    except Exception:
        pass
    from jarvis.core.router.normalize import _english_word
    for w, n in list(c.items()):      # inflections of command words that are themselves real words: "speaking", "screenshots"
        if len(w) >= 4 and w.isalpha():
            stem = w[:-1] if w.endswith("e") else w
            for form in (w + "s", stem + "ing", stem + "ed", w + "ing"):
                if form not in c and _english_word(form):
                    c[form] = max(1, n // 3)
    # words only seen in capability descriptions are not command words: keep the curated ones and keywords/examples
    for w in [w for w, n in c.items() if n == 1 and w not in _VOCAB and not _english_word(w)]:
        del c[w]
    _GLOBAL = dict(c)
    return _GLOBAL


_NO_REPAIR = frozenset("not nor yet via per rite rit tho tht thx pls plz ok okay hmm umm yeah yep nope bye wat wen wer hw sry sorry gonna wanna gimme lemme alfa beta alpha gamma".split())


def _inflection_of_vocab(w: str, vocab: dict) -> bool:
    for suf in ("ed", "d", "ing", "es", "s", "er", "ers", "ly"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            stem = w[: -len(suf)]
            if stem in vocab or stem + "e" in vocab or (len(stem) > 3 and stem[-1] == stem[-2] and stem[:-1] in vocab):
                return True
    return False


def global_repair(text: str) -> str:
    """Repair misspelt command words anywhere in a command by spelling distance or consonant skeleton, preferring the
    commonest command word. Ordinary English words, short words and the owner's own words are left alone."""
    from jarvis.core.router.normalize import _edit_distance, _english_word
    vocab = _global_vocab()
    t = " ".join(text.lower().split())
    for pat, rep in _JOINS:
        t = re.sub(pat, rep, t)
    out = []
    by_skel: dict[str, list[str]] = {}
    for v in vocab:
        if len(v) >= 3 and v.isalpha():
            by_skel.setdefault(_skeleton(v), []).append(v)
    for w in t.split():
        core = w.strip(".,!?;:'\"")
        tail = w[len(core):] if w.startswith(core) else ""
        if core in _ALIASES:
            out.append(_ALIASES[core] + tail)
            continue
        if not core.isalpha() or len(core) < 2 or core in vocab or core in _SKIP_REPAIR or core in _NO_REPAIR or _english_word(core):
            out.append(w)
            continue
        from jarvis.core.router.canonical import _known_app
        if _known_app(core):                                         # an app name is never a misspelling ("sharex")
            out.append(w)
            continue
        if _inflection_of_vocab(core, vocab):       # "deleted", "opened", "files": a real inflection, not a misspelling
            out.append(w)
            continue
        cands: list[tuple[int, int, str]] = []
        sk = _skeleton(core)
        for v in by_skel.get(sk, []):
            if abs(len(v) - len(core)) <= 3:
                d0 = _edit_distance(core, v)
                if len(core) >= 5 or d0 <= 1:         # a four-letter word two edits away is more likely another word
                    cands.append((d0, -vocab[v], v))
        if len(core) >= 4:
            for v in vocab:
                if v[0] == core[0] and abs(len(v) - len(core)) <= 2 and v.isalpha() and len(v) >= 4:
                    d = _edit_distance(core, v)
                    if d <= (1 if len(v) <= 6 else 2):
                        cands.append((d, -vocab[v], v))
        if cands:
            cands.sort()
            if len(core) >= 3 or cands[0][0] <= 1:
                out.append(cands[0][2] + tail)
                continue
        out.append(w)
    return " ".join(out)


def alternates(text: str) -> list[str]:
    """Other wordings of an unresolved request, most conservative first: a recognised paraphrase shape, then the same
    after spelling repair, then the spelling-repaired request itself."""
    t = " ".join((text or "").split())
    outs: list[str] = []
    r1 = rewrite(t)
    if r1:
        outs.append(r1)
    try:
        g = global_repair(t)
    except Exception:
        g = t
    if g and g != t.lower():
        r2 = rewrite(g)
        if r2 and r2 not in outs:
            outs.append(r2)
        if g not in outs:
            outs.append(g)
    return outs


def precise(text: str) -> str | None:
    """A recognised paraphrase shape (high precision): used before the general rules so a loose pattern cannot claim it."""
    try:
        return rewrite(text)
    except Exception:
        return None


def fallbacks(text: str) -> list[str]:
    """Wordings to try only when the rules found nothing: the spelling-repaired request, with and without a paraphrase shape."""
    t = " ".join((text or "").split())
    outs: list[str] = []
    try:
        g = global_repair(t)
    except Exception:
        return outs
    if g and g != t.lower():
        r2 = rewrite(g)
        if r2:
            outs.append(r2)
        outs.append(g)
    return outs
