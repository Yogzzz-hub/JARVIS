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
    re.compile(r"\b(?:pizzas?|pepperoni|garlic bread|domino'?s|butter chicken|butter naan|garlic naan|zomato|instacart|doordash|starbucks|macchiatos?|donuts?|krispy kreme|takeout|dining booth|bistro|table for \w+|restaurant downtown|sushi bar)\b", re.I),
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
    r"|remember (?:my|i|i'm|i've|our|the|where)\b|note down|write down|don'?t forget|keep in mind"
    r"|(?:tell|text|message|whatsapp|msg|ping|inform|ask|reply to|remind)\s+(?!me\b)[a-z]+\b.*\b(?:that|saying|to|about)\b"
    r"|(?:email|mail)\s+[a-z]+)", re.I)


# Working with information ABOUT a real-world thing on this PC is supported too: "find my flight ticket" (a document),
# "go to zomato.com" (a website), "search the web for flights to delhi". Only clearly PC objects count - a clinic, a
# restaurant, a credit score or a delivery is still the real-world thing itself.
_DOC_NOUNS = (r"ticket|tickets|receipt|receipts|statement|statements|invoice|invoices|report|reports|policy|slip|certificate|"
              r"itinerary|confirmation|bill|bills|prescription\s+(?:pdf|file|scan)|document|documents|file|files|pdf|pdfs|scan|photo")
_PC_OBJECT = re.compile(rf"^(?:please\s+)?(?:find|locate|open|show(?:\s+me)?|where(?:'s|\s+is|\s+are)|dig\s+(?:out|up)|summari[sz]e|"
                        rf"read|delete|move|copy|rename|send|share|print|attach)\s+(?:me\s+)?(?:my|the|this|that)\s+(?:\w+\s+){{0,3}}"
                        rf"(?:{_DOC_NOUNS})\b"
                        rf"|\b[\w-]+\.(?:com|in|org|net|io|co|dev|ai|edu|gov)\b"
                        rf"|^(?:search|look\s+up|google)\s+(?:the\s+web\s+|online\s+|google\s+)?(?:for\s+)?(?!.*\b(?:book|order|reserve|buy|pay)\b)", re.I)
_REAL_WORLD_ACT = re.compile(r"\b(?:book|order|reserve|buy|purchase|pay|hail|rent|deliver|delivery|transfer\s+money|send\s+money)\b", re.I)
_SHOP = re.compile(r"^(?:please\s+)?(?:buy|order|purchase)\s+(?:me\s+)?(?:a\s+|an\s+|some\s+|this\s+|that\s+)?(?P<x>.+?)\s+(?:on|from)\s+"
                   r"(?P<s>amazon|flipkart|myntra|ebay|croma)(?:\s+now)?$", re.I)
_IMPOSSIBLE = next(p for p in UNSUPPORTED_DOMAINS_PATTERNS if "teleport" in p.pattern)   # impossible: never "a PC object"


def check_unsupported_external(routing_text: str, request_id: str) -> RouteDecision | None:
    """Checks if the request targets external physical devices or unsupported services."""
    cleaned = routing_text.strip()
    if _PERSONAL_FRAME.match(cleaned):
        return None
    shop = _SHOP.match(cleaned)
    if shop:
        return RouteDecision(
            request_id=request_id, lane=RouteLane.CLARIFY, intent="unknown", slots={"shop": shop.group("s").lower()},
            confidence=0.0, source=RouteSource.EXACT, complexity=ComplexityLevel.SIMPLE,
            clarification=f"I don't buy things or pay for you. Want me to search {shop.group('s').title()} for "
                          f"{shop.group('x')} so you can check it and buy it yourself?",
            normalized_text=routing_text, reason_code=ReasonCode.UNKNOWN_INTENT, candidate_count=0)
    if not _IMPOSSIBLE.search(cleaned) and not _REAL_WORLD_ACT.search(cleaned) and _PC_OBJECT.search(cleaned):
        return None
    # the words of a message are the message ("tell arun I'll bring naan"), not a request to JARVIS
    cleaned = re.split(r"\s+(?:saying|that says|to say|that|nu)\s+", cleaned, maxsplit=1)[0] \
        if re.match(r"^(?:tell|text|message|msg|send|whatsapp|ask|let|reply|inform|remind)\b", cleaned) else cleaned
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
