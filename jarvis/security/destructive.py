"""Destructive scope guard: before a delete / move / rename is even offered for confirmation, its target is resolved and
validated. Confirmation never makes a wrong interpretation valid.

Order (Blind-11, "delete temp_test.txt from my desktop" proposed deleting the Desktop folder):
1. resolve the exact existing target (typed: a file inside its parent, not the parent);
2. validate its type and scope - a user root, the home folder or a drive is never a destructive target;
3. count what would be affected (a folder's contents);
4. only then policy and confirmation, bound to the exact resolved path.
A target that cannot be found, or matches several things, stops here with a question - nothing is proposed.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

DESTRUCTIVE_FILE_TOOLS = {"delete_file": "path", "move_file": "source", "rename_file": "source", "batch_rename": "directory"}


@dataclass
class TargetCheck:
    status: str                       # READY / NOT_FOUND / AMBIGUOUS / BLOCKED_BY_POLICY
    args: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    affected: int = 0


def _finder(name: str) -> Optional[Path]:
    try:
        from jarvis.tools.system import file_tools
        return file_tools._find_existing_item(name)
    except Exception:
        return None


def check_destructive_target(tool: str, args: dict[str, Any]) -> Optional[TargetCheck]:
    """None for tools this guard does not cover; else the verdict with arguments bound to the resolved target."""
    key = DESTRUCTIVE_FILE_TOOLS.get(tool)
    if not key:
        return None
    from jarvis.core.semantics.resources import ROOT, is_root, parse_path_ref, resolve_target
    raw = str(args.get(key) or args.get("path") or args.get("target") or "").strip()
    if not raw:
        return TargetCheck("NOT_FOUND", args, "Which file or folder exactly? Tell me its name.")
    ref = parse_path_ref(raw)
    p0 = Path(os.path.expanduser(raw))
    if p0.is_absolute() and not p0.exists():
        # an absolute path that does not exist: its last part is the name, its folder (if a known one) the parent
        from jarvis.core.semantics.resources import PathRef, _known, _item
        parent = _known(p0.parent.name)
        ref = _item(p0.name, parent, raw) if parent else _item(p0.name, None, raw)
    if ref.kind == ROOT:
        return TargetCheck("BLOCKED_BY_POLICY", args, f"I won't {tool.split('_')[0]} your whole {ref.name} - tell me the file or "
                                                      "folder inside it.")
    found: Optional[Path] = None
    p = Path(os.path.expanduser(raw))
    if p.is_absolute() and p.exists():
        found = p
    if found is None:
        found = _finder(raw)
    if found is None:
        res = resolve_target(ref, exclude=list(args.get("exclude") or []), prefer=args.get("context_folder"))
        if res.status == "ambiguous":
            names = ", ".join(c.name for c in res.candidates[:4])
            return TargetCheck("AMBIGUOUS", args, f"I found more than one match ({names}). Which one?")
        if res.status != "found":
            return TargetCheck("NOT_FOUND", args, f"I couldn't find '{ref.name}'"
                                                  + (f" in {ref.parent}" if ref.parent else "") + " - check the name?")
        found = res.path
    if is_root(found):
        return TargetCheck("BLOCKED_BY_POLICY", args, f"I won't {tool.split('_')[0]} your whole {found.name} folder - tell me what's "
                                                      "inside it that you mean.")
    affected = 1
    if found.is_dir():
        affected = sum(len(fs) for _, _, fs in os.walk(found))
    bound = {**args, key: str(found)}
    return TargetCheck("READY", bound, "", affected)
