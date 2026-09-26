"""Extended deterministic routes for phone control, messaging, knowledge, web and reminders.

These run early in SmartRouter (right after negation / safety checks) and fix whole
classes of misroutes observed in the generic pattern layer, for example:

* "tell me a joke"                 -> was a WhatsApp message to "Me"; now a chat answer
* "lock my phone"                  -> was phone mirroring; now an Android key press
* "search amazon for headphones"   -> was a local file search; now an Amazon search page
* "ask rahul if he is free"        -> was an unplanned multi-step request; now a composed WhatsApp message
* "learn my documents folder"      -> just opened the folder; now indexes it for RAG
* "what's the weather today"       -> was the clock; now a grounded (web) answer

Every rule is anchored and single-clause (compound requests fall through to the planner),
and anything that sends data outside the PC still goes through policy confirmation.
"""
from __future__ import annotations

import re
import urllib.parse
from typing import Optional

from jarvis.core.router.models import ComplexityLevel, ReasonCode, RouteDecision, RouteLane, RouteSource

PHONE_WORDS = r"(?:phone|mobile|android|cell ?phone|smartphone)"
ON_PHONE = rf"(?:\s+(?:on|in|of|from|for)\s+(?:my\s+|the\s+)?{PHONE_WORDS})"
SELF_WORDS = {"me", "myself", "us", "jarvis", "you", "yourself", "him", "her", "them", "everyone", "somebody", "someone"}
RELATION_WORDS = {
    "mom", "mum", "mother", "amma", "dad", "father", "appa", "papa", "brother", "bro", "sister", "sis", "wife",
    "husband", "son", "daughter", "boss", "manager", "friend", "uncle", "aunt", "aunty", "grandma", "grandpa",
    "team", "office", "colleague", "teacher", "sir", "madam", "hod", "principal",
}
SITE_SEARCH = {
    "amazon": "https://www.amazon.in/s?k={q}",
    "flipkart": "https://www.flipkart.com/search?q={q}",
    "youtube": "https://www.youtube.com/results?search_query={q}",
    "google": "https://www.google.com/search?q={q}",
    "bing": "https://www.bing.com/search?q={q}",
    "duckduckgo": "https://duckduckgo.com/?q={q}",
    "wikipedia": "https://en.wikipedia.org/w/index.php?search={q}",
    "github": "https://github.com/search?q={q}",
    "stack overflow": "https://stackoverflow.com/search?q={q}",
    "stackoverflow": "https://stackoverflow.com/search?q={q}",
    "reddit": "https://www.reddit.com/search/?q={q}",
    "google maps": "https://www.google.com/maps/search/{q}",
    "maps": "https://www.google.com/maps/search/{q}",
    "spotify": "https://open.spotify.com/search/{q}",
    "linkedin": "https://www.linkedin.com/search/results/all/?keywords={q}",
    "twitter": "https://x.com/search?q={q}",
    "x": "https://x.com/search?q={q}",
    "instagram": "https://www.instagram.com/explore/search/keyword/?q={q}",
    "netflix": "https://www.netflix.com/search?q={q}",
    "imdb": "https://www.imdb.com/find/?q={q}",
    "google images": "https://www.google.com/search?tbm=isch&q={q}",
    "google news": "https://news.google.com/search?q={q}",
}
_SITES = "|".join(sorted((re.escape(s) for s in SITE_SEARCH), key=len, reverse=True))
FOLDER_WORDS = r"(?:documents?|docs|downloads?|desktop|pictures|photos|music|videos|notes)"
KNOWLEDGE_WORDS = r"(?:documents|docs|notes|files|knowledge(?: base)?|pdfs|papers)"
_COMPOUND = re.compile(r"\b(?:and then|then|after that|also)\b|;|,\s*(?:and\s+)?(?:open|close|send|play|search|find)\b")
_WHATSAPP_TAIL = re.compile(r"\s+(?:on|via|in|through|over|using)\s+whats\s*app\s*$", re.I)
_URLISH = re.compile(r"^(?:https?://)?(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|org|net|io|ai|dev|edu|in|co|app|gov|me|tv|info|uk|us)(?:/\S*)?$", re.I)
ANDROID_KEYS = {
    "volume_up": ("volume up", "increase volume", "raise volume", "turn up", "louder"),
    "volume_down": ("volume down", "decrease volume", "lower volume", "turn down", "quieter", "softer"),
    "volume_mute": ("mute",),
    "sleep": ("lock", "turn off the screen", "screen off", "sleep"),
    "wakeup": ("wake", "unlock", "turn on the screen", "screen on"),
    "media_play_pause": ("pause", "resume", "play music", "play the music", "play pause"),
    "media_next": ("next song", "next track", "skip song", "skip track", "skip"),
    "media_previous": ("previous song", "previous track", "last song"),
    "app_switch": ("recent apps", "recents", "app switcher"),
    "camera": ("open camera", "camera"),
}


# An open question (wh-word / auxiliary first) with none of these words is general knowledge or
# conversation, not a PC command. Without this guard the fuzzy layers map e.g. "and where should
# visitors go" to show_desktop and "which level is the parking on" to the volume reader.
OPEN_QUESTION = re.compile(
    r"^(?:and |so |but |then |also |ok |okay |hey |oh )?(?:what|what's|whats|which|where|where's|who|who's|whose|why|how|how's|"
    r"when|is|are|was|were|does|do|did|can|could|should|would|will|shall)\b"
)
DEVICE_TERMS = re.compile(
    r"\b(?:time|clock|date|day|today's date|battery|charg\w*|volume|sound|audio|mute\w*|loud\w*|brightness|bright|dim|screen\w*|display|"
    r"monitor|wi-?fi|network|internet|online|offline|connected|connection|connect|bluetooth|phone|android|mobile|memory|ram|cpu|"
    r"processor|gpu|disk|storage|space|install\w*|apps?|application\w*|programs?|software|process\w*|running|open|opened|closed|"
    r"files?|folders?|director\w*|documents?|docs?|pdfs?|downloads?|downloaded|desktop|pictures?|photos?|images?|videos?|music|songs?|"
    r"windows?|tabs?|browser|chrome|edge|firefox|mic|microphone|speakers?|camera|printer|whatsapp|messages?|texts?|chats?|email|"
    r"mail|inbox|calendar|meeting|reminders?|notes?|memos?|system|pc|computer|laptop|device|jarvis|you|your|news|headlines|"
    r"notepad|calculator|spotify|youtube|vs ?code|word|excel|powerpoint|explorer|settings|clipboard|wake word|dictation|"
    r"playing|paused|recording|update|updates|password|resume|cv|invoice|report|project|repo|git|code|scripts?|ollama|model|"
    r"diagnostics?|status|health|temperature|fan|usage|speed|ip address|ip)\b"
)
_FIND_MY = re.compile(r"\bwhere(?:'s| is| are| did i (?:put|save|keep))\s+(?:my|the)\b")
# Referential follow-ups ("where is it stored?", "what is that one about?") belong to the context resolver.
_REFERENTIAL = re.compile(r"\b(?:it|its|it's|that|this|those|these|them|one|ones|stored|saved|located|location|path)\b")


def _decision(request_id: str, text: str, intent: str, slots: dict, lane: RouteLane = RouteLane.LANE_0,
              reason: str = ReasonCode.EXACT_PATTERN, clarification: str | None = None,
              context_trace: dict | None = None, needs_planner: bool = False) -> RouteDecision:
    return RouteDecision(
        request_id=request_id,
        lane=lane,
        intent=intent,
        slots=slots,
        confidence=1.0 if lane != RouteLane.CLARIFY else 0.5,
        source=RouteSource.EXACT,
        complexity=ComplexityLevel.COMPLEX if needs_planner else ComplexityLevel.SIMPLE,
        needs_planner=needs_planner,
        normalized_text=text,
        reason_code=reason,
        clarification=clarification,
        context_trace=context_trace,
    )


def _question(request_id: str, text: str) -> RouteDecision:
    """Conversational request: answered by the grounded chat model."""
    return RouteDecision(
        request_id=request_id,
        lane=RouteLane.LANE_2,
        intent=None,
        confidence=0.95,
        source=RouteSource.COMPLEXITY_GATE,
        complexity=ComplexityLevel.COMPLEX,
        needs_planner=True,
        normalized_text=text,
        clarification="Conversational request answered by the assistant.",
        reason_code=ReasonCode.QUESTION_NOT_COMMAND,
    )


