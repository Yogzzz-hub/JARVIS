from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from pydantic import Field
from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition


class BatchRenameInput(Contract):
    directory: str = Field(min_length=1, max_length=4096)
    pattern: str = Field(min_length=1, max_length=256)
    replacement: str = Field(max_length=256)
    dry_run: bool = True


class BatchRenameItem(Contract):
    original: str
    proposed: str
    applied: bool
    error: str | None = None


class BatchRenameOutput(Contract):
    items: tuple[BatchRenameItem, ...]
    dry_run: bool
    total_processed: int
    status: str


class BatchRenameTool(Tool):
    definition = ToolDefinition(
        name="batch_rename",
        description="Performs batch file renaming with preview, conflict safety, and per-item status reporting.",
        input_model=BatchRenameInput,
        output_model=BatchRenameOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=10.0,
        tags=("file", "batch", "f07"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: BatchRenameInput) -> dict[str, Any]:
        p = Path(arguments.directory)
        if not p.exists() or not p.is_dir():
            raise FileNotFoundError(f"Directory '{arguments.directory}' does not exist.")

        results: list[dict[str, Any]] = []
        for file in p.iterdir():
            if file.is_file() and arguments.pattern in file.name:
                new_name = file.name.replace(arguments.pattern, arguments.replacement)
                target_path = p / new_name

                if target_path.exists() and target_path != file:
                    results.append({
                        "original": file.name,
                        "proposed": new_name,
                        "applied": False,
                        "error": "Target filename already exists (collision skipped)",
                    })
                    continue

                applied = False
                error_msg = None
                if not arguments.dry_run:
                    try:
                        file.rename(target_path)
                        applied = True
                    except Exception as exc:
                        error_msg = str(exc)

                results.append({
                    "original": file.name,
                    "proposed": new_name,
                    "applied": applied,
                    "error": error_msg,
                })

        return {
            "items": tuple(BatchRenameItem(**r) for r in results),
            "dry_run": arguments.dry_run,
            "total_processed": len(results),
            "status": "preview" if arguments.dry_run else "completed",
        }
