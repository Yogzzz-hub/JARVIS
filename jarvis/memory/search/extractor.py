import hashlib
from pathlib import Path
import time
import xml.etree.ElementTree as ET
import zipfile

TEXT_EXTENSIONS = frozenset({
    ".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx",
    ".json", ".csv", ".log", ".yaml", ".yml", ".toml",
    ".html", ".css", ".xml", ".sql", ".sh", ".bat", ".ps1",
})

def compute_file_hash(path: Path, max_bytes: int = 10 * 1024 * 1024) -> str:
    """Computes a SHA256 hash by streaming chunks, never loading multi-GB files fully into RAM."""
    h = hashlib.sha256()
    bytes_read = 0
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
            bytes_read += len(chunk)
            if bytes_read >= max_bytes:
                break
    return h.hexdigest()

def extract_docx_text(path: Path, max_chars: int = 100_000) -> str:
    """Extracts text from a .docx file using standard library zipfile and XML parser."""
    try:
        with zipfile.ZipFile(path) as z:
            if "word/document.xml" not in z.namelist():
                return ""
            xml_data = z.read("word/document.xml")
            root = ET.fromstring(xml_data)
            # Find all text elements
            texts = [node.text for node in root.iter() if node.tag.endswith("t") and node.text]
            full_text = " ".join(texts)
            return full_text[:max_chars]
    except Exception as exc:
        raise RuntimeError(f"DOCX extraction failed: {exc}") from exc

def extract_pdf_text(path: Path, max_pages: int = 50, max_chars: int = 100_000) -> str:
    """Extracts text from a .pdf file using pypdf."""
    try:
        import pypdf
        reader = pypdf.PdfReader(str(path))
        extracted = []
        chars_collected = 0
        pages_to_read = min(len(reader.pages), max_pages)
        for i in range(pages_to_read):
            page = reader.pages[i]
            page_text = page.extract_text() or ""
            extracted.append(page_text)
            chars_collected += len(page_text)
            if chars_collected >= max_chars:
                break
        return " ".join(extracted)[:max_chars]
    except Exception as exc:
        raise RuntimeError(f"PDF extraction failed: {exc}") from exc

def extract_text_file(path: Path, max_chars: int = 100_000) -> str:
    """Reads a plain text file using UTF-8 with fallback to latin-1."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            return f.read(max_chars)
    except Exception:
        with path.open("r", encoding="latin-1", errors="replace") as f:
            return f.read(max_chars)

def extract_file_content(
    path_str: str,
    max_file_size_mb: float = 25.0,
    max_text_chars: int = 100_000,
    max_pdf_pages: int = 50,
) -> tuple[str, str, str, str | None]:
    """Extracts text and generates excerpt.
    
    Returns: (full_text, excerpt, status, error)
    Status is one of: 'SUCCESS', 'SKIPPED', 'FAILED'
    """
    p = Path(path_str)
    if not p.exists() or not p.is_file():
        return "", "", "SKIPPED", "File does not exist"

    size_mb = p.stat().st_size / (1024 * 1024)
    if size_mb > max_file_size_mb:
        return "", "", "SKIPPED", f"File size ({size_mb:.1f} MB) exceeds limit ({max_file_size_mb} MB)"

    ext = p.suffix.casefold()
    text = ""
    error = None
    status = "SUCCESS"

    t0 = time.perf_counter()
    try:
        if ext in TEXT_EXTENSIONS:
            text = extract_text_file(p, max_chars=max_text_chars)
        elif ext == ".pdf":
            text = extract_pdf_text(p, max_pages=max_pdf_pages, max_chars=max_text_chars)
        elif ext in (".docx", ".doc"):
            text = extract_docx_text(p, max_chars=max_text_chars)
        else:
            return "", "", "SKIPPED", "Unsupported content format"
    except Exception as exc:
        status = "FAILED"
        error = str(exc)

    # Generate short excerpt (first 250 chars)
    excerpt = " ".join(text[:250].split()) if text else ""
    return text, excerpt, status, error
