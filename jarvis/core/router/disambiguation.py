from typing import Any
from jarvis.core.router.models import (
    RouteDecision,
    RouteLane,
    RouteSource,
    ComplexityLevel,
    ReasonCode,
)

AMBIGUOUS_APPS = {
    "studio": ("Android Studio", "Visual Studio", "Visual Studio Code"),
    "office": ("Microsoft Word", "Microsoft Excel", "Microsoft PowerPoint"),
}

def disambiguate_app(
    app_name: str,
    resolver: Any,
    request_id: str,
    normalized_text: str,
) -> RouteDecision | None:
    """Checks if an application name is ambiguous and requires user clarification."""
    lowered = app_name.strip().casefold()

    if lowered in AMBIGUOUS_APPS:
        choices = AMBIGUOUS_APPS[lowered]
        choices_str = ", ".join(choices[:-1]) + f", or {choices[-1]}"
        return RouteDecision(
            request_id=request_id,
            lane=RouteLane.CLARIFY,
            intent="open_app",
            slots={"raw_app": app_name, "candidates": list(choices)},
            confidence=0.5,
            source=RouteSource.EXACT,
            complexity=ComplexityLevel.SIMPLE,
            clarification=f"Which one do you mean: {choices_str}?",
            normalized_text=normalized_text,
            reason_code=ReasonCode.LOW_CONFIDENCE,
            candidate_count=len(choices),
        )

    # Check resolver cache if available
    if resolver and hasattr(resolver, "cache") and isinstance(resolver.cache, dict):
        matching = [
            k for k in resolver.cache.keys()
            if lowered in k or k in lowered
        ]
        if len(matching) > 1 and lowered not in resolver.cache:
            choices_str = ", ".join(matching[:3])
            return RouteDecision(
                request_id=request_id,
                lane=RouteLane.CLARIFY,
                intent="open_app",
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
