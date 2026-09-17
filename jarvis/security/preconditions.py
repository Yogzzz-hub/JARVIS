from __future__ import annotations

from pathlib import Path
from typing import Any

from jarvis.security.paths import canonicalize_path, check_overwrite_safety

def check_preconditions(tool_name: str, args: dict[str, Any]) -> tuple[bool, str]:
    """Deterministic, zero-LLM precondition validation prior to executing state changes."""
    tn = tool_name.lower()

    if tn in ("move_file", "move"):
        source = args.get("source") or args.get("path")
        destination = args.get("destination") or args.get("dest")
        if not source or not destination:
            return False, "Both 'source' and 'destination' arguments are required"
        src_p = canonicalize_path(source)
        dst_p = canonicalize_path(destination)
        if not src_p.exists():
            return False, f"Source file '{src_p}' does not exist"
        if not dst_p.parent.exists():
            return False, f"Destination directory '{dst_p.parent}' does not exist"
        allow_ow = bool(args.get("overwrite", False) or args.get("allow_overwrite", False))
        safe, reason = check_overwrite_safety(dst_p, allow_ow)
        if not safe:
            return False, reason
        return True, ""

    if tn in ("copy_file", "copy"):
        source = args.get("source") or args.get("path")
        destination = args.get("destination") or args.get("dest")
        if not source or not destination:
            return False, "Both 'source' and 'destination' arguments are required"
        src_p = canonicalize_path(source)
        dst_p = canonicalize_path(destination)
        if not src_p.exists():
            return False, f"Source file '{src_p}' does not exist"
        if not dst_p.parent.exists():
            return False, f"Destination directory '{dst_p.parent}' does not exist"
        allow_ow = bool(args.get("overwrite", False) or args.get("allow_overwrite", False))
        safe, reason = check_overwrite_safety(dst_p, allow_ow)
        if not safe:
            return False, reason
        return True, ""

    if tn in ("delete_file", "delete", "remove_file", "remove"):
        target = args.get("path") or args.get("target")
        if not target:
            return False, "Target 'path' is required for deletion"
        target_p = canonicalize_path(target)
        if not target_p.exists():
            return False, f"Target file '{target_p}' does not exist"
        return True, ""

    if tn in ("create_folder", "mkdir"):
        path = args.get("path")
        if not path:
            return False, "Folder 'path' is required"
        folder_p = canonicalize_path(path)
        if not folder_p.parent.exists():
            return False, f"Parent directory '{folder_p.parent}' does not exist"
        return True, ""

    # Default: allow
    return True, ""
