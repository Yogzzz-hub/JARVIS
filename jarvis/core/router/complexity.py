import re
from jarvis.core.router.catalog import IntentCatalog
from jarvis.core.router.models import (
    RouteDecision,
    RouteLane,
    RouteSource,
    ComplexityLevel,
    ReasonCode,
    SubCommand,
)
from jarvis.core.router.slots import parse_app_name

COMPLEX_PATTERNS = (
    re.compile(r"\b(?:prepare|organize)\s+(?:everything|tomorrow|the\s+lab)", re.I),
    re.compile(r"\bfind\s+.+\s+(?:and|then)\s+(?:email|send|put|move|copy|summarize|extract|organize)\b", re.I),
    re.compile(r"\bfind\s+.+\s+(?:summarize|extract|organize|save|compare)\b", re.I),
    re.compile(r"\b(?:summarize|extract)\s+.+\s+(?:and|then|to|draft)\b", re.I),
    re.compile(r"\b(?:email|send\s+an?\s+email|send\s+(?:the\s+)?files?)\s+.+\s+to\s+\w+\b", re.I),
    re.compile(r"\bcheck\s+.+\s+(?:then|after\s+that)\b", re.I),
    re.compile(r"\bafter\s+that\b", re.I),
    re.compile(r"\b(?:download|install|setup|update|upgrade)\s+[a-zA-Z0-9_\-\.]+", re.I),
    re.compile(r"\b(?:powershell|run script|terminal command|as administrator|run as admin)\b", re.I),
    re.compile(r"\b(?:automate|browser automation|click on|navigate to|dom screen)\b", re.I),
    re.compile(r"\bbased\s+on\b", re.I),
    re.compile(r"\bcompare\s+.+\s+and\b", re.I),
    re.compile(r"\b(?:but\s+(?:don't|do\s+not|never)|without\s+(?:opening|modifying|deleting|sending))\b", re.I),
    re.compile(r"\b(?:in\s+read-only\s+mode|read-only|as\s+(?:a\s+)?draft\s+only|draft\s+only\s+without\s+sending)\b", re.I),
    re.compile(r"\b(?:together\s+side\s+by\s+side|and\s+.+\s+side\s+by\s+side)\b", re.I),
    re.compile(r"\b(?:take\s+screenshot\s+and\s+(?:send|transfer|open))\b", re.I),
    re.compile(r"\b(?:after\s+finding\s+it|before\s+opening\s+it)\b", re.I),
    re.compile(r"\b(?:coordinate|workflow|pipeline|multi-capability|multi capability|sequence\s+#?\d+)\b", re.I),
    re.compile(r"\bif\s+above\s+\d+%.+(?:list|notify|alert)\b", re.I),
    re.compile(r"\b(?:and\s+then|,\s*then|then\s+draft|then\s+send|then\s+copy|then\s+open)\b", re.I),
    re.compile(r"\b(?:trim\s+.+\s+and\s+send)\b", re.I),
    re.compile(r"\b(?:look\s+up\s+.+\s+and\s+(?:open|extract|save))\b", re.I),
    re.compile(r"\b(?:list\s+.+\s+and\s+organize)\b", re.I),
    re.compile(r"\b(?:check\s+.+\s+and\s+save)\b", re.I),
    re.compile(r"\b(?:extract\s+.+\s+and\s+(?:compose|draft|send))\b", re.I),
    re.compile(r"\b(?:find\s+.+\s+and\s+(?:notify|check))\b", re.I),
)


