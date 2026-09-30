"""Questions about JARVIS itself and control of its own tasks - answered from runtime state, never by a model or the web.

Routed before capability retrieval, the planner and the chat model, because these facts only exist inside JARVIS:

    system_diagnostics   "is JARVIS healthy", "run a self check"                  (existing fast 49-check health)
    jarvis_availability  "which parts of JARVIS are down / still work"
    resource_usage       "CPU / RAM / GPU usage right now"
    task_status          "what are you running, how far has it got, is anything stuck"
    previous_outcome     "what failed / succeeded in the last command"
    cancel_task          stop the foreground task (default) or only background jobs; the listener is never stopped

Negative constraints ("don't start or restart anything", "without Task Manager", "don't install anything") are
extracted first: the negated verbs can never become the action, and they are passed on as slots.
"How do I cancel a task?" is a knowledge question and is left to the normal flow (no execution).
"""
from __future__ import annotations

import re
from typing import Optional

from jarvis.core.router.models import ComplexityLevel, ReasonCode, RouteDecision, RouteLane, RouteSource

_NEG_VERBS = (r"start|restart|reboot|stop|stopping|cancel|abort|kill|end|install|uninstall|delete|deleting|remove|removing|open|"
              r"launch|wake|waking|load|touch|change|changing|close|closing|run|running|use|using|call|search|download")
# "don't start or restart anything", "without opening Task Manager", "no need to wake the models"
_NEGATION = re.compile(rf"\b(?:do\s*n[o']?t|dont|never|no\s+need\s+to|not|without|avoid)\s+(?:\w+ing\s+|\w+\s+){{0,1}}?"
                       rf"(?P<verbs>(?:{_NEG_VERBS})(?:ing|ed)?(?:\s+(?:or|and|/|,)\s+(?:{_NEG_VERBS})(?:ing|ed)?)*)\b[^,.;!?]*", re.I)
_TASK = (r"(?:task|tasks|job|jobs|command|commands|request|requests|operation|operations|action|"
         r"actions|step|steps|thing\s+you(?:'re|\s+are)\s+doing|background\s+work)")
_CANCEL = r"(?:stop|cancel|abort|kill|halt|terminate|end|interrupt|scrap|call\s+off)"
_JARVIS = (r"(?:jarvis|you|your|yourself|yours|the\s+assistant|assistant|its?\s+(?:parts|components|services|systems|modules|features)|"
           r"(?:parts|components|services|subsystems|modules|features|pieces)\s+of\s+(?:jarvis|you|the\s+assistant))")
_KNOWLEDGE = re.compile(r"^(?:why\b|how\s+(?:do|can|could|would|should|to)\b|what\s+(?:does|is\s+the\s+meaning|happens\s+if)\b|"
                        r"explain\s+how\b|is\s+it\s+possible\s+to\b|can\s+i\s+\w+\s+a\b)", re.I)
_LEAD = re.compile(r"^(?:(?:hey|ok|okay|so|um+|uh+|please|jarvis|now|also|and|quickly|just|can\s+you|could\s+you|would\s+you|"
                   r"will\s+you|i\s+want\s+you\s+to|i\s+need\s+you\s+to)[\s,]+)+", re.I)


def constraints(text: str) -> tuple[str, list[str]]:
    """(text without the negated clauses, the verbs the owner said not to do)."""
    verbs: list[str] = []

    def cut(m: re.Match) -> str:
        for v in re.split(r"\s+(?:or|and|/|,)\s+", m.group("verbs").lower()):
            v = v.strip()
            v = {"stopping": "stop", "running": "run", "waking": "wake", "closing": "close", "changing": "change",
                 "using": "use", "removing": "remove", "deleting": "delete"}.get(v, re.sub(r"(?:ing|ed)$", "", v))
            if v and v not in verbs:
                verbs.append(v)
        return " "
    rest = _NEGATION.sub(cut, text)
    return " ".join(rest.split()), verbs


