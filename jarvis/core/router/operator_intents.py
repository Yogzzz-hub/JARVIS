"""Operator semantic parser: verb class x object class -> one operator capability with typed slots.

It reads *what is acted on* (a window, a control, text in a field, a resource, a tab, the video, the IDE, the phone)
and *how* (focus, arrange, click, type, delete N units, paste/attach/send, seek, speed, watch ...). No sentence is
special-cased: each rule is a verb family applied to an object family, with ordinals, counts, times and references
as slots. It only claims requests it is sure about; everything else continues through normal routing. Negated
requests never reach it (the negation guard runs first), and nothing here executes - it only picks the capability.

Mode awareness: an ambiguous verb ("go back", "next", "scroll") is read against the app family in front (browser,
media, editor/IDE, phone session) only when the object is left implicit.
"""
from __future__ import annotations

import re
from contextvars import ContextVar
from typing import Optional

from jarvis.core.router.models import ComplexityLevel, ReasonCode, RouteDecision, RouteLane, RouteSource

_NUM = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
        "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
        "forty five": 45, "fifty": 50, "sixty": 60, "ninety": 90, "couple of": 2, "few": 3, "a couple of": 2,
        "a few": 3}
_ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
        "ninth": 9, "tenth": 10, "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5, "6th": 6, "7th": 7, "8th": 8,
        "9th": 9, "10th": 10, "last": -1, "top": 1, "next": 0}
_ORD_RE = "|".join(sorted(map(re.escape, _ORD), key=len, reverse=True))
_NUM_RE = r"\d+|" + "|".join(sorted(map(re.escape, _NUM), key=len, reverse=True))

# Object families ---------------------------------------------------------------------------------------------
_IDES = r"antigravity|anti\s?gravity|vs\s?code|vscode|visual studio code|cursor|windsurf|the ide|my ide|ide|code editor"
_APPS = (r"chrome|google chrome|edge|microsoft edge|firefox|brave|opera|notepad\+\+|notepad|word|excel|powerpoint|outlook|"
         r"vs\s?code|vscode|visual studio code|antigravity|cursor|windsurf|pycharm|explorer|file explorer|whatsapp|"
         r"telegram|slack|teams|discord|spotify|vlc|terminal|command prompt|powershell|settings|task manager|paint|"
         r"calculator|obsidian|sublime|zoom|youtube|gmail")
_FAMILY = (r"(?:text |code )?editor|browser|web browser|ide|media player|player|file manager|chat app|"
           r"previous (?:window|app)|last (?:window|app)|other (?:window|app)|old window|earlier window")
_WIN_WORDS = r"window|app|application|program|screen"
_ROLE = (r"button|btn|link|tab|checkbox|check box|toggle|switch|icon|menu item|menu|option|radio button|field|box|"
         r"input|text box|search bar|search box|dropdown|item|entry|row|result|thumbnail|tile")
_RESOURCE = (r"screenshot|screen shot|screengrab|screen grab|capture|snip|image|picture|photo|file|pdf|document|doc|"
             r"report|download|downloaded file|clip(?:board)?|copied text|link|url|answer|summary|text|it|that|this|them")
_UNITS = r"char(?:acter)?s?|letters?|words?|lines?|sentences?|paragraphs?"


def _d(rid: str, t: str, intent: Optional[str], slots: dict, lane: RouteLane = RouteLane.LANE_0,
       clarification: Optional[str] = None, risk: Optional[str] = None) -> RouteDecision:
    return RouteDecision(request_id=rid, lane=lane, intent=intent, slots=slots, confidence=0.95, source=RouteSource.EXACT,
                         complexity=ComplexityLevel.SIMPLE, normalized_text=t, clarification=clarification,
                         reason_code=ReasonCode.EXACT_PATTERN if lane != RouteLane.CLARIFY else ReasonCode.MISSING_REQUIRED_SLOT,
                         candidate_count=1, risk=risk)


def _n(word: str, default: int = 1) -> int:
    if not word:
        return default
    w = word.strip().lower()
    if w.isdigit():
        return int(w)
    return _NUM.get(w, _ORD.get(w, default))


def _raw(raw: str, piece: str) -> str:
    """The owner's own casing for a span the lower-cased text matched."""
    if not piece:
        return piece
    i = raw.lower().find(piece.lower())
    return raw[i:i + len(piece)] if i >= 0 else piece


def _surface(t: str) -> str:
    if re.search(r"\b(?:on|in|from|to)\s+(?:my|the)\s+(?:phone|mobile|android|cell)\b", t):
        return "phone"
    if re.search(rf"\b(?:in|on|inside)\s+(?:the\s+)?(?:{_IDES})\b", t):
        return "ide"
    if re.search(r"\b(?:on|in)\s+(?:this|the)\s+(?:page|site|website|tab)\b", t):
        return "browser"
    return "auto"


def _ide_name(t: str) -> str:
    m = re.search(rf"\b({_IDES})\b", t)
    if not m:
        return ""
    name = m.group(1).replace(" ", "")
    return {"antigravity": "antigravity", "vscode": "vs code", "visualstudiocode": "vs code", "theide": "",
            "myide": "", "ide": "", "codeeditor": ""}.get(name, name)


_VERBS = ("go switch return take bring jump flip head open launch start show make turn full screen maximize minimize "
          "restore snap move dock push arrange tile split paste attach drop insert upload send share transfer write type "
          "draft enter accept approve reject discard decline delete remove erase scratch clear select highlight copy cut "
          "capitalize uppercase lowercase replace change swap undo redo skip forward rewind seek speed slow faster slower "
          "captions subtitles restart replay loop click press tap check uncheck tick untick toggle scroll find search tell "
          "notify watch stop cancel previous window windows other second third fourth fifth first last result results link "
          "video videos screenshot download phone mobile prompt agent changes edits suggestions seconds minutes minute "
          "second hours automatically characters italic times watching installer updates refresh three four five "
          "seven eight third fifth phone paste refresh sidebar response discard skipping image")
_OP_VOCAB: frozenset[str] = frozenset(
    w for w in re.findall(r"[a-z]{4,}", " ".join((_IDES, _APPS, _FAMILY, _ROLE, _UNITS, _RESOURCE, _VERBS)))
)