def _clean_person(raw: str) -> str:
    who = _WHATSAPP_TAIL.sub("", raw.strip(" ,.")).strip()
    who = re.sub(r"^(?:my|our|the)\s+", "", who, flags=re.I)
    return who.strip(" ,.")


def _looks_like_person(who: str, text: str) -> bool:
    low = who.lower()
    if not low or low in SELF_WORDS or len(low.split()) > 3:
        return False
    if re.fullmatch(rf"(?:my\s+|the\s+)?(?:{PHONE_WORDS}|pc|laptop|computer|desktop)", low):
        return False
    if "whatsapp" in text.lower():
        return True
    if low in RELATION_WORDS or re.fullmatch(r"\+?\d[\d\s-]{6,}", low):
        return True
    try:
        from jarvis.integrations.whatsapp.contact_resolver import ContactResolver
        contact, ambiguous, _ = _contact_resolver().resolve(who)
        return bool(contact or ambiguous)
    except Exception:
        return False


_resolver_cache = None


def _contact_resolver():
    global _resolver_cache
    if _resolver_cache is None:
        from jarvis.integrations.whatsapp.contact_resolver import ContactResolver
        _resolver_cache = ContactResolver()
    return _resolver_cache


_ACTION_VERBS = (
    r"open|close|send|play|search|find|copy|move|delete|take|check|read|tell|message|turn|set|mute|save|create|"
    r"draft|email|calculate|summari[sz]e|extract|organi[sz]e|download|upload|share|launch|start|stop|show|list|"
    r"call|type|remind|install|compare|write|reply|forward|notify"
)
_COMPOUND_JOIN = re.compile(rf"(?:,|\band\b|&)\s+(?:then\s+)?(?:also\s+)?(?:{_ACTION_VERBS})\b")
# An explicit reference to the user's phone (not "mobile app", "phone number", ...).
PHONE_REF = re.compile(
    rf"\b(?:my|the|on|from|of|to)\s+(?:android\s+)?{PHONE_WORDS}\b(?!\s+(?:app|apps|number|bill|case|call|charger|plan))"
    rf"|^{PHONE_WORDS}\b(?!\s+(?:app|apps|number|bill|case|call|charger|plan))|\bandroid\b"
    rf"|\b{PHONE_WORDS}(?:'s)?\s+(?:volume|brightness|screen|wi-?fi|bluetooth|battery|settings|notifications?)\b"
)


def _is_compound(text: str) -> bool:
    return bool(_COMPOUND.search(text)) or bool(_COMPOUND_JOIN.search(text))


# "everyone / all the guys / those who are messaging me" (people who wrote to the owner on WhatsApp)
_BULK_PEOPLE = re.compile(
    r"\b(?:all(?:\s+(?:the|of the|my))?(?:\s+(?:guys|people|persons|contacts|folks|ones|friends))?|everyone|everybody|every ?one|"
    r"whoever|anyone|anybody|those(?:\s+(?:guys|people|persons|ones))?|these(?:\s+(?:guys|people|persons|ones))?|"
    r"the\s+(?:guys|people|persons|ones|contacts|folks)|people|guys)\s+"
    r"(?:who|that|which|whom)?\s*(?:are\s+|is\s+|have\s+|has\s+|were\s+|was\s+|had\s+|all\s+)?(?:been\s+|all\s+)?"
    r"(?:messag|text|ping|whats\s?app|chat|writ|dm|contact|reach|wish)\w*\s+(?:to\s+|with\s+)?me\b(?:\s+(?:on|in|via)\s+whats\s?app)?"
    r"(?:\s+(?:today|now|recently|so far|this morning|this evening|tonight|just now))?"
)
_BULK_ALL_MESSAGES = re.compile(
    r"\b(?:reply|respond|answer)\s+(?:to\s+)?(?:all|every|each)\s+(?:of\s+)?(?:my\s+|the\s+)?"
    r"(?:new\s+|unread\s+|pending\s+|recent\s+|latest\s+)*(?:whats\s?app\s+)?(?:messages?|chats?|texts?|people)\b"
    r"|\b(?:reply|respond)\s+(?:to\s+)?(?:everyone|everybody|all)\b(?:\s+(?:on|in)\s+whats\s?app)?"
)
_BULK_VERB = re.compile(r"\b(?:reply|respond|answer|send|tell|message|text|inform|let|notify|write|msg|ping|say)\b")


def match_auto_reply(text: str, request_id: str) -> Optional[RouteDecision]:
    """'Reply to Yoga automatically for the next hour' / 'Stop WhatsApp auto reply' -> whatsapp_auto_reply."""
    from jarvis.integrations.whatsapp.personal_reply.commands import parse_command
    cmd = parse_command(text)
    if cmd is None:
        return None
    t = re.sub(r"\s+", " ", (text or "").lower()).strip(" .!?")
    return _decision(request_id, t, "whatsapp_auto_reply", cmd)


_GROUP_REPLY = re.compile(
    r"^(?:(?:hey |ok )?jarvis,? )?(?:please )?(?:reply|respond|answer|send|write|post|message|text|tell)\s+(?:a message\s+|it\s+)?"
    r"(?:in|to|on)\s+(?P<group>(?:the |that |this |my |our )?[\w .&'-]{0,40}?\b(?:group|grp))(?:\s+on whatsapp)?"
    r"\s*(?:,|:|-)?\s*(?:saying|that|with|and say|to say)?\s*(?P<msg>.+)?$", re.I)
_GROUP_READ = re.compile(
    r"^(?:(?:hey |ok )?jarvis,? )?(?:please )?(?:summari[sz]e|read(?: out)?|check|show|what(?:'s| is| are)? (?:new )?(?:in|on))\s+"
    r"(?:(?:the |my |new |unread |recent )*(?:whatsapp )?(?:messages?|msgs?|chats?)\s+(?:in|from|of|on)\s+)?"
    r"(?P<group>(?:the |that |this |my |our )?[\w .&'-]{0,40}?\b(?:group|grp)s?)(?:\s+(?:messages?|msgs?|chats?))?(?:\s+on whatsapp)?$", re.I)


def match_group_whatsapp(text: str, request_id: str) -> Optional[RouteDecision]:
    """The owner explicitly names a group: 'reply in the CSE group saying ...', 'summarize the CSE group'."""
    t = " ".join((text or "").split()).strip(" .!?")
    m = _GROUP_REPLY.match(t)
    if m:
        group, body = m.group("group").strip(), (m.group("msg") or "").strip()
        if body and not re.match(r"^(?:reply|respond|answer)\b", t, re.I):
            # "send/post/tell ... in the X group saying <text>": exactly that text, confirmed before sending
            return _decision(request_id, t.lower(), "send_whatsapp_message", {"recipient": group, "message": body})
        slots = {"recipient": group, **({"instruction": body} if body else {})}
        return _decision(request_id, t.lower(), "reply_whatsapp_message", slots)
    m = _GROUP_READ.match(t)
    if m:
        from jarvis.tools.system.whatsapp_tools import group_scope_from_text
        intent = "read_whatsapp_messages" if t.lower().startswith("read") else "summarize_whatsapp_messages"
        return _decision(request_id, t.lower(), intent, dict(group_scope_from_text(t)))
    return None


def match_bulk_reply(text: str, request_id: str) -> Optional[RouteDecision]:
    """'Send all the guys who are messaging me that I'm busy' -> reply_whatsapp_all (personal chats only)."""
    raw = (text or "").strip()
    auto = match_auto_reply(raw, request_id)  # time-boxed auto-reply grants come first ("reply to everyone until 10")
    if auto:
        return auto
    group = match_group_whatsapp(raw, request_id)  # a group only when the owner names it
    if group:
        return group
    t = re.sub(r"\s+", " ", raw.lower()).strip(" .!?")
    if not t:
        return None
    m = _BULK_PEOPLE.search(t) or _BULK_ALL_MESSAGES.search(t)
    if not m or re.search(r"\b(?:e-?mails?|mails?|gmail|inbox|sms|missed calls?)\b", t[: m.end() + 12]):
        return None
    outside = (t[: m.start()] + " " + t[m.end():]).strip()
    if not _BULK_VERB.search(outside) and not _BULK_VERB.search(m.group(0)[:12]):
        return None  # "who is messaging me?" is a question, not a request to reply
    if re.match(r"^(?:who|what|how many|did|has|have|is|are)\b", t) and not re.search(r"\b(?:reply|respond|send|tell)\b", t):
        return None
    tail = t[m.end():]
    tail = re.sub(r"^\s*(?:,|\.|;|:|-)?\s*(?:and\s+)?(?:please\s+)?(?:just\s+)?(?:(?:tell|say|saying|inform|let)\s+(?:them|those|everyone|all)?\s*(?:know)?\s*)?"
                  r"(?:know\s+)?(?:that|saying|with|:)?\s*", "", tail)
    body = raw_body(raw, tail).strip(" ,.;:") if tail.strip() else ""
    slots = {"message": body, "request": raw}
    return _decision(request_id, t, "reply_whatsapp_all", slots, context_trace={"bulk_reply": True})


