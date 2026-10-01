"""Desktop, app-catalog, settings, message and content requests whose object decides the tool.

Each matcher reads the *object* of the request, so the verb alone never picks the tool:

    "restore the window I minimized earlier"        -> bring that window back (title from the action log)
    "move this window to the other monitor"          -> move_resize_window(next_monitor)
    "bring the window containing my JARVIS project"  -> switch_window("jarvis")
    "take only the active window"                    -> take_screenshot(window=active)
    "where is VS Code installed"                     -> get_app_location
    "find an installed program that sounds like X"   -> list_installed_applications(filter=X)
    "check the setting related to automatic updates" -> open_system_settings(windows_update)
    "the most recent unread message from Yoga"       -> WhatsApp, not Gmail (mail words pick Gmail)
    "summarize this page" / "extract the article title" -> the page already open (its text is data, never instructions)
    "attach ..."                                     -> the planner (no single tool attaches), never a screenshot alone
"""
from __future__ import annotations

import re
from typing import Optional

from jarvis.core.router.models import ComplexityLevel, ReasonCode, RouteDecision, RouteLane, RouteSource


def _d(request_id: str, text: str, intent: Optional[str], slots: dict, lane: RouteLane = RouteLane.LANE_0,
       clarification: Optional[str] = None, reason: ReasonCode = ReasonCode.EXACT_PATTERN) -> RouteDecision:
    return RouteDecision(request_id=request_id, lane=lane, intent=intent, slots=slots, confidence=0.95, source=RouteSource.EXACT,
                         complexity=ComplexityLevel.SIMPLE if lane != RouteLane.LANE_2 else ComplexityLevel.COMPLEX,
                         needs_planner=lane == RouteLane.LANE_2, normalized_text=text, clarification=clarification,
                         reason_code=reason if lane != RouteLane.LANE_2 else ReasonCode.MULTI_STEP, candidate_count=1)


def _planner(request_id: str, text: str) -> RouteDecision:
    return _d(request_id, text, None, {}, lane=RouteLane.LANE_2)


_NUMS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
         "fifteen": 15, "twenty": 20}
_SETTINGS = (
    (r"update|upgrade|patch", "windows_update"), (r"sound|audio|volume|speaker|microphone|mic", "sound"),
    (r"display|screen|brightness|resolution|monitor|night\s+light|scal", "display"), (r"wi-?fi|wireless", "wifi"),
    (r"network|internet|ethernet|vpn|proxy", "network"), (r"bluetooth|pair", "bluetooth"),
    (r"apps?|programs?|installed|default\s+apps?|startup", "apps"), (r"notification", "notifications"),
    (r"power|sleep|shut\s*down|lid", "power"), (r"battery|charging", "battery"), (r"storage|disk|space", "storage"),
)
_FILE_NOUN = (r"report|document|doc|pdf|file|presentation|slides|deck|spreadsheet|sheet|notes|assignment|paper|resume|cv|"
              r"invoice|receipt|certificate|thesis|essay|project\s+file|record|draft")
_STOP = {"the", "a", "an", "my", "that", "this", "from", "around", "when", "we", "did", "i", "you", "it", "was", "were", "about",
         "of", "for", "with", "in", "on", "at", "to", "work", "worked", "stuff", "thing", "time", "period", "back", "then",
         "earlier", "before", "last", "previous", "one", "and", "or", "us", "our", "some", "something", "had", "made", "which"}


def _last_minimized_title() -> str:
    try:
        from jarvis.core.action_log import get_action_log
        e = get_action_log().last(tools=("minimize_window",))
    except Exception:
        return ""
    title = e.args.get("window") if e is not None and e.ok else ""
    return title.strip() if isinstance(title, str) else ""


