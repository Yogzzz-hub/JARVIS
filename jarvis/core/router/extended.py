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

PHONE_WORDS = r"(?:phone|mobile|android(?!\s+(?:studio|emulator|sdk))|cell ?phone|smartphone)"  # Android Studio is a PC app
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
_URLISH = re.compile(r"^(?:https?://)?(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|org|net|io|ai|dev|edu|in|co|app|gov|me|tv|info|uk|us|to|gg|ly|xyz|site|online|tech|blog|news|biz|cc|fm|so|sh|page|"
    r"link|store|shop|cloud|live|au|ca|de|fr|jp|sg|ae|lk|pk)(?:/\S*)?$", re.I)
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
        if contact or ambiguous:
            return True
    except Exception:
        pass
    # not saved (yet): a name-like word still reads as a person; the send step looks it up and asks if unknown
    return _name_like(low)


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
    rf"|^{PHONE_WORDS}\b(?!\s+(?:app|apps|number|bill|case|call|charger|plan))|\bandroid\b(?!\s+(?:studio|emulator|sdk))"
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
    r"(?:messag|text|ping|whats\s?app|chat|writ|dm|contact|reach|wish|typ|call|mail)\w*\s+(?:to\s+|with\s+)?me\b(?:\s+(?:on|in|via)\s+whats\s?app)?"
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


_LEARN_CHATS = re.compile(
    r"^(?:please\s+)?(?:learn|train|study|import|feed)\s+(?:on\s+|from\s+)?(?:all\s+)?(?:my\s+|the\s+)?"
    r"(?:whats\s?app\s+|chat\s+)?(?:chats?|chat\s+(?:exports?|files?|history)|exports?|feed(?:\s+folder)?|conversations?|"
    r"texting\s+style|style)(?:\s+(?:from|in)\s+(?:the\s+)?(?:feed(?:\s+folder)?|folder))?"
    r"|^(?:my\s+)?(?:whats\s?app\s+)?chats?\s+(?:ellam\s+)?(?:learn|train|import)\s+(?:pannu|panu)")


def match_learn_chats(text: str, request_id: str) -> Optional[RouteDecision]:
    """'Learn my WhatsApp chats' -> import every chat file in data/whatsapp_feed (all supported formats)."""
    t = re.sub(r"\s+", " ", (text or "").lower()).strip(" .!?")
    t = re.sub(r"^(?:hey |ok )?jarvis,? ", "", t)
    if _LEARN_CHATS.search(t) and "group" not in t:
        return _decision(request_id, t, "whatsapp_learn_chats", {})
    return None


def match_bulk_reply(text: str, request_id: str) -> Optional[RouteDecision]:
    """'Send all the guys who are messaging me that I'm busy' -> reply_whatsapp_all (personal chats only)."""
    raw = (text or "").strip()
    auto = match_auto_reply(raw, request_id)  # time-boxed auto-reply grants come first ("reply to everyone until 10")
    if auto:
        return auto
    learn = match_learn_chats(raw, request_id)
    if learn:
        return learn
    t0 = re.sub(r"\s+", " ", raw.lower()).strip(" .!?")
    if re.fullmatch(r"(?:(?:do i have|have i got|got|are there|is there)\s+)?any\s+(?:new\s+|unread\s+)?(?:whats\s?app\s+)?"
                    r"(?:chats?|messages?|msgs?|texts?)(?:\s+(?:on|in)\s+whats\s?app)?(?:\s+for\s+me)?", t0):
        return _decision(request_id, t0, "summarize_whatsapp_messages", {})
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
    tail = re.sub(r"^(?:is|as|like|with|to)\s+", "", tail.strip())  # "... typing to me is i am at work"
    body = raw_body(raw, tail).strip(" ,.;:") if tail.strip() else ""
    slots = {"message": body, "request": raw}
    return _decision(request_id, t, "reply_whatsapp_all", slots, context_trace={"bulk_reply": True})


_WA_IN_ON = r"(?:\s+(?:in|on|from|via|to|of)\s+(?:my\s+)?whats\s*app)"
_MSG_WORDS = r"(?:messages?|msgs?|texts?|chats?)"
_UNREAD_WORDS = r"(?:unread|new|recent|pending|latest)"
_GROUP_WORD = re.compile(r"\b(?:groups?|grps?)\b", re.I)
_COUNT_WORDS = re.compile(r"\b(?:total|how many|count|number of)\b")


def match_whatsapp_read(t: str, raw: str, request_id: str) -> Optional[RouteDecision]:
    """Instant deterministic routing for reading/counting/summarising WhatsApp messages."""
    if _GROUP_WORD.search(t):
        return None

    # 1. Summaries: "summarize whatsapp", "summarize my whatsapp messages", "whatsapp summary", "who messaged me on whatsapp"
    if re.match(rf"^(?:summari[sz]e|summary of)\s+(?:my\s+|the\s+)?(?:whats\s*app(?:\s+{_MSG_WORDS})?|{_MSG_WORDS}{_WA_IN_ON})$", t) \
            or re.match(r"^whats\s*app\s+summary$", t) \
            or re.match(rf"^(?:who\s+messaged\s+me|who\s+sent\s+me\s+{_MSG_WORDS}){_WA_IN_ON}$", t):
        return _decision(request_id, t, "summarize_whatsapp_messages", {})

    # 2. Count or read WhatsApp messages
    is_wa_read = (
        # "tell me the total unread msg in whatsapp", "tell me my unread messages in whatsapp", "what is the total unread msg in whatsapp"
        re.match(rf"^(?:tell me|show me|what(?:'s| is| are)|check|get|read)(?:\s+(?:the|all|my|any))?(?:\s+(?:total|count of|number of))?(?:\s+{_UNREAD_WORDS})?\s+{_MSG_WORDS}{_WA_IN_ON}$", t)
        # "how many unread messages in whatsapp", "how many unread messages do i have in whatsapp"
        or re.match(rf"^how many(?:\s+total)?(?:\s+{_UNREAD_WORDS})?\s+{_MSG_WORDS}(?:\s+(?:do i have|are there))?{_WA_IN_ON}$", t)
        or re.match(rf"^(?:how many|any|are there(?:\s+any)?|do i have(?:\s+any)?)(?:\s+{_UNREAD_WORDS})?\s+whats\s*app\s+{_MSG_WORDS}(?:\s+(?:do i have|are there|today|now))?$", t)
        # "total unread messages in whatsapp", "the total unread msg in whatsapp"
        or re.match(rf"^(?:the\s+)?(?:total\s+)?{_UNREAD_WORDS}\s+{_MSG_WORDS}{_WA_IN_ON}$", t)
        # "any unread messages in whatsapp", "do i have any unread messages in whatsapp"
        or re.match(rf"^(?:do i have\s+|are there\s+)?any\s+{_UNREAD_WORDS}\s+{_MSG_WORDS}{_WA_IN_ON}$", t)
        # "read my whatsapp messages", "check whatsapp messages", "show whatsapp messages"
        or re.match(rf"^(?:read|check|show|get)\s+(?:my\s+|the\s+)?(?:{_UNREAD_WORDS}\s+)?whats\s*app(?:\s+{_MSG_WORDS})?$", t)
        # "whatsapp unread messages", "whatsapp messages"
        or re.match(rf"^whats\s*app(?:\s+{_UNREAD_WORDS})?\s+{_MSG_WORDS}$", t)
        # "tell me my whatsapp messages", "tell me whatsapp messages"
        or re.match(rf"^(?:tell me|what are)\s+(?:my\s+|the\s+)?whats\s*app(?:\s+{_MSG_WORDS})?$", t)
    )
    if is_wa_read:
        filt = "unread"
        if "urgent" in t:
            filt = "urgent"
        elif " all " in f" {t} ":
            filt = "all"
        slots = {"filter": filt}
        if _COUNT_WORDS.search(t):
            slots["count_only"] = True  # "total" / "how many": the exact number, per person
        return _decision(request_id, t, "read_whatsapp_messages", slots)

    # 1b. "what's new on whatsapp", "anything new in whatsapp", "whatsapp updates"
    if re.fullmatch(r"(?:what(?:'s| is)\s+(?:new|up|happening)|anything\s+new|any\s+updates?|what\s+did\s+i\s+miss)\s+"
                    r"(?:on|in)\s+(?:my\s+)?whats\s*app|whats\s*app\s+updates?", t):
        return _decision(request_id, t, "summarize_whatsapp_messages", {})

    # 2b. "read messages waiting for my reply", "who is waiting for my reply", "which messages need a reply"
    if re.fullmatch(rf"(?:(?:read|show|check|which|what)(?:\s+me)?\s+)?(?:my\s+|the\s+)?{_MSG_WORDS}\s+(?:are\s+)?(?:waiting\s+for|that\s+need|"
                    r"needing|need)\s+(?:a\s+|my\s+|an\s+)?(?:reply|replies|response|answer)(?:\s+(?:on|in)\s+whats\s*app)?", t) \
            or re.fullmatch(r"who(?:\s+all)?\s+(?:is|are)\s+(?:still\s+)?waiting\s+for\s+(?:my\s+|a\s+)?(?:reply|response|answer)"
                            r"(?:\s+(?:on|in)\s+whats\s*app)?", t):
        return _decision(request_id, t, "read_whatsapp_messages", {"filter": "needs_reply"})

    # 3. Reading / counting unread messages without explicitly saying "in whatsapp"
    # "read my unread messages", "show my new messages"
    if re.fullmatch(rf"(?:read|check|show)(?:\s+me)?\s+(?:my\s+|the\s+|all\s+(?:my\s+|the\s+)?)?(?:unread|new)\s+{_MSG_WORDS}", t):
        return _decision(request_id, t, "read_whatsapp_messages", {"filter": "unread"})
    # "tell me the total unread messages", "how many unread messages", "how many unread messages do i have"
    if re.match(rf"^(?:tell me\s+)?(?:the\s+)?(?:total\s+)?unread\s+{_MSG_WORDS}$", t) \
            or re.match(rf"^how many\s+(?:total\s+)?(?:unread\s+|new\s+)?{_MSG_WORDS}(?:\s+(?:do i have|have i got|are there|did i get|i have|i got))?(?:\s+(?:today|now))?$", t) \
            or re.match(rf"^(?:what(?:'s| is| are)\s+)?(?:the\s+)?(?:total\s+|number\s+of\s+|count\s+of\s+)(?:unread\s+|new\s+)?{_MSG_WORDS}$", t):
        slots = {"filter": "unread"}
        if _COUNT_WORDS.search(t):
            slots["count_only"] = True
        return _decision(request_id, t, "read_whatsapp_messages", slots)

    # 4. "who messaged me", "who texted me today", "anyone messaged me?"
    if re.fullmatch(r"(?:who(?:\s+all)?|anyone|anybody|did anyone|has anyone)\s+(?:has\s+|have\s+)?(?:messaged|texted|pinged|msged|"
                    r"sent\s+(?:me\s+)?(?:a\s+)?(?:message|msg|text))(?:\s+me)?(?:\s+(?:today|now|recently|just now))?", t):
        return _decision(request_id, t, "summarize_whatsapp_messages", {})

    # 4b. "did arun reply", "has priya texted back"
    m = re.fullmatch(r"(?:did|has)\s+(?P<who>[a-z][a-z .'-]{0,30}?)\s+(?:reply|replied|respond(?:ed)?|answer(?:ed)?|text(?:ed)?\s+back|"
                     r"message(?:d)?\s+back|write\s+back|wrote\s+back|get\s+back(?:\s+to\s+me)?)(?:\s+(?:yet|to\s+me|on\s+whatsapp))?", t)
    if m and m.group("who").strip() not in ("you", "u", "it", "they", "he", "she", "anyone", "someone", "jarvis"):
        return _decision(request_id, t, "read_whatsapp_messages", {"filter": "all", "sender": raw_body(raw, m.group("who").strip()), "limit": 5})

    # 5. One person's messages: "what did arun say", "what did amma send", "messages from priya", "what is arun saying"
    if re.match(r"^what(?:'s|\s+is|\s+does)\s+(?:this|that|the)\s+(?:popup|pop-up|dialog|window|box|notification|error|warning|alert|screen|app|page|website|site)\b", t):
        return None  # something on the screen, not a WhatsApp contact
    m = (re.fullmatch(r"what\s+(?:did|has)\s+(?P<who>[a-z][a-z .'-]{0,30}?)\s+(?:say|said|send|sent|text|texted|message|messaged|write|wrote)"
                      r"(?:\s+(?:me|to me))?(?:\s+(?:today|now|recently|just now|on whatsapp|in whatsapp))?", t)
         or re.fullmatch(r"what\s+(?:is|'s)\s+(?P<who>[a-z][a-z .'-]{0,30}?)\s+(?:saying|asking|telling me)", t)
         or re.fullmatch(r"what\s+(?P<who>[a-z][a-z .'-]{0,30}?)\s+(?:said|sent|texted|wrote|asked|messaged)(?:\s+(?:me|to me))?"
                         r"(?:\s+(?:today|now|recently|on whatsapp|in whatsapp))?", t)
         or re.fullmatch(rf"(?:read\s+|show\s+|check\s+|any\s+|are\s+there\s+any\s+)?(?:the\s+|my\s+)?(?:latest\s+|last\s+|new\s+|unread\s+)?(?:whatsapp\s+)?{_MSG_WORDS}\s+from\s+"
                         r"(?P<who>[a-z0-9][a-z0-9 .'+-]{0,30}?)(?:\s+(?:on|in)\s+whats\s*app)?", t))
    if m:
        who = m.group("who").strip()
        if who not in ("you", "u", "it", "they", "that", "this", "he", "she", "we", "someone", "anyone", "everyone", "jarvis"):
            return _decision(request_id, t, "read_whatsapp_messages", {"filter": "all", "sender": raw_body(raw, who), "limit": 5})

    return None



