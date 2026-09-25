"""Package Catalog and Software Installer Integration for JARVIS EDGE.
Provides exact package resolution, trusted installer command generation,
and installation verification for winget packages.
"""
from __future__ import annotations

import logging
import re
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

from jarvis.core.catalog.models import PackageEntry

logger = logging.getLogger("jarvis.catalog.package_catalog")

# Curated repository of trusted Windows packages commonly requested
CURATED_PACKAGES: Dict[str, PackageEntry] = {
    "vlc": PackageEntry(
        package_id="VideoLAN.VLC",
        display_name="VLC Media Player",
        canonical_name="vlc",
        aliases=("vlc", "vlc media player", "vlc player", "videolan", "videolan vlc"),
        installer_type="winget",
        category="media",
        expected_process_names=("vlc.exe",),
        expected_executable_stems=("vlc",),
    ),
    "vscode": PackageEntry(
        package_id="Microsoft.VisualStudioCode",
        display_name="Visual Studio Code",
        canonical_name="vscode",
        aliases=("vscode", "vs code", "visual studio code", "code"),
        installer_type="winget",
        category="development",
        expected_process_names=("code.exe",),
        expected_executable_stems=("code",),
    ),
    "chrome": PackageEntry(
        package_id="Google.Chrome",
        display_name="Google Chrome",
        canonical_name="chrome",
        aliases=("chrome", "google chrome", "chrome browser"),
        installer_type="winget",
        category="browser",
        expected_process_names=("chrome.exe",),
        expected_executable_stems=("chrome",),
    ),
    "firefox": PackageEntry(
        package_id="Mozilla.Firefox",
        display_name="Mozilla Firefox",
        canonical_name="firefox",
        aliases=("firefox", "mozilla firefox", "mozilla"),
        installer_type="winget",
        category="browser",
        expected_process_names=("firefox.exe",),
        expected_executable_stems=("firefox",),
    ),
    "git": PackageEntry(
        package_id="Git.Git",
        display_name="Git",
        canonical_name="git",
        aliases=("git", "git scm", "git bash"),
        installer_type="winget",
        category="development",
        expected_process_names=("git.exe", "git-bash.exe"),
        expected_executable_stems=("git", "git-bash"),
    ),
    "ollama": PackageEntry(
        package_id="Ollama.Ollama",
        display_name="Ollama",
        canonical_name="ollama",
        aliases=("ollama", "ollama ai"),
        installer_type="winget",
        category="ai",
        expected_process_names=("ollama.exe", "ollama app.exe"),
        expected_executable_stems=("ollama",),
    ),
    "obs": PackageEntry(
        package_id="OBSProject.OBSStudio",
        display_name="OBS Studio",
        canonical_name="obs",
        aliases=("obs", "obs studio", "open broadcaster software"),
        installer_type="winget",
        category="media",
        expected_process_names=("obs64.exe", "obs32.exe", "obs.exe"),
        expected_executable_stems=("obs64", "obs32", "obs"),
    ),
    "7zip": PackageEntry(
        package_id="7zip.7zip",
        display_name="7-Zip",
        canonical_name="7zip",
        aliases=("7zip", "7-zip", "7z"),
        installer_type="winget",
        category="utilities",
        expected_process_names=("7zfm.exe", "7z.exe"),
        expected_executable_stems=("7zfm", "7z"),
    ),
    "notepadplusplus": PackageEntry(
        package_id="Notepad++.Notepad++",
        display_name="Notepad++",
        canonical_name="notepadplusplus",
        aliases=("notepad++", "notepad plus plus", "npp"),
        installer_type="winget",
        category="utilities",
        expected_process_names=("notepad++.exe",),
        expected_executable_stems=("notepad++",),
    ),
    "brave": PackageEntry(
        package_id="Brave.Brave",
        display_name="Brave Browser",
        canonical_name="brave",
        aliases=("brave", "brave browser"),
        installer_type="winget",
        category="browser",
        expected_process_names=("brave.exe",),
        expected_executable_stems=("brave",),
    ),
    "spotify": PackageEntry(
        package_id="Spotify.Spotify",
        display_name="Spotify",
        canonical_name="spotify",
        aliases=("spotify", "spotify music"),
        installer_type="winget",
        category="media",
        expected_process_names=("spotify.exe",),
        expected_executable_stems=("spotify",),
    ),
    "discord": PackageEntry(
        package_id="Discord.Discord",
        display_name="Discord",
        canonical_name="discord",
        aliases=("discord",),
        installer_type="winget",
        category="communication",
        expected_process_names=("discord.exe",),
        expected_executable_stems=("discord",),
    ),
    "zoom": PackageEntry(
        package_id="Zoom.Zoom",
        display_name="Zoom Workplace",
        canonical_name="zoom",
        aliases=("zoom", "zoom meetings"),
        installer_type="winget",
        category="communication",
        expected_process_names=("zoom.exe",),
        expected_executable_stems=("zoom",),
    ),
}


