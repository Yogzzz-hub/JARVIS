import re
from jarvis.memory.search.models import SearchQuery
from jarvis.memory.search.tokenizer import tokenize_filename

TYPE_MAP = {
    "pdf": ".pdf",
    "pdfs": ".pdf",
    "document": ".docx",
    "documents": ".docx",
    "doc": ".doc",
    "docx": ".docx",
    "docs": ".docx",
    "word": ".docx",
    "word docs": ".docx",
    "presentation": ".pptx",
    "presentations": ".pptx",
    "ppt": ".ppt",
    "pptx": ".pptx",
    "powerpoint": ".pptx",
    "power bi": ".pbix",
    "powerbi": ".pbix",
    "pbix": ".pbix",
    "excel": ".xlsx",
    "excel sheets": ".xlsx",
    "sheet": ".xlsx",
    "sheets": ".xlsx",
    "spreadsheet": ".xlsx",
    "spreadsheets": ".xlsx",
    "xls": ".xls",
    "xlsx": ".xlsx",
    "csv": ".csv",
    "code": ".py",
    "python": ".py",
    "pyhton": ".py",
    "py": ".py",
    "text": ".txt",
    "txt": ".txt",
    "markdown": ".md",
    "md": ".md",
    "image": ".png",
    "images": ".png",
    "photo": ".jpg",
    "picture": ".png",
    "screenshot": ".png",
    "video": ".mp4",
    "videos": ".mp4",
    "folder": "[directory]",
    "directory": "[directory]",
}

DIRECTORY_PATTERN = re.compile(
    r"\b(?:in|from|inside|under)\s+(?:my\s+|the\s+)?(?P<dir>downloads?|desktop|documents?|docs)(?:\s+(?:folder|directory))?\b",
    re.IGNORECASE,
)

CONTENT_SEARCH_PATTERN = re.compile(
    r"\b(?:(?:the\s+)?files?\s+)?(?:containing|with\s+content|with\s+text|having\s+text|having\s+content)\s+[\"']?(?P<phrase>[^\"'\n\r]+)[\"']?",
    re.IGNORECASE,
)

QUOTES_PATTERN = re.compile(r'["\']([^"\']+)["\']')

TEMPORAL_PHRASES = (
    "opened yesterday",
    "used yesterday",
    "used recently",
    "opened recently",
    "this morning",
    "last night",
    "last week",
    "yesterday",
    "today",
    "recently",
    "recent",
    "latest",
    "newest",
    "oldest",
)

TEMPORAL_PATTERN = re.compile(
    rf"\b(?:{'|'.join(re.escape(p) for p in sorted(TEMPORAL_PHRASES, key=len, reverse=True))})\b",
    re.IGNORECASE,
)

CONTEXT_PATTERNS = re.compile(
    r"\b(?:that file|that document|that one|the second one|the first one|the last one|"
    r"the third one|the fourth one|open that|the pdf|same folder|that folder|that directory)\b",
    re.IGNORECASE,
)

SEMANTIC_TRIGGERS = (
    "explaining",
    "discussing",
    "about",
    "concept of",
    "describing",
    "summary of",
    "overview of",
    "related to",
    "how to",
    "guide to",
    "tutorial on",
)

SEMANTIC_PATTERN = re.compile(
    rf"\b(?:{'|'.join(re.escape(s) for s in sorted(SEMANTIC_TRIGGERS, key=len, reverse=True))})\b",
    re.IGNORECASE,
)

FILLER_WORDS = re.compile(
    r"^(?:hey\s+|jarvis\s+|bro\s+|could\s+you\s+|can\s+you\s+|please\s+|kindly\s+|"
    r"find\s+files?\s+named\s+|find\s+files?\s+called\s+|find\s+files?\s+|find\s+file\s+|find\s+that\s+|find\s+my\s+|find\s+|"
    r"search\s+for\s+files?\s+named\s+|search\s+for\s+|search\s+|"
    r"where\s+is\s+that\s+|where\s+is\s+my\s+|where\s+is\s+the\s+file\s+|where\s+is\s+|where\s+are\s+that\s+|where\s+are\s+my\s+|where\s+are\s+|locate\s+|"
    r"show\s+my\s+recent\s+|show\s+my\s+|show\s+files\s+|show\s+|open\s+my\s+|open\s+that\s+|open\s+file\s+|open\s+|"
    r"files?\s+named\s+|files?\s+called\s+|named\s+|called\s+)+",
    re.IGNORECASE,
)

TYPE_WORDS_PATTERN = re.compile(
    rf"\b(?:{'|'.join(re.escape(w) for w in sorted(TYPE_MAP.keys(), key=len, reverse=True))}|file|files|document|documents)\b",
    re.IGNORECASE,
)