def _match_clause_to_subcommand(clause: str) -> SubCommand | None:
    c = clause.strip()
    if not c:
        return None

    # 1. open_app: open / start / launch
    m_open = re.match(r"^(?:open|start|launch|bring up)\s+(?:the\s+)?([a-zA-Z0-9_\s\.\-]+)$", c, re.I)
    if m_open:
        app_name = parse_app_name(m_open.group(1).strip())
        if app_name and len(app_name.split()) <= 3 and not any(w in app_name for w in ("message", "send", "check", "then")):
            return SubCommand(intent="open_app", tool="open_app", arguments={"name": app_name})

    # 2. close_app: close / exit / kill
    m_close = re.match(r"^(?:close|exit|quit|kill)\s+(?:the\s+)?([a-zA-Z0-9_\s\.\-]+)$", c, re.I)
    if m_close:
        app_name = parse_app_name(m_close.group(1).strip())
        if app_name and len(app_name.split()) <= 3:
            return SubCommand(intent="close_app", tool="close_app", arguments={"name": app_name})

    # 3. send_whatsapp_message: message / send message to / tell / say / send <msg> to <recipient>
    m_msg = re.match(
        r"^(?:say|send|tell)\s+(?P<message>(?!whatsapp|message|this|the|a\s+message).+?)\s+to\s+(?P<recipient>[a-zA-Z0-9_\-\s]+?)(?:\s+(?:in|on)\s+whatsapp)?$",
        c,
        re.I,
    )
    if not m_msg:
        m_msg = re.match(
            r"^(?:tell|text|message)\s+(?P<recipient>[a-zA-Z0-9_\-]+)(?:\s+(?:in|on)\s+whatsapp)?\s+(?:saying\s+|that\s+|:\s*)?(?P<message>.+?)(?:\s+(?:in|on)\s+whatsapp)?$",
            c,
            re.I,
        )
    if not m_msg:
        m_msg = re.match(
            r"^(?:(?:send(?: a)? )?whatsapp (?:message )?to |whatsapp )(?P<recipient>[a-zA-Z0-9_\-\s]+?)(?:\s+(?:saying|that|:)\s+|\s*:\s*|\s+)(?P<message>.+)$",
            c,
            re.I,
        )
    if not m_msg:
        m_msg = re.match(
            r"^(?:(?:send(?: a)? )?message (?:to )?|tell |whatsapp )(?P<recipient>[a-zA-Z0-9_\s\-]+?)(?:\s+on whatsapp)?(?:\s+(?:saying|that|:)\s+|\s*:\s*)(?P<message>.+)$",
            c,
            re.I,
        )
    if m_msg:
        rec = m_msg.group("recipient").strip()
        msg_text = re.sub(r"\s+message$", "", m_msg.group("message").strip().strip('"\''), flags=re.I)
        if rec and msg_text and rec.lower() not in ("if", "the", "a", "me"):
            return SubCommand(intent="send_whatsapp_message", tool="send_whatsapp_message", arguments={"recipient": rec, "message": msg_text})

    # 4. search_web: check / search web / google / look up
    m_search = re.match(r"^(?:check(?: if)?|search(?: the)? web for|google|look up)\s+(.+)$", c, re.I)
    if m_search:
        query = m_search.group(1).strip()
        return SubCommand(intent="search_web", tool="search_web", arguments={"query": query})

    # 5. volume_set: set volume to X%
    m_vol = re.match(r"^set volume to\s+(\d+)%?$", c, re.I)
    if m_vol:
        return SubCommand(intent="volume_set", tool="volume_set", arguments={"percent": int(m_vol.group(1))})

    # 6. show_dashboard: show / open dashboard
    if re.match(r"^(?:show|open|bring up)\s+(?:the\s+)?dashboard$", c, re.I):
        return SubCommand(intent="show_dashboard", tool="show_dashboard", arguments={})

    # 7. system_info: system info / status
    if re.match(r"^(?:system\s+info|system\s+status|hardware\s+info)$", c, re.I):
        return SubCommand(intent="system_info", tool="system_info", arguments={})

    # 8. read_whatsapp_messages
    if re.match(r"^(?:read|check)\s+(?:my\s+)?(?:whatsapp\s+)?messages?$", c, re.I):
        return SubCommand(intent="read_whatsapp_messages", tool="read_whatsapp_messages", arguments={})

    # 9. android_open_control: show phone / mirror phone
    if re.match(r"^(?:show|mirror|open)\s+(?:my\s+)?phone$", c, re.I):
        return SubCommand(intent="android_open_control", tool="android_open_control", arguments={})

    # 10. localsend_file: send file to phone / send this to my phone
    if re.match(r"^(?:send\s+(?:this\s+)?(?:file\s+)?to\s+(?:my\s+)?phone|send\s+(?:the\s+)?latest\s+pdf\s+to\s+(?:my\s+)?phone)$", c, re.I):
        return SubCommand(intent="localsend_file", tool="localsend_file", arguments={})

    # 11. memos_create: make a note / take a note
    m_note = re.match(r"^(?:make|take|create)\s+a\s+note(?:\s+(?:that|:))?\s+(.+)$", c, re.I)
    if m_note:
        return SubCommand(intent="memos_create", tool="memos_create", arguments={"content": m_note.group(1).strip()})

    # 12. morning_briefing
    if re.match(r"^(?:good\s+morning(?:\s+jarvis)?|morning\s+briefing|what's\s+happening\s+today)$", c, re.I):
        return SubCommand(intent="morning_briefing", tool="morning_briefing", arguments={})

    # 13. play_youtube
    m_yt = re.match(r"^(?:play\s+(?P<query2>.+?)\s+(?:on|in)\s+youtube|(?:open\s+youtube\s+(?:and\s+)?play|play)\s+(?:on\s+youtube\s+|in\s+youtube\s+)?(?P<query>.+))$", c, re.I)
    if m_yt:
        q_yt = (m_yt.group("query2") or m_yt.group("query") or "").strip()
        # Clean any remaining redundant youtube references
        q_yt = re.sub(r"\b(?:in|on)\s+youtube\b", "", q_yt, flags=re.I).strip()
        if q_yt:
            return SubCommand(intent="play_youtube", tool="play_youtube", arguments={"query": q_yt})

    # 14. search_news
    m_news = re.match(r"^(?:(?:open\s+google\s+(?:and\s+)?search\s+news|search\s+news|what(?:'s| is)\s+the\s+news|latest\s+news|today(?:'s)?\s+news)(?:\s+(?:in|about|for))?\s*(?P<query>.*))$", c, re.I)
    if m_news:
        q_news = (m_news.group("query") or "India today news").strip()
        if not q_news:
            q_news = "India today news"
        return SubCommand(intent="search_news", tool="search_news", arguments={"query": q_news, "open_browser": True})

    # 15. window controls
    if re.match(r"^(?:close(?:\s+active)?\s+window|close(?:\s+this)?)$", c, re.I):
        return SubCommand(intent="close_window", tool="close_window", arguments={})
    if re.match(r"^(?:maximize(?:\s+window)?|max(?:\s+window)?|ful+[\s-]*screen(?:\s+window)?|(?:make\s+(?:it\s+|this\s+)?)?ful+[\s-]*screen)$", c, re.I):
        return SubCommand(intent="maximize_window", tool="maximize_window", arguments={})
    if re.match(r"^(?:minimize(?:\s+window)?|min(?:\s+window)?)$", c, re.I):
        return SubCommand(intent="minimize_window", tool="minimize_window", arguments={})
    if re.match(r"^(?:show\s+desktop|desktop|minimize\s+all)$", c, re.I):
        return SubCommand(intent="show_desktop", tool="show_desktop", arguments={})

    # 16. media controls
    m_media = re.match(r"^(?P<act>play|pause|next\s+track|next\s+song|next|previous\s+track|previous\s+song|previous|prev|stop\s+media|stop|mute|unmute|volup|voldown)$", c, re.I)
    if m_media:
        act = m_media.group("act").lower().replace(" ", "_")
        return SubCommand(intent="media_control", tool="media_control", arguments={"action": act})

    return None



