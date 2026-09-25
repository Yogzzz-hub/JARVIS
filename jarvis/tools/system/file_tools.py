import asyncio
import mimetypes
import os
from pathlib import Path
import shutil
import sqlite3
import time
from typing import Any
from pydantic import Field
from jarvis.config import ROOT
from jarvis.memory.search.engine import SearchEngine
from jarvis.memory.search.models import SearchQuery
from jarvis.memory.working_memory import WorkingMemory
from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition

# ----------------- CONTRACTS -----------------

class FindFileInput(Contract):
    query: str = Field(min_length=1, max_length=1024)
    type_hint: str | None = None
    time_hint: str | None = None
    directory_hint: str | None = None
    limit: int = Field(default=5, ge=1, le=50)

class FileSearchResultItem(Contract):
    file_id: int
    path: str
    name: str
    extension: str
    score: float
    confidence: float
    match_reasons: tuple[str, ...] = ()
    excerpt: str | None = None

class FindFileOutput(Contract):
    query: str
    results: tuple[FileSearchResultItem, ...]
    search_mode: str
    semantic_used: bool
    latency_ms: float
    is_ambiguous: bool
    clarification: str | None = None

class OpenFileInput(Contract):
    path: str | None = None
    file_id: int | None = None

class OpenFileOutput(Contract):
    path: str
    file_id: int | None = None
    opened: bool
    message: str

class ReadMetadataInput(Contract):
    path: str = Field(min_length=1, max_length=4096)

class ReadMetadataOutput(Contract):
    path: str
    name: str
    extension: str
    size_bytes: int
    created_iso: str
    modified_iso: str
    is_directory: bool
    mime_type: str | None = None

class CreateFolderInput(Contract):
    path: str = Field(min_length=1, max_length=4096)

class CreateFolderOutput(Contract):
    path: str
    created: bool

class CopyFileInput(Contract):
    source: str = Field(min_length=1, max_length=4096)
    destination: str = Field(min_length=1, max_length=4096)

class CopyFileOutput(Contract):
    source: str
    destination: str
    copied: bool

class MoveFileInput(Contract):
    source: str = Field(min_length=1, max_length=4096)
    destination: str = Field(min_length=1, max_length=4096)

class MoveFileOutput(Contract):
    source: str
    destination: str
    moved: bool

class RenameFileInput(Contract):
    source: str = Field(min_length=1, max_length=4096)
    new_name: str = Field(min_length=1, max_length=256)

class RenameFileOutput(Contract):
    source: str
    new_path: str
    renamed: bool

class DeleteFileInput(Contract):
    path: str = Field(min_length=1, max_length=4096)

class DeleteFileOutput(Contract):
    path: str
    deleted: bool
    method: str

# ----------------- TOOL IMPLEMENTATIONS -----------------

