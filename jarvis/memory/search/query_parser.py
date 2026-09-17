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
    r"find\s+file\s+|find\s+that\s+|find\s+my\s+|find\s+|search\s+for\s+|search\s+|"
    r"where\s+is\s+that\s+|where\s+is\s+my\s+|where\s+is\s+|where\s+are\s+that\s+|where\s+are\s+my\s+|where\s+are\s+|locate\s+|show\s+my\s+recent\s+|"
    r"show\s+my\s+|show\s+files\s+|show\s+|open\s+my\s+|open\s+that\s+|open\s+file\s+|open\s+)+",
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

    # 2. Detect Temporal Hints
    temp_match = TEMPORAL_PATTERN.search(lowered)
    temporal_hint = temp_match.group(0) if temp_match else None
    latest = any(w in lowered for w in ("latest", "newest", "recent", "recently", "used recently", "opened recently"))

    # 3. Detect Semantic Intent (Descriptive query vs direct filename)
    semantic = bool(SEMANTIC_PATTERN.search(lowered))

    # 4. Detect Type Hint
    type_hint = None
    ext_match = EXT_PATTERN.search(lowered)
    if ext_match:
        type_hint = f".{ext_match.group(1)}"
    else:
        padded = f" {lowered} "
        for phrase, ext in sorted(TYPE_MAP.items(), key=lambda x: len(x[0]), reverse=True):
            if f" {phrase} " in padded:
                type_hint = ext
                break

    # 5. Extract and Clean Search Terms
    cleaned = FILLER_WORDS.sub("", lowered).strip()
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
        if type_hint or temporal_hint or context_ref:
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
    )
