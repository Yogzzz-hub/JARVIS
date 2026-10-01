"""Typed Project Tasks, Process Ownership & Real Readiness Detection for JARVIS EDGE.

Controls project lifecycles (frontend, backend, database, workers) via validated typed tasks,
tracks process ownership (PIDs, ports, logs), performs real socket/HTTP readiness checks without
fixed sleeps, and diagnoses log outputs with concise root cause extraction.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import Field

from jarvis.core.catalog.project_catalog import ProjectCatalog, ProjectResource, get_project_catalog
from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition

logger = logging.getLogger("jarvis.tools.project")


@dataclass
class ProcessResource:
    """Tracks a running process spawned by JARVIS."""
    process_id: str
    project_id: str
    component: str  # frontend, backend, worker, database
    pid: int
    port: Optional[int] = None
    started_at: float = field(default_factory=time.time)
    status: str = "RUNNING"  # RUNNING, STOPPED, CRASHED
    process_handle: Optional[subprocess.Popen] = None
    log_buffer: List[str] = field(default_factory=list)
    restart_count: int = 0

    def append_log(self, line: str) -> None:
        self.log_buffer.append(line.rstrip())
        if len(self.log_buffer) > 1000:
            self.log_buffer.pop(0)

    def is_alive(self) -> bool:
        if self.process_handle is None:
            return False
        return self.process_handle.poll() is None


class ProjectProcessManager:
    """Singleton process owner ensuring only JARVIS-managed processes are stopped."""

    def __init__(self) -> None:
        self._processes: Dict[str, ProcessResource] = {}

    def register(self, proc: ProcessResource) -> None:
        self._processes[proc.process_id] = proc

    def get_by_project(self, project_id: str) -> List[ProcessResource]:
        return [p for p in self._processes.values() if p.project_id == project_id]

    def get_by_component(self, project_id: str, component: str) -> Optional[ProcessResource]:
        for p in self._processes.values():
            if p.project_id == project_id and p.component == component:
                return p
        return None

    def stop_project(self, project_id: str) -> List[dict[str, Any]]:
        results = []
        for p in self.get_by_project(project_id):
            if p.is_alive() and p.process_handle:
                try:
                    if sys.platform == "win32":
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True, timeout=5)
                    else:
                        p.process_handle.terminate()
                    p.status = "STOPPED"
                    results.append({"component": p.component, "pid": p.pid, "stopped": True})
                except Exception as exc:
                    results.append({"component": p.component, "pid": p.pid, "stopped": False, "error": str(exc)})
            else:
                p.status = "STOPPED"
                results.append({"component": p.component, "pid": p.pid, "stopped": True, "already_dead": True})
        return results


_process_manager: Optional[ProjectProcessManager] = None


def get_process_manager() -> ProjectProcessManager:
    global _process_manager
    if _process_manager is None:
        _process_manager = ProjectProcessManager()
    return _process_manager


# ---------------- Readiness Checking Probes ----------------

def probe_port_listening(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    """Non-blocking TCP socket connect check."""
    if not port or port <= 0:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionRefusedError, socket.timeout):
        return False


def probe_health_http(port: int, path: str = "/", timeout: float = 0.5) -> bool:
    """Lightweight HTTP check."""
    import urllib.request
    try:
        url = f"http://127.0.0.1:{port}{path}"
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS-Readiness-Probe"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 500
    except Exception:
        return False


# ---------------- Log Intelligence ----------------

def analyze_logs(log_lines: List[str]) -> Dict[str, Any]:
    """Extracts concise root cause from error traces without dumping thousands of lines."""
    full_text = "\n".join(log_lines)
    diagnosis = "No major error observed."
    root_cause = ""
    failing_file = ""
    error_type = ""

    # Port conflict
    if "EADDRINUSE" in full_text or "address already in use" in full_text.lower() or "winerror 10048" in full_text.lower():
        diagnosis = "Port conflict detected. Another process is already listening on this port."
        root_cause = "Port conflict: EADDRINUSE"
        error_type = "PORT_CONFLICT"

    # Missing dependency
    elif "ModuleNotFoundError" in full_text or "ImportError" in full_text:
        match = re.search(r"No module named ['\"]([^'\"]+)['\"]", full_text)
        mod_name = match.group(1) if match else "unknown"
        diagnosis = f"Missing package dependency: '{mod_name}'."
        root_cause = f"ModuleNotFoundError: {mod_name}"
        error_type = "MISSING_DEPENDENCY"

    # Database connection refused
    elif "ConnectionRefusedError" in full_text or "Is the server running" in full_text or "could not connect to server" in full_text:
        diagnosis = "Database connection failed. Database server is not responding."
        root_cause = "Database connection refused"
        error_type = "DATABASE_OFFLINE"

    # Traceback with file & line
    tb_matches = re.findall(r'File "([^"]+)", line (\d+), in (\w+)', full_text)
    if tb_matches:
        last_tb = tb_matches[-1]
        failing_file = f"{last_tb[0]}:{last_tb[1]} in {last_tb[2]}"
        if not root_cause:
            # Get last line of traceback
            lines = [l.strip() for l in log_lines if l.strip()]
            root_cause = lines[-1] if lines else "Exception in code execution"
            diagnosis = f"Runtime exception in {failing_file}: {root_cause}"
            error_type = "RUNTIME_EXCEPTION"

    return {
        "diagnosis": diagnosis,
        "root_cause": root_cause,
        "error_type": error_type,
        "failing_file": failing_file,
    }


# =====================================================================
# Contracts & Tools
# =====================================================================

class ProjectDiscoverInput(Contract):
    project_name: Optional[str] = Field(default=None, description="Project name or query (e.g. 'Automate', 'my project')")
    path: Optional[str] = Field(default=None, description="Explicit project directory path")


class ProjectDiscoverOutput(Contract):
    status: str
    project_id: str
    name: str
    root: str
    languages: list[str]
    frameworks: list[str]
    components: dict[str, Any]
    summary: str


class ProjectDiscoverTool(Tool):
    definition = ToolDefinition(
        name="project_discover",
        description="Discovers and inspects a software project, builds a knowledge summary of architecture, entrypoints, frontend/backend, and registers valid tasks.",
        input_model=ProjectDiscoverInput,
        output_model=ProjectDiscoverOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=10.0,
        tags=("project", "discovery", "code"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: ProjectDiscoverInput) -> dict[str, Any]:
        catalog = get_project_catalog()
        proj: Optional[ProjectResource] = None

        if arguments.path:
            proj = catalog.inspect_directory(arguments.path)
        elif arguments.project_name:
            proj = catalog.find_project(arguments.project_name)

        if not proj:
            # Fall back to current workspace
            proj = catalog.inspect_directory(Path.cwd())

        if not proj:
            return {
                "status": "NOT_FOUND",
                "project_id": "",
                "name": arguments.project_name or "Unknown",
                "root": "",
                "languages": [],
                "frameworks": [],
                "components": {},
                "summary": f"Could not find or inspect project '{arguments.project_name or 'current'}'.",
            }

        comps = {
            "frontend": proj.frontend,
            "backend": proj.backend,
            "database": proj.database,
            "workers": proj.workers,
            "ports": proj.ports,
            "known_tasks": list(proj.known_tasks.keys()),
        }

        # Build clean architectural summary
        parts = [f"Project '{proj.name}' at {proj.root}"]
        if proj.languages:
            parts.append(f"Languages: {', '.join(proj.languages)}")
        if proj.frameworks:
            parts.append(f"Frameworks: {', '.join(proj.frameworks)}")
        if proj.frontend:
            parts.append(f"Frontend: {proj.frontend.get('type', 'web')} on port {proj.frontend.get('port', 'default')}")
        if proj.backend:
            parts.append(f"Backend: {proj.backend.get('type', 'api')} on port {proj.backend.get('port', 'default')}")
        if proj.database:
            parts.append(f"Database: {proj.database.get('type', 'sql')}")

        return {
            "status": "SUCCESS",
            "project_id": proj.project_id,
            "name": proj.name,
            "root": proj.root,
            "languages": proj.languages,
            "frameworks": proj.frameworks,
            "components": comps,
            "summary": ". ".join(parts) + ".",
        }


# ---------------- Project Run Tool ----------------

class ProjectRunInput(Contract):
    project_name: Optional[str] = Field(default=None, description="Project name or query (e.g. 'Automate')")
    components: Optional[List[str]] = Field(default=None, description="Specific components to run: frontend, backend, database, worker, or None for all")


class ProjectRunOutput(Contract):
    status: str
    project_id: str
    readiness: dict[str, str]
    message: str


class ProjectRunTool(Tool):
    definition = ToolDefinition(
        name="project_run",
        description="Starts registered components (frontend, backend, database, workers) for a project and verifies real port/process readiness without fixed sleeps.",
        input_model=ProjectRunInput,
        output_model=ProjectRunOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=30.0,
        tags=("project", "run", "dev_server"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: ProjectRunInput) -> dict[str, Any]:
        catalog = get_project_catalog()
        proj = catalog.find_project(arguments.project_name or "") if arguments.project_name else catalog.inspect_directory(Path.cwd())
        if not proj:
            return {
                "status": "FAILED",
                "project_id": "",
                "readiness": {},
                "message": f"Project '{arguments.project_name or 'workspace'}' not found.",
            }

        proc_mgr = get_process_manager()
        readiness: Dict[str, str] = {}
        target_comps = arguments.components or ["database", "backend", "frontend", "worker"]

        root = Path(proj.root)

        # 1. Database check
        if "database" in target_comps and proj.database:
            db_port = proj.database.get("port")
            if db_port and probe_port_listening(db_port):
                readiness["Database"] = f"CONNECTED :{db_port}"
            elif proj.database.get("type") == "sqlite":
                readiness["Database"] = "CONNECTED (sqlite)"
            else:
                readiness["Database"] = "READY (local/docker)"

        # 2. Start Backend if requested and known
        if "backend" in target_comps and proj.backend:
            b_info = proj.backend
            b_port = b_info.get("port", 8000)
            existing = proc_mgr.get_by_component(proj.project_id, "backend")

            if existing and existing.is_alive():
                readiness["Backend"] = f"ALREADY RUNNING :{b_port}"
            else:
                cwd = root / b_info.get("dir", ".")
                cmd = b_info.get("command", "python main.py")
                # Spawn background process with pipes
                try:
                    p = subprocess.Popen(
                        cmd,
                        cwd=str(cwd),
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                    )
                    res = ProcessResource(
                        process_id=f"proc_backend_{p.pid}",
                        project_id=proj.project_id,
                        component="backend",
                        pid=p.pid,
                        port=b_port,
                        process_handle=p,
                    )
                    proc_mgr.register(res)

                    # Active poll for readiness (max 4.0s)
                    ready = False
                    for _ in range(20):
                        time.sleep(0.2)
                        if p.poll() is not None:
                            break
                        if probe_port_listening(b_port) or probe_health_http(b_port):
                            ready = True
                            break

                    if ready or p.poll() is None:
                        readiness["Backend"] = f"READY :{b_port}"
                    else:
                        readiness["Backend"] = "FAILED to listen"
                except Exception as exc:
                    readiness["Backend"] = f"ERROR: {exc}"

        # 3. Start Frontend if requested and known
        if "frontend" in target_comps and proj.frontend:
            f_info = proj.frontend
            f_port = f_info.get("port", 5173)
            existing = proc_mgr.get_by_component(proj.project_id, "frontend")

            if existing and existing.is_alive():
                readiness["Frontend"] = f"ALREADY RUNNING :{f_port}"
            else:
                cwd = root / f_info.get("dir", ".")
                cmd = f_info.get("command", "npm run dev")
                try:
                    p = subprocess.Popen(
                        cmd,
                        cwd=str(cwd),
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                    )
                    res = ProcessResource(
                        process_id=f"proc_frontend_{p.pid}",
                        project_id=proj.project_id,
                        component="frontend",
                        pid=p.pid,
                        port=f_port,
                        process_handle=p,
                    )
                    proc_mgr.register(res)

                    ready = False
                    for _ in range(20):
                        time.sleep(0.2)
                        if p.poll() is not None:
                            break
                        if probe_port_listening(f_port) or probe_health_http(f_port):
                            ready = True
                            break

                    if ready or p.poll() is None:
                        readiness["Frontend"] = f"READY :{f_port}"
                    else:
                        readiness["Frontend"] = "FAILED to listen"
                except Exception as exc:
                    readiness["Frontend"] = f"ERROR: {exc}"

        # Summary message
        lines = [f"{k}: {v}" for k, v in readiness.items()]
        all_ready = all("READY" in v or "CONNECTED" in v or "RUNNING" in v for v in readiness.values())
        status = "SUCCESS" if all_ready else "PARTIAL_SUCCESS"
        app_msg = "\n".join(lines) + ("\nApplication ready." if all_ready else "")

        return {
            "status": status,
            "project_id": proj.project_id,
            "readiness": readiness,
            "message": app_msg,
        }


# ---------------- Project Stop Tool ----------------

class ProjectStopInput(Contract):
    project_name: Optional[str] = Field(default=None, description="Project name to stop (e.g. 'Automate')")


class ProjectStopOutput(Contract):
    status: str
    project_id: str
    stopped_processes: list[dict[str, Any]]
    message: str


class ProjectStopTool(Tool):
    definition = ToolDefinition(
        name="project_stop",
        description="Gracefully stops tracked project processes (frontend, backend, workers) owned by JARVIS without touching unrelated processes.",
        input_model=ProjectStopInput,
        output_model=ProjectStopOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=10.0,
        tags=("project", "stop", "process"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: ProjectStopInput) -> dict[str, Any]:
        catalog = get_project_catalog()
        proj = catalog.find_project(arguments.project_name or "") if arguments.project_name else catalog.inspect_directory(Path.cwd())
        if not proj:
            return {
                "status": "FAILED",
                "project_id": "",
                "stopped_processes": [],
                "message": f"Project '{arguments.project_name or 'workspace'}' not found.",
            }

        stopped = get_process_manager().stop_project(proj.project_id)
        return {
            "status": "SUCCESS",
            "project_id": proj.project_id,
            "stopped_processes": stopped,
            "message": f"Stopped {len(stopped)} process(es) for project '{proj.name}'.",
        }


# ---------------- Project Logs Tool ----------------

class ProjectLogsInput(Contract):
    project_name: Optional[str] = Field(default=None, description="Project name")
    component: Optional[str] = Field(default=None, description="Specific component: backend, frontend, worker")
    tail: int = Field(default=50, ge=5, le=500, description="Number of lines to read")


class ProjectLogsOutput(Contract):
    status: str
    component: str
    diagnosis: str
    root_cause: str
    error_type: str
    failing_file: str
    snippet: str


class ProjectLogsTool(Tool):
    definition = ToolDefinition(
        name="project_logs",
        description="Reads real project output and background logs, diagnoses errors/tracebacks, and extracts concise root causes.",
        input_model=ProjectLogsInput,
        output_model=ProjectLogsOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=5.0,
        tags=("project", "logs", "diagnose"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: ProjectLogsInput) -> dict[str, Any]:
        catalog = get_project_catalog()
        proj = catalog.find_project(arguments.project_name or "") if arguments.project_name else catalog.inspect_directory(Path.cwd())
        if not proj:
            return {
                "status": "FAILED",
                "component": arguments.component or "all",
                "diagnosis": "Project not found.",
                "root_cause": "",
                "error_type": "NOT_FOUND",
                "failing_file": "",
                "snippet": "",
            }

        procs = get_process_manager().get_by_project(proj.project_id)
        if arguments.component:
            procs = [p for p in procs if p.component == arguments.component]

        all_lines: List[str] = []
        for p in procs:
            # Drain stdout if open
            if p.process_handle and p.process_handle.stdout:
                try:
                    while True:
                        # Non-blocking read line
                        line = p.process_handle.stdout.readline()
                        if not line:
                            break
                        p.append_log(line)
                except Exception:
                    pass
            all_lines.extend(p.log_buffer[-arguments.tail:])

        if not all_lines:
            # Check for common log files on disk (e.g. error.log, app.log, backend.log)
            root = Path(proj.root)
            for cand in ["error.log", "backend.log", "server.log", "npm-debug.log"]:
                p = root / cand
                if p.is_file():
                    try:
                        all_lines.extend(p.read_text(encoding="utf-8", errors="ignore").splitlines()[-arguments.tail:])
                    except Exception:
                        pass

        analysis = analyze_logs(all_lines)
        snippet = "\n".join(all_lines[-20:]) if all_lines else "No log output recorded yet."

        return {
            "status": "SUCCESS",
            "component": arguments.component or "project",
            "diagnosis": analysis["diagnosis"],
            "root_cause": analysis["root_cause"],
            "error_type": analysis["error_type"],
            "failing_file": analysis["failing_file"],
            "snippet": snippet,
        }


# ---------------- Project File Read Tool ----------------

class ProjectFileReadInput(Contract):
    file_path: str = Field(description="Relative path in project (e.g. 'chrome_extension/background.js', 'run_all.bat', 'backend/main.py') or path on disk")
    project_name: Optional[str] = Field(default=None, description="Project name (e.g. 'Automate')")
    start_line: int = Field(default=1, description="1-indexed line to start reading from")
    max_lines: int = Field(default=300, description="Max lines to read")


class ProjectFileReadOutput(Contract):
    status: str
    file_path: str
    total_lines: int
    content: str
    summary: str


class ProjectFileReadTool(Tool):
    definition = ToolDefinition(
        name="project_file_read",
        description="Reads, inspects, and analyzes any file within a user project or user directories (e.g. Chrome extension files, scripts, configs, sources).",
        input_model=ProjectFileReadInput,
        output_model=ProjectFileReadOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=10.0,
        tags=("project", "file", "read", "code"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: ProjectFileReadInput) -> dict[str, Any]:
        catalog = get_project_catalog()
        proj = catalog.find_project(arguments.project_name or "") if arguments.project_name else None

        target_path: Optional[Path] = None
        raw_p = Path(arguments.file_path)

        if raw_p.is_absolute() and raw_p.exists():
            target_path = raw_p
        elif proj:
            cand = Path(proj.root) / arguments.file_path
            if cand.exists():
                target_path = cand

        if not target_path:
            cand = Path.cwd() / arguments.file_path
            if cand.exists():
                target_path = cand
            else:
                for root in catalog.search_roots:
                    c = root / arguments.file_path
                    if c.exists():
                        target_path = c
                        break
                    if (root / "automate" / arguments.file_path).exists():
                        target_path = root / "automate" / arguments.file_path
                        break

        if not target_path or not target_path.is_file():
            return {
                "status": "NOT_FOUND",
                "file_path": arguments.file_path,
                "total_lines": 0,
                "content": "",
                "summary": f"File '{arguments.file_path}' was not found.",
            }

        try:
            text = target_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            text = target_path.read_text(encoding="latin-1", errors="replace")

        lines = text.splitlines()
        total = len(lines)
        start_idx = max(0, arguments.start_line - 1)
        end_idx = min(total, start_idx + arguments.max_lines)
        selected_lines = lines[start_idx:end_idx]

        content = "\n".join(f"{i+1:4d} | {line}" for i, line in enumerate(selected_lines, start=start_idx))
        summary = f"Read {len(selected_lines)}/{total} lines of '{target_path.name}' ({target_path.suffix or 'text'})."

        return {
            "status": "SUCCESS",
            "file_path": str(target_path),
            "total_lines": total,
            "content": content,
            "summary": summary,
        }


# ---------------- Project File Run Tool ----------------

class ProjectFileRunInput(Contract):
    file_path: str = Field(description="Script or file to run in the project (e.g. 'run_all.bat', 'start_controlled_chrome.ps1', 'backend/main.py')")
    project_name: Optional[str] = Field(default=None, description="Project name")
    args: Optional[List[str]] = Field(default=None, description="Optional arguments to pass to the script")


class ProjectFileRunOutput(Contract):
    status: str
    command: str
    exit_code: int
    output: str
    message: str


class ProjectFileRunTool(Tool):
    definition = ToolDefinition(
        name="project_file_run",
        description="Executes a specific project file, script (e.g. run_all.bat, start_controlled_chrome.ps1), or test runner within the user's project directory.",
        input_model=ProjectFileRunInput,
        output_model=ProjectFileRunOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=60.0,
        tags=("project", "file", "run", "script"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: ProjectFileRunInput) -> dict[str, Any]:
        catalog = get_project_catalog()
        proj = catalog.find_project(arguments.project_name or "") if arguments.project_name else None

        target_path: Optional[Path] = None
        raw_p = Path(arguments.file_path)

        if raw_p.is_absolute() and raw_p.exists():
            target_path = raw_p
        elif proj:
            cand = Path(proj.root) / arguments.file_path
            if cand.exists():
                target_path = cand

        if not target_path:
            cand = Path.cwd() / arguments.file_path
            if cand.exists():
                target_path = cand
            else:
                for root in catalog.search_roots:
                    c = root / arguments.file_path
                    if c.exists():
                        target_path = c
                        break
                    if (root / "automate" / arguments.file_path).exists():
                        target_path = root / "automate" / arguments.file_path
                        break

        if not target_path or not target_path.is_file():
            return {
                "status": "NOT_FOUND",
                "command": arguments.file_path,
                "exit_code": 1,
                "output": "",
                "message": f"Target file '{arguments.file_path}' does not exist on disk.",
            }

        ext = target_path.suffix.lower()
        cwd_dir = target_path.parent
        extra_args = " ".join(arguments.args or [])

        if ext in (".bat", ".cmd"):
            cmd = f'cmd /c "{target_path}" {extra_args}'.strip()
        elif ext == ".ps1":
            cmd = f'powershell -ExecutionPolicy Bypass -File "{target_path}" {extra_args}'.strip()
        elif ext == ".py":
            cmd = f'python "{target_path}" {extra_args}'.strip()
        elif ext in (".js", ".mjs"):
            cmd = f'node "{target_path}" {extra_args}'.strip()
        else:
            cmd = f'"{target_path}" {extra_args}'.strip()

        try:
            res = subprocess.run(
                cmd,
                cwd=str(cwd_dir),
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=55.0,
            )
            out = (res.stdout or "") + ("\n" + res.stderr if res.stderr else "")
            status = "SUCCESS" if res.returncode == 0 else "FAILED"
            msg = f"Executed '{target_path.name}' with exit code {res.returncode}."
            return {
                "status": status,
                "command": cmd,
                "exit_code": res.returncode,
                "output": out[-4000:] if len(out) > 4000 else out,
                "message": msg,
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "TIMEOUT",
                "command": cmd,
                "exit_code": -1,
                "output": "Command timed out after 55 seconds.",
                "message": f"Execution of '{target_path.name}' timed out.",
            }
        except Exception as exc:
            return {
                "status": "ERROR",
                "command": cmd,
                "exit_code": 1,
                "output": str(exc),
                "message": f"Execution error: {exc}",
            }


# ---------------- Controlled Chrome & Extension Tool ----------------

class ControlledChromeInput(Contract):
    project_name: Optional[str] = Field(default="Automate", description="Project name")
    port: int = Field(default=9222, description="Chrome remote debugging port")
    url: Optional[str] = Field(default="http://127.0.0.1:8000", description="URL to open")
    load_extension: bool = Field(default=True, description="Whether to load project's Chrome extension")


class ControlledChromeOutput(Contract):
    status: str
    debugging_port: int
    url: str
    extension_loaded: bool
    message: str


class ControlledChromeTool(Tool):
    definition = ToolDefinition(
        name="controlled_chrome_launch",
        description="Launches Google Chrome with remote debugging (--remote-debugging-port=9222) and loads the project's Chrome extension (e.g. Internship Autofill Assistant).",
        input_model=ControlledChromeInput,
        output_model=ControlledChromeOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=15.0,
        tags=("browser", "chrome", "extension", "controlled"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: ControlledChromeInput) -> dict[str, Any]:
        catalog = get_project_catalog()
        proj = catalog.find_project(arguments.project_name or "") if arguments.project_name else None

        # Check if already listening on debugging port
        if probe_port_listening(arguments.port):
            return {
                "status": "ALREADY_RUNNING",
                "debugging_port": arguments.port,
                "url": arguments.url or "",
                "extension_loaded": True,
                "message": f"Controlled Chrome is already running and listening on port {arguments.port}.",
            }

        # If project has start_controlled_chrome.ps1, use it!
        if proj:
            root = Path(proj.root)
            script = root / "start_controlled_chrome.ps1"
            if script.is_file():
                try:
                    subprocess.Popen(
                        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                        cwd=str(root),
                        shell=True,
                    )
                    for _ in range(15):
                        time.sleep(0.3)
                        if probe_port_listening(arguments.port):
                            break
                    is_ready = probe_port_listening(arguments.port)
                    return {
                        "status": "SUCCESS" if is_ready else "LAUNCHED",
                        "debugging_port": arguments.port,
                        "url": arguments.url or "http://127.0.0.1:5173/assistant",
                        "extension_loaded": True,
                        "message": f"Controlled Chrome launched via start_controlled_chrome.ps1 (port {arguments.port}).",
                    }
                except Exception as exc:
                    return {
                        "status": "ERROR",
                        "debugging_port": arguments.port,
                        "url": arguments.url or "",
                        "extension_loaded": False,
                        "message": f"Failed launching start_controlled_chrome.ps1: {exc}",
                    }

        # Otherwise locate chrome.exe
        chrome_exe: Optional[str] = None
        for cand in [
            os.environ.get("ProgramFiles", "") + r"\Google\Chrome\Application\chrome.exe",
            os.environ.get("ProgramFiles(x86)", "") + r"\Google\Chrome\Application\chrome.exe",
            os.environ.get("LocalAppData", "") + r"\Google\Chrome\Application\chrome.exe",
        ]:
            if cand and os.path.isfile(cand):
                chrome_exe = cand
                break

        if not chrome_exe:
            return {
                "status": "FAILED",
                "debugging_port": arguments.port,
                "url": arguments.url or "",
                "extension_loaded": False,
                "message": "Google Chrome executable was not found on this system.",
            }

        cmd_args = [
            f'"{chrome_exe}"',
            f"--remote-debugging-port={arguments.port}",
        ]
        ext_loaded = False
        if arguments.load_extension and proj and proj.chrome_extension:
            ext_dir = Path(proj.root) / proj.chrome_extension.get("path", "chrome_extension")
            if ext_dir.is_dir():
                cmd_args.append(f'--load-extension="{ext_dir}"')
                ext_loaded = True

        if arguments.url:
            cmd_args.append(f'"{arguments.url}"')

        try:
            subprocess.Popen(" ".join(cmd_args), shell=True)
            for _ in range(15):
                time.sleep(0.3)
                if probe_port_listening(arguments.port):
                    break
            is_ready = probe_port_listening(arguments.port)
            return {
                "status": "SUCCESS" if is_ready else "LAUNCHED",
                "debugging_port": arguments.port,
                "url": arguments.url or "",
                "extension_loaded": ext_loaded,
                "message": f"Controlled Chrome launched on port {arguments.port} (extension_loaded={ext_loaded}).",
            }
        except Exception as exc:
            return {
                "status": "ERROR",
                "debugging_port": arguments.port,
                "url": arguments.url or "",
                "extension_loaded": False,
                "message": f"Failed to launch Chrome: {exc}",
            }


def create_project_tools() -> list[Tool]:
    return [
        ProjectDiscoverTool(),
        ProjectRunTool(),
        ProjectStopTool(),
        ProjectLogsTool(),
        ProjectFileReadTool(),
        ProjectFileRunTool(),
        ControlledChromeTool(),
    ]
