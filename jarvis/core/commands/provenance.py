"""Authenticated command text; model-produced arguments are not owner evidence."""
from contextvars import ContextVar

owner_command: ContextVar[str | None] = ContextVar("owner_command", default=None)


def draft_instruction(content: str) -> str:
    raw = owner_command.get() or ""
    # Literal text can be used as owner evidence only when it actually occurs in
    # the authenticated request. Negative instructions stay intact for review.
    from jarvis.integrations.whatsapp.intelligence.language import semantic_frame
    import time
    negative = semantic_frame("", raw, time.time()).negations if raw else []
    literal = content.strip().strip('"\' .!?')
    if literal and literal.casefold() in raw.casefold() and not negative:
        return raw + "\n" + content
    return raw
