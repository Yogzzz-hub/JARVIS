import re
from typing import Any, Optional
from jarvis.core.router.models import (
    RouteDecision,
    RouteLane,
    RouteSource,
    ComplexityLevel,
    ReasonCode,
)

AMBIGUOUS_APPS = {
    "studio": ("Android Studio", "Visual Studio", "Visual Studio Code", "OBS Studio"),
    "visual studio": ("Visual Studio Code", "Visual Studio IDE"),
    "office": ("Microsoft Word", "Microsoft Excel", "Microsoft PowerPoint"),
    "terminal": ("Windows Terminal", "Command Prompt", "PowerShell"),
    "player": ("Windows Media Player", "VLC media player", "Spotify"),
    "reader": ("Adobe Acrobat Reader", "Foxit Reader", "Kindle"),
    "editor": ("Notepad", "Visual Studio Code", "Notepad++"),
    "workbench": ("MySQL Workbench", "Azure Data Studio"),
    "paint": ("MS Paint", "Paint.NET"),
    "notes": ("OneNote", "Sticky Notes", "Memos"),
    "music": ("Spotify", "YouTube Music", "Groove Music"),
    "messenger": ("WhatsApp", "Telegram", "Facebook Messenger"),
    "code": ("Visual Studio Code", "CodeBlocks", "Claude Code"),
    "python": ("Python Interactive", "IDLE", "PyCharm"),
    "browser": ("Chrome", "Edge", "Firefox"),
}

GENERIC_RESOURCE_PATTERNS = (
    re.compile(r"^(?:(?:i\s+want\s+to\s+|can\s+i\s+|let\s+me\s+)?(?:open|delete|remove|edit|view|show|see|look\s+at|print|share|export))\s+(?:the\s+|that\s+|this\s+)?(?P<res_type>file|document|pdf|pdf\s+file|code\s+file|notes\s+file|log\s+file|archive|backup|spreadsheet|presentation|invoice|contract|report|image|receipt|script|dataset|audio|audio\s+recording|video|video\s+clip)$", re.I),
    re.compile(r"^(?:click|press|tap)\s+(?:the\s+)?(?:continue|submit|download|accept|confirm|next|ok)\s*(?:button|link)?(?:\s+on\s+(?:the\s+)?page)?$", re.I),
    re.compile(r"^(?:play|put\s+on)\s+(?:some\s+)?(?:music|songs?|tracks?|videos?|a\s+video)$", re.I),
    re.compile(r"^(?:connect\s+to|pair\s+with)\s+(?:my\s+)?(?:phone|mobile|device|display)$", re.I),
    re.compile(r"^(?:switch\s+to|open)\s+(?:the\s+)?(?:terminal|documentation|project\s+settings|notes)$", re.I),
    re.compile(r"^(?:send|forward)\s+(?:the\s+)?(?:email|document|file)(?:\s+to\s+\w+)?$", re.I),
)

_HELPER_WORDS = re.compile(r"stub|helper|service|updater|update|crash|report|setup|uninst|install|host|daemon|agent|broker|"
                           r"elevat|notif|svc|tray|diag|reset|repair|telemetry|bootstrap|launcher\.exe|runtime|redist")
_BARE_VERBS = {"", "open", "start", "launch", "run", "the", "app", "application", "program", "it", "that", "this", "something"}


def _app_words(name: str) -> list[str]:
    n = re.sub(r"\.exe$", "", (name or "").casefold())
    n = re.sub(r"([a-z])([A-Z])", r"\1 \2", n)
    return [w for w in re.split(r"[^a-z0-9+]+", n) if w]


