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
    "actually don't",
    "actually do not",
    "please don't",
    "please do not",
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
    "compare",
    "contrast",
)

def check_negation(text: str) -> tuple[bool, list[dict[str, Any]]]:
    """Returns (is_negated_command, constraints).

    If is_negated_command is True, the primary command is negated and must NOT execute.
    If positive_override constraint is present, the user negated one action but explicitly commanded another.
    """
    lowered = text.strip().casefold()
    constraints = []

    # Check "don't X, do Y" or "don't X, open Y instead"
    m_split = re.match(r"^(?:don't|do not|never)\s+([^,]+),\s*(?:instead\s+)?(.+)$", lowered)
    if m_split:
        negated = m_split.group(1).strip()
        positive = m_split.group(2).strip()
        positive = re.sub(r"\s+instead$", "", positive)
        constraints.append({"type": "negative_action", "target": negated})
        constraints.append({"type": "positive_override", "target": positive})
        return False, constraints

    # Check "do Y, not X" or "do Y instead of X"
    m_override = re.match(r"^(.+?)(?:,\s*not\s+|\s+instead\s+of\s+)(.+)$", lowered)
    if m_override:
        positive = m_override.group(1).strip()
        negated = m_override.group(2).strip()
        constraints.append({"type": "negative_action", "target": negated})
        constraints.append({"type": "positive_override", "target": positive})
        return False, constraints

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

    # Registered read-only capability queries must stay on the deterministic path
    if re.fullmatch(
        r"(?:what(?:'s| is| are) (?:the )?(?:current )?time(?: and date)?|what time is it|"
        r"what(?:'s| is) (?:the )?(?:current )?volume|"
        r"what(?:'s| is) (?:today'?s? |the )?date.*|what date is it.*|what day is it.*|today'?s? date.*|"
        r"what(?:'s| is) (?:the )?(?:jarvis |system |backend )?status.*|"
        r"what(?:'s| is| are) (?:the )?(?:latest |top )?news.*|search news.*|today(?:'s)? news.*|"
        r"what(?: are)?(?: the)? (?:unread |recent )?messages?.*|who messaged me.*|any(?: urgent| unread)? messages?.*|"
        r"what(?:'s| is| are)(?: the)? (?:unread |recent )?whatsapp.*|"
        r"(?:how much )?(?:memory|ram)(?: is)? (?:currently )?(?:available|free|used)(?: on this pc)?|"
        r"(?:is )?(?:my )?(?:android )?phone (?:connected|linked|reachable).*|"
        r"describe (?:what'?s? )?(?:on )?(?:my )?screen.*|what(?:'s| is)? on (?:my )?screen.*|"
        r"what (?:app|application|window) is (?:currently )?(?:visible|open|active).*|"
        r"(?:can i |could i |let me )?(?:see|view|show|check|look at)\s+(?:my\s+|the\s+)?(?:downloads|desktop|documents|pictures|videos|files|folder|directory).*|"
        r"(?:explain|diagnose) (?:visible |selected |current |this |the )?error.*|"
        r"explain (?:the )?selected text.*|"
        r"check (?:latest )?rss.*)",
        routing_clean,
    ):
        return False

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
    if orig_clean.endswith("?") and not re.match(r"^(?:open|start|launch|bring|pull|put|set|turn|list|take|show|see|view|check|get|read|send|tell|mute|unmute|play|pause|next|prev|close|max|min|find|search|locate|where|create|make|rename|delete|remove)\b", routing_clean):
        return True

    return False