class FindFileTool(Tool):
    def __init__(self, search_engine: SearchEngine | None = None):
        self.search_engine = search_engine
        self.definition = ToolDefinition(
            name="find_file",
            description="Searches local indexed files using multi-tier cascaded search (FTS5 + semantic).",
            input_model=FindFileInput,
            output_model=FindFileOutput,
            read_only=True,
            risk=RiskLevel.READ_ONLY,
            timeout_s=5.0,
            tags=("search", "files", "knowledge"),
        )

    def run(self, input_data: FindFileInput) -> FindFileOutput:
        if isinstance(input_data, dict):
            q_val = input_data.get("query") or input_data.get("filename") or input_data.get("name") or "latest"
            input_data = FindFileInput(
                query=str(q_val) if q_val else "latest",
                type_hint=input_data.get("type_hint"),
                time_hint=input_data.get("time_hint"),
                directory_hint=input_data.get("directory_hint"),
                limit=input_data.get("limit", 5),
            )
        if self.search_engine is None:
            # Fallback search if engine uninitialized
            return FindFileOutput(
                query=input_data.query,
                results=(),
                search_mode="UNINITIALIZED",
                semantic_used=False,
                latency_ms=0.0,
                is_ambiguous=False,
            )

        from jarvis.memory.search.query_parser import parse_search_query
        q = parse_search_query(input_data.query)
        if input_data.type_hint:
            q.type_hint = input_data.type_hint
        if input_data.time_hint:
            q.temporal_hint = input_data.time_hint
        if input_data.directory_hint:
            q.directory_hint = input_data.directory_hint
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                resp = executor.submit(lambda: asyncio.run(self.search_engine.search(q))).result()
        else:
            resp = asyncio.run(self.search_engine.search(q))
        items = tuple(
            FileSearchResultItem(
                file_id=r.file_id,
                path=r.path,
                name=r.name,
                extension=r.extension,
                score=r.score,
                confidence=r.confidence,
                match_reasons=tuple(r.match_reasons),
                excerpt=r.excerpt,
            )
            for r in resp.results[:input_data.limit]
        )
        return FindFileOutput(
            query=input_data.query,
            results=items,
            search_mode=resp.search_mode,
            semantic_used=resp.semantic_used,
            latency_ms=resp.latency_ms,
            is_ambiguous=resp.is_ambiguous,
            clarification=resp.clarification,
        )