_ON_PC = r"(?:\s+(?:for me|please|now|right now|quickly))?(?:\s+(?:on|in|to|from)\s+(?:my|this|the)\s+(?:pc|laptop|computer|system|machine|desktop))?(?:\s+(?:for me|please|now))?"
_APP = r"(?P<app>[a-z0-9][a-z0-9 .+#&'-]{0,48}?)"


def match_software(t: str, request_id: str) -> Optional[RouteDecision]:
    """install / uninstall / update applications (winget)."""
    m = re.match(rf"^(?:install|set ?up|download and install|get and install)\s+(?:the\s+)?(?:app\s+|application\s+|software\s+)?{_APP}(?:\s+(?:app|application|software))?{_ON_PC}$", t)
    if m and m.group("app").strip() not in ("it", "that", "this", "them", "updates", "all updates"):
        return _decision(request_id, t, "install_software", {"name": m.group("app").strip()})
    m = re.match(rf"^(?:uninstall|un install|remove|delete)\s+(?:the\s+)?(?:app\s+|application\s+|program\s+|software\s+)?{_APP}(?P<kind>\s+(?:app|application|program|software))?{_ON_PC}$", t)
    if m and (t.startswith(("uninstall", "un install")) or m.group("kind") or re.search(r"\bfrom (?:my|this|the) (?:pc|laptop|computer|system)", t)):
        return _decision(request_id, t, "uninstall_software", {"name": m.group("app").strip()})
    if re.match(rf"^(?:update|upgrade)\s+(?:all\s+)?(?:(?:of\s+)?my\s+|the\s+)?(?:installed\s+)?(?:apps|applications|programs|software|softwares){_ON_PC}$", t) \
            or re.match(r"^(?:check for|install)\s+(?:app|software)\s+updates$", t):
        return _decision(request_id, t, "update_software", {})
    m = re.match(rf"^(?:update|upgrade)\s+(?:the\s+|my\s+)?{_APP}\s+(?:app|application|software|program){_ON_PC}$", t)
    if m:
        return _decision(request_id, t, "update_software", {"name": m.group("app").strip()})
    return None


_CORRECTION = re.compile(r"(?:,|\u2014|-)?\s*(?:no wait|no no|no|wait|actually|sorry|i mean|make (?:that|it)|rather)\b[, ]*(?:make (?:that|it)\s+)?(?:to\s+)?(?P<n>\d{1,3})\s*(?:%|percent)?$")


_NUMBERS = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "ten": 10}
_KINDS = [
    (r"screen ?shots?", "screenshot"), (r"videos?|clips?", "video"), (r"(?:voice |call )?recordings?", "recording"),
    (r"whats ?app (?:photos|images|pics|media|files)", "whatsapp_media"), (r"documents?|docs|pdfs?", "document"),
    (r"downloads?|downloaded files?", "download"), (r"photos?|pictures?|pics?|images?|selfies?", "photo"),
]
_PULL_VERB = r"(?:copy|get|pull|bring|transfer|move|send|fetch|grab|import)"
_TO_PC = r"(?:\s+(?:to|on|onto|into)\s+(?:my\s+|the\s+|this\s+)?(?:pc|laptop|computer|desktop|system))?"


def match_phone_transfer(t: str, raw: str, request_id: str) -> Optional[RouteDecision]:
    """Copy files between phone and PC over USB/ADB."""
    kinds = "|".join(k for k, _ in _KINDS)
    m = re.match(rf"^{_PULL_VERB}\s+(?:me\s+)?(?:the\s+|my\s+|all\s+)?(?:(?:latest|last|newest|recent|new)\s+)?"
                 rf"(?:(?P<n>\d{{1,2}}|a|one|two|three|four|five|six|ten)\s+)?(?:(?:latest|last|newest|recent|new)\s+)?"
                 rf"(?P<kind>{kinds})\s+(?:from|off|on)\s+(?:my\s+|the\s+)?{PHONE_WORDS}{_TO_PC}$", t)
    if m:
        kind = next(v for k, v in _KINDS if re.fullmatch(k, m.group("kind")))
        n = m.group("n")
        count = int(n) if n and n.isdigit() else _NUMBERS.get(n or "", 1)
        if not n and re.search(r"s$", m.group("kind")) and not re.search(r"\b(?:latest|last|newest)\b", t):
            count = 5
        return _decision(request_id, t, "android_pull_file", {"kind": kind, "count": max(1, min(20, count))})
    m = re.match(rf"^{_PULL_VERB}\s+(?:the\s+|my\s+)?(?:file\s+)?(?:called\s+|named\s+)?(?P<name>[\w.()+-][\w .()+-]{{1,60}}?)\s+(?:file\s+)?from\s+(?:my\s+|the\s+)?{PHONE_WORDS}{_TO_PC}$", t)
    if m and not re.fullmatch(r"(?:it|this|that|everything|all|something)", m.group("name")):
        return _decision(request_id, t, "android_pull_file", {"name": raw_body(raw, m.group("name")), "kind": "download"})
    m = re.match(rf"^(?:copy|push|transfer|put|move)\s+(?:the\s+|my\s+)?(?:file\s+)?(?P<path>.+?)\s+(?:to|onto|into)\s+(?:my\s+|the\s+)?{PHONE_WORDS}"
                 r"(?:\s+(?:via|using|over|with|through)\s+(?:usb|cable|adb))?$", t)
    if m and not re.fullmatch(r"(?:it|this|that|this file|that file|these|them)", m.group("path")):
        return _decision(request_id, t, "android_push_file", {"path": raw_body(raw, m.group("path"))})
    return None


def _web_task_pending() -> bool:
    try:
        from jarvis.tools.system.web_agent import WebTaskTool
        return bool(WebTaskTool._pending_goal)
    except Exception:
        return False


def match_everyday(t: str, request_id: str) -> Optional[RouteDecision]:
    """Implicit everyday phrasings and spoken self-corrections ("volume 30, no wait, 20")."""
    m = _CORRECTION.search(t)
    if m and re.search(r"\b(volume|sound|brightness)\b", t[: m.start()]):
        n = max(0, min(100, int(m.group("n"))))
        if "brightness" in t[: m.start()]:
            return _decision(request_id, t, "brightness_set", {"level": n})
        return _decision(request_id, t, "volume_set", {"percent": n})
    if re.match(r"^(?:it'?s\s+)?(?:way\s+|too\s+|so\s+|very\s+)+loud(?:\s+in\s+here)?$|^(?:that'?s|this is)\s+too\s+loud$", t):
        return _decision(request_id, t, "volume_down", {})
    if re.match(r"^(?:i\s+)?can'?t hear (?:anything|you|it|a thing)(?:\s+from the speakers?)?$|^(?:it'?s\s+)?too (?:quiet|soft|low)$", t):
        return _decision(request_id, t, "volume_up", {})
    if re.match(r"^(?:total |complete )?silence(?: please)?$|^(?:mute|silence) everything$|^shut (?:it|the sound) off$", t):
        return _decision(request_id, t, "volume_mute", {})
    if re.match(r"^(?:open|launch|show|start)\s+(?:the\s+|my\s+)?(?:windows\s+)?(?:file explorer|file manager|my computer|this pc)$", t):
        return _decision(request_id, t, "open_app", {"name": "file explorer"})
    return None


_TODO_LIST = r"(?:to-?\s?do|todo|task|tasks|checklist)(?:\s+list)?"