def _repair(t: str) -> str:
    """Fix one-slip typos in the words this parser keys on ('ediotr' -> 'editor', 'atnigravity' -> 'antigravity').
    Real English words and anything not within one edit of exactly one vocabulary word are left alone."""
    from jarvis.core.router.normalize import _edit_distance, _english_word
    out, changed = [], False
    for w in t.split():
        if len(w) < 4 or not w.isalpha() or w in _OP_VOCAB or _english_word(w):
            out.append(w)
            continue
        if len(w) == 4:      # short words: only a dropped letter of a longer vocabulary word ("frst", "wrds", "phne")
            cands = [v for v in _OP_VOCAB if v[0] == w[0] and len(v) == 5 and _edit_distance(w, v) == 1]
        else:
            cands = [v for v in _OP_VOCAB if v[0] == w[0] and abs(len(v) - len(w)) <= 1 and _edit_distance(w, v) <= 1]
        if len(cands) > 1:   # prefer the word the typo drops a letter from ("miute" -> "minute", not "mute")
            longer = [v for v in cands if len(v) == len(w) + 1]
            cands = longer if len(longer) == 1 else cands
        if len(cands) == 1:
            out.append(cands[0])
            changed = True
        else:
            out.append(w)
    return " ".join(out) if changed else t


_STEP = (r"open|close|go|switch|take|paste|attach|send|delete|remove|erase|select|copy|cut|replace|type|write|click|press|"
         r"tap|play|pause|skip|rewind|jump|seek|turn|mute|unmute|maximi[sz]e|minimi[sz]e|restore|snap|put|move|find|search|"
         r"ask|read|scroll|save|undo|redo|accept|reject|show|list|start|stop|make|set|bring|return|capture|upload|share|"
         r"check|uncheck|zoom|refresh|reload|loop|restart|full ?screen|focus|tell me|let me know|notify me|split")
_CLAUSE = re.compile(rf"\s*(?:,\s*(?:and\s+|then\s+)?|\s+and\s+(?:then\s+)?|\s+then\s+)(?=(?:{_STEP})\b)")
_PAYLOAD_SLOTS = ("text", "find", "replace_with")
_NESTED: ContextVar[bool] = ContextVar("operator_nested", default=False)
_MESSAGE = re.compile(r"\b(?:tell|message|text|whatsapp|email|mail|reply|say|saying|send)\b")
_CORRECTION = re.compile(r"\b(?:no wait|wait|sorry|actually|i mean|instead|rather|scratch that)\b|\bno\s*,|\bnot\b")


def _clean(t: str) -> str:
    t = _repair(re.sub(r"\s+", " ", t).strip(" .!?"))
    t = re.sub(r"^(?:(?:hey |ok )?jarvis,?\s+)?(?:please |kindly |can you |could you |would you |pls )*", "", t)
    t = re.sub(r"\s+(?:please|for me|right now|now|quickly|pls)$", "", t)
    return re.sub(r"^tell me\s+(?=(?:what|which|how|is|are|where)\b)", "", t)


def _single(t: str, raw: str, rid: str, mode: str) -> Optional[RouteDecision]:
    for fn in (_window, _deliver, _ide, _text_edit, _video, _watch, _browser, _ui):
        d = fn(t, raw, rid, mode)
        if d is not None:
            # an object slot that swallowed a second step ("the second result in a new tab and find pricing") means
            # the rule read two commands as one: not this rule's request
            if any(isinstance(v, str) and k not in _PAYLOAD_SLOTS and _CLAUSE.search(" " + v)
                   for k, v in (d.slots or {}).items()):
                return None
            return d
    return None


def match_operator(t: str, raw: str, request_id: str, mode: str = "") -> Optional[RouteDecision]:
    """t: lower-cased routing text; raw: original wording; mode: app family in front ('' when unknown)."""
    t = _clean(t)
    if not t:
        return None
    d = _single(t, raw, request_id, mode)
    if d is not None:
        return d
    return _compound(t, raw, request_id, mode)


def _compound(t: str, raw: str, rid: str, mode: str) -> Optional[RouteDecision]:
    """'go back to my editor and delete the last word': every step parsed -> one deterministic step list (no model);
    an operator step mixed with a step that needs thinking -> the planner, with the operator tools available."""
    if _CORRECTION.search(t):
        return None
    if re.search(r"\b(?:and|then)\s+(?:then\s+)?(?:click|tap|press|select|open|toggle)\s+(?:on\s+)?(?:it|that|them)$", t):
        return None                                      # "find the wifi icon and click it": one located action
    parts = [p.strip(" ,") for p in _CLAUSE.split(t) if p.strip(" ,")]
    if not 2 <= len(parts) <= 5:
        return None
    from jarvis.core.router.models import SubCommand
    ops = [_single(p, raw, rid, mode) for p in parts]
    if not any(ops):
        return None                                      # no operator step: the normal router decides
    if _NESTED.get():
        return None
    from jarvis.core.router.extended import match_extended
    token = _NESTED.set(True)
    try:
        whole = match_extended(t, rid)
        if whole is not None and whole.lane == RouteLane.LANE_0 and whole.intent == "pc_quick_action":
            return None                                  # one action worded as two ("copy this and paste it in notepad")
        decisions = [d if d is not None else match_extended(p, rid) for d, p in zip(ops, parts)]
    finally:
        _NESTED.reset(token)
    if ops[0] is None and _MESSAGE.search(parts[0]):
        return None                                      # a message's own words ("tell mom ... and then call")
    if all(d is not None and d.lane == RouteLane.LANE_0 and d.intent for d in decisions):
        subs = [SubCommand(intent=d.intent, tool=d.intent, arguments=dict(d.slots or {})) for d in decisions]
        return RouteDecision(request_id=rid, lane=RouteLane.LANE_0, intent="compound",
                             slots={"steps": [s.tool for s in subs]}, confidence=0.95, source=RouteSource.EXACT,
                             complexity=ComplexityLevel.COMPOUND, risk="REVERSIBLE", normalized_text=t,
                             reason_code=ReasonCode.COMPOUND_COMMAND, subcommands=subs, candidate_count=len(subs))
    return RouteDecision(request_id=rid, lane=RouteLane.LANE_2, intent=None, slots={}, confidence=0.9,
                         source=RouteSource.COMPLEXITY_GATE, complexity=ComplexityLevel.COMPLEX, needs_planner=True,
                         normalized_text=t, reason_code=ReasonCode.MULTI_STEP, candidate_count=0)


