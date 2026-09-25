"""Thin, robust wrapper around the Windows Package Manager (winget).

Why a wrapper: winget prints tables sized to the console (names/ids get truncated with "…"),
progress spinners, localized text and success-like non-zero exit codes. Everything that installs,
removes or updates software goes through here so those quirks are handled once.
"""
from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("jarvis.tools.winget")

# winget exit codes (HRESULTs as signed 32-bit ints) that are not real failures.
ALREADY_INSTALLED = {-1978335189, -1978335135, 0x8A15002B, 0x8A150061}  # no applicable upgrade / already installed
NO_PACKAGE_FOUND = {-1978335212, 0x8A150014}
REBOOT_REQUIRED = {3010, 1641, -1978335131, 0x8A150065}
INSTALLER_HASH_OR_POLICY = {-1978335215, 0x8A150011, -1978335191, 0x8A150029}

_NOISE = re.compile(r"[▀-▟─-╿█|/\\\-]{3,}|[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]")


@dataclass
class WingetPackage:
    name: str
    package_id: str
    version: str = ""
    source: str = ""


@dataclass
class WingetResult:
    ok: bool
    code: int
    status: str          # INSTALLED | ALREADY_INSTALLED | REBOOT_REQUIRED | NOT_FOUND | BLOCKED | FAILED | UNAVAILABLE
    output: str = ""

    @property
    def tail(self) -> str:
        lines = [ln.strip() for ln in self.output.splitlines() if ln.strip() and not _NOISE.search(ln)]
        return " ".join(lines[-3:])[:300]


def executable() -> Optional[str]:
    return shutil.which("winget.exe") or shutil.which("winget")


