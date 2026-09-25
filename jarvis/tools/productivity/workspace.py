from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from pydantic import Field
from jarvis.config import ROOT
from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition

WORKSPACE_DIR = ROOT / "jarvis" / "data" / "workspaces"


class WorkspaceSaveInput(Contract):
    name: str = Field(min_length=1, max_length=128)
    folders: tuple[str, ...] = ()
    urls: tuple[str, ...] = ()
    notes_path: str | None = None
    editor_command: str | None = None
    timer_minutes: int | None = None


class WorkspaceSaveOutput(Contract):
    name: str
    manifest_path: str
    status: str


class WorkspaceLaunchInput(Contract):
    name: str = Field(min_length=1, max_length=128)


class WorkspaceLaunchOutput(Contract):
    name: str
    opened_folders: tuple[str, ...]
    opened_urls: tuple[str, ...]
    notes_path: str | None
    status: str


class SaveWorkspaceTool(Tool):
    definition = ToolDefinition(
        name="save_workspace",
        description="Saves a workspace manifest (notes, folders, browser tabs, timer) for future resumption.",
        input_model=WorkspaceSaveInput,
        output_model=WorkspaceSaveOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=5.0,
        tags=("workspace", "f04"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: WorkspaceSaveInput) -> dict[str, Any]:
        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        manifest_file = WORKSPACE_DIR / f"{arguments.name.lower().replace(' ', '_')}.json"
        data = {
            "name": arguments.name,
            "folders": list(arguments.folders),
            "urls": list(arguments.urls),
            "notes_path": arguments.notes_path,
            "editor_command": arguments.editor_command,
            "timer_minutes": arguments.timer_minutes,
            "saved_at": time.time(),
        }
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return {
            "name": arguments.name,
            "manifest_path": str(manifest_file),
            "status": "saved",
        }


class LaunchWorkspaceTool(Tool):
    definition = ToolDefinition(
        name="launch_workspace",
        description="Launches and restores a previously saved workspace manifest.",
        input_model=WorkspaceLaunchInput,
        output_model=WorkspaceLaunchOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=10.0,
        tags=("workspace", "f04"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: WorkspaceLaunchInput) -> dict[str, Any]:
        manifest_file = WORKSPACE_DIR / f"{arguments.name.lower().replace(' ', '_')}.json"
        if not manifest_file.exists():
            raise FileNotFoundError(f"Workspace manifest '{arguments.name}' does not exist.")

        with open(manifest_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return {
            "name": data["name"],
            "opened_folders": tuple(data.get("folders", [])),
            "opened_urls": tuple(data.get("urls", [])),
            "notes_path": data.get("notes_path"),
            "status": "restored",
        }
