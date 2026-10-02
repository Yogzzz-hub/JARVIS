from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

# Builtin protected roots on Windows
DEFAULT_PROTECTED_ROOTS = [
    "C:\\Windows",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
    "C:\\ProgramData",
    "C:\\Recovery",
    "C:\\System Volume Information",
]

def get_jarvis_protected_paths() -> list[str]:
    """Returns canonical paths to critical Jarvis assets that normal tools cannot mutate."""
    paths = []
    # Project root
    root = Path(__file__).resolve().parent.parent.parent
    paths.append(str(root / "jarvis" / "db" / "jarvis.db"))
    paths.append(str(root / "config" / "policy.toml"))
    paths.append(str(root / "jarvis" / "security"))
    paths.append(str(root / "jarvis" / "core"))
    return paths

def get_known_folder(folder_name: str) -> Path:
    """Dynamically resolves Windows Known Folders via registry and Known Folders API."""
    name_clean = folder_name.lower().strip()
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        guid_map = {
            "desktop": "Desktop",
            "downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
            "documents": "Personal",
            "pictures": "My Pictures",
            "music": "My Music",
            "videos": "My Video",
        }
        attr = guid_map.get(name_clean, name_clean)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as k:
            val, _ = winreg.QueryValueEx(k, attr)
            resolved = Path(os.path.expandvars(val)).resolve()
            if resolved.exists():
                return resolved
    except Exception:
        pass

    user_prof = Path(os.environ.get("USERPROFILE", str(Path.home())))
    candidates = [
        user_prof / "OneDrive" / folder_name.capitalize(),
        user_prof / folder_name.capitalize(),
        Path.home() / folder_name.capitalize(),
    ]
    for c in candidates:
        if c.exists():
            return c.resolve()
    return candidates[0]


def canonicalize_path(path_str: str | Path) -> Path:
    """Canonicalize a filesystem path:
    1. Expand environment variables (e.g. %WINDIR%, %USERPROFILE%)
    2. Expand ~ to user home
    3. Normalize slashes, eliminate redundant separators and traversal ('..')
    4. Resolve symlinks / junctions where the target exists
    5. Resolve simple names/relative paths to common user roots (Desktop, Downloads, Documents)
    """
    raw = str(path_str).strip().strip("'\"")
    lowered = raw.lower()

    # Exact known folder keywords / aliases
    if lowered in ("desktop", "~/desktop", "desk top"):
        return get_known_folder("desktop")
    if lowered in ("downloads", "~/downloads", "down loads"):
        return get_known_folder("downloads")
    if lowered in ("documents", "~/documents", "docs", "doc u ments"):
        return get_known_folder("documents")
    if lowered in ("pictures", "~/pictures", "photos"):
        return get_known_folder("pictures")
    if lowered in ("music", "~/music"):
        return get_known_folder("music")
    if lowered in ("videos", "~/videos"):
        return get_known_folder("videos")

    expanded = os.path.expanduser(os.path.expandvars(raw))
    p = Path(expanded)
    if p.is_absolute():
        try:
            return p.resolve(strict=False)
        except Exception:
            return Path(os.path.normpath(expanded))

    # "Documents/tax 2025", "pictures/trips": a known user folder first, then the rest inside it
    import re as _re
    m = _re.match(r"^(?P<k>desktop|downloads|documents|pictures|music|videos)[\\/]+(?P<rest>.+)$", raw, _re.IGNORECASE)
    if m:
        return (get_known_folder(m.group("k").lower()) / m.group("rest").strip()).resolve(strict=False)

    # For relative names, check approved user locations
    desktop = get_known_folder("desktop")
    downloads = get_known_folder("downloads")
    documents = get_known_folder("documents")

    for base in (desktop, downloads, documents, Path.cwd()):
        candidate = base / raw
        if candidate.exists():
            return candidate.resolve(strict=False)

    # If location keyword is present in relative string
    base_dir = desktop
    clean_name = raw
    import re
    if " on desktop" in lowered or " in desktop" in lowered:
        clean_name = re.sub(r"\s+(?:on|in)\s+desktop", "", raw, flags=re.IGNORECASE).strip()
        base_dir = desktop
    elif " in downloads" in lowered or " to downloads" in lowered or " on downloads" in lowered:
        clean_name = re.sub(r"\s+(?:in|to|on)\s+downloads", "", raw, flags=re.IGNORECASE).strip()
        base_dir = downloads
    elif " in documents" in lowered or " to documents" in lowered:
        clean_name = re.sub(r"\s+(?:in|to)\s+documents", "", raw, flags=re.IGNORECASE).strip()
        base_dir = documents

    if clean_name.lower() in ("desktop", "downloads", "documents"):
        return base_dir
    return (base_dir / clean_name).resolve(strict=False)

