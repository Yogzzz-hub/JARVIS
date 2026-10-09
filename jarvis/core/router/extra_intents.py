"""Deterministic matchers for capabilities the first parsers did not reach: developer-project tools (logs, database,
discovery, code search, git diff), media trimming, call controls on the phone, voice selection and workflow creation.

Same contract as capability_intents: the object family decides the capability, the verb family decides the action,
references stay references, nothing executes here, and no sentence is special-cased.
"""
from __future__ import annotations

import re
from typing import Optional

from jarvis.core.router.models import RouteDecision
from jarvis.core.router.operator_intents import _d

_P = r"(?P<p>[a-z][a-z0-9_-]{1,24})"
_PROJ = rf"(?:the\s+)?{_P}(?:\s+(?:project|repo|repository|app|codebase|database|db))?"
_PN = lambda n: rf"(?P<p{n}>[a-z][a-z0-9_-]{{1,24}})"       # a project name; one group per alternative of a pattern
_PROJN = lambda n: rf"(?:the\s+)?{_PN(n)}(?:\s+(?:project|repo|repository|app|codebase|database|db))?"
_NOT_PROJ = frozenset("the my this that it all every any our your a an of for in on from to and or".split())
_COMPONENT = r"(?:backend|frontend|server|api|client|web|ui|worker|database|db|app)"
_VERB_SHOW = r"(?:show|display|view|see|get|open|read|tail|pull\s+up|check|fetch|print)"


def _proj(m: re.Match | None) -> str | None:
    if not m:
        return None
    p = next((v for k, v in m.groupdict().items() if k.startswith("p") and k[1:].isdigit() or k == "p" if v), "") or ""
    return None if (not p or p in _NOT_PROJ) else p


def _nums(text: str) -> Optional[int]:
    from jarvis.core.router.paraphrase import words_to_int
    m = re.search(r"\b(?:last|latest|recent|final)\s+(?P<n>\d+|[a-z]+(?:\s+[a-z]+)?)\s+lines?\b|\b(?P<n2>\d+)\s+lines?\b", text)
    if not m:
        return None
    return words_to_int(m.group("n") or m.group("n2") or "")


_PNAME = r"[A-Za-z][A-Za-z'.-]{1,19}"
_PNAMES = rf"(?P<names>{_PNAME}(?:\s*(?:,|&|\band\b)\s*{_PNAME}){{1,5}})"
_NOT_NAMES = frozenset("the my me him her them us you it all everyone everybody group groups chat chats contacts friends family team class "
                       "phone laptop pc computer file files folder screen".split())
_DETERMINER = re.compile(r"^(?:the|my|this|that|these|those|a|an|our|your|his|her|their|some)\b", re.I)