# --------------------------------------------------------------------------------------------- windows
def _window(t, raw, rid, mode):
    # go back / switch back / return to <window or family or app>
    m = re.match(rf"^(?:go|switch|get|take me|bring me|jump|flip|return|head)\s+back(?:\s+(?:to|into))?\s+"
                 rf"(?P<x>(?:my|the|that)?\s*(?:{_FAMILY}|{_APPS})(?:\s+(?:{_WIN_WORDS}))?)$", t) or \
        re.match(rf"^(?:return|go back|back)\s+to\s+(?P<x>(?:my|the|that)?\s*(?:{_FAMILY}|{_APPS})(?:\s+(?:{_WIN_WORDS}))?)$", t)
    if m:
        x = m.group("x").strip()
        if re.match(r"^(?:the |my |that )?(?:previous|last|other|prior|earlier|old) (?:window|app|application|program)$", x):
            x = "previous"
        return _d(rid, t, "window_op", {"action": "focus", "target": x})
    if re.match(r"^(?:switch|go|flip|jump|toggle)\s+(?:back\s+)?to\s+(?:the\s+)?(?:previous|last|other|prior|earlier)\s+"
                r"(?:window|app|application|program)$|^(?:go|switch)\s+back$|^alt\s?tab$|^(?:switch|toggle)\s+back"
                r"(?:\s+and\s+forth)?$|^previous (?:window|app)$|^back to (?:the |my )?(?:previous|last|other) (?:window|app)$", t):
        if t in ("go back",) and mode in ("browser", "media", "phone"):
            return None
        return _d(rid, t, "window_op", {"action": "focus", "target": "previous"})
    # <open> X <state>: "open chrome full screen", "open notepad maximized"
    m = re.match(rf"^(?:open|launch|start|bring up|pull up|show)\s+(?P<x>{_APPS})\s+(?:in\s+|as\s+)?(?P<s>full\s?screen|"
                 rf"maximi[sz]ed|maximum|big|max|minimi[sz]ed|on the (?:left|right)(?: side| half)?|on (?:the )?other (?:monitor|screen))$", t)
    if m:
        s = m.group("s")
        if "left" in s or "right" in s or "monitor" in s or "screen" in s and "full" not in s:
            layout = "left" if "left" in s else "right" if "right" in s else "next_monitor"
            return _d(rid, t, "window_op", {"action": "arrange", "target": m.group("x"), "layout": layout, "launch": True})
        state = "fullscreen" if "full" in s else "minimize" if "minim" in s else "maximize"
        return _d(rid, t, "window_op", {"action": state, "target": m.group("x"), "launch": True})
    # make <window> full screen / fullscreen <window>
    m = re.match(rf"^(?:make|put|set|turn)\s+(?P<x>(?:the |this |my )?(?:{_APPS}|window|app|it|this|that)(?:\s+(?:{_WIN_WORDS}))?)\s+"
                 rf"(?:to\s+|in\s+|into\s+)?(?P<s>full\s?screen|maximi[sz]ed|bigger|smaller|small)$", t) or \
        re.match(rf"^(?P<s>full\s?screen|maximi[sz]e|minimi[sz]e|restore|unminimi[sz]e)\s+(?P<x>(?:the |this |my )?(?:{_APPS})"
                 rf"(?:\s+(?:{_WIN_WORDS}))?)$", t)
    if m:
        s = m.group("s")
        state = "fullscreen" if "full" in s else "minimize" if ("minim" in s or s.startswith("small")) else \
            "restore" if ("restore" in s or "unminim" in s) else "maximize"
        x = re.sub(rf"^(the|this|my)\s+|\s+(?:{_WIN_WORDS})$", "", m.group("x")).strip()
        if x in ("it", "this", "that", "window", "app", "current", "active"):
            return None                                   # the window in front: the window tools already do this
        return _d(rid, t, "window_op", {"action": state, "target": x})
    # side by side / split screen / tile
    m = re.match(rf"^(?:put|place|arrange|show|open|set|tile|snap|split(?: screen)?|line up)\s+(?P<a>{_APPS}|this|it)\s+"
                 rf"(?:and|&|with|next to|beside)\s+(?P<b>{_APPS}|this|it)\s*(?P<l>side by side|next to each other|split screen|"
                 rf"in split screen|left and right|on top of each other|stacked|one above the other)?$", t) or \
        re.match(rf"^(?:split screen|side by side|tile)\s+(?:with\s+)?(?P<a>{_APPS})\s+(?:and|&|with)\s+(?P<b>{_APPS})(?P<l>)$", t)
    if m:
        if not m.group("l") and re.match(r"^(?:put|place|show|open|set)\b", t):
            return None                                   # "open chrome and calculator": two apps, no layout asked
        lay = m.group("l") or "side by side"
        layout = "stack" if re.search(r"top|stack|above", lay) else "side_by_side"
        targets = [x if x not in ("this", "it") else "current" for x in (m.group("a"), m.group("b"))]
        return _d(rid, t, "window_op", {"action": "arrange", "targets": targets, "layout": layout})
    # snap <window> to the left/right half
    m = re.match(rf"^(?:snap|move|put|dock|push)\s+(?P<x>(?:the |this |my )?(?:{_APPS}|window|it|this))(?:\s+(?:{_WIN_WORDS}))?\s+"
                 rf"(?:to\s+|on\s+)?(?:the\s+)?(?P<side>left|right|top|bottom|top left|top right|bottom left|bottom right)"
                 rf"(?:\s+(?:half|side|corner|quarter))?(?:\s+of the screen)?$", t)
    if m:
        x = re.sub(r"^(the|this|my)\s+", "", m.group("x")).strip()
        if x in ("window", "it", "this", "this window"):
            return None                                   # the window in front: snap_window
        return _d(rid, t, "window_op", {"action": "arrange", "target": x, "layout": m.group("side").replace(" ", "_")})
    # the second chrome window / the chrome window with youtube
    m = re.match(rf"^(?:switch|go|jump|flip)\s+to\s+(?:the\s+)?(?P<o>{_ORD_RE})\s+(?P<x>{_APPS})\s+window$", t)
    if m:
        return _d(rid, t, "window_op", {"action": "focus", "target": f"{m.group('o')} {m.group('x')}"})
    return None