def match_utilities(t: str, raw: str, request_id: str) -> Optional[RouteDecision]:
    """Instant offline utilities: calculator/units/dates, battery, network, timers, stopwatch, to-do list,
    personal memory, voice shortcuts, command history, passwords, recycle bin."""
    from jarvis.tools.system.everyday_tools import quick_answer, split_steps

    if not PHONE_REF.search(t) and quick_answer(raw) is not None:
        return _decision(request_id, t, "quick_answer", {"query": raw.strip()})
    # ---- voice shortcuts (before the compound check: their bodies contain several actions)
    m = re.match(r"^(?:when(?:ever)? i say|if i say)\s+[\"']?(?P<p>[^,\"']{2,60}?)[\"']?\s*(?:,|then|jarvis should|you should|please)\s*(?P<steps>.+)$", t) \
        or re.match(r"^(?:create|make|add|set up|save)\s+(?:a\s+|new\s+)?(?:shortcut|macro|routine|voice command)\s+(?:called|named)\s+[\"']?(?P<p>.+?)[\"']?\s+(?:that|to|which|for)\s+(?P<steps>.+)$", t)
    if m:
        return _decision(request_id, t, "create_shortcut", {"phrase": m.group("p").strip(), "steps": split_steps(raw_body(raw, m.group("steps")))})
    if re.match(r"^(?:list|show|what are)\s+(?:all\s+)?(?:my\s+)?(?:shortcuts|macros|routines|voice commands|custom commands)$", t):
        return _decision(request_id, t, "list_shortcuts", {})
    m = re.match(r"^(?:delete|remove)\s+(?:the\s+)?(?:shortcut|macro|routine)\s+(?:called\s+|named\s+)?[\"']?(?P<p>.+?)[\"']?$", t)
    if m:
        return _decision(request_id, t, "delete_shortcut", {"phrase": m.group("p")})
    if PHONE_REF.search(t):
        return None
    # ---- battery / network
    if re.match(r"^(?:what(?:'s| is)\s+(?:my|the)\s+|check\s+(?:my\s+|the\s+)?|show\s+(?:me\s+)?(?:my\s+|the\s+)?)?(?:laptop\s+|pc\s+)?battery(?:\s+(?:level|status|percentage|life|left|charge|health))?$", t) \
            or re.match(r"^how much (?:battery|charge)(?: do i have| is left| left| remaining)?(?: on (?:my |the )?(?:laptop|pc|computer))?$", t) \
            or re.match(r"^is (?:my |the )?(?:laptop|pc|computer|battery|it) (?:charging|plugged in|on charge)$", t):
        return _decision(request_id, t, "battery_status", {})
    if re.match(r"^(?:what(?:'s| is)\s+)?my\s+(?:local\s+)?ip(?:\s+address)?$", t) \
            or re.match(r"^(?:am i|are we|is (?:the |my )?(?:pc|laptop|computer))\s+(?:connected to (?:the )?internet|online|connected)$", t) \
            or re.match(r"^(?:is (?:the |my )?(?:internet|connection)\s+(?:working|down|up|ok|okay|connected))$", t) \
            or re.match(r"^(?:check|test|show)\s+(?:my\s+|the\s+)?(?:internet|network)(?:\s+(?:connection|status|info|details))?$", t):
        return _decision(request_id, t, "network_info", {})
    # ---- timers (spoken like reminders) and stopwatch
    m = re.match(r"^(?:set|start|create|put on)\s+(?:a\s+|an\s+)?(?:timer|countdown)\s+(?:for\s+)?(?P<n>\d+|a|an|one|two|three|five|ten|fifteen|twenty|thirty|half an?)\s*(?P<u>seconds?|secs?|minutes?|mins?|hours?|hrs?)$", t) \
        or re.match(r"^(?:set|start|create)\s+(?:a\s+|an\s+)?(?P<n>\d+|a|an|one|two|three|five|ten|fifteen|twenty|thirty)[- ](?P<u>second|sec|minute|min|hour)s?\s+(?:timer|countdown)$", t) \
        or re.match(r"^(?:timer|countdown)\s+(?:for\s+)?(?P<n>\d+)\s*(?P<u>seconds?|secs?|minutes?|mins?|hours?|hrs?)$", t)
    if m:
        n, u = m.group("n"), m.group("u")
        span = "30 minutes" if n.startswith("half") else f"{n} {u if u.endswith('s') or n in ('a', 'an', 'one', '1') else u + 's'}"
        return _decision(request_id, t, "set_reminder", {"text": f"timer: in {span}"})
    m = re.match(r"^(?P<a>start|stop|pause|resume|reset|restart|clear)\s+(?:the\s+|a\s+|my\s+)?stop ?watch$", t) \
        or re.match(r"^stop ?watch\s+(?P<a>start|stop|lap|reset|status)$", t)
    if m:
        a = {"restart": "reset", "clear": "reset"}.get(m.group("a"), m.group("a"))
        return _decision(request_id, t, "stopwatch", {"action": a})
    if re.match(r"^(?:lap|record (?:a )?lap|stop ?watch lap)$", t):
        return _decision(request_id, t, "stopwatch", {"action": "lap"})
    if re.match(r"^(?:how long has (?:the )?stop ?watch been running|stop ?watch (?:time|status)|check (?:the )?stop ?watch)$", t):
        return _decision(request_id, t, "stopwatch", {"action": "status"})
    # ---- to-do list
    m = re.match(rf"^(?:add|put|write)\s+(?P<x>.+?)\s+(?:to|on|in)\s+(?:my\s+|the\s+)?{_TODO_LIST}$", t) \
        or re.match(rf"^(?:new|add (?:a )?)\s*(?:task|to-?do|todo)\s*[:\-]?\s+(?P<x>.+)$", t)
    if m:
        return _decision(request_id, t, "todo", {"action": "add", "item": raw_body(raw, m.group("x"))})
    if re.match(rf"^(?:show|read|list|open|check|what(?:'s| is) on|what are)\s+(?:me\s+)?(?:my\s+|the\s+)?{_TODO_LIST}$", t) \
            or re.match(r"^what (?:do i have to do|are my (?:tasks|to-?dos|todos))(?: today)?$", t):
        return _decision(request_id, t, "todo", {"action": "list"})
    m = re.match(rf"^(?:mark|tick off|check off|cross off)\s+(?P<x>.+?)(?:\s+(?:as\s+)?(?:done|complete|completed|finished))?(?:\s+(?:on|from) (?:my\s+)?{_TODO_LIST})?$", t)
    if m and (re.search(r"\b(?:done|complete|completed|finished)\b", t) or re.match(r"^(?:tick|check|cross) off", t)):
        return _decision(request_id, t, "todo", {"action": "done", "item": raw_body(raw, m.group("x"))})
    m = re.match(rf"^(?:remove|delete|take)\s+(?P<x>.+?)\s+(?:off|from)\s+(?:my\s+|the\s+)?{_TODO_LIST}$", t)
    if m:
        return _decision(request_id, t, "todo", {"action": "remove", "item": raw_body(raw, m.group("x"))})
    if re.match(rf"^clear\s+(?:the\s+|all\s+)?(?:completed|done|finished)\s+(?:tasks|to-?dos|todos|items)$", t):
        return _decision(request_id, t, "todo", {"action": "clear_done"})
    # ---- personal memory (SQLite + knowledge base)
    m = re.match(r"^(?:please\s+)?(?:remember|note|keep in mind|don'?t forget)\s+that\s+(?P<f>.{3,})$", t) \
        or re.match(r"^remember\s+(?P<f>(?:my|i|i'm|i've|our|the)\b(?!.*\b(?:to|about)\s+(?:call|buy|send|pay|take|do)\b).{3,})$", t)
    if m:
        return _decision(request_id, t, "remember_fact", {"fact": raw_body(raw, m.group("f"))})
    m = re.match(r"^(?:what do you (?:remember|know)|what did i tell you)(?:\s+about\s+(?P<q>.+))?$", t) \
        or re.match(r"^do you remember\s+(?P<q>.+)$", t) \
        or re.match(r"^where did i (?P<q>park(?:\s+(?:my|the)\s+\w+)?)$", t)
    if m:
        return _decision(request_id, t, "recall_facts", {"query": raw_body(raw, m.group("q")) if m.group("q") else ""})
    m = re.match(r"^forget\s+(?:that|about|what i (?:said|told you) about)\s+(?P<q>.+)$", t)
    if m:
        return _decision(request_id, t, "forget_fact", {"query": raw_body(raw, m.group("q"))})
    # ---- history, passwords, recycle bin
    if re.match(r"^(?:what did i (?:just )?(?:ask|say|tell)(?: you)?(?: (?:earlier|before|last|recently))?|show (?:me )?(?:my )?(?:command |recent )?history|(?:my )?recent commands)$", t):
        return _decision(request_id, t, "command_history", {})
    m = re.match(r"^(?:generate|create|make|give me|suggest)\s+(?:me\s+)?(?:a\s+|an\s+)?(?:new\s+)?(?:strong\s+|secure\s+|random\s+|safe\s+)*password(?:\s+(?:of|with)\s+(?P<n>\d{1,2})\s*(?:characters|chars|letters)?|\s+(?P<n2>\d{1,2})\s*(?:characters|chars) long)?$", t)
    if m:
        n = int(m.group("n") or m.group("n2") or 16)
        return _decision(request_id, t, "generate_password", {"length": max(8, min(64, n))})
    if re.match(r"^(?:empty|clear|clean(?: out)?)\s+(?:the\s+|my\s+)?(?:recycle ?bin|trash|bin)$", t):
        return _decision(request_id, t, "empty_recycle_bin", {})
    return None


