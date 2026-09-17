import re
from pathlib import Path
from typing import Any

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
    "downloads": "~/Downloads",
    "documents": "~/Documents",
    "docs": "~/Documents",
    "pictures": "~/Pictures",
    "photos": "~/Pictures",
    "music": "~/Music",
    "videos": "~/Videos",
}

APP_CANONICAL = {
    "google chrome": "chrome",
    "chrome": "chrome",
    "visual studio code": "vscode",
    "vs code": "vscode",
    "vscode": "vscode",
    "code": "vscode",
    "notepad": "notepad",
    "calculator": "calculator",
    "calc": "calculator",
    "command prompt": "cmd",
    "cmd": "cmd",
    "powershell": "powershell",
    "windows terminal": "terminal",
    "terminal": "terminal",
    "file explorer": "explorer",
    "explorer": "explorer",
    "edge": "msedge",
    "microsoft edge": "msedge",
}

def parse_integer(val: str | int | None) -> int | None:
    if val is None:
        return None
    if isinstance(val, int):
        return val
    cleaned = str(val).strip().casefold()
    cleaned = re.sub(r"\s*(?:percent|%)\b", "", cleaned).strip()
    if cleaned in NUMBER_WORDS:
        return NUMBER_WORDS[cleaned]
    digits = re.findall(r"\d+", cleaned)
    if digits:
        return int(digits[0])
    return None

def parse_percentage(val: str | int | None) -> int | None:
    if val is None:
        return None
    cleaned = str(val).strip().casefold().replace("%", "").replace("percent", "").strip()
    parsed = parse_integer(cleaned)
    if parsed is not None and 0 <= parsed <= 100:
        return parsed
    return None

def parse_duration_seconds(val: str | int | None) -> int | None:
    """Parses durations like '20 minutes', '600 seconds', '1 hour', 'twenty minutes' into seconds."""
    if val is None:
        return None
    if isinstance(val, int):
        return val
    cleaned = str(val).strip().casefold()

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

    # Default fallback to integer parse
    return parse_integer(cleaned)

def parse_app_name(val: str) -> str:
    cleaned = val.strip().casefold()
    cleaned = re.sub(r"^(?:the\s+)?", "", cleaned)
    return APP_CANONICAL.get(cleaned, cleaned)

def parse_folder_path(val: str) -> str:
    cleaned = val.strip().strip('"\'')
    lowered = cleaned.casefold()
    if lowered in FOLDER_ALIASES:
        resolved = Path(FOLDER_ALIASES[lowered]).expanduser()
        return str(resolved)
    return str(Path(cleaned).expanduser())

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
        case "path":
            return parse_folder_path(str(raw_value))
        case "limit":
            return parse_integer(raw_value) or 100
        case _:
            return raw_value
