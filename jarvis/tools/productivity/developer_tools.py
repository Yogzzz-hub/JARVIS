from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
from pydantic import Field
from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition

SECRET_PATTERNS = [
    r"(?i)(password|secret|key|token|auth|bearer)\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.\$\/]{8,})['\"]?",
    r"(?i)AIza[0-9A-Za-z-_]{35}",
    r"(?i)sk-[A-Za-z0-9]{20,}",
]


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = re.sub(pattern, r"[REDACTED_SECRET]", redacted)
    return redacted


class GitStatusInput(Contract):
    repo_path: str = Field(min_length=1, max_length=4096)


class GitStatusOutput(Contract):
    branch: str
    modified_files: tuple[str, ...]
    untracked_files: tuple[str, ...]
    status: str


class RunTestsInput(Contract):
    repo_path: str = Field(min_length=1, max_length=4096)
    test_target: str = Field(default=".", max_length=512)


class RunTestsOutput(Contract):
    passed: bool
    summary: str
    exit_code: int


class DiagnoseErrorInput(Contract):
    error_log: str = Field(min_length=1, max_length=20000)


class DiagnoseErrorOutput(Contract):
    diagnosis: str
    suggested_fix: str
    redacted_log: str


class GitStatusTool(Tool):
    definition = ToolDefinition(
        name="git_status",
        description="Inspects Git status and modified files in an approved developer repository without remote mutations.",
        input_model=GitStatusInput,
        output_model=GitStatusOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=10.0,
        tags=("developer", "git", "f18"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: GitStatusInput) -> dict[str, Any]:
        p = Path(arguments.repo_path)
        if not p.exists() or not (p / ".git").exists():
            raise FileNotFoundError(f"Path '{arguments.repo_path}' is not a valid Git repository.")

        git = shutil.which("git")
        if not git:
            raise RuntimeError("Git is not installed on system.")

        proc = subprocess.run(
            [git, "-C", str(p), "status", "--porcelain", "-b"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        lines = proc.stdout.splitlines()
        branch = lines[0].replace("## ", "") if lines else "unknown"
        modified: list[str] = []
        untracked: list[str] = []

        for line in lines[1:]:
            if line.startswith("??"):
                untracked.append(line[3:].strip())
            else:
                modified.append(line[3:].strip())

        return {
            "branch": branch,
            "modified_files": tuple(modified),
            "untracked_files": tuple(untracked),
            "status": "clean" if not modified and not untracked else "dirty",
        }


class RunProjectTestsTool(Tool):
    definition = ToolDefinition(
        name="run_project_tests",
        description="Runs local unit tests for an approved trusted project and collects pass/fail metrics.",
        input_model=RunTestsInput,
        output_model=RunTestsOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=60.0,
        tags=("developer", "test", "f18"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: RunTestsInput) -> dict[str, Any]:
        p = Path(arguments.repo_path)
        if not p.exists():
            raise FileNotFoundError(f"Project path '{arguments.repo_path}' not found.")

        # Safe local test run using pytest
        proc = subprocess.run(
            ["pytest", arguments.test_target, "-q"],
            cwd=str(p),
            capture_output=True,
            text=True,
            timeout=60,
        )
        return {
            "passed": proc.returncode == 0,
            "summary": (proc.stdout or proc.stderr)[:500].strip(),
            "exit_code": proc.returncode,
        }


class DiagnoseErrorTool(Tool):
    definition = ToolDefinition(
        name="diagnose_error",
        description="Analyzes error stack traces or logs, redacts sensitive tokens, and suggests a concrete fix.",
        input_model=DiagnoseErrorInput,
        output_model=DiagnoseErrorOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=10.0,
        tags=("developer", "diagnosis", "f19"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: DiagnoseErrorInput) -> dict[str, Any]:
        redacted = redact_secrets(arguments.error_log)
        
        # Heuristic diagnosis
        diagnosis = "Standard error trace detected."
        suggested_fix = "Review the top of the stack trace and verify function arguments and imports."
        if "ModuleNotFoundError" in redacted or "ImportError" in redacted:
            diagnosis = "Missing Python module or package dependency."
            suggested_fix = "Install the missing package into the active virtual environment."
        elif "PermissionError" in redacted or "AccessDenied" in redacted:
            diagnosis = "Insufficient file system or process permissions."
            suggested_fix = "Verify file permissions or check if another process holds an exclusive lock."
        elif "FileNotFoundError" in redacted:
            diagnosis = "Target file or directory does not exist."
            suggested_fix = "Verify canonical path resolution and ensure parent directories are created."

        return {
            "diagnosis": diagnosis,
            "suggested_fix": suggested_fix,
            "redacted_log": redacted[:1000],
        }
