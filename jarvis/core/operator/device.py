"""device.* primitives: the owner's Android phone over ADB, as typed operations only.

Every ADB call is built here from a fixed operation table with validated parameters (package names, key names,
file paths, http(s) URLs) - never a shell string from a model. Only devices ADB reports as *authorized* are used.
A locked phone stays locked: UI work pauses for the owner, and PINs/patterns are never entered. Taps come from the
phone's own UI tree (uiautomator), so a control is found by its text/description, not by guessed coordinates.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from jarvis.core.operator.refs import ControlRef, OperatorOutcome, ScreenshotResourceRef
from jarvis.core.operator.resources import OperatorResources, get_resources
from jarvis.core.operator.ui import SENSITIVE, UIAdapter, UIOperator, UITarget

logger = logging.getLogger("jarvis.operator.device")

KEYS = {"back": 4, "home": 3, "recents": 187, "app_switch": 187, "enter": 66, "delete": 67, "tab": 61,
        "volume_up": 24, "volume_down": 25, "mute": 164, "play_pause": 85, "play": 126, "pause": 127,
        "next": 87, "previous": 88, "stop": 86, "wake": 224, "sleep": 223, "lock": 223, "menu": 82, "search": 84,
        "camera": 27, "brightness_up": 221, "brightness_down": 220, "notifications": -1, "quick_settings": -2,
        "screenshot": 120, "page_down": 93, "page_up": 92, "dpad_up": 19, "dpad_down": 20, "escape": 111}
APPS = {"whatsapp": "com.whatsapp", "youtube": "com.google.android.youtube", "chrome": "com.android.chrome",
        "gmail": "com.google.android.gm", "maps": "com.google.android.apps.maps", "camera": "com.android.camera",
        "settings": "com.android.settings", "photos": "com.google.android.apps.photos",
        "spotify": "com.spotify.music", "instagram": "com.instagram.android", "telegram": "org.telegram.messenger",
        "phone": "com.google.android.dialer", "messages": "com.google.android.apps.messaging",
        "calendar": "com.google.android.calendar", "clock": "com.google.android.deskclock",
        "files": "com.google.android.apps.nbu.files", "play store": "com.android.vending",
        "calculator": "com.google.android.calculator", "contacts": "com.google.android.contacts",
        "drive": "com.google.android.apps.docs", "meet": "com.google.android.apps.tachyon"}
_PKG = re.compile(r"^[a-zA-Z][\w]*(\.[\w]+)+$")
DEV_OPS = ("logcat", "packages", "battery", "install_apk", "uninstall", "open_url", "screen_state", "storage",
           "device_info", "clear_app_data")
DEV_NEEDS_APPROVAL = {"install_apk", "uninstall", "clear_app_data"}


class Adb:
    """argv-only ADB runner bound to one authorized device."""

    def __init__(self, adb_path: str = "", serial: str = ""):
        self.bin = adb_path or shutil.which("adb") or ""
        if not self.bin:
            try:
                from jarvis.connectors.android.scrcpy import find_tool
                self.bin = find_tool("adb") or ""
            except Exception:
                self.bin = ""
        self.serial = serial

    def devices(self) -> list[dict]:
        code, out, _ = self.run(["devices", "-l"], device=False)
        found = []
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2:
                found.append({"serial": parts[0], "state": parts[1],
                              "model": next((p.split(":", 1)[1] for p in parts[2:] if p.startswith("model:")), "")})
        return found

    def run(self, args: list[str], device: bool = True, timeout: float = 8.0, binary: bool = False):
        if not self.bin:
            return -1, b"" if binary else "", "adb not found"
        cmd = [self.bin] + (["-s", self.serial] if device and self.serial else []) + args
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=timeout, text=not binary,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return r.returncode, r.stdout if binary else r.stdout.strip(), (r.stderr or "") if not binary else ""
        except subprocess.TimeoutExpired:
            return -1, b"" if binary else "", "timed out"
        except Exception as e:
            return -1, b"" if binary else "", str(e)


class FakeAdb(Adb):
    """Scripted phone for tests: a UI tree, installed packages, files, lock state, and a call log."""

    def __init__(self, xml: str = "", locked: bool = False, authorized: bool = True):
        self.bin, self.serial = "adb", "FAKE01"
        self.xml = xml
        self.locked = locked
        self.authorized = authorized
        self.calls: list[list[str]] = []
        self.files: dict[str, bytes] = {}
        self.packages = {"com.whatsapp", "com.google.android.youtube", "com.android.chrome", "com.android.settings"}
        self.typed: list[str] = []
        self.on_tap = None

    def devices(self):
        return [{"serial": "FAKE01", "state": "device" if self.authorized else "unauthorized", "model": "Pixel"}]

    def run(self, args, device=True, timeout=8.0, binary=False):
        self.calls.append(list(args))
        a = args
        if a[:2] == ["shell", "dumpsys"] and a[2:3] == ["window"]:
            return 0, f"mDreamingLockscreen={'true' if self.locked else 'false'} isKeyguardShowing={str(self.locked).lower()}", ""
        if a[:3] == ["shell", "uiautomator", "dump"]:
            return 0, "UI hierchary dumped to: /sdcard/jarvis_ui.xml", ""
        if a[:2] == ["shell", "cat"]:
            return 0, self.xml, ""
        if a[:3] == ["shell", "input", "tap"]:
            if self.on_tap:
                self.on_tap(int(a[3]), int(a[4]))
            return 0, "", ""
        if a[:3] == ["shell", "input", "text"]:
            self.typed.append(a[3])
            return 0, "", ""
        if a[:2] == ["push", a[1]] and len(a) == 3:
            self.files[a[2].rstrip("/") + "/" + os.path.basename(a[1])] = b"x"
            return 0, "1 file pushed", ""
        if a[:2] == ["shell", "ls"]:
            path = a[2]
            return (0, path, "") if path in self.files else (1, "", "No such file")
        if a[:3] == ["shell", "pm", "list"]:
            return 0, "\n".join(f"package:{p}" for p in sorted(self.packages)), ""
        if a[:2] == ["exec-out", "screencap"]:
            return 0, b"\x89PNG\r\n\x1a\nfakephone", ""
        if a[:2] == ["shell", "monkey"]:
            return (0, "Events injected: 1", "") if a[3] in self.packages else (0, "No activities found", "")
        return 0, "", ""


def _parse_nodes(xml: str) -> list[dict]:
    nodes = []
    for m in re.finditer(r"<node\b[^>]*>", xml or ""):
        tag = m.group(0)
        attr = dict(re.findall(r'(\w[\w-]*)="([^"]*)"', tag))
        b = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", attr.get("bounds", ""))
        if not b:
            continue
        nodes.append({**attr, "_bounds": tuple(map(int, b.groups()))})
    return nodes


class AndroidUIAdapter(UIAdapter):
    platform = "android"

    def __init__(self, op: "DeviceOperator"):
        self.op = op
        self._gen = 0
        self._typed: dict[str, str] = {}

    def snapshot(self) -> list[ControlRef]:
        xml = self.op.ui_xml()
        self._gen += 1
        out = []
        for n in _parse_nodes(xml):
            name = n.get("text") or n.get("content-desc") or ""
            cls = n.get("class", "")
            clickable = n.get("clickable") == "true"
            editable = cls.endswith("EditText")
            if not (name or editable or clickable):
                continue
            out.append(ControlRef(resource_id=f"and:{n.get('resource-id', '')}:{n['_bounds']}", platform="android",
                                  role=cls if not (clickable and cls.endswith(("TextView", "View", "Layout",
                                                                                "FrameLayout", "LinearLayout")))
                                  else "button", name=name, automation_id=n.get("resource-id", ""),
                                  selector=",".join(map(str, n["_bounds"])), enabled=n.get("enabled", "true") == "true",
                                  visible=True, editable=editable, bounds=n["_bounds"], generation=self._gen,
                                  metadata={"password": n.get("password") == "true", "checked": n.get("checked")}))
        return out

    def _tap(self, c: ControlRef) -> bool:
        l, t, r, b = c.bounds
        code, _, _ = self.op.adb.run(["shell", "input", "tap", str((l + r) // 2), str((t + b) // 2)])
        self._gen += 1
        return code == 0

    def invoke(self, c):
        return self._tap(c)

    def focus(self, c):
        return self._tap(c)

    def set_value(self, c, text):
        if (c.metadata or {}).get("password"):
            return False
        if not self._tap(c):
            return False
        escaped = re.sub(r"([\\\"'`$&|;<>()* ])", lambda m: "%s" if m.group(1) == " " else "\\" + m.group(1), text)
        code, _, _ = self.op.adb.run(["shell", "input", "text", escaped])
        if code == 0:
            self._typed[c.resource_id] = text
        return code == 0

    def read(self, c):
        return self._typed.get(c.resource_id, c.name)

    def toggle_state(self, c):
        v = (c.metadata or {}).get("checked")
        if v is None or canonical_checkable(c) is False:
            return None
        for x in self.snapshot():
            if x.bounds == c.bounds:
                return (x.metadata or {}).get("checked") == "true"
        return None

    def scroll(self, direction, amount=1):
        dy = {"down": (1500, 500), "up": (500, 1500)}.get(direction)
        if not dy:
            return False
        for _ in range(max(1, amount)):
            self.op.adb.run(["shell", "input", "swipe", "540", str(dy[0]), "540", str(dy[1]), "250"])
        return True

    def generation(self):
        return self._gen


def canonical_checkable(c: ControlRef) -> bool:
    return c.role.endswith(("CheckBox", "Switch", "ToggleButton", "RadioButton"))


class DeviceOperator:
    def __init__(self, adb: Optional[Adb] = None, resources: Optional[OperatorResources] = None,
                 allowed_serials: tuple[str, ...] = ()):
        self._adb = adb
        self._res = resources
        self.allowed = allowed_serials
        self.ui = UIOperator()

    @property
    def adb(self) -> Adb:
        if self._adb is None:
            self._adb = Adb()
        return self._adb

    @property
    def resources(self) -> OperatorResources:
        return self._res or get_resources()

    # -- device checks ---------------------------------------------------------------------------------------
    def ready(self) -> OperatorOutcome:
        if not self.adb.bin:
            return OperatorOutcome(False, "ADB isn't installed, so I can't reach the phone.")
        devs = self.adb.devices()
        authorized = [d for d in devs if d["state"] == "device" and (not self.allowed or d["serial"] in self.allowed)]
        if not authorized:
            if any(d["state"] == "unauthorized" for d in devs):
                return OperatorOutcome(False, "The phone is asking to allow USB debugging - tap Allow on the phone.",
                                       needs="user")
            return OperatorOutcome(False, "No phone is connected.")
        if not self.adb.serial:
            self.adb.serial = authorized[0]["serial"]
        elif self.adb.serial not in {d["serial"] for d in authorized}:
            return OperatorOutcome(False, "That phone isn't authorized.")
        return OperatorOutcome(True, authorized[0].get("model") or self.adb.serial)

    def locked(self) -> bool:
        _, out, _ = self.adb.run(["shell", "dumpsys", "window"])
        return bool(re.search(r"(mDreamingLockscreen|isKeyguardShowing|mShowingLockscreen)=true", out or ""))

    def _gate(self, needs_unlocked: bool = True) -> Optional[OperatorOutcome]:
        r = self.ready()
        if not r.ok:
            return r
        if needs_unlocked and self.locked():
            return OperatorOutcome(False, "The phone is locked - unlock it yourself and I'll carry on.", needs="user")
        return None

    def ui_xml(self) -> str:
        self.adb.run(["shell", "uiautomator", "dump", "/sdcard/jarvis_ui.xml"])
        _, out, _ = self.adb.run(["shell", "cat", "/sdcard/jarvis_ui.xml"])
        return out or ""

    def adapter(self) -> AndroidUIAdapter:
        return AndroidUIAdapter(self)

    # -- primitives ------------------------------------------------------------------------------------------
    def key(self, name: str, repeat: int = 1) -> OperatorOutcome:
        name = name.lower().replace(" ", "_")
        if name not in KEYS:
            return OperatorOutcome(False, f"The phone has no '{name}' key.", needs="clarify")
        bad = self._gate(needs_unlocked=name not in ("wake", "sleep", "lock", "volume_up", "volume_down", "mute",
                                                     "play_pause", "play", "pause", "next", "previous"))
        if bad:
            return bad
        code = KEYS[name]
        for _ in range(max(1, min(repeat, 30))):
            if code == -1:
                self.adb.run(["shell", "cmd", "statusbar", "expand-notifications"])
            elif code == -2:
                self.adb.run(["shell", "cmd", "statusbar", "expand-settings"])
            else:
                self.adb.run(["shell", "input", "keyevent", str(code)])
        return OperatorOutcome(True, f"Pressed {name.replace('_', ' ')} on the phone.", evidence={"keycode": code})

    def open_app(self, app: str) -> OperatorOutcome:
        bad = self._gate()
        if bad:
            return bad
        pkg = APPS.get(app.lower().strip(), app.strip())
        if not _PKG.match(pkg):
            pkg = self._find_package(app)
            if not pkg:
                return OperatorOutcome(False, f"I can't find {app} on the phone.")
        _, out, _ = self.adb.run(["shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"])
        ok = "No activities" not in (out or "") and "aborted" not in (out or "").lower()
        return OperatorOutcome(ok, f"Opened {app} on the phone." if ok else f"{app} didn't open on the phone.",
                               evidence={"package": pkg})

    def close_app(self, app: str) -> OperatorOutcome:
        bad = self._gate(needs_unlocked=False)
        if bad:
            return bad
        pkg = APPS.get(app.lower().strip(), app.strip())
        if not _PKG.match(pkg):
            return OperatorOutcome(False, f"Which app is {app}?", needs="clarify")
        self.adb.run(["shell", "am", "force-stop", pkg])
        return OperatorOutcome(True, f"Closed {app} on the phone.", evidence={"package": pkg})

    def _find_package(self, app: str) -> str:
        _, out, _ = self.adb.run(["shell", "pm", "list", "packages"])
        want = re.sub(r"\W", "", app.lower())
        hits = [l.split(":", 1)[1] for l in (out or "").splitlines() if l.startswith("package:")
                and want and want in l.lower().replace(".", "")]
        return hits[0] if len(hits) == 1 else ""

    def tap(self, target: str, approved: bool = False) -> OperatorOutcome:
        bad = self._gate()
        if bad:
            return bad
        return self.ui.invoke(self.adapter(), target, approved=approved)

    def type_into(self, target: str, text: str) -> OperatorOutcome:
        bad = self._gate()
        if bad:
            return bad
        if SENSITIVE.search(target):
            return OperatorOutcome(False, "I never type passwords or codes - please enter it on the phone.", needs="user")
        return self.ui.set_value(self.adapter(), target or "text field", text)

    def media(self, op: str) -> OperatorOutcome:
        return self.key({"toggle": "play_pause"}.get(op, op))

    def notifications(self) -> OperatorOutcome:
        bad = self._gate(needs_unlocked=False)
        if bad:
            return bad
        from jarvis.connectors.android.scrcpy import parse_notifications
        _, out, _ = self.adb.run(["shell", "dumpsys", "notification", "--noredact"], timeout=10)
        items = parse_notifications(out or "")
        # Notification text is untrusted: summarised for the owner, never followed.
        lines = [f"{n.get('app', '')}: {n.get('title', '')} - {n.get('text', '')}".strip(" -:") for n in items[:15]]
        return OperatorOutcome(True, "\n".join(lines) or "No notifications.", evidence={"untrusted": True,
                                                                                        "count": len(items)})

    def screenshot(self, folder: Optional[Path] = None) -> OperatorOutcome:
        bad = self._gate(needs_unlocked=False)
        if bad:
            return bad
        code, data, _ = self.adb.run(["exec-out", "screencap", "-p"], binary=True, timeout=10)
        if code != 0 or not data:
            return OperatorOutcome(False, "The phone didn't send a screenshot.")
        from jarvis.config import ROOT
        out = (folder or ROOT / "screenshots") / f"phone-{time.strftime('%Y%m%d-%H%M%S')}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        ref = ScreenshotResourceRef(resource_id=f"shot:{out.name}", path=str(out), source_window="phone",
                                    source_app="android", capture_time=time.time())
        self.resources.record(ref)
        return OperatorOutcome(True, "Phone screenshot saved.", resource=ref, evidence={"path": str(out)})

    def push(self, local: str, device=None, folder: str = "/sdcard/Download") -> OperatorOutcome:
        bad = self._gate(needs_unlocked=False)
        if bad:
            return bad
        p = Path(local)
        if not p.is_file():
            return OperatorOutcome(False, f"{p.name} doesn't exist any more.")
        code, _, err = self.adb.run(["push", str(p), folder + "/"], timeout=120)
        remote = f"{folder}/{p.name}"
        lc, _, _ = self.adb.run(["shell", "ls", remote])
        ok = code == 0 and lc == 0
        return OperatorOutcome(ok, f"Sent {p.name} to the phone's Downloads." if ok else
                               f"The transfer didn't complete ({err or 'not found on the phone'}).",
                               evidence={"remote": remote, "verified": ok})

    def dev(self, op: str, arg: str = "", approved: bool = False) -> OperatorOutcome:
        """Allow-listed developer operations."""
        if op not in DEV_OPS:
            return OperatorOutcome(False, f"'{op}' isn't an allowed phone operation.", needs="clarify")
        if op in DEV_NEEDS_APPROVAL and not approved:
            return OperatorOutcome(False, f"{op.replace('_', ' ').title()} {arg} on the phone - say yes to confirm.",
                                   needs="approve")
        bad = self._gate(needs_unlocked=False)
        if bad:
            return bad
        a = self.adb
        if op == "logcat":
            n = int(arg) if arg.isdigit() else 200
            _, out, _ = a.run(["logcat", "-d", "-t", str(min(n, 2000))], timeout=10)
            return OperatorOutcome(True, out[-8000:] or "Log is empty.", evidence={"untrusted": True})
        if op == "packages":
            _, out, _ = a.run(["shell", "pm", "list", "packages", "-3"])
            pk = [l.split(":", 1)[1] for l in (out or "").splitlines() if ":" in l]
            return OperatorOutcome(True, "\n".join(pk) or "No user apps.", evidence={"count": len(pk)})
        if op == "battery":
            _, out, _ = a.run(["shell", "dumpsys", "battery"])
            lvl = re.search(r"level:\s*(\d+)", out or "")
            chg = re.search(r"(AC|USB|Wireless) powered:\s*true", out or "")
            return OperatorOutcome(bool(lvl), f"Battery {lvl.group(1)}%{' and charging' if chg else ''}." if lvl
                                   else "I couldn't read the battery.")
        if op == "screen_state":
            return OperatorOutcome(True, "Locked." if self.locked() else "Unlocked.")
        if op == "storage":
            _, out, _ = a.run(["shell", "df", "-h", "/sdcard"])
            return OperatorOutcome(True, out or "Unknown.")
        if op == "device_info":
            _, model, _ = a.run(["shell", "getprop", "ro.product.model"])
            _, ver, _ = a.run(["shell", "getprop", "ro.build.version.release"])
            return OperatorOutcome(True, f"{model} on Android {ver}.")
        if op == "open_url":
            if not re.match(r"^https?://[\w.-]+(/\S*)?$", arg or ""):
                return OperatorOutcome(False, "That isn't a web address I can open.", needs="clarify")
            a.run(["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", arg])
            return OperatorOutcome(True, f"Opened {arg} on the phone.")
        if op == "install_apk":
            p = Path(arg)
            if p.suffix.lower() != ".apk" or not p.is_file():
                return OperatorOutcome(False, "Give me a local .apk file to install.", needs="clarify")
            code, out, err = a.run(["install", "-r", str(p)], timeout=180)
            ok = code == 0 and "Success" in (out or "")
            return OperatorOutcome(ok, f"Installed {p.name}." if ok else f"Install failed: {err or out}")
        if op in ("uninstall", "clear_app_data"):
            pkg = APPS.get(arg.lower(), arg)
            if not _PKG.match(pkg):
                return OperatorOutcome(False, f"Which app is {arg}?", needs="clarify")
            argv = ["uninstall", pkg] if op == "uninstall" else ["shell", "pm", "clear", pkg]
            code, out, err = a.run(argv, timeout=60)
            ok = code == 0 and "Success" in (out or "")
            return OperatorOutcome(ok, f"{'Uninstalled' if op == 'uninstall' else 'Cleared data for'} {arg}." if ok
                                   else f"That didn't work: {err or out}")
        return OperatorOutcome(False, "Not supported.")


_dev: Optional[DeviceOperator] = None


def get_device_operator() -> DeviceOperator:
    global _dev
    if _dev is None:
        _dev = DeviceOperator()
    return _dev


def set_device_operator(d: Optional[DeviceOperator]) -> None:
    global _dev
    _dev = d