_ON_PC = r"(?:\s+(?:for me|please|now|right now|quickly))?(?:\s+(?:on|in|to|from)\s+(?:my|this|the)\s+(?:pc|laptop|computer|system|machine|desktop))?(?:\s+(?:for me|please|now))?"
_APP = r"(?P<app>[a-z0-9][a-z0-9 .+#&'-]{0,48}?)"


def match_software(t: str, request_id: str) -> Optional[RouteDecision]:
    """install / uninstall / update applications (winget)."""
    t = re.sub(r"^(?:can|could|would|will)\s+(?:you|u)\s+(?:please\s+|pls\s+|plz\s+)?", "", t)
    # "install cisco packet tracer and set up and do all installation" - the extra words are not part of the name
    t = re.sub(r"\s*(?:,|and|&|then)\s+(?:(?:please|also)\s+)?(?:set\s*(?:it\s+)?up|setup|configure|finish|complete|do\s+(?:all|the|every)\w*|"
               r"make\s+it\s+work|run\s+it|open\s+it|get\s+it\s+(?:running|working|ready))\b.*$", "", t).strip(" ?.!")
    m = re.match(rf"^(?:install|set ?up|download and install|get and install)\s+(?:the\s+)?(?:app\s+|application\s+|software\s+)?{_APP}(?:\s+(?:app|application|software))?{_ON_PC}$", t) \
        or re.match(rf"^(?:get|have)\s+(?:the\s+)?{_APP}(?:\s+(?:app|application|software))?\s+installed{_ON_PC}$", t)
    g = re.match(rf"^(?:get\s+rid\s+of|remove|delete|uninstall)\s+(?:the\s+)?{_APP}(?:\s+(?:app|application|software|program))?\s+(?:from|off)\s+(?:my|this|the)\s+"
                 rf"(?:pc|laptop|computer|system|machine)$", t)
    if g and not m:
        return _decision(request_id, t, "uninstall_software", {"name": g.group("app").strip()}, lane=RouteLane.CLARIFY,
                         clarification=f"Uninstall {g.group('app').strip()}? Say yes to confirm.")
    u = re.match(rf"^(?:update|upgrade)\s+(?:the\s+)?(?!(?:my|all|every|everything|status|notes?|to-?do|list|calendar|reminders?|profile|"
                 rf"password|contacts?|drivers?|windows|the\s+system)\b){_APP}(?:\s+(?:app|application|software|to\s+the\s+latest(?:\s+version)?))?{_ON_PC}$", t)
    if u and not m:
        return _decision(request_id, t, "update_software", {"name": u.group("app").strip()})
    c = re.match(r"^(?:do\s+i\s+have|have\s+i\s+got|did\s+i\s+install)\s+(?:the\s+)?(?!(?:a|an|any|some|enough|space|files?|folders?)\b)"
                 r"(?P<app>[a-z0-9][a-z0-9 .+#&'-]{0,40}?)"
                 r"(?:\s+(?:app|application|software))?(?:\s+installed)?\s+(?:on|in)\s+(?:this|my|the)\s+(?:pc|laptop|computer|system|machine)$", t)
    if c and not m:
        return _decision(request_id, t, "check_app_installed", {"name": c.group("app").strip()})
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
    m = re.match(rf"^(?:send|share|push|forward|copy)\s+(?:this|that|the|my)\s+(?:link|url|web\s*page\s+link|copied\s+text|clipboard(?:\s+text)?|address)"
                 rf"\s+(?:to|on)\s+(?:my\s+|the\s+)?{PHONE_WORDS}$", t)
    if m:
        return _decision(request_id, t, "localsend_text", {"text": ""})  # the tool sends what was copied
    m = re.match(rf"^(?:send|share|push|forward)\s+(?:the\s+|this\s+)?(?:link|url|text|note)\s*:?\s+(?P<x>.+?)\s+(?:to|on)\s+(?:my\s+|the\s+)?{PHONE_WORDS}$", t) \
        or re.match(rf"^(?:send|share|push|forward)\s+(?P<x>(?:https?://|www\.)\S+)\s+(?:to|on)\s+(?:my\s+|the\s+)?{PHONE_WORDS}$", t)
    if m:
        return _decision(request_id, t, "localsend_text", {"text": raw_body(raw, m.group("x"))})
    m = re.match(rf"^(?:send|share)\s+(?:the\s+|my\s+)?(?:file\s+)?(?P<path>[\w .()'&+-]{{1,60}}?\.{_DOC_EXT})\s+(?:to|onto)\s+(?:my\s+|the\s+)?{PHONE_WORDS}$", t)
    if m:
        return _decision(request_id, t, "android_push_file", {"path": raw_body(raw, m.group("path"))})
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
            return _decision(request_id, t, "brightness_set", {"percent": n})
        return _decision(request_id, t, "volume_set", {"percent": n})
    if re.match(r"^(?:it'?s\s+)?(?:way\s+|too\s+|so\s+|very\s+)+loud(?:\s+in\s+here)?$|^(?:that'?s|this is)\s+too\s+loud$", t):
        return _decision(request_id, t, "volume_down", {})
    if re.match(r"^(?:i\s+)?can'?t hear (?:anything|you|it|a thing)(?:\s+from the speakers?)?$|^(?:it'?s\s+)?too (?:quiet|soft|low)$", t):
        return _decision(request_id, t, "volume_up", {})
    if re.match(r"^(?:total |complete )?silence(?: please)?$|^(?:mute|silence) everything$|^shut (?:it|the sound) off$"
                r"|^(?:silence|mute|hush)\s+(?:my|the|this)\s+(?:computer|pc|laptop|system|speakers?|sound|audio)$", t):
        return _decision(request_id, t, "volume_mute", {})
    if re.match(r"^(?:open|launch|show|start)\s+(?:the\s+|my\s+)?(?:windows\s+)?(?:file explorer|file manager|my computer|this pc)$", t):
        return _decision(request_id, t, "open_app", {"name": "file explorer"})
    return None


_TODO_LIST = r"(?:to-?\s?do|todo|task|tasks|checklist|shopping|grocery|groceries)(?:\s+list)?"