_BROWSER_QUICK = [
    (r"^(?:open\s+)?(?:a\s+)?new\s+tab(?:\s+in\s+(?:the\s+)?browser)?$", "new_tab"),
    (r"^close\s+(?:this\s+|the\s+|current\s+|that\s+)?(?:browser\s+)?tab$", "close_tab"),
    (r"^(?:re-?open|restore|bring back|undo close)\s+(?:the\s+)?(?:last\s+)?(?:closed\s+)?tab$", "reopen_tab"),
    (r"^(?:go\s+to\s+|switch\s+to\s+)?(?:the\s+)?next\s+tab$", "next_tab"),
    (r"^(?:go\s+to\s+|switch\s+to\s+)?(?:the\s+)?(?:previous|prev|last\s+used)\s+tab$", "previous_tab"),
    (r"^go\s+back$|^(?:go\s+)?back(?:\s+(?:a|one)\s+page)?\s+in\s+(?:the\s+)?browser$|^(?:go\s+)?(?:to\s+the\s+)?previous\s+page$|^go\s+back\s+a\s+page$", "back"),
    (r"^(?:go\s+)?forward(?:\s+(?:a|one)\s+page)?(?:\s+in\s+(?:the\s+)?browser)?$|^(?:go\s+to\s+(?:the\s+)?)?next\s+page$", "forward"),
    (r"^(?:refresh|reload)\s+(?:the\s+|this\s+)?(?:page|tab|website|site|web\s*page)$|^reload$", "reload"),
    (r"^hard\s+(?:refresh|reload)(?:\s+(?:the\s+|this\s+)?page)?$", "hard_reload"),
    (r"^zoom\s+in(?:\s+(?:the\s+|this\s+)?page)?$|^make\s+(?:the\s+)?(?:page|text)\s+bigger$", "zoom_in"),
    (r"^zoom\s+out(?:\s+(?:the\s+|this\s+)?page)?$|^make\s+(?:the\s+)?(?:page|text)\s+smaller$", "zoom_out"),
    (r"^(?:reset|normal)\s+zoom$|^reset\s+(?:the\s+)?zoom(?:\s+level)?$|^zoom\s+(?:to\s+)?(?:100|normal)%?$", "zoom_reset"),
    (r"^bookmark\s+(?:this|the)(?:\s+(?:page|site|tab|website))?$|^(?:save|add)\s+(?:this\s+)?(?:page|site)\s+(?:to|as\s+a)\s+bookmarks?$", "bookmark"),
    (r"^(?:show|open)\s+(?:my\s+|the\s+)?(?:browser|browsing|chrome|edge)\s+history$", "history"),
    (r"^(?:show|open)\s+(?:my\s+|the\s+)?(?:browser|chrome|edge)\s+downloads$", "downloads"),
    (r"^(?:open\s+)?(?:an?\s+)?(?:incognito|private|inprivate)(?:\s+(?:window|tab|mode|browsing|browser))?$", "incognito"),
    (r"^(?:find|search)\s+(?:on|in)\s+(?:this\s+|the\s+)?page$", "find"),
    (r"^(?:go\s+to|focus|select|click)\s+(?:the\s+)?(?:address|url)\s+bar$", "address_bar"),
    (r"^scroll\s+down(?:\s+(?:a\s+bit|the\s+page|page))?$", "scroll_down"),
    (r"^scroll\s+up(?:\s+(?:a\s+bit|the\s+page|page))?$", "scroll_up"),
    (r"^(?:scroll|go)\s+to\s+(?:the\s+)?top(?:\s+of\s+(?:the\s+)?page)?$", "top"),
    (r"^(?:scroll|go)\s+to\s+(?:the\s+)?bottom(?:\s+of\s+(?:the\s+)?page)?$", "bottom"),
    (r"^(?:open|show|toggle)\s+(?:the\s+)?(?:dev(?:eloper)?\s*tools|inspect\s+element)$", "dev_tools"),
]
_PC_QUICK = [
    (r"^(?:open|show|launch|start|bring up)\s+(?:the\s+)?task\s*manager$", "task_manager"),
    (r"^(?:open|show)\s+(?:the\s+)?(?:windows|pc|computer|system|laptop)\s+settings$", "settings"),
    (r"^(?:open|show|view)\s+(?:my\s+|the\s+)?clipboard(?:\s+(?:history|saved\s+items|items|manager))?$", "clipboard_history"),
    (r"^(?:open|show)\s+(?:the\s+)?emoji(?:s|\s+panel|\s+picker|\s+keyboard)?$", "emoji_panel"),
    (r"^(?:take\s+a\s+|do\s+a\s+)?(?:screen\s+)?(?:snip|clip)(?:\s+of\s+(?:the\s+|my\s+)?screen)?$|^(?:open\s+)?snipping\s+tool$", "snip"),
    (r"^(?:open|show)\s+task\s+view$|^show\s+(?:me\s+)?all\s+(?:my\s+)?open\s+windows$", "task_view"),
    (r"^(?:(?:create|make|add|open)\s+)?(?:a\s+)?new\s+virtual\s+desktop$|^(?:create|make|add|open)\s+(?:a\s+)?new\s+desktop$", "new_desktop"),
    (r"^(?:switch|go|move)\s+to\s+(?:the\s+)?(?:next|right)\s+(?:virtual\s+)?desktop$", "next_desktop"),
    (r"^(?:switch|go|move)\s+to\s+(?:the\s+)?(?:previous|left)\s+(?:virtual\s+)?desktop$", "previous_desktop"),
    (r"^close\s+(?:this|the\s+current)\s+(?:virtual\s+)?desktop$", "close_desktop"),
    (r"^open\s+(?:the\s+)?run(?:\s+(?:dialog|box|window|command))?$", "run_dialog"),
    (r"^(?:project|extend|duplicate|mirror)\s+(?:my\s+)?(?:screen|display)(?:\s+to\s+(?:the\s+)?(?:tv|projector|monitor))?$|^(?:open\s+)?project(?:ion)?\s+(?:menu|options)$", "project_display"),
    (r"^(?:open|show)\s+(?:the\s+)?(?:pc\s+|windows\s+)?(?:notification|action)\s+(?:center|centre|panel)$", "notification_center"),
    (r"^(?:open|show)\s+(?:the\s+)?(?:windows\s+|pc\s+)?quick\s+settings$", "quick_settings"),
    (r"^(?:open\s+)?windows\s+search$", "windows_search"),
]


def match_quick_actions(t: str, request_id: str) -> Optional[RouteDecision]:
    """Browser and Windows shortcuts: instant, no model."""
    if PHONE_REF.search(t):
        return None
    m = re.match(r"^(?:go\s+to|switch\s+to|open|show)\s+(?:the\s+)?tab\s+(?:number\s+)?(\d|one|two|three|four|five|six|seven|eight|nine)$", t) \
        or re.match(r"^(?:go\s+to|switch\s+to|open)\s+(?:the\s+)?(first|second|third|fourth|fifth|last)\s+tab$", t)
    if m:
        v = m.group(1)
        n = int(v) if v.isdigit() else _NUM_WORDS.get(v) or {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "last": 9}[v]
        return _decision(request_id, t, "browser_quick_action", {"action": "go_to_tab", "tab": max(1, min(9, n))})
    for pattern, action in _BROWSER_QUICK:
        if re.match(pattern, t):
            return _decision(request_id, t, "browser_quick_action", {"action": action})
    for pattern, action in _PC_QUICK:
        if re.match(pattern, t):
            return _decision(request_id, t, "pc_quick_action", {"action": action})
    return None


