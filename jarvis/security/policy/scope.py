"""Task-Scoped Capability Access Manager for JARVIS EDGE.

Enforces principle of least privilege: LLM/Agent never has permanent unrestricted
computer access. For each task, temporary capability grants are issued based on intent
and context, and revoked immediately upon task completion.
"""
from __future__ import annotations

import contextlib
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, Iterator, Optional, Set

logger = logging.getLogger("jarvis.security.scope")


class ComputerCapability(str, Enum):
    # Project capabilities
    PROJECT_READ = "project.read"
    PROJECT_WRITE = "project.write"
    PROJECT_TASK_START = "project.task.start"
    PROJECT_TASK_STOP = "project.task.stop"

    # File / folder capabilities
    FILE_READ = "file.read"
    FILE_SEARCH = "file.search"
    FILE_WRITE = "file.write"
    FILE_DELETE = "file.delete"

    # Code capabilities
    CODE_INDEX = "code.index"
    CODE_EDIT = "code.edit"
    GIT_READ = "git.read"
    GIT_WRITE = "git.write"
    TEST_RUN = "test.run"
    BUILD_RUN = "build.run"

    # Process & Runtime capabilities
    PROCESS_READ = "process.read"
    PROCESS_STOP = "process.stop"
    LOG_READ = "log.read"
    NETWORK_LOCAL_STATUS = "network.local_status"

    # Database capabilities
    DATABASE_STATUS = "database.status"
    DATABASE_READ = "database.read"
    DATABASE_MIGRATE = "database.migrate"

    # RAG capabilities
    RAG_QUERY = "rag.query"

    # Browser capabilities
    BROWSER_READ = "browser.read"
    BROWSER_NAVIGATE = "browser.navigate"
    BROWSER_SUBMIT = "browser.submit"
    FORM_AUTOFILL = "form.autofill"

    # IDE capabilities
    IDE_CONTROL = "ide.control"
    IDE_DICTATE = "ide.dictate"

    # Phone capabilities
    PHONE_READ = "phone.read"
    PHONE_CONTROL = "phone.control"
    PHONE_TRANSFER = "phone.transfer"

    # Assessment capability
    ASSESSMENT_PRACTICE = "assessment.practice"
    ASSESSMENT_ACTIVE_SOLVE = "assessment.active_solve"  # ALWAYS BLOCKED BY POLICY


# Base capabilities safe for general conversation and reading
READ_ONLY_BASE_CAPABILITIES: FrozenSet[str] = frozenset({
    ComputerCapability.FILE_SEARCH.value,
    ComputerCapability.FILE_READ.value,
    ComputerCapability.PROJECT_READ.value,
    ComputerCapability.RAG_QUERY.value,
    ComputerCapability.LOG_READ.value,
    ComputerCapability.PROCESS_READ.value,
    ComputerCapability.NETWORK_LOCAL_STATUS.value,
    ComputerCapability.DATABASE_STATUS.value,
    ComputerCapability.DATABASE_READ.value,
    ComputerCapability.GIT_READ.value,
    ComputerCapability.BROWSER_READ.value,
    ComputerCapability.PHONE_READ.value,
})