def check_deterministic_compound(
    routing_text: str,
    catalog: IntentCatalog,
    request_id: str,
) -> RouteDecision | None:
    """Detects safe, bounded deterministic compound commands (max 5 subcommands)."""
    cleaned = routing_text.strip().rstrip(".!?")

    # Directly route 'open youtube and play <query>' to play_youtube
    m_yt_direct = re.match(r"^open\s+youtube\s+and\s+play\s+(?P<query>.+)$", cleaned, re.I)
    if m_yt_direct:
        q = m_yt_direct.group("query").strip()
        return RouteDecision(
            request_id=request_id,
            lane=RouteLane.LANE_0,
            intent="play_youtube",
            slots={"query": q},
            confidence=1.0,
            source=RouteSource.EXACT,
            complexity=ComplexityLevel.SIMPLE,
            risk="REVERSIBLE",
            missing_slots=[],
            normalized_text=routing_text,
            reason_code=ReasonCode.EXACT_PATTERN,
            subcommands=[],
            candidate_count=1,
        )

    # Case A: Homogeneous multi-app launch
    m_app = re.match(r"^(?:open|start|launch)\s+(.+)$", cleaned, re.I)
    if m_app:
        apps_clause = m_app.group(1)
        action_verb_prefix = re.compile(r"^(?:open|start|launch|message|send|tell|check|search|google|look up|find|set|close|show|bring up|play|pause|next|prev|mute|maximize|minimize)\b", re.I)
        app_names = re.split(r",\s*(?:and\s+)?|\s+and\s+", apps_clause)
        app_names = [a.strip() for a in app_names if a.strip()]
        if len(app_names) >= 2 and not any(action_verb_prefix.match(a) for a in app_names[1:]):
            subcommands = []
            for name in app_names:
                is_known = getattr(catalog, "is_known_app", lambda n: True)(name)
                if is_known:
                    subcommands.append(SubCommand(intent="open_app", tool="open_app", arguments={"name": name}))
                else:
                    break
            if len(subcommands) == len(app_names) and len(subcommands) <= 5:
                return RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.LANE_0,
                    intent="open_app",
                    slots={"apps": [sub.arguments["name"] for sub in subcommands]},
                    confidence=1.0,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.COMPOUND,
                    risk="REVERSIBLE",
                    missing_slots=[],
                    normalized_text=routing_text,
                    reason_code=ReasonCode.COMPOUND_COMMAND,
                    subcommands=subcommands,
                    candidate_count=1,
                )

    # Case B: Heterogeneous multi-action compound sentence
    # Split on commas or conjunctions followed by action keywords
    action_verbs = r"(?:open|start|launch|message|send|tell|check|search|google|look up|find|set|close|show|bring up|play|pause|next|prev|mute|maximize|minimize|summarize|extract|organize|draft|read|save|list|transfer|take|paste|copy|move|record|convert|inspect|review|audit|scan|compare|compose)"
    normalized = re.sub(r",\s*(?:and\s+)?then\s+", " ; ", cleaned, flags=re.I)
    normalized = re.sub(r"\s+(?:and\s+)?then\s+", " ; ", normalized, flags=re.I)
    normalized = re.sub(rf",\s*(?={action_verbs}\b)", " ; ", normalized, flags=re.I)
    normalized = re.sub(rf"\s+and\s+(?={action_verbs}\b)", " ; ", normalized, flags=re.I)

    clauses = [c.strip() for c in normalized.split(";") if c.strip()]
    if len(clauses) >= 2:
        subcommands = []
        for clause in clauses:
            sub = _match_clause_to_subcommand(clause)
            if sub is None:
                # If any clause cannot be matched deterministically, escalate to Lane 2 planner
                return RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.LANE_2,
                    intent=None,
                    slots={},
                    confidence=0.95,
                    source=RouteSource.COMPLEXITY_GATE,
                    complexity=ComplexityLevel.COMPLEX,
                    needs_planner=True,
                    normalized_text=routing_text,
                    reason_code=ReasonCode.MULTI_STEP,
                    candidate_count=0,
                )
            subcommands.append(sub)

        # Determine overall risk
        has_external = any(s.tool == "send_whatsapp_message" for s in subcommands)
        has_destructive = any(s.tool in ("delete_file", "delete") for s in subcommands)
        overall_risk = "DESTRUCTIVE" if has_destructive else ("EXTERNAL_EFFECT" if has_external else "REVERSIBLE")

        return RouteDecision(
            request_id=request_id,
            lane=RouteLane.LANE_0,
            intent="compound",
            slots={"steps": [s.tool for s in subcommands]},
            confidence=1.0,
            source=RouteSource.EXACT,
            complexity=ComplexityLevel.COMPOUND,
            risk=overall_risk,
            missing_slots=[],
            normalized_text=routing_text,
            reason_code=ReasonCode.COMPOUND_COMMAND,
            subcommands=subcommands,
            candidate_count=len(subcommands),
        )

    return None

