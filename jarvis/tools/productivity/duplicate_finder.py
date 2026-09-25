from __future__ import annotations

import hashlib
import os
from collections import defaultdict
from pathlib import Path
from typing import Any
from pydantic import Field
from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition


class FindDuplicatesInput(Contract):
    directory: str = Field(min_length=1, max_length=4096)
    min_size_bytes: int = Field(default=1, ge=0)


class DuplicateGroup(Contract):
    sha256: str
    size_bytes: int
    file_paths: tuple[str, ...]


class FindDuplicatesOutput(Contract):
    directory: str
    duplicate_groups: tuple[DuplicateGroup, ...]
    total_duplicates: int
    wasted_bytes: int


def hash_file(path: Path, chunk_size: int = 65536) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


class DuplicateFinderTool(Tool):
    definition = ToolDefinition(
        name="find_duplicates",
        description="Finds verified duplicate files grouped first by exact byte size then SHA-256 content hash. Filenames alone are not duplicates.",
        input_model=FindDuplicatesInput,
        output_model=FindDuplicatesOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=30.0,
        tags=("file", "duplicate", "f08"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: FindDuplicatesInput) -> dict[str, Any]:
        p = Path(arguments.directory)
        if not p.exists() or not p.is_dir():
            raise FileNotFoundError(f"Directory '{arguments.directory}' does not exist.")

        # 1. Group by file size
        size_groups: dict[int, list[Path]] = defaultdict(list)
        for item in p.rglob("*"):
            if item.is_file() and not item.is_symlink():
                try:
                    s = item.stat().st_size
                    if s >= arguments.min_size_bytes:
                        size_groups[s].append(item)
                except (OSError, PermissionError):
                    continue

        # 2. For matching sizes, compute SHA-256
        hash_groups: dict[tuple[int, str], list[str]] = defaultdict(list)
        for size, files in size_groups.items():
            if len(files) > 1:
                for f in files:
                    try:
                        digest = hash_file(f)
                        hash_groups[(size, digest)].append(str(f))
                    except (OSError, PermissionError):
                        continue

        # 3. Format output
        duplicates: list[DuplicateGroup] = []
        wasted_bytes = 0
        for (size, digest), matched_paths in hash_groups.items():
            if len(matched_paths) > 1:
                duplicates.append(
                    DuplicateGroup(
                        sha256=digest,
                        size_bytes=size,
                        file_paths=tuple(matched_paths),
                    )
                )
                wasted_bytes += size * (len(matched_paths) - 1)

        return {
            "directory": str(p),
            "duplicate_groups": tuple(duplicates),
            "total_duplicates": sum(len(d.file_paths) - 1 for d in duplicates),
            "wasted_bytes": wasted_bytes,
        }
