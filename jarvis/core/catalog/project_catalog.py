"""Project Discovery & ProjectCatalog for JARVIS EDGE.

Automatically inspects and catalogs user projects (Node, Python, Java, Docker, etc.)
from project manifests without guessing or running arbitrary commands.
Produces typed ProjectResource definitions.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("jarvis.catalog.project")

# Ignored vendor / generated directories
IGNORE_DIRS = frozenset({
    "node_modules", ".git", ".venv", "venv", "dist", "build",
    "__pycache__", ".pytest_cache", ".next", ".nuxt", "target",
    "out", "coverage", ".turbo", "bin", "obj", ".idea", ".vscode",
})


@dataclass
class ProjectResource:
    """Canonical descriptor for an inspected software project."""
    project_id: str
    name: str
    root: str
    languages: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    frontend: Optional[Dict[str, Any]] = None
    backend: Optional[Dict[str, Any]] = None
    database: Optional[Dict[str, Any]] = None
    workers: List[Dict[str, Any]] = field(default_factory=list)
    build_system: str = "unknown"
    known_tasks: Dict[str, Any] = field(default_factory=dict)
    ports: List[int] = field(default_factory=list)
    configs: List[str] = field(default_factory=list)
    important_files: List[str] = field(default_factory=list)
    chrome_extension: Optional[Dict[str, Any]] = None
    run_all_script: Optional[str] = None
    last_seen: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProjectCatalog:
    """Discovers, caches, and indexes user software projects across authorized directories."""

    def __init__(self, search_roots: Optional[List[str | Path]] = None) -> None:
        self._projects: Dict[str, ProjectResource] = {}
        self._last_scan: float = 0.0
        self.search_roots = [Path(r) for r in search_roots] if search_roots else self._default_search_roots()

    def _default_search_roots(self) -> List[Path]:
        roots: List[Path] = []
        cwd = Path.cwd()
        roots.append(cwd)

        # Check common developer directories
        home = Path.home()
        candidates = [
            cwd.parent,
            home / "Desktop",
            home / "OneDrive" / "Desktop",
            home / "Documents" / "Projects",
            home / "Projects",
            home / "source" / "repos",
            home / "workspace",
        ]
        for c in candidates:
            if c.exists() and c.is_dir() and c not in roots:
                roots.append(c)
        return roots

    def inspect_directory(self, directory: Path | str) -> Optional[ProjectResource]:
        """Inspects a single folder to determine if it is a valid project and extracts metadata."""
        root = Path(directory).resolve()
        if not root.is_dir():
            return None

        # Check for presence of project manifests
        manifests = [
            root / "package.json",
            root / "pyproject.toml",
            root / "requirements.txt",
            root / "setup.py",
            root / "Pipfile",
            root / "pom.xml",
            root / "build.gradle",
            root / "docker-compose.yml",
            root / "Dockerfile",
            root / "Cargo.toml",
            root / "go.mod",
        ]

        sub_manifests = [
            root / "frontend" / "package.json",
            root / "client" / "package.json",
            root / "backend" / "pyproject.toml",
            root / "backend" / "requirements.txt",
            root / "server" / "package.json",
            root / "api" / "requirements.txt",
        ]

        has_manifest = any(m.is_file() for m in manifests + sub_manifests)
        if not has_manifest:
            return None

        name = root.name
        languages: set[str] = set()
        frameworks: set[str] = set()
        known_tasks: dict[str, Any] = {}
        ports: set[int] = set()
        configs: list[str] = []
        important_files: list[str] = []
        build_system = "unknown"

        frontend_info: Optional[dict[str, Any]] = None
        backend_info: Optional[dict[str, Any]] = None
        database_info: Optional[dict[str, Any]] = None
        workers: list[dict[str, Any]] = []

        # 1. Inspect package.json (root or frontend)
        pkg_paths = [root / "package.json", root / "frontend" / "package.json", root / "client" / "package.json"]
        for pkg_p in pkg_paths:
            if pkg_p.is_file():
                configs.append(str(pkg_p.relative_to(root)))
                languages.add("javascript")
                languages.add("typescript")
                try:
                    with open(pkg_p, "r", encoding="utf-8") as f:
                        pkg_data = json.load(f)
                    if pkg_p.parent == root and pkg_data.get("name"):
                        name = str(pkg_data["name"])
                    scripts = pkg_data.get("scripts", {})
                    deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}

                    # Frameworks
                    if "vite" in deps:
                        frameworks.add("vite")
                        ports.add(5173)
                    if "next" in deps:
                        frameworks.add("next.js")
                        ports.add(3000)
                    if "react" in deps:
                        frameworks.add("react")
                    if "vue" in deps:
                        frameworks.add("vue")
                    if "express" in deps:
                        frameworks.add("express")
                        ports.add(3000)

                    rel_dir = str(pkg_p.parent.relative_to(root)) if pkg_p.parent != root else "."
                    build_system = "npm"

                    # Register frontend tasks
                    if "dev" in scripts or "start" in scripts:
                        run_cmd = "npm run dev" if "dev" in scripts else "npm start"
                        frontend_info = {
                            "type": "node",
                            "dir": rel_dir,
                            "command": run_cmd,
                            "port": 5173 if "vite" in deps else (3000 if "next" in deps or "react" in deps else 5000),
                        }
                        known_tasks["frontend.start"] = {"command": run_cmd, "cwd": rel_dir, "component": "frontend"}
                    if "build" in scripts:
                        known_tasks["frontend.build"] = {"command": "npm run build", "cwd": rel_dir, "component": "frontend"}
                    if "test" in scripts:
                        known_tasks["frontend.test"] = {"command": "npm test", "cwd": rel_dir, "component": "frontend"}
                except Exception as exc:
                    logger.debug("Failed reading %s: %s", pkg_p, exc)

        # 2. Inspect Python manifests (pyproject.toml, requirements.txt)
        py_paths = [root / "pyproject.toml", root / "requirements.txt", root / "backend" / "requirements.txt", root / "api" / "requirements.txt"]
        for py_p in py_paths:
            if py_p.is_file():
                languages.add("python")
                configs.append(str(py_p.relative_to(root)))
                build_system = "pip/python" if build_system == "unknown" else build_system
                try:
                    content = py_p.read_text(encoding="utf-8", errors="ignore").lower()
                    if "fastapi" in content:
                        frameworks.add("fastapi")
                        ports.add(8000)
                    if "flask" in content:
                        frameworks.add("flask")
                        ports.add(5000)
                    if "django" in content:
                        frameworks.add("django")
                        ports.add(8000)
                    if "celery" in content:
                        frameworks.add("celery")
                        workers.append({"name": "celery", "type": "task_queue"})
                        known_tasks["worker.start"] = {"command": "celery -A tasks worker", "cwd": ".", "component": "worker"}
                    if "sqlalchemy" in content or "psycopg" in content or "asyncpg" in content:
                        database_info = {"type": "postgresql", "port": 5432, "client": "sqlalchemy"}
                        ports.add(5432)
                    elif "sqlite" in content:
                        database_info = {"type": "sqlite", "file": "app.db"}
                    elif "pymongo" in content or "motor" in content:
                        database_info = {"type": "mongodb", "port": 27017}
                        ports.add(27017)

                    rel_dir = str(py_p.parent.relative_to(root)) if py_p.parent != root else "."
                    # Detect start command
                    start_cmd = "python main.py"
                    if "fastapi" in frameworks:
                        start_cmd = "uvicorn main:app --reload --port 8000"
                    elif "flask" in frameworks:
                        start_cmd = "flask run"
                    elif "django" in frameworks:
                        start_cmd = "python manage.py runserver"

                    backend_info = {
                        "type": "python",
                        "dir": rel_dir,
                        "command": start_cmd,
                        "port": 8000 if "fastapi" in frameworks or "django" in frameworks else 5000,
                    }
                    known_tasks["backend.start"] = {"command": start_cmd, "cwd": rel_dir, "component": "backend"}
                    known_tasks["backend.test"] = {"command": "pytest", "cwd": rel_dir, "component": "backend"}
                except Exception as exc:
                    logger.debug("Failed reading %s: %s", py_p, exc)

        # 3. Docker / compose
        compose_p = root / "docker-compose.yml"
        if compose_p.is_file():
            configs.append("docker-compose.yml")
            frameworks.add("docker-compose")
            try:
                comp_text = compose_p.read_text(encoding="utf-8", errors="ignore").lower()
                if "postgres" in comp_text:
                    database_info = {"type": "postgresql", "port": 5432, "via": "docker-compose"}
                    ports.add(5432)
                if "redis" in comp_text:
                    ports.add(6379)
                if "mongo" in comp_text:
                    database_info = {"type": "mongodb", "port": 27017, "via": "docker-compose"}
                    ports.add(27017)
                known_tasks["database.status"] = {"check_type": "port", "port": 5432 if "postgres" in comp_text else 27017}
            except Exception:
                pass

        # 4. Standard tasks
        known_tasks["project.status"] = {"check_type": "composite"}
        known_tasks["project.test"] = {"command": "pytest" if "python" in languages else "npm test", "cwd": "."}
        if database_info:
            known_tasks["database.check"] = {"component": "database", "info": database_info}

        # 4b. Check for Chrome extension
        chrome_extension_info: Optional[Dict[str, Any]] = None
        ext_candidates = [
            root / "chrome_extension",
            root / "extension",
            root / "browser_extension",
        ]
        ext_dir = next((d for d in ext_candidates if d.is_dir()), None)
        if not ext_dir:
            try:
                for sub in root.iterdir():
                    if sub.is_dir() and "extension" in sub.name.lower() and (sub / "manifest.json").is_file():
                        ext_dir = sub
                        break
            except Exception:
                pass

        if ext_dir and (ext_dir / "manifest.json").is_file():
            manifest_file = ext_dir / "manifest.json"
            ext_meta: Dict[str, Any] = {"path": str(ext_dir.relative_to(root))}
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    m_data = json.load(f)
                    ext_meta["name"] = m_data.get("name", "Chrome Extension")
                    ext_meta["version"] = m_data.get("version", "1.0")
                    ext_meta["manifest_version"] = m_data.get("manifest_version", 3)
            except Exception:
                pass
            chrome_extension_info = ext_meta
            important_files.append(str(manifest_file.relative_to(root)))
            known_tasks["chrome_extension.reload"] = {"path": str(ext_dir.relative_to(root))}
            if (root / "start_controlled_chrome.ps1").is_file():
                known_tasks["chrome_extension.launch"] = {
                    "command": "powershell -ExecutionPolicy Bypass -File start_controlled_chrome.ps1",
                    "cwd": ".",
                    "component": "browser",
                }
                ports.add(9222)

        # 4c. Check for run_all or start scripts
        run_all_script: Optional[str] = None
        for run_fname in ["run_all.bat", "run_all.cmd", "run_all.ps1", "start.bat", "start.ps1"]:
            if (root / run_fname).is_file():
                run_all_script = run_fname
                important_files.append(run_fname)
                cmd_str = f"cmd /c {run_fname}" if run_fname.endswith((".bat", ".cmd")) else f"powershell -ExecutionPolicy Bypass -File {run_fname}"
                known_tasks["project.run_all"] = {
                    "command": cmd_str,
                    "cwd": ".",
                    "component": "all",
                }
                break

        if (root / "start_controlled_chrome.ps1").is_file() and "start_controlled_chrome.ps1" not in important_files:
            important_files.append("start_controlled_chrome.ps1")

        # 5. Important files
        for fname in ["README.md", "README", ".env.example", ".env", "main.py", "app.py", "index.html", "src/App.tsx", "src/main.tsx"]:
            if (root / fname).exists() and fname not in important_files:
                important_files.append(fname)

        project_id = f"proj_{root.name.lower().replace(' ', '_')}_{abs(hash(str(root))) % 10000}"

        return ProjectResource(
            project_id=project_id,
            name=name,
            root=str(root),
            languages=sorted(languages),
            frameworks=sorted(frameworks),
            frontend=frontend_info,
            backend=backend_info,
            database=database_info,
            workers=workers,
            build_system=build_system,
            known_tasks=known_tasks,
            ports=sorted(ports),
            configs=configs,
            important_files=important_files,
            chrome_extension=chrome_extension_info,
            run_all_script=run_all_script,
            last_seen=time.time(),
        )

    def scan(self, max_depth: int = 2) -> List[ProjectResource]:
        """Scans search roots recursively up to max_depth for projects."""
        discovered: Dict[str, ProjectResource] = {}
        for base in self.search_roots:
            if not base.exists():
                continue
            # First check if base itself is a project
            proj = self.inspect_directory(base)
            if proj:
                discovered[proj.root] = proj

            # Scan children
            try:
                for entry in os.scandir(base):
                    if entry.is_dir() and entry.name not in IGNORE_DIRS and not entry.name.startswith("."):
                        child_proj = self.inspect_directory(Path(entry.path))
                        if child_proj:
                            discovered[child_proj.root] = child_proj
                        elif max_depth > 1:
                            try:
                                for sub in os.scandir(entry.path):
                                    if sub.is_dir() and sub.name not in IGNORE_DIRS and not sub.name.startswith("."):
                                        sub_proj = self.inspect_directory(Path(sub.path))
                                        if sub_proj:
                                            discovered[sub_proj.root] = sub_proj
                            except PermissionError:
                                pass
            except PermissionError:
                pass

        self._projects.update(discovered)
        self._last_scan = time.time()
        logger.info("ProjectCatalog scanned %d projects", len(self._projects))
        return list(self._projects.values())

    def find_project(self, query: str) -> Optional[ProjectResource]:
        """Resolves natural language project queries (e.g. 'my Automate project', 'automate', 'jarvis')."""
        try:
            p_cand = Path(query).resolve()
            if p_cand.is_dir():
                direct = self.inspect_directory(p_cand)
                if direct:
                    self._projects[direct.root] = direct
                    return direct
        except Exception:
            pass

        if not self._projects:
            self.scan()

        q = query.lower().strip()
        # Clean phrases like 'my automate project', 'the automate app'
        q_clean = re.sub(r"\b(my|the|project|app|codebase|repo|repository)\b", "", q).strip()
        if not q_clean:
            q_clean = q

        # Exact name match
        for proj in self._projects.values():
            if proj.name.lower() == q_clean:
                return proj

        # Substring / partial match
        for proj in self._projects.values():
            if q_clean in proj.name.lower() or proj.name.lower() in q_clean:
                return proj

        # Match against root path
        for proj in self._projects.values():
            if q_clean in Path(proj.root).name.lower():
                return proj

        # Check search roots for matching child directory
        for s_root in self.search_roots:
            if s_root.exists() and s_root.is_dir():
                try:
                    for entry in os.scandir(s_root):
                        if entry.is_dir():
                            c_proj = self.inspect_directory(Path(entry.path))
                            if c_proj and (q_clean in c_proj.name.lower() or q_clean in entry.name.lower()):
                                self._projects[c_proj.root] = c_proj
                                return c_proj
                except PermissionError:
                    pass

        return None

    def get_by_root(self, root: str) -> Optional[ProjectResource]:
        norm = str(Path(root).resolve())
        return self._projects.get(norm) or self.inspect_directory(norm)


_global_project_catalog: Optional[ProjectCatalog] = None


def get_project_catalog() -> ProjectCatalog:
    global _global_project_catalog
    if _global_project_catalog is None:
        _global_project_catalog = ProjectCatalog()
    return _global_project_catalog
