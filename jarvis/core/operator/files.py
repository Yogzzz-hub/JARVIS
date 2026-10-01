"""file.* primitives for things the catalog search doesn't do on its own: filter by size / sort by size or age,
reveal in Explorer, open the containing folder, copy a path, duplicate safely, open with a chosen app, open the
newest download, re-find a moved file, verify a move/delete, restore from the Recycle Bin.

A file is named by a resolved resource ("this" / "that" / "the download" from resource memory or working memory) or
by an explicit path; nothing here guesses a file from a pronoun with nothing behind it. Explorer and app launches use
fixed argv lists, never a shell string.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from jarvis.core.operator.refs import DownloadResource, OperatorOutcome
from jarvis.core.operator.resources import OperatorResources, get_resources

_SIZE_UNITS = {"b": 1, "byte": 1, "bytes": 1, "kb": 1024, "k": 1024, "mb": 1024 ** 2, "m": 1024 ** 2, "megabyte": 1024 ** 2,
               "megabytes": 1024 ** 2, "gb": 1024 ** 3, "g": 1024 ** 3, "gigabyte": 1024 ** 3, "gigabytes": 1024 ** 3}
TYPE_EXT = {"pdf": (".pdf",), "pdfs": (".pdf",), "image": (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".heic"),
            "images": (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".heic"), "picture": (".png", ".jpg", ".jpeg"),
            "pictures": (".png", ".jpg", ".jpeg"), "photo": (".jpg", ".jpeg", ".png", ".heic"), "photos": (".jpg", ".jpeg", ".png", ".heic"),
            "video": (".mp4", ".mkv", ".mov", ".avi", ".webm"), "videos": (".mp4", ".mkv", ".mov", ".avi", ".webm"),
            "document": (".docx", ".doc", ".pdf", ".txt", ".odt"), "documents": (".docx", ".doc", ".pdf", ".txt", ".odt"),
            "spreadsheet": (".xlsx", ".xls", ".csv"), "presentation": (".pptx", ".ppt"), "zip": (".zip", ".rar", ".7z"),
            "text": (".txt", ".md"), "code": (".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs")}
EDITORS = {".txt": "notepad", ".md": "notepad", ".py": "code", ".js": "code", ".json": "code", ".csv": "excel",
           ".xlsx": "excel", ".docx": "winword", ".doc": "winword", ".pptx": "powerpnt", ".png": "mspaint", ".jpg": "mspaint"}


def parse_size(text: str) -> Optional[int]:
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([a-z]+)?\s*", (text or "").lower())
    if not m:
        return None
    return int(float(m.group(1)) * _SIZE_UNITS.get(m.group(2) or "mb", 1024 ** 2))


def ref_path(ref) -> str:
    return getattr(ref, "path", "") or getattr(ref, "canonical_path", "") or getattr(ref, "canonical_identifier", "") or ""


def downloads_dir() -> Path:
    try:
        from jarvis.tools.system.window_management_tools import get_known_folder_path
        return Path(get_known_folder_path("downloads"))
    except Exception:
        return Path.home() / "Downloads"


class FileOperator:
    def __init__(self, resources: Optional[OperatorResources] = None, runner=None):
        self._res = resources
        self._run = runner or (lambda argv: subprocess.Popen(argv, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)))

    @property
    def resources(self) -> OperatorResources:
        return self._res or get_resources()

    # -- resolving "this file" ---------------------------------------------------------------------------------
    def resolve(self, ref: str = "") -> tuple[Optional[Path], str]:
        r = (ref or "").strip().strip("'\"")
        if r and (os.path.sep in r or "/" in r or re.search(r"\.\w{2,5}$", r)) and Path(r).expanduser().exists():
            return Path(r).expanduser(), ""
        for rtype in ("FILE", "DOWNLOAD", "SCREENSHOT"):
            hit = self.resources.latest(rtype)
            if hit is not None and ref_path(hit) and (not r or rtype.lower() in r.lower()
                                                                   or re.fullmatch(r"(?:this|that|it|the)?\s*(?:file|folder|one|download|pdf|screenshot)?", r.lower())):
                return Path(ref_path(hit)), ""
        wm = getattr(self.resources, "_wm", None)
        try:
            cur = wm.get_current_file() if wm is not None else None
        except Exception:
            cur = None
        if cur:
            return Path(cur), ""
        return None, "Which file do you mean? Find it first (\"find my report\") or tell me its name."

    # -- primitives ---------------------------------------------------------------------------------------------
    def search(self, folder: str = "", types: tuple[str, ...] = (), min_size: int = 0, max_size: int = 0,
               sort: str = "newest", limit: int = 10, name_part: str = "") -> OperatorOutcome:
        root = Path(folder).expanduser() if folder else Path.home()
        if not root.exists():
            return OperatorOutcome(False, f"{root} doesn't exist.")
        items = []
        deadline = time.monotonic() + 4.0
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith((".", "$")) and d not in ("node_modules", "AppData", "__pycache__")]
            for f in filenames:
                p = Path(dirpath) / f
                if types and p.suffix.lower() not in types:
                    continue
                if name_part and name_part.lower() not in f.lower():
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                if min_size and st.st_size < min_size or max_size and st.st_size > max_size:
                    continue
                items.append((p, st.st_size, st.st_mtime))
            if time.monotonic() > deadline or len(items) > 20000:
                break
        key = {"largest": lambda x: -x[1], "smallest": lambda x: x[1], "oldest": lambda x: x[2]}.get(sort, lambda x: -x[2])
        items.sort(key=key)
        top = items[:limit]
        if not top:
            return OperatorOutcome(False, "No files match.", evidence={"folder": str(root)})
        from jarvis.core.context.models import FileResourceRef
        refs = []
        for i, (p, size, mtime) in enumerate(top):
            refs.append(FileResourceRef(resource_id=f"file:{p}", canonical_path=str(p), size_bytes=size, result_rank=i + 1))
        for ref in reversed(refs):
            self.resources.record(ref)
        lines = [f"{i + 1}. {p.name} ({size / 1024 ** 2:.1f} MB, {time.strftime('%d %b %Y', time.localtime(m))})"
                 for i, (p, size, m) in enumerate(top)]
        return OperatorOutcome(True, "\n".join(lines), resource=refs[0], candidates=refs, evidence={"count": len(items)})

    def reveal(self, ref: str = "") -> OperatorOutcome:
        p, q = self.resolve(ref)
        if p is None:
            return OperatorOutcome(False, q, needs="clarify")
        if not p.exists():
            return OperatorOutcome(False, f"{p.name} isn't at {p.parent} any more - say 'find it again'.", needs="clarify")
        if os.name == "nt":
            self._run(["explorer.exe", f"/select,{p}"])
        return OperatorOutcome(True, f"Showing {p.name} in {p.parent}.", evidence={"path": str(p)})

    def open_folder(self, ref: str = "") -> OperatorOutcome:
        p, q = self.resolve(ref)
        if p is None:
            return OperatorOutcome(False, q, needs="clarify")
        folder = p if p.is_dir() else p.parent
        if not folder.exists():
            return OperatorOutcome(False, f"{folder} no longer exists.")
        if os.name == "nt":
            self._run(["explorer.exe", str(folder)])
        return OperatorOutcome(True, f"Opened {folder}.", evidence={"path": str(folder)})

    def copy_path(self, ref: str = "", folder: bool = False, desktop=None) -> OperatorOutcome:
        p, q = self.resolve(ref)
        if p is None:
            return OperatorOutcome(False, q, needs="clarify")
        target = str(p.parent if folder and not p.is_dir() else p)
        from jarvis.core.operator.platform import get_desktop
        d = desktop or get_desktop()
        ok = d.set_clipboard_text(target) and d.clipboard_text() == target
        return OperatorOutcome(ok, f"Copied {target}" if ok else "I couldn't copy the path.", evidence={"path": target})

    def duplicate(self, ref: str = "") -> OperatorOutcome:
        p, q = self.resolve(ref)
        if p is None:
            return OperatorOutcome(False, q, needs="clarify")
        if not p.is_file():
            return OperatorOutcome(False, f"{p.name} isn't a file I can copy.")
        n, dst = 1, p.with_name(f"{p.stem} - copy{p.suffix}")
        while dst.exists():
            n += 1
            dst = p.with_name(f"{p.stem} - copy ({n}){p.suffix}")
        shutil.copy2(p, dst)
        ok = dst.exists() and dst.stat().st_size == p.stat().st_size
        if ok:
            self.resources.record(DownloadResource(resource_id=f"file:{dst}", path=str(dst), filename=dst.name))
        return OperatorOutcome(ok, f"Made a copy: {dst.name}." if ok else "The copy didn't complete.", evidence={"path": str(dst)})

    def open_with(self, ref: str = "", app: str = "", launcher=None) -> OperatorOutcome:
        p, q = self.resolve(ref)
        if p is None:
            return OperatorOutcome(False, q, needs="clarify")
        exe = (app or "").lower().strip() or EDITORS.get(p.suffix.lower(), "")
        exe = {"edge": "msedge", "chrome": "chrome", "vs code": "code", "vscode": "code", "notepad": "notepad",
               "word": "winword", "excel": "excel", "paint": "mspaint", "an editor": EDITORS.get(p.suffix.lower(), "notepad"),
               "editor": EDITORS.get(p.suffix.lower(), "notepad")}.get(exe, exe)
        if not exe:
            return OperatorOutcome(False, f"Which app should open {p.name}?", needs="clarify")
        if not re.fullmatch(r"[a-z0-9_.+-]+", exe):
            return OperatorOutcome(False, f"'{app}' isn't an app name I can launch.", needs="clarify")
        if os.name == "nt":
            self._run(["cmd", "/c", "start", "", exe, str(p)])
        return OperatorOutcome(True, f"Opening {p.name} in {exe}.", evidence={"app": exe, "path": str(p), "verified": None})

    def newest(self, folder: str = "", types: tuple[str, ...] = ()) -> OperatorOutcome:
        root = Path(folder).expanduser() if folder else downloads_dir()
        if not root.exists():
            return OperatorOutcome(False, f"{root} doesn't exist.")
        partial = {".crdownload", ".part", ".tmp", ".download"}
        files = [p for p in root.iterdir() if p.is_file() and p.suffix.lower() not in partial
                 and (not types or p.suffix.lower() in types)]
        if not files:
            return OperatorOutcome(False, f"There's nothing in {root.name}.")
        p = max(files, key=lambda x: x.stat().st_mtime)
        ref = DownloadResource(resource_id=f"dl:{p}", path=str(p), filename=p.name)
        self.resources.record(ref)
        return OperatorOutcome(True, p.name, resource=ref, evidence={"path": str(p)})

    def open(self, p: Path) -> OperatorOutcome:
        if not p.exists():
            return OperatorOutcome(False, f"{p.name} no longer exists.")
        if os.name == "nt":
            os.startfile(str(p))  # type: ignore[attr-defined]
        return OperatorOutcome(True, f"Opened {p.name}.", evidence={"path": str(p)})

    def relocate(self, ref: str = "", search_root: str = "") -> OperatorOutcome:
        """A stale reference: same name (and same content hash when we have it) somewhere else."""
        p, q = self.resolve(ref)
        if p is None:
            return OperatorOutcome(False, q, needs="clarify")
        if p.exists():
            return OperatorOutcome(True, f"{p.name} is still at {p.parent}.", evidence={"path": str(p)})
        found = self.search(search_root or str(Path.home()), name_part=p.name, limit=5)
        exact = [c for c in found.candidates if Path(ref_path(c)).name == p.name]
        if not exact:
            return OperatorOutcome(False, f"I can't find {p.name} anywhere in your folders - it may have been renamed or deleted.")
        if len(exact) > 1:
            return OperatorOutcome(False, "It's in more than one place: " + "; ".join(ref_path(c) for c in exact[:4]),
                                   needs="clarify", candidates=exact)
        self.resources.record(exact[0])
        return OperatorOutcome(True, f"{p.name} moved to {Path(ref_path(exact[0])).parent}.", resource=exact[0])

    def verify(self, ref: str = "", expect: str = "moved", destination: str = "") -> OperatorOutcome:
        p, q = self.resolve(ref)
        if p is None:
            return OperatorOutcome(False, q, needs="clarify")
        if expect == "deleted":
            ok = not p.exists()
            return OperatorOutcome(ok, f"Confirmed: {p.name} is gone." if ok else f"{p.name} is still at {p.parent}.",
                                   evidence={"exists": p.exists()})
        if destination:
            dst = Path(destination).expanduser() / p.name
            ok = dst.exists() and not (p.exists() and p.resolve() != dst.resolve())
            return OperatorOutcome(ok, f"Confirmed: {p.name} is in {dst.parent}." if ok else
                                   f"{p.name} isn't in {dst.parent}.", evidence={"destination": str(dst)})
        ok = p.exists()
        return OperatorOutcome(ok, f"{p.name} is at {p.parent}." if ok else f"{p.name} isn't where I last saw it.",
                               evidence={"path": str(p)})

    def checksum(self, path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    def restore_from_recycle_bin(self, name: str) -> OperatorOutcome:
        """Only an item whose original name matches exactly once; the Shell's own 'Restore' verb, nothing else."""
        if os.name != "nt":
            return OperatorOutcome(False, "The Recycle Bin is only on Windows.")
        try:
            import win32com.client
            shell = win32com.client.Dispatch("Shell.Application")
            bin_ = shell.Namespace(10)
            items = [it for it in bin_.Items() if name.lower() in (it.Name or "").lower()]
        except Exception as e:
            return OperatorOutcome(False, f"I can't read the Recycle Bin ({e}).")
        if not items:
            return OperatorOutcome(False, f"'{name}' isn't in the Recycle Bin.")
        if len(items) > 1:
            return OperatorOutcome(False, "More than one match: " + "; ".join(it.Name for it in items[:5]), needs="clarify")
        verbs = [v for v in items[0].Verbs() if re.sub(r"&", "", v.Name or "").lower().startswith(("restore", "undelete"))]
        if not verbs:
            return OperatorOutcome(False, "Windows doesn't offer Restore for that item.")
        verbs[0].DoIt()
        return OperatorOutcome(True, f"Restored {items[0].Name} to where it was.", evidence={"verified": None})
