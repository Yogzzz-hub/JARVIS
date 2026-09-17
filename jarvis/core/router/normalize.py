import re
import unicodedata

WAKE_WORDS = (
    "hey jarvis",
    "ok jarvis",
    "okay jarvis",
    "hi jarvis",
    "hello jarvis",
    "jarvis",
)

POLITE_PREFIXES = (
    "could you please",
    "can you please",
    "would you please",
    "could you",
    "can you",
    "would you",
    "will you",
    "please",
    "kindly",
)

SLANG_FILLER = (
    "bro",
    "dude",
    "da",
    "yaar",
    "machan",
    "pa",
    "nanba",
    "pannunga",
    "pannu",
)

# Crucial semantic words that MUST NEVER be removed
PROTECTED_WORDS = frozenset({
    "just", "only", "don't", "dont", "do not", "not", "without", "except",
    "before", "after", "instead", "same", "again", "and", "or", "then",
})

NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
}

APP_ALIASES = {
    "google chrome": "chrome",
    "visual studio code": "vscode",
    "vs code": "vscode",
    "command prompt": "cmd",
    "powershell": "powershell",
    "file explorer": "explorer",
    "windows explorer": "explorer",
    "ms edge": "edge",
    "microsoft edge": "edge",
}

def normalize_text(text: str) -> tuple[str, str]:
    """Returns (original_text, routing_text)."""
    original = text
    # 1. Unicode normalization (NFKC decomposes combined chars, normalizes spaces)
    normalized = unicodedata.normalize("NFKC", text)
    # 2. Lowercase / casefold
    cleaned = normalized.strip().casefold()
    # 3. Clean punctuation except quotes, dashes, apostrophes inside words
    cleaned = re.sub(r"[?!,;:]+", " ", cleaned)
    # 4. Iteratively strip leading wake words, polite prefixes, and leading slang
    for _ in range(3):
        changed = False
        for wake in WAKE_WORDS:
            if cleaned.startswith(wake + " ") or cleaned.startswith(wake + ","):
                cleaned = cleaned[len(wake):].strip(" ,")
                changed = True
                break
            elif cleaned == wake:
                cleaned = ""
                changed = True
                break
        for prefix in POLITE_PREFIXES:
            if cleaned.startswith(prefix + " "):
                cleaned = cleaned[len(prefix):].strip()
                changed = True
                break
        leading_tokens = cleaned.split()
        if leading_tokens and leading_tokens[0] in SLANG_FILLER and leading_tokens[0] not in PROTECTED_WORDS:
            cleaned = " ".join(leading_tokens[1:])
            changed = True
        if not changed:
            break

    # 5. Remove any remaining conversational slang / filler words
    tokens = cleaned.split()
    filtered_tokens = []
    for token in tokens:
        if token in SLANG_FILLER and token not in PROTECTED_WORDS:
            continue
        filtered_tokens.append(token)
    cleaned = " ".join(filtered_tokens)

    # Strip trailing politeness words like "please" or "kindly"
    cleaned = re.sub(r"\s+(?:please|kindly|plz)$", "", cleaned).strip()

    # 7. Convert compound number words (e.g. "twenty five" -> "25", "thirty percent" -> "30%")
    # Replace number words with digits
    for word, num in NUMBER_WORDS.items():
        # Match word surrounded by word boundaries
        cleaned = re.sub(rf"\b{word}\s+percent\b", f"{num}%", cleaned)
        cleaned = re.sub(rf"\b{word}\b", str(num), cleaned)

    # 8. Collapse whitespace
    routing = " ".join(cleaned.split())

    # 9. Normalize common app aliases in routing text
    for alias, canonical in APP_ALIASES.items():
        if alias in routing:
            routing = re.sub(rf"\b{re.escape(alias)}\b", canonical, routing)

    return original, routing