# ---------------------------------------------------------------------------------------------- deliver
def _deliver(t, raw, rid, mode):
    # [take a screenshot (of X) and] paste/attach/put/drop/send it|that screenshot (in|into|to) <dest>
    cap = re.match(r"^(?:(?:take|grab|capture|snap|get)\s+(?:a\s+|an\s+|another\s+|one\s+more\s+)?(?:quick\s+|new\s+)?(?:screenshot|screen ?shot|screen grab|"
                   r"snip|capture)(?:\s+of\s+(?P<scope>(?:the |this |my )?(?:whole |entire |full )?(?:screen|window|active window|"
                   r"current window|[\w ]+? window)))?|(?:capture|grab|snap|screenshot)\s+(?P<scope2>(?:the |this |my )?"
                   r"(?:whole |entire |full )?(?:screen|window|active window|current window)))(?:\s*(?:,|\band\b|\bthen\b|&)\s*|"
                   r"\s+(?=(?:paste|attach|put|drop|insert|send|upload|share)\b))(?:then\s+)?(?P<rest>.+)$", t)
    capture_first, scope = False, "screen"
    rest = t
    if cap:
        capture_first, rest = True, cap.group("rest").strip()
        sc = cap.group("scope") or cap.group("scope2") or ""
        scope = "active" if re.search(r"active|current|this window", sc) else "screen" if (not sc or "screen" in sc) else \
            re.sub(r"^(the|my)\s+|\s+window$", "", sc).strip()
    m = re.match(rf"^(?P<verb>paste|attach|put|drop|insert|add|upload|send|share|throw|give|transfer|push)\s+"
                 rf"(?P<res>(?:the |that |this |my |it|them|those)?(?:last |latest |recent |new |same )?"
                 rf"(?:phone |pc |laptop |computer |screen |desktop )?(?:{_RESOURCE})?"
                 rf"(?:\s+(?:i|you)\s+(?:just\s+)?(?:took|made|captured|copied|downloaded|got))?)\s+"
                 rf"(?:in|into|to|onto|on|inside|over to|in the|to the)\s+(?P<dest>.+)$", rest)
    if not m:
        return None
    verb, res, dest = m.group("verb"), (m.group("res") or "it").strip(), m.group("dest").strip()
    dest = re.sub(r"^(?:the|my)\s+", "", dest)
    if not capture_first and not re.search(rf"\b(?:{_RESOURCE})\b", res):
        return None
    res_word = re.sub(r"^(?:the|that|this|my)\s+|\s+(?:i|you)\s+.*$", "", res).strip() or "it"
    res_word = re.sub(r"^(?:last|latest|recent|new|same)\s+", "", res_word) or res_word
    if capture_first:
        res_word = "screenshot"
    send = bool(re.search(r"\b(?:and\s+)?(?:send|submit)\s+it\b$", dest)) or verb in ("send", "share") and \
        re.search(r"\b(?:chat|whatsapp|telegram|slack|teams)\b", dest) is not None
    dest = re.sub(r"\s*,?\s*(?:and|then)\s+(?:send|submit)\s+it$", "", dest)
    field = ""
    fm = re.match(rf"^(?P<field>.+?\s+(?:{_ROLE}|prompt|composer|chat|message box))\s+(?:in|of|on)\s+(?P<app>.+)$", dest)
    if fm:
        field, dest = fm.group("field"), fm.group("app")
    if re.match(r"^(?:my\s+|the\s+)?(?:phone|mobile|android|cell(?:\s?phone)?)$", dest):
        if not (capture_first or re.search(r"screen ?shot|screen grab|snip|capture|image|picture|photo", res_word)):
            return None                                  # files and text go to the phone through LocalSend
        return _d(rid, t, "deliver_op", {"resource": res_word, "to": "phone", "capture_first": capture_first,
                                         "scope": scope})
    if verb in ("send", "share", "give", "transfer", "push") and not re.search(rf"\b(?:{_IDES}|{_APPS})\b", dest):
        return None                                      # a person ("send it to arun"): messaging handles it
    if verb == "send" and res_word in ("it", "that", "this") and re.fullmatch(rf"(?:the\s+)?(?:{_IDES})(?:\s+agent)?", dest):
        return None                                      # "send it to antigravity": the written prompt (IDE send)
    if not re.match(rf"^(?:{_IDES}|{_APPS}|this (?:window|app)|the (?:window|app) in front)(?:\s+(?:{_WIN_WORDS}|agent|chat))?$",
                    dest) and not field:
        return None                                      # "upload it to the current web page": the planner reads that
    if capture_first and scope == "screen" and not field and not send and not re.match(rf"^(?:{_IDES})", dest):
        # the existing quick action, now built on the verified primitives
        return _d(rid, t, "pc_quick_action", {"action": "screenshot_paste", "app": dest})
    return _d(rid, t, "deliver_op", {"resource": res_word, "to": dest, "field": field, "send": send,
                                     "capture_first": capture_first, "scope": scope,
                                     "how": "upload" if verb == "upload" else "paste"})


# ---------------------------------------------------------------------------------------------- IDE
def _ide(t, raw, rid, mode):
    if not re.search(rf"\b(?:{_IDES})\b", t):
        return None
    ide = _ide_name(t)
    # ask/tell antigravity to X  | write a prompt in antigravity (to|saying|:) X [and send it]
    m = re.match(rf"^(?:ask|tell|instruct|get|have)\s+(?:the\s+)?(?:{_IDES})(?:\s+agent)?\s+(?:to\s+)?(?P<x>.+)$", t)
    if m:
        body = _raw(raw, m.group("x"))
        return _d(rid, t, "ide_op", {"action": "prompt", "ide": ide, "text": body, "send": True})
    m = re.match(rf"^(?:write|type|put|draft|enter|give|add)\s+(?:a\s+|the\s+|this\s+|my\s+)?(?:prompt|message|task|instruction)s?"
                 rf"\s+(?:in|into|to|for|on)\s+(?:the\s+)?(?:{_IDES})(?:\s+agent|\s+chat)?\s*(?:to|saying|that says|:|,|-|"
                 rf"asking (?:it )?to)\s+(?P<x>.+)$", t) or \
        re.match(rf"^(?:in|on)\s+(?:{_IDES}),?\s+(?:write|type|put)\s+(?:a\s+)?(?:prompt\s+)?(?:to\s+|saying\s+)?(?P<x>.+)$", t)
    if m:
        body = m.group("x")
        send = bool(re.search(r"\s*,?\s*(?:and|then)\s+(?:send|submit|run)\s+(?:it|that)$", body))
        body = re.sub(r"\s*,?\s*(?:and|then)\s+(?:send|submit|run)\s+(?:it|that)$", "", body)
        return _d(rid, t, "ide_op", {"action": "prompt", "ide": ide, "text": _raw(raw, body), "send": send})
    if re.match(rf"^(?:send|submit|run)\s+(?:it|that|the prompt|the message)\s+(?:in|to|on)\s+(?:the\s+)?(?:{_IDES})(?:\s+agent)?$", t):
        return _d(rid, t, "ide_op", {"action": "send", "ide": ide})
    m = re.match(rf"^(?P<v>accept|approve|keep|apply|reject|discard|decline|undo)\s+(?:all\s+)?(?:the\s+|those\s+|its\s+)?"
                 rf"(?:changes|edits|suggestions|diff|code)\s+(?:in|from|on)\s+(?:the\s+)?(?:{_IDES})$", t)
    if m:
        dec = "accept" if m.group("v") in ("accept", "approve", "keep", "apply") else "reject"
        return _d(rid, t, "ide_op", {"action": dec, "ide": ide})
    m = re.match(rf"^(?:open|start|create)\s+(?:a\s+)?new\s+(?:chat|conversation|agent|session|thread)\s+(?:in|on)\s+(?:the\s+)?(?:{_IDES})$", t)
    if m:
        return _d(rid, t, "ide_op", {"action": "key", "ide": ide, "name": "new_chat"})
    m = re.match(rf"^(?:open|toggle|show|hide|close)\s+(?:the\s+)?(?P<w>terminal|sidebar|explorer|agent panel|command palette)\s+"
                 rf"(?:in|on)\s+(?:the\s+)?(?:{_IDES})$", t)
    if m:
        name = {"terminal": "toggle_terminal", "sidebar": "toggle_sidebar", "explorer": "explorer",
                "agent panel": "agent_panel", "command palette": "command_palette"}[m.group("w")]
        if name == "command_palette":
            return None
        return _d(rid, t, "ide_op", {"action": "key", "ide": ide, "name": name})
    if re.match(rf"^(?:is|has)\s+(?:the\s+)?(?:{_IDES})(?:\s+agent)?\s+(?:done|finished|still (?:working|generating|running)|"
                rf"ready)$", t):
        return _d(rid, t, "ide_op", {"action": "status", "ide": ide})
    m = re.match(rf"^(?:read|show|tell me|what(?:'s| is| did))\s+(?:me\s+)?(?:the\s+)?(?:last\s+|latest\s+)?(?:response|reply|answer|output)"
                 rf"\s+(?:from|of|in)\s+(?:the\s+)?(?:{_IDES})(?:\s+agent)?$|^what did (?:the\s+)?(?:{_IDES})(?:\s+agent)? (?:say|reply|answer)$", t)
    if m:
        return _d(rid, t, "ide_op", {"action": "read", "ide": ide})
    return None


