import re
from collections import Counter
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
    "umm",
    "uhh",
    "erm",
    "hmm",
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


_ORDINALS = "first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last|next|previous"


def resolve_discourse_correction(text: str) -> str:
    """Detects and applies mid-utterance self-corrections (e.g. 'Open Chrome—actually Edge', 'Launch Notepad, sorry I meant VS Code')."""
    cleaned = text.strip().rstrip(".!?")

    # Handle "do X instead of Y": X is the positive target, Y is the excluded alternative
    m_instead_of = re.match(r"^(?P<target>.+?)\s+instead\s+of\s+(?P<excluded>.+)$", cleaned, re.I)
    if m_instead_of:
        return m_instead_of.group("target").strip()

    corr_cues = (r"no\s*,?\s*wait|oh\s+wait|actually|wait(?:\s+no)?|sorry\s*,?\s*(?:i\s+meant|make\s+(?:it|that))?|make\s+that|scratch\s+that|rather|"
                 r"\bno\b|i\s+mean|correction|instead\s+use")

    pattern = re.compile(
        rf"^(?P<initial>.+?)(?:—|\.\.\.|[,;!?])\s*(?:{corr_cues})\s*,?\s*(?P<corr>.+)$",
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
    if re.search(r"\b(?:type|write|saying|says)\s+\S", initial, re.I):
        return text  # "type I'm late, wait for me": the words after 'type'/'saying' are content, not a correction
    corr = m.group("corr").strip()
    # Strip politeness suffixes from correction part
    clean_corr = re.sub(r"\s+please$", "", corr, flags=re.I).strip()
    clean_corr = re.sub(r"^(?:take|pick|use|open|make\s+(?:it|that))\s+(?=the\s+(?:%s)\b)" % _ORDINALS, "", clean_corr, flags=re.I)

    # Check for exclusion + target structure: "not Chrome—use Edge", "not Chrome, use Edge", "not Chrome, Edge"
    m_excl = re.match(
        r"^(?:actually\s*,?\s*)?(?:not|instead\s+of)\s+[a-zA-Z0-9_\s\-]+?\s*(?:—|,\s*|\s*-\s*|\s+)(?:use|open|launch|make\s+it)?\s*(?P<target>[a-zA-Z0-9_\s\-]+)$",
        clean_corr,
        re.I
    )
    if m_excl:
        target = m_excl.group("target").strip()
        m_open_init = re.match(r"^(?:open|launch|start|bring\s+up|pull\s+up|get\s+(?:my\s+|the\s+)?\w+\s+up)\b", initial, re.I)
        if m_open_init or "browser" in initial.lower():
            return f"open {target}"
        return target

    # "open the second file - sorry, the third" / "pick the first result, wait, take the last one": swap the ordinal
    new_ord = re.match(r"^(?:the\s+)?(%s)(?:\s+one)?$" % _ORDINALS, clean_corr, re.I)
    if new_ord and re.search(r"\b(?:%s)\b" % _ORDINALS, initial, re.I):
        return re.sub(r"\b(?:%s)\b" % _ORDINALS, new_ord.group(1), initial, count=1, flags=re.I)

    verb_prefix = re.match(r"^(?:open|launch|start|bring\s+up|pull\s+up|send|message|search|find|adjust|set)\b", clean_corr, re.I)
    if verb_prefix:
        return clean_corr

    m_open = re.match(r"^(?P<cmd>open|launch|start|bring\s+up|pull\s+up|get\s+(?:my\s+|the\s+)?\w+\s+up)\s*(.+)?$", initial, re.I)
    if m_open:
        cmd = "open" if "get " in m_open.group("cmd").lower() else m_open.group("cmd")
        # Strip leading "use " or "make it " if user said "actually, use Edge" or "actually, make it Edge"
        app_target = re.sub(r"^(?:use|take|make\s+it|make\s+that|open|launch)\s+", "", clean_corr, flags=re.I).strip()
        return f"{cmd} {app_target}"

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

    # If initial ends with a number and clean_corr is a number (e.g. "turn volume down to 30", "20" -> "turn volume down to 20")
    if re.search(r"\b\d+%?$", initial.strip()) and re.match(r"^\d+%?$", clean_corr.strip()):
        return re.sub(r"\b\d+%?$", clean_corr.strip(), initial.strip())

    if len(clean_corr.split()) >= 2:
        return clean_corr
    return f"{initial} {clean_corr}"


_HEDGED_VERBS = (r"(?:open|start|launch|run|bring|close|find|search|set|adjust|check|turn|play|mute|unmute|show|take|send|"
                 r"put|make|increase|decrease|lower|raise|read|tell|call|delete|copy|move|minimi[sz]e|maximi[sz]e|switch|lock|"
                 r"shut|restart|pause|stop|go|type|create|add|remind|remember|let|text|message|ask|ping|whatsapp|inform|reply|"
                 r"drop|shoot|organi[sz]e|clean|find|minimi[sz]e|lower|raise|dim|say|repeat|put|move|copy|rename|delete)\b")


_FILLER_LEAD = re.compile(r"^(?:(?:(?:can|could|would|will)\s+(?:you|u)(?:\s+please)?(?=\s+(?:uh|um|so|okay|ok|hey|yeah|alright|jarvis|hmm|well|oh)\b)|"
                          r"okay|oaky|ok|so|um+|uh+|erm|hmm+|yeah|yaeh|yeha|yep|alright|basically|well|hey|jarvis|oh\s+yeah|oh|right|"
                          r"like|you\s+know|i\s+mean|anyway|anyways|actually\s+so|hi|and|also|oh\s+and|plus)\s*[,.!?]*\s+)+", re.I)
_MSG_VERBS = r"(?:tell|text|message|msg|ask|whatsapp|send|say|let|inform|reply|ping|remind\s+\w+\s+to)"


def strip_ramble(t: str) -> str:
    """Spoken disfluency around a command: "uh yeah so i need the volume at like 40", "jarvis jarvis are you listening,
    okay, open chrome", "search google for X, i want to buy one", "can you uh set the volume to 60 please thanks"."""
    if not t:
        return t
    t = re.sub(r"\b(\w+)(?:\s*,?\s+\1\b)+", r"\1", t, flags=re.I)  # "okay okay", "jarvis jarvis"
    t = re.sub(r"(?<=\s)(?:um+|uh+|erm|hmm+)\b\s*,?\s*", "", t, flags=re.I)  # inner hesitations
    t = re.sub(r"\b(so|at|to|about)\s+(?:like|lkie|liek)\s*,?\s+(?!(?:it|this|that|them|him|her|me|to)\b)", r"\1 ", t, flags=re.I)
    t = re.sub(r"\b((?:can|could|will)\s+you)\s+(?:like|lkie|liek)\s*,?\s+(?!(?:it|this|that|them|him|her|me|to)\b)", r"\1 ", t, flags=re.I)
    t = re.sub(r"\s*,?\s*(?:and\s+)?then\s*,?\s*after\s+that\s*,?\s*|\s*,\s*and\s+after\s+that\s*,?\s*", " and then ", t, flags=re.I)
    t = re.sub(r"\b(then|and)\s*,?\s*(?:can|could|would)\s+you\s+(?:please\s+)?", r"\1 ", t, flags=re.I)  # "at like 40", "can you like"
    t = re.sub(r",\s*like\s*,\s*", ", ", t, flags=re.I)
    t = re.sub(r"\b(can|could|would|will)\s+you\s+maybe\b", r"\1 you", t, flags=re.I)
    t = re.sub(r"\s+(?:or\s+something|or\s+anything|or\s+whatever)\b", "", t, flags=re.I)
    without = re.sub(r"\s*,?\s+(?:please\s+)?(?:thanks|thank\s+you|thx)(?:\s+(?:a\s+lot|so\s+much))?\s*[.!]*$", "", t, flags=re.I)
    if without != t and not re.fullmatch(r"(?:(?:can|could|would|will)\s+(?:you|u)|please|jarvis|okay|ok|um+|uh+|hey|so|and|\s|,)*", without, re.I):
        t = without  # "... set the volume to 60, thanks"; "could you please thank you so much" stays thanks
    for _ in range(3):
        new = _FILLER_LEAD.sub("", t).strip(" ,")
        if new == t or not new:
            break
        t = new
    # a trailing remark after the command: "lock the pc, i'm going out", "add X to my list, i need to buy it"
    m = re.match(r"^(?P<cmd>[^,]{4,}?)\s*,\s*(?P<tail>(?:i|i'?m|i'?ll|i'?ve|it'?s|because|cause|coz|since|as|for|so\s+that|"
                 r"thanks|thank\s+you|please|(?:can\s+you\s+)?(?:tell|show)\s+me|let\s+me\s+know)\b[^,]{0,60})$", t, flags=re.I)
    if m and not re.search(rf"\b{_MSG_VERBS}\b|\b(?:messag\w*|reply|replies|saying|whats\s*app|email|mail|anuppu|sollu)\b", m.group("cmd"), re.I) and \
            (re.match(rf"^(?:(?:please|just|so|and|oh|okay|(?:can|could|would|will)\s+(?:you|u))\s+)*{_HEDGED_VERBS}", _FILLER_LEAD.sub("", m.group("cmd")), re.I)
             or re.search(r"\b(?:pannu|podu|anuppu|sollu|thedu|vai|edu|moodu|thora)\b|\b(?:what|where|who|how|which)\b", m.group("cmd"), re.I)) and \
            not re.match(r"^(?:if|when|whenever|once|after|before|until|unless)\b", m.group("cmd"), re.I):
        t = m.group("cmd")
    for _ in range(3):
        new = _FILLER_LEAD.sub("", t).strip(" ,")
        if new == t or not new:
            break
        t = new
    return t


_GOOGLE_PRODUCTS = r"(?:chrome|drive|meet|maps|docs|sheets|slides|calendar|photos|classroom|translate|keep|earth|lens|pay|play|news|assistant|account|home|fit|forms)"


def _rephrase_wants(t: str) -> str:
    # real-word slips a spell checker can't see: "form now on" = "from now on", "garb a screenshot" = "grab"
    t = re.sub(r"^form\s+(?=(?:now\s+on|my|the|this|that|here|there|today|tomorrow)\b)", "from ", t)
    t = re.sub(r"^garb\s+(?=(?:a|the|my|this)\s)", "grab ", t)
    # "don't let me forget to call gokul" is a reminder
    t = re.sub(r"^(?:please\s+)?(?:don'?t|do\s+not)\s+(?:let\s+me\s+)?forget\s+(?:to\s+)?(?=\S)", "remind me to ", t)
    """'i want you to open X' -> 'open X'; 'i want to listen to X' -> 'play X'; 'take me to site.com' -> 'go to site.com';
    'google best laptops' -> 'search google for best laptops'."""
    t = re.sub(rf"^i\s+(?:want|need|would\s+like|'d\s+like)\s+(?:you|u)\s+to\s+(?={_HEDGED_VERBS})", "", t)
    t = re.sub(r"^i\s+(?:want|wanna|need|would\s+like|'d\s+like|feel\s+like)\s+(?:to\s+)?(?:listen(?:ing)?\s+to|hear(?:ing)?)\s+(?=\S)", "play ", t)
    # a leading remark before the command: "i'm heading out, lock the pc"
    t = re.sub(r",\s*(?:oh\s+yeah|okay|ok|so|yeah|right|anyway)\s*,\s*", ", ", t)
    m = re.match(r"^(?P<remark>[^,]{4,60}?)\s*,\s*(?P<rest>.+)$", t)
    if m and len(m.group("remark").split()) >= 2 and not re.match(rf"^(?:please\s+)?{_HEDGED_VERBS}|^(?:no|not|don'?t|do\s+not|never|"
                                                                     r"wait|actually|if|when|whenever|after|once|until|unless|tell|text|"
                                                                     r"ask|message|whatsapp|reply)\b", m.group("remark")) \
            and re.match(rf"^(?:(?:please|just|quickly|now|so|and|(?:can|could|would|will)\s+(?:you|u))\s+)*{_HEDGED_VERBS}", m.group("rest")) \
            and not re.match(r"^(?:call|name|label|save)\s+(?:it|that|them)\b", m.group("rest")) \
            and not re.match(r"^(?:(?:please|just|quickly|now|so|and|(?:can|could|would|will)\s+(?:you|u))\s+)*(?:open|find|delete|send|move|copy|"
                             r"rename|play|show|read|share|print|upload|locate|get|organi[sz]e|clean|sort|fix|check)\s+(?:it|that|them|this|those)\b", m.group("rest")) \
            and "," not in m.group("rest"):
        # a remark before the command: "i'm heading out, lock the pc", "someone's coming, minimize everything"
        t = re.sub(r"^(?:(?:please|just|quickly|now|so|and|(?:can|could|would|will)\s+(?:you|u))\s+)+", "", m.group("rest"))
    t = re.sub(rf"^(?:i\s+(?:want|wanna|need|would\s+like)|i'?d\s+like|let\s+me)\s+(?:to\s+)?(?=(?:open|launch|start|close|play|mute|lock|check|see|read|turn)\b)", "", t)
    t = re.sub(r"^(?:check|look\s+(?:on|at|in)|browse|search\s+on)\s+(amazon|flipkart|myntra|ebay|youtube|google|wikipedia)\s+for\s+(?:an?\s+)?", r"search \1 for ", t)
    t = re.sub(r"^(?:any|what(?:'s|\s+is)\s+the)\s+(?:latest\s+)?news\s+(?:about|on|from|in)\s+", "latest news about ", t)
    t = re.sub(r"^(?:take|bring)\s+me\s+to\s+(?=(?:https?://)?[\w-]+(?:\.[\w-]+)+(?:/\S*)?$)", "go to ", t)
    t = re.sub(r"^(?:i\s+think\s+)?i'?m\s+(?:done|finished)\s+with\s+(?P<a>.+?)(?:\s+for\s+(?:now|today))?\s*,?\s*(?:(?:so\s+)?you\s+can\s+|please\s+|just\s+)?"
               r"(?:close|quit|exit|shut)\s+(?:it|that)(?:\s+(?:now|down))?$", r"close \g<a>", t)
    t = re.sub(r"^fire\s+(?:up\s+)?(?P<a>.+?)(?:\s+up)?$", r"open \g<a>", t) if re.match(r"^fire\s+\S", t) else t
    t = re.sub(r"^shut\s+(?!(?:up|down|off|it|the\s+(?:pc|computer|laptop|system|lid)|my\s+(?:pc|computer|laptop)|everything)\b)(?=\S+$|\S+\s+\S+$)", "close ", t)
    t = re.sub(r"^(?:i'?m\s+curious|just\s+curious|quick\s+question|random\s+question|out\s+of\s+curiosity)\s*,?\s+", "", t)
    t = re.sub(r"^i\s+(?:want|wanna|would\s+like|'d\s+like)\s+to\s+watch\s+(?=.+\s+on\s+youtube$)", "play ", t)
    t = re.sub(r"^(?:listen\s+to|lemme\s+hear|let\s+me\s+hear)\s+(?!(?:me|him|her|them|this|that|it|what)\b)(?=\S)", "play ", t)
    if not re.search(r"\b(?:in|on)\s+(?:my\s+|the\s+)?(?:pc|computer|laptop|files?|folders?|documents|downloads|notes|drive)\b"
                     r"|\b(?:hardware|temperatures?|network|wi-?fi|bluetooth|battery|cpu|gpu|ram|memory|disk|storage|processes|"
                     r"settings|system|without|except|but\s+not)\b", t):
        t = re.sub(r"^look\s+up\s+(?=\S)(?!.*\s(?:on|in)\s+\S+$)", "search google for ", t)
        t = re.sub(r"^look\s+up\s+(?=\S)", "search for ", t)
    t = re.sub(rf"^google\s+(?!{_GOOGLE_PRODUCTS}\b|it\b|that\b|this\b)(?=\S)", "search google for ", t)
    return t


def normalize_text(text: str) -> tuple[str, str]:
    """Returns (original_text, routing_text)."""
    original = text
    # 1. Unicode normalization (NFKC decomposes combined chars, normalizes spaces)
    normalized = unicodedata.normalize("NFKC", text)
    # 2. Lowercase / casefold
    cleaned = normalized.strip().strip("\"'“”`").casefold().replace("’", "'").rstrip(".?!").strip("\"'“”`")
    # 2a. Spoken rambles around the command
    cleaned = strip_ramble(cleaned) or cleaned
    # 2b. Discourse self-correction resolution
    cleaned = resolve_discourse_correction(cleaned)
    # 2c. Collapse spaced letters
    cleaned = collapse_spaced_letters(cleaned)
    # 3. Clean punctuation except quotes, dashes, apostrophes; preserve clause delimiters , and ;
    cleaned = re.sub(r"[?!:]+", " ", cleaned)
    cleaned = re.sub(r"[,;]+", " , ", cleaned)
    # 3b. Typos in the first words before the politeness / wake prefixes are recognised ("cuold you open ...")
    cleaned = correct_command_typos(" ".join(cleaned.split()))
    # 3c. A spoken address or thanks at the end is not part of the command ("... jarvis", "... thank you")
    for _ in range(3):
        stripped = re.sub(r"\s*,?\s+(?:hey\s+)?(?:jarvis|thank\s+you(?:\s+so\s+much)?|thanks|thank\s+u|thx|ty|man|buddy|sir|boss|"
                          r"okay|ok)\s*,?$", "", cleaned).strip()
        if stripped == cleaned or not stripped:
            break
        cleaned = stripped

    # 4. Iteratively strip leading wake words, polite prefixes, hesitation markers, and leading slang
    for _ in range(5):
        changed = False
        for wake in WAKE_WORDS:
            if cleaned.startswith(wake + " ") or cleaned.startswith(wake + ". ") or cleaned.startswith(wake + "."):
                cleaned = cleaned[len(wake):].strip(" ,.")
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

        # Wanting phrasings are the command itself ("i want you to open steam", "i want to listen to X on youtube")
        rephrased = _rephrase_wants(cleaned)
        if rephrased != cleaned:
            cleaned = rephrased
            changed = True
        # Spoken commas left behind by a stripped prefix ("uh, could you, like, open brave")
        if cleaned.startswith(","):
            cleaned = cleaned.lstrip(" ,")
            changed = True
        # Strip conversational hesitation phrases e.g. "you know open notepad" or "like open notepad"
        if cleaned.startswith("you know "):
            cleaned = cleaned[9:].strip()
            changed = True
        elif re.match(rf"^(?:like|maybe)\s*,?\s+(?={_HEDGED_VERBS})", cleaned):
            cleaned = cleaned[5:].strip()
            changed = True

        leading_tokens = cleaned.split()
        if len(leading_tokens) > 1 and (leading_tokens[0] in ("yes", "yeah", "yep", "sure", "ok", "okay", "so", "alright", "anyway", "anyways")
                                        or (leading_tokens[0] in ("well", "look", "listen") and leading_tokens[1] == ",")):
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
    routing = re.sub(r"\bget\s+([a-zA-Z0-9_\-\.]+?)(?:\s+(?:media\s+player|player|app|application|browser))?\s+(?:running|rolling|going)\b", r"open \1", routing, flags=re.I)
    routing = re.sub(r"\bbring\s+([a-zA-Z0-9_\-\.]+?)\s+onto\s+(?:the\s+)?desktop\b", r"open \1", routing, flags=re.I)
    routing = re.sub(r"\b(?:fire\s+up|spin\s+up)\b", "open", routing, flags=re.I)
    routing = re.sub(r"^(?:pull|bring|boot|load)\s+up\s+(?!the\s+(?:volume|sound|brightness))", "open ", routing, flags=re.I)

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
    routing = correct_command_typos(routing)
    routing = normalize_paraphrases(routing)

    return original, routing


# ------------------------------------------------------------------------------------------------ typo repair
# Words that start / shape a command, and app names. A misspelt one ("launsh chrom", "mut volum") is repaired only
# when the token is not a real English word and is very close to exactly one of these.
COMMAND_VOCAB = frozenset("""
node nodejs jdk python java open launch start run close quit exit find search show hide mute unmute check where install uninstall update play pause
resume stop skip next previous set turn increase decrease raise lower take lock unlock minimize maximize restore switch
snap move copy rename delete organize list read send reply summarize remind timer screenshot volume brightness desktop
window windows files file folder downloads documents pictures music videos installed applications apps phone android
bluetooth wifi battery status notifications clipboard settings system info memory storage display screen recording
chrome firefox edge notepad calculator spotify explorer vscode terminal paint word excel powerpoint outlook teams zoom
discord telegram whatsapp youtube vlc steam obs photoshop gmail calendar drive browser tab tabs bookmark bookmarks
browse surf need want make give tell ask app pc web all
paste copy cut select undo redo type save press enter snip clipboard
kill capture reboot restart shutdown shut power sleep hibernate laptop computer lower make could would should pull bring silence just yeah remember quickly news talk again charger barely prefer latest texted create download downloaded saved okay time percent back forward tab message messages monday tuesday wednesday thursday friday saturday sunday mark specs
put reduce louder quieter brighter dimmer sound speaker speakers mic microphone camera email emails mail inbox meeting
meetings schedule remember forget note notes reminder reminders todo focus workspace shortcut describe click
have free busy block draft compose write mails mail calendar agenda any whatsapp dial call
what who where when which whom did was were learn remove find copy move rename recent
much many eating using
text ask let know messaged chats chat group reply
like that this repeat hear male female change actually mirror connect dial press
notification shortcuts
rewind seek jump fast speed slow faster slower captions subtitles loop replay fullscreen editor antigravity cursor windsurf
result results link links video videos option item button field tab prompt agent accept reject discard keep apply
highlight erase scratch words line lines sentence sentences paragraph paragraphs character characters uppercase lowercase
capitalize bold italic underline replace attach drop insert upload share split tile arrange monitor notify watch
scroll tap uncheck untick toggle player media installer updates never
first second third fourth fifth minute minutes seconds hour hours
""".split())
_TYPO_CACHE: dict[str, str] = {}


_EXTRA_ENGLISH = frozenset("than nor yet via per amid unto whom whose thus hence ought shall whilst amongst".split())


def _english_word(tok: str) -> bool:
    if tok in _EXTRA_ENGLISH:
        return True
    try:
        from jarvis.integrations.whatsapp.personal_reply.language import english_words
        return tok in english_words()
    except Exception:
        return False


def _edit_distance(a: str, b: str) -> int:
    """Damerau-Levenshtein (optimal string alignment): a swapped pair of letters counts as one typo."""
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[-1][-1]


def _typo_distance_ok(word: str, cand: str) -> bool:
    """A real typo is one slip (two in a long word of the same length); 'terminate' is not a typo of 'terminal'."""
    dist = _edit_distance(word, cand)
    return dist <= 1 or (dist == 2 and len(word) == len(cand) and len(word) >= 8)


_APP_NAMES: frozenset[str] | None = None


def _app_names() -> frozenset[str]:
    global _APP_NAMES
    if _APP_NAMES is None:
        try:
            from jarvis.core.router.slots import APP_CANONICAL
            _APP_NAMES = frozenset(k for k in APP_CANONICAL if " " not in k)
        except Exception:
            _APP_NAMES = frozenset()
    return _APP_NAMES


def correct_command_typos(routing: str) -> str:
    """'launsh chrom' -> 'launch chrome', 'mut volum' -> 'mute volume'. Only the command head (first 4 words),
    never message content ('saying ...', quotes), never real English words or names that are not close to a command."""
    if not routing or '"' in routing or "'" in routing[:1]:
        return routing
    import difflib
    words = routing.split()
    stop = next((i for i, w in enumerate(words) if w in ("saying", "that", "say", "message", "text", "tell")
                 and not (w == "say" and i + 1 < len(words) and (words[i + 1] in ("it", "that", "this")
                                                                  or any(_edit_distance(words[i + 1], x) <= 1 for x in ("that", "this"))))
                 and not (w == "that" and i > 0 and words[i - 1] == "say")), len(words))
    head = min(4, stop)
    changed = False
    for i in range(head):
        w = words[i]
        if len(w) < 3 or not w.isalpha() or w in COMMAND_VOCAB or w in APP_ALIASES or w in ASR_TYPOS or w in _app_names():
            continue  # app nicknames ("calc") and known speech slips are handled by their own tables
        fixed = _TYPO_CACHE.get(w)
        if fixed is None:
            fixed = w
            if not _english_word(w):
                cands = [c for c in difflib.get_close_matches(w, COMMAND_VOCAB, n=3, cutoff=0.75) if c[0] == w[0]
                         and _typo_distance_ok(w, c)]
                if not cands and len(w) >= 5:
                    # two slips in an unknown word ("vloum" -> "volume") when exactly one command word is that close
                    near = [c for c in difflib.get_close_matches(w, COMMAND_VOCAB, n=5, cutoff=0.6)
                            if c[0] == w[0] and len(c) - len(w) in (0, 1) and _edit_distance(w, c) == 2
                            and not (Counter(w) - Counter(c))]  # only swapped / dropped letters, no new ones
                    cands = near if len(near) == 1 else []
                # a word-ending variant of a command word is a real word, not a typo ("shortcuts", "notification")
                if any(w in (c + "s", c + "es", c + "ed", c + "d", c + "ing") for c in cands):
                    cands = []
                swapped = [c for c in cands if sorted(c) == sorted(w)]  # two letters swapped: the likeliest typo
                if swapped:
                    cands = swapped[:1]
                if len(cands) == 1 or (len(cands) == 2 and difflib.SequenceMatcher(None, w, cands[0]).ratio()
                                       - difflib.SequenceMatcher(None, w, cands[1]).ratio() > 0.08):
                    fixed = cands[0]
            _TYPO_CACHE[w] = fixed
        if fixed != w:
            words[i] = fixed
            changed = True
    for i in range(head, len(words)):
        # the device a command is aimed at, anywhere in it ("open chrome on my phnoe"): swapped letters only
        w = words[i]
        if 4 <= len(w) <= 8 and w.isalpha() and w not in _DEVICE_NOUNS:
            hit = next((d for d in _DEVICE_NOUNS if (sorted(d) == sorted(w) or len(d) == len(w) + 1)
                        and _edit_distance(w, d) == 1 and not _english_word(w)), None)
            if hit:
                words[i] = hit
                changed = True
    return " ".join(words) if changed else routing


_DEVICE_NOUNS = ("phone", "mobile", "android", "laptop", "computer", "tablet")


_APP_WORD = r"[a-z0-9][a-z0-9.+\-]*(?:\s+(?!is\b|installed\b|web\b|browser\b|app\b|application\b|program\b)[a-z0-9][a-z0-9.+\-]*)?"


def normalize_paraphrases(routing: str) -> str:
    """Everyday paraphrases -> the canonical phrasing the deterministic lane already understands."""
    r = routing
    # "open calculator but not notepad" / "run edge but definitely not chrome": the exclusion is not a second command
    r = re.sub(r"^(.+?)\s*(?:,?\s*but\s+(?:definitely\s+|absolutely\s+|please\s+)?not|,?\s*but\s+(?:don't|do\s+not)|,?\s*and\s+(?:don't|do\s+not)|,\s*not)\s+(?:to\s+)?.+$", r"\1", r)
    # "don't mute the sound , just turn it down to 20" -> the positive instruction
    r = re.sub(r"^(?:do\s+not|don't|dont)\s+mute\b.*?\b(?:just\s+)?(?:turn\s+it\s+down|lower\s+it|set\s+it)\s+to\s+(\d+)%?$",
               r"set volume to \1", r)
    # installed?  "is firefox on this computer", "check whether firefox is on this pc", "check if c h r o m e is there"
    r = re.sub(r"^(?:check\s+(?:whether|if)\s+|is\s+)(%s)\s+(?:is\s+)?(?:present(?:\s+on\s+(?:this|my|the)\s+(?:computer|pc|laptop|system|machine))?|on\s+(?:this|my|the)\s+(?:computer|pc|laptop|system|machine)|there|available)$" % _APP_WORD,
               r"is \1 installed", r)
    r = re.sub(r"^check\s+(?:whether|if)\s+(%s)\s+(?:is\s+)?installed$" % _APP_WORD, r"is \1 installed", r)
    # where is it installed
    r = re.sub(r"^(?:find|show|get|tell\s+me)\s+(?:the\s+)?(?:location|install(?:ation)?\s+(?:folder|path|location)|"
               r"executable\s+(?:directory|folder|path)|path)\s+(?:of|for)\s+(%s)(?:\s+on\s+disk|\s+installed)?$" % _APP_WORD,
               r"where is \1 installed", r)
    r = re.sub(r"^where\s+is\s+(%s)\s+(?:located|on\s+disk|stored)$" % _APP_WORD, r"where is \1 installed", r)
    # installed programs
    r = re.sub(r"^(?:list|show)\s+(?:every|all|all\s+the)\s+(?:programs?|software|apps?|applications?)\s+installed(?:\s+on\s+(?:this\s+|my\s+)?(?:pc|computer|laptop))?$",
               "list installed applications", r)
    r = re.sub(r"^rebuild\s+(?:the\s+)?(?:application|app)\s+(?:index|catalog)(?:\s+cache)?$", "refresh applications", r)
    # desktop / windows / lock
    r = re.sub(r"^(?:go\s+)?back\s+to\s+(?:the\s+)?desktop$|^minimi[sz]e\s+all(?:\s+windows)?(?:\s+to\s+see\s+(?:the\s+)?desktop)?$",
               "show desktop", r)
    r = re.sub(r"^(?:kill|dismiss|close)\s+(?:the\s+)?(?:current|active|focused|this)\s+(?:active\s+)?window$", "close window", r)
    r = re.sub(r"^lock\s+(?:my\s+|the\s+)?(?:windows\s+)?(?:session|computer|laptop|workstation)$", "lock the pc", r)
    # hardware / system
    r = re.sub(r"^(?:check|show|what\s+are)\s+(?:my\s+|the\s+)?(?:processor|cpu|hardware|pc|computer)\s+(?:specs|specifications|details)$",
               "system info", r)
    # "i need terminal", "need to browse the web", "need to do some math", "somewhere to type"
    r = re.sub(r"^(?:(?:i\s+)?need|give\s+me|find\s+me|i\s+want)\s+to\s+(?:do\s+(?:some\s+)?)?(?:math|maths|calculations?|math\s+calculations)$", "open calculator", r)
    r = re.sub(r"^(?:(?:i\s+)?need|give\s+me|find\s+me|i\s+want)\s+(?:something|a\s+tool)\s+to\s+(?:calculate|do\s+math|compute)(?:\s+this)?$", "open calculator", r)
    r = re.sub(r"^(?:(?:i\s+)?need|give\s+me|find\s+me|i\s+want)\s+to\s+(?:browse|surf)\s+(?:the\s+)?(?:web|internet)$", "open chrome", r)
    r = re.sub(r"^(?:(?:i\s+)?need|give\s+me|find\s+me|i\s+want)\s+(?:my\s+|the\s+)?browser$", "open chrome", r)
    r = re.sub(r"^(?:(?:i\s+)?need|give\s+me|find\s+me|i\s+want)\s+(?:somewhere|a\s+place)\s+to\s+(?:type|write|jot\s+down)(?:\s+(?:a\s+)?(?:quick\s+)?(?:note|notes|memo|text))?$", "open notepad", r)
    r = re.sub(r"^(?:(?:i\s+)?need|give\s+me|find\s+me|i\s+want)\s+somewhere\s+to\s+(?:take\s+notes?|write\s+things?\s+down)$", "open notepad", r)
    # Window switching / return to previous application
    r = re.sub(r"^(?:get|take|bring|switch|go|return)\s+(?:(?:me\s+)?back\s+to|to)\s+(?:whatever|the)\s+(?:app|window|program)\s+(?:i\s+was\s+using\s+)?(?:before|previously|earlier).*$", "switch to previous window", r)
    r = re.sub(r"^(?:get|take|bring|switch|go|return)\s+(?:me\s+)?back\s+to\s+(?:the\s+)?(?:previous|last\s+active)\s+(?:app|window|program)$", "switch to previous window", r)
    r = re.sub(r"^(?:return|go\s+back)\s+to\s+(?:the\s+)?(?:last\s+active|previous)\s+(?:window|app|program)$", "switch to previous window", r)
    # Relative clause app descriptions: "pull up the calculator thing I normally use"
    r = re.sub(r"^(?:pull\s+up|open|launch|start|bring\s+up)\s+(?:the\s+)?([a-zA-Z0-9_\s\-]+?)\s+(?:thing|tool|utility|app|program)\s+(?:(?:that|which)\s+)?(?:i\s+|we\s+)?(?:normally|usually|always)?\s*(?:use|open|have)?$", r"open \1", r)
    r = re.sub(r"^i\s+need\s+(?:the\s+|my\s+)?(%s)$" % _APP_WORD,
               lambda m: f"open {m.group(1)}" if m.group(1).split()[0] in COMMAND_VOCAB else m.group(0), r)
    # "pull up file explorer", "display the chrome web browser", "open up paint application", "initialize excel software"
    r = re.sub(r"^(?:pull\s+up|display|open\s+up|bring\s+up|load\s+up|fire\s+up|start\s+up|boot\s+up|initialize|initialise)\s+(?:the\s+)?(%s)(?:\s+(?:web\s+)?(?:browser|application|app|program|software))?$" % _APP_WORD,
               lambda m: f"open {m.group(1)}", r)
    # "pick the first result, wait, take the last one" (after correction) -> an ordinal reference
    r = re.sub(r"^(?:pick|take|choose|select)\s+the\s+(first|second|third|fourth|fifth|last)\s+(?:result|one|item|file)$", r"open the \1 one", r)
    # Deictic file reference: "i want to see that pdf", "show that document", "view that file"
    r = re.sub(r"^(?:i\s+want\s+to\s+|can\s+i\s+|let\s+me\s+)?(?:see|view|look\s+at|show)\s+(that\s+(?:pdf|document|file))$", r"open \1", r)
    return " ".join(r.split())


# ------------------------------------------------------------------------------------------------ light clean
_LEAD = re.compile(r"^(?:(?:hey|hi|ok|okay|hello|yo)\s+)?jarvis\s*[,.!:]?\s+|^(?:um+|uh+|erm|er|hmm+|ah|so|okay so|ok so|"
                   r"alright)\s*[,.]?\s+|^(?:well|right|now|listen|look|okay|ok)\s*,\s*"
                   r"|^(?:(?:can|could|would|will)\s+(?:you|u)\s+)?(?:please|pls|plz|kindly)\s+"
                   # hedges before a command: "could you, like, open brave", "can you just turn it up"
                   r"|^(?:(?:can|could|would|will)\s+(?:you|u)\s*,\s*|(?:(?:can|could|would|will)\s+(?:you|u)\s+)?"
                   rf"(?:like|just|maybe|quickly|quick|real\s+quick|now)\s*,?\s+(?={_HEDGED_VERBS}))|^,\s*", re.I)
_TRAIL = re.compile(r"\s*[,.!]?\s+(?:(?:hey\s+)?jarvis|thank\s+you(?:\s+so\s+much)?|thanks|thank\s+u|thx|ty|please|pls|plz)"
                    r"\s*[.!?]*$", re.I)


_SPLIT_FIX = {"wi fi": "wifi", "blue tooth": "bluetooth", "whats app": "whatsapp", "what's app": "whatsapp", "you tube": "youtube",
              "screen shot": "screenshot", "note pad": "notepad", "v s code": "vs code", "power point": "powerpoint",
              "g mail": "gmail", "e mail": "email", "insta gram": "instagram", "tele gram": "telegram"}
_SPOKEN_SPLITS = re.compile(r"\b(?:" + "|".join(k.replace(" ", r"\s+").replace("'", "'?") for k in _SPLIT_FIX) + r")\b", re.I)
_CONTRACTION_FIX = {"whats": "what's", "wheres": "where's", "hows": "how's", "whos": "who's", "thats": "that's",
                    "dont": "don't", "cant": "can't", "wont": "won't", "didnt": "didn't", "doesnt": "doesn't", "isnt": "isn't",
                    "im": "i'm", "ive": "i've", "youre": "you're", "theres": "there's", "lets": "let's"}
_CONTRACTIONS = re.compile(r"\b(?:" + "|".join(_CONTRACTION_FIX) + r")\b", re.I)


def clean_for_matching(text: str) -> str:
    """The command with wake words, hesitations, trailing thanks/address and typos in the first words removed,
    keeping the owner's casing (message text and names stay exactly as said). Used by pattern matchers."""
    t = unicodedata.normalize("NFKC", text or "").strip().strip("\"'“”`").replace("\u2019", "'")
    t = strip_ramble(t) or t
    for _ in range(4):
        new = _LEAD.sub("", t, count=1).strip()
        new = _TRAIL.sub("", new).strip()
        if new == t or not new:
            break
        t = new
    t = _CONTRACTIONS.sub(lambda m: _CONTRACTION_FIX[m.group(0).lower()], t)
    t = _SPOKEN_SPLITS.sub(lambda m: _SPLIT_FIX[re.sub(r"\s+", " ", m.group(0).lower())], t)
    words = t.split()
    head = " ".join(words[:4]).lower()
    fixed = correct_command_typos(head)
    if fixed != head and len(fixed.split()) == len(words[:4]):
        t = " ".join(fixed.split() + words[4:])
    low = t.lower()
    wanted = _rephrase_wants(low)
    if wanted != low:  # only the opening is rewritten: keep the owner's casing in the rest
        k = 0
        while k < min(len(low), len(wanted)) and low[len(low) - 1 - k] == wanted[len(wanted) - 1 - k]:
            k += 1
        t = wanted[: len(wanted) - k] + (t[len(t) - k:] if k else "")
    return t
