"""Sentence constructions -> the one canonical wording the deterministic router already understands.

The router's rules know "open X", "close X", "set the volume to N". People say the same thing in many shapes, so this
module rewrites *constructions*, never particular sentences:

    synonym verbs          "gimme X", "fire up X", "load X", "get X going"          -> "open X"
                           "kill X", "terminate X", "exit X", "force close X"       -> "close X"
    subject first          "X is stuck, kill it", "I'm done with X, close it"       -> "close X"
    modal / question       "can the volume be 40", "could you bump the volume to 40" -> "set the volume to 40"
    elided second verb     "set volume to 40 and brightness to 60"                   -> "... and set brightness to 60"
    trailing filler        "open X again like last time", "... as usual"            -> "open X"
    spoken output          "say the time out loud"                                   -> "tell me the time"

A rewrite only fires when its whole shape matches, and never on a command that carries the owner's own words (a
message, typed text, a note), so content is never changed. App-like objects must look like an app (a known name or a
short name before "going / running / open").
"""
from __future__ import annotations

import re

_DEVICE_OR_PC = r"(?:pc|computer|laptop|system|machine|windows|phone|mobile|everything|all|it|this|that)"
_SETTING = r"(?:the\s+)?(?:volume|sound|brightness|screen\s+brightness)"
_NUM = r"(?P<n>\d{1,3})\s*(?:%|percent|per\s*cent)?"
_CONTENT = re.compile(r"\b(?:send|text|message|msg|tell|type|write|dictate|note|remind|reply|email|mail|say\s+(?!the\s+time|the\s+date))\b")


def _known_app(name: str) -> bool:
    try:
        from jarvis.core.router.normalize import APP_ALIASES, _app_names
        from jarvis.core.router.slots import APP_CANONICAL
    except Exception:
        return False
    n = name.strip().lower()
    return n in _app_names() or n in APP_ALIASES or n in APP_CANONICAL


def _app_like(x: str, *, strong: bool) -> bool:
    """A plausible app name: known, or (with a strong cue such as "running") one to three plain words."""
    x = x.strip().lower()
    if not x or re.fullmatch(_DEVICE_OR_PC, x) or re.match(r"(?:the|my|a|an|some|this|that)\s", x):
        return _known_app(re.sub(r"^(?:the|my)\s+", "", x))
    return _known_app(x) or (strong and bool(re.fullmatch(r"[a-z][\w.+-]*(?:\s+[a-z][\w.+-]*){0,2}", x)))