def match_domains(t: str, raw: str, request_id: str) -> Optional[RouteDecision]:
    """t: lower-cased request without wake words / politeness; raw: the original text."""
    if re.match(r"^(?:check|look|scan)\s+for\s+(?:new\s+)?(?:windows\s+|system\s+|pc\s+)?updates?$", t):
        return _d(request_id, t, "open_system_settings", {"page": "windows_update"})
    # ------------------------------------------------------------------ windows
    if re.match(r"^(?:restore|bring\s+back|un-?minimi[sz]e|get\s+back|show\s+(?:me\s+)?again|re-?open)\s+(?:the\s+|that\s+|my\s+)?"
                r"(?:window|app|program)\s+(?:that\s+|which\s+)?(?:i|you|we)\s+(?:just\s+)?minimi[sz]ed\b"
                r"|^(?:restore|bring\s+back|un-?minimi[sz]e)\s+(?:the\s+|that\s+)?(?:last\s+|previously\s+)?minimi[sz]ed\s+(?:window|app)\b", t):
        title = _last_minimized_title()
        if title:
            return _d(request_id, t, "switch_window", {"target": title, "resolved_from": "action_log"})
        return _d(request_id, t, "clarify", {}, lane=RouteLane.CLARIFY, reason=ReasonCode.MISSING_REQUIRED_SLOT,
                  clarification="Which window should I bring back? I don't have a record of minimizing one - tell me the app.")
    m = re.match(r"^(?:move|send|put|throw|shift|drag|push)\s+(?:this|the|my|that|it)?\s*(?:current\s+|active\s+)?(?:window|app)?\s*"
                 r"(?:to|onto|on|over\s+to)\s+(?:the\s+|my\s+)?(?P<which>other|next|second|2nd|another|secondary|external|previous|"
                 r"left|right|first|main|primary)\s+(?:monitor|screen|display)$", t)
    if m:
        back = m.group("which") in ("previous", "left", "first", "main", "primary")
        return _d(request_id, t, "move_resize_window", {"action": "previous_monitor" if back else "next_monitor"})
    m = re.match(r"^(?:bring|switch\s+to|go\s+to|focus(?:\s+on)?|show(?:\s+me)?|pull\s+up|jump\s+to)\s+(?:up\s+)?(?:the\s+)?window\s+"
                 r"(?:containing|with|that\s+has|that\s+shows|titled|named|called|showing|for|of)\s+(?:my\s+|the\s+)?(?P<x>.+?)"
                 r"(?:\s+(?:to\s+the\s+front|to\s+front|forward|up|on\s+top))?$", t)
    if m:
        target = re.sub(r"\s+(?:project|window|file|folder|document|tab|app|repo(?:sitory)?|code)$", "", m.group("x")).strip()
        if target:
            return _d(request_id, t, "switch_window", {"target": target})
    if re.match(r"^(?:close|dismiss|cancel|shut|get\s+rid\s+of|clear)\s+(?:only\s+)?(?:the\s+|this\s+|that\s+)?(?:open\s+)?"
                r"(?:dialog(?:\s+box)?|pop-?up|modal|message\s+box|alert|prompt\s+window)\b", t):
        return _d(request_id, t, "dialog_interaction", {"action": "dismiss"})
    if re.match(r"^(?:take|capture|grab|snap|screenshot)\s+(?:a\s+)?(?:screenshot\s+|screen\s*shot\s+|capture\s+|picture\s+|snap\s+)?"
                r"(?:of\s+)?(?:only\s+|just\s+)?(?:the\s+)?(?:active|current|focused|front|foreground|this)\s+window(?:\s+only)?$", t):
        return _d(request_id, t, "take_screenshot", {"window": "active"})

    # ------------------------------------------------------------------ composing a prompt for something else to answer
    if re.match(r"^(?:type|write|draft|compose|prepare)\s+(?:a|an|the)\s+(?:request|prompt|question|query|instruction|message)\s+"
                r"(?:to|asking|that\s+asks|for|telling)\b", t):
        return _planner(request_id, t)

    # ------------------------------------------------------------------ attaching is never one tool
    if re.match(r"^(?:attach|upload|insert|embed)\b", t) \
            or re.search(r"\b(?:and|then)\s+(?:attach|upload)\s+(?:it|that|this|them)\b", t):
        return _planner(request_id, t)

    # ------------------------------------------------------------------ app catalog
    m = re.match(r"^(?:tell\s+me\s+|show\s+me\s+|find\s+(?:out\s+)?)?where\s+(?:is|was|did|has)\s+(?:the\s+|my\s+)?(?P<n>[\w .+#-]+?)\s+"
                 r"(?:actually\s+|really\s+|get\s+|been\s+)?install(?:ed)?(?:\s+to)?$", t) \
        or re.match(r"^(?:tell\s+me\s+|show\s+me\s+|find\s+(?:out\s+)?)?where\s+(?:the\s+|my\s+)?(?P<n>[\w .+#-]+?)\s+(?:is|was|got|has\s+been)\s+"
                    r"(?:actually\s+|really\s+)?installed(?:\s+to)?$", t)
    if m:
        return _d(request_id, t, "get_app_location", {"name": m.group("n").strip()})
    m = re.match(r"^(?:find|search(?:\s+for)?|look\s+for|list|show(?:\s+me)?|is\s+there|do\s+i\s+have)\s+(?:an?\s+|any\s+|the\s+)?installed\s+"
                 r"(?:program|app|application|software|tool)s?\s+(?:whose\s+name\s+|that\s+|which\s+)?(?:sounds?\s+like|looks?\s+like|named|"
                 r"called|like|matching|similar\s+to|resembling|with\s+(?:a\s+)?name\s+like|containing)\s+['\"]?(?P<n>[^'\"]+?)['\"]?$", t)
    if m:
        return _d(request_id, t, "list_installed_applications", {"filter": m.group("n").strip()})

    # ------------------------------------------------------------------ settings pages
    m = re.match(r"^(?:check|open|show(?:\s+me)?|go\s+to|take\s+me\s+to|change|find)\s+(?:the\s+)?settings?\s+(?:related\s+to|for|about|of|on|"
                 r"regarding|that\s+controls?)\s+(?P<x>.+)$", t)
    if m:
        for pattern, page in _SETTINGS:
            if re.search(rf"\b(?:{pattern})", m.group("x")):
                return _d(request_id, t, "open_system_settings", {"page": page})

    # ------------------------------------------------------------------ messages are WhatsApp unless mail is named
    if not re.search(r"\b(?:e-?mails?|mails?|gmail|inbox|sms|text\s+messages?)\b", t):
        m = re.match(r"^(?:show|read|tell|give|get|open)\s+(?:me\s+)?(?:the\s+|my\s+)?(?:most\s+recent|latest|last|newest|recent)\s+"
                     r"(?P<unread>unread\s+|new\s+)?(?:whats\s*app\s+)?(?:message|msg|text|chat)\s+from\s+(?P<who>[a-z][\w .'-]{0,30}?)$", t)
        if m:
            return _d(request_id, t, "read_whatsapp_messages", {"sender": raw_name(raw, m.group("who")), "limit": 1,
                                                                "filter": "unread" if m.group("unread") else "all"})
        m = re.match(r"^(?:summari[sz]e|recap|sum\s+up)\s+(?:the\s+|my\s+)?(?:last|latest|recent|past)\s+(?:(?P<n>\d+|[a-z]+)\s+)?"
                     r"(?:whats\s*app\s+)?(?:messages|msgs|chats|texts)$", t)
        if m and (not m.group("n") or m.group("n").isdigit() or m.group("n") in _NUMS):
            return _d(request_id, t, "summarize_whatsapp_messages", {"include_all": True})

    # ------------------------------------------------------------------ what is already open (content is data)
    if re.match(r"^(?:summari[sz]e|recap|tl;?dr|sum\s+up|give\s+me\s+(?:a\s+)?(?:summary|gist)\s+of|what(?:'s|\s+is)\s+(?:on|in)|"
                r"read(?:\s+out)?|extract|pull\s+out|get)\s+(?:me\s+)?(?:the\s+)?(?:\w+\s+){0,2}?(?:(?:of|from|on|in)\s+)?"
                r"(?:this|the\s+current|the\s+open|that|the)\s+(?:web\s*)?(?:page|tab|article|site|website|blog\s+post)\b", t) \
            or re.match(r"^(?:extract|get|pull|read|what(?:'s|\s+is))\s+(?:me\s+)?the\s+(?:article|page|post|blog)(?:'s)?\s+"
                        r"(?:title|headline|heading|author|date|summary|main\s+points?|key\s+points?)$", t):
        return _d(request_id, t, "web_task", {"goal": raw.strip(), "resume": True})
    if re.match(r"^(?:summari[sz]e|read|show|what(?:'s|\s+is)\s+(?:new\s+)?in|check|catch\s+me\s+up\s+on)\s+(?:me\s+)?"
                r"(?:today'?s|my|the|latest|new|recent)\s+(?:rss\s+|news\s+)?feeds?(?:\s+(?:for\s+)?today)?$", t):
        return _d(request_id, t, "rss_latest", {"limit": 10})

    # ------------------------------------------------------------------ "I need the report from when we did the CNN work"
    m = re.match(rf"^(?:i\s+(?:need|want)|i'?m\s+looking\s+for|i\s+am\s+looking\s+for|get\s+me|fetch(?:\s+me)?|dig\s+up|pull\s+up)\s+"
                 rf"(?:the|my|that|a)\s+(?P<noun>{_FILE_NOUN})s?\b(?P<rest>.*)$", t)
    if m:
        words = [w for w in re.findall(r"[a-z0-9+#]+", m.group("rest")) if w not in _STOP and len(w) > 1]
        query = " ".join(dict.fromkeys(words + [m.group("noun")]))
        return _d(request_id, t, "find_file", {"query": query})

    # ------------------------------------------------------------------ send to my phone, said loosely
    m = re.match(r"^(?:throw|toss|fling|beam|zap|chuck|flick)\s+(?P<what>.+?)\s+(?:onto|to|on|over\s+to)\s+(?:my\s+|the\s+)?"
                 r"(?:phone|mobile|android|cell)$", t)
    if m:
        what = m.group("what").strip()
        if re.fullmatch(r"(?:it|that|this|them|these|those|the\s+file|that\s+file|this\s+file)", what):
            return _d(request_id, t, "localsend_file", {})
        return _d(request_id, t, "localsend_file", {"path": raw_name(raw, what)})
    return None


def raw_name(raw: str, lowered: str) -> str:
    """The span of the original text for a lower-cased fragment (keeps the owner's capitalisation)."""
    i = raw.lower().find(lowered)
    return raw[i:i + len(lowered)].strip() if i >= 0 else lowered.strip()