def _run(args: list[str], timeout: float) -> tuple[int, str]:
    exe = executable()
    if not exe:
        return -1, "winget is not available"
    proc = subprocess.run(
        [exe, *args],
        capture_output=True,
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    parts = [proc.stdout or b"", proc.stderr or b""]
    text = "\n".join(p.decode("utf-8", errors="replace") if isinstance(p, bytes) else str(p) for p in parts)
    code = proc.returncode
    if code > 0x7FFFFFFF:  # unsigned HRESULT -> signed, as winget documents them
        code -= 1 << 32
    return code, text


def parse_table(text: str) -> list[WingetPackage]:
    """Parse `winget search/list` output using the header's column offsets (names may contain spaces)."""
    lines = [ln.rstrip("\r") for ln in text.splitlines()]
    header_idx = next((i for i, ln in enumerate(lines)
                       if re.search(r"\bName\b", ln) and re.search(r"\bId\b", ln) and re.search(r"\bVersion\b", ln)), -1)
    if header_idx < 0:
        return []
    header = lines[header_idx]
    # the header can be preceded by spinner garbage on the same line
    start = header.find("Name")
    header = header[start:]
    cols = {name: header.find(name) for name in ("Name", "Id", "Version", "Match", "Source")}
    id_at, ver_at = cols["Id"], cols["Version"]
    after_ver = min([p for k, p in cols.items() if k in ("Match", "Source") and p > ver_at] or [10_000])
    src_at = cols["Source"] if cols["Source"] > 0 else -1
    out: list[WingetPackage] = []
    for ln in lines[header_idx + 1:]:
        if not ln.strip() or set(ln.strip()) <= set("-"):
            continue
        ln = ln[start:] if len(ln) > start else ln
        name = ln[:id_at].strip()
        pkg_id = ln[id_at:ver_at].strip()
        version = ln[ver_at:after_ver].strip() if after_ver < 10_000 else ln[ver_at:].strip().split(" ")[0]
        source = ln[src_at:].strip() if src_at > 0 else ""
        if not name or not pkg_id or " " in pkg_id or "…" in pkg_id:
            continue  # truncated or malformed row
        out.append(WingetPackage(name=name.rstrip("…").strip(), package_id=pkg_id, version=version, source=source))
    return out


def search(query: str, limit: int = 8, timeout: float = 30.0) -> list[WingetPackage]:
    code, text = _run(["search", "--query", query, "--accept-source-agreements", "--disable-interactivity",
                       "--count", str(limit)], timeout)
    if code not in (0,) and not parse_table(text):
        return []
    return parse_table(text)[:limit]


def best_match(query: str, packages: list[WingetPackage]) -> Optional[WingetPackage]:
    """Prefer an exact name, then a name starting with the query, then the winget community source."""
    if not packages:
        return None
    q = re.sub(r"[^a-z0-9]+", " ", query.lower()).strip()

    def score(p: WingetPackage) -> tuple:
        n = re.sub(r"[^a-z0-9]+", " ", p.name.lower()).strip()
        pid = p.package_id.lower()
        return (
            n == q,
            n.startswith(q) or q in pid.split(".")[-1],
            q in n,
            p.source.lower() == "winget",
            -len(n),
        )

    return max(packages, key=score)


def _classify(code: int, text: str) -> WingetResult:
    low = text.lower()
    if code == 0:
        if "restart" in low and "required" in low:
            return WingetResult(True, code, "REBOOT_REQUIRED", text)
        return WingetResult(True, code, "INSTALLED", text)
    if code in ALREADY_INSTALLED or "already installed" in low or "no available upgrade" in low or "no newer package" in low:
        return WingetResult(True, code, "ALREADY_INSTALLED", text)
    if code in REBOOT_REQUIRED:
        return WingetResult(True, code, "REBOOT_REQUIRED", text)
    if code in NO_PACKAGE_FOUND or "no package found" in low:
        return WingetResult(False, code, "NOT_FOUND", text)
    if code in INSTALLER_HASH_OR_POLICY or "blocked by policy" in low or "hash does not match" in low:
        return WingetResult(False, code, "BLOCKED", text)
    if code == -1 and "not available" in low:
        return WingetResult(False, code, "UNAVAILABLE", text)
    return WingetResult(False, code, "FAILED", text)


def install(package_id: str, timeout: float = 570.0, source: str = "") -> WingetResult:
    args = ["install", "--id", package_id, "--exact", "--silent", "--accept-source-agreements",
            "--accept-package-agreements", "--disable-interactivity"]
    if source:
        args += ["--source", source]
    try:
        code, text = _run(args, timeout)
    except subprocess.TimeoutExpired:
        return WingetResult(False, -2, "FAILED", f"The installer was still running after {timeout / 60:.0f} minutes.")
    return _classify(code, text)


def uninstall(package_id: str, timeout: float = 540.0) -> WingetResult:
    try:
        code, text = _run(["uninstall", "--id", package_id, "--exact", "--silent", "--accept-source-agreements",
                           "--disable-interactivity"], timeout)
    except subprocess.TimeoutExpired:
        return WingetResult(False, -2, "FAILED", "The uninstaller did not finish in time.")
    res = _classify(code, text)
    if res.status == "INSTALLED":
        res.status = "REMOVED"
    return res


def upgrade_all_background() -> bool:
    """Start `winget upgrade --all` detached (it may run for a long time)."""
    exe = executable()
    if not exe:
        return False
    try:
        subprocess.Popen(
            [exe, "upgrade", "--all", "--include-unknown", "--silent", "--accept-source-agreements",
             "--accept-package-agreements", "--disable-interactivity"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0),
        )
        return True
    except OSError as exc:
        logger.warning("Could not start winget upgrade: %s", exc)
        return False


def upgrade(package_id: str = "", timeout: float = 570.0) -> WingetResult:
    args = ["upgrade", "--silent", "--accept-source-agreements", "--accept-package-agreements", "--disable-interactivity"]
    args += ["--id", package_id, "--exact"] if package_id else ["--all", "--include-unknown"]
    try:
        code, text = _run(args, timeout)
    except subprocess.TimeoutExpired:
        return WingetResult(False, -2, "FAILED", "Updates were still running when I stopped waiting.")
    res = _classify(code, text)
    if res.status == "INSTALLED":
        res.status = "UPDATED"
    return res


def list_installed(query: str = "", timeout: float = 60.0) -> list[WingetPackage]:
    args = ["list", "--accept-source-agreements", "--disable-interactivity"]
    if query:
        args += ["--query", query]
    try:
        _code, text = _run(args, timeout)
    except subprocess.TimeoutExpired:
        return []
    return parse_table(text)
