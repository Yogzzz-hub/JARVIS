import re
from pathlib import Path

# Regex patterns for splitting tokens
CAMEL_CASE_PATTERN = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
DIGIT_LETTER_PATTERN = re.compile(r"(?<=\D)(?=\d)|(?<=\d)(?=\D)")
DELIMITER_PATTERN = re.compile(r"[_\-.\s/\\:,;]+")

def tokenize_filename(filename: str) -> list[str]:
    """Tokenizes a filename or stem into normalized individual tokens.
    
    Examples:
        'UNIT_4_DL_FINAL_2.pdf' -> ['unit', '4', 'dl', 'final', '2', 'pdf']
        'DeepLearningNotes.pdf' -> ['deep', 'learning', 'notes', 'pdf']
        'nlp-unit5_final-v2.pdf' -> ['nlp', 'unit', '5', 'final', 'v', '2', 'pdf']
    """
    # 1. Split camelCase / PascalCase first
    camel_split = CAMEL_CASE_PATTERN.sub(" ", filename)
    # 2. Split letter/digit boundaries
    digit_split = DIGIT_LETTER_PATTERN.sub(" ", camel_split)
    # 3. Split on common delimiters
    tokens = DELIMITER_PATTERN.split(digit_split)
    # 4. Clean, lowercase, filter empty
    cleaned_tokens = [t.lower().strip() for t in tokens if t.strip()]
    return cleaned_tokens

def tokenize_path(path_str: str) -> list[str]:
    """Tokenizes a full filesystem path into clean tokens."""
    p = Path(path_str)
    all_parts = list(p.parts)
    tokens = []
    for part in all_parts:
        # Strip drive letter colon like 'C:'
        part_clean = part.rstrip(":\\/")
        if part_clean:
            tokens.extend(tokenize_filename(part_clean))
    return tokens

def path_tokens_string(path_str: str) -> str:
    """Returns a space-separated string of path tokens suitable for FTS5 indexing."""
    return " ".join(tokenize_path(path_str))