def check_complexity_gate(
    routing_text: str,
    request_id: str,
) -> RouteDecision | None:
    """Evaluates whether the request requires the Phase-4 planner (Lane 2)."""
    text = routing_text.strip()

    constraints_list: list[dict[str, Any]] = []
    if re.search(r"\b(?:read-only|in read-only mode|read only)\b", text, re.I):
        constraints_list.append({"type": "read_only"})
    if re.search(r"\b(?:don't open|do not open|under no circumstances open|without opening|never open)\b", text, re.I):
        constraints_list.append({"type": "no_open"})
    if re.search(r"\b(?:don't modify|do not modify|without modifying|never modify|don't alter|no modify)\b", text, re.I):
        constraints_list.append({"type": "no_modify"})
    if re.search(r"\b(?:don't delete|do not delete|without deleting|never delete)\b", text, re.I):
        constraints_list.append({"type": "no_delete"})
    if re.search(r"\b(?:draft only|as draft only|as a draft only|without sending|do not send|don't send)\b", text, re.I):
        constraints_list.append({"type": "draft_only"})
        constraints_list.append({"type": "no_send"})
    if re.search(r"\b(?:don't install|do not install|without installing)\b", text, re.I):
        constraints_list.append({"type": "no_install"})

    for pattern in COMPLEX_PATTERNS:
        if pattern.search(text):
            return RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_2,
                intent=None,
                slots={},
                confidence=0.95,
                source=RouteSource.COMPLEXITY_GATE,
                complexity=ComplexityLevel.COMPLEX,
                needs_planner=True,
                normalized_text=routing_text,
                reason_code=ReasonCode.MULTI_STEP,
                constraints=constraints_list,
                candidate_count=0,
            )

    if constraints_list:
        return RouteDecision(
            request_id=request_id,
            lane=RouteLane.LANE_2,
            intent=None,
            slots={},
            confidence=0.95,
            source=RouteSource.COMPLEXITY_GATE,
            complexity=ComplexityLevel.COMPLEX,
            needs_planner=True,
            normalized_text=routing_text,
            reason_code=ReasonCode.MULTI_STEP,
            constraints=constraints_list,
            candidate_count=0,
        )

    return None
