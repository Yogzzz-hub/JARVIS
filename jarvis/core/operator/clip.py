"""clip.* primitives: read the clipboard as a typed resource, copy the selection (waiting for the clipboard to
actually change - no fixed sleep), put text/image/files on it, and save/restore what the owner had there."""
from __future__ import annotations

from typing import Optional

from jarvis.core.operator.platform import Desktop, get_desktop, parse_chord
from jarvis.core.operator.refs import ClipboardResource, OperatorOutcome
from jarvis.core.operator.resources import OperatorResources, get_resources


class ClipOperator:
    def __init__(self, desktop: Optional[Desktop] = None, resources: Optional[OperatorResources] = None):
        self._desktop = desktop
        self._res = resources
        self._saved: Optional[ClipboardResource] = None

    @property
    def desktop(self) -> Desktop:
        return self._desktop or get_desktop()

    @property
    def resources(self) -> OperatorResources:
        return self._res or get_resources()

    def get(self) -> OperatorOutcome:
        d = self.desktop
        files = d.clipboard_files()
        if files:
            ref = ClipboardResource(resource_id="clip:files", kind="files", files=files)
        elif d.clipboard_has_image():
            ref = ClipboardResource(resource_id="clip:image", kind="image")
        else:
            text = d.clipboard_text()
            if text is None or text == "":
                return OperatorOutcome(False, "The clipboard is empty.")
            ref = ClipboardResource(resource_id="clip:text", kind="text", text=text)
        self.resources.record(ref)
        # Clipboard text is data the owner copied from somewhere: shown/used, never obeyed.
        return OperatorOutcome(True, ref.display_name, resource=ref, evidence={"kind": ref.kind, "untrusted": True})

    def copy_selection(self) -> OperatorOutcome:
        d = self.desktop
        marker = "⁣jarvis-copy-probe⁣"
        before = d.clipboard_text()
        d.set_clipboard_text(marker)                 # so an unchanged clipboard is detectable
        d.press(parse_chord("ctrl+c"))
        changed = d.wait_until(lambda: d.clipboard_text() != marker or d.clipboard_has_image() or bool(d.clipboard_files()),
                               timeout=1.0)
        if not changed:
            if before is not None:
                d.set_clipboard_text(before)
            return OperatorOutcome(False, "Nothing was selected to copy.", needs="clarify")
        return self.get()

    def set_text(self, text: str) -> OperatorOutcome:
        ok = self.desktop.set_clipboard_text(text) and self.desktop.clipboard_text() == text
        ref = ClipboardResource(resource_id="clip:text", kind="text", text=text)
        if ok:
            self.resources.record(ref)
            get_clipboard_history().note(text)
        return OperatorOutcome(ok, "Copied to the clipboard." if ok else "I couldn't set the clipboard.", resource=ref)

    def set_image(self, path: str) -> OperatorOutcome:
        ok = self.desktop.set_clipboard_image(path) and self.desktop.clipboard_has_image()
        return OperatorOutcome(ok, "Image copied to the clipboard." if ok else "I couldn't copy that image.",
                               evidence={"path": path})

    def save(self) -> None:
        d = self.desktop
        text = d.clipboard_text()
        self._saved = ClipboardResource(resource_id="clip:saved", kind="text", text=text) if text is not None else None

    def restore(self) -> OperatorOutcome:
        if not self._saved:
            return OperatorOutcome(False, "There's no earlier clipboard to put back.")
        ok = self.desktop.set_clipboard_text(self._saved.text)
        return OperatorOutcome(ok, "Your clipboard is back." if ok else "I couldn't restore the clipboard.")


class ClipboardHistory:
    """The last few text items the owner copied, newest first - in memory only (never written to disk: clipboards hold
    passwords and one-time codes). Fed by a light poller in the runtime and by JARVIS's own clipboard writes."""

    def __init__(self, size: int = 25, desktop: Optional[Desktop] = None):
        import threading
        self.size = size
        self._items: list[str] = []
        self._lock = threading.Lock()
        self._desktop = desktop
        self._thread = None

    @property
    def desktop(self) -> Desktop:
        return self._desktop or get_desktop()

    def note(self, text: Optional[str]) -> None:
        t = (text or "").strip("\x00")
        if not t.strip() or len(t) > 20000 or "jarvis-copy-probe" in t:
            return
        with self._lock:
            if self._items and self._items[0] == t:
                return
            self._items = [t] + [i for i in self._items if i != t][: self.size - 1]

    def items(self) -> list[str]:
        with self._lock:
            return list(self._items)

    def clear(self) -> int:
        with self._lock:
            n = len(self._items)
            self._items = []
        return n

    def poll_once(self) -> None:
        try:
            self.note(self.desktop.clipboard_text())
        except Exception:
            pass

    def start(self, interval: float = 0.8) -> None:
        import os
        import threading
        import time
        if self._thread is not None or os.environ.get("PYTEST_CURRENT_TEST"):
            return

        def loop():
            while True:
                self.poll_once()
                time.sleep(interval)

        self._thread = threading.Thread(target=loop, name="clipboard-history", daemon=True)
        self._thread.start()

    # -- operations ------------------------------------------------------------------------------------------
    def show(self, n: int = 10) -> OperatorOutcome:
        items = self.items()[:n]
        if not items:
            return OperatorOutcome(True, "Nothing copied yet this session.")
        lines = [f"{i}. {(' '.join(t.split()))[:70]}" for i, t in enumerate(items, 1)]
        return OperatorOutcome(True, "\n".join(lines), evidence={"count": len(items), "untrusted": True})

    def recall(self, n: int, paste: bool = True, expect=None) -> OperatorOutcome:
        """Put the n-th most recent item (1 = latest) back on the clipboard and, if asked, paste it where the owner is."""
        items = self.items()
        if not 1 <= n <= len(items):
            return OperatorOutcome(False, f"I only have {len(items)} item{'s' if len(items) != 1 else ''} in the clipboard "
                                          "history." if items else "Nothing copied yet this session.", needs="clarify")
        text = items[n - 1]
        d = self.desktop
        if not (d.set_clipboard_text(text) and d.clipboard_text() == text):
            return OperatorOutcome(False, "I couldn't put it back on the clipboard.")
        if not paste:
            return OperatorOutcome(True, f"Copied item {n} again: {' '.join(text.split())[:60]}", evidence={"verified": True})
        from jarvis.core.operator.text import TextOperator
        before = d.focused_text()
        out = TextOperator(d).press("paste", expect=expect)
        if not out.ok:
            return out
        after = d.focused_text()
        verified = None if before is None or after is None else (text in after and after != before)
        return OperatorOutcome(True, f"Pasted item {n}: {' '.join(text.split())[:60]}", evidence={"verified": verified})


_history: Optional[ClipboardHistory] = None


def get_clipboard_history() -> ClipboardHistory:
    global _history
    if _history is None:
        _history = ClipboardHistory()
    return _history
