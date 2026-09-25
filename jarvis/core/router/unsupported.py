"""Unsupported external domain recognition for JARVIS EDGE."""

from __future__ import annotations

import re
from jarvis.core.router.models import (
    RouteDecision,
    RouteLane,
    RouteSource,
    ComplexityLevel,
    ReasonCode,
)

UNSUPPORTED_DOMAINS_PATTERNS = [
    # 1. Smart home & physical IoT appliances
    re.compile(r"\b(?:kitchen|bedroom|living room|hallway|garden|front door|garage)\s+(?:lights?|lamp|thermostat|blinds?|deadbolt|sprinklers?|door)\b", re.I),
    re.compile(r"\b(?:dishwasher|microwave|oven|refrigerator|fridge|coffee machine|espresso|pet feeder|vacuum cleaner|robotic vacuum|lawnmower|kettle|air conditioner)\b", re.I),
    re.compile(r"\b(?:turn (?:on|off)|start|dim|warm up|preheat|boil|mow|dispense|adjust)\s+(?:the\s+)?(?:kitchen|bedroom|living room|garden|garage|front door|dishwasher|microwave|oven|coffee|espresso|pet feeder|vacuum|lawnmower|kettle|thermostat|sprinklers?|blinds?)\b", re.I),
    re.compile(r"\b(?:led ceiling strip|motorized window blinds)\b", re.I),
    re.compile(r"\b(?:deadbolt|smart lock)\b", re.I),

    # 2. Travel booking & Ride hailing
    re.compile(r"\b(?:flight|flights|airline|airport shuttle|train ticket|eurostar|sleeper train|rental car|hotel room|uber|lyft|auto-rickshaw|taxi to|cab to|charging station)\b", re.I),
    re.compile(r"\b(?:book|reserve|hail|schedule)\s+(?:a |an |two )?(?:direct )?(?:flight|ticket|cab|taxi|uber|lyft|shuttle|hotel|rental car|train|auto-rickshaw|room in|sleeper|parking spot|table|private dining|tennis court|pet grooming|piano tuning)\b", re.I),

    # 3. Food delivery & Dining reservations
    re.compile(r"\b(?:pizzas?|pepperoni|garlic bread|domino'?s|butter chicken|naan|zomato|instacart|doordash|starbucks|macchiatos?|donuts?|krispy kreme|takeout|dining booth|bistro|table for \w+|restaurant downtown|sushi bar)\b", re.I),
    re.compile(r"\b(?:order|reserve)\s+(?:a |two |some )?(?:large |box of )?(?:pizzas?|table|groceries|macchiatos?|donuts?|takeout|food|dinner|lunch|breakfast|cake delivery|flowers|dry cleaning|prescription|contact lenses|birthday greeting|propane tank|embroidery)\b", re.I),
    re.compile(r"\b(?:cake delivery|flowers delivery|grocery delivery)\b", re.I),

    # 4. Financial trading, banking, loans, crypto
    re.compile(r"\b(?:shares? of|stock on|nasdaq|cryptocurrency|crypto\b|bitcoin|ether\b|ethereum|solana|tokens in|checking account|savings account|credit score|personal loan|property tax|limit buy order|lottery)\b", re.I),
    re.compile(r"\b(?:buy|sell|stake|transfer|exchange|apply for|pay my)\s+(?:\d+\s+)?(?:shares?|stocks?|ether|bitcoin|solana|dollars|euros|loan|tax bill|scratch cards?|lottery|monthly subway)\b", re.I),
    re.compile(r"\bstart mining bitcoin\b", re.I),
    re.compile(r"\b(?:exchange\s+[\w\s]{1,30}\s+(?:dollars|euros|currency|usd)|currency exchange)\b", re.I),

    # 5. Clinical medical services
    re.compile(r"\b(?:dental cleaning|prescription|medication at the pharmacy|blood glucose|telemedicine|doctor|eye checkup|blood test|pathology lab|heart rate variability|health insurance|walk-in clinic|hospital bills?|contact lenses)\b", re.I),

    # 6. Physical manufacturing, electronics, heavy machinery
    re.compile(r"\b(?:3d print|laser cut|robotic arm|cnc milling|solder (?:the )?surface|circuit breaker|transceiver|custom firmware onto|ikea|telescope)\b", re.I),

    # 7. Supernatural, physics violations, impossible tasks
    re.compile(r"\b(?:spell\b|teleport|winning lottery|read the thoughts|reverse time|materialize|telepathically|gold bar|speed of light|dolphin whistles)\b", re.I),

    # 8. Physical services & tickets
    re.compile(r"\b(?:movie (?:show|tickets?)|imax|cinema|concert tickets?)\b", re.I),
    re.compile(r"\b(?:subway (?:transit )?pass|transit pass|bus pass|metro pass)\b", re.I),
    re.compile(r"\b(?:greeting cards?)\b", re.I),
    re.compile(r"\b(?:dry cleaning|oil change|plumber|piano tuning|pet grooming|propane tank|scuba diving|karaoke room|notary public|embroidery|hot air balloon|physical real-world task)\b", re.I),
]


# Organising, remembering or messaging ABOUT a real-world thing is fully supported
# ("remind me to call the doctor", "add call the plumber to my to-do list", "tell mom the cab is here").
_PERSONAL_FRAME = re.compile(
    r"^(?:please\s+)?(?:remind me|set (?:a |an )?(?:reminder|alarm|timer)|add .+ to (?:my |the )?(?:to-?\s?do|todo|task|shopping|checklist)"
    r"|put .+ on (?:my |the )?(?:to-?\s?do|todo|task|shopping)|mark .+ (?:as )?(?:done|complete)|remember that|note that|take a note|make a note"
    r"|(?:tell|text|message|whatsapp|msg|ping|inform|ask|reply to|remind)\s+(?!me\b)[a-z]+\b.*\b(?:that|saying|to|about)\b"
    r"|(?:email|mail)\s+[a-z]+)", re.I)


def check_unsupported_external(routing_text: str, request_id: str) -> RouteDecision | None:
    """Checks if the request targets external physical devices or unsupported services."""
    cleaned = routing_text.strip()
    if _PERSONAL_FRAME.match(cleaned):
        return None
    for pattern in UNSUPPORTED_DOMAINS_PATTERNS:
        if pattern.search(cleaned):
            return RouteDecision(
                request_id=request_id,
                lane=RouteLane.CLARIFY,
                intent="unknown",
                slots={},
                confidence=0.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                clarification="This request involves physical appliances, external bookings, financial transactions, or unsupported physical services outside desktop control.",
                normalized_text=routing_text,
                reason_code=ReasonCode.UNKNOWN_INTENT,
                candidate_count=0,
            )
    return None
