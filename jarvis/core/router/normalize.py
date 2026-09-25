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
    "could u please",
    "can u please",
    "would u please",
    "could u",
    "can u",
    "would u",
    "will u",
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
    "uh",
    "um",
    "ah",
    "er",
    "ri8",
    "ryt",
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

ASR_TYPOS = {
    "ope": "open",
    "opn": "open",
    "opne": "open",
    "valume": "volume",
    "vol": "volume",
    "volum": "volume",
    "screenshit": "screenshot",
    "screenshoot": "screenshot",
    "notpad": "notepad",
    "chrme": "chrome",
    "calculatr": "calculator",
    "calculater": "calculator",
    "calcualtor": "calculator",
    "clsoe": "close",
    "windwo": "window",
    "windw": "window",
    "minmize": "minimize",
    "maxmize": "maximize",
    "shutdwn": "shutdown",
    "downlods": "downloads",
    "down loads": "downloads",
    "fulll": "full",
    "fullll": "full",
    "fullscren": "fullscreen",
    "fulscreen": "fullscreen",
    "fulllscreen": "fullscreen",
}


def collapse_spaced_letters(text: str) -> str:
    """Collapses spaced individual letters like 'v l c' -> 'vlc' or 'down loads' -> 'downloads'."""
    t = text
    t = re.sub(r"\bdown\s+loads\b", "downloads", t, flags=re.I)
    t = re.sub(r"\bnote\s+pad\b", "notepad", t, flags=re.I)
    t = re.sub(r"\bdesk\s+top\b", "desktop", t, flags=re.I)
    t = re.sub(r"\bdoc\s+u\s+ments\b", "documents", t, flags=re.I)

    def _repl(m: re.Match) -> str:
        return m.group(0).replace(" ", "")

    t = re.sub(r"\b[a-zA-Z](?:\s+[a-zA-Z]){1,7}\b", _repl, t)
    return t


def resolve_discourse_correction(text: str) -> str:
    """Detects and applies mid-utterance self-corrections (e.g. 'Open Chrome—actually Edge', 'Launch Notepad, sorry I meant VS Code')."""
    cleaned = text.strip().rstrip(".!?")

    corr_cues = r"actually|wait(?:\s+no)?|sorry\s*,?\s*(?:i\s+meant|make\s+(?:it|that))|make\s+that|scratch\s+that|rather|\bno\b"

    pattern = re.compile(
        rf"^(?P<initial>.+?)(?:—|\.\.\.|,)\s*(?:{corr_cues})\s*,?\s*(?P<corr>.+)$",
        re.I
    )
    m = pattern.match(cleaned)
    if not m:
        pattern2 = re.compile(
            rf"^(?P<initial>.+?)\s+(?:{corr_cues})\s+(?P<corr>.+)$",
            re.I
        )
        m = pattern2.match(cleaned)

    if not m:
        return text

    initial = m.group("initial").strip()
    corr = m.group("corr").strip()
    # Strip politeness suffixes from correction part
    clean_corr = re.sub(r"\s+please$", "", corr, flags=re.I).strip()

    verb_prefix = re.match(r"^(?:open|launch|start|bring\s+up|pull\s+up|send|message|search|find|adjust|set)\b", clean_corr, re.I)
    if verb_prefix:
        return clean_corr

    m_open = re.match(r"^(?P<cmd>open|launch|start|bring\s+up|pull\s+up)\s+(.+)$", initial, re.I)
    if m_open:
        return f"{m_open.group('cmd')} {clean_corr}"

    m_vol = re.match(r"^(?P<cmd>set\s+volume\s+to|adjust\s+speaker\s+volume\s+to|volume\s+to)\s+\d+%?", initial, re.I)
    if m_vol:
        corr_num = re.search(r"\d+", clean_corr)
        if corr_num:
            return f"{m_vol.group('cmd')} {corr_num.group(0)}"

    m_send = re.match(r"^(?P<cmd>(?:send\s+(?:a\s+)?message\s+to|tell|message))\s+[a-zA-Z\s]+(?P<rest>.*)$", initial, re.I)
    if m_send and ("to" not in clean_corr.lower()):
        return f"{m_send.group('cmd')} {clean_corr}{m_send.group('rest')}"

    m_email = re.match(r"^(?P<cmd>prepare\s+(?:an?\s+)?email\s+to|draft\s+(?:an?\s+)?email\s+to)\s+[a-zA-Z\s]+(?P<rest>.*)$", initial, re.I)
    if m_email and ("to" not in clean_corr.lower()):
        return f"{m_email.group('cmd')} {clean_corr}{m_email.group('rest')}"

    m_search = re.match(r"^(?P<cmd>search\s+(?:for\s+files\s+)?in|find\s+(?:files\s+)?in)\s+\w+(?P<rest>.*)$", initial, re.I)
    if m_search:
        clean_search = re.sub(r"^(?:in\s+)?|(?:\s+instead)$", "", clean_corr, flags=re.I).strip()
        return f"{m_search.group('cmd')} {clean_search}{m_search.group('rest')}"

    if len(clean_corr.split()) >= 2:
        return clean_corr
    return f"{initial} {clean_corr}"