# ---------------------------------------------------------------------------------------------- text edit
def _text_edit(t, raw, rid, mode):
    m = re.match(rf"^(?P<v>delete|remove|erase|scratch|clear|backspace|kill|cut|select|highlight|copy|capitali[sz]e|uppercase|"
                 rf"upper case|lowercase|lower case)\s+(?:the\s+)?(?:(?P<dir>last|previous|next|following|past)\s+)?"
                 rf"(?:(?P<n>{_NUM_RE})\s+)?(?P<u>{_UNITS})(?:\s+(?:i|you)\s+(?:just\s+)?(?:typed|wrote|said|dictated))?$", t) or \
        re.match(rf"^(?P<v>delete|remove|erase|select|highlight|copy|cut)\s+(?:this|that|the current|current|the whole|whole|the entire|entire)"
                 rf"\s+(?P<u>{_UNITS})(?P<dir>)(?P<n>)$", t)
    if m:
        v = m.group("v")
        op = {"delete": "delete", "remove": "delete", "erase": "delete", "scratch": "delete", "clear": "delete",
              "backspace": "delete", "kill": "delete", "cut": "cut", "select": "select", "highlight": "select",
              "copy": "copy"}.get(v, "upper" if "upper" in v else "lower" if "lower" in v else "capitalize")
        unit = re.sub(r"s$", "", m.group("u")).replace("character", "char").replace("letter", "char")
        direction = "forward" if (m.group("dir") or "") in ("next", "following") else "back"
        n = _n(m.group("n") or "", 1)
        return _d(rid, t, "text_op", {"action": op, "unit": unit, "n": n, "direction": direction})
    m = re.match(r"^(?:select|highlight)\s+(?:all|everything)\s+(?:the\s+)?text$|^(?:delete|clear|erase)\s+(?:all|everything)"
                 r"\s+(?:i\s+(?:typed|wrote)|in (?:the|this) (?:box|field))$", t)
    if m:
        op = "select" if t.startswith(("select", "highlight")) else "delete"
        return _d(rid, t, "text_op", {"action": op, "unit": "all", "n": 1})
    m = re.match(r"^(?:replace|change|swap|switch)\s+(?P<w>the word\s+|every\s+|all\s+)?(?P<q>['\"])?(?P<a>[^'\"]+?)['\"]?\s+"
                 r"(?:with|to|for|into)\s+['\"]?(?P<b>[^'\"]+?)['\"]?(?P<all>\s+everywhere|\s+throughout|"
                 r"\s+in (?:the )?whole (?:text|document))?$", t)
    textual = m is not None and (t.startswith("replace") and " with " in t or bool(m.group("w")) or bool(m.group("q")))
    if m and textual and not re.search(rf"\b(?:{_WIN_WORDS}|tab|wallpaper|theme|language|voice|password|name of|volume|"
                                       rf"sound|level|brightness|speed|resolution|setting)\b", m.group("a")) \
            and len(m.group("a").split()) <= 6 and not re.match(r"^(?:it|that|this)$", m.group("a")):
        every = bool(m.group("all")) or bool(re.match(r"^(?:replace|change)\s+(?:every|all)\b", t))
        return _d(rid, t, "text_op", {"action": "replace", "find": _raw(raw, m.group("a")),
                                      "replace_with": _raw(raw, m.group("b")), "all": every})
    m = re.match(r"^(?:make|turn|change)\s+(?:the\s+)?(?:(?:last|previous)\s+(?P<n>\w+\s+)?(?P<u>words?|sentences?|lines?)|that|it|this)\s+"
                 r"(?:in(?:to)?\s+)?(?P<c>upper ?case|caps|capitals?|lower ?case|bold|italic|underlined?)$", t)
    if m:
        c = m.group("c")
        if c in ("bold", "italic") or c.startswith("underline"):
            return _d(rid, t, "text_op", {"action": "press", "key": "bold" if c == "bold" else "italic" if c == "italic"
                                          else "underline", "n": 1})
        op = "upper" if ("upper" in c or c.startswith("cap")) else "lower"
        unit = re.sub(r"s$", "", m.group("u") or "word")
        return _d(rid, t, "text_op", {"action": op, "unit": unit, "n": _n((m.group("n") or "").strip(), 1)})
    m = re.match(rf"^(?:undo|redo)\s+(?:the\s+)?(?:last\s+)?(?P<n>{_NUM_RE})\s+(?:times|changes|edits|steps)$", t)
    if m:
        return _d(rid, t, "text_op", {"action": "undo" if t.startswith("undo") else "redo", "n": _n(m.group("n"))})
    return None