def canonicalize(text: str) -> str:
    """The canonical command for a known construction, or the text unchanged."""
    raw = " ".join((text or "").split())
    t = raw.lower().rstrip(" .!?")
    if not t or len(t) > 160:
        return raw
    # wake word, fillers and courtesy around the command are not part of its shape
    for _ in range(3):
        t = re.sub(r"^(?:(?:hey|hi|ok|okay)\s+)?jarvis\s*[,.!:]?\s+|^(?:um+|uh+|hmm+|so|okay|ok|well|alright|quick\s+question)\s*,?\s+",
                   "", t)
        t = re.sub(r"\s*,?\s+(?:jarvis|please|pls|thanks|thank\s+you|for\s+me|(?<!from\s)(?<!till\s)(?<!until\s)(?<!by\s)(?:right\s+)?now)$",
                   "", t)
        t = re.sub(r"^(?:(?:can|could|would|will)\s+you\s+(?:please\s+|kindly\s+)?|please\s+|kindly\s+)", "", t)
        t = re.sub(r"\s*,\s*(?:yeah|yep|yes|okay|ok|right|alright|eh|will\s+you|would\s+you)$", "", t)       # a tag question: "get rid of that file, yeah?"

    # trailing filler that never changes the command
    t2 = re.sub(r"\s+(?:again\s+)?(?:like\s+(?:last\s+time|before|usual|always)|as\s+(?:usual|always|before))$", "", t)
    tail_dropped = t2 != t and not _CONTENT.search(t2)
    if tail_dropped:
        t = t2
    # "email arun that the report is ready": the frame is rewritten, the owner's words are kept as said
    m = re.match(r"^(?:e-?mail|mail)\s+(?P<p>[a-z][\w'-]{1,20})\s+(?:that|saying|to\s+say)\s+(?P<m>\S.*)$", t)
    if m and m.group("p") not in ("me", "it", "this", "that", "them"):
        i = raw.lower().find(m.group("m"))
        return f"draft an email to {m.group('p')} saying {raw[i:i + len(m.group('m'))] if i >= 0 else m.group('m')}"
    # "tell me where temp_test.txt is", "where did i save my resume pdf": locating one of the owner's files is a file search;
    # "where is chennai" stays a question (only a file-like object - extension or file word - is searched for)
    m = re.match(r"^(?:(?:can\s+you\s+)?(?:tell|show)\s+me\s+|do\s+you\s+know\s+|any\s+idea\s+)?where\s+"
                 r"(?:(?:is|are)\s+(?P<a>.+?)|(?P<b>.+?)\s+(?:is|are)|did\s+i\s+(?:save|put|keep|download|store)\s+(?P<c>.+?))"
                 r"(?:\s+(?:saved|stored|kept|located))?$", t)
    if m:
        obj = (m.group("a") or m.group("b") or m.group("c") or "").strip()
        from jarvis.core.semantics.resources import FILE, FOLDER, parse_path_ref
        if obj and parse_path_ref(obj).kind in (FILE, FOLDER) and len(obj.split()) <= 6:
            return f"find {obj}"
    # "write back to vignesh telling him the notes are in the drive", "get back to priya saying ok": a reply
    m = re.match(r"^(?:write|get|text|message|reply|respond|answer)\s+back\s+to\s+(?P<p>[a-z][\w'-]{1,20})\s+(?:telling|saying|to\s+say|"
                 r"that|and\s+(?:tell|say))\s+(?:(?:him|her|them)\s+)?(?:that\s+)?(?P<m>\S.*)$", t)
    if m:
        i = raw.lower().find(m.group("m"))
        j = raw.lower().find(m.group("p"))
        who = raw[j:j + len(m.group("p"))] if j >= 0 else m.group("p")
        return f"reply to {who} saying {raw[i:i + len(m.group('m'))] if i >= 0 else m.group('m')}"
    # "kavya's been waiting on my reply since morning": the owner owes a reply - draft it (sending is still confirmed)
    m = re.match(r"^(?P<p>[a-z][\w-]{1,20})(?:'s|\s+has|\s+is|\s+have)\s+(?:been\s+)?waiting\s+(?:on|for)\s+(?:my\s+|a\s+)?"
                 r"(?:reply|response|answer|message)\b", t)
    if m and m.group("p") not in ("he", "she", "it", "who", "everyone", "someone", "that", "this", "there"):
        j = raw.lower().find(m.group("p"))
        return f"reply to {raw[j:j + len(m.group('p'))] if j >= 0 else m.group('p')}"
    # "fire the same note off to Mala and Revathi", "shoot 'on my way' off to Arun": send
    m = re.match(r"^(?:fire|shoot|zap)\s+(?P<x>.+?)\s+off\s+to\s+(?P<r>[a-z][a-z' ,&-]{1,60})$", t)
    if m:
        j = raw.lower().find(m.group("x")); k = raw.lower().rfind(m.group("r"))
        body = raw[j:j + len(m.group("x"))] if j >= 0 else m.group("x")
        who = raw[k:k + len(m.group("r"))] if k >= 0 else m.group("r")
        return f"send {body} to {who}"
    # "bin the scratch file", "throw away screenshot_0413", "chuck that old log into the bin": delete, for a file-like object
    m = re.match(r"^(?:bin|chuck|toss|junk|scrap|dump|trash|throw\s+away|throw\s+out|get\s+rid\s+of)\s+(?P<x>.+?)"
                 r"(?:\s+(?:in|into)\s+the\s+(?:bin|trash|recycle\s*bin|garbage|dustbin))?$", t)
    if m and re.search(r"\b(?:file|log|logs|installer|screenshot|screenshots|photo|pic|picture|image|doc|document|pdf|folder|download|video|song|invoice|report)\b|"
                       r"\.\w{2,4}\b|\b\w+_\d+\b|\bscreenshot_\w+", m.group("x")) \
            and not re.search(r"\b(?:phone|mobile|whatsapp|chat|email|mail|message)\b", m.group("x")):
        j = raw.lower().find(m.group("x"))
        return "delete " + (raw[j:j + len(m.group("x"))] if j >= 0 else m.group("x"))
    if _CONTENT.match(t):
        return raw
    # speech recognition often hears "open" as "on": "on calculator on chrome", "on notepad"
    m = re.match(r"^on\s+(?P<rest>[a-z][\w .+-]*)$", t)
    if m and (_known_app(re.split(r"\s+(?:on|in)\s+", m.group("rest"))[0].strip())
              or re.search(r"\s(?:on|in)\s+(?:chrome|edge|firefox|brave|(?:the\s+|my\s+)?browser)$", t)):
        return "open " + m.group("rest")
    # "announce it / let me know when nisha messages me": a watch
    m = re.match(r"^(?:announce(?:\s+it)?|let\s+me\s+know|alert\s+me|ping\s+me|tell\s+me|notify\s+me)\s+(?P<c>(?:when|whenever|if|as\s+soon\s+as)\s+.+)$", t)
    if m and not t.startswith("tell me when") and not t.startswith("notify me when"):
        return f"tell me {m.group('c')}"
    # "show what's in my documents"
    m = re.match(r"^(?:show|tell)\s+(?:me\s+)?what'?s\s+(?:in|inside)\s+(?:my\s+|the\s+)?(?P<f>downloads|documents|desktop|pictures|videos|music)"
                 r"(?:\s+folder)?$|^what'?s\s+(?:in|inside)\s+(?:my\s+|the\s+)?(?P<f2>downloads|documents|desktop|pictures|videos|music)(?:\s+folder)?$", t)
    if m:
        return f"list files in {m.group('f') or m.group('f2')}"
    # "show the commands i used for X"
    m = re.match(r"^(?:show|list|what\s+(?:are|were))\s+(?:me\s+)?(?:the\s+|my\s+)?(?:commands?|requests?|things)\s+i\s+(?:used|gave|said|ran|asked)"
                 r"(?:\s+(?:for|with|about)\s+(?P<x>.+))?$", t)
    if m:
        return f"show my command history for {m.group('x')}" if m.group("x") else "show my command history"
    # "show your recent actions"
    if re.fullmatch(r"(?:show|list|tell\s+me)\s+(?:me\s+)?(?:your|my|the)\s+(?:recent|last|latest)\s+(?:actions|activity|activities|steps)", t):
        return "what did you do recently"
    # "call meena": a phone call to a person (not "call it final", which names something)
    m = re.match(r"^(?:call|ring)\s+(?P<p>[a-z][\w'-]{1,20}(?:\s+[a-z][\w'-]{1,20})?)$", t)
    if m and not re.match(r"(?:it|this|that|them|him|her|me|back|the|a|an|my|up|off|out|for|on|in)\b", m.group("p")) \
            and not re.search(r"\b(?:wifi|wi-fi|bluetooth|data|hotspot|airplane|flight|mode|on|off|silent|dnd|volume|brightness|"
                              r"torch|flashlight|location|gps)\b", m.group("p")):
        return f"call {m.group('p')} on my phone"
    # "open the folder this file is in" / "open the containing folder"
    if re.fullmatch(r"(?:open|show)\s+(?:me\s+)?(?:the\s+)?(?:folder\s+(?:this|that|the)\s+(?:file|document|pdf|download)\s+is\s+in|"
                    r"(?:containing|parent)\s+folder(?:\s+of\s+(?:this|that|the)\s+(?:file|document|pdf|download))?)", t):
        return "open the containing folder"
    # "zoom in on the page"
    m = re.fullmatch(r"(zoom\s+(?:in|out))\s+(?:on\s+)?(?:the|this)\s+(?:page|website|site|tab|browser)", t)
    if m:
        return m.group(1)
    # polite opener before a rewritable command
    t = re.sub(r"^(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?|please\s+)(?=(?:gimme|give|fire|load|boot|spin|pull|bring|get|"
               r"kill|terminate|exit|quit|end|force|shut|bump|put|change|make|turn|crank|push|move|drop|take|adjust|keep|say|read|"
               r"open|visit|go|dim)\b)", "", t)
    # full screen is a mode, not an app: leaving it is the Escape key
    if re.fullmatch(r"(?:exit|leave|quit|close|get\s+out\s+of|turn\s+off|stop)\s+(?:the\s+)?full\s*-?\s*screen(?:\s+mode)?", t):
        return "press escape"
    # "no, cancel that" / "nah, never mind"
    if re.fullmatch(r"(?:no|nope|nah)\s*,?\s+(?:cancel|stop|scrap|drop)\s+(?:that|it|this)", t):
        return "cancel that"
    # British spellings the rules don't know: "summarise", "organise", "minimise"
    t = re.sub(r"\b(summar|organ|minim|maxim|custom|priorit|recogn|finali|categor)is(e|ed|es|ing)\b", r"\1iz\2", t)
    # install / update constructions
    m = re.fullmatch(r"(?:grab|get|download|fetch)\s+(?:the\s+)?(?P<x>[a-z][\w .+-]{1,30}?)\s+(?:from\s+(?:the\s+)?(?:internet|web|net|"
                     r"online)\s+)?and\s+(?:then\s+)?install\s+it", t)
    if m:
        return f"install {m.group('x')}"
    m = re.fullmatch(r"(?:get|grab|install|download)\s+(?:the\s+)?(?:latest|newest|new)\s+(?:version|update|release)\s+of\s+"
                     r"(?P<x>[a-z][\w .+-]{1,30})", t)
    if m:
        return f"update {m.group('x')}"
    # window constructions
    m = re.fullmatch(r"(?:get\s+rid\s+of|dismiss)\s+(?:the\s+)?(?P<x>[a-z][\w .+-]{1,30}?)\s+window", t)
    if m:
        return f"close the {m.group('x')} window"
    m = re.fullmatch(r"(?:shrink|hide|tuck\s+away)\s+(?:the\s+)?(?P<x>[a-z][\w .+-]{1,30}?)(?:\s+window)?", t)
    if m and _app_like(m.group("x"), strong=False):
        return f"minimize {m.group('x')}"
    m = re.fullmatch(r"(?:jump|hop|flip|go\s+over|swap)\s+(?:back\s+)?to\s+(?:the\s+)?(?P<x>[a-z][\w .+-]{1,30}?)(?:\s+window)?", t)
    if m and _app_like(m.group("x"), strong=False):
        return f"switch to {m.group('x')}"
    # find synonyms: "dig out my X", "locate X", "hunt down X"
    m = re.fullmatch(r"(?:dig\s+(?:out|up)|hunt\s+down|track\s+down|locate)\s+(?P<x>(?:my\s+|the\s+)?[a-z0-9][\w .()-]{1,60})", t)
    if m and not re.match(r"(?:my\s+)?(?:phone|mobile|laptop)$", m.group("x")):
        return f"find {m.group('x')}"
    # "open my <document>": a file of the owner's, not an app
    m = re.fullmatch(r"open\s+my\s+(?P<x>(?:[a-z]+\s+){0,3}(?:policy|statement|receipt|ticket|certificate|slip|bill|report|letter|"
                     r"itinerary|record|marksheet|resume|cv|invoice|agreement|scan|document|file|pdf))(?:\s+file)?", t)
    if m:
        return f"find my {m.group('x')}"
    # "take me to documents"
    m = re.fullmatch(r"(?:take|bring)\s+me\s+to\s+(?:my\s+|the\s+)?(?P<f>downloads|documents|desktop|pictures|videos|music)(?:\s+folder)?", t)
    if m:
        return f"open my {m.group('f')} folder"
    if re.fullmatch(r"show\s+(?:me\s+)?the\s+desktop|(?:go\s+)?(?:to|back\s+to)\s+the\s+desktop", t):
        return "show desktop"
    # web: reviews / prices, headlines
    m = re.fullmatch(r"(?:find|show|get|check)\s+(?:me\s+)?(?:the\s+)?(?P<k>reviews?|ratings?|prices?|specs|specifications)\s+(?:of|for)\s+(?P<x>.+)", t)
    if m and not re.search(r"\s(?:on|at|from|in)\s+(?:the\s+)?[\w.-]+(?:\.\w+)?$", m.group("x")):   # "... on amazon": the web agent
        return f"search the web for {m.group('k')} of {m.group('x')}"
    if re.fullmatch(r"(?:today'?s\s+|the\s+|top\s+|latest\s+)?(?:news\s+)?headlines(?:\s+(?:today|now))?|(?:what'?s\s+in\s+)?the\s+news\s+today|"
                    r"today'?s\s+news|top\s+news", t):
        return "latest news about today's headlines"
    # status questions
    if re.fullmatch(r"am\s+i\s+(?:plugged\s+in|charging|on\s+(?:battery|power|charge))|is\s+(?:my\s+|the\s+)?(?:laptop|pc|computer)\s+plugged\s+in", t):
        return "is the laptop charging"
    if re.fullmatch(r"how\s+much\s+(?:storage|disk\s+space|space|disk)\s+(?:do\s+i\s+have\s+)?(?:left|free|remaining)(?:\s+on\s+(?:my\s+)?(?:pc|laptop|computer|disk|drive))?", t):
        return "how much disk space is left"
    if re.fullmatch(r"how\s+much\s+(?:charge|battery|juice)\s+(?:does|has)\s+(?:my\s+)?(?:phone|mobile)(?:\s+(?:have|got|left))?(?:\s+left)?", t) \
            or re.fullmatch(r"how\s+much\s+(?:charge|battery|juice)\s+(?:is\s+)?(?:left\s+)?(?:on|in)\s+(?:my\s+|the\s+)?(?:phone|mobile)", t):
        return "phone battery level"
    # task control phrasings
    if re.fullmatch(r"(?:pause|hold|freeze)\s+(?:what|whatever)\s+you'?r?e?\s*(?:are\s+)?doing", t):
        return "pause the current task"
    if re.fullmatch(r"(?:never\s*mind|forget\s+it|scratch\s+that)\s*,?\s+(?:don'?t|do\s+not)\s+(?:send|do|run)\s+(?:it|that|this)", t):
        return "cancel that"
    # "when my battery hits 80 percent tell me" -> "tell me when ..."
    m = re.fullmatch(r"(?P<c>(?:when|once|as\s+soon\s+as)\s+.+?)\s*,?\s+(?:tell|notify|alert|ping)\s+me", t)
    if m:
        return f"tell me {m.group('c')}"
    # "launch camera on the phone"
    m = re.fullmatch(r"(?:launch|open|start)\s+(?:the\s+)?(?P<x>[a-z][\w+-]{1,20}(?:\s+[a-z][\w+-]{1,20})?)(?:\s+app)?\s+on\s+(?:my|the)\s+"
                     r"(?:phone|mobile)", t)
    if m and not re.search(r"\b(?:settings?|screen|recording|record|url|link|page|tab|this|that|it|file|photo|video|call|"
                           r"notification|mode|wifi|bluetooth|hotspot|location)\b", m.group("x")):
        return f"launch the {m.group('x')} app on my phone"
    # "I don't need report.pdf anymore, delete it"
    m = re.fullmatch(r"i\s+(?:don'?t|do\s+not)\s+(?:need|want)\s+(?P<f>[\w .()-]+\.[a-z0-9]{1,5})\s+(?:any\s*more|now)?\s*,?\s*(?:so\s+|please\s+|just\s+)*"
                     r"(?P<v>delete|remove|trash|bin)\s+it", t)
    if m:
        return f"delete {m.group('f')}"
    # device-setting shorthand: "phone wifi off", "my phone's bluetooth on"
    m = re.fullmatch(r"(?:my\s+)?(?:phone|mobile)(?:'s)?\s+(?P<x>wi-?fi|bluetooth|mobile\s+data|data|hotspot|torch|flashlight|location|"
                     r"airplane\s+mode|flight\s+mode|do\s+not\s+disturb|dnd)\s+(?P<s>on|off)", t)
    if m:
        return f"turn {m.group('s')} {m.group('x')} on my phone"
    # phone brightness: "dim my phone to 40%"
    m = re.fullmatch(rf"(?:dim|set|turn|make|put)\s+(?:my\s+|the\s+)?(?:phone|mobile)(?:'s)?(?:\s+(?:screen|brightness|screen\s+brightness))?\s+"
                     rf"(?:down\s+)?to\s+{_NUM}", t)
    if m:
        return f"set my phone brightness to {m.group('n')}"

    # open: synonym verbs and "get X going"
    m = re.match(r"^(?:gimme|give\s+me|fire\s+up|load(?:\s+up)?|boot\s+up|spin\s+up|pull\s+up|bring\s+up|"
                 r"(?:let'?s\s+)?get|(?:can|could|may)\s+i\s+(?:have|get))\s+(?:the\s+)?(?P<x>[a-z][\w .+-]{1,30}?)"
                 r"(?P<cue>\s+(?:going|running|started|open(?:ed)?|up(?:\s+and\s+running)?))?(?:\s+(?:please|now|for\s+me))?$", t)
    if m and _app_like(m.group("x"), strong=bool(m.group("cue"))):
        return f"open {m.group('x').strip()}"
    m = re.match(r"^i\s+(?:need|want|would\s+like)\s+(?P<x>[a-z][\w .+-]{1,30}?)\s+(?:open(?:ed)?|running|up)(?:\s+(?:please|now))?$", t)
    if m and _app_like(m.group("x"), strong=True):
        return f"open {m.group('x').strip()}"

    # close: synonym verbs
    m = re.match(r"^(?:kill|terminate|exit|quit|end|force\s+(?:close|quit|stop)|shut(?:\s+down)?)\s+(?:the\s+)?(?P<x>[a-z][\w .+-]{1,30}?)"
                 r"(?:\s+(?:app|application|program|window))?(?:\s+(?:for\s+now|please|now))?$", t)
    if m and _app_like(m.group("x"), strong=False) and not re.search(rf"\b{_DEVICE_OR_PC}$", m.group("x")):
        return f"close {m.group('x').strip()}"

    # subject first: "<X> is stuck / I'm done with X, <verb> it"
    m = re.match(r"^(?:i'?m\s+(?:done|finished)\s+with\s+|(?:the\s+)?)(?P<x>[a-z][\w .+-]{1,30}?)(?:\s+(?:is|keeps|has|won'?t|isn'?t|"
                 r"just|seems|looks|got)\b[^,]{0,40})?\s*[,;]\s*(?:so\s+|please\s+|just\s+|can\s+you\s+)*"
                 r"(?P<v>kill|close|quit|exit|force\s+close|shut|restart|relaunch|reopen|minimi[sz]e|maximi[sz]e)\s+it(?:\s+please)?$", t)
    if m and _app_like(m.group("x"), strong=True) and not re.search(rf"\b{_DEVICE_OR_PC}$", m.group("x")):
        verb = {"kill": "close", "quit": "close", "exit": "close", "force close": "close", "shut": "close",
                "reopen": "restart", "relaunch": "restart"}.get(m.group("v"), m.group("v"))
        return f"{verb} {m.group('x').strip()}"

    # settings: modal / question / synonym verbs
    m = re.match(rf"^(?:can|could|would)\s+(?:the\s+|my\s+)?(?P<w>volume|sound|brightness)\s+(?:be|go(?:\s+to)?)\s+(?:at\s+)?{_NUM}$", t) or \
        re.match(rf"^(?:(?:can|could|would)\s+you\s+)?(?:bump|put|change|make|turn|crank|push|move|bring|drop|take|adjust|keep|get)\s+"
                 rf"(?:the\s+|my\s+)?(?P<w>volume|sound|brightness)\s+(?:up\s+|down\s+)?(?:to|at)\s+{_NUM}$", t) or \
        re.match(rf"^(?:the\s+|my\s+)?(?P<w>volume|sound|brightness)\s+(?:to\s+|at\s+)?{_NUM}$", t)
    if m:
        what = "brightness" if m.group("w") == "brightness" else "volume"
        return f"set {what} to {m.group('n')}"

    # elided second verb: "set volume to 40 and brightness to 60"
    m = re.match(rf"^(?P<v>set|turn|change|make|put)\s+(?P<a>{_SETTING}\s+to\s+\d{{1,3}}\s*(?:%|percent)?)\s*(?:,\s*|\s+)(?:and\s+)?"
                 rf"(?P<b>{_SETTING}\s+to\s+\d{{1,3}}\s*(?:%|percent)?)$", t)
    if m:
        return f"{m.group('v')} {m.group('a')} and {m.group('v')} {m.group('b')}"

    # spoken output: "say / read the time out loud"
    m = re.match(r"^(?:say|tell\s+me|read(?:\s+out)?)\s+(?P<x>the\s+(?:time|date|weather)|today'?s\s+(?:date|calendar|schedule|agenda|"
                 r"weather)|my\s+(?:calendar|schedule|agenda|reminders|battery))(?:\s+(?:out\s+loud|aloud|for\s+me))?$", t)
    if m and m.group("x") != t:
        x = m.group("x")
        if re.search(r"calendar|schedule|agenda", x):
            return "what's on my calendar today"
        return f"tell me {x}" if x.startswith("the") else f"what's {x}"

    # alarms are reminders that wake you: "wake me up at 6", "set an alarm for 7 am" (not the phone's own alarm app)
    m = re.match(r"^(?:wake\s+me(?:\s+up)?|set\s+(?:an?\s+|my\s+)?alarm|alarm)\s+(?:for\s+|at\s+|by\s+)?(?P<w>(?:\d{1,2}(?::\d{2})?\s*"
                 r"(?:a\.?m\.?|p\.?m\.?)?|noon|midnight)(?:\s+(?:today|tomorrow|tonight))?|in\s+\d+\s+(?:minutes?|mins?|hours?))$", t)
    if m and not re.search(r"\b(?:phone|mobile)\b", t):
        w = m.group("w")
        return f"remind me {w} to wake up" if w.startswith("in ") else f"remind me at {w} to wake up"
    # questions about reminders and scheduled jobs are look-ups, never new ones
    if re.fullmatch(r"(?:what|which)\s+reminders\s+(?:do\s+i\s+have|have\s+i\s+(?:got|set)|are\s+(?:there|set|pending))(?:\s+(?:today|tomorrow))?"
                    r"|(?:do\s+i\s+have|have\s+i\s+got|are\s+there)\s+any\s+reminders(?:\s+(?:set|today|tomorrow|pending))?"
                    r"|what\s+are\s+my\s+reminders|any\s+reminders(?:\s+(?:today|tomorrow|set))?", t):
        return "show my reminders"
    if re.fullmatch(r"(?:show|list|what\s+are)\s+(?:me\s+)?(?:the\s+|my\s+|all\s+)?(?:scheduled|planned|pending)\s+(?:jobs|tasks|commands|actions)"
                    r"|what'?s\s+scheduled|(?:scheduled|planned)\s+(?:jobs|tasks|commands)", t):
        return "list my scheduled tasks"
    # "after 20 minutes pause the music": a delay, same as "in 20 minutes"
    m = re.match(r"^after\s+(?P<d>\d+\s+(?:seconds?|secs?|minutes?|mins?|hours?|hrs?))\s*,?\s+(?P<c>[a-z].+)$", t)
    if m:
        return f"in {m.group('d')} {m.group('c')}"
    # "go to the paint window": the window, not a website
    m = re.match(r"^(?:go|jump|switch(?:\s+over)?|move|take\s+me)\s+(?:back\s+)?to\s+(?:the\s+|my\s+)?(?P<x>[a-z][\w .+-]{1,30}?)\s+(?:window|app)$", t)
    if m and _app_like(m.group("x"), strong=True) and not re.match(r"(?:previous|last|other|next|old|first)\b", m.group("x")):
        return f"switch to {m.group('x').strip()}"
    m = re.match(r"^(?P<v>search|look|google)\s+(?:it\s+)?again\s+(?P<rest>(?:for|up)\s+.+)$", t)
    if m:
        return f"{m.group('v')} {m.group('rest')}"     # "search again for X": the same search verb, a new query
    if re.fullmatch(r"skip(?:\s+(?:it|that|this|this\s+one|this\s+song|this\s+track))?|skip\s+(?:to\s+)?(?:the\s+)?next(?:\s+one)?", t):
        return "next track"
    if re.fullmatch(r"(?:hey|hi|hello|hiya|yo)\s+(?:there|buddy|mate|friend)", t):
        return "hello"
    if re.fullmatch(r"am\s+i\s+(?:on|connected\s+to)\s+(?:the\s+)?(?:charger|charging|power|ac)|is\s+(?:the\s+)?charger\s+(?:connected|plugged\s+in|on)", t):
        return "is the laptop charging"
    if re.fullmatch(r"minimi[sz]e\s+(?:all|every|everything)(?:\s+(?:of\s+)?(?:my\s+|the\s+)?(?:open\s+)?windows)?", t):
        return "show the desktop"
    if re.fullmatch(r"(?:speed\s+up|quicken)\s+(?:your\s+)?(?:speech|voice|talking|speaking)|(?:speak|talk)\s+(?:a\s+bit\s+|a\s+little\s+)?quicker", t):
        return "talk faster"
    if re.fullmatch(r"(?:slow\s+down)\s+(?:your\s+)?(?:speech|voice|talking|speaking)", t):
        return "speak slower"
    if re.fullmatch(r"go\s+back(?:\s+(?:one|a|1)\s+page|\s+to\s+the\s+(?:previous|last)\s+page)?", t):
        return "go back a page"
    m = re.fullmatch(r"enter\s+(?P<x>(?!(?:full\s*screen|the\s+room|sleep|safe\s+mode|key|button|it|that)\b).{3,80})", t)
    if m and not re.search(r"\b(?:password|passcode|pin|otp|cvv|card)\b", m.group("x")):
        return f"type {m.group('x')}"

    # a bare website: "open zomato.com", "visit github.com"
    m = re.match(r"^(?:open|visit|load|go\s+to|show)\s+(?:the\s+)?(?:site\s+|website\s+)?(?P<d>[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|in|org|net|io|"
                 r"co|dev|ai|edu|gov|app|me)(?:/\S*)?)$", t)
    if m:
        return f"go to {m.group('d')}"

    # where is my <thing> -> find it (not a device, not an installed app)
    m = re.match(r"^where(?:'s|\s+is|\s+are|\s+did\s+i\s+(?:put|save|keep))\s+(?:my|the)\s+(?P<x>[a-z][\w .-]{2,40}?)(?:\s+(?:saved|stored|kept))?$", t)
    if m and not re.search(r"\b(?:phone|mobile|charger|keys?|wallet|laptop|pc|installed|defined|declared|function|class|method|variable|implemented)\b", m.group("x")):
        return f"find my {m.group('x')}"

    # no construction matched: the router sees exactly what was said (minus a filler tail that changes nothing)
    return t if tail_dropped else raw
