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


def match_extra(t: str, raw: str, rid: str) -> Optional[RouteDecision]:
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
