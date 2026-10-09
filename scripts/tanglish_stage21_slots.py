"""Offline typed slot probe for Stage 2.1. This module has no executor access."""
from __future__ import annotations

import re

from scripts.build_tanglish_semantic_stage2 import NAMES

SLOT_NAMES = ("target", "recipient", "sender", "application", "file", "folder", "file_type",
              "message_content", "query", "date", "time", "time_range", "number", "quantity",
              "ordinal", "source", "destination", "device", "browser_tab", "attachment",
              "include_constraint", "exclude_constraint")
OBJECTS = ("pdf", "file", "photo", "message", "folder", "app", "tab", "report", "audio", "document")
ORDINALS = ("first", "second", "third", "latest")
CHANNELS = ("whatsapp", "email", "browser", "local")


def extract_slots(text: str, previous_turns: list[str] | None = None) -> dict[str, str | None]:
    """Read a few explicitly supported relations; leave unsupported slots unresolved."""
    previous_turns = previous_turns or []
    words = re.findall(r"\w+", text.casefold())
    lower = text.casefold()
    result: dict[str, str | None] = {key: None for key in SLOT_NAMES}
    if any(x in words for x in ("atha", "athaye")) and previous_turns:
        result["target"] = "context.selected_resource"
    else:
        for obj in OBJECTS:
            if obj in words:
                result["target"] = obj
                break
    people = []
    for name in NAMES:
        for match in re.finditer(rf"\b{re.escape(name.casefold())}\s+(?:ku|kitta)\b", lower):
            people.append((match.start(), name))
    # A correction keeps the last explicitly selected recipient.
    if people:
        result["recipient"] = max(people)[1]
    for ordinal in ORDINALS:
        if ordinal in words:
            result["ordinal"] = ordinal
            break
    if result["ordinal"] is None and previous_turns:
        for ordinal in ORDINALS:
            if any(ordinal in re.findall(r"\w+", turn.casefold()) for turn in reversed(previous_turns)):
                result["ordinal"] = ordinal
                break
    if "pdf" in words:
        result["file_type"] = "pdf"
    if "app" in words:
        result["application"] = "app"
    for channel in CHANNELS:
        if channel in words:
            result["destination"] = channel
            break
    return result
