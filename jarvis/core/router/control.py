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
})

def match_control(text: str, request_id: str) -> RouteDecision | None:
    cleaned = " ".join(text.strip().casefold().split())
    if cleaned in CONTROL_PHRASES:
        intent = "stop_task" if "task" in cleaned else "cancel_task"
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