def match_extended(text: str, request_id: str) -> Optional[RouteDecision]:
    """Return a routing decision for the extended domains, or None to continue normal routing."""
    raw = text.strip()
    bulk = match_bulk_reply(raw, request_id)
    if bulk:
        return bulk
    t = re.sub(r"\s+", " ", raw.lower()).strip(" .!?")
    t = re.sub(r"^(?:please|kindly|jarvis|hey jarvis|ok jarvis|can you|could you|would you)\s+", "", t)
    t = re.sub(r"^(?:please|kindly)\s+", "", t)
    if not t:
        return None
    software = match_software(re.sub(r"^(?:please|kindly|jarvis|hey jarvis|can you|could you|would you|just)\s+", "", t), request_id)
    if software:
        return software
    if re.match(r"^(?:continue|carry on|go on|resume|keep going)(?:\s+(?:the|with the|in the))?\s+(?:browser|web)(?:\s+task)?$"
                r"|^(?:i(?:'ve| have)?|ok(?:ay)?,? i(?:'ve| have)?)\s+(?:logged|signed)\s+in(?:\s+now)?(?:,? continue)?$"
                r"|^done logging in$", t) or (re.match(r"^(?:continue|carry on|go on|keep going|resume)$", t) and _web_task_pending()):
        return _decision(request_id, t, "web_task", {"resume": True})
    quick = match_quick_actions(t, request_id)
    if quick:
        return quick
    if re.search(r"\b(?:sms|text message)\b", t):
        sms = _match_phone_quick(t, raw, request_id)
        if sms:
            return sms
    transfer = match_phone_transfer(t, raw, request_id)
    if transfer:
        return transfer
    everyday = match_everyday(t, request_id)
    if everyday:
        return everyday
    utility = match_utilities(t, raw, request_id)
    if utility:
        return utility
    m = re.match(r"^(?:send|push)\s+(?:a\s+|an\s+)?(?:notification|alert|reminder|note)\s+to\s+(?:my\s+|the\s+)?" + PHONE_WORDS +
                 r"(?:\s+(?:saying|that says|with|:)\s+(?P<body>.+))?$", t)
    if m:
        return _decision(request_id, t, "notification_send",
                         {"title": "JARVIS", "message": raw_body(raw, m.group("body")) if m.group("body") else "Message from JARVIS"})
    # ---------------------------------------------------------------- operate the PC by what's on screen
    if not PHONE_REF.search(t):
        m = re.match(r"^(?:use|control)\s+(?:my|the)\s+(?:computer|pc|laptop|mouse|screen)\s+(?:to|and)\s+(?P<goal>.+)$", t)
        if m:
            return _decision(request_id, t, "computer_task", {"goal": raw_body(raw, m.group("goal"))})
        m = re.match(r"^(?:in|on|inside)\s+(?:the\s+)?(?P<app>[a-z][\w.+-]*(?:\s+[a-z][\w.+-]*){0,2}?)(?:\s+app)?,?\s+"
                     r"(?P<rest>(?:click|type|turn|enable|disable|change|set|select|make|go to|switch|toggle|press|choose|scroll)\b.+)$", t)
        if m and not re.match(r"^(?:\d|a minute|an hour|the morning|the evening|whatsapp|my phone|the phone|google|youtube|amazon|flipkart)", m.group("app")):
            return _decision(request_id, t, "computer_task", {"goal": raw})
        m = re.match(r"^(?P<how>double[- ]click|right[- ]click|click|press|hit|select|tap)\s+(?:on\s+)?(?P<target>.+?)$", t)
        consequential = re.search(r"\b(?:continue|submit|confirm|download|send|pay|delete|buy|accept|agree|yes|proceed|install|"
                                  r"uninstall|remove|sign out|log ?out|purchase|checkout|order)\b", m.group("target")) if m else None
        if m and not consequential and not re.fullmatch(r"(?:the\s+)?(?:enter|escape|esc|tab|space|spacebar|backspace|delete|home|end|f\d{1,2}|up|down|left|right|"
                                  r"play|pause|next|previous|windows key|win)(?:\s+key)?|.*\+.*", m.group("target")):
            how = m.group("how").replace(" ", "-")
            return _decision(request_id, t, "screen_click", {"target": raw_body(raw, m.group("target")),
                                                            "button": "right" if how == "right-click" else "left",
                                                            "double": how == "double-click"})

    # ---------------------------------------------------------------- screen understanding (vision)
    if re.match(r"^(?:what(?:'s| is| does)|read|look at|describe|explain|check|can you see|tell me what)\b.*\b(?:my |the |this |on )?(?:screen|monitor|display|error on (?:my|the) screen)\b", t) \
            and not re.search(r"\b(?:screenshot|brightness|resolution|record|share|lock|off|on my phone|phone)\b", t):
        return _decision(request_id, t, "describe_screen", {"device": "pc", "question": raw})

    if _is_compound(t):
        # Multi-action requests belong to the planner; only messaging (whose body may contain verbs) continues.
        return _match_whatsapp(t, raw, request_id) if re.match(r"^(?:ask|remind|let|inform|wish|reply|respond|tell|text|message|msg|ping|whatsapp)\b", t) else None

    # ---------------------------------------------------------------- open questions (knowledge / conversation)
    if (OPEN_QUESTION.match(t) and not DEVICE_TERMS.search(t) and not _FIND_MY.search(t)
            and not _REFERENTIAL.search(t) and not _is_compound(t)):
        return _question(request_id, t)

    # ---------------------------------------------------------------- self-directed chat
    if re.match(r"^(?:tell|give|show)\s+me\s+(?:a|an|some|another|one more)\s+(?:joke|fun fact|fact|quote|story|riddle|poem|motivational quote)s?\b", t) \
            or re.match(r"^(?:tell|teach)\s+me\s+(?:about|how|what|why|who|when|where|something)\b(?!.*\b(?:time|date|day is it|battery|volume|brightness|wi-?fi)\b)", t) \
            or re.match(r"^(?:make me laugh|cheer me up|motivate me|say something(?: nice| funny)?|how are you(?: doing)?|who are you|what can you do|what are your capabilities)$", t) \
            or re.match(r"^(?:write|draft|compose)\s+(?:me\s+)?(?:a|an)\s+(?:poem|story|essay|summary|paragraph|haiku|limerick|caption|bio)\b", t) \
            or re.match(r"^(?:explain|define|translate|summari[sz]e)\s+(?!my\b|the file|this file|that file|it\b)(?!.*\b(?:news|headlines|whatsapp|messages|emails?|inbox)\b)\S", t):
        return _question(request_id, t)

    # ---------------------------------------------------------------- weather / live info questions
    if re.match(r"^(?:what(?:'s| is) the |how(?:'s| is) the |check the |get the |show (?:me )?the )?(?:weather|forecast|temperature)\b", t) \
            or re.match(r"^(?:will it|is it going to|is it gonna)\s+(?:rain|snow|be (?:hot|cold|sunny))\b", t) \
            or re.match(r"^(?:ask|search)\s+(?:google|the web|the internet|online)\s+(?:who|what|when|where|why|how|which|if|whether)\b", t):
        return _question(request_id, t)

    # ---------------------------------------------------------------- reminders
    m = re.match(r"^(?:remind me|set (?:a )?reminder|create (?:a )?reminder|add (?:a )?reminder)(?:\s+(?:to|that|about|for))?\s+(?P<body>.+)$", t)
    if m:
        return _decision(request_id, t, "set_reminder", {"text": raw_body(raw, m.group("body"))})
    m = re.match(r"^(?:list|show|what are) (?:my )?(?:pending |upcoming )?reminders$", t)
    if m:
        return _decision(request_id, t, "list_reminders", {})

    # ---------------------------------------------------------------- knowledge base (RAG)
    m = re.match(rf"^(?:learn|index|memori[sz]e|study|ingest|read and remember|scan and learn)\s+(?:everything in\s+|all (?:the )?(?:files|documents) in\s+|the (?:files|documents) in\s+)?(?:my\s+|the\s+)?(?P<target>{FOLDER_WORDS}(?:\s+folder)?|[a-z]:[\\/].+|~[\\/].+|/.+|\S+\.(?:pdf|docx|txt|md|csv|py))$", t)
    if m:
        target = re.sub(r"\s+folder$", "", m.group("target")).strip()
        if not re.match(r"^(?:[a-z]:[\\/]|~|/)", target) and "." not in target:
            target = {"doc": "documents", "docs": "documents", "document": "documents", "download": "downloads", "photos": "pictures"}.get(target, target)
        else:
            target = raw_body(raw, target)
        return _decision(request_id, t, "knowledge_ingest", {"path": target})
    m = re.match(rf"^(?:add|put)\s+(?P<target>.+?)\s+(?:to|into|in)\s+(?:your|the|my)\s+(?:knowledge(?: base)?|memory|brain|rag)$", t)
    if m:
        target = re.sub(r"^(?:my|the)\s+|\s+folder$", "", m.group("target")).strip()
        return _decision(request_id, t, "knowledge_ingest", {"path": raw_body(raw, target)})
    m = re.match(rf"^(?:search|ask|query|check|look in)\s+(?:my|the)\s+{KNOWLEDGE_WORDS}\s+(?:for|about|on|regarding)\s+(?P<q>.+)$", t) \
        or re.match(rf"^what\s+(?:do|does)\s+(?:my|the)\s+{KNOWLEDGE_WORDS}\s+say\s+(?:about|on)\s+(?P<q>.+)$", t) \
        or re.match(rf"^(?:according to|based on|from)\s+my\s+{KNOWLEDGE_WORDS},?\s+(?P<q>.+)$", t)
    if m:
        if re.search(r"\bmy notes\b", t) and not re.search(r"\bsay\b", t):
            return _decision(request_id, t, "search_notes", {"query": raw_body(raw, m.group("q"))})
        return _decision(request_id, t, "knowledge_search", {"question": raw_body(raw, m.group("q"))})

    # ---------------------------------------------------------------- web agent (multi-step browsing goals)
    m = re.match(r"^(?:use|using) (?:the |my )?(?:browser|web|internet|chrome|edge) (?:to |and )?(?P<goal>.{6,})$", t) \
        or re.match(r"^(?:go online and|browse the web (?:to|and)|on the web,?|online,) (?P<goal>.{6,})$", t) \
        or re.match(r"^(?P<goal>(?:find|check|look up|compare) (?:the )?(?:price|prices|cost|reviews?|rating|availability) of .+ on (?:amazon|flipkart|the web|google|ebay|myntra|croma))$", t)
    if m:
        return _decision(request_id, t, "web_task", {"goal": raw_body(raw, m.group("goal"))})

    # ---------------------------------------------------------------- web: site search & URLs
    m = re.match(rf"^(?:search|look up|find)\s+(?:on\s+)?(?P<site>{_SITES})\s+(?:for\s+)?(?P<q>.+)$", t) \
        or re.match(rf"^(?:search for|look up|find|search)\s+(?P<q>.+?)\s+(?:on|in|at|using)\s+(?P<site>{_SITES})$", t) \
        or re.match(rf"^(?:go to|open|visit|launch)\s+(?P<site>{_SITES})(?:\.com|\.in|\.org)?\s+and\s+(?:search|look up|find)\s+(?:for\s+)?(?P<q>.+)$", t)
    if m:
        site = m.group("site")
        query = m.group("q").strip(" .")
        if site == "youtube" and not re.search(r"\bsearch\b", t):
            return None  # "play X on youtube" is handled by play_youtube
        template = SITE_SEARCH[site]
        encoded = urllib.parse.quote_plus(query) if "?" in template else urllib.parse.quote(query)
        url = template.format(q=encoded)
        return _decision(request_id, t, "open_website", {"url": url, "title": f"{site.title()} search: {query}"})
    m = re.match(r"^(?:go to|open|visit|browse to|navigate to|load)\s+(?:the\s+)?(?:website\s+|site\s+|page\s+)?(?P<url>\S+)$", t)
    if m and _URLISH.match(m.group("url")):
        return _decision(request_id, t, "open_website", {"url": m.group("url")})

    # ---------------------------------------------------------------- phone control
    if PHONE_REF.search(t) and not re.search(r"\b(?:send|share|transfer|push)\b.*\bto (?:my |the )?" + PHONE_WORDS, t):
        decision = _match_phone(t, raw, request_id)
        if decision:
            return decision

    # ---------------------------------------------------------------- WhatsApp messaging
    decision = _match_whatsapp(t, raw, request_id)
    if decision:
        return decision
    return None


