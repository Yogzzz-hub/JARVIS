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
)


def _is_compound(text: str) -> bool:
    return bool(_COMPOUND.search(text)) or bool(_COMPOUND_JOIN.search(text))


def match_extended(text: str, request_id: str) -> Optional[RouteDecision]:
    """Return a routing decision for the extended domains, or None to continue normal routing."""
    raw = text.strip()
    t = re.sub(r"\s+", " ", raw.lower()).strip(" .!?")
    t = re.sub(r"^(?:please|kindly|jarvis|hey jarvis|ok jarvis|can you|could you|would you)\s+", "", t)
    t = re.sub(r"^(?:please|kindly)\s+", "", t)
    if not t:
        return None
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


def _match_phone(t: str, raw: str, request_id: str) -> Optional[RouteDecision]:
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
