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

                # Guard: Do not let open_app swallow multi-action compound sentences, action verbs, or pronouns
                if defn.name == "open_app" and "name" in raw_dict:
                    val = str(raw_dict["name"]).lower().strip()
                    if val in ("it", "that", "this", "them", "window", "this window", "active window"):
                        continue
                    if any(sep in val for sep in (",", ";", " and ", " and then ", " then ", " play ", " message ", " send ", " check ", " search ", " find ")):
                        continue

                # Guard: Do not let find_file swallow news, web, youtube, duplicate checking, app location, or UI element queries
                if defn.name == "find_file" and "query" in raw_dict:
                    val = str(raw_dict["query"]).lower().strip()
                    if any(kw in val for kw in ("news", "on youtube", "in youtube", "google", "web", "located", "installed", "where is", "is installed", "duplicate", "duplicates", "button", "on screen", "on the screen")):
                        continue

                # Guard: Do not let search_web swallow system, hardware, rss, or device queries
                if defn.name == "search_web" and "query" in raw_dict:
                    val = str(raw_dict["query"]).lower().strip()
                    if any(kw in val for kw in ("rss", "feed", "phone", "installed", "status", "mic", "microphone", "diagnostics", "active window")):
                        continue

                # Guard: Do not let list_directory swallow UI, status, info, or date commands
                if defn.name == "list_directory" and "path" in raw_dict:
                    val = str(raw_dict["path"]).lower().strip()
                    if (
                        val in ("desktop", "the desktop", "dashboard", "the dashboard", "phone", "my phone")
                        or any(w in val for w in ("info", "status", "diagnostics", "weather", "news", "specs", "system", "date", "time"))
                    ):
                        continue

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

                if defn.name == "read_whatsapp_messages" and "filter" not in parsed_slots:
                    if "unread" in text_clean:
                        parsed_slots["filter"] = "unread"
                    elif "urgent" in text_clean:
                        parsed_slots["filter"] = "urgent"
                    elif "all" in text_clean:
                        parsed_slots["filter"] = "all"
                    else:
                        parsed_slots["filter"] = "needs_reply"

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