def _scope(t: str) -> str:
    """Which task(s) a cancel request targets: 'background' only when background is named and not excluded."""
    bg = re.search(r"\bbackground\b", t)
    bg_excluded = re.search(r"\b(?:not|except|but\s+not|leave|keep)\s+(?:the\s+|any\s+|my\s+)?background\b", t)
    fg_excluded = re.search(r"\b(?:not|except|but\s+not|leave|keep)\s+(?:the\s+|my\s+)?(?:foreground|current|main|active)\b"
                            r"|\bnot\s+the\s+(?:task|one|job)\s+i(?:'m|\s+am)\s+waiting", t)
    if bg and not bg_excluded:
        return "background"
    if fg_excluded and not bg_excluded:
        return "background"
    return "foreground"


def classify(text: str) -> Optional[tuple[str, dict]]:
    """(intent, slots) for a question about JARVIS / control of its tasks, else None."""
    raw = " ".join((text or "").replace("’", "'").split())
    if not raw:
        return None
    t = _LEAD.sub("", raw.lower()).strip(" .!?")
    if _KNOWLEDGE.match(t):
        return None  # "how do I cancel a task?" - an explanation, not an action
    rest, negated = constraints(t)
    slots: dict = {"constraints": negated} if negated else {}
    has_task = re.search(rf"\b{_TASK}\b", rest) or re.search(r"\bwhat\s+you(?:'re|\s+are)\s+(?:doing|running|working\s+on)\b", rest)
    # "jarvis status please": the name may be the first word (stripped above as a wake word)
    about_jarvis = re.search(rf"\b{_JARVIS}\b", constraints(raw.lower())[0])

    # 1. cancel / stop a task (never the listener: "keep listening" is honoured by design)
    cancel = re.search(rf"\b{_CANCEL}\s+(?:(?:the|this|that|my|your|current|currently|running|active|ongoing|only|all|any|"
                       rf"of|whatever|everything|in|stuff|jobs?\s+in)\s+)*(?:{_TASK}\b|what\s+you(?:'re|\s+are)\s+doing|"
                       rf"background\b(?!\s+(?:window|app|tab|image|colou?r|music|process))|foreground\s+(?:task|job|work)|it\b)", rest) \
        or re.search(rf"\b(?:background|foreground)\s+{_TASK}\b.{{0,30}}\b{_CANCEL}\b", rest)
    if cancel \
            and not re.search(rf"\b{_CANCEL}\s+(?:the\s+|my\s+)?(?:music|song|video|audio|playback|timer|alarm|reminder|meeting|"
                              r"download|recording|dictation|screen\s+share)\b", rest):
        return "cancel_task", {**slots, "scope": _scope(rest), "keep_listening": True}

    # 2. resource usage
    if (re.search(r"\b(?:utili[sz]ation|resources?\s+(?:usage|use|used)|(?:memory|ram)\b(?:\s+\w+){0,2}?\s+(?:usage|use|used|load|consum\w*))\b", rest)
            or (re.search(r"\b(?:cpu|processor|gpu|vram|ram|resources?)\b", rest)
                and re.search(r"\b(?:usage|use|used|using|load|loaded|percent|how\s+(?:busy|hard)|busy|utili[sz]\w*|right\s+now|"
                              r"current(?:ly)?|live|consum\w*)\b|%", rest)
                # "how much RAM does this laptop have" asks for the size, not the load
                and not re.search(r"\b(?:have|has|installed|total|capacity|size|how\s+big|max(?:imum)?)\b", rest))) \
            and not re.search(r"\b(?:which|what)\s+(?:programs?|apps?|applications?|process(?:es)?)\b|\b(?:most|top)\s+(?:ram|memory|cpu)\b", rest):
        return "resource_usage", slots

    # 3. the previous command's outcome
    if re.search(rf"\b(?:previous|last|earlier|prior|preceding|that)\s+(?:\w+\s+)?{_TASK}\b", rest) \
            and re.search(r"\b(?:fail\w*|succe\w*|complet\w*|finish\w*|result\w*|outcome|happen\w*|went|go|status|error\w*|wrong|work\w*|"
                          r"done|skip\w*|broke\w*)\b", rest):
        return "previous_outcome", slots
    if re.fullmatch(r"(?:what|which\s+\w+)\s+(?:failed|went\s+wrong|broke)(?:\s+(?:just\s+now|last\s+time|earlier))?", rest):
        return "previous_outcome", slots

    # 5. which parts work / are down (needs a component word: "what are you working on" is about tasks)
    components = re.search(r"\b(?:parts?|components?|services?|subsystems?|modules?|features?)\b", rest)
    if components and (about_jarvis or re.search(r"\b(?:which|what|any|list|tell)\b", rest)) \
            and re.search(r"\b(?:unavailable|available|offline|online|down|broken|disabled|not\s+working|still\s+work\w*|can\s+(?:still\s+)?work|"
                          r"working|missing|degraded)\b", rest):
        return "jarvis_availability", slots

    # 4. what is running now / progress / stuck
    stuck = bool(re.search(r"\b(?:stuck|hung|hanging|frozen|freez\w*|not\s+responding|taking\s+(?:so\s+|too\s+)?long)\b", rest))
    running = re.search(r"\b(?:current(?:ly)?|now|running|executing|in\s+progress|active|going\s+on|progress|how\s+far|reached|"
                        r"which\s+step|what\s+step|still)\b", rest)
    if (has_task and (running or stuck)) \
            or re.search(r"\bwhat\s+are\s+you\s+(?:doing|working\s+on|busy\s+with|running)\b", rest) \
            or re.search(r"\b(?:is\s+)?(?:anything|something|any\s+task|any\s+job)\s+(?:stuck|running|still\s+running|hung|frozen|"
                         r"not\s+responding)\b", rest) \
            or re.search(r"\bwhat(?:'s|\s+is)\s+running\b", rest):
        return "task_status", {**slots, "stuck": stuck}

    # 6. overall health / status of JARVIS
    if re.search(r"\bself[\s-]?(?:check|test|diagnos\w*)\b", rest):
        return "system_diagnostics", slots
    own_health = re.search(r"\b(?:jarvis|you|your|yourself)(?:'s|\s+is|\s+are|'re)?\s+(?:\w+\s+){0,2}?(?:health\w*|status|diagnos\w*|"
                           r"working\s+(?:properly|fine|correctly))\b|\b(?:health|status)\s+(?:of|for)\s+(?:jarvis|you|yourself)\b|"
                           r"^(?:current\s+)?(?:jarvis\s+)?(?:health|status)(?:\s+(?:check|report|please))?$", rest)
    feels_ok = re.search(r"\b(?:you|jarvis)(?:'re|\s+are|\s+is|'s)?\s+(?:\w+\s+)?(?:ok|okay|fine|all\s+good|alright)\b|"
                         r"\beverything\s+(?:ok|okay|fine|all\s+right)\s+with\s+(?:you|jarvis)\b", rest)
    if (own_health or feels_ok or (about_jarvis and re.search(r"\bsystems?\s+check\b", rest))) \
            and not re.search(r"\bhow\s+are\s+you\b(?!\s+(?:running|working|doing\s+technically))", rest):
        return "system_diagnostics", slots
    return None


def match_introspection(text: str, request_id: str) -> Optional[RouteDecision]:
    hit = classify(text)
    if hit is None:
        return None
    intent, slots = hit
    return RouteDecision(request_id=request_id, lane=RouteLane.LANE_0, intent=intent, slots=slots, confidence=0.98,
                         source=RouteSource.EXACT, complexity=ComplexityLevel.SIMPLE, normalized_text=text.strip().lower(),
                         reason_code=ReasonCode.EXACT_PATTERN, candidate_count=1, routing_ms=0.0)