def _multi_send(raw: str, rid: str) -> Optional[RouteDecision]:
    """One message to several named people: "send good night to Mala and Revathi", "message Arun, Ravi and Divya saying I'm late",
    "fire 'Pongal at our place' off to Mala and Revathi" -> one send per person (each confirmed)."""
    r = " ".join((raw or "").split()).strip(" .!?")
    r = re.sub(r"^(?:(?:hey\s+)?jarvis\s*,?\s*)?(?:(?:can|could|would|will)\s+you\s+)?(?:please\s+)?", "", r, flags=re.I)
    m = re.match(rf"^(?:send|text|whatsapp|message|msg|ping|dm)\s+(?:a\s+message\s+)?(?P<msg>.+?)\s+to\s+{_PNAMES}$", r, re.I) \
        or re.match(rf"^(?:fire|shoot|zap)\s+(?P<msg>.+?)\s+off\s+to\s+{_PNAMES}$", r, re.I)
    msg = ""
    spoken = False
    if m:
        msg = m.group("msg").strip()
    else:
        spoken = True
        m = re.match(rf"^(?:message|text|whatsapp|msg|ping|dm|tell)\s+{_PNAMES}\s*(?:,|:|-)?\s*(?:saying|that|to\s+say|with|:)\s*(?P<msg>.+)$", r, re.I)
        if m:
            msg = m.group("msg").strip()
    if not m or not msg:
        return None
    names = [n.strip() for n in re.split(r"\s*(?:,|&|\band\b)\s*", m.group("names")) if n.strip()]
    if len(names) < 2 or any(n.lower() in _NOT_NAMES for n in names):
        return None
    qm = re.search(r"[\"“‘](.+?)[\"”’]|(?<!\w)'(.+?)'(?!\w)", msg)
    if qm:
        msg = (qm.group(1) or qm.group(2)).strip()          # "the same note — 'Pongal at our place' —": the quoted words are the message
    quoted = bool(qm) or re.match(r"^[\"'“‘].*[\"'”’]$", msg) is not None
    if not quoted and not spoken and (_DETERMINER.match(msg) or re.search(r"\.\w{2,4}\b|\b(?:file|files|photo|photos|pic|pics|picture|screenshot|document|pdf|report|link|location)\b", msg, re.I)):
        return None
    msg = msg.strip("\"'“”‘’ ")
    from jarvis.core.router.models import ComplexityLevel, ReasonCode, RouteLane, RouteSource, SubCommand
    subs = [SubCommand(intent="send_whatsapp_message", tool="send_whatsapp_message", arguments={"recipient": n, "message": msg}) for n in names]
    return RouteDecision(request_id=rid, lane=RouteLane.LANE_0, intent="compound", slots={"steps": ["send_whatsapp_message"] * len(subs)},
                         confidence=0.93, source=RouteSource.EXACT, complexity=ComplexityLevel.COMPOUND, risk="EXTERNAL_EFFECT",
                         normalized_text=" ".join(raw.lower().split()), reason_code=ReasonCode.COMPOUND_COMMAND, subcommands=subs,
                         candidate_count=len(subs))


_KNOWN_FOLDERS = ("desktop", "downloads", "download", "documents", "document", "pictures", "picture", "music", "videos", "video", "home")


def _folder_name(f: str) -> str:
    f = f.strip()
    low = f.lower()
    if low in _KNOWN_FOLDERS:
        return low.capitalize() + ("s" if low in ("download", "document", "picture", "video") else "")
    return f


def _file_transfer(raw: str, rid: str) -> Optional[RouteDecision]:
    """"copy holiday_video.mp4 from Downloads into the Videos folder", "move beach.jpg from Pictures onto the Desktop": the file is
    the source, "from <folder>" says where it is (never the thing to copy)."""
    r = " ".join((raw or "").split()).strip(" .!?")
    r = re.sub(r"^(?:(?:hey\s+)?jarvis\s*,?\s*)?(?:(?:can|could|would|will)\s+you\s+)?(?:please\s+)?", "", r, flags=re.I)
    m = re.match(r"^(?P<v>copy|move|duplicate|shift|transfer|relocate)\s+(?:the\s+|my\s+)?(?P<x>[\w .()-]+?\.[A-Za-z0-9]{2,5})\s+"
                 r"(?:from\s+(?:the\s+|my\s+|inside\s+)?(?P<f>[\w .-]+?)(?:\s+folder)?\s+)?"
                 r"(?:(?:in)?to|onto|over\s+to|in)\s+(?:the\s+|my\s+)?(?P<d>[\w .-]+?)(?:\s+folder)?(?:\s+(?:please|now))?$", r, re.I)
    if not m or not m.group("f"):
        return None            # without "from <folder>" the router's own file rules already read it correctly
    f, d, x = m.group("f").strip(), m.group("d").strip(), m.group("x").strip()
    if re.search(r"\b(?:phone|mobile|android|whatsapp|drive|cloud|email|mail)\b", " ".join((f, d)), re.I):
        return None
    intent = "copy_file" if m.group("v").lower() in ("copy", "duplicate") else "move_file"
    return _d(rid, " ".join(r.lower().split()), intent, {"source": f"{_folder_name(f)}/{x}", "destination": _folder_name(d)})


