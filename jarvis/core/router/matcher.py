from typing import Any
from jarvis.core.router.catalog import IntentCatalog, IntentDefinition
from jarvis.core.router.models import RouteDecision, RouteLane, RouteSource, ComplexityLevel, ReasonCode
from jarvis.core.router.slots import parse_slot_value

def match_patterns(
    routing_text: str,
    candidate_intents: list[str],
    catalog: IntentCatalog,
    request_id: str,
) -> RouteDecision | None:
    """Evaluates compiled regex patterns for candidate intents only."""
    text_clean = routing_text.strip()
    if not text_clean:
        return None

    for intent_name in candidate_intents:
        defn = catalog.intents.get(intent_name)
        if not defn or not defn.lane0_enabled:
            continue

        for pattern in defn.compiled_patterns:
            match = pattern.match(text_clean)
            if match:
                raw_dict = match.groupdict()
                parsed_slots: dict[str, Any] = {}
                missing_slots: list[str] = []

                for req in defn.required_slots:
                    raw_val = raw_dict.get(req)
                    parsed_val = parse_slot_value(req, raw_val) if raw_val is not None else None
                    if parsed_val is None:
                        missing_slots.append(req)
                    else:
                        parsed_slots[req] = parsed_val

                for opt in defn.optional_slots:
                    if opt in raw_dict and raw_dict[opt] is not None:
                        parsed_slots[opt] = parse_slot_value(opt, raw_dict[opt])

                # Any extra matched groups (e.g. minutes converted to seconds)
                if "minutes" in raw_dict and raw_dict["minutes"] is not None and "seconds" not in parsed_slots:
                    mins = parse_slot_value("minutes", raw_dict["minutes"])
                    if mins is not None:
                        parsed_slots["seconds"] = int(mins) * 60
                        if "seconds" in missing_slots:
                            missing_slots.remove("seconds")

                if missing_slots:
                    return RouteDecision(
                        request_id=request_id,
                        lane=RouteLane.CLARIFY,
                        intent=defn.name,
                        slots=parsed_slots,
                        confidence=0.5,
                        source=RouteSource.GRAMMAR,
                        complexity=ComplexityLevel.SIMPLE,
                        risk=defn.risk,
                        missing_slots=missing_slots,
                        clarification=f"Please specify the required {missing_slots[0]} for {defn.name.replace('_', ' ')}.",
                        normalized_text=routing_text,
                        reason_code=ReasonCode.MISSING_REQUIRED_SLOT,
                        candidate_count=len(candidate_intents),
                    )

                return RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.LANE_0,
                    intent=defn.name,
                    slots=parsed_slots,
                    confidence=1.0,
                    source=RouteSource.EXACT if not parsed_slots else RouteSource.GRAMMAR,
                    complexity=ComplexityLevel.SIMPLE,
                    risk=defn.risk,
                    missing_slots=[],
                    normalized_text=routing_text,
                    reason_code=ReasonCode.EXACT_PATTERN,
                    candidate_count=len(candidate_intents),
                )

    return None
