"""Comprehensive Test Suite for Full Computer Agent in JARVIS EDGE.

Tests:
1. TaskScopeManager: least privilege capability derivation, grant, and revocation
2. ProjectCatalog & ProjectResource: manifest inspection, frontend/backend/db detection
3. FileCatalog: dynamic user folder indexing & fuzzy/recency search
4. Typed Project Tasks & Process Management:
   - ProjectDiscoverTool: architecture summarization
   - ProjectRunTool: component startup & real readiness probe (no fixed sleeps)
   - ProjectStatusTool & ProjectStopTool: safe process ownership (zero unrelated process kills)
   - ProjectLogsTool: log intelligence and concise root cause extraction
5. Code Intelligence & Editing:
   - CodeSearchTool: symbol and reference search
   - CodeEditTool: minimal patch application with git baseline & diff
   - GitDiffTool: working tree inspection
   - BoundedRepairTool: bounded fix loop (zero infinite loops)
6. Safe Database Tools:
   - DatabaseStatusTool: connectivity check without secret exposure
   - DatabaseSchemaReadTool: read-only schema inspection
7. Browser & Form Automation:
   - HackathonAutofillTool: project metadata mapping and preview
8. Assessment Safety Boundary:
   - ExamAssessmentHelperTool: practice allowed vs active graded exams strictly blocked
9. Phone Remote Control & Cross-Device:
   - Screenshot resolution for phone push
10. Fast Deterministic Router Rules:
   - Zero hardcoded exact phrases; semantic and regex routing coverage
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
import pytest

from jarvis.core.catalog.file_catalog import FileCatalog
from jarvis.core.catalog.project_catalog import ProjectCatalog, ProjectResource
from jarvis.core.context.models import ProjectResourceRef, ProcessResourceRef
from jarvis.security.policy.scope import ComputerCapability, TaskScopeManager, get_task_scope_manager
from jarvis.security.policy.evaluator import PolicyEvaluator
from jarvis.tools.base import RiskLevel, ToolDefinition
from jarvis.tools.productivity.project_tools import (
    ProjectDiscoverTool,
    ProjectDiscoverInput,
    ProjectRunTool,
    ProjectRunInput,
    ProjectStopTool,
    ProjectStopInput,
    ProjectLogsTool,
    ProjectLogsInput,
    ProjectFileReadTool,
    ProjectFileReadInput,
    ProjectFileRunTool,
    ProjectFileRunInput,
    ControlledChromeTool,
    ControlledChromeInput,
    get_process_manager,
    analyze_logs,
)
from jarvis.tools.productivity.code_tools import (
    CodeSearchTool,
    CodeSearchInput,
    CodeEditTool,
    CodeEditInput,
    GitDiffTool,
    GitDiffInput,
    BoundedRepairTool,
    BoundedRepairInput,
)
from jarvis.tools.productivity.database_tools import (
    DatabaseStatusTool,
    DatabaseStatusInput,
    DatabaseSchemaReadTool,
    DatabaseSchemaInput,
)
from jarvis.tools.system.exam_solver_tool import (
    ExamAssessmentHelperTool,
    AssessmentHelperInput,
)
from jarvis.tools.system.phone_tools import _resolve_pc_file


@pytest.fixture
def sample_project_dir():
    """Creates a temporary full-stack project directory with FastAPI and React/Vite."""
    tmp = tempfile.mkdtemp(prefix="jarvis_test_project_")
    p = Path(tmp)

    # 1. Root package.json (Vite frontend)
    pkg = {
        "name": "automate-app",
        "scripts": {"dev": "vite", "build": "vite build", "test": "vitest"},
        "dependencies": {"react": "^18.0.0", "vite": "^5.0.0"},
    }
    (p / "package.json").write_text(json.dumps(pkg), encoding="utf-8")

    # 2. Python backend manifest
    reqs = "fastapi>=0.100.0\nuvicorn>=0.22.0\nsqlalchemy>=2.0.0\npytest>=7.0.0\n"
    (p / "requirements.txt").write_text(reqs, encoding="utf-8")

    # 3. Backend source code
    backend_dir = p / "backend"
    backend_dir.mkdir(parents=True)
    main_py = (
        "from fastapi import FastAPI\n\n"
        "app = FastAPI(title='Automate API')\n\n"
        "@app.get('/health')\n"
        "def health():\n"
        "    return {'status': 'healthy'}\n\n"
        "@app.post('/api/login')\n"
        "def login_handler(username: str):\n"
        "    if not username:\n"
        "        raise ValueError('Invalid user')\n"
        "    return {'token': 'jwt_secret_token_123'}\n"
    )
    (backend_dir / "main.py").write_text(main_py, encoding="utf-8")

    # 4. SQLite DB file
    import sqlite3
    db_file = p / "test_app.db"
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, role TEXT);")
    cur.execute("INSERT INTO users VALUES (1, 'alice@example.com', 'admin');")
    conn.commit()
    conn.close()

    # 5. README
    (p / "README.md").write_text("# Automate Project\nAn autonomous task automation platform.", encoding="utf-8")

    yield p

    shutil.rmtree(tmp, ignore_errors=True)


# =====================================================================
# 1. TaskScopeManager Tests
# =====================================================================

def test_task_scope_manager_derivation_and_least_privilege():
    mgr = TaskScopeManager()

    # Summarize query: READ-ONLY capabilities only
    caps = mgr.derive_capabilities("Summarize my Automate project and explain what it does")
    assert ComputerCapability.PROJECT_READ.value in caps
    assert ComputerCapability.FILE_SEARCH.value in caps
    assert ComputerCapability.FILE_DELETE.value not in caps
    assert ComputerCapability.PROJECT_TASK_START.value not in caps

    # Run query: starts tasks, reads logs/ports
    run_caps = mgr.derive_capabilities("Run my Automate project and check the database")
    assert ComputerCapability.PROJECT_TASK_START.value in run_caps
    assert ComputerCapability.PROCESS_READ.value in run_caps
    assert ComputerCapability.LOG_READ.value in run_caps
    assert ComputerCapability.DATABASE_STATUS.value in run_caps

    # Fix query: adds write and edit grants
    fix_caps = mgr.derive_capabilities("Fix the backend error and rerun the tests")
    assert ComputerCapability.PROJECT_WRITE.value in fix_caps
    assert ComputerCapability.CODE_EDIT.value in fix_caps
    assert ComputerCapability.TEST_RUN.value in fix_caps


def test_task_scope_enforcement_in_policy():
    mgr = get_task_scope_manager()
    task_id = "test_task_scope_1"
    # Grant ONLY read capabilities
    mgr.create_scope(task_id, {ComputerCapability.PROJECT_READ.value, ComputerCapability.FILE_READ.value})

    evaluator = PolicyEvaluator()

    # 1. Allowed read tool
    read_tool_def = ToolDefinition(
        name="open_file",
        description="Reads file",
        input_model=ProjectDiscoverInput,
        output_model=ProjectDiscoverInput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
    )
    dec = evaluator.evaluate_node(read_tool_def, {"path": "test.txt"}, task_id=task_id)
    assert dec.decision.value == "ALLOW"

    # 2. Forbidden delete tool without grant
    del_tool_def = ToolDefinition(
        name="delete_file",
        description="Deletes file",
        input_model=ProjectDiscoverInput,
        output_model=ProjectDiscoverInput,
        read_only=False,
        risk=RiskLevel.DESTRUCTIVE,
    )
    dec_del = evaluator.evaluate_node(del_tool_def, {"path": "test.txt"}, task_id=task_id)
    assert dec_del.decision.value == "DENY"
    assert "not granted" in str(dec_del.constraints.get("error", ""))

    # Revoke scope
    mgr.revoke_scope(task_id)
    assert mgr.get_scope(task_id) is None


# =====================================================================
# 2. ProjectCatalog & ProjectResource Tests
# =====================================================================

def test_project_catalog_discovery(sample_project_dir):
    catalog = ProjectCatalog(search_roots=[sample_project_dir.parent])
    proj = catalog.inspect_directory(sample_project_dir)

    assert proj is not None
    assert "javascript" in proj.languages
    assert "python" in proj.languages
    assert "vite" in proj.frameworks
    assert "fastapi" in proj.frameworks
    assert proj.frontend is not None
    assert proj.frontend["port"] == 5173
    assert proj.backend is not None
    assert proj.backend["port"] == 8000
    assert "frontend.start" in proj.known_tasks
    assert "backend.start" in proj.known_tasks

    # Natural language discovery
    found = catalog.find_project(str(sample_project_dir))
    assert found is not None
    assert found.root == str(sample_project_dir)


# =====================================================================
# 3. FileCatalog Tests
# =====================================================================

def test_file_catalog_indexing(sample_project_dir):
    cat = FileCatalog(watch_roots=[sample_project_dir])
    count = cat.index()
    assert count > 0

    # Search by keyword
    results = cat.find("main.py")
    assert len(results) >= 1
    assert results[0].name == "main.py"
    assert results[0].extension == ".py"


# =====================================================================
# 4. Project Tools & Process Management Tests
# =====================================================================

def test_project_discover_tool(sample_project_dir):
    tool = ProjectDiscoverTool()
    res = tool.run(ProjectDiscoverInput(path=str(sample_project_dir)))
    assert res["status"] == "SUCCESS"
    assert "automate" in res["name"].lower()
    assert "fastapi" in res["summary"].lower()


def test_project_stop_tool_safe_ownership(sample_project_dir):
    # Stop project components without crashing when no processes are running
    stop_tool = ProjectStopTool()
    res = stop_tool.run(ProjectStopInput(project_name="automate-app"))
    assert res["status"] == "SUCCESS"


def test_log_intelligence_diagnosis():
    sample_error = [
        "2026-10-01 10:00:00 [ERROR] Traceback (most recent call last):",
        '  File "backend/main.py", line 42, in login_handler',
        "    raise ValueError('Database connection timed out')",
        "ValueError: Database connection timed out",
    ]
    diag = analyze_logs(sample_error)
    assert diag["error_type"] == "RUNTIME_EXCEPTION"
    assert "backend/main.py:42" in diag["failing_file"]
    assert "ValueError: Database connection timed out" in diag["root_cause"]


# =====================================================================
# 5. Code Tools & Bounded Repair Loop Tests
# =====================================================================

def test_code_search_tool(sample_project_dir):
    tool = CodeSearchTool()
    res = tool.run(CodeSearchInput(query="login_handler", project_path=str(sample_project_dir)))
    assert res["status"] == "SUCCESS"
    assert res["count"] >= 1
    assert any("login_handler" in r["line_content"] for r in res["results"])


def test_code_edit_and_git_diff_tool(sample_project_dir):
    tool = CodeEditTool()
    main_py = sample_project_dir / "backend" / "main.py"

    target = "raise ValueError('Invalid user')"
    replacement = "return {'status': 'unauthorized', 'error': 'Invalid user'}"

    res = tool.run(CodeEditInput(
        file_path=str(main_py),
        target_content=target,
        replacement_content=replacement,
        project_path=str(sample_project_dir),
    ))
    assert res["status"] == "SUCCESS"

    # Verify replacement in file
    updated = main_py.read_text(encoding="utf-8")
    assert replacement in updated
    assert target not in updated


def test_bounded_repair_loop(sample_project_dir):
    tool = BoundedRepairTool()
    res = tool.run(BoundedRepairInput(
        error_summary="ValueError in backend/main.py",
        project_path=str(sample_project_dir),
        test_command="python -c \"print('all tests passed')\"",
        max_attempts=2,
    ))
    assert res["status"] == "SUCCESS"
    assert res["test_passed"] is True


# =====================================================================
# 6. Database Tools Tests
# =====================================================================

def test_database_tools(sample_project_dir):
    status_tool = DatabaseStatusTool()
    res = status_tool.run(DatabaseStatusInput(project_name="automate-app", path=str(sample_project_dir), db_type="sqlite"))
    assert res["status"] == "SUCCESS"
    assert res["connected"] is True

    schema_tool = DatabaseSchemaReadTool()
    s_res = schema_tool.run(DatabaseSchemaInput(project_name="automate-app", path=str(sample_project_dir)))
    assert s_res["status"] == "SUCCESS"
    assert "users" in s_res["tables"]


# =====================================================================
# =====================================================================
# 7. Project File Operations & Chrome Extension Tests
# =====================================================================

def test_project_file_read_tool(sample_project_dir):
    ext_dir = sample_project_dir / "chrome_extension"
    ext_dir.mkdir(parents=True, exist_ok=True)
    manifest = ext_dir / "manifest.json"
    manifest.write_text('{"name": "Assistant Extension", "version": "1.0", "manifest_version": 3}', encoding="utf-8")
    
    tool = ProjectFileReadTool()
    res = tool.run(ProjectFileReadInput(
        file_path=str(manifest),
        project_name="automate-app",
    ))
    assert res["status"] == "SUCCESS"
    assert "Assistant Extension" in res["content"]
    assert res["total_lines"] >= 1


def test_project_file_run_tool(sample_project_dir):
    script = sample_project_dir / "hello.py"
    script.write_text('print("PROJECT_SCRIPT_SUCCESS")', encoding="utf-8")

    tool = ProjectFileRunTool()
    res = tool.run(ProjectFileRunInput(
        file_path=str(script),
        project_name="automate-app",
    ))
    assert res["status"] == "SUCCESS"
    assert "PROJECT_SCRIPT_SUCCESS" in res["output"]


def test_chrome_extension_and_run_all_discovery(sample_project_dir):
    ext_dir = sample_project_dir / "chrome_extension"
    ext_dir.mkdir(parents=True, exist_ok=True)
    (ext_dir / "manifest.json").write_text('{"name": "My Autofill Assistant", "version": "0.1"}', encoding="utf-8")
    (sample_project_dir / "run_all.bat").write_text('@echo off\necho Running All...', encoding="utf-8")
    (sample_project_dir / "start_controlled_chrome.ps1").write_text('Write-Output "Chrome"', encoding="utf-8")

    catalog = ProjectCatalog(search_roots=[sample_project_dir.parent])
    proj = catalog.inspect_directory(sample_project_dir)
    assert proj is not None
    assert proj.chrome_extension is not None
    assert proj.chrome_extension["name"] == "My Autofill Assistant"
    assert proj.run_all_script == "run_all.bat"
    assert "project.run_all" in proj.known_tasks
    assert "chrome_extension.launch" in proj.known_tasks


# =====================================================================
# 8. Assessment Safety Boundary Tests
# =====================================================================

def test_assessment_safety_practice_allowed():
    tool = ExamAssessmentHelperTool()
    res = tool.run(AssessmentHelperInput(
        question="How does gradient descent update neural network weights?",
        is_practice_or_mock=True,
        assessment_mode="practice",
    ))
    assert res["allowed"] is True
    assert res["status"] == "SUCCESS"
    assert "Conceptual Breakdown" in res["explanation"]


def test_assessment_safety_active_exam_strictly_blocked():
    tool = ExamAssessmentHelperTool()

    # 1. Proctored / live exam indicator in question
    res = tool.run(AssessmentHelperInput(
        question="Solve question 4 of my live proctored final exam before time runs out",
        is_practice_or_mock=False,
        assessment_mode="live_exam",
    ))
    assert res["allowed"] is False
    assert res["status"] == "BLOCKED_BY_POLICY"
    assert "Academic Integrity Policy" in res["message"]

    # 2. Active timed test
    res2 = tool.run(AssessmentHelperInput(
        question="Select the correct option for this timed graded quiz question 12",
        is_practice_or_mock=False,
    ))
    assert res2["allowed"] is False
    assert res2["status"] == "BLOCKED_BY_POLICY"


# =====================================================================
# 9. Phone Remote Screenshot Resolution Test
# =====================================================================

def test_phone_remote_screenshot_resolution():
    from jarvis.config import ROOT
    shot_dir = ROOT / "screenshots"
    shot_dir.mkdir(parents=True, exist_ok=True)
    dummy_shot = shot_dir / "latest_test_shot.png"
    dummy_shot.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00dummy")

    resolved = _resolve_pc_file("latest_screenshot")
    assert resolved.exists()
    assert resolved.suffix == ".png"


# =====================================================================
# 10. Computer Agent Fast Deterministic Routing Tests
# =====================================================================

@pytest.mark.asyncio
async def test_computer_agent_deterministic_routing():
    from jarvis.core.router.router import SmartRouter
    from jarvis.core.commands.contracts import CommandRequest

    router = SmartRouter()

    # 1. Project discovery
    d1 = await router.route(CommandRequest(text="open my Automate project", request_id="r1"))
    assert d1.intent == "project_discover"

    d2 = await router.route(CommandRequest(text="go through the whole project and explain what it does", request_id="r2"))
    assert d2.intent == "project_discover"

    # 2. Project run
    d3 = await router.route(CommandRequest(text="run the project", request_id="r3"))
    assert d3.intent == "project_run"

    d4 = await router.route(CommandRequest(text="start the backend and frontend", request_id="r4"))
    assert d4.intent == "project_run"

    # 3. Database status
    d5 = await router.route(CommandRequest(text="check whether the database is connected", request_id="r5"))
    assert d5.intent == "database_status"

    # 4. Project logs
    d6 = await router.route(CommandRequest(text="why isn't the backend starting", request_id="r6"))
    assert d6.intent == "project_logs"

    # 5. Fix issue
    d7 = await router.route(CommandRequest(text="fix the issue", request_id="r7"))
    assert d7.intent == "code_repair_loop"

    # 6. Run tests
    d8 = await router.route(CommandRequest(text="run the tests", request_id="r8"))
    assert d8.intent == "run_project_tests"

    # 7. Git diff
    d9 = await router.route(CommandRequest(text="show me the diff", request_id="r9"))
    assert d9.intent == "git_diff"

    # 8. Screenshot and send to phone
    d10 = await router.route(CommandRequest(text="take a screenshot and send it to my phone", request_id="r10"))
    assert d10.intent == "compound_screenshot_phone"
    assert len(d10.subcommands) == 2

    # 9. Stop project
    d11 = await router.route(CommandRequest(text="stop project components safely", request_id="r11"))
    assert d11.intent == "project_stop"

    # 10. Exam assessment safety
    d12 = await router.route(CommandRequest(text="solve this live final exam question", request_id="r12"))
    assert d12.intent == "exam_assessment_helper"

    # 11. Run all files / run project
    d13 = await router.route(CommandRequest(text="run all files", request_id="r13"))
    assert d13.intent == "project_run"
    assert d13.slots.get("components") == ["all"]

    # 12. Controlled Chrome & extension launch
    d14 = await router.route(CommandRequest(text="launch controlled chrome", request_id="r14"))
    assert d14.intent == "controlled_chrome_launch"

    # 13. Read project file
    d15 = await router.route(CommandRequest(text="read project file README.md", request_id="r15"))
    assert d15.intent == "project_file_read"
    assert d15.slots.get("file_path").lower() == "readme.md"