def raw_body(raw: str, lowered_fragment: str) -> str:
    """Recover the original casing of a fragment matched in the lowered text."""
    idx = raw.lower().find(lowered_fragment.lower())
    if idx >= 0:
        return raw[idx: idx + len(lowered_fragment)].strip()
    return lowered_fragment.strip()


_TOGGLES = {
    "wifi": r"wi-?fi|wireless", "bluetooth": r"blue ?tooth", "mobile_data": r"mobile data|data|internet|cellular data",
    "airplane_mode": r"air ?plane mode|flight mode", "do_not_disturb": r"do not disturb|dnd|silent mode",
    "auto_rotate": r"auto ?-?rotat(?:e|ion)|screen rotation",
}


_NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_PHONE_SETTINGS_PAGES = ("wifi", "wi-fi", "bluetooth", "battery", "display", "sound", "location", "apps", "storage", "hotspot",
                         "data usage", "security", "developer", "date")


def _match_phone_quick(t: str, raw: str, request_id: str) -> Optional[RouteDecision]:
    body = re.sub(ON_PHONE + r"\b", " ", t)
    body = " ".join(re.sub(rf"\b(?:(?:my|the)\s+)?{PHONE_WORDS}(?:'s)?\b", " ", body).split())
    m = re.match(r"^(?:set|change|put|make)?\s*(?:the\s+)?(?:screen\s+)?brightness\s+(?:to\s+|at\s+)?(\d{1,3})\s*(?:%|percent)?$", body)
    if m:
        return _decision(request_id, t, "android_quick_action", {"action": "brightness", "value": m.group(1)})
    m = re.match(r"^(?:set|change|put|make)?\s*(?:the\s+)?(?:media\s+|music\s+)?volume\s+(?:to\s+|at\s+)?(\d{1,2})$", body)
    if m:
        return _decision(request_id, t, "android_quick_action", {"action": "media_volume", "value": m.group(1)})
    if re.match(r"^(?:open|show|pull down|swipe down)\s+(?:the\s+)?quick\s+(?:settings|toggles)(?:\s+panel)?$", body):
        return _decision(request_id, t, "android_quick_action", {"action": "quick_settings"})
    if re.match(r"^(?:open|show|pull down|swipe down|expand)\s+(?:the\s+)?(?:notification|notifications)\s+(?:shade|panel|bar|drawer)$", body):
        return _decision(request_id, t, "android_quick_action", {"action": "notifications_panel"})
    if re.match(r"^(?:close|collapse|hide)\s+(?:the\s+)?(?:notification\s+|quick\s+settings\s+)?(?:panels?|shade|drawer)$", body):
        return _decision(request_id, t, "android_quick_action", {"action": "collapse_panels"})
    m = re.match(r"^(?:open|show|go to)\s+(?:the\s+)?(?:(?P<page>" + "|".join(_PHONE_SETTINGS_PAGES) + r")\s+)?settings$", body)
    if m:
        page = (m.group("page") or "main").replace("-", "").replace(" ", "_")
        return _decision(request_id, t, "android_quick_action", {"action": "settings", "value": page})
    if re.match(r"^(?:what|which)\s+app\s+(?:is\s+)?(?:open|running|on screen|showing)(?:\s+(?:now|right now))?$", body):
        return _decision(request_id, t, "android_quick_action", {"action": "current_app"})
    m = re.match(r"^(?:send\s+(?:an?\s+)?)?(?:sms|text\s+message)\s+(?:to\s+)?(?P<num>\+?[\d ]{6,18})\s+(?:saying|that says|with)\s+(?P<body>.+)$", body) \
        or re.match(r"^(?:sms|text)\s+(?P<num>\+?[\d ]{6,18})\s+(?:saying|that)\s+(?P<body>.+)$", body)
    if m:
        return _decision(request_id, t, "android_quick_action",
                         {"action": "sms_draft", "number": re.sub(r"\s", "", m.group("num")), "text": raw_body(raw, m.group("body"))})
    return None


