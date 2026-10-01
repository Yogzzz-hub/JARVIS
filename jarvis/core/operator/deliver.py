"""deliver: put a resource (screenshot, file, download, copied text, answer) somewhere - a window, a control in it,
a web upload field, the phone - as a paste, an attachment or an upload, and verify it arrived.

Delivery never *sends*: pressing Send/Enter in a chat or an IDE prompt is a separate, explicit step that needs the
owner's go-ahead (``approved``), and success is only reported when the effect was observed. When the effect can't
be observed from outside the app, the outcome says so instead of claiming success.
"""
from __future__ import annotations

import os
import re
from typing import Optional

from jarvis.core.context.models import BaseResourceRef
from jarvis.core.operator.platform import Desktop, get_desktop, parse_chord
from jarvis.core.operator.refs import ControlRef, OperatorOutcome, WindowRef
from jarvis.core.operator.ui import UIAdapter, UIOperator, UITarget

_ATTACHMENT_HINT = re.compile(r"\b(attach(ment|ed)?|image|screenshot|remove|\.png|\.jpg|\.jpeg|\.pdf|file|preview)\b", re.I)


def payload_of(resource: BaseResourceRef) -> tuple[str, str]:
    """(kind, value): kind is 'image' | 'files' | 'text'."""
    rtype = resource.resource_type
    if rtype == "SCREENSHOT":
        return "image", getattr(resource, "path", "")
    if rtype in ("FILE", "DOWNLOAD"):
        return "files", getattr(resource, "path", "") or resource.canonical_identifier
    if rtype == "CLIPBOARD":
        kind = getattr(resource, "kind", "text")
        if kind == "files":
            return "files", ";".join(getattr(resource, "files", []))
        if kind == "image" and not getattr(resource, "image_path", ""):
            return "clipboard", "image"                     # already on the clipboard: paste as it is
        return kind, getattr(resource, "text", "") if kind == "text" else getattr(resource, "image_path", "")
    if rtype in ("BROWSER_TAB", "LINK", "MEDIA"):
        return "text", getattr(resource, "url", "") or resource.canonical_identifier
    return "text", getattr(resource, "text", "") or getattr(resource, "content", "") or resource.display_name


class DeliverOperator:
    def __init__(self, desktop: Optional[Desktop] = None, tracker=None):
        self._desktop = desktop
        self._tracker = tracker
        self.ui = UIOperator()

    @property
    def desktop(self) -> Desktop:
        return self._desktop or get_desktop()

    @property
    def tracker(self):
        if self._tracker is None:
            from jarvis.core.operator.windows import get_window_tracker
            self._tracker = get_window_tracker()
        return self._tracker

    def to_window(self, resource: BaseResourceRef, window: WindowRef, adapter: Optional[UIAdapter] = None,
                  field: str = "", send: bool = False, approved: bool = False) -> OperatorOutcome:
        kind, value = payload_of(resource)
        if not value:
            return OperatorOutcome(False, f"{resource.display_name or 'That'} has nothing to deliver.")
        if kind in ("image", "files"):
            missing = [p for p in value.split(";") if p and not os.path.exists(p)]
            if missing:
                return OperatorOutcome(False, f"{os.path.basename(missing[0])} no longer exists.", resource=resource)
        if send and not approved:
            return OperatorOutcome(False, f"Ready to send {resource.display_name} in {window.display_name}. "
                                          "Say yes to send.", resource=resource, needs="approve")
        focused = self.tracker.focus(window)
        if not focused.ok:
            return focused
        d = self.desktop
        # Put the payload on the clipboard (the transport every app understands)
        if kind == "clipboard":
            ok = d.clipboard_has_image()
        elif kind == "image":
            ok = d.set_clipboard_image(value) and d.clipboard_has_image()
        elif kind == "files":
            ok = d.set_clipboard_files(value.split(";"))
        else:
            ok = d.set_clipboard_text(value)
        if not ok:
            return OperatorOutcome(False, "I couldn't put it on the clipboard.", resource=resource)
        target_ctrl: Optional[ControlRef] = None
        before_controls: list[ControlRef] = []
        if adapter is not None:
            before_controls = adapter.snapshot()
            want = UITarget.parse(field) if field else UITarget(role="textbox", editable=True)
            found = self.ui.resolver.resolve(before_controls, want)
            if not found.ok:
                return found
            target_ctrl = found.resource
            adapter.focus(target_ctrl)
        # The paste goes to the window we just verified is in front - checked again right before the keys.
        fg = d.foreground()
        if not fg or fg.hwnd != window.hwnd:
            return OperatorOutcome(False, f"{window.display_name} lost focus before I could paste.", needs="target_lost")
        text_before = d.focused_text()
        d.press(parse_chord("ctrl+v"))
        verified = self._verify(kind, value, text_before, adapter, before_controls, target_ctrl)
        what = {"image": "the screenshot", "files": os.path.basename(value.split(";")[0]), "text": "the text",
                "clipboard": "the image"}[kind]
        where = window.display_name
        sent: Optional[bool] = None
        if send and verified is not False:
            d.press(parse_chord("enter"))
            if adapter is not None and target_ctrl is not None:
                # A sent message leaves the composer empty; anything else is not a confirmed send.
                sent = d.wait_until(lambda: not (adapter.read(target_ctrl) or "").strip(), timeout=2.0, interval=0.1)
            if sent is False:
                return OperatorOutcome(False, f"I pressed send in {window.display_name} but the message is still "
                                              "in the box - it may not have gone.", resource=resource,
                                       evidence={"verified": verified, "sent": False})
            if sent is None:
                verified = None
        if verified is False:
            return OperatorOutcome(False, f"I pasted {what} into {where} but it didn't show up.", resource=resource,
                                   evidence={"verified": False})
        msg = f"{'Sent' if send else 'Pasted'} {what} in {where}."
        if verified is None:
            msg += " (I can't see inside that app to confirm it.)"
        return OperatorOutcome(True, msg, resource=resource, evidence={"verified": verified, "kind": kind})

    def _verify(self, kind, value, text_before, adapter, before_controls, target_ctrl) -> Optional[bool]:
        d = self.desktop
        if kind == "text":
            after = d.focused_text()
            if after is not None and text_before is not None:
                return value in after and after != text_before
            if adapter is not None and target_ctrl is not None:
                got = adapter.read(target_ctrl)
                return value in (got or "")
            return None
        if adapter is not None:
            # An attachment chip/thumbnail appearing next to the prompt is the observable effect.
            def appeared() -> bool:
                after = adapter.snapshot()
                names_before = {(c.role, c.name) for c in before_controls}
                new = [c for c in after if (c.role, c.name) not in names_before]
                base = os.path.basename(value.split(";")[0]).lower()
                return any(_ATTACHMENT_HINT.search(c.name or "") or (base and base in (c.name or "").lower()) for c in new)
            return d.wait_until(appeared, timeout=2.0, interval=0.1)
        return None

    def to_phone(self, resource: BaseResourceRef, device=None) -> OperatorOutcome:
        kind, value = payload_of(resource)
        if kind not in ("image", "files"):
            return OperatorOutcome(False, "Only files and screenshots can go to the phone.", needs="clarify")
        from jarvis.core.operator.device import get_device_operator
        return get_device_operator().push(value.split(";")[0], device=device)