def match_utilities(t: str, raw: str, request_id: str) -> Optional[RouteDecision]:
    """Instant offline utilities: calculator/units/dates, battery, network, timers, stopwatch, to-do list,
    personal memory, voice shortcuts, command history, passwords, recycle bin."""
    from jarvis.tools.system.everyday_tools import quick_answer, split_steps

    if not PHONE_REF.search(t) and quick_answer(raw) is not None:
        return _decision(request_id, t, "quick_answer", {"query": raw.strip()})
    # ---- voice shortcuts (before the compound check: their bodies contain several actions)
    m = re.match(r"^(?:when(?:ever)? i say|if i say)\s+[\"']?(?P<p>[^,\"']{2,60}?)[\"']?(?:\s*(?:,|then|jarvis should|you should|please)\s*|\s+(?=(?:lock|mute|unmute|open|close|turn|set|play|start|shut|launch|show|send|take|dim|pause|stop|switch|minimi[sz]e)\b))(?P<steps>.+)$", t) \
        or re.match(r"^(?:create|make|add|set up|save)\s+(?:a\s+|new\s+)?(?:shortcut|macro|routine|voice command)\s+(?:called|named)\s+[\"']?(?P<p>.+?)[\"']?\s+(?:that|to|which|for)\s+(?P<steps>.+)$", t)
    if m:
        return _decision(request_id, t, "create_shortcut", {"phrase": m.group("p").strip(), "steps": split_steps(raw_body(raw, m.group("steps")))})
    if re.match(r"^(?:list|show|what are)\s+(?:all\s+)?(?:my\s+)?(?:shortcuts|macros|routines|voice commands|custom commands)$", t):
        return _decision(request_id, t, "list_shortcuts", {})
    m = re.match(r"^(?:delete|remove|forget)\s+(?:the\s+)?(?:shortcut|macro|routine)\s+(?:called\s+|named\s+)?[\"']?(?P<p>.+?)[\"']?$", t) \
        or re.match(r"^(?:delete|remove|forget)\s+(?:the\s+|my\s+)?[\"']?(?P<p>(?!.*\bdesktop\b)[^\"']{2,40}?)[\"']?\s+(?:voice\s+)?(?:shortcut|macro|routine)$", t)
    if m:
        return _decision(request_id, t, "delete_shortcut", {"phrase": m.group("p")})
    if PHONE_REF.search(t):
        return None
    # ---- battery / network
    if re.match(r"^(?:what(?:'s| is)\s+(?:my|the)\s+|check\s+(?:my\s+|the\s+)?|show\s+(?:me\s+)?(?:my\s+|the\s+)?)?(?:laptop\s+|pc\s+)?battery(?:\s+(?:level|status|percentage|life|left|charge|health))?$", t) \
            or re.match(r"^how much (?:battery|charge|juice|power)(?: do i have(?: left)?| have i got(?: left)?| is left| left| remaining| is there)?(?: on (?:my |the )?(?:laptop|pc|computer))?$", t) \
            or re.match(r"^is (?:my |the )?(?:laptop|pc|computer|battery|it) (?:charging|plugged in|on charge)$", t) \
            or re.match(r"^is (?:my |the )?(?:charger|power (?:cable|cord|adapter)|adapter) (?:plugged in|connected|on|working)$", t):
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
    if re.match(rf"^(?:show|read|list|open|check|what(?:'s| is) on|what are)\s+(?:me\s+)?(?:my\s+|the\s+)?{_TODO_LIST}(?:\s+(?:for\s+)?(?:today|tomorrow|now|this\s+week))?$", t) \
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
    m = re.match(r"^(?:what do you (?:remember|know)|what did i tell you(?: to remember)?|what did i ask you to remember)(?:\s+about\s+(?P<q>.+))?$", t) \
        or re.match(r"^do you remember\s+(?P<q>.+)$", t) \
        or re.match(r"^where did i (?P<q>park(?:\s+(?:my|the)\s+\w+)?)$", t)
    if m:
        return _decision(request_id, t, "recall_facts", {"query": raw_body(raw, m.group("q")) if m.group("q") else ""})
    m = re.match(r"^forget\s+(?:that|about|what i (?:said|told you) about)\s+(?P<q>.+)$", t)
    if m:
        return _decision(request_id, t, "forget_fact", {"query": raw_body(raw, m.group("q"))})
    # ---- history, passwords, recycle bin
    if re.match(r"^(?:what did i (?:just )?(?:ask|say|tell)(?: you)?(?: to do)?(?: (?:earlier|before|last|recently|today|this morning|so far|yesterday))*|show (?:me )?(?:my )?(?:command |recent )?history|(?:my )?recent commands"
                r"|what (?:were|are) my (?:last|recent|previous)(?: few| \d+)? commands|(?:list|show)(?: me)? (?:the |my )?(?:last |recent )?commands(?: i (?:gave|said|asked)(?: you)?)?(?: today| earlier)?"
                r"|what (?:was|were) the last (?:thing|things|command|commands|request|few things) i (?:asked|told|said to|gave)(?: you)?(?: to do)?"
                r"|(?:list|show|tell)(?: me)? (?:the |all (?:the )?)?(?:things|stuff|commands|requests) i (?:told|asked|gave)(?: you)?(?: to do)?(?: today| earlier| so far)?"
                r"|what (?:have|did) i (?:asked|ask|told|tell|said|say)(?: to)? you(?: to do)? (?:today|so far|earlier|this morning|till now))$", t):
        return _decision(request_id, t, "command_history", {})
    m = re.match(r"^(?:generate|create|make|give me|suggest)\s+(?:me\s+)?(?:a\s+|an\s+)?(?:new\s+)?(?:strong\s+|secure\s+|random\s+|safe\s+)*password(?:\s+(?:of|with)\s+(?P<n>\d{1,2})\s*(?:characters|chars|letters)?|\s+(?P<n2>\d{1,2})\s*(?:characters|chars) long)?$", t)
    if m:
        n = int(m.group("n") or m.group("n2") or 16)
        return _decision(request_id, t, "generate_password", {"length": max(8, min(64, n))})
    if re.match(r"^(?:empty|clear|clean(?: out)?)\s+(?:the\s+|my\s+)?(?:recycle ?bin|trash|bin)$", t):
        return _decision(request_id, t, "empty_recycle_bin", {})
    return None


_BROWSER_QUICK = [
    (r"^(?:open\s+)?(?:a\s+)?(?:new\s+(?:browser\s+)?tab|(?:browser\s+)?new\s+tab)(?:\s+in\s+(?:the\s+)?browser)?(?:\s+please)?$", "new_tab"),
    (r"^close\s+(?:(?:this|the|current|that|my|active)\s+)*(?:browser\s+)?tab$", "close_tab"),
    (r"^(?:re-?open|restore|bring back|undo close)\s+(?:the\s+)?(?:last\s+)?(?:closed\s+)?tab$", "reopen_tab"),
    (r"^(?:go\s+to\s+|switch\s+to\s+)?(?:the\s+)?next\s+tab$", "next_tab"),
    (r"^(?:go\s+to\s+|switch\s+to\s+)?(?:the\s+)?(?:previous|prev|last\s+used)\s+tab$", "previous_tab"),
    (r"^go\s+back$|^(?:go\s+)?back(?:\s+(?:a|one)\s+page)?\s+in\s+(?:the\s+)?browser$|^(?:go\s+)?(?:to\s+the\s+)?previous\s+page$|^go\s+back\s+a\s+page$|^go\s+back\s+to\s+(?:the\s+)?(?:last|previous)\s+(?:page|site|website)$", "back"),
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
    (r"^(?:take\s+a\s+|do\s+a\s+)?(?:screen\s+)?(?:snip|clip)(?:\s+of\s+(?:the\s+|my\s+)?screen)?$|^snipping\s+tool$", "snip"),
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
    (r"^select\s+(?:all|everything)(?:\s+(?:the\s+)?text)?$", "select_all"),
    (r"^copy(?:\s+(?:this|that|it|the\s+text|the\s+selection|selected\s+text|selection))?$", "copy"),
    (r"^cut(?:\s+(?:this|that|it|the\s+text|the\s+selection))?$", "cut"),
    (r"^paste(?:\s+(?:it|this|that|here|the\s+text))?(?:\s+here)?$", "paste"),
    (r"^undo(?:\s+(?:that|it|the\s+last\s+(?:change|action)))?$", "undo"),
    (r"^redo(?:\s+(?:that|it))?$", "redo"),
    (r"^(?:save|save\s+(?:it|this|the\s+file))$", "save"),
    (r"^(?:take\s+a\s+|take\s+|capture\s+(?:a\s+)?)?screenshot\s+(?:and\s+)?(?:paste|put)(?:\s+it)?(?:\s+(?:here|in\s+(?:here|this|the\s+(?:chat|box|text\s*box))))?$",
     "screenshot_paste"),
    (r"^copy\s+(?:a\s+)?screenshot(?:\s+to\s+(?:the\s+)?clipboard)?$|^(?:take\s+a\s+)?screenshot\s+to\s+(?:the\s+)?clipboard$",
     "screenshot_to_clipboard"),
]


_BROWSERS = r"chrome|google chrome|edge|microsoft edge|firefox|brave|the browser|browser"
_LOGIN = re.compile(
    rf"^(?:(?:open|launch|start)\s+(?P<b1>{_BROWSERS})\s+(?:and|&|then)\s+)?(?:please\s+)?(?:log\s*into|sign\s*into|log\s*in|sign\s*in|login|signin)"
    rf"\s+(?:to\s+|into\s+|in\s+to\s+|on\s+|at\s+)?(?:my\s+)?(?P<site>[a-z0-9][a-z0-9. ]{{0,24}}?)(?:\s+(?:account|site|website|page))?"
    rf"(?:\s+(?:in|on|using|with|via)\s+(?P<b2>{_BROWSERS}))?$")


_DICTATION_START = re.compile(
    r"^(?:(?:start|begin|turn on|enable|activate|switch on)\s+)?(?:voice typing|voice type|dictation|dictating|live typing|"
    r"typing mode|speech to text|talk to type)(?:\s+(?:in|into|on)\s+(?P<a1>.+))?$"
    r"|^type\s+(?:what|whatever|everything|all that|what ever)\s+i\s+(?:say|speak|tell)(?:\s+(?:in|into|on)\s+(?P<a2>.+))?$"
    r"|^(?:dictate|voice type)(?:\s+(?:in|into|on)\s+(?P<a3>.+))?$"
    r"|^start\s+(?:typing|dictating|writing)\s+(?:in|into|on)\s+(?P<a4>.+)$")


def match_voice_and_screen(t: str, raw: str, request_id: str) -> Optional[RouteDecision]:
    """JARVIS's own voice, the microphone, and questions about what is on the PC screen."""
    m = re.search(r"\b(?P<g>female|woman|girl|lady|male|man|boy|guy)\b", t)
    if m and re.search(r"\bvoice\b|\b(?:the|a)\s+(?:female|male)\s+one\b", t) and \
            re.search(r"\b(?:change|switch|use|set|want|give|prefer|try|make|speak|talk|sound)\b", t) and not re.search(rf"\b{PHONE_WORDS}\b", t):
        gender = "female" if m.group("g") in ("female", "woman", "girl", "lady") else "male"
        return _decision(request_id, t, "set_voice", {"gender": gender})
    if re.fullmatch(r"(?:(?:can|do)\s+you\s+)?hear\s+me(?:\s+(?:properly|clearly|now|well|ok|okay))?|are\s+you\s+(?:hearing|listening\s+to)\s+me"
                    r"|is\s+(?:my\s+|the\s+)?(?:mic|microphone)\s+(?:on|working|muted)(?:\s+properly)?", t):
        return _decision(request_id, t, "microphone_status", {})
    if re.fullmatch(r"what\s+does\s+(?:this|the|that)\s+(?:popup|pop-up|pop\s+up|dialog|dialogue|message|window|box|notification|error|warning|alert)\s+say"
                    r"|(?:(?:can|could)\s+you\s+)?see\s+my\s+(?:screen|display|monitor)"
                    r"|what\s+am\s+i\s+(?:looking\s+at|seeing)(?:\s+(?:right\s+)?now)?"
                    r"|(?:summari[sz]e|read(?:\s+out)?|explain)\s+(?:what(?:'s|\s+is)\s+on\s+my\s+screen|my\s+screen|the\s+screen)"
                    r"|what(?:'s|\s+is)\s+(?:this|that)\s+(?:error|popup|pop-up|warning|message)(?:\s+(?:on\s+(?:my|the)\s+screen|here))?"
                    r"|what\s+does\s+(?:this|that)\s+(?:error|popup|pop-up|warning|message|dialog)(?:\s+(?:on\s+(?:my|the)\s+screen|here))?\s+mean"
                    r"|what(?:'s|\s+is|\s+does)\s+(?:this|that|the)\s+(?:popup|pop-up|pop\s+up|dialog|dialogue|window|box|notification|error|warning|alert|screen)\s+(?:saying|say|telling\s+me)"
                    r"|what(?:'s|\s+is)\s+(?:written|showing|displayed)\s+on\s+(?:my|the)\s+(?:screen|display|monitor)"
                    r"|(?:tell\s+me\s+)?what\s+(?:do\s+)?you\s+see\s+on\s+(?:my|the)\s+screen|read\s+what(?:'s|\s+is)\s+on\s+(?:my|the)\s+screen"
                    r"|what(?:'s|\s+is)\s+(?:this|that)\s+(?:thing|stuff|window|icon|box|sign|symbol)\s+on\s+(?:my|the)\s+screen", t):
        return _decision(request_id, t, "describe_screen", {"device": "pc", "question": raw})
    m = re.fullmatch(r"(?:find|locate|look\s+for|search\s+for)\s+(?P<target>.+?)\s+(?:on\s+(?:the|my)\s+screen\s+)?and\s+(?:then\s+)?"
                     r"(?P<how>double[- ]click|right[- ]click|click|tap|press|select)\s+(?:on\s+)?(?:it|that)", t)
    if m:
        how = m.group("how").replace(" ", "-")
        return _decision(request_id, t, "screen_click", {"target": raw_body(raw, m.group("target")),
                                                        "button": "right" if how == "right-click" else "left", "double": how == "double-click"})
    return None