# ---------------------------------------------------------------------------------------------- video
def _video(t, raw, rid, mode):
    vid = r"(?:(?:the|this|that|my)\s+)?(?:video|clip|movie|song|track|stream|player|youtube)|it|this"
    vid = rf"(?:{vid})"
    m = re.match(rf"^(?:skip|fast forward|forward|go forward|jump forward|move forward|skip ahead|seek forward|ff)\s+"
                 rf"(?:by\s+)?(?P<x>(?:{_NUM_RE}|\d+(?:\.\d+)?)\s*(?:seconds?|secs?|s|minutes?|mins?|m)\b(?:\s+and\s+\w+\s+seconds?)?)"
                 rf"(?:\s+(?:in|of|on)\s+{vid})?$", t) or \
        re.match(rf"^(?:skip|go|jump|move|seek)\s+(?:ahead|forward)\s+(?:by\s+)?(?P<x>(?:{_NUM_RE}|\d+)\s*(?:seconds?|secs?|minutes?|mins?))$", t)
    if m:
        return _d(rid, t, "video_op", {"action": "seek_by", "value": _secs(m.group("x"))})
    m = re.match(rf"^(?:rewind|go back|skip back|jump back|move back|back|seek back|rewind back)\s+(?:by\s+)?"
                 rf"(?P<x>(?:{_NUM_RE}|\d+(?:\.\d+)?)\s*(?:seconds?|secs?|s|minutes?|mins?|m)\b)(?:\s+(?:in|of|on)\s+{vid})?$", t)
    if m:
        return _d(rid, t, "video_op", {"action": "seek_by", "value": -_secs(m.group("x"))})
    m = re.match(rf"^(?:jump|go|skip|seek|move|fast forward)\s+(?:straight\s+)?to\s+(?:the\s+)?(?:(?:minute|timestamp|time)\s+)?"
                 rf"(?P<x>\d{{1,2}}:\d{{2}}(?::\d{{2}})?|\d+\s*(?:minutes?|mins?|seconds?|secs?)(?:\s+(?:and\s+)?\d+\s*(?:seconds?|secs?))?)"
                 rf"(?:\s+(?:mark|in the video|of the video|in {vid}))?$", t) or \
        re.match(rf"^(?:play|start|watch)\s+(?:{vid}\s+)?from\s+(?P<x>\d{{1,2}}:\d{{2}}(?::\d{{2}})?|\d+\s*(?:minutes?|mins?|seconds?))$", t)
    if m:
        return _d(rid, t, "video_op", {"action": "seek_to", "value": _secs(m.group("x"))})
    m = re.match(rf"^(?:play|set|put|change|make)?\s*(?:{vid}\s+)?(?:at|to|on)?\s*(?:the\s+)?(?:speed\s+(?:to\s+)?)?"
                 rf"(?P<r>\d+(?:\.\d+)?|half|double|normal|1)\s*(?:x|times)?\s*(?:speed|playback speed)?$", t)
    if m and re.search(r"speed|\dx|\d\s*times|double|half|normal speed", t) and not re.search(r"\b(?:volume|brightness)\b", t):
        r = m.group("r")
        rate = {"half": 0.5, "double": 2.0, "normal": 1.0}.get(r) or float(r)
        return _d(rid, t, "video_op", {"action": "rate", "value": rate})
    m = re.match(rf"^(?P<v>speed up|slow down|go faster|go slower|play faster|play slower|normal speed|reset (?:the )?speed)"
                 rf"(?:\s+{vid})?$|^(?:speed|slow)\s+{vid}\s+(?P<v2>up|down)$", t)
    if m:
        v = m.group("v") or ("speed up" if m.group("v2") == "up" else "slow down")
        rate = 1.0 if ("normal" in v or "reset" in v) else (1.5 if re.search(r"up|faster", v) else 0.75)
        return _d(rid, t, "video_op", {"action": "rate", "value": rate, "relative": "normal" not in v and "reset" not in v})
    m = re.match(r"^(?:turn|switch|put)\s+(?P<o>on|off)\s+(?:the\s+)?(?:captions|subtitles|subs|cc|closed captions)$|"
                 r"^(?:enable|show|disable|hide|toggle)\s+(?:the\s+)?(?:captions|subtitles|subs|cc|closed captions)$|"
                 r"^(?:captions|subtitles|subs)\s+(?P<o2>on|off)$", t)
    if m:
        return _d(rid, t, "video_op", {"action": "captions"})
    if re.match(rf"^(?:skip|close|dismiss)\s+(?:this\s+|the\s+)?ad(?:vert(?:isement)?)?s?(?:\s+now)?$", t):
        return _d(rid, t, "video_op", {"action": "skip_ad"})
    if re.match(rf"^(?:restart|replay|start over|play again|rewatch)(?:\s+{vid})?(?:\s+from the (?:start|beginning))?$"
                rf"|^(?:go|jump|skip) (?:back )?to the (?:start|beginning)(?: of {vid})?$", t):
        return _d(rid, t, "video_op", {"action": "restart"})
    m = re.match(rf"^(?:make|put|turn)\s+(?P<o>{vid})\s+(?:full ?screen|bigger)$|^full ?screen\s+(?P<o2>{vid})$|"
                 rf"^(?:watch|play)\s+(?:it\s+)?(?:in\s+)?full ?screen$", t)
    if m and (mode == "media" or not re.fullmatch(r"it|this", (m.group("o") or m.group("o2") or "it").strip())):
        return _d(rid, t, "video_op", {"action": "fullscreen"})   # "make it full screen" is the window unless a video plays
    if re.match(rf"^(?:how (?:much|long) is left|how long is (?:{vid})|what(?:'s| is) (?:playing|this video)|where am i in {vid}|"
                rf"how far (?:in|into) {vid}(?: am i)?)$", t):
        return _d(rid, t, "video_op", {"action": "state"})
    m = re.match(rf"^(?:set|put|turn)\s+(?:the\s+)?(?:video|player|youtube)\s+volume\s+(?:to\s+)?(?P<v>\d+)\s*%?$", t)
    if m:
        return _d(rid, t, "video_op", {"action": "volume", "value": float(m.group("v"))})
    if re.match(rf"^(?:loop|repeat)\s+{vid}$|^(?:put|set)\s+{vid}\s+on\s+(?:loop|repeat)$", t):
        return _d(rid, t, "video_op", {"action": "loop", "value": 1})
    return None


def _secs(x: str) -> float:
    from jarvis.core.operator.media import parse_seconds
    x = re.sub(r"\b(" + "|".join(sorted(map(re.escape, _NUM), key=len, reverse=True)) + r")\b",
               lambda m: str(_NUM[m.group(1)]), x)
    return float(parse_seconds(x) or 0)