def plausible_app_match(query: str, candidate: str) -> bool:
    """Would a person saying ``query`` plausibly mean the app ``candidate``?

    "engine" does not mean "mlenginestub" or "resetengine" (helper executables, substring hits), and a bare verb
    ("open") means no app at all. A whole-word or real prefix match is required.
    """
    q_words = [w for w in _app_words(query) if w not in ("the", "a", "an", "my")]
    q = "".join(q_words)
    if not q or " ".join(q_words) in _BARE_VERBS or len(q) < 3:
        return False
    cand = (candidate or "").casefold()
    if _HELPER_WORDS.search(cand) and not _HELPER_WORDS.search(q):
        return False
    c_words = _app_words(candidate)
    compact = "".join(c_words)
    if any(w in c_words for w in q_words if len(w) >= 3):
        return True
    return compact.startswith(q) and len(q) / max(1, len(compact)) >= 0.34


def is_launchable_application_name(name: str) -> bool:
    """Filters out python scripts, internal utilities, test runners, and technical symbols."""
    low = name.casefold().strip()
    if any(p in low for p in ("plotly", "pytest", "pip", "wheel", "twine", "setup", "helper", "daemon", "stub", "broker")):
        return False
    if "_" in low:
        return False
    if low.endswith(("-cli", ".py", ".sh", ".bat", ".cmd", ".ps1")):
        return False
    return True


def disambiguate_app(
    app_name: str,
    resolver: Any,
    request_id: str,
    normalized_text: str,
) -> RouteDecision | None:
    """Checks if an application name is ambiguous and requires user clarification."""
    lowered = app_name.strip().casefold()
    clean_app = re.sub(r"\s+(?:on\s+(?:my\s+)?screen|for\s+me|right\s+now|please|now)$", "", lowered).strip()

    # Explicit multi-word names that are already specific must not be flagged ambiguous
    if clean_app in ("file explorer", "windows explorer", "explorer", "google chrome", "visual studio code", "terminal window", "windows terminal", "terminal"):
        return None

    matched_ambig = None
    if clean_app in AMBIGUOUS_APPS:
        matched_ambig = clean_app
    elif clean_app.split()[0] in AMBIGUOUS_APPS and len(clean_app.split()) <= 2:
        matched_ambig = clean_app.split()[0]

    if matched_ambig:
        choices = AMBIGUOUS_APPS[matched_ambig]
        choices_str = ", ".join(choices[:-1]) + f", or {choices[-1]}"
        return RouteDecision(
            request_id=request_id,
            lane=RouteLane.CLARIFY,
            intent="clarify",
            slots={"raw_app": clean_app, "candidates": list(choices)},
            confidence=0.5,
            source=RouteSource.EXACT,
            complexity=ComplexityLevel.SIMPLE,
            clarification=f"Which application did you mean: {choices_str}?",
            normalized_text=normalized_text,
            reason_code=ReasonCode.LOW_CONFIDENCE,
            candidate_count=len(choices),
        )

    # Check resolver cache if available
    if resolver and hasattr(resolver, "cache") and isinstance(resolver.cache, dict):
        matching = []
        for k in resolver.cache.keys():
            if not is_launchable_application_name(k):
                continue
            if plausible_app_match(clean_app, k) and re.sub(r"\.exe$", "", k) not in [re.sub(r"\.exe$", "", m) for m in matching]:
                matching.append(k)

        # Deduplicate candidates that resolve to the same application
        distinct_targets = {}
        for m in matching:
            try:
                t = resolver.resolve(m) if hasattr(resolver, "resolve") else None
                path = getattr(t, "path", m)
                if path not in distinct_targets:
                    distinct_targets[path] = m
            except Exception:
                if m not in distinct_targets:
                    distinct_targets[m] = m
        matching = list(distinct_targets.values())

        if len(matching) > 1 and lowered not in resolver.cache:
            choices_str = ", ".join(m.title() for m in matching[:3])
            return RouteDecision(
                request_id=request_id,
                lane=RouteLane.CLARIFY,
                intent="clarify",
                slots={"raw_app": app_name, "candidates": matching[:3]},
                confidence=0.5,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                clarification=f"Which one do you mean: {choices_str}?",
                normalized_text=normalized_text,
                reason_code=ReasonCode.LOW_CONFIDENCE,
                candidate_count=len(matching),
            )

    return None

