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
    # "no, don't close audacity": the leading "no" belongs to the negation
    lowered = re.sub(r"^(?:no+|nah|nope|oh\s+no|wait|hey)\s*,?\s+(?=(?:don't|dont|do not|never|please don't|please do not)\b)", "", lowered)
    # "don't let me forget to call arun" / "don't forget to ..." ask for a reminder, not for nothing to happen
    if re.match(r"^(?:please\s+)?(?:don't|dont|do not)\s+(?:let\s+me\s+)?forget\b", lowered):
        return False, constraints

    # Meta-instructions modifying reporting preferences must NEVER be marked as negated tool commands!
    from jarvis.core.router.meta_policy import match_meta_policy
    if match_meta_policy(text, "negation-guard") is not None:
        return False, constraints

    # Check "don't <action> <target>, just <inquire>" (e.g. "don't open notepad, just tell me whether it's installed")
    m_split = re.match(r"^(?:(?:please|kindly|jarvis|hey\s+jarvis)\s*,?\s+)?(?:don't|do not|never)\s+([^,]+),\s*(?:just\s+)?(.+)$",
                       lowered)
    if m_split:
        negated = m_split.group(1).strip()
        positive = m_split.group(2).strip()
        positive = re.sub(r"\s+instead$", "", positive)

        # Entity resolution across negation: resolve "it" to the entity in the negated phrase
        m_neg_act = re.match(r"^(?P<verb>open|launch|start|run|delete|remove|close|install)\s+(?P<ent>.+)$", negated)
        if m_neg_act:
            neg_verb = m_neg_act.group("verb")
            neg_ent = m_neg_act.group("ent").strip()
            # If positive clause asks about installation status:
            if re.search(r"\b(?:whether\s+it'?s?|if\s+it'?s?|is\s+it)\s+installed\b", positive) or positive in ("whether it's installed", "if it's installed", "is it installed"):
                positive = f"is {neg_ent} installed"
            elif re.search(r"\b(?:whether\s+it'?s?|if\s+it'?s?|is\s+it)\s+(?:running|active|open)\b", positive):
                positive = f"is {neg_ent} running"
            elif re.search(r"\b(?:its|the)\s+size\b", positive):
                positive = f"get size of {neg_ent}"

            constraints.append({"type": f"no_{neg_verb}", "target": neg_ent})
            constraints.append({"type": "negative_action", "target": negated, "forbidden_action": neg_verb, "entity": neg_ent})
            constraints.append({"type": "positive_override", "target": positive})
            return False, constraints

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

    # Check for embedded negation clause (e.g. "open chrome but don't close edge", "show me messages from arun, but don't reply to him", "see that pdf, not edit or move it")
    if re.search(r"\b(?:,\s*not\s+|,\s*but\s+not\s+|but\s+don't|and\s+don't|without|except)\b", lowered):
        parts = re.split(r"\b(?:,\s*not\s+|,\s*but\s+not\s+|but\s+don't|and\s+don't|without|except)\b", lowered, maxsplit=1)
        if len(parts) == 2:
            primary = parts[0].strip().rstrip(",;.- ")
            clause = parts[1].strip().rstrip(",;.- ")
            forbidden = []
            if re.search(r"\b(?:reply|send|message|text)\b", clause):
                forbidden.extend(["reply", "send"])
            if re.search(r"\b(?:edit|modify|alter|change|overwrite)\b", clause):
                forbidden.append("modify")
            if re.search(r"\b(?:delete|remove|erase|trash)\b", clause):
                forbidden.append("delete")
            if re.search(r"\b(?:open|launch|start)\b", clause):
                forbidden.append("open")
            neg_dict: dict[str, Any] = {"type": "negative_action", "target": clause}
            if forbidden:
                neg_dict["forbidden_actions"] = forbidden
            constraints.append(neg_dict)
            return False, constraints

    return False, constraints

def is_informational_or_question(original_text: str, routing_text: str) -> bool:
    """Detects queries, informational requests, or capability questions that must NOT trigger actions.

    Example:
    - 'Can Chrome open PDFs?' -> True (informational)
    - 'How do I open Chrome?' -> True (informational)
    - 'Is Chrome open?' -> True (query state)
    - 'Is Chrome installed?' -> True (query state)
    - 'Why did Chrome crash?' -> True (informational)
    - 'I'm only asking what WhatsApp does; don't open it.' -> True (informational)
    - 'Can you tell me how deleting a file works without deleting anything?' -> True (informational)
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
        r"what(?:'s| is| are)(?: the)? (?:unread |recent )?whatsapp (?:messages?|msgs?|texts?|chats?|updates?).*|"
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

    # Meta-informational / knowledge question patterns
    if re.search(
        r"\b(?:i'?m\s+(?:only|just)\s+asking|just\s+asking|just\s+curious|"
        r"can\s+(?:you|jarvis)\s+(?:tell\s+me\s+|explain\s+)?(?:how|what|why)\b|"
        r"(?:tell\s+me|explain)\s+(?:how|what|why)\b|"
        r"what\s+does\s+[a-zA-Z0-9_\-\s]+\s+(?:do|mean|work|provide)\b|"
        r"how\s+does\s+[a-zA-Z0-9_\-\s]+\s+work\b|"
        r"can\s+(?:jarvis|you)\s+use\s+[a-zA-Z0-9_\-\s]+\??$|"
        r"how\s+(?:do\s+i|can\s+i|to)\s+(?:delete|install|open|use|send|configure)\b)",
        orig_clean,
    ):
        return True

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