NOISE_PATTERN = re.compile(
    r"\b(?:i|me|my|you|we|us|they|used|opened|that|the|in|for|from|a|an|of|on|and|or|with|about|related|to|explaining|discussing)\b",
    re.IGNORECASE,
)

EXT_PATTERN = re.compile(r"\.([a-z0-9]{2,5})\b", re.IGNORECASE)
REPEATED_CHARS_PATTERN = re.compile(r"([a-zA-Z])\1{2,}")

def parse_search_query(query_text: str) -> SearchQuery:
    """Parses a natural language search utterance into a structured SearchQuery."""
    raw = query_text.strip()
    lowered = REPEATED_CHARS_PATTERN.sub(r"\1\1", raw.casefold())

    # 1. Detect Context Reference (e.g. "open that file", "the second one")
    context_ref = bool(CONTEXT_PATTERNS.search(lowered))

    # 2. Detect Directory / Location Hint (e.g. "in my downloads folder", "in desktop")
    directory_hint = None
    dir_match = DIRECTORY_PATTERN.search(lowered)
    query_without_dir = lowered
    if dir_match:
        matched_dir = dir_match.group("dir").lower()
        if matched_dir in ("downloads", "download"):
            directory_hint = "downloads"
        elif matched_dir in ("documents", "document", "docs"):
            directory_hint = "documents"
        elif matched_dir == "desktop":
            directory_hint = "desktop"
        else:
            directory_hint = matched_dir
        query_without_dir = DIRECTORY_PATTERN.sub(" ", lowered).strip()

    # 3. Detect Content Search / Exact Phrase
    content_match = CONTENT_SEARCH_PATTERN.search(raw)
    quotes_match = QUOTES_PATTERN.search(raw)
    if content_match:
        phrase = content_match.group("phrase").strip().strip('"\'')
        tokens = tokenize_filename(phrase) if phrase else []
        return SearchQuery(
            raw_query=raw,
            text=phrase,
            type_hint=None,
            temporal_hint=None,
            latest=False,
            context_reference=False,
            semantic=True,
            tokens=tokens,
            directory_hint=directory_hint,
        )

    # 4. Detect Temporal Hints
    temp_match = TEMPORAL_PATTERN.search(query_without_dir)
    temporal_hint = temp_match.group(0) if temp_match else None
    latest = any(w in query_without_dir for w in ("latest", "newest", "recent", "recently", "used recently", "opened recently"))

    # 5. Detect Semantic Intent (Descriptive query vs direct filename)
    semantic = bool(SEMANTIC_PATTERN.search(query_without_dir))

    # 6. Detect Type Hint
    type_hint = None
    ext_match = EXT_PATTERN.search(query_without_dir)
    if ext_match:
        type_hint = f".{ext_match.group(1)}"
    else:
        padded = f" {query_without_dir} "
        # Prioritize concrete file formats first over general directories
        for phrase, ext in sorted(TYPE_MAP.items(), key=lambda x: len(x[0]), reverse=True):
            if ext != "[directory]" and f" {phrase} " in padded:
                type_hint = ext
                break
        if not type_hint and not directory_hint:
            for phrase, ext in (("folder", "[directory]"), ("directory", "[directory]")):
                if f" {phrase} " in padded:
                    type_hint = ext
                    break

    # 7. Extract and Clean Search Terms
    cleaned = FILLER_WORDS.sub("", query_without_dir).strip()
    cleaned = CONTEXT_PATTERNS.sub("", cleaned).strip()
    if temporal_hint:
        cleaned = TEMPORAL_PATTERN.sub(" ", cleaned)
    if type_hint:
        cleaned = TYPE_WORDS_PATTERN.sub(" ", cleaned)
    if semantic:
        cleaned = SEMANTIC_PATTERN.sub(" ", cleaned)
    cleaned = NOISE_PATTERN.sub(" ", cleaned)
    cleaned = " ".join(cleaned.split()).strip(".,;:?!_- ")

    # Fallback to raw only if no hints were extracted
    if not cleaned:
        if type_hint or temporal_hint or context_ref or directory_hint:
            final_text = ""
        else:
            final_text = raw
    else:
        final_text = cleaned

    # Generate token list
    tokens = tokenize_filename(final_text) if final_text else []

    return SearchQuery(
        raw_query=raw,
        text=final_text,
        type_hint=type_hint,
        temporal_hint=temporal_hint,
        latest=latest,
        context_reference=context_ref,
        semantic=semantic,
        tokens=tokens,
        directory_hint=directory_hint,
    )