def match_dictation(t: str, request_id: str) -> Optional[RouteDecision]:
    """'start voice typing', 'type what I say in claude', 'dictate into notepad' -> live dictation into that box."""
    m = re.fullmatch(r"(?P<a>start|begin|turn\s+on|enable|switch\s+on|activate|enter|stop|end|turn\s+off|disable|switch\s+off|deactivate|exit|quit|"
                     r"leave|pause|finish)\s+(?:the\s+|voice\s+)?(?:dictation|voice\s+typing|typing\s+mode)(?:\s+mode)?(?:\s+now)?", t)
    if m:
        on = m.group("a").split()[0] in ("start", "begin", "enable", "activate", "enter") or m.group("a").endswith("on")
        return _decision(request_id, t, "dictation_mode_control", {"action": "start" if on else "stop"})
    m = _DICTATION_START.match(t)
    if not m:
        return None
    app = next((g for g in (m.group("a1"), m.group("a2"), m.group("a3"), m.group("a4")) if g), "")
    app = re.sub(r"^(?:the|my)\s+|\s+(?:text\s*box|box|chat|window|tab|app)$", "", app.strip())
    return _decision(request_id, t, "dictation_mode_control", {"action": "start", **({"target_app": app} if app else {})})


def match_person(t: str, request_id: str) -> Optional[RouteDecision]:
    """'who is yoga' -> the owner's contact, only when that name is really in their contacts or chats."""
    m = re.match(r"^(?:who\s+is|who's|whos|tell\s+me\s+about|do\s+you\s+know|what\s+do\s+you\s+know\s+about)\s+"
                 r"(?:my\s+(?:contact|friend)\s+)?(?P<n>[a-z][a-z .'-]{1,40}?)$", t)
    if not m or m.group("n").split()[0] in ("the", "a", "an", "this", "that", "my", "your", "he", "she", "it", "you", "i"):
        return None
    try:
        from jarvis.integrations.whatsapp.people import known_person
        if not known_person(m.group("n")):
            return None
    except Exception:
        return None
    return _decision(request_id, t, "contact_info", {"name": m.group("n").strip()})


def match_login(t: str, request_id: str) -> Optional[RouteDecision]:
    """'open chrome and login linkedin', 'login linkedin in chrome' -> the site's sign-in page in that browser."""
    m = _LOGIN.match(t)
    if not m or m.group("site").strip() in ("", "it", "there", "here", "again", "now", "the browser"):
        return None
    from jarvis.tools.system.assistant_tools import login_url
    site = m.group("site").strip()
    browser = (m.group("b1") or m.group("b2") or "").replace("google ", "").replace("microsoft ", "")
    browser = "" if browser in ("browser", "the browser") else browser
    slots = {"url": login_url(site), "title": f"{site.title()} sign-in page", **({"browser": browser} if browser else {})}
    return _decision(request_id, t, "open_website", slots)


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
    if re.match(r"^(?:auto\s*-?\s*fill|fill(?:\s+(?:in|out|up))?)\s+(?:this|the|that)?\s*(?:form|page|details|fields|application)"
                r"(?:\s+(?:with|using)\s+my\s+(?:details|info|information|data|profile))?(?:\s+for\s+me)?$"
                r"|^fill\s+(?:in\s+)?my\s+(?:details|info|information)(?:\s+(?:in|on)\s+(?:this|the)\s+(?:form|page))?$", t):
        return _decision(request_id, t, "browser_autofill", {})
    for pattern, action in _BROWSER_QUICK:
        if re.match(pattern, t):
            return _decision(request_id, t, "browser_quick_action", {"action": action})
    m = re.match(r"^(?:copy|cut)\s+(?:the\s+|this\s+|that\s+|selected\s+)?(?:text|selection|it)?\s*(?:and|&|then)\s+paste\s+"
                 r"(?:it\s+)?(?:in|into|to|on)\s+(?:the\s+|my\s+)?(?P<app>[a-z0-9 .+-]{2,30})$", t)
    if m:
        return _decision(request_id, t, "pc_quick_action", {"action": "copy_paste_to_app", "app": m.group("app").strip()})
    m = re.match(r"^(?:take\s+a\s+|take\s+|capture\s+(?:a\s+)?)?screenshot\s+(?:and\s+|then\s+|and\s+then\s+)?(?:paste|put|send)"
                 r"(?:\s+it)?\s+(?:in|into|to|on)\s+(?:the\s+|my\s+)?(?P<app>[a-z0-9 .+-]{2,30})$", t)
    if m and not re.fullmatch(r"(?:here|this|it|chat|box|text\s*box|this\s+(?:chat|box))", m.group("app").strip()):
        return _decision(request_id, t, "pc_quick_action", {"action": "screenshot_paste", "app": m.group("app").strip()})
    m = re.match(r"^paste\s+(?:it\s+|this\s+|that\s+)?(?:in|into|to|on)\s+(?:the\s+|my\s+)?(?P<app>[a-z0-9 .+-]{2,30})$", t)
    if m and not re.fullmatch(r"(?:here|this|it|chat|box|text\s*box|this\s+(?:chat|box))", m.group("app").strip()):
        return _decision(request_id, t, "pc_quick_action", {"action": "paste_to_app", "app": m.group("app").strip()})
    for pattern, action in _PC_QUICK:
        if re.match(pattern, t):
            return _decision(request_id, t, "pc_quick_action", {"action": action})
    return None


_MAIL = r"(?:e-?mails?|mails?|gmail|inbox)"
_DAYS = r"(?:today|tonight|tomorrow|day after tomorrow|this week|next week|this weekend|weekend|monday|tuesday|wednesday|thursday|friday|saturday|sunday)"


def match_google(t: str, raw: str, request_id: str) -> Optional[RouteDecision]:
    """Gmail and Google Calendar in everyday words: reading mail, drafting mail, reading and adding calendar events."""
    # --- reading mail
    if re.fullmatch(rf"(?:check|read|show|see|get)\s+(?:me\s+)?(?:my\s+|the\s+)?(?:new\s+|latest\s+|unread\s+|recent\s+)*{_MAIL}(?:\s+(?:today|now))?"
                    rf"|open\s+(?:my\s+)?(?:new\s+|latest\s+|unread\s+)+{_MAIL}"
                    rf"|(?:do i have|did i get|have i got|got|are there|is there)\s+(?:any\s+)?(?:new\s+|unread\s+)?{_MAIL}(?:\s+from\s+.+)?(?:\s+today)?"
                    rf"|any\s+(?:new\s+|unread\s+)?{_MAIL}(?:\s+from\s+.+)?"
                    rf"|(?:did|has)\s+[a-z .'-]{{1,30}}\s+(?:e-?mail(?:ed)?|mail(?:ed)?|sent\s+(?:me\s+)?(?:an?\s+)?(?:e-?mail|mail))(?:\s+me)?"
                    rf"|what(?:'s| is)?\s+new\s+in\s+my\s+{_MAIL}|anything\s+(?:new|important|urgent)\s+in\s+my\s+{_MAIL}(?:\s+today)?"
                    rf"|(?:latest|recent|unread|new)\s+{_MAIL}", t):
        slots = {"unread_only": True} if re.search(r"\b(?:new|unread|any)\b", t) else {}
        who = re.search(r"\bfrom\s+(?P<w>[a-z0-9 .@'-]{1,40}?)(?:\s+today)?$", t) or \
            re.match(r"^(?:did|has)\s+(?P<w>[a-z .'-]{1,30}?)\s+(?:e-?mail|mail|sent)", t)
        if who:
            slots["sender"] = raw_body(raw, who.group("w").strip())
        return _decision(request_id, t, "gmail_list_recent", slots)
    # --- drafting mail (address and body are confirmed before anything is sent)
    m = re.fullmatch(rf"(?:draft|write|compose|prepare|send)\s+(?:an?\s+)?(?:e-?mail|mail)\s+to\s+(?P<to>[a-z0-9 .@'-]{{1,40}}?)"
                     rf"(?:\s+(?:about|regarding|saying|asking(?:\s+for)?|that|to say)\s+(?P<about>.+))?", t) \
        or re.fullmatch(rf"e-?mail\s+(?P<to>[a-z0-9 .@'-]{{1,30}}?)\s+(?P<about>the\s+.+|about\s+.+|saying\s+.+)", t)
    if m:
        about = (m.group("about") or "").strip()
        slots = {"to_name": raw_body(raw, m.group("to").strip())}
        if about:
            slots["subject"] = raw_body(raw, re.sub(r"^(?:about|saying|regarding)\s+", "", about))
        return _decision(request_id, t, "gmail_create_draft", slots, lane=RouteLane.CLARIFY,
                         clarification=f"I'll draft that email to {slots['to_name']}. What's their email address, "
                                       "and anything else to include?")
    # --- reading the calendar
    m = re.fullmatch(rf"(?:what(?:'s| is)|show(?:\s+me)?|check|read|tell me)\s+(?:on\s+)?(?:my\s+)?(?:calendar|schedule|agenda|plan)"
                     rf"(?:\s+(?:for|on))?(?:\s+(?P<w1>{_DAYS}))?"
                     rf"|(?:what(?:'s| is)\s+on\s+my\s+(?:calendar|schedule|agenda))(?:\s+(?:for|on))?(?:\s+(?P<w2>{_DAYS}))?"
                     rf"|(?:do i have|have i got|are there)\s+(?:any\s+)?(?:meetings?|events?|appointments?|calls?|classes)(?:\s+(?:on|for))?(?:\s+(?P<w3>{_DAYS}))?"
                     rf"|what\s+(?:meetings?|events?|appointments?)\s+(?:do i have|are there|have i got)(?:\s+(?:on|for))?(?:\s+(?P<w4>{_DAYS}))?"
                     rf"|what(?:'s| is)\s+my\s+(?:next|first|last)\s+(?:meeting|event|appointment|call|class)"
                     rf"|(?:am i|is my)\s+(?:free|busy|available)\s+(?:on\s+)?(?P<w5>{_DAYS}(?:\s+(?:morning|afternoon|evening|night))?)(?:\s+(?:free|busy))?"
                     rf"|is\s+my\s+(?P<w6>{_DAYS})\s+(?:morning|afternoon|evening)\s+free"
                     rf"|(?:my\s+)?(?:schedule|agenda|meetings)\s+(?:for\s+)?(?P<w7>{_DAYS})"
                     rf"|(?:do\s+i\s+have|have\s+i\s+got|is\s+there)\s+(?:anything|something|stuff)\s+(?:booked|scheduled|planned|on|lined\s+up)"
                     rf"(?:\s+(?:on|for))?\s+(?P<w8>{_DAYS}(?:\s+(?:morning|afternoon|evening|night))?)"
                     rf"|what(?:'s|\s+is)\s+my\s+(?:schedule|agenda|plan)\s+(?:for|on)\s+(?P<w9>{_DAYS})", t)
    if m:
        window = next((g for g in m.groups() if g), "today")
        return _decision(request_id, t, "calendar_list_events", {"time_window": window})
    # --- adding to the calendar (the exact date/time is confirmed before it is created)
    m = re.fullmatch(r"(?:schedule|book|arrange|set\s+up|add|create|put|block|plan)\s+(?:an?\s+|the\s+)?(?P<what>.+?)"
                     r"(?:\s+(?:on|to|in)\s+my\s+calendar)?\s+(?P<when>(?:on\s+|at\s+|for\s+|this\s+|next\s+|tomorrow|today|tonight)"
                     rf".*?(?:\d|{_DAYS}|morning|afternoon|evening|noon).*)", t)
    if m and re.search(r"\b(?:meeting|call|appointment|event|lunch|dinner|interview|review|session|class|hours?|minutes?|"
                       r"calendar|reminder|sync|standup|catch\s*up)\b", m.group("what") + " " + t):
        what = re.sub(r"\s+(?:on|to|in)\s+my\s+calendar$", "", m.group("what")).strip()
        what = re.sub(r"^(?:on\s+|to\s+)?my\s+calendar\s+", "", what)
        from jarvis.tools.system.google_tools import parse_when
        slots = {"summary": raw_body(raw, what), "when": m.group("when")}
        if parse_when(m.group("when")):  # a day and a time: the tool itself asks before creating it
            return _decision(request_id, t, "calendar_create_event", slots)
        return _decision(request_id, t, "calendar_create_event", slots, lane=RouteLane.CLARIFY,
                         clarification=f"What time should '{what}' be {m.group('when')}?")
    return None


