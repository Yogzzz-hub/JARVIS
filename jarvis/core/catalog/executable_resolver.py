"""Executable Resolver and Security Boundary for JARVIS EDGE.
Validates trusted application roots, extracts shortcut targets, rejects untrusted
temporary locations, and derives candidate process names for window management.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
import re
from typing import List, Optional, Set, Tuple

logger = logging.getLogger("jarvis.catalog.executable_resolver")

# Directories strictly forbidden from automatic discovery or execution
UNTRUSTED_SUBSTRINGS = (
    "\\temp\\",
    "/temp/",
    "\\tmp\\",
    "/tmp/",
    "appdata\\local\\temp",
    "appdata/local/temp",
    "\\downloads\\",
    "/downloads/",
    "\\node_modules\\",
    "/node_modules/",
    "\\site-packages\\",
    "/site-packages/",
    "\\.venv\\",
    "/.venv/",
    "\\__pycache__\\",
    "/__pycache__/",
    "\\.git\\",
    "/.git/",
    "\\.cache\\",
    "/.cache/",
)

# Standard known process name overrides for applications whose process name differs from executable name
PROCESS_NAME_OVERRIDES: dict[str, tuple[str, ...]] = {
    "calc.exe": ("calculatorapp.exe", "calculator.exe", "calc.exe"),
    "calculatorapp.exe": ("calculatorapp.exe", "calculator.exe", "calc.exe"),
    "code.exe": ("code.exe",),
    "msedge.exe": ("msedge.exe",),
    "chrome.exe": ("chrome.exe",),
    "notepad.exe": ("notepad.exe",),
    "wt.exe": ("windowsterminal.exe", "wt.exe"),
    "windowsterminal.exe": ("windowsterminal.exe", "wt.exe"),
    "vlc.exe": ("vlc.exe",),
    "obs64.exe": ("obs64.exe", "obs32.exe", "obs.exe"),
    "spotify.exe": ("spotify.exe",),
    "discord.exe": ("discord.exe",),
    "winword.exe": ("winword.exe",),
    "excel.exe": ("excel.exe",),
    "powerpnt.exe": ("powerpnt.exe",),
    "outlook.exe": ("outlook.exe", "olk.exe"),
    "mspaint.exe": ("mspaint.exe", "paint.exe"),
    "snippingtool.exe": ("snippingtool.exe", "screensketch.exe"),
}


class ExecutableResolver:
    """Validates trusted executables, dereferences shortcuts, and derives process names."""

    def __init__(self, extra_trusted_roots: Optional[List[Path]] = None):
        self._extra_trusted_roots: List[Path] = [r.resolve() for r in (extra_trusted_roots or []) if hasattr(r, "is_dir") and r.is_dir()]
        self._trusted_roots: List[Path] = self._init_trusted_roots(self._extra_trusted_roots)

    def _init_trusted_roots(self, extra: Optional[List[Path]] = None) -> List[Path]:
        roots: List[Path] = []
        # Standard Windows system roots
        for env_key in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
            val = os.environ.get(env_key)
            if val and os.path.isdir(val):
                try:
                    roots.append(Path(val).resolve())
                except Exception:
                    pass

        # User profile application directories
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app and os.path.isdir(local_app):
            local_path = Path(local_app).resolve()
            # Programs (e.g. VS Code, Python, Slack)
            roots.append(local_path / "Programs")
            # Microsoft WindowsApps (UWP Execution Aliases)
            roots.append(local_path / "Microsoft" / "WindowsApps")

        app_data = os.environ.get("APPDATA")
        if app_data and os.path.isdir(app_data):
            try:
                roots.append(Path(app_data).resolve())
            except Exception:
                pass

        if extra:
            for r in extra:
                if r.is_dir():
                    roots.append(r.resolve())

        return roots

    def is_trusted_location(self, file_path: Path | str) -> bool:
        """Verifies if an executable path is within trusted roots and not in an untrusted directory."""
        raw_str = str(file_path).strip().strip('"').strip("'")
        if not raw_str:
            return False

        try:
            path = Path(raw_str).resolve()
        except Exception:
            return False

        # Check if path is under an explicitly supplied trusted root (e.g. test environment or custom root)
        in_extra_root = False
        for root in self._extra_trusted_roots:
            try:
                if path.is_relative_to(root):
                    # Reject if inside an untrusted subfolder within the extra root
                    rel = path.relative_to(root)
                    rel_parts = [p.casefold() for p in rel.parts]
                    if any(bad in rel_parts for bad in ("temp", "tmp", "downloads", "node_modules", ".venv", "windowsapps")):
                        return False
                    return True
            except (ValueError, AttributeError):
                pass

        lower_str = raw_str.casefold()

        # 1. Reject untrusted path substrings (temp, downloads, venv, etc.)
        for forbidden in UNTRUSTED_SUBSTRINGS:
            if forbidden in lower_str:
                return False

        # 2. Reject raw binaries inside Program Files\WindowsApps (they fail when directly invoked without package identity)
        parts_lower = [p.casefold() for p in path.parts]
        if "windowsapps" in parts_lower and ("program files" in parts_lower or "program files (x86)" in parts_lower):
            return False

        # 3. Must be under a registered trusted root
        for root in self._trusted_roots:
            try:
                if path.is_relative_to(root):
                    return True
            except (ValueError, AttributeError):
                try:
                    if str(path).casefold().startswith(str(root).casefold()):
                        return True
                except Exception:
                    pass

        return False

    def validate_executable(self, raw_path: str | Path) -> Optional[str]:
        """Validates that a path points to an existing, trusted .exe file."""
        if not raw_path:
            return None

        # Clean string from quotes and variables
        expanded = os.path.expandvars(str(raw_path).strip().strip('"').strip("'"))
        # Strip trailing argument flags if accidentally passed from registry uninstall / command string
        # e.g., "C:\Program Files\App\app.exe" /s -> "C:\Program Files\App\app.exe"
        if ".exe" in expanded.casefold():
            idx = expanded.casefold().find(".exe") + 4
            candidate_part = expanded[:idx].strip().strip('"').strip("'")
            if os.path.isfile(candidate_part):
                expanded = candidate_part

        try:
            p = Path(expanded).resolve()
        except Exception:
            return None

        if p.suffix.casefold() != ".exe" or not p.is_file():
            return None

        if not self.is_trusted_location(p):
            logger.debug("Rejected untrusted executable location: %s", p)
            return None

        return str(p)

    def resolve_shortcut(self, lnk_path: Path | str) -> Tuple[str, bool]:
        """
        Extracts target executable from a Windows .lnk shortcut.
        Returns: (target_path_or_lnk, is_associated)
        If the target is a verified .exe, returns (target_path, False).
        Otherwise returns (original_lnk_path, True).
        """
        lnk_str = str(lnk_path).strip().strip('"')
        if not os.path.isfile(lnk_str):
            return lnk_str, True

        # Attempt COM WScript.Shell extraction on Windows
        if os.name == "nt":
            try:
                import win32com.client
                shell = win32com.client.Dispatch("WScript.Shell")
                shortcut = shell.CreateShortcut(lnk_str)
                target_path = shortcut.TargetPath
                if target_path and target_path.strip():
                    validated = self.validate_executable(target_path)
                    if validated:
                        return validated, False
            except Exception as exc:
                logger.debug("COM shortcut resolution failed for %s: %s", lnk_str, exc)

        # Fallback: check if the .lnk file itself can be launched via ShellExecute
        return lnk_str, True

    def get_process_names(self, executable_or_target: str) -> Tuple[str, ...]:
        """Derives candidate process names for window management and verification."""
        target_clean = executable_or_target.strip().strip('"').casefold()

        # Check protocol URIs
        if ":" in target_clean and not target_clean.startswith(("c:", "d:", "e:", "f:")):
            protocol = target_clean.split(":")[0] + ":"
            from jarvis.tools.system.app_resolver import LaunchTarget
            uwp_protocols = {
                "ms-settings:": ("systemsettings.exe",),
                "ms-photos:": ("microsoft.photos.exe",),
                "bingweather:": ("microsoft.bingweather.exe",),
                "bingmaps:": ("microsoft.windowsmaps.exe",),
                "microsoft.windows.camera:": ("windowscamera.exe",),
                "ms-clock:": ("time.exe",),
                "outlookmail:": ("hxoutlook.exe",),
                "outlookcal:": ("hxcalendarappimm.exe",),
            }
            if protocol in uwp_protocols:
                return uwp_protocols[protocol]
            return (protocol,)

        file_name = Path(target_clean).name.casefold()

        if file_name in PROCESS_NAME_OVERRIDES:
            return PROCESS_NAME_OVERRIDES[file_name]

        if file_name.endswith(".exe"):
            return (file_name,)

        if file_name.endswith(".lnk"):
            stem = Path(file_name).stem.casefold().replace(" ", "")
            return (f"{stem}.exe",)

        return (file_name,)