# ---------------------------------------------------------------------------------------------- watch
def _watch(t, raw, rid, mode):
    if re.match(r"^(?:(?:keep|auto(?:matically)?)\s+)?skip(?:ping)?\s+(?:the\s+)?ads?(?:verts?)?\s+(?:whenever|when(?:ever)?|as soon as|once|if)\s+"
                r"(?:it|you|they|youtube)\s+(?:lets?|allows?|can|possible|appears?|shows?)|^skip\s+(?:the\s+|all\s+)?ads?\s+"
                r"(?:automatically|for me|as they come|on this video|for this video|whenever possible|when possible)$|"
                r"^(?:auto ?skip|keep skipping)\s+(?:the\s+)?ads?$|^(?:watch for|handle)\s+(?:the\s+)?ads?\s+and\s+skip\s+them$", t):
        return _d(rid, t, "watch_op", {"action": "skip_ads"})
    if re.match(r"^(?:stop|quit|cancel|don't keep|no more)\s+(?:auto\s?)?skipping\s+(?:the\s+)?ads?$|^stop\s+watching\s+(?:for\s+)?ads?$", t):
        return _d(rid, t, "watch_op", {"action": "cancel", "kind": "skip_ad"})
    m = re.match(rf"^(?:tell|let|notify|ping|alert|remind)\s+(?:me\s+)?(?:know\s+)?(?:when|once|as soon as)\s+(?:the\s+|my\s+|this\s+)?"
                 rf"(?P<what>download|file|pdf|installer|(?:{_IDES})(?:\s+agent)?|agent|generation|build|render)\s+"
                 rf"(?:is\s+)?(?:done|finishes|finished|completes|completed|downloads|is downloaded|is ready|stops?|ends?)"
                 rf"(?:\s+(?:generating|downloading|working|running|thinking))?$", t)
    if m:
        what = m.group("what")
        if re.search(rf"download|file|pdf|installer", what):
            return _d(rid, t, "watch_op", {"action": "download_done"})
        if re.search(rf"{_IDES}|agent|generation", what):
            return _d(rid, t, "watch_op", {"action": "ide_done", "ide": _ide_name(what)})
        return None
    if re.match(r"^(?:what are you watching(?: for)?|list (?:the |your )?watch(?:es|ers)|what watches are (?:on|running))$", t):
        return _d(rid, t, "watch_op", {"action": "list"})
    if re.match(r"^(?:stop|cancel)\s+(?:all\s+)?(?:the\s+)?(?:watch(?:es|ers)?|watching)$", t):
        return _d(rid, t, "watch_op", {"action": "cancel", "kind": ""})
    return None


# ---------------------------------------------------------------------------------------------- browser
def _browser(t, raw, rid, mode):
    m = re.match(rf"^(?P<v>open|play|click|go to|show me|pick|choose|watch|select|take me to)\s+(?:on\s+)?(?:the\s+)?(?P<o>{_ORD_RE})\s+"
                 rf"(?P<k>one|(?:search\s+)?result|link|video|hit|option|entry|item|article|thumbnail)s?"
                 rf"(?P<nt>\s+in (?:a )?new tab)?(?:\s+(?:on|in|from) (?:the|this) (?:page|list|results))?$", t) or \
        re.match(rf"^(?:open|play|click)\s+(?:result|link|video)\s+(?:number\s+)?(?P<o>\d+)(?P<nt>\s+in (?:a )?new tab)?$", t)
    if m and m.group("k") == "one" and mode not in ("browser", "media"):
        m = None                                          # "open the second one" with no list in front: ask
    if m and m.groupdict().get("v") in ("click", "pick", "choose", "select") \
            and m.group("k") not in ("result", "search result", "video", "hit", "article"):
        m = None                                          # "click the first link / item": a control on any surface
    if m and not re.search(r"\b(?:file|pdf|folder|document|photo|image|download)s?\b", t):
        o = m.group("o")
        return _d(rid, t, "browser_op", {"action": "open_result", "ordinal": _n(o, 1) if o != "next" else 1,
                                         "new_tab": bool(m.group("nt"))})
    m = re.match(r"^(?:switch|go|jump|flip|move)\s+to\s+(?:the\s+)?(?P<x>.+?)\s+tab$|^(?:switch|go)\s+to\s+tab\s+(?:number\s+)?(?P<n>\d+)$|"
                 r"^(?:open|show)\s+(?:the\s+)?(?P<x2>[a-z0-9.]+(?:\s+[a-z0-9.]+)?)\s+tab$", t)
    if m:
        which = m.group("x") or m.group("x2") or m.group("n") or ""
        if re.fullmatch(r"(?:number\s+)?\d+|(?:first|second|third|fourth|fifth|last)", which):
            return None                                   # "go to tab 3": the browser chord tool (Ctrl+3)
        if which in ("new", "a new", "another", "an empty", "blank", "incognito", "private"):
            return None
        if which in ("next", "previous", "last", "other", "prior"):
            return _d(rid, t, "browser_op", {"action": "tab_next" if which == "next" else "tab_previous"})
        return _d(rid, t, "browser_op", {"action": "tab_switch", "which": which})
    m = re.match(r"^close\s+(?:the\s+)?(?P<x>.+?)\s+tab$", t)
    if m and m.group("x") not in ("this", "current", "the current", "active", "that", "this browser"):
        return _d(rid, t, "browser_op", {"action": "tab_close", "which": m.group("x")})
    if re.match(r"^(?:list|show|what are|which are)\s+(?:me\s+)?(?:all\s+)?(?:my\s+|the\s+)?(?:open\s+)?tabs(?:\s+(?:are\s+)?open)?$|"
                r"^what tabs (?:do i have|are) open$|^how many tabs (?:are|do i have) open$", t):
        return _d(rid, t, "browser_op", {"action": "tab_list"})
    m = re.match(r"^(?:find|search(?: for)?|look for|locate|highlight)\s+['\"]?(?P<q>.+?)['\"]?\s+(?:on|in)\s+(?:this|the)\s+(?:page|site|"
                 r"article|tab|website)$", t)
    if m and not re.search(rf"\b(?:{_ROLE})s?$", m.group("q")):
        return _d(rid, t, "browser_op", {"action": "find", "target": _raw(raw, m.group("q"))})
    m = re.match(r"^(?:what are|read|list|show me|tell me)\s+(?:me\s+)?(?:the\s+)?(?:top\s+)?(?:search\s+)?results(?:\s+on (?:this|the) page)?$", t)
    if m:
        return _d(rid, t, "browser_op", {"action": "results"})
    if mode == "browser" and re.match(r"^(?:go\s+)?back(?:\s+(?:a|one)\s+page)?$|^previous page$", t):
        return _d(rid, t, "browser_op", {"action": "back"})
    if mode == "browser" and re.match(r"^(?:go\s+)?forward(?:\s+(?:a|one)\s+page)?$|^next page$", t):
        return _d(rid, t, "browser_op", {"action": "forward"})
    return None


# ---------------------------------------------------------------------------------------------- ui
def action_is_plain_tap(verb: str, target: str) -> bool:
    return verb in ("tap", "tap on", "click", "click on", "press") and not re.search(rf"\b(?:{_ORD_RE})\b", target)


_KEYS = r"enter|return|escape|esc|tab|space|spacebar|backspace|delete|home|end|page up|page down|f\d{1,2}|up|down|left|right"