def _match_phone(t: str, raw: str, request_id: str) -> Optional[RouteDecision]:
    quick = _match_phone_quick(t, raw, request_id)
    if quick:
        return quick
    if re.search(r"\b(?:notifications?|alerts)\b", t) and re.match(r"^(?:read|show|check|what(?:'s| are)?|any|do i have|tell me)\b", t) \
            and not re.match(r"^(?:send|push)\b", t):
        return _decision(request_id, t, "android_notifications", {})
    m = re.match(r"^(?:turn|switch|put|set)\s+(?P<state>on|off)\s+(?:the\s+)?(?P<what>.+?)" + ON_PHONE + r"$", t) \
        or re.match(r"^(?:turn|switch|put|set)\s+(?:the\s+)?(?P<what>.+?)\s+(?P<state>on|off)" + ON_PHONE + r"$", t) \
        or re.match(r"^(?P<state>enable|disable)\s+(?:the\s+)?(?P<what>.+?)" + ON_PHONE + r"$", t)
    if m:
        what = m.group("what").strip()
        for setting, pattern in _TOGGLES.items():
            if re.fullmatch(rf"(?:{pattern})", what):
                return _decision(request_id, t, "android_toggle", {"setting": setting, "on": m.group("state") in ("on", "enable")})
    m = re.match(r"^(?:tap|press|click|touch|hit)\s+(?:on\s+)?(?:the\s+)?(?P<label>.+?)(?:\s+button)?" + ON_PHONE + r"$", t)
    if m and not re.match(r"^(?:home|back|power|volume)", m.group("label")):
        return _decision(request_id, t, "android_tap_text", {"text": raw_body(raw, m.group("label"))})
    if re.search(r"\b(?:what(?:'s| is)|read|look at|describe|see|check)\b.*\bscreen\b", t):
        return _decision(request_id, t, "describe_screen", {"device": "phone", "question": raw})

    body = re.sub(ON_PHONE + r"\s*$", "", t).strip()
    body = re.sub(rf"^(?:on|in)\s+(?:my\s+|the\s+)?{PHONE_WORDS}\s*,?\s*", "", body)
    body = re.sub(rf"\s+(?:my|the)\s+{PHONE_WORDS}(?:'s)?\b", "", body).strip()

    if re.search(r"\b(?:screenshot|screen ?shot|screen capture|capture (?:the |my )?screen|snap the screen)\b", t):
        return _decision(request_id, t, "android_screenshot", {})
    if re.search(r"\b(?:mirror|show (?:my |the )?(?:phone )?screen|screen mirror|scrcpy|control my phone|phone control)\b", t) \
            or re.search(rf"\b{PHONE_WORDS}(?:'s)? screen\b(?!\s+(?:shot|off|on\b(?!\s+(?:my|the|pc|computer|monitor|laptop|desktop))))", t):
        return _decision(request_id, t, "android_open_control", {})
    if re.search(r"\b(?:battery|connected|connectivity|connection|status|charging|charge level)\b", t):
        return _decision(request_id, t, "android_status", {})

    m = re.match(r"^(?:call|dial|ring)\s+(?P<who>.+)$", body)
    if m:
        who = m.group("who").strip()
        digits = re.sub(r"[^\d+]", "", who)
        if len(re.sub(r"\D", "", digits)) >= 6:
            return _decision(request_id, t, "android_dial", {"number": digits})
        return _decision(request_id, t, "android_dial", {"number": raw_body(raw, who)})

    m = re.match(r"^(?:type|write|enter|input)\s+(?P<text>.+)$", body)
    if m:
        return _decision(request_id, t, "android_input", {"action": "text", "text": raw_body(raw, m.group("text"))})

    m = re.match(r"^(?:open|go to|visit|browse)\s+(?P<url>\S+)$", body)
    if m and _URLISH.match(m.group("url")):
        return _decision(request_id, t, "android_open_url", {"url": m.group("url")})

    if re.search(r"\b(?:go )?(?:home|home screen)\b", body) and re.match(r"^(?:go|press|tap|return|take me|open)?\s*(?:to\s+)?(?:the\s+)?home", body):
        return _decision(request_id, t, "android_home", {})
    if re.match(r"^(?:go |press )?back$", body):
        return _decision(request_id, t, "android_back", {})

    for key, phrases in ANDROID_KEYS.items():
        for phrase in phrases:
            if re.search(rf"\b{re.escape(phrase)}\b", body) or body == phrase:
                if key == "camera" and not re.match(r"^(?:open |launch |start )?(?:the )?camera$", body):
                    continue
                return _decision(request_id, t, "android_key", {"key": key})

    m = re.match(r"^(?:open|launch|start|run)\s+(?:the\s+)?(?P<app>[a-z0-9 .+&'-]{2,40}?)(?:\s+app)?$", body)
    if m:
        return _decision(request_id, t, "android_open_app", {"app_name": m.group("app").strip()})
    return None


def _match_whatsapp(t: str, raw: str, request_id: str) -> Optional[RouteDecision]:
    has_wa = "whatsapp" in t or "whats app" in t
    stripped = _WHATSAPP_TAIL.sub("", t)
    raw_stripped = _WHATSAPP_TAIL.sub("", raw.strip(" .!?"))

    # Reply to the latest message (optionally from someone, optionally with guidance).
    m = re.match(r"^(?:reply|respond|answer|write back)(?:\s+to)?\s+(?:the\s+)?(?:last|latest|recent|new)\s+(?:whatsapp\s+)?(?:message|msg|text)(?:\s+from\s+(?P<who>[\w .'-]+?))?(?:\s+(?:saying|with|that|and say)\s+(?P<body>.+))?$", stripped)
    if m:
        slots = {}
        if m.group("who"):
            slots["recipient"] = raw_body(raw, _clean_person(m.group("who")))
        if m.group("body"):
            slots["instruction"] = raw_body(raw_stripped, m.group("body"))
        return _decision(request_id, t, "reply_whatsapp_message", slots)
    m = re.match(r"^(?:reply|respond|write back|answer)\s+(?:to\s+)?(?P<who>[\w .'-]+?)(?:'s\s+(?:message|msg|text))?(?:\s+(?:saying|with|that|and say|and tell (?:him|her|them))\s+(?P<body>.+))?$", stripped)
    if m and _looks_like_person(_clean_person(m.group("who")), t) and not re.match(r"^(?:email|mail|all|everyone|the)\b", m.group("who")):
        slots = {"recipient": raw_body(raw, _clean_person(m.group("who")))}
        if m.group("body"):
            slots["instruction"] = raw_body(raw_stripped, m.group("body"))
        return _decision(request_id, t, "reply_whatsapp_message", slots)

    patterns = (
        ("ask", r"^ask\s+(?P<who>[\w .'+-]+?)\s+(?P<body>(?:if|whether|about|to|for|when|what|where|why|how|who|which|is|are|does|do|can|will)\b.+)$"),
        ("remind", r"^remind\s+(?P<who>[\w .'+-]+?)\s+(?P<body>(?:to|about|that|of)\b.+)$"),
        ("inform", r"^let\s+(?P<who>[\w .'+-]+?)\s+know\s+(?P<body>.+)$"),
        ("inform", r"^inform\s+(?P<who>[\w .'+-]+?)\s+(?P<body>(?:that|about)\b.+)$"),
        ("wish", r"^wish\s+(?P<who>[\w .'+-]+?)\s+(?P<body>(?:a\s+)?(?:very\s+)?(?:happy|merry|good|congrat|best|all the best|luck|safe).+)$"),
        ("direct", r"^(?:tell|text|message|msg|ping|whatsapp|send)\s+(?:a\s+(?:message|msg|text)\s+to\s+)?(?P<who>[\w .'+-]+?)\s+(?:saying|that says|to say|stating|with the message|with message)\s+(?P<body>.+)$"),
    )
    for style, pattern in patterns:
        m = re.match(pattern, stripped)
        if not m:
            continue
        who = _clean_person(m.group("who"))
        if who.lower() in ("me", "myself", "us") and style == "remind":
            return None  # "remind me ..." is a reminder, not a message
        if not _looks_like_person(who, t) or (style != "direct" and not has_wa and who.lower() not in RELATION_WORDS and not _known_contact(who)):
            return None
        body = raw_body(raw_stripped, m.group("body")).strip()
        slots = {"recipient": raw_body(raw, who), "message": body}
        return _decision(request_id, t, "send_whatsapp_message", slots,
                         context_trace={"compose_style": style, "raw_text": raw})
    return None


def _known_contact(who: str) -> bool:
    try:
        contact, ambiguous, _ = _contact_resolver().resolve(who)
        return bool(contact or ambiguous)
    except Exception:
        return False