class PackageCatalog:
    """Manages package discovery, exact package matching, and trusted installation commands."""

    def __init__(self, packages: Optional[Dict[str, PackageEntry]] = None):
        self._packages: Dict[str, PackageEntry] = dict(packages or CURATED_PACKAGES)
        self._alias_map: Dict[str, PackageEntry] = {}
        self._rebuild_alias_map()

    def _rebuild_alias_map(self) -> None:
        self._alias_map.clear()
        for pkg in self._packages.values():
            self._alias_map[pkg.canonical_name.casefold()] = pkg
            self._alias_map[pkg.display_name.casefold()] = pkg
            self._alias_map[pkg.package_id.casefold()] = pkg
            for alias in pkg.aliases:
                self._alias_map[alias.casefold()] = pkg

    def resolve_package(self, name_or_query: str) -> Optional[PackageEntry]:
        """Resolves user query to an exact PackageEntry."""
        clean = " ".join(name_or_query.strip().casefold().split())
        clean = re.sub(r"^(?:please\s+|install\s+|setup\s+|download\s+|the\s+)+", "", clean).strip()

        # 1. Exact alias match in curated repository
        if clean in self._alias_map:
            return self._alias_map[clean]

        # 2. Substring match in curated repository
        for alias, pkg in self._alias_map.items():
            if len(clean) >= 3 and (clean == alias or clean in alias):
                return pkg

        # 3. Dynamic winget search fallback if winget is available
        dynamic_pkg = self._search_winget(clean)
        if dynamic_pkg:
            self._packages[dynamic_pkg.canonical_name] = dynamic_pkg
            self._rebuild_alias_map()
            return dynamic_pkg

        return None

    def _search_winget(self, query: str) -> Optional[PackageEntry]:
        """Finds the best winget package for a spoken name ("vlc", "android studio", "obs")."""
        from jarvis.tools.system import winget

        if not winget.executable():
            return None
        try:
            pkg = winget.best_match(query, winget.search(query))
        except Exception as exc:
            logger.debug("Dynamic winget search error for %s: %s", query, exc)
            return None
        if pkg is None:
            return None
        canonical = re.sub(r"[^a-z0-9]+", "", query.lower()) or pkg.package_id.lower()
        stem = re.sub(r"[^a-z0-9]+", "", pkg.name.lower())
        return PackageEntry(
            package_id=pkg.package_id,
            display_name=pkg.name,
            canonical_name=canonical,
            aliases=(query.lower(), pkg.name.lower()),
            installer_type="winget",
            expected_executable_stems=tuple(dict.fromkeys((canonical, stem))),
        )

    def build_install_command(self, package: PackageEntry) -> str:
        """Constructs trusted silent administrative winget install command string."""
        return f"winget install --id {package.package_id} -e --silent --accept-source-agreements --accept-package-agreements"

    def list_curated_packages(self) -> List[PackageEntry]:
        return list(self._packages.values())
