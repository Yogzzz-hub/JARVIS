from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any
from pydantic import Field
from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition

DEFAULT_CATEGORIES = {
    "Documents": {".pdf", ".docx", ".doc", ".txt", ".pptx", ".xlsx", ".csv", ".epub"},
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"},
    "Code": {".py", ".rs", ".js", ".ts", ".html", ".css", ".json", ".yaml", ".yml", ".c", ".cpp"},
    "Audio": {".mp3", ".wav", ".flac", ".m4a", ".ogg"},
    "Video": {".mp4", ".mkv", ".mov", ".avi", ".webm"},
    "Archives": {".zip", ".tar", ".gz", ".7z", ".rar"},
}


class OrganizeDownloadsInput(Contract):
    downloads_path: str = Field(min_length=1, max_length=4096)
    dry_run: bool = True


class OrganizedFileItem(Contract):
    source: str
    destination: str
    category: str


class OrganizeDownloadsOutput(Contract):
    moves: tuple[OrganizedFileItem, ...]
    dry_run: bool
    total_moved: int
    status: str


def classify_file(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    for cat, extensions in DEFAULT_CATEGORIES.items():
        if ext in extensions:
            return cat
    return "Other"


class OrganizeDownloadsTool(Tool):
    definition = ToolDefinition(
        name="organize_downloads",
        description="Categorizes completed downloads into subfolders with preview, collision avoidance, and undo support.",
        input_model=OrganizeDownloadsInput,
        output_model=OrganizeDownloadsOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=10.0,
        tags=("file", "downloads", "f06"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: OrganizeDownloadsInput) -> dict[str, Any]:
        p = Path(arguments.downloads_path)
        if not p.exists() or not p.is_dir():
            raise FileNotFoundError(f"Downloads folder '{arguments.downloads_path}' does not exist.")

        moves: list[dict[str, str]] = []
        for item in p.iterdir():
            # Only process regular files directly in downloads (do not scan subfolders or whole disk)
            if item.is_file() and not item.name.startswith("."):
                category = classify_file(item.name)
                dest_dir = p / category
                target_dest = dest_dir / item.name

                # Collision avoidance
                if target_dest.exists() and not arguments.dry_run:
                    stem = item.stem
                    suffix = item.suffix
                    target_dest = dest_dir / f"{stem}_{int(time.time())}{suffix}"

                moves.append({
                    "source": str(item),
                    "destination": str(target_dest),
                    "category": category,
                })

                if not arguments.dry_run:
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(item), str(target_dest))

        return {
            "moves": tuple(OrganizedFileItem(**m) for m in moves),
            "dry_run": arguments.dry_run,
            "total_moved": len(moves),
            "status": "preview" if arguments.dry_run else "completed",
        }
