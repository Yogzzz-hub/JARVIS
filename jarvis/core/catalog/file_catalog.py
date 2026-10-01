"""File Catalog for dynamic user folder intelligence in JARVIS EDGE.

Tracks user-authorized locations (Desktop, Documents, Downloads, Projects)
and provides fast indexed search, recency tracking, and natural language file resolution.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.catalog.file")


@dataclass
class FileEntry:
    path: str
    name: str
    extension: str
    size_bytes: int
    modified_time: float
    is_directory: bool = False
    folder_type: str = "custom"  # desktop, documents, downloads, projects, custom

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "extension": self.extension,
            "size_bytes": self.size_bytes,
            "modified_time": self.modified_time,
            "is_directory": self.is_directory,
            "folder_type": self.folder_type,
        }


class FileCatalog:
    """Dynamic user file catalog supporting natural language reference resolution and recency."""

    def __init__(self, watch_roots: Optional[List[str | Path]] = None) -> None:
        self._entries: Dict[str, FileEntry] = {}
        self.watch_roots: List[Path] = [Path(r) for r in watch_roots] if watch_roots else self._default_roots()
        self._last_index_time: float = 0.0

    def _default_roots(self) -> List[Path]:
        home = Path.home()
        roots: List[Path] = []
        for name in ["Desktop", "OneDrive/Desktop", "Documents", "OneDrive/Documents", "Downloads"]:
            p = home / name
            if p.exists() and p.is_dir() and p not in roots:
                roots.append(p)
        cwd = Path.cwd()
        if cwd not in roots:
            roots.append(cwd)
        return roots

    def index(self, max_files_per_root: int = 1000) -> int:
        """Indexes files across watch roots (ignoring vendor/build caches)."""
        from jarvis.core.catalog.project_catalog import IGNORE_DIRS
        new_entries: Dict[str, FileEntry] = {}

        for root in self.watch_roots:
            if not root.exists():
                continue
            folder_type = root.name.lower()
            count = 0
            try:
                for root_dir, dirs, files in os.walk(root):
                    # Prune ignored directories
                    dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
                    for fname in files:
                        if fname.startswith("."):
                            continue
                        fpath = os.path.join(root_dir, fname)
                        try:
                            st = os.stat(fpath)
                            entry = FileEntry(
                                path=fpath,
                                name=fname,
                                extension=os.path.splitext(fname)[1].lower(),
                                size_bytes=st.st_size,
                                modified_time=st.st_mtime,
                                is_directory=False,
                                folder_type=folder_type,
                            )
                            new_entries[fpath] = entry
                            count += 1
                            if count >= max_files_per_root:
                                break
                        except (OSError, PermissionError):
                            continue
                    if count >= max_files_per_root:
                        break
            except (OSError, PermissionError):
                continue

        self._entries.update(new_entries)
        self._last_index_time = time.time()
        logger.info("FileCatalog indexed %d files across %d roots", len(self._entries), len(self.watch_roots))
        return len(self._entries)

    def find(self, query: str, limit: int = 10) -> List[FileEntry]:
        """Searches files by name, extension, or recency."""
        if not self._entries or (time.time() - self._last_index_time > 300):
            self.index()

        q = query.lower().strip()
        matches: List[tuple[float, FileEntry]] = []

        # Keywords for type filtering
        pdf_only = "pdf" in q
        image_only = any(k in q for k in ["screenshot", "image", "photo", "png", "jpg"])

        for entry in self._entries.values():
            score = 0.0
            ename = entry.name.lower()

            if pdf_only and entry.extension != ".pdf":
                continue
            if image_only and entry.extension not in (".png", ".jpg", ".jpeg", ".webp"):
                continue

            if q in ename:
                score += 10.0
                if ename.startswith(q):
                    score += 5.0
            else:
                # Token match
                tokens = [t for t in q.split() if len(t) > 2 and t not in ("the", "and", "for", "with", "yesterday", "recent")]
                matched_tokens = sum(1 for t in tokens if t in ename)
                if matched_tokens:
                    score += matched_tokens * 3.0

            if score > 0:
                # Recency bonus: files modified recently get a boost
                age_days = (time.time() - entry.modified_time) / 86400.0
                if age_days < 1:
                    score += 4.0
                elif age_days < 7:
                    score += 2.0
                matches.append((score, entry))

        matches.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in matches[:limit]]

    def get_recent_files(self, limit: int = 5, extension: Optional[str] = None) -> List[FileEntry]:
        if not self._entries:
            self.index()
        items = list(self._entries.values())
        if extension:
            items = [i for i in items if i.extension == extension.lower()]
        items.sort(key=lambda x: x.modified_time, reverse=True)
        return items[:limit]


_global_file_catalog: Optional[FileCatalog] = None


def get_file_catalog() -> FileCatalog:
    global _global_file_catalog
    if _global_file_catalog is None:
        _global_file_catalog = FileCatalog()
    return _global_file_catalog
