import re

from jarvis.core.router.models import RouteDecision, RouteLane, RouteSource, ComplexityLevel, ReasonCode

CONTROL_PHRASES = frozenset({
    "stop",
    "cancel",
    "cancel that",
    "stop everything",
    "never mind",
    "nevermind",
    "abort",
    "stop task",
    "cancel task",
    "stop now",
    "cancel now",
    "stop speaking",
    "stop talking",
    "stop voice",
    "stop audio",
    "stop speech",
    "be quiet",
    "silence",
    "shut up",
    "stop the voice",
    "stop your voice",
    "stop the speech",
    "stop reading",
    "stop reading that",
    "quiet",
    "quiet please",
    "enough",
    "that's enough",
    "okay that's enough",
    "ok that's enough",
    "hush",
})

def match_control(text: str, request_id: str) -> RouteDecision | None:
    from jarvis.core.router.normalize import normalize_text
    _, cleaned = normalize_text(text)
    cleaned = cleaned.strip().lower()

    # 1. Confirm / approve action
    if cleaned in ("confirm", "yes", "proceed", "approve", "do it", "sure", "go ahead", "yes go ahead", "yes do it", "yes please",
                   "ok do it", "okay do it", "sure go ahead", "confirmed", "yep", "yeah", "yeah do it", "go for it", "yes proceed",
                   "send it", "yes send it", "ok send it") \
            or cleaned.startswith(("confirm ticket", "approve ticket")):
        parts = cleaned.split()
        ticket_id = parts[2] if len(parts) >= 3 else ""
        return RouteDecision(
            request_id=request_id,
            lane=RouteLane.CONTROL,
            intent="confirm_ticket",
            slots={"ticket_id": ticket_id},
            confidence=1.0,
            source=RouteSource.CONTROL,
            complexity=ComplexityLevel.SIMPLE,
            normalized_text=cleaned,
            reason_code=ReasonCode.CONTROL_COMMAND,
            candidate_count=1,
            routing_ms=0.0,
        )

    # 2. Reject / cancel action
    if cleaned in ("reject", "no", "deny", "don't do it", "dont do it", "no don't", "no dont", "don't", "no thanks", "nope",
                   "no no", "don't send it", "dont send it", "no don't send", "don't do that") \
            or cleaned.startswith(("reject ticket", "deny ticket")):
        parts = cleaned.split()
        ticket_id = parts[2] if len(parts) >= 3 else ""
        return RouteDecision(
            request_id=request_id,
            lane=RouteLane.CONTROL,
            intent="reject_ticket",
            slots={"ticket_id": ticket_id},
            confidence=1.0,
            source=RouteSource.CONTROL,
            complexity=ComplexityLevel.SIMPLE,
            normalized_text=cleaned,
            reason_code=ReasonCode.CONTROL_COMMAND,
            candidate_count=1,
            routing_ms=0.0,
        )

    # 2b. About JARVIS's own voice: "say that again", "speak slower", "talk louder", "continue reading", "stop talking"
    from jarvis.core.audio.speech_control import classify as speech_action
    voice = speech_action(cleaned, speaking=False)
    if voice == "stop":
        return RouteDecision(request_id=request_id, lane=RouteLane.CONTROL, intent="stop_speaking", confidence=1.0,
                             source=RouteSource.CONTROL, complexity=ComplexityLevel.SIMPLE, normalized_text=cleaned,
                             reason_code=ReasonCode.CONTROL_COMMAND, candidate_count=1, routing_ms=0.0)
    if voice is not None:
        return RouteDecision(request_id=request_id, lane=RouteLane.CONTROL, intent="speech_control", slots={"action": voice},
                             confidence=1.0, source=RouteSource.CONTROL, complexity=ComplexityLevel.SIMPLE,
                             normalized_text=cleaned, reason_code=ReasonCode.CONTROL_COMMAND, candidate_count=1, routing_ms=0.0)

    # 3. Stop speaking / stop audio / cancel / pause / resume active tasks
    _stop = re.compile(r"(?:ok(?:ay)?\s+|alright\s+)?(?:that'?s\s+)?enough(?:\s+(?:talking|speaking|reading|now))?"
                       r"|(?:you\s+can\s+|please\s+|just\s+)?stop\s+(?:reading|talking|speaking)(?:\s+(?:now|please|it|that|out\s+loud))*"
                       r"|(?:ok(?:ay)?\s+)?(?:shh+|shush|hush)(?:\s+(?:now|please))?|pesa+dh?[ae]|pesa+the|summa\s+iru|stop")
    clauses = [c.strip(" .!") for c in cleaned.split(",") if c.strip(" .!")]
    if len(clauses) > 1 and all(_stop.fullmatch(c) for c in clauses) or cleaned in ("pesadha", "pesadhe", "pesaathe", "summa iru"):
        return RouteDecision(request_id=request_id, lane=RouteLane.CONTROL, intent="stop_speaking", confidence=1.0,
                             source=RouteSource.CONTROL, complexity=ComplexityLevel.SIMPLE, normalized_text=cleaned,
                             reason_code=ReasonCode.CONTROL_COMMAND, candidate_count=1, routing_ms=0.0)
    is_control = (
        cleaned in CONTROL_PHRASES
        or cleaned.startswith(("stop speaking", "stop talking", "be quiet", "cancel current", "stop current", "pause task", "resume task", "cancel task", "stop task"))
        or bool(re.fullmatch(r"(?:ok(?:ay)?\s+|alright\s+)?(?:that'?s\s+)?enough\s+(?:talking|speaking|reading|now)"
                             r"|(?:you\s+can\s+|please\s+|just\s+)?stop\s+(?:reading|talking|speaking)(?:\s+(?:now|please|it|that|out\s+loud))*"
                             r"|(?:ok(?:ay)?\s+)?(?:shh+|shush|hush)(?:\s+(?:now|please))?", cleaned))
        or (cleaned in ("pause", "resume") and not cleaned.startswith(("pause music", "resume music")))
    )
    if is_control:
        if any(w in cleaned for w in ("speaking", "talking", "voice", "audio", "quiet", "silence", "shut up", "speech", "reading",
                                      "enough", "hush", "shh", "shush")):
            intent = "stop_speaking"
        elif "pause" in cleaned:
            intent = "pause_task"
        elif "resume" in cleaned:
            intent = "resume_task"
        elif "task" in cleaned or "current" in cleaned:
            intent = "cancel_task"
        else:
            intent = "cancel_task"
        return RouteDecision(
            request_id=request_id,
            lane=RouteLane.CONTROL,
            intent=intent,
            slots={},
            confidence=1.0,
            source=RouteSource.CONTROL,
            complexity=ComplexityLevel.SIMPLE,
            normalized_text=cleaned,
            reason_code=ReasonCode.CONTROL_COMMAND,
            candidate_count=1,
            routing_ms=0.0,
        )
    return None