# Tool name -> Required capability mapping
TOOL_CAPABILITY_REQUIREMENTS: Dict[str, str] = {
    # Project tools
    "project_discover": ComputerCapability.PROJECT_READ.value,
    "project_scan": ComputerCapability.PROJECT_READ.value,
    "project_summarize": ComputerCapability.PROJECT_READ.value,
    "project_run": ComputerCapability.PROJECT_TASK_START.value,
    "project_stop": ComputerCapability.PROJECT_TASK_STOP.value,
    "project_status": ComputerCapability.NETWORK_LOCAL_STATUS.value,
    "project_logs": ComputerCapability.LOG_READ.value,

    # File tools
    "find_file": ComputerCapability.FILE_SEARCH.value,
    "open_file": ComputerCapability.FILE_READ.value,
    "read_file_metadata": ComputerCapability.FILE_READ.value,
    "create_folder": ComputerCapability.FILE_WRITE.value,
    "copy_file": ComputerCapability.FILE_WRITE.value,
    "move_file": ComputerCapability.FILE_WRITE.value,
    "rename_file": ComputerCapability.FILE_WRITE.value,
    "delete_file": ComputerCapability.FILE_DELETE.value,

    # Code tools
    "git_status": ComputerCapability.GIT_READ.value,
    "git_diff": ComputerCapability.GIT_READ.value,
    "code_search": ComputerCapability.CODE_INDEX.value,
    "code_edit": ComputerCapability.CODE_EDIT.value,
    "code_repair_loop": ComputerCapability.CODE_EDIT.value,
    "run_project_tests": ComputerCapability.TEST_RUN.value,
    "build_project": ComputerCapability.BUILD_RUN.value,
    "diagnose_error": ComputerCapability.LOG_READ.value,

    # Database tools
    "database_status": ComputerCapability.DATABASE_STATUS.value,
    "database_schema_read": ComputerCapability.DATABASE_READ.value,
    "database_connectivity_check": ComputerCapability.DATABASE_STATUS.value,

    # Browser tools
    "browser_autofill": ComputerCapability.FORM_AUTOFILL.value,
    "hackathon_autofill": ComputerCapability.FORM_AUTOFILL.value,
    "web_agent": ComputerCapability.BROWSER_NAVIGATE.value,

    # IDE tools
    "antigravity_ide_control": ComputerCapability.IDE_CONTROL.value,

    # Phone tools
    "android_key": ComputerCapability.PHONE_CONTROL.value,
    "android_input": ComputerCapability.PHONE_CONTROL.value,
    "android_open_url": ComputerCapability.PHONE_CONTROL.value,
    "android_dial": ComputerCapability.PHONE_CONTROL.value,
    "android_screenshot": ComputerCapability.PHONE_READ.value,
    "android_notifications": ComputerCapability.PHONE_READ.value,
    "android_tap_text": ComputerCapability.PHONE_CONTROL.value,
    "android_toggle": ComputerCapability.PHONE_CONTROL.value,
    "android_pull_file": ComputerCapability.PHONE_TRANSFER.value,
    "android_push_file": ComputerCapability.PHONE_TRANSFER.value,

    # Assessment tool
    "exam_assessment_helper": ComputerCapability.ASSESSMENT_PRACTICE.value,
}


@dataclass
class TaskScope:
    task_id: str
    granted_capabilities: Set[str] = field(default_factory=set)
    target_project_root: Optional[str] = None
    target_files: Set[str] = field(default_factory=set)
    created_at: float = 0.0

    def allows(self, capability: str) -> bool:
        return capability in self.granted_capabilities

    def check_tool(self, tool_name: str) -> tuple[bool, str]:
        required = TOOL_CAPABILITY_REQUIREMENTS.get(tool_name)
        if not required:
            # Tools not listed in requirement map are permitted under default baseline
            return True, ""
        if required in self.granted_capabilities:
            return True, ""
        return False, f"Capability '{required}' is not granted for this task scope."