def normalize_text(text: str) -> tuple[str, str]:
    """Returns (original_text, routing_text)."""
    original = text
    # 1. Unicode normalization (NFKC decomposes combined chars, normalizes spaces)
    normalized = unicodedata.normalize("NFKC", text)
    # 2. Lowercase / casefold
    cleaned = normalized.strip().casefold().replace("’", "'").rstrip(".?!")
    # 2b. Discourse self-correction resolution
    cleaned = resolve_discourse_correction(cleaned)
    # 2c. Collapse spaced letters
    cleaned = collapse_spaced_letters(cleaned)
    # 3. Clean punctuation except quotes, dashes, apostrophes; preserve clause delimiters , and ;
    cleaned = re.sub(r"[?!:]+", " ", cleaned)
    cleaned = re.sub(r"[,;]+", " , ", cleaned)

    # 4. Iteratively strip leading wake words, polite prefixes, hesitation markers, and leading slang
    for _ in range(5):
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

        # Strip conversational hesitation phrases e.g. "you know open notepad" or "like open notepad"
        if cleaned.startswith("you know "):
            cleaned = cleaned[9:].strip()
            changed = True
        elif cleaned.startswith("like ") and any(v in cleaned for v in ("open", "start", "launch", "run", "bring", "close", "find", "search", "set", "adjust", "check")):
            cleaned = cleaned[5:].strip()
            changed = True

        leading_tokens = cleaned.split()
        if len(leading_tokens) > 1 and leading_tokens[0] in ("yes", "yeah", "yep", "sure", "ok", "okay"):
            cleaned = " ".join(leading_tokens[1:])
            changed = True
        elif leading_tokens and leading_tokens[0] in SLANG_FILLER and leading_tokens[0] not in PROTECTED_WORDS:
            cleaned = " ".join(leading_tokens[1:])
            changed = True
        if not changed:
            break

    # 4b. Common texting shorthand expansion
    cleaned = re.sub(r"\bmsg\b", "message", cleaned, flags=re.I)
    cleaned = re.sub(r"\bmsgs\b", "messages", cleaned, flags=re.I)
    cleaned = re.sub(r"\bu\b", "you", cleaned, flags=re.I)
    cleaned = re.sub(r"\bur\b", "your", cleaned, flags=re.I)

    # 5. Remove any remaining conversational slang / filler words
    tokens = cleaned.split()
    filtered_tokens = []
    for token in tokens:
        if token in SLANG_FILLER and token not in PROTECTED_WORDS:
            continue
        filtered_tokens.append(token)
    cleaned = " ".join(filtered_tokens)

    # Strip trailing politeness and conversational padding phrases (e.g. "for me", "please", "right now", "bro", "ri8")
    for _ in range(3):
        prev_len = len(cleaned)
        cleaned = re.sub(
            r"\s+(?:for me please|for us please|for me|for us|please|kindly|plz|if you can|right now|quickly|immediately|now|bro|dude|yaar|da|ri8|ryt)$",
            "",
            cleaned,
        ).strip()
        if len(cleaned) == prev_len:
            break

    # 7. Convert compound number words (e.g. "twenty five" -> "25", "thirty percent" -> "30%")
    tens = "twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety"
    units = "one|two|three|four|five|six|seven|eight|nine"
    cleaned = re.sub(
        rf"\b({tens})[ -]+({units})\b",
        lambda m: str(NUMBER_WORDS[m[1]] + NUMBER_WORDS[m[2]]), cleaned,
    )
    for word, num in NUMBER_WORDS.items():
        cleaned = re.sub(rf"\b{word}\s+percent\b", f"{num}%", cleaned)
        cleaned = re.sub(rf"\b{word}\b", str(num), cleaned)

    # 8. Collapse whitespace
    routing = " ".join(cleaned.split())

    # 8b. Semantic Action Normalization (Action-Family Concept Normalization)
    routing = re.sub(r"\bget\s+([a-zA-Z0-9_\-\.]+?)\s+(?:running|rolling)\b", r"open \1", routing, flags=re.I)
    routing = re.sub(r"\bbring\s+([a-zA-Z0-9_\-\.]+?)\s+onto\s+(?:the\s+)?desktop\b", r"open \1", routing, flags=re.I)
    routing = re.sub(r"\b(?:fire\s+up|spin\s+up)\b", "open", routing, flags=re.I)

    routing = re.sub(r"\b(?:shut\s+down|terminate|kill\s+off)\s+(?!computer|pc|system|windows\b)([a-zA-Z0-9_\-\.]+)", r"close \1", routing, flags=re.I)
    routing = re.sub(r"\b(?:dismiss|shut|close)\s+(?:the\s+)?(?:open\s+)?(?:active|current|focused|top|this)\s+window\b", "close window", routing, flags=re.I)
    routing = re.sub(r"\b(?:dismiss\s+(?:the\s+)?(?:open\s+)?(?!active\b|current\b|focused\b|top\b|this\b)([a-zA-Z0-9_\-]+)\s+window)\b", r"close \1", routing, flags=re.I)
    routing = re.sub(r"\bget\s+rid\s+of\s+(?:this\s+)?(?:active\s+)?window\b", "close window", routing, flags=re.I)
    routing = re.sub(r"\bun[- ]?maximize\s+(?:the\s+)?(?:active\s+)?window\b", "restore window", routing, flags=re.I)
    routing = re.sub(r"\b(?:make\s+(?:the\s+)?(?:current\s+|active\s+)?window\s+full\s*screen|expand\s+(?:this\s+)?window\s+to\s+full\s+monitor\s+size|make\s+this\s+bigger\s+to\s+fill\s+screen|blow\s+up\s+active\s+window\s+to\s+maximum|enlarge\s+active\s+window)\b", "maximize window", routing, flags=re.I)
    routing = re.sub(r"\b(?:hide\s+all\s+(?:open\s+)?windows\s+and\s+reveal\s+(?:my\s+)?desktop|clear\s+screen\s+to\s+see\s+desktop(?:\s+icons)?|reveal\s+(?:my\s+)?desktop)\b", "show desktop", routing, flags=re.I)

    routing = re.sub(r"\b(?:silence\s+all\s+audio(?:\s+output)?|put\s+sound\s+on\s+mute|mute\s+all\s+audio)\b", "mute", routing, flags=re.I)
    routing = re.sub(r"\b(?:un[- ]?silence(?:\s+the\s+computer\s+speakers)?|restore\s+audio(?:\s+sound)?(?:\s+playback)?)\b", "unmute", routing, flags=re.I)

    routing = re.sub(r"\b(?:capture\s+(?:desktop\s+)?screen(?:\s+image)?|grab\s+a\s+screen\s*shot(?:\s+of\s+current\s+workspace)?)\b", "take screenshot", routing, flags=re.I)

    routing = re.sub(r"\b(?:enumerate\s+all\s+software(?:\s+packages)?(?:\s+installed)?(?:\s+on\s+windows)?|list\s+all\s+installed\s+apps)\b", "list installed applications", routing, flags=re.I)
    routing = re.sub(r"\b(?:rescan\s+(?:local\s+)?program\s+files(?:\s+for\s+recently\s+added\s+applications)?|refresh\s+applications|refresh\s+app\s+catalog)\b", "refresh applications", routing, flags=re.I)

    routing = re.sub(r"\b(?:check\s+(?:the\s+)?cpu\s+usage\s+and\s+free\s+memory(?:\s+capacity)?)\b", "system info", routing, flags=re.I)
    routing = re.sub(r"\b(?:check\s+for\s+cloned\s+or\s+repeated\s+files|find\s+cloned\s+files)\b", "find duplicates", routing, flags=re.I)
    routing = " ".join(routing.split())


    # 9. Normalize common app aliases in routing text
    for alias, canonical in APP_ALIASES.items():
        if alias in routing:
            routing = re.sub(rf"\b{re.escape(alias)}\b", canonical, routing)

    # 10. Normalize speech-to-text / ASR soundalikes and typos
    for typo, corrected in ASR_TYPOS.items():
        if typo in routing:
            routing = re.sub(rf"\b{re.escape(typo)}\b", corrected, routing)

    return original, routing
