"""Central Application Catalog for JARVIS EDGE.
Provides automatic multi-source application discovery, canonical launch metadata tracking,
fast in-memory cached resolution, and deterministic query commands.
Subclasses AppResolver for 100% backward compatibility with all existing tools and tests.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import shutil
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from jarvis.config import ROOT
from jarvis.core.catalog.alias_resolver import AliasResolver
from jarvis.core.catalog.executable_resolver import ExecutableResolver
from jarvis.core.catalog.models import AppEntry, AvailabilityState, RefreshSummary
from jarvis.core.catalog.package_catalog import PackageCatalog
from jarvis.tools.system.app_resolver import (
    ALIASES,
    SYNONYMS,
    WEB_SERVICES,
    AppResolver,
    LaunchTarget,
    normalize,
    trusted_executable,
)

logger = logging.getLogger("jarvis.catalog.app_catalog")

# Standard Windows UWP protocol targets
UWP_PROTOCOLS: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "settings": ("ms-settings:", ("systemsettings.exe",)),
    "default apps": ("ms-settings:defaultapps", ("systemsettings.exe",)),
    "defaultapps": ("ms-settings:defaultapps", ("systemsettings.exe",)),
    "default applications": ("ms-settings:defaultapps", ("systemsettings.exe",)),
    "default app": ("ms-settings:defaultapps", ("systemsettings.exe",)),
    "photos": ("ms-photos:", ("microsoft.photos.exe",)),
    "microsoft photos": ("ms-photos:", ("microsoft.photos.exe",)),
    "camera": ("microsoft.windows.camera:", ("windowscamera.exe",)),
    "microsoft camera": ("microsoft.windows.camera:", ("windowscamera.exe",)),
    "clock": ("ms-clock:", ("time.exe",)),
    "windows clock": ("ms-clock:", ("time.exe",)),
    "alarms": ("ms-clock:", ("time.exe",)),
    "weather": ("bingweather:", ("microsoft.bingweather.exe",)),
    "msn weather": ("bingweather:", ("microsoft.bingweather.exe",)),
    "maps": ("bingmaps:", ("microsoft.windowsmaps.exe",)),
    "windows maps": ("bingmaps:", ("microsoft.windowsmaps.exe",)),
    "mail": ("outlookmail:", ("hxoutlook.exe",)),
    "outlook": ("outlookmail:", ("hxoutlook.exe",)),
    "calendar": ("outlookcal:", ("hxcalendarappimm.exe",)),
    "downloads": ("shell:Downloads", ("explorer.exe",)),
    "downloads folder": ("shell:Downloads", ("explorer.exe",)),
    "my downloads": ("shell:Downloads", ("explorer.exe",)),
    "documents": ("shell:Personal", ("explorer.exe",)),
    "documents folder": ("shell:Personal", ("explorer.exe",)),
    "my documents": ("shell:Personal", ("explorer.exe",)),
    "pictures": ("shell:My Pictures", ("explorer.exe",)),
    "pictures folder": ("shell:My Pictures", ("explorer.exe",)),
    "my pictures": ("shell:My Pictures", ("explorer.exe",)),
    "videos": ("shell:My Video", ("explorer.exe",)),
    "videos folder": ("shell:My Video", ("explorer.exe",)),
    "my videos": ("shell:My Video", ("explorer.exe",)),
    "music": ("shell:My Music", ("explorer.exe",)),
    "music folder": ("shell:My Music", ("explorer.exe",)),
    "my music": ("shell:My Music", ("explorer.exe",)),
}


class AppCatalog(AppResolver):
    """
    Authoritative Application Catalog for JARVIS EDGE.
    Extends AppResolver, providing multi-source discovery, rich metadata,
    and automatic post-installation registration.
    """

    _instance: Optional["AppCatalog"] = None

    def __init__(
        self,
        aliases: Any = (),
        cache_path: Optional[Path] = None,
        package_catalog: Optional[PackageCatalog] = None,
        auto_build: bool = True,
    ):
        super().__init__(aliases=aliases)
        self.cache_path = cache_path or (ROOT.parent / "data" / "app_catalog_cache.json")
        self.executable_resolver = ExecutableResolver()
        self.alias_resolver = AliasResolver()
        self.package_catalog = package_catalog or PackageCatalog()
        self._entries: Dict[str, AppEntry] = {}
        self._apps: Dict[str, LaunchTarget] = {}  # Compatibility with test fixtures
        self._last_mtimes: Dict[str, float] = {}
        self._last_refresh_summary: Optional[RefreshSummary] = None

        # Seed alias resolver with user aliases
        for name, raw_path in self.user_aliases:
            self.alias_resolver.register_alias(name, normalize(name))

        if auto_build:
            self.build()

    @classmethod
    def get_default(cls, aliases: Any = ()) -> "AppCatalog":
        if cls._instance is None:
            cls._instance = cls(aliases=aliases)
        return cls._instance

    def list_installed_entries(self) -> List[AppEntry]:
        """Returns all registered AppEntry metadata objects."""
        return sorted(self._entries.values(), key=lambda e: e.display_name.casefold())

    def get_app(self, name: str) -> Optional[AppEntry]:
        """Looks up canonical AppEntry by name or alias."""
        app_id, _, _ = self.alias_resolver.resolve(name)
        if app_id and app_id in self._entries:
            return self._entries[app_id]
        norm = normalize(name)
        if norm in self._entries:
            return self._entries[norm]
        for entry in self._entries.values():
            if norm == entry.canonical_name or norm == entry.display_name.casefold():
                return entry
            if norm in [a.casefold() for a in entry.aliases]:
                return entry
        return None

    def is_installed(self, name: str) -> Tuple[bool, Optional[AppEntry]]:
        """Answers 'Is <app> installed?' with verified metadata."""
        entry = self.get_app(name)
        if entry and entry.availability == AvailabilityState.AVAILABLE.value:
            return True, entry
        return False, None

    def where_installed(self, name: str) -> Optional[str]:
        """Answers 'Where is <app> installed?' returning path or install directory."""
        entry = self.get_app(name)
        if entry:
            return entry.install_location or entry.executable_path
        return None

    def register_entry(self, entry: AppEntry, update_resolver: bool = True) -> None:
        """Registers or updates an AppEntry and synchronizes launch targets."""
        self._entries[entry.app_id] = entry
        self.alias_resolver.register_app_aliases(entry.app_id, entry.display_name, entry.aliases)

        if update_resolver:
            target = LaunchTarget(
                path=entry.executable_path,
                process_names=entry.process_names,
                associated=entry.associated,
            )
            norm_id = normalize(entry.app_id)
            self.cache[norm_id] = target
            self.cache[normalize(entry.display_name)] = target
            self.cache[normalize(entry.canonical_name)] = target
            for alias in entry.aliases:
                self.cache[normalize(alias)] = target
            self._apps[norm_id] = target

    # =====================================================================
    # Discovery Engine
    # =====================================================================

    def build(self) -> None:
        """Performs initial build, loading persistent snapshot if available or running full scan."""
        # Try loading disk snapshot first for fast startup
        loaded_from_cache = self._load_cache_snapshot()
        if not loaded_from_cache or len(self._entries) < 10:
            self.refresh(full=True)
        else:
            # Rebuild resolver cache dict from entries
            self._rebuild_cache_from_entries()
            self.build_count += 1

    def refresh(self, full: bool = False, targeted: Optional[str] = None) -> RefreshSummary:
        """
        Executes discovery scan across all trusted Windows registration sources.
        Guarantees zero modification to Windows system PATH.
        """
        t0 = time.perf_counter()
        sources_scanned: List[str] = []
        old_count = len(self._entries)

        # 1. Base built-in applications and ALIASES
        self._scan_builtins()
        sources_scanned.append("built_in")

        # 2. Windows Registry: App Paths
        if os.name == "nt":
            self._scan_registry_app_paths()
            sources_scanned.append("app_paths")

        # 3. Windows Registry: Uninstall (32-bit & 64-bit)
        if os.name == "nt":
            self._scan_registry_uninstall()
            sources_scanned.append("registry_uninstall")

        # 4. Windows Start Menu Shortcuts (.lnk)
        if os.name == "nt":
            self._scan_start_menu_shortcuts()
            sources_scanned.append("start_menu")

        # 5. UWP / App Execution Aliases & Protocols
        if os.name == "nt":
            self._scan_uwp_and_execution_aliases()
            sources_scanned.append("uwp")

        # 6. Existing PATH Entries (inspect without mutating PATH)
        self._scan_existing_path_entries()
        sources_scanned.append("path")

        # 7. Web services & user configured aliases
        self._scan_web_and_user_aliases()
        sources_scanned.append("user_aliases")

        # Targeted scan if installing software
        if targeted:
            self._targeted_check(targeted)

        self._rebuild_cache_from_entries()
        self.build_count += 1
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        summary = RefreshSummary(
            total_apps=len(self._entries),
            new_apps=max(0, len(self._entries) - old_count),
            updated_apps=len(self._entries),
            elapsed_ms=elapsed_ms,
            sources_scanned=tuple(sources_scanned),
        )
        self._last_refresh_summary = summary
        self._save_cache_snapshot()
        logger.info(
            "AppCatalog refresh complete: %d apps in %.2f ms (sources: %s)",
            summary.total_apps,
            summary.elapsed_ms,
            ", ".join(sources_scanned),
        )
        return summary

    def _scan_builtins(self) -> None:
        """Indexes known built-in apps and ALIASES using executable resolver."""
        for name, (executable, procs) in ALIASES.items():
            # If already registered with a verified absolute path, do not overwrite with bare string!
            if name in self._entries:
                existing = self._entries[name]
                if existing.executable_path and os.path.isabs(existing.executable_path) and os.path.exists(existing.executable_path):
                    continue

            candidate = shutil.which(executable)
            cand_path = self.executable_resolver.validate_executable(candidate) if candidate else None
            path = cand_path or executable
            self.register_entry(
                AppEntry(
                    app_id=name,
                    display_name=name.title(),
                    canonical_name=name,
                    aliases=(name,),
                    executable_path=str(path),
                    source="built_in",
                    process_names=procs,
                    availability=AvailabilityState.AVAILABLE.value if cand_path or not os.path.isabs(path) else AvailabilityState.MISSING.value,
                ),
                update_resolver=False,
            )

    def _scan_registry_app_paths(self) -> None:
        """Reads HKLM and HKCU Software\\Microsoft\\Windows\\CurrentVersion\\App Paths."""
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive, r"Software\Microsoft\Windows\CurrentVersion\App Paths", 0, winreg.KEY_READ | view) as parent:
                        num_subkeys = winreg.QueryInfoKey(parent)[0]
                        for idx in range(num_subkeys):
                            try:
                                key_name = winreg.EnumKey(parent, idx)
                                with winreg.OpenKey(parent, key_name, 0, winreg.KEY_READ | view) as child:
                                    raw_val, _ = winreg.QueryValueEx(child, None)
                                    val_path = self.executable_resolver.validate_executable(raw_val)
                                    if val_path:
                                        stem = Path(key_name).stem.casefold()
                                        procs = self.executable_resolver.get_process_names(val_path)
                                        self.register_entry(
                                            AppEntry(
                                                app_id=stem,
                                                display_name=stem.title(),
                                                canonical_name=stem,
                                                aliases=(stem, key_name.casefold()),
                                                executable_path=val_path,
                                                source="app_paths",
                                                install_location=str(Path(val_path).parent),
                                                process_names=procs,
                                            ),
                                            update_resolver=False,
                                        )
                            except (OSError, ValueError):
                                continue
                except OSError:
                    continue

    def _scan_registry_uninstall(self) -> None:
        """Reads registered installed applications from Windows Uninstall registry keys."""
        import winreg
        uninstall_paths = (
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", winreg.KEY_WOW64_64KEY),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", winreg.KEY_WOW64_32KEY),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", 0),
        )

        for hive, subkey_path, view in uninstall_paths:
            try:
                flags = winreg.KEY_READ | view if view else winreg.KEY_READ
                with winreg.OpenKey(hive, subkey_path, 0, flags) as parent:
                    num_subkeys = winreg.QueryInfoKey(parent)[0]
                    for idx in range(num_subkeys):
                        try:
                            key_name = winreg.EnumKey(parent, idx)
                            with winreg.OpenKey(parent, key_name, 0, flags) as child:
                                display_name = self._reg_str(child, "DisplayName")
                                if not display_name:
                                    continue

                                # Ignore system updates or components
                                if self._reg_int(child, "SystemComponent") == 1:
                                    continue
                                parent_key = self._reg_str(child, "ParentKeyName")
                                if parent_key:
                                    continue

                                version = self._reg_str(child, "DisplayVersion")
                                install_loc = self._reg_str(child, "InstallLocation")
                                display_icon = self._reg_str(child, "DisplayIcon")
                                publisher = self._reg_str(child, "Publisher")

                                # Find primary executable
                                exe_path = None
                                if display_icon:
                                    clean_icon = display_icon.split(",")[0].strip().strip('"')
                                    exe_path = self.executable_resolver.validate_executable(clean_icon)

                                if not exe_path and install_loc and os.path.isdir(install_loc):
                                    exe_path = self._find_exe_in_dir(install_loc, display_name)

                                if exe_path:
                                    app_id = normalize(Path(exe_path).stem)
                                    procs = self.executable_resolver.get_process_names(exe_path)
                                    aliases = self._generate_aliases(display_name, app_id)
                                    self.register_entry(
                                        AppEntry(
                                            app_id=app_id,
                                            display_name=display_name.strip(),
                                            canonical_name=app_id,
                                            aliases=tuple(aliases),
                                            executable_path=exe_path,
                                            source="registry_uninstall",
                                            install_location=install_loc,
                                            version=version,
                                            process_names=procs,
                                            publisher=publisher,
                                        ),
                                        update_resolver=False,
                                    )
                        except (OSError, ValueError):
                            continue
            except OSError:
                continue

    def _scan_start_menu_shortcuts(self) -> None:
        """Discovers shortcuts from user and system Start Menu Programs."""
        roots = []
        for env_var in ("APPDATA", "PROGRAMDATA"):
            val = os.environ.get(env_var)
            if val:
                p = Path(val) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
                if p.is_dir():
                    roots.append(p)

        for root in roots:
            try:
                for lnk in root.rglob("*.lnk"):
                    stem = lnk.stem.casefold()
                    # Skip uninstaller shortcuts
                    if any(un in stem for un in ("uninstall", "remove", "help", "documentation", "readme")):
                        continue

                    target_path, is_associated = self.executable_resolver.resolve_shortcut(lnk)
                    app_id = normalize(stem)
                    procs = self.executable_resolver.get_process_names(target_path)
                    aliases = self._generate_aliases(lnk.stem, app_id)

                    self.register_entry(
                        AppEntry(
                            app_id=app_id,
                            display_name=lnk.stem.strip(),
                            canonical_name=app_id,
                            aliases=tuple(aliases),
                            executable_path=target_path,
                            source="start_menu",
                            install_location=str(Path(target_path).parent) if not is_associated else None,
                            process_names=procs,
                            associated=is_associated,
                        ),
                        update_resolver=False,
                    )
            except Exception as exc:
                logger.debug("Start menu shortcut scan error in %s: %s", root, exc)

    def _scan_uwp_and_execution_aliases(self) -> None:
        """Scans WindowsApps execution aliases and registers standard UWP protocol targets."""
        # 1. Standard protocol targets
        for name, (protocol, procs) in UWP_PROTOCOLS.items():
            app_id = normalize(name)
            self.register_entry(
                AppEntry(
                    app_id=app_id,
                    display_name=name.title(),
                    canonical_name=app_id,
                    aliases=(name,),
                    executable_path=protocol,
                    source="uwp",
                    process_names=procs,
                    associated=True,
                ),
                update_resolver=False,
            )

        # 2. LocalAppData\Microsoft\WindowsApps execution aliases (wt.exe, python.exe, etc.)
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            wa_path = Path(local_app) / "Microsoft" / "WindowsApps"
            if wa_path.is_dir():
                for exe in wa_path.glob("*.exe"):
                    val_path = self.executable_resolver.validate_executable(exe)
                    if val_path:
                        stem = exe.stem.casefold()
                        procs = self.executable_resolver.get_process_names(val_path)
                        self.register_entry(
                            AppEntry(
                                app_id=stem,
                                display_name=stem.title(),
                                canonical_name=stem,
                                aliases=(stem, exe.name.casefold()),
                                executable_path=val_path,
                                source="uwp_alias",
                                process_names=procs,
                            ),
                            update_resolver=False,
                        )

    def _scan_existing_path_entries(self) -> None:
        """Inspects executables in PATH directories without modifying PATH."""
        path_str = os.environ.get("PATH", "")
        for folder in path_str.split(os.pathsep):
            folder_clean = folder.strip().strip('"')
            if not folder_clean or not os.path.isdir(folder_clean):
                continue
            # Only check trusted system/program folders in PATH
            if not self.executable_resolver.is_trusted_location(folder_clean):
                continue
            try:
                for entry in os.scandir(folder_clean):
                    if entry.is_file() and entry.name.casefold().endswith(".exe"):
                        val = self.executable_resolver.validate_executable(entry.path)
                        if val:
                            stem = Path(entry.name).stem.casefold()
                            if stem not in self._entries:
                                procs = self.executable_resolver.get_process_names(val)
                                self.register_entry(
                                    AppEntry(
                                        app_id=stem,
                                        display_name=stem.title(),
                                        canonical_name=stem,
                                        aliases=(stem, entry.name.casefold()),
                                        executable_path=val,
                                        source="path",
                                        process_names=procs,
                                    ),
                                    update_resolver=False,
                                )
            except (OSError, PermissionError):
                continue

    def _scan_web_and_user_aliases(self) -> None:
        """Adds configured web services and explicit user aliases."""
        for svc_name, svc_url in WEB_SERVICES.items():
            self.register_entry(
                AppEntry(
                    app_id=svc_name,
                    display_name=svc_name.title(),
                    canonical_name=svc_name,
                    aliases=(svc_name,),
                    executable_path=svc_url,
                    source="web_service",
                    process_names=("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"),
                    associated=True,
                ),
                update_resolver=False,
            )

        for name, raw_path in self.user_aliases:
            path = Path(raw_path)
            if not path.is_absolute() or not path.is_file() or path.suffix.casefold() != ".exe":
                raise ValueError(f"alias {name!r} must reference an existing absolute .exe")
            app_id = normalize(name)
            self.register_entry(
                AppEntry(
                    app_id=app_id,
                    display_name=name,
                    canonical_name=app_id,
                    aliases=(name.casefold(), app_id),
                    executable_path=str(path),
                    source="user_alias",
                    process_names=(path.name.casefold(),),
                ),
                update_resolver=False,
            )

    def _targeted_check(self, app_name: str) -> None:
        """Targeted check for newly installed application in common ProgramFiles locations."""
        clean = app_name.strip().casefold()
        roots = [
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("LOCALAPPDATA"),
        ]
        for root in roots:
            if not root or not os.path.isdir(root):
                continue
            for cur_root, dirs, files in os.walk(root):
                # Don't go deeper than 3 levels for targeted check
                depth = len(Path(cur_root).relative_to(root).parts)
                if depth > 3:
                    dirs.clear()
                    continue
                for f in files:
                    if f.casefold().endswith(".exe") and clean in f.casefold():
                        val = self.executable_resolver.validate_executable(os.path.join(cur_root, f))
                        if val:
                            stem = Path(f).stem.casefold()
                            procs = self.executable_resolver.get_process_names(val)
                            self.register_entry(
                                AppEntry(
                                    app_id=stem,
                                    display_name=stem.title(),
                                    canonical_name=stem,
                                    aliases=(clean, stem),
                                    executable_path=val,
                                    source="targeted_install",
                                    install_location=cur_root,
                                    process_names=procs,
                                ),
                                update_resolver=False,
                            )
                            return

    def _rebuild_cache_from_entries(self) -> None:
        """Atomically populates self.cache dict from _entries for O(1) hot path."""
        new_cache: Dict[str, LaunchTarget] = {}
        for entry in self._entries.values():
            target = LaunchTarget(
                path=entry.executable_path,
                process_names=entry.process_names,
                associated=entry.associated,
            )
            new_cache[normalize(entry.app_id)] = target
            new_cache[normalize(entry.display_name)] = target
            new_cache[normalize(entry.canonical_name)] = target
            for alias in entry.aliases:
                new_cache[normalize(alias)] = target

        for alias, name in SYNONYMS.items():
            norm_name = normalize(name)
            if norm_name in new_cache:
                new_cache[normalize(alias)] = new_cache[norm_name]

        self.cache = new_cache
        self._apps = new_cache

    # =====================================================================
    # Hot-Path Resolution (Zero Disk Rescan)
    # =====================================================================

    def resolve(self, name: str) -> LaunchTarget:
        """
        Hot path: Resolves an application name to a LaunchTarget.
        O(1) in-memory lookup. Zero filesystem crawling or registry scanning.
        """
        # 1. Direct cache lookup (honors test mocks and exact matches)
        norm = normalize(name)
        if norm in self.cache:
            return self.cache[norm]

        cleaned = self.alias_resolver.clean_conversational(name)
        if cleaned in ("default apps", "defaultapps", "default applications", "default app"):
            return LaunchTarget("ms-settings:defaultapps", ("systemsettings.exe",), True)
        if cleaned in ("downloads", "download", "downloads folder", "my downloads"):
            return LaunchTarget("shell:Downloads", ("explorer.exe",), True)
        if cleaned in ("documents", "document", "documents folder", "my documents"):
            return LaunchTarget("shell:Personal", ("explorer.exe",), True)
        if cleaned in ("pictures", "pictures folder", "my pictures", "photos folder"):
            return LaunchTarget("shell:My Pictures", ("explorer.exe",), True)
        if cleaned in ("music", "music folder", "my music"):
            return LaunchTarget("shell:My Music", ("explorer.exe",), True)
        if cleaned in ("videos", "videos folder", "my videos"):
            return LaunchTarget("shell:My Video", ("explorer.exe",), True)
        if cleaned in ("desktop folder", "my desktop folder"):
            return LaunchTarget("shell:Desktop", ("explorer.exe",), True)
        if cleaned in self.cache:
            return self.cache[cleaned]

        if cleaned in SYNONYMS and SYNONYMS[cleaned] in self.cache:
            return self.cache[SYNONYMS[cleaned]]

        # 2. AliasResolver fast resolution
        app_id, ambiguous, prompt = self.alias_resolver.resolve(name)
        if ambiguous:
            raise ValueError(prompt or f"Application name '{name}' is ambiguous.")

        if app_id and app_id in self._entries:
            e = self._entries[app_id]
            return LaunchTarget(e.executable_path, e.process_names, e.associated)

        # 3. Check web services
        if cleaned in WEB_SERVICES:
            return LaunchTarget(WEB_SERVICES[cleaned], ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"), True)
        if norm in WEB_SERVICES:
            return LaunchTarget(WEB_SERVICES[norm], ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"), True)

        # 4. Word boundary or prefix match against registered cache keys
        for key, target in self.cache.items():
            if len(cleaned) >= 3 and (key.startswith(cleaned) or re.search(rf"\b{re.escape(cleaned)}\b", key)):
                return target

        # 5. Fallback to parent resolve if applicable
        return super().resolve(name)

    # =====================================================================
    # Helpers
    # =====================================================================

    def _generate_aliases(self, display_name: str, app_id: str) -> Set[str]:
        aliases = {app_id, display_name.casefold()}
        cleaned = re.sub(r"\s+\(.*?\)", "", display_name).strip().casefold()
        aliases.add(cleaned)
        # Add initials or words without publisher
        for pub in ("microsoft", "google", "mozilla", "videolan", "adobe", "apple"):
            if cleaned.startswith(pub + " "):
                aliases.add(cleaned[len(pub) + 1 :].strip())
        return aliases

    def _find_exe_in_dir(self, directory: str, display_name: str) -> Optional[str]:
        """Finds primary executable in an installation directory."""
        clean_name = re.sub(r"[^a-zA-Z0-9]", "", display_name).lower()
        candidates = []
        try:
            for root_dir, _, files in os.walk(directory):
                for f in files:
                    if f.casefold().endswith(".exe"):
                        full_p = os.path.join(root_dir, f)
                        val = self.executable_resolver.validate_executable(full_p)
                        if val:
                            candidates.append(val)
                # Don't recurse too deep
                if len(Path(root_dir).relative_to(directory).parts) >= 2:
                    break
        except Exception:
            pass

        if not candidates:
            return None

        # Prefer candidate matching clean display name
        for cand in candidates:
            cand_stem = Path(cand).stem.lower()
            if cand_stem in clean_name or clean_name in cand_stem:
                return cand
        return candidates[0]

    def _reg_str(self, key: Any, val_name: str) -> Optional[str]:
        import winreg
        try:
            val, _ = winreg.QueryValueEx(key, val_name)
            return str(val) if val else None
        except OSError:
            return None

    def _reg_int(self, key: Any, val_name: str) -> Optional[int]:
        import winreg
        try:
            val, _ = winreg.QueryValueEx(key, val_name)
            return int(val)
        except (OSError, ValueError):
            return None

    def _save_cache_snapshot(self) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "version": 1,
                "timestamp": time.time(),
                "entries": [e.to_dict() for e in self._entries.values()],
            }
            with self.cache_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as exc:
            logger.debug("Could not save AppCatalog snapshot: %s", exc)

    def _load_cache_snapshot(self) -> bool:
        if not self.cache_path.is_file():
            return False
        try:
            with self.cache_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            entries_raw = data.get("entries", [])
            for raw in entries_raw:
                entry = AppEntry.from_dict(raw)
                # Verify that the executable or launch target still exists
                if entry.associated or os.path.exists(entry.executable_path):
                    self.register_entry(entry, update_resolver=False)
            return len(self._entries) > 0
        except Exception as exc:
            logger.debug("Failed loading AppCatalog snapshot: %s", exc)
            return False
