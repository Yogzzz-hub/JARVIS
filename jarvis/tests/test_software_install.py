"""Installing, removing and updating apps with winget: table parsing, exit codes, routing."""
from __future__ import annotations

import pytest

from jarvis.tools.system import winget

SEARCH_OUT = """
   - \\ |
Name                          Id                                 Version        Match       Source
---------------------------------------------------------------------------------------------------
VLC media player              VideoLAN.VLC                       3.0.21                     winget
VLC UWP                       9NBLGGH4VVNH                       Unknown                    msstore
Android Studio                Google.AndroidStudio               2024.2.1.12    Tag: vlc    winget
Some Very Long Application N… Vendor.SomeVeryLongApplicationNam… 1.0                        winget
"""


def test_search_table_is_parsed_by_column_and_truncated_rows_are_dropped():
    pkgs = winget.parse_table(SEARCH_OUT)
    ids = [p.package_id for p in pkgs]
    assert ids == ["VideoLAN.VLC", "9NBLGGH4VVNH", "Google.AndroidStudio"]
    assert pkgs[0].name == "VLC media player" and pkgs[0].version == "3.0.21" and pkgs[0].source == "winget"
    assert pkgs[2].name == "Android Studio"


def test_best_match_prefers_the_real_app_from_winget():
    pkgs = winget.parse_table(SEARCH_OUT)
    assert winget.best_match("vlc", pkgs).package_id == "VideoLAN.VLC"
    assert winget.best_match("android studio", pkgs).package_id == "Google.AndroidStudio"


@pytest.mark.parametrize("code,text,status,ok", [
    (0, "Successfully installed", "INSTALLED", True),
    (-1978335189, "No available upgrade found.", "ALREADY_INSTALLED", True),
    (0x8A150061 - (1 << 32), "Package is already installed", "ALREADY_INSTALLED", True),
    (3010, "", "REBOOT_REQUIRED", True),
    (-1978335212, "No package found matching input criteria.", "NOT_FOUND", False),
    (1603, "Installer failed with exit code: 1603", "FAILED", False),
])
def test_exit_codes_are_understood(code, text, status, ok):
    res = winget._classify(code, text)
    assert (res.status, res.ok) == (status, ok)


def test_install_tool_reports_why_it_failed(monkeypatch):
    from jarvis.core.catalog.package_catalog import PackageCatalog, PackageEntry
    from jarvis.tools.system.app_tools import InstallSoftwareTool

    class Catalog:
        package_catalog = PackageCatalog({"vlc": PackageEntry(package_id="VideoLAN.VLC", display_name="VLC media player",
                                                             canonical_name="vlc", aliases=("vlc",), installer_type="winget",
                                                             expected_executable_stems=("vlc",))})
        refreshed = []

        def is_installed(self, name):
            return False, None

        def refresh(self, targeted=None):
            self.refreshed.append(targeted)

    calls = []
    monkeypatch.setattr(winget, "executable", lambda: "winget.exe")
    monkeypatch.setattr(winget, "install", lambda pid, **kw: calls.append(pid) or winget.WingetResult(False, 1603, "FAILED",
                        "Downloading...\nInstaller failed with exit code: 1603"))
    tool = InstallSoftwareTool(catalog=Catalog())
    res = tool.run({"name": "vlc"})
    assert calls == ["VideoLAN.VLC"]
    assert res["status"] == "FAILED" and "code 1603" in res["message"] and "Installer failed" in res["message"]

    monkeypatch.setattr(winget, "install", lambda pid, **kw: winget.WingetResult(True, -1978335189, "ALREADY_INSTALLED", ""))
    res = tool.run({"name": "vlc"})
    assert res["status"] == "SUCCESS" and "already installed" in res["message"]


def test_install_without_winget_explains_what_to_do(monkeypatch):
    from jarvis.core.catalog.package_catalog import PackageCatalog
    from jarvis.tools.system.app_tools import InstallSoftwareTool

    class Catalog:
        package_catalog = PackageCatalog()

        def is_installed(self, name):
            return False, None

        def refresh(self, targeted=None):
            pass

    monkeypatch.setattr(winget, "executable", lambda: None)
    res = InstallSoftwareTool(catalog=Catalog()).run({"name": "vlc"})
    assert res["status"] == "FAILED" and "App Installer" in res["message"]


@pytest.mark.asyncio
@pytest.mark.parametrize("text,intent,name", [
    ("install vlc", "install_software", "vlc"),
    ("can you install android studio for me", "install_software", "android studio"),
    ("install visual studio code on my laptop", "install_software", "visual studio code"),
    ("uninstall zoom", "uninstall_software", "zoom"),
    ("remove the zoom app", "uninstall_software", "zoom"),
    ("update all my apps", "update_software", None),
    ("update the chrome app", "update_software", "chrome"),
])
async def test_software_requests_route_to_the_right_tool(text, intent, name):
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter
    from jarvis.memory.working_memory import WorkingMemory

    router = SmartRouter(llm_provider=DisabledProvider(), working_memory=WorkingMemory())
    dec = await router.route(text)
    assert dec.intent == intent, (text, dec)
    assert dec.slots.get("name") == name


@pytest.mark.asyncio
async def test_deleting_a_file_is_not_uninstalling():
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter
    from jarvis.memory.working_memory import WorkingMemory

    dec = await SmartRouter(llm_provider=DisabledProvider(), working_memory=WorkingMemory()).route("delete report.pdf")
    assert dec.intent == "delete_file"
