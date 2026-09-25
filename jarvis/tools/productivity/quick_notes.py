from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any
from pydantic import Field
from jarvis.config import ROOT
from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition

NOTES_DIR = ROOT / "jarvis" / "data" / "notes"


class CaptureNoteInput(Contract):
    content: str = Field(min_length=1, max_length=10000)
    tag: str = Field(default="general", max_length=64)
    source: str = Field(default="user_capture", max_length=256)


class CaptureNoteOutput(Contract):
    note_id: str
    file_path: str
    timestamp: str
    status: str


class SearchNotesInput(Contract):
    query: str = Field(min_length=1, max_length=512)


class NoteItem(Contract):
    note_id: str
    timestamp: str
    tag: str
    snippet: str


class SearchNotesOutput(Contract):
    matches: tuple[NoteItem, ...]
    total_found: int


class QuickNoteTool(Tool):
    definition = ToolDefinition(
        name="capture_note",
        description="Quickly captures ideas, snippets, or links into plain Markdown files with timestamps and tags.",
        input_model=CaptureNoteInput,
        output_model=CaptureNoteOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=5.0,
        tags=("notes", "capture", "f10"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: CaptureNoteInput) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = CaptureNoteInput(**arguments)
        NOTES_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.datetime.now().astimezone()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        note_id = f"note_{timestamp_str}"
        note_file = NOTES_DIR / f"{note_id}.md"

        markdown_body = f"""# Note: {now.strftime("%Y-%m-%d %H:%M:%S")}
- **Tag:** #{arguments.tag}
- **Source:** {arguments.source}

---

{arguments.content}
"""
        with open(note_file, "w", encoding="utf-8") as f:
            f.write(markdown_body)

        return {
            "note_id": note_id,
            "file_path": str(note_file),
            "timestamp": now.isoformat(),
            "status": "saved",
        }


class SearchNotesTool(Tool):
    definition = ToolDefinition(
        name="search_notes",
        description="Searches previously captured local notes by keyword.",
        input_model=SearchNotesInput,
        output_model=SearchNotesOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=5.0,
        tags=("notes", "search", "f10"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: SearchNotesInput) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = SearchNotesInput(**arguments)
        if not NOTES_DIR.exists():
            return {"matches": (), "total_found": 0}

        q = arguments.query.lower()
        matches: list[NoteItem] = []

        for note_file in sorted(NOTES_DIR.glob("*.md"), reverse=True):
            try:
                content = note_file.read_text(encoding="utf-8")
                if q in content.lower():
                    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]
                    matching_lines = [l for l in lines if q in l.lower()]
                    snippet = matching_lines[0][:150] if matching_lines else (lines[0][:150] if lines else "")
                    matches.append(
                        NoteItem(
                            note_id=note_file.stem,
                            timestamp=str(note_file.stat().st_mtime_ns // 1_000_000),
                            tag="markdown",
                            snippet=snippet,
                        )
                    )
            except Exception:
                continue

        return {
            "matches": tuple(matches[:10]),
            "total_found": len(matches),
        }
