"""ui.* primitives: one target resolver over every surface (Windows UIA, a web page, an Android screen).

A target is described semantically - role, name, ordinal, "near X" - and resolved against a structured snapshot
the platform adapter produces. Scores decide; equal candidates are never guessed between (the owner is asked), a
sensitive field (password/OTP/PIN/CVV/CAPTCHA) is never filled, and a consequential button (pay, delete account,
submit order) needs the owner's approval. Coordinates never come from a model: an adapter acts on the control it
found by its own locator.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Optional

from jarvis.core.operator.refs import ControlRef, OperatorOutcome

# Canonical role -> words people use for it, and platform role names that mean it.
ROLE_WORDS: dict[str, tuple[str, ...]] = {
    "button": ("button", "btn", "icon", "key"),
    "textbox": ("box", "field", "input", "textbox", "text box", "search bar", "bar", "text area", "editor",
                "composer", "prompt"),
    "link": ("link", "hyperlink"),
    "checkbox": ("checkbox", "check box", "tick box", "toggle", "switch"),
    "radio": ("radio", "radio button", "option"),
    "tab": ("tab",),
    "menuitem": ("menu item", "menu option", "menu entry"),
    "listitem": ("item", "result", "entry", "row", "video", "message", "chat", "conversation", "file"),
    "combobox": ("dropdown", "drop down", "combo", "select", "picker"),
    "heading": ("heading", "title", "header"),
    "image": ("image", "picture", "photo", "thumbnail"),
    "slider": ("slider", "scrubber", "seek bar"),
}
PLATFORM_ROLES: dict[str, str] = {
    "buttoncontrol": "button", "splitbuttoncontrol": "button", "button": "button", "imagebutton": "button",
    "android.widget.button": "button", "android.widget.imagebutton": "button",
    "editcontrol": "textbox", "documentcontrol": "textbox", "textbox": "textbox", "searchbox": "textbox",
    "android.widget.edittext": "textbox", "textarea": "textbox", "combobox_editable": "textbox",
    "hyperlinkcontrol": "link", "link": "link",
    "checkboxcontrol": "checkbox", "checkbox": "checkbox", "switch": "checkbox", "android.widget.checkbox": "checkbox",
    "android.widget.switch": "checkbox", "togglebutton": "checkbox",
    "radiobuttoncontrol": "radio", "radio": "radio", "android.widget.radiobutton": "radio",
    "tabitemcontrol": "tab", "tab": "tab", "menuitemcontrol": "menuitem", "menuitem": "menuitem",
    "listitemcontrol": "listitem", "listitem": "listitem", "treeitemcontrol": "listitem", "dataitemcontrol": "listitem",
    "row": "listitem", "option": "listitem", "article": "listitem",
    "comboboxcontrol": "combobox", "combobox": "combobox", "android.widget.spinner": "combobox",
    "headercontrol": "heading", "heading": "heading", "imagecontrol": "image", "img": "image", "image": "image",
    "android.widget.imageview": "image",
    "slidercontrol": "slider", "slider": "slider", "range": "slider", "android.widget.seekbar": "slider",
    "windowcontrol": "dialog", "dialog": "dialog", "alertdialog": "dialog", "listcontrol": "listbox", "listbox": "listbox",
    "treecontrol": "listbox", "menubarcontrol": "menu", "menucontrol": "menu",
}
_ORDINAL = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
            "ninth": 9, "tenth": 10, "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5, "last": -1, "top": 1,
            "next": 0}
SENSITIVE = re.compile(r"\b(pass(word|code|phrase)?|pin|otp|one.?time|2fa|mfa|verification code|security code|cvv|"
                       r"cvc|card number|secret|captcha|recaptcha|i'?m not a robot)\b", re.I)
CONSEQUENTIAL = re.compile(r"\b(pay|purchase|buy now|place order|confirm (order|payment|purchase)|checkout|"
                           r"delete (account|everything|all)|close account|transfer|withdraw|uninstall|format|"
                           r"factory reset|wipe|sign out of all|deactivate)\b", re.I)


def canonical_role(platform_role: str) -> str:
    r = (platform_role or "").lower().replace(" ", "")
    return PLATFORM_ROLES.get(r, r.replace("control", ""))


@dataclass
class UITarget:
    name: str = ""
    role: str = ""
    ordinal: int = 0                 # 1-based; -1 = last; 0 = unspecified
    near: str = ""
    editable: Optional[bool] = None

    @classmethod
    def parse(cls, text: str) -> "UITarget":
        """'the second Send button', 'search box', 'the checkbox next to remember me', 'the 3rd result'."""
        t = re.sub(r"\s+", " ", (text or "").lower()).strip(" .?!")
        t = re.sub(r"^(on|at|in|into|the|a|an)\s+", "", t)
        near = ""
        m = re.search(r"\b(?:next to|near|beside|by|under|below|above|after|before)\s+(?:the\s+)?(.+)$", t)
        if m:
            near, t = m.group(1).strip(), t[: m.start()].strip()
        ordinal = 0
        m = re.search(r"\b(?:number|no\.?|#)\s*(\d+)\b", t) or re.search(r"\b(\d+)(?:st|nd|rd|th)\b", t)
        if m:
            ordinal, t = int(m.group(1)), (t[: m.start()] + t[m.end():]).strip()
        for word, n in _ORDINAL.items():
            if n and re.search(rf"\b{word}\b", t):
                ordinal, t = n, re.sub(rf"\b{word}\b", " ", t, count=1).strip()
                break
        t = re.sub(r"^(the|a|an)\s+", "", t.strip())
        role = ""
        best = ""
        for canon, words in ROLE_WORDS.items():
            for w in words:
                if re.search(rf"\b{re.escape(w)}s?$", t) and len(w) > len(best):
                    best, role = w, canon
        name = t
        if best:
            name = re.sub(rf"\b{re.escape(best)}s?$", "", t).strip()
            if canon_role_kept(best) and not name:
                name = best
        name = re.sub(r"^(?:called|named|labell?ed|titled|that says|saying)\s+", "", name).strip(" '\"")
        name = re.sub(r"\s+(?:called|named|labell?ed|titled|that says|saying)\s+", " ", name).strip(" '\"")
        return cls(name=name, role=role, ordinal=ordinal, near=near,
                   editable=True if role == "textbox" else None)


def canon_role_kept(word: str) -> bool:
    """'click the bar' has no name; words like 'video'/'message' are both role and name."""
    return word in ("video", "message", "chat", "file", "result", "prompt", "editor", "composer")


class UIResolver:
    """Score candidates for a target; ambiguity becomes a question, never a coin flip."""

    MIN_SCORE = 0.55
    TIE_MARGIN = 0.08

    def score(self, c: ControlRef, target: UITarget) -> float:
        role = canonical_role(c.role)
        s = 0.0
        if target.name:
            want, have = _norm(target.name), _norm(c.name)
            if not have:
                return 0.0
            if want == have:
                s = 1.0
            elif have.startswith(want) or have.endswith(want):
                s = 0.85
            elif re.search(rf"\b{re.escape(want)}\b", have):
                s = 0.75
            elif want in have:
                s = 0.6
            else:
                tw, hw = set(want.split()), set(have.split())
                overlap = len(tw & hw) / max(1, len(tw))
                ratio = difflib.SequenceMatcher(None, want, have).ratio()
                s = max(0.7 * overlap, 0.7 * ratio if ratio >= 0.8 else 0.0)
        else:
            s = 0.7 if target.role or target.ordinal else 0.0
        if target.role:
            if role == target.role or (target.role == "textbox" and c.editable):
                s += 0.15
            elif target.role == "listitem" and role in ("link", "heading"):
                s += 0.05                    # web results are often links/headings inside a list
            elif target.role == "button" and role in ("link", "menuitem", "tab", "image"):
                s -= 0.05                    # people say "button" for anything clickable
            else:
                s -= 0.4
        if target.editable and not c.editable:
            s -= 0.3
        if not c.visible:
            s -= 0.3
        if not c.enabled:
            s -= 0.1
        return max(0.0, min(1.2, s))

    def resolve(self, controls: list[ControlRef], target: UITarget) -> OperatorOutcome:
        if not controls:
            return OperatorOutcome(False, "I can't read the controls on this screen.", needs="vision",
                                   evidence={"reason": "no_structured_ui"})
        scored = sorted(((self.score(c, target), i, c) for i, c in enumerate(controls)), key=lambda x: (-x[0], x[1]))
        good = [(s, i, c) for s, i, c in scored if s >= self.MIN_SCORE]
        what = " ".join(x for x in (target.name, target.role) if x) or "that"
        if not good:
            near_misses = [c for s, _i, c in scored[:3] if s > 0.3]
            return OperatorOutcome(False, f"I can't find {what} here.", needs="clarify" if near_misses else "",
                                   candidates=near_misses)
        if target.near:
            anchors = [c for c in controls if _norm(target.near) in _norm(c.name)]
            if anchors:
                a = anchors[0]
                good.sort(key=lambda x: (_distance(x[2], a, controls), -x[0]))
                pick = good[0][2]
                pick.score = good[0][0]
                return OperatorOutcome(True, pick.display_name, resource=pick)
        if target.ordinal:
            top = good[0][0]
            tier = [x for x in good if x[0] >= top - 0.2]
            tier.sort(key=lambda x: x[1])                  # document order
            idx = target.ordinal - 1 if target.ordinal > 0 else len(tier) - 1
            if 0 <= idx < len(tier):
                pick = tier[idx][2]
                pick.score = tier[idx][0]
                return OperatorOutcome(True, pick.display_name, resource=pick)
            return OperatorOutcome(False, f"There are only {len(tier)} matching {target.role or 'items'}.",
                                   needs="clarify", candidates=[x[2] for x in tier])
        if len(good) > 1 and good[0][0] - good[1][0] < self.TIE_MARGIN:
            ties = [x[2] for x in good if good[0][0] - x[0] < self.TIE_MARGIN]
            visible = [c for c in ties if c.visible and c.enabled]
            if len(visible) == 1:
                visible[0].score = good[0][0]
                return OperatorOutcome(True, visible[0].display_name, resource=visible[0])
            names = "; ".join(f"{i + 1}. {c.name or c.role}" for i, c in enumerate(ties[:5]))
            return OperatorOutcome(False, f"There are {len(ties)} matches for {what}: {names}. Which one?",
                                   needs="clarify", candidates=ties)
        pick = good[0][2]
        pick.score = good[0][0]
        return OperatorOutcome(True, pick.display_name, resource=pick)


def _norm(s: str) -> str:
    return re.sub(r"[^\w\s+#@.-]", " ", (s or "").lower()).strip().replace("  ", " ")


def _distance(c: ControlRef, anchor: ControlRef, controls: list[ControlRef]) -> float:
    if any(c.bounds) and any(anchor.bounds):
        cx, cy = (c.bounds[0] + c.bounds[2]) / 2, (c.bounds[1] + c.bounds[3]) / 2
        ax, ay = (anchor.bounds[0] + anchor.bounds[2]) / 2, (anchor.bounds[1] + anchor.bounds[3]) / 2
        return abs(cx - ax) + abs(cy - ay)
    try:                                                    # no geometry: tree order distance
        return abs(controls.index(c) - controls.index(anchor))
    except ValueError:
        return 1e9


# ---------------------------------------------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------------------------------------------

class UIAdapter:
    """Structured UI of one surface. Implementations: Windows UIA, web page, Android, fake."""

    platform = "abstract"

    def snapshot(self) -> list[ControlRef]: raise NotImplementedError
    def invoke(self, c: ControlRef) -> bool: raise NotImplementedError
    def set_value(self, c: ControlRef, text: str) -> bool: raise NotImplementedError
    def focus(self, c: ControlRef) -> bool: return False
    def read(self, c: ControlRef) -> str: return c.name
    def toggle_state(self, c: ControlRef) -> Optional[bool]: return None
    def scroll(self, direction: str, amount: int = 1) -> bool: return False
    def generation(self) -> int: return 0

    def select_option(self, c: ControlRef, option: str) -> bool:
        """Open the list/combo and pick the option by name (generic: invoke, re-read, invoke the option)."""
        if not self.invoke(c):
            return False
        opt = UIResolver().resolve(self.snapshot(), UITarget(name=option, role="listitem"))
        if not opt.ok:
            opt = UIResolver().resolve(self.snapshot(), UITarget(name=option))
        return bool(opt.ok and self.invoke(opt.resource))

    def set_range(self, c: ControlRef, percent: float) -> Optional[float]:
        return None                                     # no slider support on this surface

    def expand(self, c: ControlRef, open_: bool = True) -> Optional[bool]:
        return self.invoke(c) or None


class FakeUIAdapter(UIAdapter):
    platform = "fake"

    def __init__(self, controls: Optional[list[ControlRef]] = None):
        self.controls = controls or []
        self.invoked: list[str] = []
        self.values: dict[str, str] = {}
        self.toggles: dict[str, bool] = {}
        self.scrolled: list[str] = []
        self.on_invoke = None                     # callable(control) for scenario side effects
        self._gen = 0

    def snapshot(self) -> list[ControlRef]:
        return list(self.controls)

    def invoke(self, c: ControlRef) -> bool:
        self.invoked.append(c.name or c.role)
        if canonical_role(c.role) == "checkbox":
            self.toggles[c.name] = not self.toggles.get(c.name, False)
        self._gen += 1
        if self.on_invoke:
            self.on_invoke(c)
        return True

    def set_value(self, c: ControlRef, text: str) -> bool:
        self.values[c.name or c.selector] = text
        self._gen += 1
        return True

    def read(self, c: ControlRef) -> str:
        return self.values.get(c.name or c.selector, c.name)

    def toggle_state(self, c: ControlRef) -> Optional[bool]:
        return self.toggles.get(c.name, False) if canonical_role(c.role) == "checkbox" else None

    def focus(self, c: ControlRef) -> bool:
        return True

    def scroll(self, direction: str, amount: int = 1) -> bool:
        self.scrolled.append(f"{direction}:{amount}")
        return True

    def generation(self) -> int:
        return self._gen

    def select_option(self, c: ControlRef, option: str) -> bool:
        opts = (c.metadata or {}).get("options") or []
        hit = next((o for o in opts if option.lower() in o.lower()), None)
        if hit is None:
            return False
        self.values[c.name] = hit
        self._gen += 1
        return True

    def set_range(self, c: ControlRef, percent: float) -> Optional[float]:
        if canonical_role(c.role) not in ("slider", "range"):
            return None
        self.values[c.name] = str(round(percent))
        self._gen += 1
        return float(percent)

    def expand(self, c: ControlRef, open_: bool = True) -> Optional[bool]:
        self.toggles["expanded:" + c.name] = open_
        self._gen += 1
        return open_


class UIAWindowAdapter(UIAdapter):
    """Windows UI Automation over the existing snapshot builder (patterns only, no coordinates)."""

    platform = "uia"

    def __init__(self, hwnd: int):
        self.hwnd = hwnd
        self._live: dict[str, object] = {}
        self._gen = 0

    def snapshot(self) -> list[ControlRef]:
        from jarvis.core.computer.windows.snapshot import UIASnapshotBuilder
        obs = UIASnapshotBuilder().capture_snapshot(str(self.hwnd), max_elements=400)
        self._gen += 1
        out = []
        for e in obs.elements:
            b = e.bounds_metadata or {}
            out.append(ControlRef(resource_id=e.element_id, resource_type="CONTROL", display_name="",
                                  canonical_identifier=e.element_id, platform="uia", role=e.control_type,
                                  name=e.name, automation_id=e.automation_id, selector=e.ancestor_path,
                                  enabled=e.enabled, visible=e.visible, editable=e.editable,
                                  bounds=(b.get("left", 0), b.get("top", 0), b.get("right", 0), b.get("bottom", 0)),
                                  scope=str(self.hwnd), generation=self._gen,
                                  metadata={"value": e.value_summary, "checked": e.checked}))
        return out

    def _find(self, c: ControlRef):
        from jarvis.core.computer.windows.backend import WindowsUIABackend
        win = WindowsUIABackend().find_window_control(str(self.hwnd))
        if not win:
            return None
        try:
            if c.automation_id:
                ctrl = win.Control(AutomationId=c.automation_id)
                if ctrl and ctrl.Exists(0.3):
                    return ctrl
            if c.name:
                ctrl = win.Control(Name=c.name, ControlTypeName=c.role) if c.role.endswith("Control") else \
                    win.Control(Name=c.name)
                if ctrl and ctrl.Exists(0.3):
                    return ctrl
        except Exception:
            return None
        return None

    def invoke(self, c: ControlRef) -> bool:
        from jarvis.core.computer.windows.patterns import UIAPatterns
        ctrl = self._find(c)
        if not ctrl:
            return False
        role = canonical_role(c.role)
        if role == "checkbox" and UIAPatterns.toggle(ctrl) is not None:
            return True
        if role in ("listitem", "tab", "radio") and UIAPatterns.select(ctrl):
            return True
        if UIAPatterns.invoke(ctrl):
            return True
        return bool(UIAPatterns.expand(ctrl))

    def set_value(self, c: ControlRef, text: str) -> bool:
        from jarvis.core.computer.windows.patterns import UIAPatterns
        ctrl = self._find(c)
        return bool(ctrl) and UIAPatterns.set_value(ctrl, text)

    def focus(self, c: ControlRef) -> bool:
        ctrl = self._find(c)
        try:
            return bool(ctrl) and ctrl.SetFocus() is not False
        except Exception:
            return False

    def read(self, c: ControlRef) -> str:
        ctrl = self._find(c)
        try:
            vp = ctrl.GetValuePattern() if ctrl else None
            if vp:
                return vp.Value or ""
        except Exception:
            pass
        return (ctrl.Name if ctrl else c.name) or ""

    def toggle_state(self, c: ControlRef) -> Optional[bool]:
        ctrl = self._find(c)
        try:
            tp = ctrl.GetTogglePattern() if ctrl else None
            return tp.ToggleState == 1 if tp else None
        except Exception:
            return None

    def scroll(self, direction: str, amount: int = 1) -> bool:
        from jarvis.core.operator.platform import get_desktop, parse_chord
        key = {"down": "pagedown", "up": "pageup", "top": "ctrl+home", "bottom": "ctrl+end"}.get(direction)
        if not key:
            return False
        for _ in range(max(1, amount)):
            get_desktop().press(parse_chord(key))
        return True

    def generation(self) -> int:
        return self._gen


# ---------------------------------------------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------------------------------------------

    def select_option(self, c: ControlRef, option: str) -> bool:
        ctrl = self._find(c)
        if not ctrl:
            return False
        try:
            ec = ctrl.GetExpandCollapsePattern()
            if ec:
                ec.Expand()
            item = ctrl.ListItemControl(Name=option) if hasattr(ctrl, "ListItemControl") else None
            if item is None or not item.Exists(0.5):
                item = next((x for x in ctrl.GetChildren() if option.lower() in (x.Name or "").lower()), None)
            if item is None:
                return False
            sp = item.GetSelectionItemPattern()
            if sp:
                sp.Select()
                return True
            ip = item.GetInvokePattern()
            if ip:
                ip.Invoke()
                return True
        except Exception:
            return False
        return False


    def set_range(self, c: ControlRef, percent: float) -> Optional[float]:
        ctrl = self._find(c)
        try:
            rv = ctrl.GetRangeValuePattern() if ctrl else None
            if not rv:
                return None
            lo, hi = rv.Minimum, rv.Maximum
            rv.SetValue(lo + (hi - lo) * max(0.0, min(percent, 100.0)) / 100.0)
            return (rv.Value - lo) * 100.0 / (hi - lo) if hi > lo else None
        except Exception:
            return None


    def expand(self, c: ControlRef, open_: bool = True) -> Optional[bool]:
        ctrl = self._find(c)
        try:
            ec = ctrl.GetExpandCollapsePattern() if ctrl else None
            if not ec:
                return None
            ec.Expand() if open_ else ec.Collapse()
            return ec.ExpandCollapseState in ((1, 2) if open_ else (0,))   # 1 expanded, 2 partial, 0 collapsed
        except Exception:
            return None


_REQUIRED = re.compile(r"\*|\brequired\b|\bmandatory\b")
_AGREE = re.compile(r"\b(agree|accept|terms|consent|confirm|i have read)\b", re.I)


class UIOperator:
    """find / invoke / set_value / read / scroll with the safety rules and verification."""

    def __init__(self, resolver: Optional[UIResolver] = None):
        self.resolver = resolver or UIResolver()

    def find(self, adapter: UIAdapter, target: UITarget | str) -> OperatorOutcome:
        t = UITarget.parse(target) if isinstance(target, str) else target
        return self.resolver.resolve(adapter.snapshot(), t)

    def invoke(self, adapter: UIAdapter, target: UITarget | str, approved: bool = False) -> OperatorOutcome:
        found = self.find(adapter, target)
        if not found.ok:
            return found
        c: ControlRef = found.resource
        if re.search(r"not a robot|captcha", c.name, re.I):
            return OperatorOutcome(False, "That's a CAPTCHA - please complete it yourself; I'll wait.", resource=c,
                                   needs="user")
        if CONSEQUENTIAL.search(c.name) and not approved:
            return OperatorOutcome(False, f"'{c.name}' has real consequences. Say yes to confirm.", resource=c,
                                   needs="approve")
        if not c.enabled:
            return OperatorOutcome(False, f"'{c.name or c.role}' is disabled right now.", resource=c)
        before_gen = adapter.generation()
        before_toggle = adapter.toggle_state(c)
        ok = adapter.invoke(c)
        if not ok:
            return OperatorOutcome(False, f"'{c.name or c.role}' didn't respond.", resource=c)
        evidence = {"invoked": c.name, "role": canonical_role(c.role), "platform": c.platform}
        after_toggle = adapter.toggle_state(c)
        if before_toggle is not None:
            evidence["toggled"] = before_toggle != after_toggle
            ok = before_toggle != after_toggle
        evidence["ui_changed"] = adapter.generation() != before_gen
        return OperatorOutcome(ok, f"Clicked {c.name or c.role}." if ok else f"{c.name} didn't change.",
                               resource=c, evidence=evidence)

    def set_value(self, adapter: UIAdapter, target: UITarget | str, text: str) -> OperatorOutcome:
        t = UITarget.parse(target) if isinstance(target, str) else target
        if t.editable is None:
            t.editable = True
        found = self.resolver.resolve(adapter.snapshot(), t)
        if not found.ok:
            return found
        c: ControlRef = found.resource
        if SENSITIVE.search(f"{c.name} {c.automation_id}"):
            return OperatorOutcome(False, "That's a password/code field - I never type those. Please enter it yourself.",
                                   resource=c, needs="user")
        if not c.editable:
            return OperatorOutcome(False, f"'{c.name or c.role}' isn't a text field.", resource=c, needs="clarify")
        if not adapter.set_value(c, text):
            return OperatorOutcome(False, f"I couldn't type into {c.name or c.role}.", resource=c)
        got = adapter.read(c)
        ok = got == text or text in (got or "")
        return OperatorOutcome(ok, f"Typed into {c.name or c.role}." if ok else
                               f"The text in {c.name or c.role} didn't take.", resource=c,
                               evidence={"value_verified": ok})

    def read(self, adapter: UIAdapter, target: UITarget | str) -> OperatorOutcome:
        found = self.find(adapter, target)
        if not found.ok:
            return found
        text = adapter.read(found.resource)
        # Screen text is data: returned for display, never executed.
        return OperatorOutcome(True, text, resource=found.resource, evidence={"untrusted": True})

    def scroll(self, adapter: UIAdapter, direction: str = "down", amount: int = 1) -> OperatorOutcome:
        ok = adapter.scroll(direction, amount)
        return OperatorOutcome(ok, f"Scrolled {direction}." if ok else "I can't scroll this.")

    def select(self, adapter: UIAdapter, option: str, within: str = "") -> OperatorOutcome:
        """'choose Python from this list' / 'pick India': the option inside a combo/list (or a radio by name)."""
        controls = adapter.snapshot()
        lists = [c for c in controls if canonical_role(c.role) in ("combobox", "listbox", "list")]
        if within:
            hit = self.resolver.resolve(controls, UITarget.parse(within))
            lists = [hit.resource] if hit.ok else lists
        for c in lists:
            if adapter.select_option(c, option):
                got = adapter.read(c)
                return OperatorOutcome(True, f"Selected {option}.", resource=c, evidence={"value": got})
        direct = self.resolver.resolve(controls, UITarget(name=option))
        if direct.ok and canonical_role(direct.resource.role) in ("radio", "listitem", "menuitem", "tab", "button", "checkbox"):
            return self.invoke(adapter, UITarget(name=option))
        if len(lists) > 1 and not within:
            return OperatorOutcome(False, "Which list? " + "; ".join(c.name or c.role for c in lists[:5]), needs="clarify",
                                   candidates=lists)
        return OperatorOutcome(False, f"I can't find the option '{option}' here.", needs="clarify" if lists else "")

    def slider(self, adapter: UIAdapter, target: str, percent: float) -> OperatorOutcome:
        controls = adapter.snapshot()
        t = UITarget.parse(target) if target else UITarget(role="slider")
        if not t.role:
            t.role = "slider"
        found = self.resolver.resolve(controls, t)
        if not found.ok:
            sliders = [c for c in controls if canonical_role(c.role) in ("slider", "range")]
            if len(sliders) == 1:
                found = OperatorOutcome(True, sliders[0].name, resource=sliders[0])
            else:
                return found if not sliders else OperatorOutcome(False, "Which slider?", needs="clarify", candidates=sliders)
        got = adapter.set_range(found.resource, percent)
        if got is None:
            return OperatorOutcome(False, f"'{found.resource.name or 'That control'}' isn't a slider I can set.",
                                   resource=found.resource)
        ok = abs(got - percent) <= 2.0
        return OperatorOutcome(ok, f"Set {found.resource.name or 'the slider'} to {round(got)}%." if ok else
                               f"The slider stopped at {round(got)}%.", resource=found.resource, evidence={"value": got})

    def expand(self, adapter: UIAdapter, target: str, open_: bool = True) -> OperatorOutcome:
        found = self.find(adapter, target or "tree item")
        if not found.ok:
            return found
        got = adapter.expand(found.resource, open_)
        verb = "Expanded" if open_ else "Collapsed"
        if got is None:
            return OperatorOutcome(False, f"'{found.resource.name}' can't be {verb.lower()}.", resource=found.resource)
        return OperatorOutcome(bool(got) == open_ or got is True, f"{verb} {found.resource.name or 'it'}.",
                               resource=found.resource)

    def menu(self, adapter: UIAdapter, path: list[str]) -> OperatorOutcome:
        """'open the File menu and choose Save As': each level is found again after the previous one opened."""
        last = None
        for i, name in enumerate(path):
            role = "menuitem"
            found = self.resolver.resolve(adapter.snapshot(), UITarget(name=name, role=role))
            if not found.ok:
                return OperatorOutcome(False, f"I opened {' > '.join(path[:i]) or 'the menu bar'} but can't see '{name}'.",
                                       needs=found.needs, candidates=found.candidates)
            if CONSEQUENTIAL.search(found.resource.name):
                return OperatorOutcome(False, f"'{found.resource.name}' has real consequences. Say yes to confirm.",
                                       resource=found.resource, needs="approve")
            if not adapter.invoke(found.resource):
                return OperatorOutcome(False, f"'{name}' didn't open.", resource=found.resource)
            last = found.resource
        return OperatorOutcome(True, f"Chose {' > '.join(path)}.", resource=last)

    def clear(self, adapter: UIAdapter, target: str = "") -> OperatorOutcome:
        t = UITarget.parse(target) if target else UITarget(role="textbox", editable=True)
        t.editable = True
        controls = adapter.snapshot()
        found = self.resolver.resolve(controls, t)
        if not found.ok:
            focused = [c for c in controls if c.editable and (c.metadata or {}).get("focused")]
            if len(focused) != 1:
                return found
            found = OperatorOutcome(True, focused[0].name, resource=focused[0])
        c = found.resource
        if SENSITIVE.search(f"{c.name} {c.automation_id}"):
            return OperatorOutcome(False, "That's a password/code field - clear it yourself.", resource=c, needs="user")
        if not adapter.set_value(c, ""):
            return OperatorOutcome(False, f"I couldn't clear {c.name or 'the field'}.", resource=c)
        ok = not (adapter.read(c) or "").strip() or adapter.read(c) == c.name
        return OperatorOutcome(ok, f"Cleared {c.name or 'the field'}." if ok else "The field still has text.", resource=c)

    def explain(self, adapter: UIAdapter, target: str) -> OperatorOutcome:
        """'why can't I press Continue?': the control's state plus what on the form usually blocks it."""
        controls = adapter.snapshot()
        found = self.resolver.resolve(controls, UITarget.parse(target)) if target else OperatorOutcome(False, "")
        reasons: list[str] = []
        for c in controls:
            if c.editable and _REQUIRED.search(c.name or "") and not (adapter.read(c) or "").strip("* ") \
                    and adapter.read(c) != c.name:
                reasons.append(f"the required field '{c.name.strip(' *')}' is empty")
            elif canonical_role(c.role) == "checkbox" and _AGREE.search(c.name or "") and adapter.toggle_state(c) is False:
                reasons.append(f"'{c.name}' isn't ticked")
            elif re.search(r"\b(error|invalid|incorrect|must|required)\b", c.name or "", re.I) and \
                    canonical_role(c.role) not in ("button", "textbox"):
                reasons.append(f"the page says: {c.name[:80]}")
        if found.ok:
            c = found.resource
            state = "disabled" if not c.enabled else "enabled"
            head = f"'{c.name}' is {state}."
            if c.enabled:
                return OperatorOutcome(True, head + " It should respond - want me to click it?", resource=c,
                                       evidence={"enabled": True})
        else:
            head = "I can't find that control." if target else "Here's what I see."
        if reasons:
            return OperatorOutcome(True, head + " Likely blocking it: " + "; ".join(reasons[:4]) + ".",
                                   resource=found.resource, evidence={"reasons": reasons, "untrusted": True})
        return OperatorOutcome(True, head + " I don't see an empty required field or an unticked box - it may be "
                               "waiting on something off-screen.", resource=found.resource, evidence={"reasons": []})

    def remove_attachment(self, adapter: UIAdapter, which: str = "") -> OperatorOutcome:
        """Removes an attachment chip by invoking its own Remove/Close control - never deletes a file."""
        controls = adapter.snapshot()
        removers = [c for c in controls if re.search(r"\b(remove|delete|close|clear|discard)\b", c.name or "", re.I)
                    and canonical_role(c.role) in ("button", "image", "link")]
        if which:
            words = [w for w in re.findall(r"[a-z0-9]+", which.lower()) if w not in ("the", "attachment", "attached")]
            ords = {"first": 0, "second": 1, "third": 2, "last": -1}
            idx = next((v for k, v in ords.items() if k in words), None)
            named = [c for c in removers if any(w in (c.name or "").lower() for w in words if w not in ords)]
            removers = named or removers
            if idx is not None and removers:
                removers = [removers[idx]]
        if not removers:
            return OperatorOutcome(False, "I don't see an attachment with a remove button.")
        if len(removers) > 1:
            return OperatorOutcome(False, "Which attachment? " + "; ".join(c.name for c in removers[:5]), needs="clarify",
                                   candidates=removers)
        before = len(controls)
        if not adapter.invoke(removers[0]):
            return OperatorOutcome(False, "The remove button didn't respond.", resource=removers[0])
        gone = len(adapter.snapshot()) < before
        return OperatorOutcome(True, "Removed the attachment." if gone else "Pressed remove on the attachment.",
                               resource=removers[0], evidence={"verified": gone})

    def modal(self, adapter: UIAdapter) -> OperatorOutcome:
        controls = adapter.snapshot()
        dialogs = [c for c in controls if canonical_role(c.role) in ("dialog", "window") or (c.metadata or {}).get("modal")]
        if not dialogs:
            return OperatorOutcome(True, "No popup is blocking the window.", evidence={"modal": False})
        d = dialogs[0]
        return OperatorOutcome(True, f"Yes - a dialog '{d.name or 'untitled'}' is open.", resource=d,
                               evidence={"modal": True, "untrusted": True})
