from dataclasses import dataclass
from rapidfuzz import fuzz
from jarvis.core.router.catalog import IntentCatalog, IntentDefinition
from jarvis.core.router.models import RouteDecision, RouteLane, RouteSource, ComplexityLevel, ReasonCode
from jarvis.core.router.slots import parse_slot_value

@dataclass
class FuzzyCandidate:
    intent_name: str
    example: str
    score: float

def match_fuzzy(
    routing_text: str,
    candidate_intents: list[str],
    catalog: IntentCatalog,
    request_id: str,
) -> RouteDecision | None:
    """Performs RapidFuzz token matching against pre-filtered candidate examples."""
    text_clean = routing_text.strip()
    if not text_clean:
        return None

    scores: list[FuzzyCandidate] = []

    for intent_name in candidate_intents:
        defn = catalog.intents.get(intent_name)
        if not defn or not defn.fuzzy_allowed or not defn.lane0_enabled:
            continue

        for ex in defn.examples:
            score = fuzz.ratio(text_clean, ex)
            if score >= 50.0:  # Base cutoff
                scores.append(FuzzyCandidate(intent_name=defn.name, example=ex, score=score))

    if not scores:
        return None

    # Sort descending by score
    scores.sort(key=lambda c: c.score, reverse=True)
    top1 = scores[0]

    # Find top2 from a DIFFERENT intent
    top2 = None
    for cand in scores[1:]:
        if cand.intent_name != top1.intent_name:
            top2 = cand
            break

    defn = catalog.intents[top1.intent_name]
    margin = (top1.score - top2.score) if top2 else 100.0

    # Ambiguity check
    if top2 and margin < defn.ambiguity_margin and top1.score < 95.0:
        # Ambiguous between top two intents -> send to Lane 1 or Clarify
        return None

    # Threshold check
    if top1.score >= defn.fuzzy_threshold and margin >= defn.ambiguity_margin:
        # Attempt slot extraction from routing text
        slots = {}
        for pattern in defn.compiled_patterns:
            m = pattern.match(text_clean)
            if m:
                for k, v in m.groupdict().items():
                    if v is not None:
                        slots[k] = parse_slot_value(k, v)
                break

        # Fallback slot extraction for app opening / directory listing
        if defn.name == "open_app" and "name" not in slots:
            # E.g. "bro bring chrome up for me" -> extract "chrome"
            for token in text_clean.split():
                if token in ("chrome", "vscode", "notepad", "calculator", "terminal", "cmd", "explorer"):
                    slots["name"] = token
                    break

        confidence = round(top1.score / 100.0, 3)
        return RouteDecision(
            request_id=request_id,
            lane=RouteLane.LANE_0,
            intent=defn.name,
            slots=slots,
            confidence=confidence,
            source=RouteSource.FUZZY,
            complexity=ComplexityLevel.SIMPLE,
            risk=defn.risk,
            missing_slots=[],
            normalized_text=routing_text,
            reason_code=ReasonCode.FUZZY_HIGH_CONFIDENCE,
            candidate_count=len(candidate_intents),
        )

    return None
