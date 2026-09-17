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

def canonicalize_path(path_str: str | Path) -> Path:
    """Canonicalize a filesystem path:
    1. Expand environment variables (e.g. %WINDIR%, %USERPROFILE%)
    2. Expand ~ to user home
    3. Normalize slashes, eliminate redundant separators and traversal ('..')
    4. Resolve symlinks / junctions where the target exists
    """
    raw = str(path_str).strip()
    expanded = os.path.expanduser(os.path.expandvars(raw))
    p = Path(expanded)
    try:
        # Resolve resolves symlinks and normalizes '..'
        resolved = p.resolve(strict=False)
        return resolved
    except Exception:
        return Path(os.path.normpath(expanded))

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