def is_protected_path(
    path: str | Path,
    protected_roots: list[str] | None = None,
    deny_other_users: bool = True,
    protect_jarvis_internals: bool = True,
) -> tuple[bool, str]:
    """Evaluates whether a target path falls under protected system, user, or Jarvis roots.
    Returns (is_protected, reason).
    """
    canonical = canonicalize_path(path)
    canonical_str = str(canonical).lower()

    # 1. Check configured protected system roots
    roots = protected_roots if protected_roots is not None else DEFAULT_PROTECTED_ROOTS
    for root in roots:
        c_root = str(canonicalize_path(root)).lower()
        if canonical_str == c_root or canonical_str.startswith(c_root + os.sep) or canonical_str.startswith(c_root + "/"):
            return True, f"Target path falls inside protected system root: {root}"

    # 2. Check other user profiles
    if deny_other_users and sys.platform == "win32":
        users_dir = Path("C:\\Users").resolve()
        current_user_profile = Path.home().resolve()
        current_user_str = str(current_user_profile).lower()
        users_dir_str = str(users_dir).lower()

        if canonical_str.startswith(users_dir_str):
            # Check if it starts with current user's profile
            if not (canonical_str == current_user_str or canonical_str.startswith(current_user_str + os.sep)):
                # If path is inside C:\Users\Public or C:\Users\Default or other users
                rel_parts = canonical.relative_to(users_dir).parts
                if rel_parts:
                    target_user = rel_parts[0].lower()
                    current_username = os.environ.get("USERNAME", "").lower()
                    if target_user != current_username and target_user != "public":
                        return True, f"Target path falls inside another user's profile: {rel_parts[0]}"

    # 3. Check Jarvis self-protection
    if protect_jarvis_internals:
        for jp in get_jarvis_protected_paths():
            c_jp = str(canonicalize_path(jp)).lower()
            if canonical_str == c_jp or canonical_str.startswith(c_jp + os.sep):
                return True, f"Target path points to protected internal Jarvis asset: {jp}"

    return False, ""

def toctou_snapshot(path: str | Path) -> dict[str, Any] | None:
    """Takes a lightweight snapshot of file metadata immediately prior to execution."""
    canonical = canonicalize_path(path)
    if not canonical.exists():
        return None
    try:
        st = canonical.stat()
        return {
            "path": str(canonical),
            "exists": True,
            "size": st.st_size,
            "mtime_ns": st.st_mtime_ns,
            "is_file": canonical.is_file(),
            "is_dir": canonical.is_dir(),
        }
    except Exception:
        return None

def verify_toctou(path: str | Path, snapshot: dict[str, Any] | None) -> tuple[bool, str]:
    """Verifies that the target file has not been replaced or modified between check and execution."""
    current = toctou_snapshot(path)
    if snapshot is None:
        if current is not None:
            return False, "Target unexpectedly created after pre-check"
        return True, ""

    if current is None:
        return False, "Target was removed or disappeared before execution"

    if current["size"] != snapshot["size"] or current["mtime_ns"] != snapshot["mtime_ns"]:
        return False, f"Target file identity changed (size: {snapshot['size']} -> {current['size']})"

    return True, ""

def check_overwrite_safety(destination: str | Path, allow_overwrite: bool = False) -> tuple[bool, str]:
    """Prevents silent file overwriting without explicit authorization."""
    canonical = canonicalize_path(destination)
    if canonical.exists():
        if not allow_overwrite:
            return False, f"Destination '{canonical}' already exists; silent overwrite is forbidden"
    return True, ""
