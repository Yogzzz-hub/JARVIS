"""Comprehensive Automated Test Suite for Application Discovery & Path Resolution.
Tests AppCatalog, PackageCatalog, ExecutableResolver, AliasResolver, Security Invariants,
Software Installation Lifecycle, and Performance Latencies.
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import time
from unittest.mock import MagicMock, Mock, patch
import pytest

from jarvis.core.catalog.alias_resolver import AliasResolver
from jarvis.core.catalog.app_catalog import AppCatalog
from jarvis.core.catalog.executable_resolver import ExecutableResolver
from jarvis.core.catalog.models import AppEntry, AvailabilityState, PackageEntry
from jarvis.core.catalog.package_catalog import PackageCatalog
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.router.models import RouteLane
from jarvis.core.router.router import SmartRouter
from jarvis.tools.system.app_resolver import LaunchTarget
from jarvis.tools.system.app_tools import (
    CheckAppInstalledTool,
    GetAppLocationTool,
    InstallSoftwareTool,
    ListInstalledApplicationsTool,
    RefreshApplicationsTool,
)


@pytest.fixture
def mock_fs_env(tmp_path):
    """Sets up a mock Windows directory hierarchy with trusted and untrusted locations."""
    sys_root = tmp_path / "Windows"
    sys_root.mkdir()
    prog_files = tmp_path / "Program Files"
    prog_files.mkdir()
    local_app = tmp_path / "AppData" / "Local"
    (local_app / "Programs").mkdir(parents=True)
    (local_app / "Temp").mkdir(parents=True)
    downloads = tmp_path / "Downloads"
    downloads.mkdir()

    # Trusted executables
    notepad_exe = sys_root / "notepad.exe"
    notepad_exe.write_bytes(b"MZfakebinary")

    vlc_dir = prog_files / "VideoLAN" / "VLC"
    vlc_dir.mkdir(parents=True)
    vlc_exe = vlc_dir / "vlc.exe"
    vlc_exe.write_bytes(b"MZfakebinary")

    code_dir = local_app / "Programs" / "Microsoft VS Code"
    code_dir.mkdir(parents=True)
    code_exe = code_dir / "Code.exe"
    code_exe.write_bytes(b"MZfakebinary")

    # Untrusted executables
    malicious_temp = local_app / "Temp" / "fake_installer.exe"
    malicious_temp.write_bytes(b"MZfakebinary")

    malicious_dl = downloads / "sketchy_app.exe"
    malicious_dl.write_bytes(b"MZfakebinary")

    return {
        "root": tmp_path,
        "sys_root": sys_root,
        "prog_files": prog_files,
        "local_app": local_app,
        "notepad_exe": notepad_exe,
        "vlc_exe": vlc_exe,
        "code_exe": code_exe,
        "temp_exe": malicious_temp,
        "dl_exe": malicious_dl,
    }


# =====================================================================
# 1. EXECUTABLE RESOLVER & TRUSTED ROOTS SECURITY TESTS
# =====================================================================

def test_executable_resolver_security(mock_fs_env):
    """CRITICAL SECURITY TEST: Only executables in trusted roots are accepted. Untrusted paths rejected."""
    trusted_roots = [
        mock_fs_env["sys_root"],
        mock_fs_env["prog_files"],
        mock_fs_env["local_app"] / "Programs",
    ]
    resolver = ExecutableResolver(extra_trusted_roots=trusted_roots)

    # 1. Trusted paths must validate
    assert resolver.validate_executable(mock_fs_env["notepad_exe"]) is not None
    assert resolver.validate_executable(mock_fs_env["vlc_exe"]) is not None
    assert resolver.validate_executable(mock_fs_env["code_exe"]) is not None

    # 2. Untrusted temporary directory paths MUST BE REJECTED
    assert resolver.validate_executable(mock_fs_env["temp_exe"]) is None
    assert resolver.is_trusted_location(mock_fs_env["temp_exe"]) is False

    # 3. Downloads folder paths MUST BE REJECTED
    assert resolver.validate_executable(mock_fs_env["dl_exe"]) is None
    assert resolver.is_trusted_location(mock_fs_env["dl_exe"]) is False

    # 4. Raw WindowsApps paths rejected
    windows_apps_exe = mock_fs_env["prog_files"] / "WindowsApps" / "calc.exe"
    assert resolver.is_trusted_location(windows_apps_exe) is False


# =====================================================================
# 2. ALIAS RESOLVER TESTS
# =====================================================================

def test_alias_resolver_normalization_and_ambiguity():
    """Tests conversational query normalization and ambiguity detection."""
    resolver = AliasResolver()
    resolver.register_alias("vlc", "vlc")
    resolver.register_alias("vlc media player", "vlc")
    resolver.register_alias("chrome", "chrome")
    resolver.register_alias("visual studio code", "vscode")

    # Conversational variations
    app_id, ambig, prompt = resolver.resolve("can you please open VLC for me")
    assert app_id == "vlc"
    assert ambig is None

    app_id, ambig, prompt = resolver.resolve("launch the vlc media player app please")
    assert app_id == "vlc"

    app_id, ambig, prompt = resolver.resolve("open vs code")
    assert app_id == "vscode"

    # Inherent ambiguity test (e.g. 'studio')
    app_id, ambig, prompt = resolver.resolve("open studio")
    assert app_id is None
    assert ambig is not None
    assert len(ambig) > 1
    assert "Which one do you mean" in prompt


# =====================================================================
# 3. PACKAGE CATALOG TESTS
# =====================================================================

def test_package_catalog_resolution():
    """Tests exact package resolution and trusted install command construction."""
    catalog = PackageCatalog()

    # 1. Exact resolution for VLC
    pkg = catalog.resolve_package("vlc")
    assert pkg is not None
    assert pkg.package_id == "VideoLAN.VLC"
    assert pkg.canonical_name == "vlc"

    # 2. Command builder generates silent administrative winget command
    cmd = catalog.build_install_command(pkg)
    assert "winget install --id VideoLAN.VLC" in cmd
    assert "-e --silent" in cmd
    assert "--accept-source-agreements" in cmd
    assert "--accept-package-agreements" in cmd

    # 3. Resolution for VS Code
    pkg_vscode = catalog.resolve_package("vs code")
    assert pkg_vscode is not None
    assert pkg_vscode.package_id == "Microsoft.VisualStudioCode"

    # 4. Unknown package returns None gracefully
    pkg_unknown = catalog.resolve_package("nonexistent_random_software_xyz123")
    assert pkg_unknown is None


# =====================================================================
# 4. APPCATALOG HOT-PATH & ZERO-RESCAN CACHING
# =====================================================================

def test_app_catalog_hot_path_zero_disk_rescan(mock_fs_env, monkeypatch):
    """
    CRITICAL HOT PATH INVARIANT:
    'Open Chrome' or 'Open VLC' MUST NOT rescan the filesystem or registry.
    """
    cache_file = mock_fs_env["root"] / "app_catalog_cache.json"
    catalog = AppCatalog(cache_path=cache_file, auto_build=False)

    # Register known test app
    vlc_entry = AppEntry(
        app_id="vlc",
        display_name="VLC Media Player",
        canonical_name="vlc",
        aliases=("vlc", "vlc player", "vlc media player"),
        executable_path=str(mock_fs_env["vlc_exe"]),
        source="registry_uninstall",
        process_names=("vlc.exe",),
    )
    catalog.register_entry(vlc_entry)

    # Monkeypatch os.walk, os.scandir, and winreg to blow up if called on hot path!
    monkeypatch.setattr("os.walk", Mock(side_effect=AssertionError("Hot path must NOT call os.walk")))
    monkeypatch.setattr("os.scandir", Mock(side_effect=AssertionError("Hot path must NOT call os.scandir")))

    # Resolve hot path
    t0 = time.perf_counter_ns()
    target = catalog.resolve("open vlc")
    elapsed_us = (time.perf_counter_ns() - t0) / 1000.0

    assert target is not None
    assert target.path == str(mock_fs_env["vlc_exe"])
    assert "vlc.exe" in target.process_names
    # Verify sub-millisecond lookup
    assert elapsed_us < 1000.0, f"Hot path took {elapsed_us:.2f} µs, expected < 1000 µs"


# =====================================================================
# 5. SOFTWARE INSTALLATION & AUTOMATIC REFRESH LIFECYCLE
# =====================================================================

def test_software_installation_lifecycle_and_auto_refresh(mock_fs_env, monkeypatch):
    """
    Simulates:
    1. Software is not installed initially.
    2. User says 'Install VLC'.
    3. Installation succeeds.
    4. AppCatalog AUTOMATICALLY refreshes without restarting JARVIS.
    5. 'Open VLC' immediately resolves.
    """
    cache_file = mock_fs_env["root"] / "app_catalog_cache.json"
    catalog = AppCatalog(cache_path=cache_file, auto_build=False)

    # Initially, VLC is NOT indexed
    is_inst, _ = catalog.is_installed("vlc")
    assert is_inst is False

    with pytest.raises(ValueError):
        catalog.resolve("vlc")

    # Mock subprocess.run for winget installer
    mock_run = MagicMock()
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "Successfully installed VideoLAN.VLC"
    mock_run.return_value.stderr = ""
    monkeypatch.setattr("subprocess.run", mock_run)
    monkeypatch.setattr("jarvis.tools.system.winget.executable", lambda: "winget.exe")

    # Mock targeted discovery simulating newly installed VLC files appearing
    def mock_targeted_check(app_name):
        catalog.register_entry(
            AppEntry(
                app_id="vlc",
                display_name="VLC Media Player",
                canonical_name="vlc",
                aliases=("vlc", "vlc media player", "vlc player"),
                executable_path=str(mock_fs_env["vlc_exe"]),
                source="targeted_install",
                install_location=str(mock_fs_env["vlc_exe"].parent),
                version="3.0.21",
                process_names=("vlc.exe",),
            )
        )
    monkeypatch.setattr(catalog, "_targeted_check", mock_targeted_check)

    # Run InstallSoftwareTool
    install_tool = InstallSoftwareTool(catalog=catalog)
    res = install_tool.run({"name": "vlc"})

    assert res["status"] == "SUCCESS"
    assert res["app_name"] == "VLC Media Player"
    assert "is installed" in res["message"] and "Open VLC Media Player" in res["message"]
    assert "--silent" in mock_run.call_args[0][0] and "VideoLAN.VLC" in mock_run.call_args[0][0]

    # Invariant: Next command 'Open VLC' MUST WORK without restart!
    target = catalog.resolve("Open VLC")
    assert target is not None
    assert target.path == str(mock_fs_env["vlc_exe"])
    assert "vlc.exe" in target.process_names

    # Invariant: is_installed and where_installed return verified information
    is_inst, entry = catalog.is_installed("vlc")
    assert is_inst is True
    assert entry.version == "3.0.21"

    loc = catalog.where_installed("vlc")
    assert loc == str(mock_fs_env["vlc_exe"].parent)


# =====================================================================
# 6. APPLICATION DISCOVERY TOOLS & COMMANDS
# =====================================================================

def test_application_discovery_tools(mock_fs_env):
    """Tests refresh_applications, list_installed_applications, check_app_installed, get_app_location."""
    cache_file = mock_fs_env["root"] / "app_catalog_cache.json"
    catalog = AppCatalog(cache_path=cache_file, auto_build=False)

    # Register test applications
    catalog.register_entry(
        AppEntry(
            app_id="vlc",
            display_name="VLC Media Player",
            canonical_name="vlc",
            aliases=("vlc", "vlc media player"),
            executable_path=str(mock_fs_env["vlc_exe"]),
            install_location=str(mock_fs_env["vlc_exe"].parent),
            version="3.0.21",
            source="registry_uninstall",
        )
    )
    catalog.register_entry(
        AppEntry(
            app_id="chrome",
            display_name="Google Chrome",
            canonical_name="chrome",
            aliases=("chrome", "google chrome"),
            executable_path="C:\\Program Files\\Google\\Chrome\\chrome.exe",
            version="128.0",
            source="registry_uninstall",
        )
    )

    # 1. check_app_installed tool ("Is VLC installed?")
    check_tool = CheckAppInstalledTool(catalog=catalog)
    res_vlc = check_tool.run({"name": "vlc"})
    assert res_vlc["installed"] is True
    assert "VLC Media Player" in res_vlc["message"]
    assert "3.0.21" in res_vlc["message"]

    res_unknown = check_tool.run({"name": "nonexistent_app"})
    assert res_unknown["installed"] is False
    assert "not currently installed" in res_unknown["message"]

    # 2. get_app_location tool ("Where is VLC installed?")
    loc_tool = GetAppLocationTool(catalog=catalog)
    res_loc = loc_tool.run({"name": "vlc"})
    assert res_loc["found"] is True
    assert str(mock_fs_env["vlc_exe"].parent) in res_loc["message"]

    res_loc_unknown = loc_tool.run({"name": "fake_app"})
    assert res_loc_unknown["found"] is False

    # 3. list_installed_applications tool ("Show installed applications")
    list_tool = ListInstalledApplicationsTool(catalog=catalog)
    res_list = list_tool.run({})
    assert res_list["status"] == "SUCCESS"
    assert res_list["total_installed"] >= 2
    assert "VLC Media Player" in res_list["spoken_summary"]

    # 4. refresh_applications tool ("Refresh applications")
    refresh_tool = RefreshApplicationsTool(catalog=catalog)
    res_ref = refresh_tool.run({"force": False})
    assert res_ref["status"] == "SUCCESS"
    assert "Application catalog refreshed" in res_ref["message"]


# =====================================================================
# 7. ROUTER FAST-PATH INTEGRATION
# =====================================================================

@pytest.mark.asyncio
async def test_router_application_discovery_intents():
    """Verifies that user natural language commands route to exact Lane 0 application discovery intents."""
    router = SmartRouter()

    # "Refresh applications."
    d1 = await router.route("Refresh applications.")
    assert d1.lane == RouteLane.LANE_0
    assert d1.intent == "refresh_applications"

    # "Show installed applications."
    d2 = await router.route("Show installed applications.")
    assert d2.lane == RouteLane.LANE_0
    assert d2.intent == "list_installed_applications"

    # "Is VLC installed?"
    d3 = await router.route("Is VLC installed?")
    assert d3.lane == RouteLane.LANE_0
    assert d3.intent == "check_app_installed"
    assert d3.slots["name"].lower() == "vlc"

    # "Where is VLC installed?"
    d4 = await router.route("Where is VLC installed?")
    assert d4.lane == RouteLane.LANE_0
    assert d4.intent == "get_app_location"
    assert d4.slots["name"].lower() == "vlc"

    # "Install VLC."
    d5 = await router.route("Install VLC.")
    assert d5.lane == RouteLane.LANE_0
    assert d5.intent == "install_software"
    assert d5.slots["name"].lower() == "vlc"


# =====================================================================
# 8. PERFORMANCE BENCHMARK: REFRESH VS LAUNCH HOT-PATH
# =====================================================================

def test_performance_benchmark_catalog_refresh_vs_launch(mock_fs_env):
    """
    Benchmarks:
    1. Catalog refresh execution time.
    2. Cached application launch hot-path resolution time.
    Asserts normal application launch remains ultra-fast without rescanning.
    """
    cache_file = mock_fs_env["root"] / "app_catalog_cache.json"
    catalog = AppCatalog(cache_path=cache_file, auto_build=False)

    catalog.register_entry(
        AppEntry(
            app_id="vlc",
            display_name="VLC Media Player",
            canonical_name="vlc",
            aliases=("vlc", "vlc player"),
            executable_path=str(mock_fs_env["vlc_exe"]),
        )
    )

    # 1. Benchmark catalog refresh
    t0_refresh = time.perf_counter_ns()
    summary = catalog.refresh(full=False)
    refresh_dur_ms = (time.perf_counter_ns() - t0_refresh) / 1e6

    # 2. Benchmark hot-path launch resolution (100 iterations)
    launch_latencies_us = []
    for _ in range(100):
        t0_launch = time.perf_counter_ns()
        target = catalog.resolve("vlc")
        dur_us = (time.perf_counter_ns() - t0_launch) / 1000.0
        launch_latencies_us.append(dur_us)

    p50_launch_us = sorted(launch_latencies_us)[50]
    p95_launch_us = sorted(launch_latencies_us)[95]

    print(f"\n[BENCHMARK] Catalog Refresh: {refresh_dur_ms:.2f} ms")
    print(f"[BENCHMARK] Application Launch Hot Path: p50={p50_launch_us:.2f} µs, p95={p95_launch_us:.2f} µs")

    # Invariants
    assert p50_launch_us < 200.0, f"Hot path p50 too slow: {p50_launch_us} µs"
    assert target.path == str(mock_fs_env["vlc_exe"])