_SECRET = re.compile(r"\b(?:password|passcode|pin|otp|one time code|cvv|cvc|card number|security code|verification code|"
                     r"2fa code)\b")


def _ui(t, raw, rid, mode):
    surface = _surface(t)
    if re.match(r"^(?:type|enter|put|fill(?: in)?|input|write|paste)\b", t) and _SECRET.search(t):
        return _d(rid, t, "clarify", {}, lane=RouteLane.CLARIFY,
                  clarification="I don't type passwords, PINs or codes - please enter that yourself.")
    # type <text> in(to) the <field> [on my phone / in X]
    m = re.match(rf"^(?:type|enter|write|put|fill(?: in)?|input)\s+['\"]?(?P<text>.+?)['\"]?\s+(?:in|into|inside|on)\s+(?:the\s+)?"
                 rf"(?P<f>[\w' -]*?(?:{_ROLE}|bar|prompt|composer|search))(?P<where>\s+(?:on|in)\s+(?:my\s+|the\s+)?[\w ]+)?$", t)
    if m and not re.search(r"\b(?:password|passcode|pin|otp|one time code|cvv|cvc|card number|security code|"
                           r"verification code)\b", t):
        where = (m.group("where") or "").strip()
        surf = "phone" if re.search(r"phone|mobile|android", where) else surface
        app = re.sub(r"^(?:on|in)\s+(?:my\s+|the\s+)?", "", where) if where and surf != "phone" else ""
        return _d(rid, t, "ui_op", {"action": "type", "target": m.group("f").strip(), "text": _raw(raw, m.group("text")),
                                    "surface": surf, "window": app})
    if m:
        return _d(rid, t, "clarify", {}, lane=RouteLane.CLARIFY,
                  clarification="I don't type passwords or codes - please enter that yourself.")
    g = re.match(r"^\W*(?:(?:um+|uh+|hey|ok)\s+)*(?:jarvis\W*)?(?:(?:please|can you|could you)\s+)*(?P<b>right|double)"
                 r"[\s-]*click\s+(?:on\s+)?(?P<x>.+?)(?:\s+(?:please|jarvis))*[.!?]*$", raw.lower())
    if g:
        # pointer gestures go to the screen tool - with the button the owner said (cleaning drops "right")
        return _d(rid, t, "screen_click", {"target": g.group("x").strip(), "button": "right" if g.group("b") == "right"
                                           else "left", "double": g.group("b") == "double"})
    # click / press / tap / hit / select <control>
    m = re.match(rf"^(?P<v>click|click on|press|tap|tap on|hit|push|select|choose|check|uncheck|tick|untick|toggle)\s+"
                 rf"(?:on\s+)?(?P<x>.+?)(?P<where>\s+(?:on|in)\s+(?:my\s+)?(?:phone|mobile|android|the phone|this page|the page|"
                 rf"this window|the window|(?:the\s+)?(?:{_IDES}|{_APPS})))?$", t)
    if m:
        v, x, where = m.group("v"), m.group("x").strip(), (m.group("where") or "").strip()
        if re.fullmatch(rf"(?:the\s+)?(?:{_KEYS})(?:\s+key)?(?:\s+\w+\s+times)?", x) or re.match(r"^(?:ctrl|control|alt|shift|win|windows)\b", x):
            return None                                   # a keyboard key: the keyboard tool
        if re.match(r"^(?:a\s+|an\s+)?new\b", x) or (v == "open" and re.search(
                r"\b(?:file|pdf|folder|documents?|downloads?|desktop|photos?|images?|pictures|music|videos)\b", x)):
            return None                                   # "open a new tab", "open the first result in my documents"
        named_control = re.search(rf"\b(?:{_ROLE})s?$", x) or re.search(rf"^(?:the\s+)?(?:{_ORD_RE})\s+(?:{_ROLE})", x)
        if v in ("open", "select", "choose", "check", "toggle") and not named_control:
            return None                                   # "open chrome", "select all": not a control
        if v in ("press", "push", "hit") and not named_control and not re.match(r"^(?:the\s+)?(?:send|submit|ok|cancel|"
                                                                                 r"save|next|continue|done|allow|accept)\b", x):
            return None
        if re.search(r"\b(?:screen|desktop|anywhere|at\s+\d|coordinates?|pixel)\b", x):
            return None
        if re.search(r"\b(?:same|that|previous|earlier|again)\b", x) or \
                re.search(rf"\b(?:in|inside|within|of|from|under)\s+(?:the|this|that|current|my)\s+[\w ]*?(?:{_ROLE}|menu|list|panel|dialog)s?\b", x):
            return None                                   # a referent or a nested scope: resolution/planning decides
        surf = "phone" if re.search(r"phone|mobile|android", where) else "browser" if "page" in where else surface
        if surf == "phone" and action_is_plain_tap(v, x):
            label = re.sub(r"^(?:the|on)\s+|\s+(?:button|icon|option|app)$", "", x).strip()
            return _d(rid, t, "android_tap_text", {"text": _raw(raw, label)})   # tap-by-label on the phone
        app = re.sub(r"^(?:on|in)\s+(?:the\s+)?", "", where) if where and surf not in ("phone", "browser") \
            and "window" not in where else ""
        action = {"check": "check", "tick": "check", "uncheck": "uncheck", "untick": "uncheck"}.get(v, "click")
        ordinal = re.search(rf"\b(?:{_ORD_RE})\b(?!\s+(?:right|left|corner|of the))", x) and not re.search(r"\bat the top\b", x)
        if action == "click" and v != "toggle" and surf != "phone" and not ordinal:
            # a plain "click X": screen_click, which resolves structurally first and uses vision last
            return _d(rid, t, "screen_click", {"target": _raw(raw, x), "button": "left", "double": False})
        return _d(rid, t, "ui_op", {"action": action, "target": x, "surface": surf, "window": app})
    # scroll down on my phone / in antigravity
    m = re.match(rf"^scroll\s+(?P<d>up|down|(?:to\s+(?:the\s+)?)?(?:top|bottom))(?:\s+(?P<n>{_NUM_RE})\s+times)?\s+(?:on|in)\s+"
                 rf"(?:my\s+|the\s+)?(?P<w>phone|mobile|android|{_IDES}|{_APPS})$", t)
    if m:
        d = re.sub(r"^to\s+(?:the\s+)?", "", m.group("d"))
        surf = "phone" if m.group("w") in ("phone", "mobile", "android") else "auto"
        return _d(rid, t, "ui_op", {"action": "scroll", "direction": d, "n": _n(m.group("n") or "", 1), "surface": surf,
                                    "window": "" if surf == "phone" else m.group("w")})
    return None
