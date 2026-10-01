"""screen.* primitives: capture the screen / the active window / a named window as a ScreenshotResource (recorded,
so "send that screenshot", "paste it in Antigravity" resolve), optionally onto the clipboard; read a window's text
structured-first (UI Automation names and values) - vision OCR only when the structure is empty."""
from __future__ import annotations

import hashlib
import time
import uuid
from pathlib import Path
from typing import Optional

from jarvis.core.operator.platform import Desktop, get_desktop
from jarvis.core.operator.refs import OperatorOutcome, ScreenshotResourceRef, WindowRef
from jarvis.core.operator.resources import OperatorResources, get_resources


def _default_dir() -> Path:
    from jarvis.config import ROOT
    return ROOT / "screenshots"


class ScreenOperator:
    def __init__(self, desktop: Optional[Desktop] = None, resources: Optional[OperatorResources] = None,
                 folder: Optional[Path] = None):
        self._desktop = desktop
        self._res = resources
        self._folder = folder

    @property
    def desktop(self) -> Desktop:
        return self._desktop or get_desktop()

    @property
    def resources(self) -> OperatorResources:
        return self._res or get_resources()

    def capture(self, window: Optional[WindowRef] = None, to_clipboard: bool = False,
                path: str = "") -> OperatorOutcome:
        folder = self._folder or _default_dir()
        out = Path(path) if path else folder / f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}.png"
        try:
            w, h = self.desktop.capture(str(out), hwnd=window.hwnd if window else 0)
        except Exception as e:
            return OperatorOutcome(False, f"I couldn't take the screenshot ({e}).")
        if not out.exists() or out.stat().st_size == 0:
            return OperatorOutcome(False, "The screenshot file wasn't written.")
        digest = hashlib.sha1(out.read_bytes()).hexdigest()[:16]
        ref = ScreenshotResourceRef(resource_id=f"shot:{digest}", path=str(out),
                                    source_window=window.title if window else "screen",
                                    source_app=window.process if window else "", width=w, height=h,
                                    file_hash=digest, capture_time=time.time())
        self.resources.record(ref)
        msg = f"Screenshot of {window.display_name if window else 'the screen'} saved."
        if to_clipboard:
            if self.desktop.set_clipboard_image(str(out)) and self.desktop.clipboard_has_image():
                msg += " It's on the clipboard."
            else:
                msg += " (I couldn't put it on the clipboard.)"
        return OperatorOutcome(True, msg, resource=ref, evidence={"path": str(out), "size": [w, h]})

    def read(self, window: Optional[WindowRef] = None, adapter=None) -> OperatorOutcome:
        """Visible text of a window, from its accessibility tree. Untrusted data: displayed, never obeyed."""
        if adapter is None and window is not None:
            from jarvis.core.operator.ui import UIAWindowAdapter
            adapter = UIAWindowAdapter(window.hwnd)
        if adapter is None:
            return OperatorOutcome(False, "Which window should I read?", needs="clarify")
        try:
            controls = adapter.snapshot()
        except Exception:
            controls = []
        lines: list[str] = []
        for c in controls:
            for piece in (c.name, (c.metadata or {}).get("value", "")):
                piece = (piece or "").strip()
                if piece and piece not in lines:
                    lines.append(piece)
        if not lines:
            return OperatorOutcome(False, "That window doesn't expose its text.", needs="vision")
        return OperatorOutcome(True, "\n".join(lines), evidence={"untrusted": True, "lines": len(lines)})
