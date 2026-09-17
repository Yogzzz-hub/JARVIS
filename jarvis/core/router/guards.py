import re
from typing import Any

# Negative action prefixes
NEGATION_STARTS = (
    "don't",
    "dont",
    "do not",
    "never",
    "not now",
    "without",
    "avoid",
    "stop opening",
    "stop launching",
    "stop starting",
)

# Question / informational prefixes that ask questions rather than issuing commands
INFORMATIONAL_PREFIXES = (
    "why did",
    "why is",
    "why does",
    "why are",
    "why",
    "how do i",
    "how can i",
    "how to",
    "how does",
    "how is",
    "how",
    "what is",
    "what does",
    "what are",
    "tell me what",
    "tell me about",
    "explain",
    "describe",
)

def check_negation(text: str) -> tuple[bool, list[dict[str, Any]]]:
    """Returns (is_negated_command, constraints).

    If is_negated_command is True, the primary command is negated and must NOT execute.
    """
    lowered = text.strip().casefold()
    constraints = []

    # Check for full negation (e.g. "don't open chrome", "do not start vscode")
    for neg in NEGATION_STARTS:
        if lowered.startswith(neg + " ") or lowered == neg:
            rest = lowered[len(neg):].strip()
            action_match = re.match(r"^(?:open|launch|start|run|delete|close|shutdown|set)\s+(.+)$", rest)
            target = action_match.group(1) if action_match else rest
            constraints.append({"type": "negative_action", "target": target})
            return True, constraints

    # Check for embedded negation clause (e.g. "open chrome but don't close edge")
    if " but don't " in lowered or " and don't " in lowered or " without " in lowered or " except " in lowered:
        parts = re.split(r"\b(?:but\s+don't|and\s+don't|without|except)\b", lowered)
        if len(parts) > 1:
            clause = parts[1].strip()
            constraints.append({"type": "negative_action", "target": clause})

    return False, constraints

def is_informational_or_question(original_text: str, routing_text: str) -> bool:
    """Detects queries, informational requests, or capability questions that must NOT trigger actions.

    Example:
    - 'Can Chrome open PDFs?' -> True (informational)
    - 'How do I open Chrome?' -> True (informational)
    - 'Is Chrome open?' -> True (query state)
    - 'Is Chrome installed?' -> True (query state)
    - 'Why did Chrome crash?' -> True (informational)
    - 'Open Chrome' -> False (command)
    - 'Can you open Chrome?' -> False (normalize strips 'can you', leaving 'open chrome' command)
    """
    orig_clean = original_text.strip().casefold()
    routing_clean = routing_text.strip().casefold()

    # Direct question prefixes
    for prefix in INFORMATIONAL_PREFIXES:
        if orig_clean.startswith(prefix + " ") or routing_clean.startswith(prefix + " "):
            return True

    # State query checks: "is <app> open", "is <app> installed", "is <app> running"
    if re.match(r"^is\s+[\w\s]+\s+(?:open|installed|running|active|closed)\??$", orig_clean):
        return True

    # App capability questions: "can <app> <verb> ... ?" (e.g. "can chrome open pdfs", "can whatsapp send pdf")
    if re.match(r"^can\s+(?:chrome|vscode|notepad|calculator|whatsapp|word|excel|firefox|edge)\s+\w+", orig_clean):
        return True

    # General questions ending with '?' that do not begin with an imperative command
    if orig_clean.endswith("?") and not re.match(r"^(?:open|start|launch|set|turn|list|take|show|get|mute|unmute)\b", routing_clean):
        return True

    return False