def match_extra(t: str, raw: str, rid: str) -> Optional[RouteDecision]:
    xfer = _file_transfer(raw, rid)
    if xfer is not None:
        return xfer
    multi = _multi_send(raw, rid)
    if multi is not None:
        return multi
    t = " ".join(t.lower().split()).strip(" .!?")
    # ---- project logs
    m = re.match(rf"^{_VERB_SHOW}\s+(?:me\s+)?(?:the\s+)?(?:(?P<c>{_COMPONENT})\s+)?logs?\s+(?:for|of|from|in)\s+{_PROJ}(?P<tail>.*)$", t)
    if m and _proj(m):
        slots = {"project_name": _proj(m)}
        if m.group("c"):
            slots["component"] = m.group("c")
        n = _nums(m.group("tail") or "")
        if n:
            slots["tail"] = n
        return _d(rid, t, "project_logs", slots)
    # ---- database
    m = re.match(rf"^(?:what|which)\s+tables\s+(?:are\s+)?(?:there\s+)?(?:in|inside|of)\s+(?:the\s+)?{_PN(1)}\s+(?:database|db)$|"
                 rf"^(?:show|read|get|list|display)\s+(?:me\s+)?(?:the\s+)?(?:database\s+|db\s+)?(?:schema|tables)\s+(?:of|for|in)\s+{_PROJN(2)}(?:\s+(?:database|db))?$", t)
    if m and _proj(m):
        return _d(rid, t, "database_schema_read", {"project_name": _proj(m)})
    m = re.match(rf"^(?:is|are)\s+(?:the\s+)?(?:database|db)\s+(?:for|of|in)\s+{_PROJN(1)}\s+(?:up|running|alive|online|working|ok|okay|available|reachable)$|"
                 rf"^(?:database|db)\s+(?:status|health)\s+(?:of|for|in)\s+{_PROJN(2)}$|^(?:is\s+)?{_PN(3)}(?:'s)?\s+(?:database|db)\s+(?:up|running|alive|online)$", t)
    if m and _proj(m):
        return _d(rid, t, "database_status", {"project_name": _proj(m)})
    # ---- discover a project
    m = re.match(rf"^(?:figure\s+out|find\s+out|work\s+out|tell\s+me|explain|describe|analy[sz]e|inspect|summari[sz]e|what\s+is|what'?s)\s+(?:what\s+)?"
                 rf"(?:the\s+)?{_PN(1)}\s+project(?:\s+is)?(?:\s+and\s+how\s+(?:it'?s|its|it\s+is)\s+built)?$|"
                 rf"^how\s+is\s+(?:the\s+)?{_PN(2)}(?:\s+project)?\s+(?:built|structured|set\s+up)$", t)
    if m and _proj(m):
        return _d(rid, t, "project_discover", {"project_name": _proj(m)})
    # ---- code search
    m = re.match(rf"^where\s+(?:is|are)\s+(?:the\s+)?(?:(?:function|class|method|variable|constant|module)\s+)?(?P<q>[A-Za-z_][\w.]*)\s+"
                 rf"(?:defined|declared|implemented|used|called)(?:\s+(?:in|inside|within)\s+{_PROJN(1)})?$|"
                 rf"^(?:find|show|locate|look\s+up)\s+(?:me\s+)?(?:the\s+)?(?:definition|declaration|implementation|usages?)\s+of\s+(?P<q2>[A-Za-z_][\w.]*)"
                 rf"(?:\s+(?:in|inside|within)\s+{_PROJN(2)})?$|^(?:search|grep|look)\s+(?:through\s+)?(?:the\s+)?(?:code|source|codebase)\s+(?:in\s+{_PROJN(3)}\s+)?for\s+(?P<q3>\S.*)$", t)
    if m:
        q = m.group("q") or m.group("q2") or m.group("q3")
        raw_q = re.search(re.escape(q), raw, re.I)
        slots = {"query": raw[raw_q.start():raw_q.end()] if raw_q else q}
        if _proj(m):
            slots["project_path"] = _proj(m)
        return _d(rid, t, "code_search", slots)
    # ---- git diff
    m = re.match(rf"^(?:show|get|see|view|display)\s+(?:me\s+)?(?:the\s+)?(?:uncommitted\s+|unstaged\s+|current\s+)?(?:git\s+)?diff\s*(?:of|for|in)?\s*{_PROJN(1)}?$|"
                 rf"^(?:what\s+)?(?:did|have)\s+i\s+(?:change|changed|modify|modified|edit|edited)\s+(?:anything\s+)?(?:in|on)\s+{_PROJN(2)}(?:\s+since\s+(?:the\s+)?last\s+commit)?$|"
                 rf"^did\s+i\s+change\s+anything\s+in\s+{_PROJN(3)}(?:\s+since\s+the\s+last\s+commit)?$|"
                 rf"^show\s+(?:me\s+)?the\s+uncommitted\s+(?:diff|changes)\s+(?:in|of|for)\s+{_PROJN(4)}$", t)
    if m and _proj(m):
        return _d(rid, t, "git_diff", {"repo_path": _proj(m)})
    # ---- trim a clip
    m = re.match(r"^(?:chop|cut|trim|clip|slice)\s+(?:off\s+)?(?:out\s+)?(?:the\s+)?first\s+(?P<n>\d+|[a-z]+(?:\s+[a-z]+)?)\s+(?P<u>seconds?|secs?|minutes?|mins?)\s+(?:of|from)\s+"
                 r"(?P<f>[\w .()-]+\.[a-z0-9]{2,4})(?:\s+(?:into|as)\s+(?:a\s+)?(?:clip|new\s+file))?$", t)
    if m:
        from jarvis.core.router.paraphrase import words_to_int
        n = words_to_int(m.group("n"))
        if n is not None:
            secs = n * (60 if m.group("u").startswith("min") else 1)
            f = re.search(re.escape(m.group("f")), raw, re.I)
            return _d(rid, t, "trim_media_clip", {"media_path": raw[f.start():f.end()] if f else m.group("f"), "start_time": "0", "duration": str(secs)})
    # ---- phone call controls (in-call screen)
    if re.match(r"^(?:(?:switch|put|turn|set|move)\s+(?:this|the|my)\s+call\s+(?:on\s+|to\s+)(?:the\s+)?(?:speaker|speakerphone|loudspeaker)|"
                r"(?:speaker(?:phone)?|loudspeaker)\s+on|turn\s+on\s+(?:the\s+)?speaker(?:phone)?(?:\s+on\s+(?:this\s+)?call)?)$", t):
        return _d(rid, t, "phone_op", {"action": "tap", "target": "speaker"})
    if re.match(r"^(?:mute\s+(?:myself|me)(?:\s+on\s+(?:this|the)\s+call)?|mute\s+(?:this|the)\s+call|put\s+(?:me|myself)\s+on\s+mute)$", t):
        return _d(rid, t, "phone_op", {"action": "key", "key": "mute"})
    if re.match(r"^(?:bump|turn|raise|increase|crank)\s+(?:up\s+)?(?:the\s+)?call\s+volume(?:\s+up)?$", t):
        return _d(rid, t, "phone_op", {"action": "key", "key": "volume_up"})
    if re.match(r"^(?:hang\s+up|end|cut|drop)\s+(?:on\s+)?(?:this\s+)?(?:guy|caller|person|call|one)$|^(?:reject|decline)\s+(?:this\s+)?(?:caller|call)$", t):
        return _d(rid, t, "phone_op", {"action": "key", "key": "end_call"})
    # ---- voice choice
    m = re.match(r"^(?:(?:go|switch|change)\s+(?:over\s+)?(?:with|to)\s+(?:the\s+|a\s+)?|(?:use|speak\s+in|talk\s+in|sound\s+like)\s+(?:the\s+|a\s+)?|"
                 r"(?:can|could)\s+you\s+sound\s+like\s+(?:a\s+)?)(?P<g>male|female|man|woman|boy|girl|masculine|feminine)(?:\s+voice)?"
                 r"(?:\s+(?:instead|from\s+here\s+on|from\s+now\s+on|please|now))*$", t)
    if m:
        return _d(rid, t, "set_voice", {"gender": "male" if m.group("g") in ("male", "man", "boy", "masculine") else "female"})
    return None