_DEVICE = r"(?:pc|computer|laptop|system|machine|desktop|windows)"
_FOLDERS = {"downloads": "downloads", "download": "downloads", "documents": "documents", "docs": "documents",
            "desktop": "desktop", "pictures": "pictures", "photos": "pictures", "videos": "videos", "music": "music"}
_SETTINGS = {"sound": "sound", "audio": "sound", "display": "display", "screen": "display", "bluetooth": "bluetooth",
             "wifi": "wifi", "wi-fi": "wifi", "network": "network", "internet": "network", "apps": "apps",
             "app": "apps", "windows": "settings", "system": "settings", "device manager": "device_manager"}


_KNOWLEDGE_Q = re.compile(
    r"^(?:what|how)\s+(?:does|do)\s+(?!(?:this|that)\s+(?:error|popup|pop-up|message|warning|dialog)\b).+\s+(?:mean|stand\s+for|work)$"
    r"|^what(?:'s|\s+is|\s+are)\s+(?:the\s+)?(?:meaning|definition|difference|purpose|use)\s+(?:of|between)\b"
    r"|^what\s+(?:is|are)\s+.+\s+(?:used\s+for|good\s+for)$"
    r"|^(?:should|shall|must)\s+i\b"
    r"|^(?:is|are)\s+.+\s+(?:better|worse|faster|safer)\s+than\b"
    r"|^(?:how\s+(?:do|can|should|would)\s+i|how\s+to)\s+(?!.*\b(?:phone|whatsapp)\b)"
    r"|^why\s+(?:is|are|does|do|did|can't|won't|isn't)\b"
    r"|^(?:explain|define)\s+(?!(?:this|the|my)\s+(?:error|screen|popup|message))"
    r"|^(?:what(?:'s|\s+is)\s+)?(?:the\s+)?difference\s+between\b"
    r"|^i\s+(?:was|am|'m)\s+(?:just\s+|really\s+)?(?:wondering|curious)\b|^i\s+wonder\s+(?:how|why|what|if|whether)\b"
    r"|^what\s+(?:does|do)\s+.+?\s+(?:actually\s+|exactly\s+|really\s+)?do(?:\s+exactly)?$|^what\s+(?:is|are)\s+.+?\s+(?:actually\s+)?(?:used\s+)?for$"
    r"|^what\s+do\s+you\s+(?:think|feel)\s+(?:about|of)\b|^(?:do\s+you\s+think|in\s+your\s+opinion|what'?s\s+your\s+(?:opinion|view|take)\s+on)\b"
    r"|^how\s+does\s+.+\s+compare\s+(?:to|with)\b|^(?:is|are)\s+(?!my\b|i\b|it\b)[^?]+?\s+(?:a\s+)?(?:good|bad|safe|worth\s+it|reliable|free\s+to\s+use)\b"
    r"|^(?:is|would)\s+it\s+(?:be\s+)?(?:better|worse|safer|safe|smarter|ok|okay|fine|good|bad|healthy|wise|possible|necessary|normal|risky|"
    r"dangerous|required|legal|worth\s+it|a\s+good\s+idea|a\s+bad\s+idea)\s+(?:to|if)\b")


def match_knowledge_question(t: str, request_id: str) -> Optional[RouteDecision]:
    """'what does mute mean', 'should I close edge to save battery', 'how do I open chrome': questions about a thing
    are answered, never turned into doing the thing."""
    if _KNOWLEDGE_Q.search(t):
        return _decision(request_id, t, None, {}, lane=RouteLane.LANE_2, reason=ReasonCode.QUESTION_NOT_COMMAND)
    return None


def match_system(t: str, request_id: str) -> Optional[RouteDecision]:
    """Everyday PC control in many wordings: power, volume, brightness, folders, settings, specs, memory, screenshots."""
    if re.search(rf"\b{PHONE_WORDS}\b", t):
        return None  # "lock my phone", "volume up on my phone": the phone matchers
    t = re.sub(r"^(?:(?:can|could|would|will)\s+(?:you|u)\s+(?:please\s+|pls\s+|plz\s+|just\s+)?|(?:please|pls|plz|kindly|just)\s+"
               r"|(?:i'?d\s+like|i\s+want|i\s+need)\s+(?=the\s+(?:volume|sound|brightness)))+", "", t).strip()
    d = lambda intent, slots=None: _decision(request_id, t, intent, slots or {})  # noqa: E731
    # ---- power (shutdown / restart still ask for confirmation before anything happens)
    if re.fullmatch(rf"(?:shut\s*down|shutdown|turn\s+off|power\s+off|switch\s+off|power\s+down)(?:\s+(?:the|my|this))?\s+{_DEVICE}(?:\s+now)?"
                    rf"|shut\s*down|shutdown(?:\s+now)?|(?:shut|power|switch|turn)\s+(?:the\s+|my\s+|this\s+)?{_DEVICE}\s+(?:down|off)(?:\s+now)?", t):
        return d("system_power_control", {"action": "shutdown"})
    if re.fullmatch(rf"(?:restart|reboot)(?:\s+(?:the|my|this))?(?:\s+{_DEVICE})?(?:\s+now)?", t):
        return d("system_power_control", {"action": "restart"})
    if re.fullmatch(rf"(?:put|send)\s+(?:the\s+|my\s+|this\s+)?{_DEVICE}\s+(?:to\s+)?sleep|(?:sleep|hibernate|suspend)(?:\s+(?:the|my|this))?(?:\s+{_DEVICE})?(?:\s+now)?"
                    rf"|go\s+to\s+sleep\s+{_DEVICE}", t):
        return d("system_power_control", {"action": "sleep"})
    if re.fullmatch(rf"lock(?:\s+(?:the|my|this))?(?:\s+{_DEVICE}|\s+screen)?(?:\s+now)?|lock\s+it(?:\s+up)?(?:\s*,?.*leaving.*)?", t):
        return d("system_power_control", {"action": "lock"})  # the executable lock (there is no separate lock tool)
    # ---- volume
    m = re.fullmatch(r"(?:(?:set|make|put|turn|change|adjust|bring|keep|lower|raise|reduce|increase|decrease|drop|boost)\s+)?(?:the\s+|my\s+)?(?:speaker\s+|system\s+|master\s+|pc\s+)?"
                     r"(?:volume|sound|audio)(?:\s+level)?\s+(?:to\s+|too\s+|at\s+|on\s+|as\s+)?(?:like\s+|about\s+|around\s+|exactly\s+)?"
                     r"(\d{1,3})\s*(?:%|percent|per\s*cent)?", t)
    if m and int(m.group(1)) <= 100:
        return d("volume_set", {"percent": int(m.group(1))})
    _snd = r"(?:the\s+)?(?:volume|sound|audio|music|speakers?)"
    if re.fullmatch(rf"(?:turn|switch|shut)\s+off\s+{_snd}(?:\s+(?:completely|fully|entirely|totally))?|(?:turn|switch|shut)\s+{_snd}\s+off(?:\s+completely)?"
                    rf"|kill\s+{_snd}|no\s+(?:more\s+)?sound(?:\s+please)?", t):
        return d("volume_mute")
    if re.fullmatch(rf"(?:make|set|get|turn)\s+{_snd}\s+(?:a\s+(?:bit|little|tad)\s+|slightly\s+|much\s+)?(?:lower|quieter|softer|down)", t):
        return d("volume_down")
    if re.fullmatch(rf"(?:make|set|get|turn)\s+{_snd}\s+(?:a\s+(?:bit|little|tad)\s+|slightly\s+|much\s+)?(?:louder|higher|up)", t) \
            or re.fullmatch(rf"(?:crank|jack|pump|bump|turn)\s+(?:up\s+{_snd}|{_snd}\s+up|it\s+up)(?:\s+a\s+(?:bit|little|notch|tad))?", t) \
            or re.fullmatch(rf"(?:yo\s+|hey\s+)?turn\s+it\s+up(?:\s+a\s+(?:bit|little|notch|tad))?", t) \
            or re.search(rf"\b(?:sound|volume|audio|music)(?:'s|\s+is)\s+(?:too|very|so|really)\s+(?:low|quiet|soft)\b", t):
        return d("volume_up")
    if re.search(r"\b(?:too\s+loud|so\s+loud|way\s+too\s+loud|quieter|softer)\b", t) or \
            re.fullmatch(r"(?:lower|reduce|decrease|drop|lessen|turn\s+down|bring\s+down)\s+(?:the\s+)?(?:volume|sound|audio|it)(?:\s+a\s+(?:bit|little))?", t) \
            or re.fullmatch(r"(?:turn|bring)\s+(?:the\s+)?(?:volume|sound|audio|it)\s+down(?:\s+a\s+(?:bit|little|notch))?", t):
        return d("volume_down")
    if re.search(r"\b(?:can'?t\s+hear|barely\s+hear|can\s+barely\s+hear|louder)\b", t) or \
            re.fullmatch(r"(?:raise|increase|boost|pump\s+up|bump\s+up|turn\s+up)\s+(?:the\s+)?(?:volume|sound|audio|it)(?:\s+a\s+(?:bit|little|notch))?", t) \
            or re.fullmatch(r"(?:turn|bump|pump|crank)\s+(?:the\s+)?(?:volume|sound|audio|it)\s+up(?:\s+a\s+(?:bit|little|notch))?", t) \
            or re.search(r",?\s*turn\s+it\s+up$", t):
        return d("volume_up")
    # ---- brightness
    m = re.fullmatch(r"(?:(?:set|make|put|turn|change|adjust|lower|raise|reduce|increase|decrease|drop|bring|dim|boost)\s+)?(?:the\s+|my\s+)?(?:screen\s+|display\s+)?"
                     r"brightness\s+(?:(?:down|up)\s+)?(?:to\s+|at\s+)?(\d{1,3})\s*(?:%|percent)?", t) \
        or re.fullmatch(r"(?:dim|brighten|darken)\s+(?:the\s+|my\s+)?(?:screen|display|monitor)\s+(?:to|at)\s+(\d{1,3})\s*(?:%|percent)?", t)
    if m and int(m.group(1)) <= 100:
        return d("brightness_set", {"percent": int(m.group(1))})
    _scr = r"(?:the\s+|my\s+)?(?:screen|display|monitor)(?:\s+brightness)?|(?:the\s+)?brightness"
    if re.fullmatch(rf"(?:make|turn|set)\s+(?:{_scr})\s+(?:a\s+(?:bit|little|tad)\s+|slightly\s+|much\s+)?(?:brighter|lighter)|brighten(?:\s+(?:up\s+)?(?:{_scr}))?(?:\s+(?:a\s+bit|a\s+little))?"
                    rf"|(?:increase|raise|boost|turn\s+up)\s+(?:{_scr})(?:\s+a\s+(?:bit|little))?|turn\s+(?:{_scr})\s+up|(?:it'?s|the\s+screen\s+is)\s+too\s+dark", t):
        return d("brightness_set", {"step": 20})
    if re.fullmatch(rf"(?:make|turn|set)\s+(?:{_scr})\s+(?:a\s+(?:bit|little|tad)\s+|slightly\s+|much\s+)?(?:dimmer|darker|less\s+bright)|(?:dim|darken)(?:\s+(?:{_scr}))?(?:\s+(?:a\s+bit|a\s+little))?"
                    rf"|(?:decrease|lower|reduce|turn\s+down)\s+(?:{_scr})(?:\s+a\s+(?:bit|little))?|turn\s+(?:{_scr})\s+down|(?:it'?s|the\s+screen\s+is)\s+too\s+bright", t):
        return d("brightness_set", {"step": -20})
    # ---- known folders ("open my downloads folder"; a bare "open music" may mean an app, so it stays ambiguous)
    m = re.fullmatch(r"(?:open|go\s+to|take\s+me\s+to|browse)\s+(?:my\s+|the\s+)?(?P<f>downloads?|documents|docs|desktop|pictures|photos|videos|music)"
                     r"(?P<folder>\s+folder)?", t)
    if m and (m.group("folder") or " my " in f" {t} " or m.group("f") not in ("music", "photos", "desktop")):
        return d("open_known_folder", {"folder": _FOLDERS[m.group("f")]})
    # ---- settings pages
    m = re.fullmatch(r"(?:open|show(?:\s+me)?|go\s+to|take\s+me\s+to|launch)\s+(?:the\s+)?(?:windows\s+)?(?P<p>sound|audio|display|screen|bluetooth|wi-?fi|network|internet|apps?|system|device\s+manager)\s+settings"
                     r"|(?P<p2>device\s+manager)", t)
    if m:
        page = (m.group("p") or m.group("p2") or "").replace("wi-fi", "wifi")
        return d("open_system_settings", {"page": _SETTINGS.get(page, page)})
    # ---- specs / memory
    if re.fullmatch(r"how\s+much\s+(?:ram|memory|storage)\s+(?:does|do|is\s+in)\s+(?:this|my|the)\s+(?:pc|computer|laptop|system|machine)(?:\s+have)?"
                    r"|what\s+(?:processor|cpu|gpu|graphics\s+card|ram)\s+(?:do\s+i\s+have|does\s+(?:this|my)\s+(?:pc|laptop|computer)\s+have|is\s+(?:this|in\s+my\s+pc))"
                    r"|(?:(?:what\s+are|what're|show(?:\s+me)?|tell\s+me|check|list)\s+)?(?:my\s+|the\s+|this\s+)?(?:pc|computer|laptop|system|machine)(?:'s)?\s+(?:specs|specifications|configuration|config|details|hardware)"
                    r"|what\s+(?:are\s+)?(?:the\s+)?(?:specs|specifications)\s+(?:of|on|for)\s+(?:my|this|the)\s+(?:pc|computer|laptop|system|machine)", t):
        return d("system_info")
    if re.fullmatch(r"what(?:'s|\s+is)\s+(?:eating|using|hogging|taking(?:\s+up)?|consuming)\s+(?:up\s+)?(?:all\s+)?(?:my\s+|the\s+)?(?:ram|memory)"
                    r"|which\s+(?:apps?|programs?|processes?)\s+(?:are\s+)?(?:using|eating|hogging|taking)\s+(?:the\s+)?most\s+(?:ram|memory)", t):
        return d("top_memory_processes")
    # ---- screenshot / window
    if re.fullmatch(r"(?:grab|snap|capture|take|get|make)\s+(?:a\s+|the\s+|my\s+)?(?:screen\s*shot|screen\s*grab|screen|snapshot)(?:\s+(?:now|please))?", t) \
            or re.fullmatch(r"(?:save|take|grab|capture|snap|keep)\s+(?:a\s+|an\s+)?(?:picture|pic|image|photo|snapshot|copy|capture)\s+of\s+"
                            r"(?:what(?:'s|\s+is)\s+on\s+)?(?:my|the|this)\s+(?:screen|display|monitor)(?:\s+(?:now|right\s+now))?", t):
        return d("take_screenshot")
    if re.fullmatch(r"minimi[sz]e\s+(?:everything|all(?:\s+(?:the\s+)?(?:windows|apps))?|every\s+window)|hide\s+(?:all\s+)?(?:the\s+)?windows", t):
        return d("show_desktop")
    m = re.fullmatch(r"snap\s+(?:this\s+|the\s+|my\s+)?(?:window\s+|it\s+)?(?:to\s+)?(?:the\s+)?(left|right|top|bottom)(?:\s+side)?", t)
    if m:
        return d("snap_window", {"direction": m.group(1)})
    m = re.fullmatch(r"shut\s+(?:the\s+|my\s+)?(?P<app>[a-z0-9 .+-]{2,30}?)\s+down(?:\s+(?:now|please))?"
                     r"|(?:the\s+)?(?P<app2>[a-z0-9 .+-]{2,30}?)\s+(?:needs|has|ought)\s+to\s+(?:be\s+)?(?:closed|close|shut|go|stop)"
                     r"|(?:the\s+)?(?P<app3>[a-z0-9 .+-]{2,30}?)\s+should\s+be\s+closed", t)
    if m:
        app = (m.group("app") or m.group("app2") or m.group("app3")).strip()
        if re.fullmatch(r"(?:(?:the|this|current|active|that)\s+)*window", app):
            return d("close_window")
        if not re.fullmatch(rf"(?:{_DEVICE}|it|this|that|everything|all|windows?)", app):
            return d("close_app", {"name": app})
    m = re.fullmatch(r"get\s+(?P<app>[a-z0-9 .+-]{2,30}?)\s+off\s+(?:my|the)\s+screen(?:\s*,?\s*close\s+it)?", t)
    if m:
        return d("close_app", {"name": m.group("app").strip()})
    return None