class OpenFileTool(Tool):
    def __init__(self, db_path: Path | str, working_memory: WorkingMemory | None = None, launcher: Any = None):
        self.db_path = str(db_path)
        self.memory = working_memory
        self.launcher = launcher or getattr(os, "startfile", None)
        self.definition = ToolDefinition(
            name="open_file",
            description="Opens an existing validated file using default Windows application and records usage.",
            input_model=OpenFileInput,
            output_model=OpenFileOutput,
            read_only=False,
            risk=RiskLevel.REVERSIBLE,
            timeout_s=5.0,
            tags=("files", "launch"),
        )

    def run(self, input_data: OpenFileInput) -> OpenFileOutput:
        if isinstance(input_data, dict):
            input_data = OpenFileInput(
                path=input_data.get("path") or input_data.get("filepath") or input_data.get("file"),
                file_id=input_data.get("file_id"),
            )
        target_path = input_data.path
        file_id = input_data.file_id

        # Resolve path from file_id if needed
        if not target_path and file_id:
            with sqlite3.connect(self.db_path) as con:
                cur = con.execute("SELECT path FROM files WHERE id = ?", (file_id,))
                row = cur.fetchone()
                if row:
                    target_path = row[0]

        if not target_path:
            raise ValueError("Must provide either a valid path or file_id to open_file")

        p = Path(target_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {target_path}")

        # Launch via Windows associated app or launcher
        if self.launcher:
            self.launcher(str(p))

        # Record usage in DB and memory
        now_ns = time.time_ns()
        try:
            with sqlite3.connect(self.db_path) as con:
                con.execute(
                    "UPDATE files SET open_count = open_count + 1, last_opened_ns = ? WHERE path = ?",
                    (now_ns, str(p)),
                )
                con.commit()
        except Exception:
            pass

        if self.memory:
            self.memory.record_opened(str(p))

        return OpenFileOutput(
            path=str(p),
            file_id=file_id,
            opened=True,
            message=f"Successfully opened {p.name}",
        )

class ReadFileMetadataTool(Tool):
    def __init__(self):
        self.definition = ToolDefinition(
            name="read_file_metadata",
            description="Reads metadata (size, timestamps, MIME type) for a local path.",
            input_model=ReadMetadataInput,
            output_model=ReadMetadataOutput,
            read_only=True,
            risk=RiskLevel.READ_ONLY,
            timeout_s=3.0,
            tags=("files", "metadata"),
        )

    def run(self, input_data: ReadMetadataInput) -> ReadMetadataOutput:
        p = Path(input_data.path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {input_data.path}")

        stat = p.stat()
        mime, _ = mimetypes.guess_type(str(p))
        from datetime import datetime, timezone
        c_iso = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat()
        m_iso = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

        return ReadMetadataOutput(
            path=str(p),
            name=p.name,
            extension=p.suffix.casefold() if p.is_file() else "[directory]",
            size_bytes=stat.st_size if p.is_file() else 0,
            created_iso=c_iso,
            modified_iso=m_iso,
            is_directory=p.is_dir(),
            mime_type=mime,
        )

def _resolve_target_folder(raw_path: str) -> Path:
    raw_clean = raw_path.strip().strip("'\"")
    desktop = Path(os.environ.get("USERPROFILE", "")) / "OneDrive" / "Desktop"
    if not desktop.exists():
        desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
    downloads = Path(os.environ.get("USERPROFILE", "")) / "Downloads"
    documents = Path(os.environ.get("USERPROFILE", "")) / "OneDrive" / "Documents"
    if not documents.exists():
        documents = Path(os.environ.get("USERPROFILE", "")) / "Documents"

    lowered = raw_clean.lower()
    base_dir = desktop
    folder_name = raw_clean

    import re
    if " on desktop" in lowered or " in desktop" in lowered:
        folder_name = re.sub(r"\s+(?:on|in)\s+desktop", "", raw_clean, flags=re.IGNORECASE).strip()
        base_dir = desktop
    elif " in downloads" in lowered or " to downloads" in lowered or " on downloads" in lowered:
        folder_name = re.sub(r"\s+(?:in|to|on)\s+downloads", "", raw_clean, flags=re.IGNORECASE).strip()
        base_dir = downloads
    elif " in documents" in lowered or " to documents" in lowered:
        folder_name = re.sub(r"\s+(?:in|to)\s+documents", "", raw_clean, flags=re.IGNORECASE).strip()
        base_dir = documents

    p = Path(folder_name)
    if not p.is_absolute():
        p = base_dir / folder_name
    return p

def _find_existing_item(name_or_path: str) -> Path | None:
    raw_clean = name_or_path.strip().strip("'\"")
    p = Path(raw_clean)
    if p.exists():
        return p

    desktop = Path(os.environ.get("USERPROFILE", "")) / "OneDrive" / "Desktop"
    if not desktop.exists():
        desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
    downloads = Path(os.environ.get("USERPROFILE", "")) / "Downloads"
    documents = Path(os.environ.get("USERPROFILE", "")) / "OneDrive" / "Documents"
    if not documents.exists():
        documents = Path(os.environ.get("USERPROFILE", "")) / "Documents"

    for base in (desktop, downloads, documents, Path.cwd()):
        candidate = base / raw_clean
        if candidate.exists():
            return candidate

    # Search in database
    db_path = ROOT / "db/jarvis.db"
    if db_path.exists():
        try:
            with sqlite3.connect(str(db_path), timeout=5.0) as conn:
                row = conn.execute(
                    "SELECT path FROM files WHERE (name_norm = ? OR stem = ?) AND is_available = 1 ORDER BY modified_ns DESC LIMIT 1",
                    (raw_clean.lower(), raw_clean.lower()),
                ).fetchone()
                if row and Path(row[0]).exists():
                    return Path(row[0])
        except Exception:
            pass

    return None

class CreateFolderTool(Tool):
    def __init__(self):
        self.definition = ToolDefinition(
            name="create_folder",
            description="Creates a directory or folder path if it does not exist.",
            input_model=CreateFolderInput,
            output_model=CreateFolderOutput,
            read_only=False,
            risk=RiskLevel.REVERSIBLE,
            timeout_s=3.0,
            tags=("files", "directory"),
        )

    def run(self, input_data: CreateFolderInput) -> CreateFolderOutput:
        p = _resolve_target_folder(input_data.path)
        p.mkdir(parents=True, exist_ok=True)
        return CreateFolderOutput(path=str(p), created=True)

class CopyFileTool(Tool):
    def __init__(self):
        self.definition = ToolDefinition(
            name="copy_file",
            description="Copies a file from source to destination.",
            input_model=CopyFileInput,
            output_model=CopyFileOutput,
            read_only=False,
            risk=RiskLevel.REVERSIBLE,
            timeout_s=5.0,
            tags=("files", "copy"),
        )

    def run(self, input_data: CopyFileInput) -> CopyFileOutput:
        src = Path(input_data.source)
        dst = Path(input_data.destination)
        if not src.exists():
            raise FileNotFoundError(f"Source file not found: {input_data.source}")
        shutil.copy2(src, dst)
        return CopyFileOutput(source=str(src), destination=str(dst), copied=True)

class MoveFileTool(Tool):
    def __init__(self):
        self.definition = ToolDefinition(
            name="move_file",
            description="Moves a file or directory from source to destination.",
            input_model=MoveFileInput,
            output_model=MoveFileOutput,
            read_only=False,
            risk=RiskLevel.REVERSIBLE,
            timeout_s=5.0,
            tags=("files", "move"),
        )

    def run(self, input_data: MoveFileInput) -> MoveFileOutput:
        src = Path(input_data.source)
        dst = Path(input_data.destination)
        if not src.exists():
            raise FileNotFoundError(f"Source file not found: {input_data.source}")
        shutil.move(str(src), str(dst))
        return MoveFileOutput(source=str(src), destination=str(dst), moved=True)

class RenameFileTool(Tool):
    def __init__(self):
        self.definition = ToolDefinition(
            name="rename_file",
            description="Renames a file or directory.",
            input_model=RenameFileInput,
            output_model=RenameFileOutput,
            read_only=False,
            risk=RiskLevel.REVERSIBLE,
            timeout_s=3.0,
            tags=("files", "rename"),
        )

    def run(self, input_data: RenameFileInput) -> RenameFileOutput:
        src = _find_existing_item(input_data.source)
        if not src or not src.exists():
            raise FileNotFoundError(f"Source not found: {input_data.source}")
        clean_new_name = input_data.new_name.strip().strip("'\"")
        new_path = src.parent / clean_new_name
        if new_path.exists() and new_path.resolve() != src.resolve():
            if new_path.is_dir():
                shutil.rmtree(str(new_path), ignore_errors=True)
            else:
                new_path.unlink(missing_ok=True)
        src.rename(new_path)
        return RenameFileOutput(source=str(src), new_path=str(new_path), renamed=True)

class DeleteFileTool(Tool):
    def __init__(self):
        self.definition = ToolDefinition(
            name="delete_file",
            description="Safely moves a file or folder to the Windows Recycle Bin using send2trash.",
            input_model=DeleteFileInput,
            output_model=DeleteFileOutput,
            read_only=False,
            requires_confirmation=False,
            risk=RiskLevel.REVERSIBLE,
            timeout_s=5.0,
            tags=("files", "delete"),
        )

    def run(self, input_data: DeleteFileInput) -> DeleteFileOutput:
        p = _find_existing_item(input_data.path)
        if not p or not p.exists():
            raise FileNotFoundError(f"Path not found: {input_data.path}")
        try:
            import send2trash
            send2trash.send2trash(str(p))
            return DeleteFileOutput(path=str(p), deleted=True, method="recycle_bin")
        except Exception:
            # Safe non-permanent fallback
            trash_dir = ROOT / ".trash"
            trash_dir.mkdir(parents=True, exist_ok=True)
            target = trash_dir / p.name
            shutil.move(str(p), str(target))
            return DeleteFileOutput(path=str(p), deleted=True, method="quarantine_trash")

def create_file_tools(search_engine: SearchEngine | None = None, db_path: Path | str = ROOT / "db/jarvis.db", working_memory: WorkingMemory | None = None) -> list[Tool]:
    return [
        FindFileTool(search_engine),
        OpenFileTool(db_path, working_memory),
        ReadFileMetadataTool(),
        CreateFolderTool(),
        CopyFileTool(),
        MoveFileTool(),
        RenameFileTool(),
        DeleteFileTool(),
    ]
