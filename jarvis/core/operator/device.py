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


SETTINGS_ACTIONS = {"wifi": "android.settings.WIFI_SETTINGS", "bluetooth": "android.settings.BLUETOOTH_SETTINGS",
                    "display": "android.settings.DISPLAY_SETTINGS", "sound": "android.settings.SOUND_SETTINGS",
                    "battery": "android.intent.action.POWER_USAGE_SUMMARY", "storage": "android.settings.INTERNAL_STORAGE_SETTINGS",
                    "location": "android.settings.LOCATION_SOURCE_SETTINGS", "settings": "android.settings.SETTINGS",
                    "apps": "android.settings.APPLICATION_SETTINGS", "notifications": "android.settings.NOTIFICATION_SETTINGS",
                    "developer": "android.settings.APPLICATION_DEVELOPMENT_SETTINGS"}


def _device_extras():
    """Phone primitives added for the 520-capability set; still argv-only ADB, still lock- and approval-aware."""

    def recents(self) -> OperatorOutcome:
        return self.key("recents")

    def previous_app(self) -> OperatorOutcome:
        bad = self._gate()
        if bad:
            return bad
        self.adb.run(["shell", "input", "keyevent", "187"])
        self.adb.run(["shell", "input", "keyevent", "187"])           # double recents = switch to the previous app
        return OperatorOutcome(True, "Switched to the previous phone app.", evidence={"verified": None})

    def settings(self, page: str = "settings", app: str = "") -> OperatorOutcome:
        bad = self._gate()
        if bad:
            return bad
        page = page.lower().replace("-", "").replace(" ", "")
        page = {"wifi": "wifi", "wlan": "wifi", "bt": "bluetooth", "notification": "notifications", "appinfo": "appinfo",
                "info": "appinfo"}.get(page, page)
        if page in ("appinfo", "notifications") and app:
            pkg = APPS.get(app.lower(), app)
            if not _PKG.match(pkg):
                pkg = self._find_package(app)
            if not pkg:
                return OperatorOutcome(False, f"Which app is {app}?", needs="clarify")
            if page == "appinfo":
                argv = ["shell", "am", "start", "-a", "android.settings.APPLICATION_DETAILS_SETTINGS", "-d", f"package:{pkg}"]
            else:
                argv = ["shell", "am", "start", "-a", "android.settings.APP_NOTIFICATION_SETTINGS", "--es",
                        "android.provider.extra.APP_PACKAGE", pkg]
        else:
            action = SETTINGS_ACTIONS.get(page)
            if not action:
                return OperatorOutcome(False, f"I don't know the phone's '{page}' settings page.", needs="clarify")
            argv = ["shell", "am", "start", "-a", action]
        code, _, err = self.adb.run(argv)
        return OperatorOutcome(code == 0, f"Opened {page} settings on the phone." if code == 0 else f"That didn't open: {err}")

    def volume(self, percent: float, stream: int = 3) -> OperatorOutcome:
        bad = self._gate(needs_unlocked=False)
        if bad:
            return bad
        _, out, _ = self.adb.run(["shell", "cmd", "media_session", "volume", "--stream", str(stream), "--get"])
        m = re.search(r"in \[(\d+), (\d+)\]", out or "")
        lo, hi = (int(m.group(1)), int(m.group(2))) if m else (0, 15)
        level = round(lo + (hi - lo) * max(0.0, min(percent, 100.0)) / 100.0)
        self.adb.run(["shell", "cmd", "media_session", "volume", "--stream", str(stream), "--set", str(level)])
        _, after, _ = self.adb.run(["shell", "cmd", "media_session", "volume", "--stream", str(stream), "--get"])
        got = re.search(r"volume is (\d+)", after or "")
        ok = got is None or int(got.group(1)) == level
        return OperatorOutcome(ok, f"Phone media volume set to {round(percent)}%." if ok else "The phone volume didn't change.",
                               evidence={"level": level, "max": hi, "verified": got is not None})

    def media(self, op: str, seconds: float = 0) -> OperatorOutcome:
        code = {"seek_forward": "90", "fast_forward": "90", "seek_back": "89", "rewind": "89"}.get(op)
        if code:
            bad = self._gate(needs_unlocked=False)
            if bad:
                return bad
            presses = max(1, round(abs(seconds) / 10)) if seconds else 1   # most players skip ~10 s per press
            for _ in range(min(presses, 30)):
                self.adb.run(["shell", "input", "keyevent", code])
            return OperatorOutcome(True, f"{'Forward' if code == '90' else 'Back'} about {presses * 10} s on the phone.",
                                   evidence={"verified": None})
        return self.key({"toggle": "play_pause"}.get(op, op))

    def media_state(self) -> OperatorOutcome:
        bad = self._gate(needs_unlocked=False)
        if bad:
            return bad
        _, out, _ = self.adb.run(["shell", "dumpsys", "media_session"])
        title = re.search(r"description=([^,\n]+)", out or "")
        state = re.search(r"state=PlaybackState \{state=(\d+)", out or "")
        playing = state and state.group(1) == "3"
        if not title:
            return OperatorOutcome(True, "Nothing is playing on the phone.", evidence={"playing": False})
        return OperatorOutcome(True, f"{'Playing' if playing else 'Paused'} on the phone: {title.group(1).strip()}.",
                               evidence={"playing": bool(playing), "untrusted": True})

    def current_app(self) -> OperatorOutcome:
        bad = self._gate(needs_unlocked=False)
        if bad:
            return bad
        _, out, _ = self.adb.run(["shell", "dumpsys", "window"])
        m = re.search(r"mCurrentFocus=Window\{[^ ]+ [^ ]+ ([\w.]+)/", out or "")
        if not m:
            return OperatorOutcome(False, "I can't tell which app is in front on the phone.")
        pkg = m.group(1)
        name = next((k for k, v in APPS.items() if v == pkg), pkg)
        return OperatorOutcome(True, f"{name} is open on the phone.", evidence={"package": pkg})

    def relaunch(self, app: str) -> OperatorOutcome:
        out = self.close_app(app)
        if not out.ok:
            return out
        return self.open_app(app)

    def installed(self, app: str) -> OperatorOutcome:
        bad = self._gate(needs_unlocked=False)
        if bad:
            return bad
        pkg = APPS.get(app.lower().strip(), "")
        _, out, _ = self.adb.run(["shell", "pm", "list", "packages"])
        have = {l.split(":", 1)[1] for l in (out or "").splitlines() if ":" in l}
        hit = pkg if pkg in have else self._find_package(app)
        return OperatorOutcome(True, f"Yes, {app} is installed on the phone." if hit else f"No, {app} isn't installed on the phone.",
                               evidence={"package": hit or ""})

    def ui_tree(self) -> OperatorOutcome:
        bad = self._gate()
        if bad:
            return bad
        controls = self.adapter().snapshot()
        names = [f"{canonical(c.role)}: {c.name}" for c in controls if c.name][:40]
        return OperatorOutcome(bool(names), "\n".join(names) or "No labelled controls on the phone screen.",
                               evidence={"count": len(controls), "untrusted": True})

    def read_screen(self) -> OperatorOutcome:
        bad = self._gate()
        if bad:
            return bad
        lines = []
        for n in _parse_nodes(self.ui_xml()):
            t = (n.get("text") or n.get("content-desc") or "").strip()
            if t and t not in lines and n.get("password") != "true":
                lines.append(t)
        return OperatorOutcome(bool(lines), "\n".join(lines[:80]) or "Nothing readable on the phone screen.",
                               evidence={"untrusted": True, "lines": len(lines)})

    def find(self, target: str) -> OperatorOutcome:
        bad = self._gate()
        if bad:
            return bad
        return self.ui.find(self.adapter(), target)

    def focus(self, target: str) -> OperatorOutcome:
        bad = self._gate()
        if bad:
            return bad
        ad = self.adapter()
        found = self.ui.find(ad, UITarget.parse(target or "text field"))
        if not found.ok:
            return found
        ok = ad.focus(found.resource)
        return OperatorOutcome(ok, f"Focused {found.resource.name or 'the field'}." if ok else "It didn't take focus.",
                               resource=found.resource)

    def clear(self, target: str = "") -> OperatorOutcome:
        bad = self._gate()
        if bad:
            return bad
        ad = self.adapter()
        found = self.ui.find(ad, UITarget.parse(target or "text field"))
        if not found.ok:
            return found
        if (found.resource.metadata or {}).get("password"):
            return OperatorOutcome(False, "That's a password field - clear it yourself.", needs="user")
        ad.focus(found.resource)
        self.adb.run(["shell", "input", "keyevent", "123"])           # MOVE_END
        n = len(found.resource.name or "") + 50
        for _ in range(min(n, 300) // 50 + 1):
            self.adb.run(["shell", "input", "keyevent"] + ["67"] * 50)  # DEL x50 per call
        return OperatorOutcome(True, f"Cleared {found.resource.name or 'the field'}.", evidence={"verified": None})

    def swipe(self, direction: str = "up") -> OperatorOutcome:
        bad = self._gate()
        if bad:
            return bad
        coords = {"up": (540, 1500, 540, 500), "down": (540, 500, 540, 1500), "left": (900, 1000, 150, 1000),
                  "right": (150, 1000, 900, 1000)}.get(direction)
        if not coords:
            return OperatorOutcome(False, f"Swipe which way? ({direction})", needs="clarify")
        self.adb.run(["shell", "input", "swipe", *map(str, coords), "300"])
        return OperatorOutcome(True, f"Swiped {direction} on the phone.", evidence={"verified": None})

    def notifications_filtered(self, app: str = "", sender: str = "") -> OperatorOutcome:
        out = self.notifications()
        if not out.ok or not (app or sender):
            return out
        lines = [l for l in out.message.splitlines() if (not app or app.lower() in l.lower())
                 and (not sender or sender.lower() in l.lower())]
        return OperatorOutcome(True, "\n".join(lines) or f"No {app or sender} notifications.", evidence={"untrusted": True})

    def open_notification(self, app: str = "") -> OperatorOutcome:
        """Opens the app that posted it (ADB can't press another app's notification without UI automation of the shade)."""
        if not app:
            return OperatorOutcome(False, "Which notification - which app is it from?", needs="clarify")
        return self.open_app(app)

    def dismiss_notification(self, app: str = "") -> OperatorOutcome:
        bad = self._gate()
        if bad:
            return bad
        self.adb.run(["shell", "cmd", "statusbar", "expand-notifications"])
        ad = self.adapter()
        target = UITarget(name="clear all" if not app else "dismiss")
        found = self.ui.find(ad, target)
        if not found.ok:
            return OperatorOutcome(False, "I can't find a dismiss control in the notification shade - swipe it away "
                                          "yourself.", needs="user")
        if not app and not re.search(r"clear all", found.resource.name, re.I):
            return OperatorOutcome(False, "Which notification?", needs="clarify")
        ok = ad.invoke(found.resource)
        return OperatorOutcome(ok, "Dismissed." if ok else "It didn't dismiss.", evidence={"verified": None})

    def status(self, what: str = "battery") -> OperatorOutcome:
        bad = self._gate(needs_unlocked=False)
        if bad:
            return bad
        if what in ("memory", "ram"):
            _, out, _ = self.adb.run(["shell", "cat", "/proc/meminfo"])
            tot = re.search(r"MemTotal:\s+(\d+)", out or "")
            av = re.search(r"MemAvailable:\s+(\d+)", out or "")
            if not (tot and av):
                return OperatorOutcome(False, "I couldn't read the phone's memory.")
            t, a = int(tot.group(1)) / 1024 ** 2, int(av.group(1)) / 1024 ** 2
            return OperatorOutcome(True, f"The phone is using {t - a:.1f} of {t:.1f} GB RAM ({a:.1f} GB free).")
        if what in ("network", "online", "internet"):
            code, _, _ = self.adb.run(["shell", "ping", "-c", "1", "-W", "2", "8.8.8.8"], timeout=6)
            return OperatorOutcome(True, "The phone is online." if code == 0 else "The phone looks offline.",
                                   evidence={"online": code == 0})
        return self.dev({"storage": "storage", "battery": "battery"}.get(what, "battery"))

    def pull(self, kind: str = "screenshot", when: str = "latest", dest: str = "") -> OperatorOutcome:
        bad = self._gate(needs_unlocked=False)
        if bad:
            return bad
        from jarvis.connectors.android.scrcpy import PHONE_MEDIA
        folders, exts = PHONE_MEDIA.get(kind, PHONE_MEDIA["screenshot"])
        files: list[tuple[str, str]] = []
        for f in folders:
            _, out, _ = self.adb.run(["shell", "ls", "-t", "-l", f])
            for line in (out or "").splitlines():
                parts = line.split()
                if len(parts) >= 8 and (not exts or parts[-1].lower().endswith(exts)):
                    files.append((f"{f}/{parts[-1]}", parts[-3]))
        if not files:
            return OperatorOutcome(False, f"No {kind}s on the phone.")
        today = time.strftime("%Y-%m-%d")
        pick = [p for p, d in files if d == today] if when == "today" else [files[0][0]]
        if not pick:
            return OperatorOutcome(False, f"No {kind}s from today on the phone.")
        from pathlib import Path
        out_dir = Path(dest) if dest else Path.home() / "Downloads" / "Phone"
        out_dir.mkdir(parents=True, exist_ok=True)
        got = []
        for remote in pick[:50]:
            local = out_dir / remote.rsplit("/", 1)[-1]
            code, _, _ = self.adb.run(["pull", remote, str(local)], timeout=120)
            if code == 0 and local.exists():
                got.append(str(local))
        if not got:
            return OperatorOutcome(False, "The transfer from the phone failed.")
        ref = ScreenshotResourceRef(resource_id=f"shot:{got[0]}", path=got[0], source_window="phone", source_app="android",
                                    capture_time=time.time()) if kind == "screenshot" else None
        if ref is not None:
            self.resources.record(ref)
        return OperatorOutcome(True, f"Copied {len(got)} file{'s' if len(got) != 1 else ''} from the phone to {out_dir}.",
                               resource=ref, evidence={"files": got, "verified": True})

    def open_url(self, url: str) -> OperatorOutcome:
        return self.dev("open_url", url)

    def record(self, action: str = "start", seconds: int = 180) -> OperatorOutcome:
        """screenrecord on the phone (owner's own device); stopping pulls the video to the PC."""
        bad = self._gate(needs_unlocked=False)
        if bad:
            return bad
        remote = "/sdcard/Movies/jarvis_record.mp4"
        if action == "start":
            if getattr(self, "_rec", None) is not None and self._rec.poll() is None:
                return OperatorOutcome(True, "Already recording the phone screen.")
            argv = [self.adb.bin] + (["-s", self.adb.serial] if self.adb.serial else []) + \
                ["shell", "screenrecord", "--time-limit", str(min(int(seconds), 180)), remote]
            try:
                self._rec = subprocess.Popen(argv, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except Exception as e:
                return OperatorOutcome(False, f"Recording didn't start ({e}).")
            return OperatorOutcome(True, f"Recording the phone screen (up to {min(int(seconds), 180)} s). Say 'stop recording'.")
        rec = getattr(self, "_rec", None)
        if rec is None:
            return OperatorOutcome(False, "The phone screen isn't being recorded.")
        rec.terminate()
        self._rec = None
        from pathlib import Path
        local = Path.home() / "Videos" / f"phone-{time.strftime('%Y%m%d-%H%M%S')}.mp4"
        local.parent.mkdir(parents=True, exist_ok=True)
        time.sleep(0)                                      # screenrecord finalises on SIGINT; pull reads the file
        code, _, _ = self.adb.run(["pull", remote, str(local)], timeout=120)
        ok = code == 0 and local.exists()
        return OperatorOutcome(ok, f"Saved the phone recording to {local}." if ok else "The recording didn't come through.",
                               evidence={"path": str(local)})

    def app_logs(self, app: str, lines: int = 200) -> OperatorOutcome:
        bad = self._gate(needs_unlocked=False)
        if bad:
            return bad
        pkg = APPS.get(app.lower(), app) if app else ""
        if pkg and not _PKG.match(pkg):
            pkg = self._find_package(app)
        if not pkg:
            return self.dev("logcat", str(lines))
        _, pid, _ = self.adb.run(["shell", "pidof", pkg])
        if not (pid or "").strip():
            return OperatorOutcome(False, f"{app} isn't running on the phone, so it has no live logs.")
        _, out, _ = self.adb.run(["logcat", "-d", "-t", str(min(lines, 2000)), f"--pid={pid.split()[0]}"], timeout=10)
        return OperatorOutcome(True, (out or "")[-8000:] or "No log lines yet.", evidence={"untrusted": True, "package": pkg})

    for fn in (recents, previous_app, settings, volume, media, media_state, current_app, relaunch, installed, ui_tree,
               read_screen, find, focus, clear, swipe, notifications_filtered, open_notification, dismiss_notification,
               status, pull, open_url, record, app_logs):
        setattr(DeviceOperator, fn.__name__, fn)


def canonical(role: str) -> str:
    from jarvis.core.operator.ui import canonical_role
    return canonical_role(role)


_device_extras()

_dev: Optional[DeviceOperator] = None


def get_device_operator() -> DeviceOperator:
    global _dev
    if _dev is None:
        _dev = DeviceOperator()
    return _dev


def set_device_operator(d: Optional[DeviceOperator]) -> None:
    global _dev
    _dev = d