_DOC_NOUN = re.compile(r"\b(?:bill|card|letter|proposal|record|receipt|report|certificate|statement|agreement|slip|ticket|form|"
                       r"licen[cs]e|passport|resume|cv|invoice|contract|scan|document|file|notes?|assignment|thesis|marksheet|"
                       r"transcript|id|aadhaar|pan|visa|policy|warranty|offer)\b")
_FILE = r"(?P<file>[\w .()'&-]{1,60}?\.[a-z0-9]{2,5})"
# document / media extensions only: "open google.com" is a website, "open setup.exe" a program
_DOC_EXT = (r"(?:pdf|docx?|xlsx?|pptx?|odt|ods|txt|rtf|csv|md|json|xml|log|png|jpe?g|gif|bmp|webp|svg|heic|mp3|wav|m4a|flac|"
            r"mp4|mkv|avi|mov|webm|zip|rar|7z|py|ipynb|java|cpp|c|js|ts|html?|css)")


def match_files(t: str, raw: str, request_id: str) -> Optional[RouteDecision]:
    """File requests in everyday words: copy/move X to Y, how big is X, dig up / look for my X, recent files."""
    if re.search(rf"\b{PHONE_WORDS}\b", t):
        return None  # "copy report.pdf to my phone": a phone transfer
    d = lambda intent, slots=None: _decision(request_id, t, intent, slots or {})  # noqa: E731
    m = re.fullmatch(rf"(?P<verb>copy|move|shift|transfer|put|drag|duplicate)\s+(?:the\s+file\s+)?{_FILE}\s+(?:over\s+|across\s+|back\s+)?(?:to|into|in|onto)\s+(?:the\s+|my\s+)?(?P<dst>[\w .:/\\-]{{2,60}}?)(?:\s+folder)?", t)
    if m:
        dst = m.group("dst").strip()
        return d("copy_file" if m.group("verb") in ("copy", "duplicate") else "move_file", {"source": raw_body(raw, m.group("file")),
                                             "destination": _FOLDERS.get(dst, raw_body(raw, dst)).title() if dst in _FOLDERS else raw_body(raw, dst)})
    m = re.fullmatch(r"(?:delete|remove)\s+(?:the\s+|my\s+|a\s+)?(?:desktop\s+)?shortcut(?:\s+(?:on|from)\s+(?:the\s+|my\s+)?desktop)?"
                     r"(?:\s+(?:for|of|to)\s+(?P<app>.+))?|(?:delete|remove)\s+(?:the\s+|my\s+)?(?P<app2>\w+)\s+desktop\s+shortcut", t)
    if m and "desktop" in t:  # never "the Desktop folder": ask which shortcut file
        app = re.sub(r"\s+(?:on|from)\s+(?:the\s+|my\s+)?desktop$", "", m.group("app") or m.group("app2") or "") or None
        return _decision(request_id, t, "delete_file", {"path": f"{app} shortcut"} if app else {}, lane=RouteLane.CLARIFY,
                         reason=ReasonCode.LOW_CONFIDENCE,
                         clarification=f"Delete the {app} shortcut file on your Desktop? Say yes to confirm." if app
                         else "Which shortcut on your Desktop should I delete?")
    m = re.fullmatch(r"(?:open|view|show(?:\s+me)?|display|pull\s+up|bring\s+up)\s+(?:the\s+|my\s+|that\s+)?(?:file\s+)?"
                     rf"(?P<path>[\w .()'&-]{{1,60}}?\.{_DOC_EXT})(?:\s+(?:in|with|using)\s+[a-z ]{{2,20}})?", t)
    if m:
        return d("open_file", {"path": raw_body(raw, m.group("path"))})
    m = re.fullmatch(rf"(?:rename|change\s+the\s+name\s+of)\s+(?:the\s+file\s+)?{_FILE}\s+(?:to|as|into)\s+(?P<new>[\w .()'&-]{{1,80}})", t) \
        or re.fullmatch(rf"(?:change|update)\s+{_FILE}(?:'s|\s+file's)\s+name\s+(?:to|as)\s+(?P<new>[\w .()'&-]{{1,80}})", t)
    c = re.fullmatch(rf"(?:make|create)\s+(?:a\s+)?(?:copy|duplicate|backup)\s+of\s+{_FILE}\s+(?:on|in|to|into)\s+(?:the\s+|my\s+)?(?P<dst>[\w .:/\\-]{{2,60}}?)(?:\s+folder)?", t)
    if c and not m:
        dst = c.group("dst").strip()
        return d("copy_file", {"source": raw_body(raw, c.group("file")), "destination": _FOLDERS.get(dst, dst).title() if dst in _FOLDERS else raw_body(raw, dst)})
    if re.search(r"\bdownloads?(?:\s+folder)?\b", t) and re.search(r"\b(?:organi[sz]e|clean(?:\s+up)?|sort(?:\s+out)?|tidy(?:\s+up)?)\s+(?:it|that|them)\b", t):
        return d("organize_downloads")
    c = re.search(r"\bfolder\b.*?\b(?:call|name)\s+it\s+(?P<n>[\w .'-]{1,60})$", t)
    if c and not m:
        return d("create_folder", {"path": raw_body(raw, c.group("n").strip())})
    if m:
        return d("rename_file", {"source": raw_body(raw, m.group("file")), "new_name": raw_body(raw, m.group("new")).strip()})
    c = re.fullmatch(r"(?:i\s+remember\s+|i\s+think\s+)?(?:i\s+)?(?:saving|saved|downloading|downloaded|putting|put|keeping|kept|had|have)\s+"
                     rf"(?:this\s+|my\s+|the\s+|a\s+|an\s+)?(?:{_FILE}|(?P<q2>[\w .'-]{{2,40}}?))\s+somewhere\b.*?\b(?P<act>open|find|locate|get|look\s+for|search\s+for)\s+(?:it|that)\b.*", t)
    if c and not re.search(rf"\b(?:{PHONE_WORDS}|keys?|wallet|glasses|car|bike|charger)\b", t):
        if c.group("file"):
            return d("open_file" if c.group("act") == "open" else "find_file",
                     {"path": raw_body(raw, c.group("file"))} if c.group("act") == "open" else {"query": raw_body(raw, c.group("file"))})
        return d("find_file", {"query": raw_body(raw, c.group("q2").strip())})
    m = (re.fullmatch(r"where\s+did\s+i\s+(?:save|put|keep|store|download|leave)\s+(?:my\s+|the\s+|that\s+)?(?P<q>.{2,60}?)", t)
         or (re.fullmatch(r"(?:where(?:'s|\s+is|\s+are)|find|locate|look\s+for|search\s+for|i\s+can'?t\s+find|i\s+cannot\s+find|i\s+lost|i\s+misplaced)\s+(?:my|the)\s+(?P<q>.{2,60}?)"
                          r"(?:\s+(?:anywhere|somewhere))?"
                          r"(?:\s+(?:file|document|pdf|scan))?(?:\s+(?:somewhere\s+)?(?:on|in)\s+(?:this|my|the)\s+(?:pc|computer|laptop|system|drive))?", t)
             if _DOC_NOUN.search(t) and not re.search(rf"\b(?:{PHONE_WORDS}|keys?|wallet|glasses|car|bike|charger|remote|earphones?|headphones?)\b", t)
             else None)
         or re.fullmatch(r"(?:i\s+need|i\s+want|get\s+me)\s+(?:my\s+|the\s+)?(?P<q>.{2,60}?)\s*,?\s*(?:where(?:'s|\s+is)\s+it|find\s+it|can\s+you\s+find\s+it)", t)
         or re.fullmatch(r"(?:i\s+think\s+|maybe\s+|i\s+guess\s+)?i\s+(?:downloaded|saved|got|received|made|scanned|kept)\s+(?:a|an|the|my|that)\s+(?P<q>.{2,60}?)(?:\s+(?:yesterday|today|earlier|last\s+\w+|this\s+\w+|recently))?"
                         r"\s*,?\s*(?:(?:can\s+you\s+|please\s+)?(?:find|locate|open|get|show)\s+(?:it|that)(?:\s+for\s+me)?|where(?:'s|\s+is)\s+it(?:\s+now)?|where\s+did\s+it\s+go)", t))
    if m and not re.search(rf"\b(?:{PHONE_WORDS}|car|keys?|wallet|glasses)\b", m.group("q")):
        return d("find_file", {"query": raw_body(raw, re.sub(r"\s+(?:file|files)$", "", m.group("q")).strip())})
    m = re.fullmatch(rf"(?:how\s+big|what(?:'s|\s+is)\s+the\s+size\s+of|when\s+was)\s+(?:is\s+)?{_FILE}(?:\s+(?:last\s+)?(?:created|modified|made|changed|edited|updated|saved|opened))?", t)
    if m:
        return d("read_file_metadata", {"path": raw_body(raw, m.group("file"))})
    m = (re.fullmatch(r"(?:dig\s+up|look\s+for|hunt\s+down|track\s+down|locate|search\s+for|find)\s+(?:my\s+|the\s+)?(?P<q>.+?)"
                      r"(?:\s+(?:somewhere\s+)?on\s+(?:this|my|the)\s+(?:pc|computer|laptop|system))?", t)
         or re.fullmatch(r"(?:i\s+can'?t\s+find|where'?s|i\s+lost)\s+(?:my\s+|the\s+)?(?P<q>.+?)\s*,?\s*(?:look|search|find|check)\s+(?:for\s+)?(?:it|that)", t)
         or re.fullmatch(r"(?:that|the)\s+(?P<q>.+?)\s+i\s+(?:downloaded|saved|got|made|wrote)(?:\s+\w+)?\s*,?\s*(?:find|get|open|show)\s+(?:it|that)", t))
    if m and not re.search(r"\bduplicates?\b|\bcopies\b", t) and re.search(r"\b(?:file|files|pdf|doc|docx|resume|cv|invoice|report|letter|certificate|scan|return|statement|slip|"
                       r"ticket|photo|picture|document|notes?|presentation|spreadsheet|sheet|contract|receipt|bill)\b", m.group("q")):
        q = re.sub(r"\s+(?:file|files)$", "", m.group("q")).strip()
        return d("find_file", {"query": raw_body(raw, q)})
    if re.fullmatch(r"(?:show|list|open)(?:\s+me)?\s+(?:my\s+)?(?:recent|recently\s+(?:opened|used|modified|saved))\s+(?:files|documents|docs)", t):
        return d("find_file", {"query": "*", "time_hint": "recent"})
    return None


