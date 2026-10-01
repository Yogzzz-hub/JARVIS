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
