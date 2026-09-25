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
})

def match_control(text: str, request_id: str) -> RouteDecision | None:
    from jarvis.core.router.normalize import normalize_text
    _, cleaned = normalize_text(text)
    cleaned = cleaned.strip().lower()

    # 1. Confirm / approve action
    if cleaned in ("confirm", "yes", "proceed", "approve", "do it", "sure") or cleaned.startswith(("confirm ticket", "approve ticket")):
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
    if cleaned in ("reject", "no", "deny", "don't do it", "dont do it") or cleaned.startswith(("reject ticket", "deny ticket")):
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

    # 3. Stop speaking / stop audio / cancel / pause / resume active tasks
    is_control = (
        cleaned in CONTROL_PHRASES
        or cleaned.startswith(("stop speaking", "stop talking", "be quiet", "cancel current", "stop current", "pause task", "resume task", "cancel task", "stop task"))
        or (cleaned in ("pause", "resume") and not cleaned.startswith(("pause music", "resume music")))
    )
    if is_control:
        if any(w in cleaned for w in ("speaking", "talking", "voice", "audio", "quiet", "silence", "shut up", "speech")):
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