_SHORTCUT_KEYS = {"a": "ctrl_a", "c": "ctrl_c", "v": "ctrl_v", "x": "ctrl_x", "z": "ctrl_z", "y": "ctrl_y", "f": "ctrl_f", "s": "ctrl_s"}


def match_keys(t: str, request_id: str) -> Optional[RouteDecision]:
    """'press ctrl s', 'hit control+z', 'press alt tab': keyboard shortcuts, not clicks on something called 'ctrl s'."""
    m = re.fullmatch(r"(?:press|hit|use|do)\s+(?:the\s+)?(?P<mod>ctrl|control|alt|shift|win|windows)\s*[+\- ]\s*(?P<key>[a-z0-9]+|tab|enter|esc|escape)(?:\s+keys?)?", t)
    if not m:
        return None
    mod, key = m.group("mod"), m.group("key")
    if mod == "alt" and key == "tab":
        return _decision(request_id, t, "switch_window", {})
    if mod in ("ctrl", "control") and key in _SHORTCUT_KEYS:
        return _decision(request_id, t, "keyboard_shortcut", {"key": _SHORTCUT_KEYS[key]})
    if mod == "shift" and key == "tab":
        return _decision(request_id, t, "keyboard_shortcut", {"key": "shift_tab"})
    return _decision(request_id, t, "keyboard_shortcut", {"key": f"{'ctrl' if mod == 'control' else mod}_{key}"})


def match_routines_and_media(t: str, raw: str, request_id: str) -> Optional[RouteDecision]:
    """Workspaces, focus sessions, 'put on <song>', reopening a closed tab, and conversation that is not a command."""
    d = lambda intent, slots=None, **kw: _decision(request_id, t, intent, slots or {}, **kw)  # noqa: E731
    m = re.fullmatch(r"(?:launch|open|start|load|restore|switch\s+to)\s+(?:my\s+|the\s+)?(?P<n>[a-z0-9 _-]{1,30}?)\s+workspace", t)
    if m:
        return d("launch_workspace", {"name": m.group("n").strip()})
    m = re.fullmatch(r"(?:start|begin|turn\s+on|enable|enter)\s+(?:a\s+|the\s+)?(?:(?P<m1>\d{1,3})[- ]?(?:min(?:ute)?s?)\s+)?"
                     r"(?P<kind>focus(?:\s+mode)?|study(?:\s+(?:session|mode|time))?|pomodoro|deep\s+work)"
                     r"(?:\s+(?:session|mode))?(?:\s+(?:for|of)\s+(?P<m2>\d{1,3})\s*(?:min(?:ute)?s?|hours?|hrs?))?(?:\s+(?:on|for)\s+(?P<subj>[a-z ]{2,30}))?", t)
    if m:
        minutes = int(m.group("m1") or m.group("m2") or 25)
        if m.group("m2") and re.search(r"\b(?:hours?|hrs?)\b", t):
            minutes *= 60
        return d("start_study_focus", {"subject": (m.group("subj") or "focus").strip(), "duration_minutes": min(180, minutes)})
    if re.fullmatch(r"(?:re-?open|restore|bring\s+back)\s+(?:the\s+)?(?:last\s+|closed\s+)?tab(?:\s+(?:that\s+)?i\s+(?:just\s+)?closed)?", t):
        return d("browser_quick_action", {"action": "reopen_tab"})
    m = re.fullmatch(r"put\s+on\s+(?:some\s+)?(?P<q>.+?)(?:\s+on\s+youtube)?", t)
    if m and not re.fullmatch(r"(?:a|an|some|the)?\s*(?:video|videos|music|song|songs|track|tracks|something|anything|movie|show)", m.group("q")) \
            and not re.search(rf"\b(?:{PHONE_WORDS}|do\s+not\s+disturb|dnd|silent|mute|hold|charge|charging|speaker|headphones?|"
                           r"airplane|flight|my\s+(?:shoes|jacket|glasses))\b", t):
        return d("play_youtube", {"query": raw_body(raw, m.group("q").strip())})
    # conversation, not commands
    if re.fullmatch(r"(?:ok(?:ay)?\s+)?(?:thank\s+you|thanks|thx|ty|thank\s+u)(?:\s+(?:so\s+much|a\s+lot|jarvis|buddy|man))*"
                    r"|(?:good|great|nice|awesome|well)\s+(?:job|work|done)(?:\s+jarvis)?|you(?:'re|\s+are)\s+(?:awesome|great|the\s+best|amazing)", t) \
            or re.search(r"(?:^|,\s*)i'?m\s+(?:just\s+|so\s+|really\s+|very\s+|kinda\s+|totally\s+|completely\s+|a\s+bit\s+)*"
                         r"(?:exhausted|tired|drained|sleepy|bored|sad|stressed|worn\s+out|burnt\s+out|done|lonely|upset|happy)\s*[.!]*$", t) \
            or re.fullmatch(r"(?:thanks|thank\s+you|thx)\s+(?:da|bro|machi|macha|dude|boss|sir|ma|pa)(?:\s+jarvis)?", t) \
            or re.fullmatch(r"(?:good\s+(?:night|afternoon|evening)|gn|sweet\s+dreams|see\s+you(?:\s+later|\s+tomorrow)?|bye(?:\s+bye)?|"
                            r"goodbye|take\s+care|how(?:'s|\s+is)\s+(?:it\s+going|your\s+day(?:\s+going)?|life))(?:\s+(?:jarvis|buddy|man|bro))?", t) \
            or re.match(r"^(?:(?:honestly|really|actually|ugh|man|so|well|tbh|to\s+be\s+honest)\s*,?\s+)?"
                        r"(?:i'?m\s+feeling|i\s+am\s+feeling|i'?m|i\s+am|i\s+feel|feeling)\s+(?:so\s+|very\s+|really\s+|a\s+(?:bit|little)\s+|kinda\s+|pretty\s+|super\s+|quite\s+|too\s+)*"
                        r"(?:bored|tired|sad|happy|lonely|stressed|hungry|sleepy|excited|anxious|exhausted|sick|unwell|down|low|great|good|fine|"
                        r"angry|upset|nervous|worried|confused|lost|overwhelmed|frustrated|motivated|lazy|cold|thirsty|depressed|scared|proud)\b", t) \
            or re.match(r"^(?:tell|say\s+to)\s+me\s+(?:that\s+)?(?:i'?m|i\s+am|you'?re|you\s+are|i\s+(?:can|will|look))\b", t) \
            or re.fullmatch(r"what(?:'s|\s+is)\s+your\s+(?:name|age|favou?rite\s+\w+|purpose|job)|who\s+(?:are\s+you|made\s+you|created\s+you|built\s+you)"
                            r"|how\s+old\s+are\s+you|are\s+you\s+(?:real|human|alive|a\s+robot|an?\s+ai|single|happy|ok|okay)|do\s+you\s+have\s+(?:feelings|a\s+name)", t) \
            or re.match(r"^(?:suggest|recommend)\s+(?:me\s+)?(?:something|some|a|an|any|what)\b", t) \
            or re.match(r"^(?:give|tell|show)\s+me\s+(?:a|an|some|one|another)\s+(?:\w+\s+)?"
                        r"(?:recipe|idea|tip|suggestion|example|quote|fact|joke|story|riddle|name)s?\b", t) \
            or re.match(r"^(?:write|compose|draft|make\s+up)\s+(?:me\s+)?(?:a|an|some)\s+(?:\w+\s+){0,2}(?:poem|story|essay|song|haiku|limerick|"
                        r"joke|speech|paragraph|caption|bio|letter\s+to\s+santa)s?\b", t):
        return d(None, {}, lane=RouteLane.LANE_2, reason=ReasonCode.QUESTION_NOT_COMMAND)
    return None


