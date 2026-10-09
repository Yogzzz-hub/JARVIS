"""Side-effect-free typed SemanticFrame prototype for offline Stage 2.2 evaluation."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from scripts.build_tanglish_semantic_stage2 import NAMES


@dataclass(frozen=True)
class RefCandidate:
    kind: str
    surface: str
    context_key: str | None = None


@dataclass(frozen=True)
class TemporalRange:
    start: str | None = None
    end: str | None = None


@dataclass
class WorkingContext:
    selected_resource: RefCandidate | None = None
    current_contact: RefCandidate | None = None
    current_application: RefCandidate | None = None
    current_channel: str | None = None


SLOT_SCHEMA = (
    "application", "contact", "recipient", "sender", "file", "folder", "file_type",
    "resource_type", "query", "text_content", "url", "source", "destination",
    "device", "browser", "browser_tab", "ordinal", "count", "number", "quantity",
    "percentage", "date", "time", "date_range", "time_range", "attachment",
    "project", "workflow", "include_constraint", "exclude_constraint",
    "spatial_relation", "selected_resource", "quoted_resource",
)


@dataclass
class SemanticFrame:
    speech_act: str
    action_concept: str | None
    slots: dict[str, Any] = field(default_factory=lambda: {name: None for name in SLOT_SCHEMA})
    negated_action: bool = False
    corrections: list[dict[str, Any]] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)

    def asdict(self) -> dict[str, Any]:
        return asdict(self)


ORDINAL = {"first": 1, "muthala": 1, "second": 2, "rendaavathu": 2,
           "third": 3, "moonavathu": 3, "last": -1, "kadaisi": -1, "latest": -1}
FILE_TYPES = ("pdf", "screenshot", "png", "jpg", "docx", "txt", "zip")
APPS = ("Chrome", "Edge", "Firefox", "Notepad", "Spotify", "VS Code")


def _last_named_relation(text: str, marker: str) -> str | None:
    hits = []
    for name in NAMES:
        for match in re.finditer(rf"\b{re.escape(name)}\s+(?:{marker})\b", text, re.I):
            hits.append((match.start(), name))
    return max(hits)[1] if hits else None


def extract_frame(text: str, context: WorkingContext | None = None,
                  *, speech_act: str = "UNKNOWN", action_concept: str | None = None) -> SemanticFrame:
    """Extract what is grounded. Missing entities stay unresolved for clarification."""
    context = context or WorkingContext()
    low = text.casefold()
    words = set(re.findall(r"[\w]+", low))
    frame = SemanticFrame(speech_act=speech_act, action_concept=action_concept)
    slots = frame.slots
    recipient = _last_named_relation(text, "ku|kitta|kita")
    sender = _last_named_relation(text, "oda|irundhu|lendhu")
    if recipient:
        slots["recipient"] = RefCandidate("ContactRefCandidate", recipient)
        slots["contact"] = slots["recipient"]
    elif words & {"avanuku", "avankita", "him", "her", "avanga"}:
        if context.current_contact:
            slots["recipient"] = context.current_contact
        else:
            frame.unresolved.append("recipient")
    if sender:
        slots["sender"] = RefCandidate("ContactRefCandidate", sender)
    for app in APPS:
        if re.search(rf"\b{re.escape(app)}\b", text, re.I):
            slots["application"] = RefCandidate("AppRefCandidate", app)
            break
    for typ in FILE_TYPES:
        if typ in words:
            slots["file_type"] = typ.upper()
            slots["resource_type"] = "FileResource" if typ != "screenshot" else "ImageResource"
            break
    file_match = re.search(r"\b[\w.-]+\.(?:pdf|png|jpg|docx|txt|zip)\b", text, re.I)
    if file_match:
        slots["file"] = RefCandidate("FileRefCandidate", file_match.group())
        slots["attachment"] = slots["file"] if action_concept in {"SEND", "SHARE", "UPLOAD"} else None
    folder_match = re.search(r"\b(?:folder|directory)\s+([\w.-]+)\b", text, re.I)
    if folder_match:
        slots["folder"] = RefCandidate("FolderRefCandidate", folder_match.group(1))
    quote = re.search(r'["“]([^"”]+)["”]', text)
    if quote:
        slots["quoted_resource"] = RefCandidate("QuotedText", quote.group(1))
        if action_concept in {"SEND", "WRITE", "TYPE", "REPLY"}:
            slots["text_content"] = quote.group(1)
    url = re.search(r"https?://[^\s,;]+", text, re.I)
    if url:
        slots["url"] = url.group()
        slots["resource_type"] = "URLResource"
    for surface, number in ORDINAL.items():
        if surface in words:
            slots["ordinal"] = number
            break
    number = re.search(r"\b(\d+(?:\.\d+)?)\s*(%|percent|percentage)?\b", text, re.I)
    if number:
        value = float(number.group(1))
        slots["number"] = int(value) if value.is_integer() else value
        if number.group(2):
            slots["percentage"] = value
        if action_concept in {"SET", "INCREASE", "DECREASE"}:
            slots["quantity"] = slots["number"]
    date = re.search(r"\b(tomorrow|today|yesterday|naalaiku|inniku|nethu|next week)\b", low)
    if date:
        slots["date"] = date.group()
    clock = re.search(r"\b(?:at|ku)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", low)
    if clock:
        slots["time"] = clock.group(1).strip()
    time_range = re.search(r"\bfrom\s+(\d{1,2}(?::\d{2})?)\s+to\s+(\d{1,2}(?::\d{2})?)\b", low)
    if time_range:
        slots["time_range"] = TemporalRange(time_range.group(1), time_range.group(2))
    browser = re.search(r"\b(chrome|edge|firefox)\s+(?:browser\s+)?(first|second|third|\d+(?:st|nd|rd|th)?)\s+tab\b", low)
    if browser:
        slots["browser"] = RefCandidate("BrowserRefCandidate", browser.group(1).title())
        slots["browser_tab"] = RefCandidate("BrowserTabRefCandidate", browser.group(2))
    source = re.search(r"\b(\w+)\s+(?:lendhu|irundhu|from)\b", low)
    destination = re.search(r"\b(?:to|ku)\s+(\w+)\b|\b(\w+)\s+(?:ku|kitta)\b", low)
    if source:
        slots["source"] = source.group(1)
    if destination:
        slots["destination"] = destination.group(1) or destination.group(2)
    if action_concept == "SWITCH" and slots["destination"]:
        for app in APPS:
            if app.casefold() == slots["destination"].casefold():
                slots["application"] = RefCandidate("AppRefCandidate", app)
                break
    if context.current_channel and slots["destination"] is None and action_concept in {"SEND", "SHARE", "FORWARD"}:
        slots["destination"] = context.current_channel
    if "pdf" in words and "mattum" in words:
        slots["include_constraint"] = {"file_type": "PDF"}
    exclusion = re.search(r"\b(screenshot|pdf|arun|naveen)\s+(?:venam|venda|vendam)\b", low)
    if exclusion is None:
        exclusion = re.search(r"\b(arun|naveen)\s+(?:ku|kitta)\s+(?:venam|venda|vendam)\b", low)
    if exclusion:
        slots["exclude_constraint"] = exclusion.group(1)
    date_range = re.search(r"\bfrom\s+(tomorrow|today|next week|naalaiku|inniku)\s+to\s+(tomorrow|today|next week|naalaiku|inniku)\b", low)
    if date_range:
        slots["date_range"] = TemporalRange(date_range.group(1), date_range.group(2))
    if re.search(r"\b(?:don't|pannadha|panna venam|panna venda|do not)\b", low):
        frame.negated_action = True
    if words & {"atha", "athu", "ithu", "itha", "it", "that", "this", "same"}:
        if context.selected_resource:
            slots["selected_resource"] = context.selected_resource
        else:
            frame.unresolved.append("selected_resource")
    correction = re.search(r"\b(Arun|Naveen|Chrome|Edge|\d+)\b.*?\b(?:illa|sorry|actually)\b[\s,]+\b(Arun|Naveen|Chrome|Edge|\d+)\b", text, re.I)
    if correction:
        before, after = correction.group(1), correction.group(2)
        slot = "quantity" if before.isdigit() and after.isdigit() else "application" if before.casefold() in {"chrome", "edge"} else "recipient"
        frame.corrections.append({"slot": slot, "superseded": before, "active": after})
        if slot == "quantity":
            slots["quantity"] = int(after)
        elif slot == "application":
            slots["application"] = RefCandidate("AppRefCandidate", after)
        else:
            slots["recipient"] = RefCandidate("ContactRefCandidate", after)
    return frame