class TaskScopeManager:
    """Manages active capability grants scoped to specific user requests and tasks."""

    def __init__(self) -> None:
        self._active_scopes: Dict[str, TaskScope] = {}

    def get_scope(self, task_id: str | None) -> Optional[TaskScope]:
        if not task_id:
            return None
        return self._active_scopes.get(task_id)

    def create_scope(
        self,
        task_id: str,
        capabilities: Set[str],
        project_root: Optional[str] = None,
        target_files: Optional[Set[str]] = None,
    ) -> TaskScope:
        scope = TaskScope(
            task_id=task_id,
            granted_capabilities=set(capabilities),
            target_project_root=project_root,
            target_files=target_files or set(),
        )
        self._active_scopes[task_id] = scope
        logger.debug("TaskScope created for %s with %d capabilities", task_id, len(capabilities))
        return scope

    def derive_capabilities(self, user_text: str, intent: Optional[str] = None) -> Set[str]:
        """Derives least-privilege capability grants deterministically from text and intent."""
        caps: Set[str] = set(READ_ONLY_BASE_CAPABILITIES)
        t = user_text.lower()

        # Project run / start
        if re.search(r"\b(run|start|launch|bring up|spin up|execute)\b", t) and re.search(r"\b(project|automate|frontend|backend|app|service|server)\b", t):
            caps.update([
                ComputerCapability.PROJECT_READ.value,
                ComputerCapability.PROJECT_TASK_START.value,
                ComputerCapability.PROCESS_READ.value,
                ComputerCapability.LOG_READ.value,
                ComputerCapability.NETWORK_LOCAL_STATUS.value,
                ComputerCapability.DATABASE_STATUS.value,
            ])

        # Project stop
        if re.search(r"\b(stop|kill|shutdown|terminate|down)\b", t) and re.search(r"\b(project|automate|frontend|backend|app|service|server)\b", t):
            caps.update([
                ComputerCapability.PROJECT_TASK_STOP.value,
                ComputerCapability.PROCESS_STOP.value,
                ComputerCapability.PROCESS_READ.value,
            ])

        # Coding / Fixing / Editing
        if re.search(r"\b(fix|repair|patch|edit|modify|update|change|write|refactor|add feature)\b", t):
            caps.update([
                ComputerCapability.PROJECT_READ.value,
                ComputerCapability.PROJECT_WRITE.value,
                ComputerCapability.CODE_EDIT.value,
                ComputerCapability.CODE_INDEX.value,
                ComputerCapability.GIT_READ.value,
                ComputerCapability.GIT_WRITE.value,
                ComputerCapability.TEST_RUN.value,
                ComputerCapability.BUILD_RUN.value,
                ComputerCapability.FILE_WRITE.value,
                ComputerCapability.LOG_READ.value,
            ])

        # Testing
        if re.search(r"\b(test|tests|pytest|check tests|run test)\b", t):
            caps.update([
                ComputerCapability.PROJECT_READ.value,
                ComputerCapability.TEST_RUN.value,
                ComputerCapability.LOG_READ.value,
            ])

        # Building
        if re.search(r"\b(build|compile|bundle)\b", t):
            caps.update([
                ComputerCapability.PROJECT_READ.value,
                ComputerCapability.BUILD_RUN.value,
                ComputerCapability.LOG_READ.value,
            ])

        # Database
        if re.search(r"\b(db|database|postgres|sql|sqlite|mongo|mysql|migrate)\b", t):
            caps.update([
                ComputerCapability.DATABASE_STATUS.value,
                ComputerCapability.DATABASE_READ.value,
            ])
            if re.search(r"\b(migrate|migration)\b", t):
                caps.add(ComputerCapability.DATABASE_MIGRATE.value)

        # Form autofill
        if re.search(r"\b(fill|form|hackathon|register|registration|apply|submission)\b", t):
            caps.add(ComputerCapability.FORM_AUTOFILL.value)
            caps.add(ComputerCapability.BROWSER_NAVIGATE.value)

        # Browser
        if re.search(r"\b(chrome|browser|web|url|search|page|website)\b", t):
            caps.add(ComputerCapability.BROWSER_READ.value)
            caps.add(ComputerCapability.BROWSER_NAVIGATE.value)

        # IDE
        if re.search(r"\b(ide|antigravity|vscode|prompt|dictat|typing|tab|editor)\b", t):
            caps.add(ComputerCapability.IDE_CONTROL.value)
            caps.add(ComputerCapability.IDE_DICTATE.value)

        # Phone control & transfer
        if re.search(r"\b(phone|android|mobile|send to phone|pull from phone)\b", t):
            caps.add(ComputerCapability.PHONE_READ.value)
            caps.add(ComputerCapability.PHONE_CONTROL.value)
            caps.add(ComputerCapability.PHONE_TRANSFER.value)

        # File deletion requires explicit grant
        if re.search(r"\b(delete|remove|erase|trash)\b", t) and re.search(r"\b(file|folder|dir|log)\b", t):
            caps.add(ComputerCapability.FILE_DELETE.value)

        # Assessment / Quiz handling
        if re.search(r"\b(exam|quiz|test|assessment|question|homework|study)\b", t):
            # Practice / study is granted; active exam auto-solving is NEVER granted
            caps.add(ComputerCapability.ASSESSMENT_PRACTICE.value)

        return caps

    def revoke_scope(self, task_id: str) -> None:
        if task_id in self._active_scopes:
            del self._active_scopes[task_id]
            logger.debug("TaskScope revoked for %s", task_id)

    @contextlib.contextmanager
    def scoped_task(
        self,
        task_id: str,
        capabilities: Set[str],
        project_root: Optional[str] = None,
    ) -> Iterator[TaskScope]:
        scope = self.create_scope(task_id, capabilities, project_root)
        try:
            yield scope
        finally:
            self.revoke_scope(task_id)


_global_task_scope_manager: Optional[TaskScopeManager] = None


def get_task_scope_manager() -> TaskScopeManager:
    global _global_task_scope_manager
    if _global_task_scope_manager is None:
        _global_task_scope_manager = TaskScopeManager()
    return _global_task_scope_manager