def match_type_text(t: str, raw: str, request_id: str) -> Optional[RouteDecision]:
    """'type Hello World' -> type exactly those words (original casing) into the window in front."""
    m = re.match(r"^(?:type|type out|type in)\s+(?P<body>.+)$", t)
    if not m or re.search(rf"\b(?:on|in|into)\s+(?:my\s+|the\s+)?{PHONE_WORDS}\b", t):
        return None
    body = m.group("body")
    if re.fullmatch(r"(?:what|whatever|everything|all that)\s+i\s+(?:say|speak|tell).*", body):
        return None
    return _decision(request_id, t, "dictate_text", {"text": raw_body(raw, body).rstrip(" .!?") or body})


def match_extended(text: str, request_id: str) -> Optional[RouteDecision]:
    """Return a routing decision for the extended domains, or None to continue normal routing."""
    raw = text.strip()
    bulk = match_bulk_reply(raw, request_id)
    if bulk:
        return bulk
    t = re.sub(r"\s+", " ", raw.lower()).strip(" .!?")
    if re.match(r"^(?:would|do|don't|did)\s+(?:you|u)\s+(?:like|love|enjoy|prefer|wanna)\b(?!\s+to\s+(?:open|close|turn|set|send|launch|start)\b)", t):
        return _decision(request_id, t, None, {}, lane=RouteLane.LANE_2, reason=ReasonCode.QUESTION_NOT_COMMAND)
    t = re.sub(r"^(?:please|kindly|jarvis|hey jarvis|ok jarvis|can you|could you|would you)\s+", "", t)
    t = re.sub(r"^(?:please|kindly)\s+", "", t)
    if not t:
        return None
    wa_read = match_whatsapp_read(t, raw, request_id)
    if wa_read:
        return wa_read
    question = match_knowledge_question(t, request_id)
    if question:
        return question
    phone_extra = match_phone_extras(t, request_id)
    if phone_extra:
        return phone_extra
    google = match_google(t, raw, request_id)  # before software: "set up a call with arun" is not an install
    if google:
        return google
    system = match_system(t, request_id)
    if system:
        return system
    files = match_files(t, raw, request_id)
    if files:
        return files
    routines = match_routines_and_media(t, raw, request_id)
    if routines:
        return routines
    keys = match_keys(t, request_id)
    if keys:
        return keys
    software = match_software(re.sub(r"^(?:please|kindly|jarvis|hey jarvis|can you|could you|would you|just)\s+", "", t), request_id)
    if software:
        return software
    if re.match(r"^(?:continue|carry on|go on|resume|keep going)(?:\s+(?:the|with the|in the))?\s+(?:browser|web)(?:\s+task)?$"
                r"|^(?:i(?:'ve| have)?|ok(?:ay)?,? i(?:'ve| have)?)\s+(?:logged|signed)\s+in(?:\s+now)?(?:,? continue)?$"
                r"|^done logging in$", t) or (re.match(r"^(?:continue|carry on|go on|keep going|resume)$", t) and _web_task_pending()):
        return _decision(request_id, t, "web_task", {"resume": True})
    from jarvis.core.multilingual import match_language_switch
    language = match_language_switch(t)
    if language:
        return _decision(request_id, t, "set_reply_language", {"mode": language})
    voice_screen = match_voice_and_screen(t, raw, request_id)
    if voice_screen:
        return voice_screen
    dictation = match_dictation(t, request_id)
    if dictation:
        return dictation
    typed = match_type_text(t, raw, request_id)
    if typed:
        return typed

    person = match_person(t, request_id)
    if person:
        return person
    login = match_login(t, request_id)
    if login:
        return login
    if re.fullmatch(r"(?:in|on|via|using)\s+whats\s*app", t):
        return _decision(request_id, t, "clarify", {}, lane=RouteLane.CLARIFY,
                         clarification="What would you like me to do in WhatsApp? If a reply is awaiting confirmation, confirm that request.")
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
        return _match_whatsapp(t, raw, request_id) if re.match(r"^(?:ask|remind|let|inform|wish|reply|respond|tell|text|message|msg|ping|whatsapp|send|shoot|drop)\b", t) else None

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
    m = re.match(r"^(?:list|show|read|check|what are|tell me)(?: me)? (?:all )?(?:of )?(?:my |the )?(?:pending |upcoming |active )?reminders(?: (?:for )?(?:today|tomorrow|now))?$"
                 r"|^(?:do i have|are there) any reminders(?: (?:for )?(?:today|tomorrow))?$", t)
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
    "auto_rotate": r"auto ?-?rotat(?:e|ion)|screen rotation", "flashlight": r"(?:the\s+)?(?:flash ?light|torch)",
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


_IP = r"\d{1,3}(?:\.\d{1,3}){3}(?::\d{2,5})?"


def match_phone_extras(t: str, request_id: str) -> Optional[RouteDecision]:
    m = re.fullmatch(rf"put\s+(?:my\s+|the\s+)?{PHONE_WORDS}\s+(?:on|in|into|to)\s+(?P<mode>do\s+not\s+disturb|dnd|silent(?:\s+mode)?|airplane\s+mode|flight\s+mode)", t)
    if m:
        mode = m.group("mode")
        setting = "airplane_mode" if re.search(r"airplane|flight", mode) else "do_not_disturb"
        return _decision(request_id, t, "android_toggle", {"setting": setting, "on": True})
    m = re.fullmatch(r"(?:dial|call|ring)\s+(?P<num>\+?\d[\d\s-]{5,}\d)(?:\s+on\s+my\s+phone)?", t)
    if m:
        return _decision(request_id, t, "android_dial", {"number": re.sub(r"[^\d+]", "", m.group("num"))})
    return None


def match_phone_connect(t: str, request_id: str) -> Optional[RouteDecision]:
    """'connect my phone', 'connect my phone at 192.168.1.23', 'pair my phone with code 123456 at 192.168.1.23:37123'."""
    if not re.search(rf"\b(?:connect|reconnect|pair|link)\b.*\b{PHONE_WORDS}\b|\b{PHONE_WORDS}\b.*\b(?:connect|pair)\b", t):
        return None
    if re.search(r"\b(?:send|share|transfer|copy|file|photo)\b", t):
        return None
    if re.fullmatch(rf"connect\s+to\s+(?:my\s+|the\s+)?{PHONE_WORDS}", t):
        return None  # "connect to my phone" could mean bluetooth, a call or mirroring: ask ("connect my phone" is ADB)
    code = re.search(r"\b(?:code\s*)?(\d{6})\b", t)
    ips = re.findall(_IP, t)
    if re.search(r"\bpair", t) and code:
        slots = {"pairing_code": code.group(1)}
        if ips:
            slots["pair_address"] = ips[0]
        if len(ips) > 1:
            slots["address"] = ips[1]
        return _decision(request_id, t, "android_connect", slots)
    if re.search(r"\b(?:is\s+my\s+phone\s+connected|phone\s+status)\b", t):
        return None
    return _decision(request_id, t, "android_connect", {"address": ips[0]} if ips else {})


def _match_phone(t: str, raw: str, request_id: str) -> Optional[RouteDecision]:
    # "switch my phone's bluetooth on" -> "switch bluetooth on on my phone"
    t = re.sub(rf"\b(?:my|the)\s+({PHONE_WORDS})'?s\s+(wi-?fi|bluetooth|hotspot|flash\s*light|torch|location|gps|mobile\s+data|data|"
               r"airplane\s+mode|aeroplane\s+mode|dnd|do\s+not\s+disturb|auto[- ]?rotate|rotation|nfc|battery\s+saver|power\s+saving)\s+(on|off)$",
               r"\2 \3 on my \1", t)
    conn = match_phone_connect(t, request_id)
    if conn:
        return conn
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


_NOT_PEOPLE = frozenset({"google", "alexa", "siri", "chatgpt", "gemini", "claude", "jarvis", "youtube", "amazon", "flipkart",
                         "everyone", "everybody", "someone", "anyone", "me", "you", "him", "her", "them", "us", "it"})


def _name_like(who: str) -> bool:
    """'priya', 'arun kumar': one or two words that are not English words, apps or assistants (a person's name)."""
    words = who.lower().split()
    if not 1 <= len(words) <= 2 or any(w in _NOT_PEOPLE for w in words):
        return False
    try:
        from jarvis.integrations.whatsapp.personal_reply.language import english_words
        common = english_words()
    except Exception:
        common = frozenset()
    return all(w.isalpha() and w not in common for w in words)


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
        ("direct", r"^(?:send|shoot|drop|fire\s+off|text|message|ping|whatsapp)\s+(?P<who>[\w .'+-]+?)\s+a\s+(?:quick\s+|short\s+|small\s+)?"
                   r"(?:text|message|msg|whatsapp(?:\s+message)?|line|note)\s*(?:saying|that says|to say|stating|that|with|:)\s*(?P<body>.+)$"),
        ("direct", r"^(?:tell|text|message|msg|ping|whatsapp|send)\s+(?:a\s+(?:message|msg|text)\s+to\s+)?(?P<who>[\w .'+-]+?)\s+(?:saying|that says|to say|stating|with the message|with message)\s+(?P<body>.+)$"),
        ("direct", r"^(?:text|message|msg|ping|whatsapp)\s+(?P<who>[\w .'+-]+?)\s+and\s+(?:tell|say\s+to|let)\s+(?:him|her|them)\s+(?:know\s+)?(?:that\s+)?(?P<body>.+)$"),
        ("direct", r"^(?:text|message|msg|ping|whatsapp)\s+(?P<who>[\w .'+-]+?)\s+and\s+(?:say|write|type)\s+(?:that\s+)?(?P<body>.+)$"),
        ("direct", r"^(?:text|message|msg|ping|whatsapp|send\s+a\s+message\s+to)\s+(?P<who>[\w .'+-]+?)\s+(?:on|in|via)\s+whats\s*app\s*,?\s*(?:and\s+)?"
                   r"(?:say|saying|tell\s+(?:him|her|them)|let\s+(?:him|her|them)\s+know)\s+(?:that\s+)?(?P<body>.+)$"),
    )
    for style, pattern in patterns:
        m = re.match(pattern, stripped)
        if not m:
            continue
        who = _clean_person(m.group("who"))
        if who.lower() in ("me", "myself", "us") and style == "remind":
            return None  # "remind me ..." is a reminder, not a message
        if not _looks_like_person(who, t) or (style != "direct" and not has_wa and who.lower() not in RELATION_WORDS
                                              and not _known_contact(who) and not _name_like(who)):
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
