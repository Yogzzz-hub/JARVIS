import re
from jarvis.core.router.catalog import IntentCatalog
from jarvis.core.router.models import (
    RouteDecision,
    RouteLane,
    RouteSource,
    ComplexityLevel,
    ReasonCode,
    SubCommand,
)
from jarvis.core.router.slots import parse_app_name

COMPLEX_PATTERNS = (
    re.compile(r"\b(?:prepare|organize)\s+(?:everything|tomorrow|the\s+lab)", re.I),
    re.compile(r"\bfind\s+.+\s+(?:and|then)\s+(?:email|send|put|move|copy)\b", re.I),
    re.compile(r"\b(?:email|send)\s+.+\s+to\s+\w+\b", re.I),
    re.compile(r"\bcheck\s+.+\s+(?:then|after\s+that)\b", re.I),
    re.compile(r"\bafter\s+that\b", re.I),
    re.compile(r"\b(?:download|install)\s+.+\s+and\b", re.I),
    re.compile(r"\bbased\s+on\b", re.I),
    re.compile(r"\bcompare\s+.+\s+and\b", re.I),
)

def check_deterministic_compound(
    routing_text: str,
    catalog: IntentCatalog,
    request_id: str,
) -> RouteDecision | None:
    """Detects safe, bounded deterministic compound commands (max 3 subcommands).

    Examples:
    - 'open chrome and calculator'
    - 'open vscode and terminal'
    - 'open notepad, chrome and calculator'
    """
    cleaned = routing_text.strip()
    match = re.match(r"^(?:open|launch|start)\s+(.+)$", cleaned, re.I)
    if not match:
        return None

    remainder = match.group(1).strip()
    # Split by ' and ' or ','
    parts = re.split(r"\s+and\s+|,\s*", remainder)
    parts = [p.strip() for p in parts if p.strip()]

    # Bounded: 2 to 3 subcommands only
    if 2 <= len(parts) <= 3:
        subcommands = []
        for part in parts:
            app_name = parse_app_name(part)
            # Ensure each part looks like a single application name, not a complex clause
            if len(app_name.split()) > 2 or any(w in app_name for w in ("then", "after", "send", "email", "if")):
                return None
            subcommands.append(SubCommand(intent="open_app", tool="open_app", arguments={"name": app_name}))

        return RouteDecision(
            request_id=request_id,
            lane=RouteLane.LANE_0,
            intent="open_app",
            slots={"apps": [sub.arguments["name"] for sub in subcommands]},
            confidence=1.0,
            source=RouteSource.EXACT,
            complexity=ComplexityLevel.COMPOUND,
            risk="REVERSIBLE",
            missing_slots=[],
            normalized_text=routing_text,
            reason_code=ReasonCode.COMPOUND_COMMAND,
            subcommands=subcommands,
            candidate_count=1,
        )

    return None

def check_complexity_gate(
    routing_text: str,
    request_id: str,
) -> RouteDecision | None:
    """Evaluates whether the request requires the Phase-4 planner (Lane 2)."""
    text = routing_text.strip()

    for pattern in COMPLEX_PATTERNS:
        if pattern.search(text):
            return RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_2,
                intent=None,
                slots={},
                confidence=0.95,
                source=RouteSource.COMPLEXITY_GATE,
                complexity=ComplexityLevel.COMPLEX,
                needs_planner=True,
                normalized_text=routing_text,
                reason_code=ReasonCode.MULTI_STEP,
                candidate_count=0,
            )

    return None