def disambiguate_generic_request(
    text: str,
    working_memory: Any,
    request_id: str,
) -> RouteDecision | None:
    """Checks if a request references an ambiguous generic target without referents."""
    cleaned = text.strip().rstrip(".!?")

    # 0. Check explicit ambiguity instruction: "if you're not sure, ask me" / "ask me if you're not sure"
    if re.search(r"\b(?:if (?:you're|you are) not sure\b.*?\b(?:ask me|clarify)|ask me if (?:you're|you are) not sure)\b", cleaned, re.I):
        m_type = re.search(r"\b(document|file|pdf|spreadsheet|notes?|folder|app|program)\b", cleaned, re.I)
        type_name = m_type.group(1).lower() if m_type else "document"
        type_label = "PDF" if type_name == "pdf" else type_name
        return RouteDecision(
            request_id=request_id,
            lane=RouteLane.CLARIFY,
            intent="clarify",
            slots={},
            confidence=0.5,
            source=RouteSource.EXACT,
            complexity=ComplexityLevel.SIMPLE,
            clarification=f"Which {type_label} do you mean?",
            normalized_text=cleaned,
            reason_code=ReasonCode.LOW_CONFIDENCE,
            candidate_count=0,
        )

    # 1. Check contact messaging without message body
    m_msg_only = re.match(r"^(?:send\s+(?:a\s+)?message\s+to|message|tell|whatsapp|call)\s+([a-zA-Z0-9_\.\s]+?)(?:\s+on\s+whatsapp)?$", cleaned, re.I)
    if m_msg_only and not any(w in cleaned.lower() for w in ("saying", "that", "with text", ":")):
        contact_name = m_msg_only.group(1).strip()
        contact_tokens = contact_name.lower().split()
        msg_words = {"hi", "hello", "hey", "meeting", "at", "i", "we", "is", "are", "will", "can", "please", "come", "be", "have", "the", "a", "about", "tomorrow", "today", "tonight", "late", "done", "ready", "thanks", "good"}
        is_just_contact = len(contact_tokens) <= 3 and not any(w in msg_words for w in contact_tokens[1:])
        if is_just_contact:
            return RouteDecision(
                request_id=request_id,
                lane=RouteLane.CLARIFY,
                intent="clarify",
                slots={"contact": contact_name},
                confidence=0.5,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                clarification=f"What message would you like me to send to {contact_name}?",
                normalized_text=cleaned,
                reason_code=ReasonCode.LOW_CONFIDENCE,
                candidate_count=1,
            )

    # 2. Check generic resource without specific name or referents
    for pat in GENERIC_RESOURCE_PATTERNS:
        m = pat.match(cleaned)
        if m:
            # Check if working_memory has a valid context referent before asking
            res_type = m.groupdict().get("res_type") or "target"
            has_context = False
            if working_memory:
                if res_type.lower() == "pdf":
                    curr = getattr(working_memory, "get_current_resource", lambda: None)()
                    last_opened = getattr(working_memory, "get_last_opened_file", lambda: None)()
                    search_res = getattr(working_memory, "get_recent_search_results", lambda: [])()
                    has_context = bool((curr and getattr(curr, "canonical_path", "").lower().endswith(".pdf")) or
                                       (last_opened and last_opened.lower().endswith(".pdf")) or
                                       any(str(r).lower().endswith(".pdf") for r in search_res))
                elif res_type.lower() in ("file", "document"):
                    curr = getattr(working_memory, "get_current_resource", lambda: None)()
                    last_opened = getattr(working_memory, "get_last_opened_file", lambda: None)()
                    has_context = bool(curr or last_opened)

            if not has_context:
                type_label = "PDF" if res_type.lower() == "pdf" else res_type
                return RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.CLARIFY,
                    intent="clarify",
                    slots={},
                    confidence=0.5,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    clarification=f"Which {type_label} do you mean?",
                    normalized_text=cleaned,
                    reason_code=ReasonCode.LOW_CONFIDENCE,
                    candidate_count=0,
                )

    return None
