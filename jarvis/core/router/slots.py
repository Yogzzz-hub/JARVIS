"""Deterministic Slot Parser with Typed Value Normalization."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from jarvis.core.capabilities.typed_slots import (
    ApplicationRef,
    ContactRef,
    DeviceRef,
    FolderRef,
    Ordinal,
    Percentage,
)

NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
}

FOLDER_ALIASES = {
    "desktop": "~/Desktop",
    "desk top": "~/Desktop",
    "downloads": "~/Downloads",
    "down loads": "~/Downloads",
    "documents": "~/Documents",
    "docs": "~/Documents",
    "doc u ments": "~/Documents",
    "pictures": "~/Pictures",
    "photos": "~/Pictures",
    "music": "~/Music",
    "videos": "~/Videos",
}

APP_CANONICAL = {
    "google chrome": "chrome",
    "chrome": "chrome",
    "chrom": "chrome",
    "c h r o m e": "chrome",
    "visual studio code": "vscode",
    "vs code": "vscode",
    "vscode": "vscode",
    "code": "code",
    "notepad": "notepad",
    "note pad": "notepad",
    "calculator": "calculator",
    "calc": "calculator",
    "command prompt": "cmd",
    "cmd": "cmd",
    "powershell": "powershell",
    "windows terminal": "terminal",
    "terminal": "terminal",
    "file explorer": "explorer",
    "explorer": "explorer",
    "edge": "edge",
    "microsoft edge": "edge",
    "vlc": "vlc",
    "v l c": "vlc",
    "spotify": "spotify",
    "paint": "paint",
    "firefox": "firefox",
    "word": "word",
    "excel": "excel",
    "powerpoint": "powerpoint",
}


def collapse_spaced_letters(text: str) -> str:
    """Collapses spaced individual letters (ASR variants) like 'v l c' -> 'vlc' or 'down loads' -> 'downloads'."""
    # Multi-letter word spacing: 'down loads' -> 'downloads', 'note pad' -> 'notepad'
    t = text
    t = re.sub(r"\bdown\s+loads\b", "downloads", t, flags=re.I)
    t = re.sub(r"\bnote\s+pad\b", "notepad", t, flags=re.I)
    t = re.sub(r"\bdesk\s+top\b", "desktop", t, flags=re.I)
    t = re.sub(r"\bdoc\s+u\s+ments\b", "documents", t, flags=re.I)

    # Single spaced letters: 'v l c' -> 'vlc', 'c h r o m e' -> 'chrome'
    def _repl(m: re.Match) -> str:
        return m.group(0).replace(" ", "")

    t = re.sub(r"\b[a-zA-Z](?:\s+[a-zA-Z]){1,7}\b", _repl, t)
    return t


def resolve_correction(text: str) -> str:
    """Resolves conversational self-corrections like '70 — actually 40' -> '40'."""
    # Patterns like '... actually X', '... no, X', '... wait, X', '... rather X'
    m = re.search(r"(?:—|-|,)?\s*(?:actually|wait|rather|no,?\s+(?:not\s+)?|instead)\s+(.+)$", text, re.I)
    if m:
        return m.group(1).strip()
    return text


def parse_integer(val: str | int | None) -> int | None:
    if val is None:
        return None
    if isinstance(val, int):
        return val
    cleaned = str(val).strip().casefold()
    cleaned = resolve_correction(cleaned)
    cleaned = re.sub(r"\s*(?:percent|%)\b", "", cleaned).strip()
    if cleaned in NUMBER_WORDS:
        return NUMBER_WORDS[cleaned]
    if re.fullmatch(r"-?[0-9]+", cleaned):
        return int(cleaned)
    m = re.search(r"\b(\d+)\b", cleaned)
    if m:
        return int(m.group(1))
    return None


def parse_percentage(val: str | int | None) -> Percentage | None:
    if val is None:
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        if isinstance(val, float) and not val.is_integer():
            return None
        ival = int(val)
        return Percentage(ival) if 0 <= ival <= 100 else None

    cleaned = str(val).strip().casefold()
    cleaned = resolve_correction(cleaned)
    cleaned = re.sub(r"\s*(?:percent|%)\s*$", "", cleaned).strip()

    # Reject decimals, multiple words/numbers, or booleans
    if "." in cleaned or " " in cleaned or cleaned in ("true", "false"):
        return None
    if cleaned in NUMBER_WORDS:
        parsed = NUMBER_WORDS[cleaned]
    elif re.fullmatch(r"-?[0-9]+", cleaned):
        parsed = int(cleaned)
    else:
        return None

    if 0 <= parsed <= 100:
        return Percentage(parsed)
    return None


def parse_duration_seconds(val: str | int | None) -> int | None:
    """Parses durations like '20 minutes', '600 seconds', '1 hour', 'twenty minutes' into seconds."""
    if val is None:
        return None
    if isinstance(val, int):
        return val
    cleaned = str(val).strip().casefold()
    cleaned = resolve_correction(cleaned)

    # Direct digit check
    if cleaned.isdigit():
        return int(cleaned)

    # Check for minutes pattern
    min_match = re.search(r"(\w+|\d+)\s*(?:minutes?|mins?|m)\b", cleaned)
    if min_match:
        num = parse_integer(min_match.group(1))
        if num is not None:
            return num * 60

    # Check for hours pattern
    hr_match = re.search(r"(\w+|\d+)\s*(?:hours?|hrs?|h)\b", cleaned)
    if hr_match:
        num = parse_integer(hr_match.group(1))
        if num is not None:
            return num * 3600

    # Check for seconds pattern
    sec_match = re.search(r"(\w+|\d+)\s*(?:seconds?|secs?|s)\b", cleaned)
    if sec_match:
        num = parse_integer(sec_match.group(1))
        if num is not None:
            return num

    return parse_integer(cleaned)


def parse_app_name(val: str) -> ApplicationRef:
    cleaned = val.strip().casefold()
    cleaned = resolve_correction(cleaned)
    cleaned = collapse_spaced_letters(cleaned)
    cleaned = cleaned.strip("?.! ")

    # Iteratively strip conversational preambles, fillers, and verbs
    for _ in range(5):
        prev = cleaned
        cleaned = re.sub(
            r"^(?:uh|um|ah|like|you know|i mean|well|so|just|please|kindly|plz|hey jarvis|jarvis|hey|can you|could you|would you|open|launch|start|run|close|quit|kill|bring up|pull up|is|check if|do i have|i need|i want|give me|the|an|a|my)\s+",
            "",
            cleaned,
        ).strip()
        cleaned = re.sub(
            r"\s+(?:for me please|for us please|for me|for us|please|kindly|plz|if you can|right now|quickly|immediately|now|bro|dude|yaar|da|app|application|program|software|window|on(?: the| my)? screen|up on(?: the| my)? screen|running|up|open|active|is there|is installed|on this computer|on this pc|on my pc|installed on this machine|installed on this pc|installed on disk|installed|located on disk|located|on this machine)$",
            "",
            cleaned,
        ).strip()
        cleaned = cleaned.strip("?.! ")
        if cleaned == prev:
            break

    canonical = APP_CANONICAL.get(cleaned, cleaned)
    return ApplicationRef(canonical)



def parse_folder_path(val: str) -> FolderRef:
    cleaned = val.strip().strip('"\'')
    cleaned = resolve_correction(cleaned)
    cleaned = collapse_spaced_letters(cleaned)
    lowered = cleaned.casefold()

    for k, v in FOLDER_ALIASES.items():
        if lowered == k or lowered.endswith(f" {k}") or lowered.startswith(f"{k} "):
            return FolderRef(k.title())

    if lowered in FOLDER_ALIASES:
        return FolderRef(lowered.title())

    resolved = Path(cleaned).expanduser()
    return FolderRef(str(resolved))


def parse_slot_value(slot_name: str, raw_value: Any) -> Any:
    if raw_value is None:
        return None
    match slot_name:
        case "percent":
            return parse_percentage(raw_value)
        case "seconds":
            return parse_duration_seconds(raw_value)
        case "name":
            return parse_app_name(str(raw_value))
        case "path" | "folder":
            return parse_folder_path(str(raw_value))
        case "limit":
            return parse_integer(raw_value) or 100
        case "recipient":
            cleaned = resolve_correction(str(raw_value))
            return ContactRef(cleaned.strip().title())
        case "ordinal":
            return Ordinal(str(raw_value))
        case _:
            return raw_value
