"""Application Discovery and Software Management Tools for JARVIS EDGE.
Integrates AppCatalog, PackageCatalog, and PowerShell execution to support
automatic application discovery, installation, and location queries.
"""
from __future__ import annotations

import logging
import subprocess
from typing import Any, Dict, List, Optional
from pydantic import Field

from jarvis.core.catalog.app_catalog import AppCatalog
from jarvis.core.catalog.models import AppEntry
from jarvis.core.catalog.package_catalog import PackageCatalog
from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition

logger = logging.getLogger("jarvis.tools.app_catalog")


# =====================================================================
# 1. Refresh Applications Tool
# =====================================================================

class RefreshApplicationsInput(Contract):
    force: bool = Field(default=True, description="Force a full rescan of all registration sources")


class RefreshApplicationsOutput(Contract):
    status: str
    total_apps: int
    new_apps: int
    elapsed_ms: float
    message: str


class RefreshApplicationsTool(Tool):
    definition = ToolDefinition(
        name="refresh_applications",
        description="Refreshes the application catalog across registry, shortcuts, UWP, and PATH entries without modifying system PATH. Risk level: READ_ONLY.",
        input_model=RefreshApplicationsInput,
        output_model=RefreshApplicationsOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=30.0,
        tags=("system", "applications", "catalog", "refresh"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def __init__(self, catalog: Optional[AppCatalog] = None) -> None:
        self._catalog = catalog

    @property
    def catalog(self) -> AppCatalog:
        if self._catalog is None:
            self._catalog = AppCatalog.get_default()
        return self._catalog

    def run(self, arguments: Any) -> Dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = RefreshApplicationsInput(**arguments)

        summary = self.catalog.refresh(full=arguments.force)
        msg = f"Application catalog refreshed in {summary.elapsed_ms:.1f}ms. Discovered {summary.total_apps} applications."
        return {
            "status": "SUCCESS",
            "total_apps": summary.total_apps,
            "new_apps": summary.new_apps,
            "elapsed_ms": summary.elapsed_ms,
            "message": msg,
        }


# =====================================================================
# 2. List Installed Applications Tool
# =====================================================================

class ListInstalledApplicationsInput(Contract):
    filter: str = Field(default="", description="Optional search term to filter applications")
    limit: int = Field(default=20, ge=1, le=200, description="Max applications to return")


class ListInstalledApplicationsOutput(Contract):
    status: str
    count: int
    total_installed: int
    applications: List[Dict[str, Any]]
    spoken_summary: str


class ListInstalledApplicationsTool(Tool):
    definition = ToolDefinition(
        name="list_installed_applications",
        description="Lists verified installed applications tracked in the application catalog. Risk level: READ_ONLY.",
        input_model=ListInstalledApplicationsInput,
        output_model=ListInstalledApplicationsOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=5.0,
        tags=("system", "applications", "inventory"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def __init__(self, catalog: Optional[AppCatalog] = None) -> None:
        self._catalog = catalog

    @property
    def catalog(self) -> AppCatalog:
        if self._catalog is None:
            self._catalog = AppCatalog.get_default()
        return self._catalog

    def run(self, arguments: Any) -> Dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = ListInstalledApplicationsInput(**arguments)

        filt = arguments.filter.strip().casefold()
        entries = self.catalog.list_installed_entries()

        if filt:
            filtered = [
                e for e in entries
                if filt in e.display_name.casefold()
                or filt in e.app_id.casefold()
                or any(filt in a.casefold() for a in e.aliases)
            ]
        else:
            filtered = entries

        total_count = len(filtered)
        paged = filtered[: arguments.limit]

        app_dicts = [
            {
                "app_id": e.app_id,
                "display_name": e.display_name,
                "executable_path": e.executable_path,
                "version": e.version,
                "source": e.source,
            }
            for e in paged
        ]

        if not paged:
            spoken = "No installed applications matched your query."
        else:
            sample_names = [e.display_name for e in paged[:5]]
            sample_str = ", ".join(sample_names[:-1]) + f", and {sample_names[-1]}" if len(sample_names) > 1 else sample_names[0]
            spoken = f"Found {total_count} installed applications, including {sample_str}."

        return {
            "status": "SUCCESS",
            "count": len(paged),
            "total_installed": total_count,
            "applications": app_dicts,
            "spoken_summary": spoken,
        }


# =====================================================================
# 3. Check App Installed Tool
# =====================================================================

class CheckAppInstalledInput(Contract):
    name: str = Field(min_length=1, max_length=128, description="Name or alias of the software to check")


class CheckAppInstalledOutput(Contract):
    installed: bool
    app_name: str
    canonical_id: Optional[str] = None
    version: Optional[str] = None
    location: Optional[str] = None
    message: str


class CheckAppInstalledTool(Tool):
    definition = ToolDefinition(
        name="check_app_installed",
        description="Checks whether a specific software or application is installed on the PC. Risk level: READ_ONLY.",
        input_model=CheckAppInstalledInput,
        output_model=CheckAppInstalledOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=5.0,
        tags=("system", "applications", "check", "discovery"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def __init__(self, catalog: Optional[AppCatalog] = None) -> None:
        self._catalog = catalog

    @property
    def catalog(self) -> AppCatalog:
        if self._catalog is None:
            self._catalog = AppCatalog.get_default()
        return self._catalog

    def run(self, arguments: Any) -> Dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = CheckAppInstalledInput(**arguments)

        target_name = arguments.name.strip()
        is_inst, entry = self.catalog.is_installed(target_name)

        if is_inst and entry:
            ver_part = f" (version {entry.version})" if entry.version else ""
            loc = entry.install_location or entry.executable_path
            msg = f"Yes, {entry.display_name}{ver_part} is installed at {loc}."
            return {
                "installed": True,
                "app_name": entry.display_name,
                "canonical_id": entry.app_id,
                "version": entry.version,
                "location": loc,
                "message": msg,
            }

        return {
            "installed": False,
            "app_name": target_name,
            "canonical_id": None,
            "version": None,
            "location": None,
            "message": f"No, {target_name} is not currently installed.",
        }


# =====================================================================
# 4. Get App Location Tool
# =====================================================================

class GetAppLocationInput(Contract):
    name: str = Field(min_length=1, max_length=128, description="Name or alias of the software to find")


class GetAppLocationOutput(Contract):
    found: bool
    app_name: str
    executable_path: Optional[str] = None
    install_location: Optional[str] = None
    message: str


class GetAppLocationTool(Tool):
    definition = ToolDefinition(
        name="get_app_location",
        description="Gets the verified installation location and executable path of an installed application. Risk level: READ_ONLY.",
        input_model=GetAppLocationInput,
        output_model=GetAppLocationOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=5.0,
        tags=("system", "applications", "path", "location"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def __init__(self, catalog: Optional[AppCatalog] = None) -> None:
        self._catalog = catalog

    @property
    def catalog(self) -> AppCatalog:
        if self._catalog is None:
            self._catalog = AppCatalog.get_default()
        return self._catalog

    def run(self, arguments: Any) -> Dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = GetAppLocationInput(**arguments)

        target_name = arguments.name.strip()
        entry = self.catalog.get_app(target_name)

        if entry and (entry.executable_path or entry.install_location):
            loc = entry.install_location or entry.executable_path
            msg = f"{entry.display_name} is installed at {loc}."
            return {
                "found": True,
                "app_name": entry.display_name,
                "executable_path": entry.executable_path,
                "install_location": entry.install_location,
                "message": msg,
            }

        return {
            "found": False,
            "app_name": target_name,
            "executable_path": None,
            "install_location": None,
            "message": f"Could not find an installed application matching '{target_name}'.",
        }


# =====================================================================
# 5. Install Software Tool
# =====================================================================

class InstallSoftwareInput(Contract):
    name: str = Field(min_length=1, max_length=128, description="Name of the software or application to install")
    package_id: Optional[str] = Field(default=None, description="Optional explicit package ID")


class InstallSoftwareOutput(Contract):
    status: str
    app_name: str
    package_id: str
    executable_path: Optional[str] = None
    message: str


class InstallSoftwareTool(Tool):
    definition = ToolDefinition(
        name="install_software",
        description="Installs verified software packages via winget, verifies installation, and automatically updates the application catalog. Risk level: REVERSIBLE.",
        input_model=InstallSoftwareInput,
        output_model=InstallSoftwareOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=300.0,
        tags=("system", "install", "software", "winget"),
        execution_method=ExecutionMethod.CLI,
    )

    def __init__(
        self,
        catalog: Optional[AppCatalog] = None,
        package_catalog: Optional[PackageCatalog] = None,
    ) -> None:
        self._catalog = catalog
        self._pkg_catalog = package_catalog

    @property
    def catalog(self) -> AppCatalog:
        if self._catalog is None:
            self._catalog = AppCatalog.get_default()
        return self._catalog

    @property
    def package_catalog(self) -> PackageCatalog:
        if self._pkg_catalog is None:
            self._pkg_catalog = self.catalog.package_catalog if hasattr(self.catalog, "package_catalog") else PackageCatalog()
        return self._pkg_catalog

    def run(self, arguments: Any) -> Dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = InstallSoftwareInput(**arguments)

        raw_name = arguments.name.strip()
        pkg = None

        if arguments.package_id:
            pkg = self.package_catalog.resolve_package(arguments.package_id)

        if not pkg:
            pkg = self.package_catalog.resolve_package(raw_name)

        if not pkg:
            return {
                "status": "FAILED",
                "app_name": raw_name,
                "package_id": "",
                "executable_path": None,
                "message": f"Could not find a trusted installer package for '{raw_name}'.",
            }

        # Check if already installed
        is_inst, entry = self.catalog.is_installed(pkg.canonical_name)
        if is_inst and entry:
            return {
                "status": "ALREADY_INSTALLED",
                "app_name": entry.display_name,
                "package_id": pkg.package_id,
                "executable_path": entry.executable_path,
                "message": f"{entry.display_name} is already installed at {entry.executable_path}.",
            }

        # Construct and execute trusted installer command
        cmd = self.package_catalog.build_install_command(pkg)
        logger.info("Executing trusted software installation: %s", cmd)

        try:
            res = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=240.0,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            success = res.returncode == 0
        except Exception as exc:
            logger.error("Software installation execution failed: %s", exc)
            return {
                "status": "FAILED",
                "app_name": pkg.display_name,
                "package_id": pkg.package_id,
                "executable_path": None,
                "message": f"Installation failed with error: {exc}",
            }

        # Automatic AppCatalog refresh immediately after installation!
        logger.info("Triggering automatic AppCatalog refresh for newly installed software: %s", pkg.canonical_name)
        self.catalog.refresh(targeted=pkg.canonical_name)

        # Launch verification check
        installed, new_entry = self.catalog.is_installed(pkg.canonical_name)
        exe_path = new_entry.executable_path if new_entry else None

        if success or installed:
            msg = f"{pkg.display_name} installed successfully and registered in application catalog. You can now say 'Open {pkg.display_name}'."
            return {
                "status": "SUCCESS",
                "app_name": pkg.display_name,
                "package_id": pkg.package_id,
                "executable_path": exe_path,
                "message": msg,
            }
        else:
            return {
                "status": "FAILED",
                "app_name": pkg.display_name,
                "package_id": pkg.package_id,
                "executable_path": None,
                "message": f"Installation completed with return code {res.returncode}. Output: {res.stderr[:200] or res.stdout[:200]}",
            }


def create_app_discovery_tools(catalog: Optional[AppCatalog] = None) -> List[Tool]:
    """Factory creating all application discovery and management tools."""
    cat = catalog or AppCatalog.get_default()
    return [
        RefreshApplicationsTool(catalog=cat),
        ListInstalledApplicationsTool(catalog=cat),
        CheckAppInstalledTool(catalog=cat),
        GetAppLocationTool(catalog=cat),
        InstallSoftwareTool(catalog=cat),
    ]
