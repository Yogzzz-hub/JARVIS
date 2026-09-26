from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from jarvis.connectors.base import BaseConnector, Capability, ConnectorInfo, ConnectorStatus

logger = logging.getLogger("jarvis.connectors.android")

ANDROID_KEYCODES = {
    "home": 3, "back": 4, "call": 5, "end_call": 6, "volume_up": 24, "volume_down": 25, "power": 26,
    "camera": 27, "enter": 66, "delete": 67, "menu": 82, "search": 84, "media_play_pause": 85,
    "media_next": 87, "media_previous": 88, "volume_mute": 164, "app_switch": 187, "brightness_down": 220,
    "brightness_up": 221, "sleep": 223, "wakeup": 224, "notifications": 83,
}

COMMON_PACKAGE_MAP = {
    "spotify": "com.spotify.music",
    "whatsapp": "com.whatsapp",
    "chrome": "com.android.chrome",
    "youtube": "com.google.android.youtube",
    "maps": "com.google.android.apps.maps",
    "settings": "com.android.settings",
    "camera": "com.android.camera",
    "messages": "com.google.android.apps.messaging",
    "instagram": "com.instagram.android",
    "facebook": "com.facebook.katana",
    "telegram": "org.telegram.messenger",
    "gmail": "com.google.android.gm",
    "photos": "com.google.android.apps.photos",
    "gallery": "com.google.android.apps.photos",
    "calendar": "com.google.android.calendar",
    "clock": "com.google.android.deskclock",
    "calculator": "com.google.android.calculator",
    "phone": "com.google.android.dialer",
    "dialer": "com.google.android.dialer",
    "contacts": "com.google.android.contacts",
    "play store": "com.android.vending",
    "playstore": "com.android.vending",
    "files": "com.google.android.apps.nbu.files",
    "netflix": "com.netflix.mediaclient",
    "amazon": "in.amazon.mShop.android.shopping",
    "paytm": "net.one97.paytm",
    "phonepe": "com.phonepe.app",
    "gpay": "com.google.android.apps.nbu.paisa.user",
    "google pay": "com.google.android.apps.nbu.paisa.user",
    "twitter": "com.twitter.android",
    "x": "com.twitter.android",
    "snapchat": "com.snapchat.android",
    "linkedin": "com.linkedin.android",
    "zoom": "us.zoom.videomeetings",
    "teams": "com.microsoft.teams",
    "outlook": "com.microsoft.office.outlook",
}


class AndroidScrcpyConnector(BaseConnector):
    """Integrates scrcpy and ADB for on-demand Android screen viewing and typed control.
    Strictly forbids arbitrary shell execution. All mutations pass Phase 5 policy.
    """

    def __init__(
        self,
        device_id: Optional[str] = None,
        scrcpy_path: Optional[str] = None,
        adb_path: Optional[str] = None,
        max_size: int = 1024,
        max_fps: int = 30,
        stay_awake: bool = True,
        enabled: bool = True,
    ) -> None:
        super().__init__(
            ConnectorInfo(
                connector_id="android_scrcpy",
                name="Android scrcpy Controller",
                version="1.0.0",
                transport="ADB / USB / TCP",
                network_requirement="Local USB or LAN ADB",
                permission_scope="android:view,android:control",
            )
        )
        self.enabled = enabled
        self.device_id = device_id
        self.scrcpy_bin = scrcpy_path or shutil.which("scrcpy")
        self.adb_bin = adb_path or shutil.which("adb")
        self.max_size = max_size
        self.max_fps = max_fps
        self.stay_awake = stay_awake

        self._scrcpy_proc: Optional[subprocess.Popen] = None
        self._last_state: dict[str, Any] = {}

        if not self.enabled:
            self._status = ConnectorStatus.DISABLED
        elif self.adb_bin:
            self._status = ConnectorStatus.READY
        else:
            self._status = ConnectorStatus.UNAVAILABLE

    def discover_capabilities(self) -> list[Capability]:
        if not self.enabled:
            return []
        caps = [
            Capability(
                name="android.status",
                description="Query connection state, device ID, and battery/model information",
                risk_level="READ_ONLY",
                requires_network=False,
            ),
            Capability(
                name="android.capture_state",
                description="Capture a screen preview of the connected Android device",
                risk_level="READ_ONLY",
                requires_network=False,
            ),
        ]
        if self.scrcpy_bin:
            caps.extend([
                Capability(
                    name="android.open_control",
                    description="Launch scrcpy phone mirroring on the desktop",
                    risk_level="REVERSIBLE",
                    requires_network=False,
                ),
                Capability(
                    name="android.close_control",
                    description="Close active scrcpy screen mirroring window",
                    risk_level="REVERSIBLE",
                    requires_network=False,
                ),
            ])
        if self.adb_bin:
            caps.extend([
                Capability(name="android.key", description="Press a phone key (volume, power, media, home...)", risk_level="REVERSIBLE", requires_network=False),
                Capability(name="android.input", description="Type text, tap or swipe on the phone", risk_level="REVERSIBLE", requires_network=False),
                Capability(name="android.open_url", description="Open a web page on the phone", risk_level="REVERSIBLE", requires_network=False),
                Capability(name="android.dial", description="Open the dialer with a number", risk_level="EXTERNAL_EFFECT", requires_network=False),
                Capability(name="android.list_packages", description="List installed phone apps", risk_level="READ_ONLY", requires_network=False),
                Capability(
                    name="android.open_app",
                    description="Launch a specified app on the phone by package or common name",
                    risk_level="EXTERNAL_EFFECT",
                    requires_network=False,
                ),
                Capability(
                    name="android.back",
                    description="Press the Android Back button",
                    risk_level="REVERSIBLE",
                    requires_network=False,
                ),
                Capability(
                    name="android.home",
                    description="Press the Android Home button",
                    risk_level="REVERSIBLE",
                    requires_network=False,
                ),
            ])
        return caps

    def _run_adb(self, args: list[str], timeout: float = 5.0) -> tuple[int, str, str]:
        if not self.adb_bin:
            return -1, "", "ADB not found"
        cmd = [self.adb_bin]
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        cmd.extend(args)
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", "ADB command timed out"
        except Exception as exc:
            return -1, "", str(exc)

    def get_connected_devices(self) -> list[dict[str, str]]:
        if not self.adb_bin:
            return []
        code, out, _ = self._run_adb(["devices", "-l"], timeout=3.0)
        if code != 0:
            return []
        devices = []
        for line in out.splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                serial = parts[0]
                model = "unknown"
                for p in parts[2:]:
                    if p.startswith("model:"):
                        model = p.split(":", 1)[1]
                devices.append({"serial": serial, "model": model})
        return devices

    def health(self) -> dict[str, Any]:
        if not self.enabled:
            return {"status": ConnectorStatus.DISABLED.value, "message": "Android connector disabled in configuration."}
        if not self.adb_bin:
            return {
                "status": ConnectorStatus.UNAVAILABLE.value,
                "message": "ADB executable not found. Install Android platform-tools to enable phone control.",
            }

        devices = self.get_connected_devices()
        scrcpy_active = self._scrcpy_proc is not None and self._scrcpy_proc.poll() is None

        if not devices:
            self._status = ConnectorStatus.DEGRADED
            return {
                "status": ConnectorStatus.DEGRADED.value,
                "adb_installed": True,
                "scrcpy_installed": bool(self.scrcpy_bin),
                "devices_connected": 0,
                "scrcpy_active": scrcpy_active,
                "message": "ADB ready, but no Android device is currently connected via USB or Wi-Fi.",
            }

        self._status = ConnectorStatus.READY
        return {
            "status": ConnectorStatus.READY.value,
            "adb_installed": True,
            "scrcpy_installed": bool(self.scrcpy_bin),
            "devices_connected": len(devices),
            "primary_device": devices[0]["serial"],
            "model": devices[0]["model"],
            "scrcpy_active": scrcpy_active,
            "message": f"Connected to {devices[0]['model']} ({devices[0]['serial']})",
        }

    def read(self, resource_uri: str, **kwargs: Any) -> Any:
        if resource_uri == "devices":
            return self.get_connected_devices()
        elif resource_uri == "state":
            return dict(self._last_state)
        return None

    def prepare_action(self, action_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if action_name not in [c.name for c in self.discover_capabilities()]:
            raise ValueError(f"Unsupported Android capability: {action_name}")
        return {
            "prepared": True,
            "action": action_name,
            "arguments": arguments,
            "preview": f"Execute {action_name} on connected Android device",
        }

    # Fixed ADB templates for fast phone actions. Every value that reaches the shell is validated first.
    _SETTINGS_PAGES = {
        "main": "android.settings.SETTINGS", "wifi": "android.settings.WIFI_SETTINGS",
        "bluetooth": "android.settings.BLUETOOTH_SETTINGS", "battery": "android.intent.action.POWER_USAGE_SUMMARY",
        "display": "android.settings.DISPLAY_SETTINGS", "sound": "android.settings.SOUND_SETTINGS",
        "location": "android.settings.LOCATION_SOURCE_SETTINGS", "apps": "android.settings.APPLICATION_SETTINGS",
        "storage": "android.settings.INTERNAL_STORAGE_SETTINGS", "hotspot": "android.settings.TETHER_SETTINGS",
        "data_usage": "android.settings.DATA_USAGE_SETTINGS", "security": "android.settings.SECURITY_SETTINGS",
        "developer": "android.settings.APPLICATION_DEVELOPMENT_SETTINGS", "date": "android.settings.DATE_SETTINGS",
    }

    def _quick_action(self, arguments: dict[str, Any]) -> dict[str, Any]:
        what = str(arguments.get("what", "")).lower()
        value = arguments.get("value")

        def ok(msg: str, **extra: Any) -> dict[str, Any]:
            return {"status": "SUCCESS", "success": True, "message": msg, **extra}

        def adb(args: list[str], err_msg: str) -> str:
            code, out, err = self._run_adb(args, timeout=8.0)
            if code != 0:
                raise RuntimeError(f"{err_msg}: {err.strip() or 'the phone refused'}")
            return out

        if what in ("quick_settings", "notifications_panel", "collapse_panels"):
            verb = {"quick_settings": "expand-settings", "notifications_panel": "expand-notifications",
                    "collapse_panels": "collapse"}[what]
            adb(["shell", "cmd", "statusbar", verb], "Couldn't open the panel")
            return ok({"quick_settings": "Opened quick settings on the phone.",
                       "notifications_panel": "Opened the notification shade on the phone.",
                       "collapse_panels": "Closed the phone's panels."}[what])
        if what == "settings":
            page = str(value or "main").lower().replace(" ", "_")
            intent = self._SETTINGS_PAGES.get(page)
            if not intent:
                raise ValueError(f"I don't know the phone's '{page}' settings page")
            adb(["shell", "am", "start", "-a", intent], "Couldn't open settings")
            return ok(f"Opened {page.replace('_', ' ')} settings on the phone.")
        if what == "brightness":
            pct = max(0, min(100, int(value if value is not None else 50)))
            adb(["shell", "settings", "put", "system", "screen_brightness_mode", "0"], "Couldn't change brightness")
            adb(["shell", "settings", "put", "system", "screen_brightness", str(round(pct * 2.55))], "Couldn't change brightness")
            return ok(f"Set the phone's brightness to {pct}%.")
        if what == "media_volume":
            level = max(0, min(15, int(value if value is not None else 7)))
            adb(["shell", "cmd", "media_session", "volume", "--stream", "3", "--set", str(level)], "Couldn't change the volume")
            return ok(f"Set the phone's media volume to {level} of 15.")
        if what == "current_app":
            out = adb(["shell", "dumpsys", "window"], "Couldn't read the current app")
            m = re.search(r"mCurrentFocus=.*?\s([\w.]+)/", out) or re.search(r"mFocusedApp=.*?\s([\w.]+)/", out)
            pkg = m.group(1) if m else ""
            name = next((k for k, v in COMMON_PACKAGE_MAP.items() if v == pkg), pkg.split(".")[-1] if pkg else "unknown")
            return ok(f"The phone is showing {name}." if pkg else "I couldn't tell which app is open.", package=pkg)
        if what == "screen_off":
            adb(["shell", "input", "keyevent", "223"], "Couldn't turn the screen off")
            return ok("Turned the phone's screen off.")
        if what == "screen_on":
            adb(["shell", "input", "keyevent", "224"], "Couldn't wake the phone")
            return ok("Woke the phone's screen.")
        if what == "sms_draft":
            number = re.sub(r"[^\d+]", "", str(arguments.get("number", "")))
            body = str(arguments.get("text", ""))
            if not re.fullmatch(r"\+?\d{6,15}", number):
                raise ValueError("I need a phone number to write the SMS to")
            if not re.fullmatch(r"[\w .,!?@#%&()+:;/='-]{0,300}", body):
                raise ValueError("That message has characters I can't pass to the phone safely")
            args = ["shell", "am", "start", "-a", "android.intent.action.SENDTO", "-d", f"sms:{number}"]
            if body:  # single-quoted for the phone's shell; an apostrophe becomes '\'' (close, escaped quote, reopen)
                args += ["--es", "sms_body", "'" + body.replace("'", "'\\''") + "'"]
            adb(args, "Couldn't open the SMS app")
            return ok(f"The SMS to {number} is ready on your phone - tap send to send it.")
        raise ValueError(f"Unknown phone action: {what}")

    def execute_authorized_action(self, action_id: str, action_name: str, arguments: dict[str, Any]) -> Any:
        t0 = time.perf_counter()
        action = action_name.removeprefix("android.")

        if action == "status":
            h = self.health()
            dur = (time.perf_counter() - t0) * 1000
            return {"status": "SUCCESS", "success": True, "data": h, "duration_ms": dur}

        if action == "open_control":
            if not self.scrcpy_bin:
                raise RuntimeError("scrcpy executable not found. Cannot mirror phone screen.")
            if self._scrcpy_proc and self._scrcpy_proc.poll() is None:
                return {"status": "SUCCESS", "success": True, "message": "scrcpy window is already open.", "pid": self._scrcpy_proc.pid}

            cmd = [self.scrcpy_bin, "--max-size", str(self.max_size), "--max-fps", str(self.max_fps)]
            if self.stay_awake:
                cmd.append("--stay-awake")
            if self.device_id:
                cmd.extend(["-s", self.device_id])

            self._scrcpy_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self._last_state["scrcpy_running"] = True
            dur = (time.perf_counter() - t0) * 1000
            return {
                "status": "SUCCESS",
                "success": True,
                "message": "Phone screen mirroring opened via scrcpy.",
                "pid": self._scrcpy_proc.pid,
                "duration_ms": dur,
            }

        if action == "close_control":
            if self._scrcpy_proc and self._scrcpy_proc.poll() is None:
                self._scrcpy_proc.terminate()
                try:
                    self._scrcpy_proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    self._scrcpy_proc.kill()
                self._scrcpy_proc = None
                self._last_state["scrcpy_running"] = False
                return {"status": "SUCCESS", "success": True, "message": "Phone screen mirroring closed."}
            return {"status": "SUCCESS", "success": True, "message": "Phone screen mirroring was not active."}

        if action == "home":
            code, _, err = self._run_adb(["shell", "input", "keyevent", "3"])
            if code != 0:
                raise RuntimeError(f"Failed to trigger Home on Android: {err}")
            return {"status": "SUCCESS", "success": True, "message": "Home button pressed on phone."}

        if action == "back":
            code, _, err = self._run_adb(["shell", "input", "keyevent", "4"])
            if code != 0:
                raise RuntimeError(f"Failed to trigger Back on Android: {err}")
            return {"status": "SUCCESS", "success": True, "message": "Back button pressed on phone."}

        if action == "key":
            key = str(arguments.get("key", "")).strip().lower().replace(" ", "_")
            code = ANDROID_KEYCODES.get(key)
            if code is None:
                raise ValueError(f"Unsupported phone key: {key}")
            code_run, _, err = self._run_adb(["shell", "input", "keyevent", str(code)])
            if code_run != 0:
                raise RuntimeError(f"Failed to press {key} on Android: {err}")
            return {"status": "SUCCESS", "success": True, "message": f"Pressed {key.replace('_', ' ')} on the phone."}

        if action == "quick":
            return self._quick_action(arguments)

        if action == "input":
            kind = str(arguments.get("action", "")).lower()
            if kind == "text":
                text = str(arguments.get("text", ""))
                if not text:
                    raise ValueError("No text to type")
                # adb 'input text' needs spaces as %s and shell metacharacters escaped.
                escaped = re.sub(r"([\\\"'`$&|;<>(){}\[\]*?!#~])", r"\\\1", text).replace(" ", "%s")
                args = ["shell", "input", "text", escaped]
            elif kind == "tap":
                args = ["shell", "input", "tap", str(int(arguments["x"])), str(int(arguments["y"]))]
            elif kind == "swipe":
                direction = str(arguments.get("direction", "up")).lower()
                x1, y1, x2, y2 = {"up": (540, 1600, 540, 500), "down": (540, 500, 540, 1600),
                                  "left": (900, 1000, 150, 1000), "right": (150, 1000, 900, 1000)}.get(direction, (540, 1600, 540, 500))
                args = ["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), "250"]
            else:
                raise ValueError(f"Unsupported phone input action: {kind}")
            code_run, _, err = self._run_adb(args)
            if code_run != 0:
                raise RuntimeError(f"Phone input failed: {err}")
            return {"status": "SUCCESS", "success": True, "message": f"Phone {kind} done."}

        if action == "open_url":
            url = str(arguments.get("url", "")).strip()
            if not re.match(r"^https?://", url):
                url = "https://" + url
            if not re.match(r"^https?://[^\s'\"]+$", url):
                raise ValueError(f"Invalid URL: {url}")
            code_run, _, err = self._run_adb(["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url])
            if code_run != 0:
                raise RuntimeError(f"Failed to open {url} on the phone: {err}")
            return {"status": "SUCCESS", "success": True, "message": f"Opened {url} on the phone."}

        if action == "dial":
            number = re.sub(r"[^\d+]", "", str(arguments.get("number", "")))
            if len(number) < 3:
                raise ValueError("A phone number is required to dial")
            # DIAL (not CALL): opens the dialer with the number; the user taps call.
            code_run, _, err = self._run_adb(["shell", "am", "start", "-a", "android.intent.action.DIAL", "-d", f"tel:{number}"])
            if code_run != 0:
                raise RuntimeError(f"Failed to open the dialer: {err}")
            return {"status": "SUCCESS", "success": True, "message": f"Dialer opened with {number} on your phone. Tap call to connect."}

        if action == "list_packages":
            code_run, out, err = self._run_adb(["shell", "pm", "list", "packages", "-3"], timeout=8.0)
            if code_run != 0:
                raise RuntimeError(f"Could not list phone apps: {err}")
            return {"status": "SUCCESS", "success": True, "packages": [l.split(":", 1)[1] for l in out.splitlines() if ":" in l]}

        if action == "open_app":
            app_raw = arguments.get("app", arguments.get("name", arguments.get("app_name", ""))).strip().casefold()
            pkg = COMMON_PACKAGE_MAP.get(app_raw) or self._resolve_package(app_raw)

            if not pkg or not all(c.isalnum() or c in "._" for c in pkg):
                raise ValueError(f"Invalid Android package name: {pkg}")
            code, _, err = self._run_adb(["shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"])
            if code != 0:
                raise RuntimeError(f"Failed to launch app '{pkg}' on Android: {err}")
            return {"status": "SUCCESS", "message": f"App '{app_raw}' ({pkg}) opened on phone."}

        if action == "capture_state":
            out_path = Path(arguments.get("destination", "screenshots/android_state.png")).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.adb_bin:
                raise RuntimeError("ADB not available for screen capture")
            cmd = [self.adb_bin]
            if self.device_id:
                cmd.extend(["-s", self.device_id])
            cmd.extend(["exec-out", "screencap", "-p"])
            try:
                res = subprocess.run(cmd, capture_output=True, timeout=5.0)
                if res.returncode == 0 and len(res.stdout) > 100:
                    out_path.write_bytes(res.stdout)
                    return {"status": "SUCCESS", "path": str(out_path), "bytes": len(res.stdout)}
            except Exception as e:
                logger.warning("ADB exec-out screencap failed: %s", e)
            raise RuntimeError("Could not capture Android screen preview.")

        if action == "notifications":
            code_run, out, err = self._run_adb(["shell", "dumpsys", "notification", "--noredact"], timeout=8.0)
            if code_run != 0:
                raise RuntimeError(f"Could not read phone notifications: {err}")
            items = parse_notifications(out)
            return {"status": "SUCCESS", "success": True, "notifications": items[: int(arguments.get("limit", 15))]}

        if action == "tap_text":
            label = str(arguments.get("text", "")).strip()
            if not label:
                raise ValueError("Say what to tap, e.g. 'tap Settings on my phone'")
            code_run, _, err = self._run_adb(["shell", "uiautomator", "dump", "/sdcard/jarvis_ui.xml"], timeout=10.0)
            if code_run != 0:
                raise RuntimeError(f"Could not read the phone screen: {err}")
            code_run, xml, err = self._run_adb(["shell", "cat", "/sdcard/jarvis_ui.xml"], timeout=6.0)
            node = find_ui_node(xml, label) if code_run == 0 else None
            if node is None:
                return {"status": "NOT_FOUND", "success": False, "message": f"I couldn't find '{label}' on the phone screen."}
            x, y, shown = node
            code_run, _, err = self._run_adb(["shell", "input", "tap", str(x), str(y)])
            if code_run != 0:
                raise RuntimeError(f"Tap failed: {err}")
            return {"status": "SUCCESS", "success": True, "message": f"Tapped '{shown}' on the phone.", "x": x, "y": y}

        if action == "toggle":
            setting = str(arguments.get("setting", "")).lower().replace(" ", "_")
            on = bool(arguments.get("on", True))
            commands = {
                "wifi": [["shell", "svc", "wifi", "enable" if on else "disable"]],
                "mobile_data": [["shell", "svc", "data", "enable" if on else "disable"]],
                "bluetooth": [["shell", "cmd", "bluetooth_manager", "enable" if on else "disable"],
                              ["shell", "svc", "bluetooth", "enable" if on else "disable"]],
                "airplane_mode": [["shell", "cmd", "connectivity", "airplane-mode", "enable" if on else "disable"]],
                "do_not_disturb": [["shell", "cmd", "notification", "set_dnd", "priority" if on else "off"]],
                "auto_rotate": [["shell", "settings", "put", "system", "accelerometer_rotation", "1" if on else "0"]],
            }.get(setting)
            if not commands:
                raise ValueError(f"I can't switch '{setting}' on the phone")
            last_err = ""
            for args in commands:
                code_run, _, err = self._run_adb(args, timeout=8.0)
                if code_run == 0 and "Unknown command" not in err and "not found" not in err.lower():
                    pretty = setting.replace("_", " ")
                    return {"status": "SUCCESS", "success": True, "message": f"Turned {'on' if on else 'off'} {pretty} on the phone."}
                last_err = err
            raise RuntimeError(f"The phone refused to change {setting.replace('_', ' ')}: {last_err or 'needs permission'}")

        if action == "pull":
            dest_dir = Path(arguments.get("destination") or (Path.home() / "Downloads" / "From Phone"))
            dest_dir.mkdir(parents=True, exist_ok=True)
            count = max(1, min(20, int(arguments.get("count", 1))))
            name = str(arguments.get("name", "")).strip()
            if name:
                if not re.fullmatch(r"[\w .()+-]{1,80}", name):
                    raise ValueError("That file name has characters I can't search for safely.")
                code_run, out, err = self._run_adb(["shell", "find", "/sdcard", "-type", "f", "-iname", f"*{name}*"], timeout=20.0)
                remote = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("/sdcard/") and "/Android/" not in ln][:count]
            else:
                kind = str(arguments.get("kind", "photo")).lower()
                folders, exts = PHONE_MEDIA.get(kind, PHONE_MEDIA["photo"])
                remote = []
                for folder in folders:
                    code_run, out, _err = self._run_adb(["shell", "ls", "-t", folder], timeout=10.0)
                    if code_run != 0:
                        continue
                    for entry in out.splitlines():
                        entry = entry.strip()
                        if entry and (not exts or entry.lower().endswith(exts)):
                            remote.append(f"{folder.rstrip('/')}/{entry}")
                        if len(remote) >= count:
                            break
                    if len(remote) >= count:
                        break
            if not remote:
                return {"status": "NOT_FOUND", "success": False, "message": "I couldn't find that on the phone."}
            saved = []
            for path in remote:
                local = dest_dir / Path(path).name
                code_run, _out, err = self._run_adb(["pull", path, str(local)], timeout=120.0)
                if code_run == 0:
                    saved.append(str(local))
            if not saved:
                raise RuntimeError(f"Copying from the phone failed: {err}")
            return {"status": "SUCCESS", "success": True, "files": saved, "folder": str(dest_dir),
                    "message": f"Copied {len(saved)} file{'s' if len(saved) != 1 else ''} from your phone to {dest_dir}."}

        if action == "push":
            local = Path(str(arguments.get("path", ""))).expanduser()
            if not local.is_file():
                raise ValueError(f"I can't find the file {local}")
            remote = "/sdcard/Download/" + local.name
            code_run, _out, err = self._run_adb(["push", str(local), remote], timeout=300.0)
            if code_run != 0:
                raise RuntimeError(f"Copying to the phone failed: {err}")
            # make it show up in the phone's gallery / files app right away
            self._run_adb(["shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE", "-d", f"file://{remote}"])
            return {"status": "SUCCESS", "success": True, "remote": remote,
                    "message": f"Copied {local.name} to your phone's Download folder."}

        raise NotImplementedError(f"Action '{action_name}' not implemented")

    def _resolve_package(self, app_name: str) -> str:
        """Map a spoken app name to an installed package (e.g. 'insta' -> com.instagram.android)."""
        if "." in app_name and " " not in app_name:
            return app_name
        try:
            code, out, _ = self._run_adb(["shell", "pm", "list", "packages"], timeout=8.0)
            packages = [l.split(":", 1)[1] for l in out.splitlines() if ":" in l] if code == 0 else []
        except Exception:
            packages = []
        wanted = re.sub(r"[^a-z0-9]", "", app_name)
        best, best_score = "", 0.0
        for pkg in packages:
            parts = [p for p in pkg.lower().split(".") if p not in ("com", "org", "android", "app", "apps", "google", "net", "in", "co")]
            joined = "".join(parts)
            score = 0.0
            if wanted and any(p == wanted for p in parts):
                score = 100.0
            elif wanted and wanted in joined:
                score = 80.0 + len(wanted) / max(len(joined), 1)
            else:
                try:
                    from rapidfuzz import fuzz
                    score = max((fuzz.ratio(wanted, p) for p in parts), default=0.0)
                except ImportError:
                    score = 0.0
            if score > best_score:
                best, best_score = pkg, score
        return best if best_score >= 70.0 else app_name

    def verify(self, action_id: str, action_name: str, expected_state: Any) -> bool:
        if action_name == "android.open_control":
            return self._scrcpy_proc is not None and self._scrcpy_proc.poll() is None
        if action_name == "android.close_control":
            return self._scrcpy_proc is None or self._scrcpy_proc.poll() is not None
        return True

    def disconnect(self) -> None:
        if self._scrcpy_proc and self._scrcpy_proc.poll() is None:
            self._scrcpy_proc.terminate()
            self._scrcpy_proc = None
        self._status = ConnectorStatus.UNAVAILABLE


def parse_notifications(dumpsys: str) -> list[dict[str, str]]:
    """Title / text / app of active notifications from `dumpsys notification --noredact`."""
    items: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in dumpsys.splitlines():
        line = raw.strip()
        m = re.match(r"NotificationRecord\(0x[0-9a-f]+: pkg=([\w.]+)", line)
        if m:
            if current and (current.get("title") or current.get("text")):
                items.append(current)
            current = {"app": m.group(1), "title": "", "text": ""}
            continue
        if current is None:
            continue
        m = re.match(r"android\.(title|text|bigText)=\w+ \((.*)\)$", line)
        if m and m.group(2) and m.group(2) != "null":
            key = "text" if m.group(1) == "bigText" else m.group(1)
            if key == "text" and current.get("text") and m.group(1) != "bigText":
                continue
            current[key] = m.group(2)[:300]
    if current and (current.get("title") or current.get("text")):
        items.append(current)
    seen, unique = set(), []
    for it in items:
        key = (it["app"], it["title"], it["text"])
        if key not in seen and it["app"] not in ("android", "com.android.systemui"):
            seen.add(key)
            unique.append(it)
    return unique


def find_ui_node(xml: str, label: str) -> tuple[int, int, str] | None:
    """Centre of the on-screen element whose text / description best matches ``label``."""
    import difflib

    want = label.casefold().strip()
    best: tuple[float, int, int, str] | None = None
    for m in re.finditer(r"<node\b[^>]*>", xml or ""):
        tag = m.group(0)
        text = re.search(r'\btext="([^"]*)"', tag)
        desc = re.search(r'\bcontent-desc="([^"]*)"', tag)
        bounds = re.search(r'\bbounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', tag)
        if not bounds:
            continue
        for shown in ((text.group(1) if text else ""), (desc.group(1) if desc else "")):
            have = shown.casefold().strip()
            if not have:
                continue
            if have == want:
                score = 1.0
            elif want in have or have in want:
                score = 0.85 - abs(len(have) - len(want)) / 200
            else:
                score = difflib.SequenceMatcher(None, have, want).ratio() * 0.8
            if score >= 0.6 and (best is None or score > best[0]):
                x1, y1, x2, y2 = map(int, bounds.groups())
                best = (score, (x1 + x2) // 2, (y1 + y2) // 2, shown)
    return (best[1], best[2], best[3]) if best else None


# kind -> (phone folders, newest first; accepted extensions)
PHONE_MEDIA: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "photo": (("/sdcard/DCIM/Camera", "/sdcard/Pictures"), (".jpg", ".jpeg", ".png", ".heic", ".webp")),
    "screenshot": (("/sdcard/Pictures/Screenshots", "/sdcard/DCIM/Screenshots"), (".png", ".jpg", ".jpeg")),
    "video": (("/sdcard/DCIM/Camera", "/sdcard/Movies"), (".mp4", ".mkv", ".3gp", ".webm", ".mov")),
    "download": (("/sdcard/Download",), ()),
    "document": (("/sdcard/Download", "/sdcard/Documents"), (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt")),
    "recording": (("/sdcard/Recordings", "/sdcard/Music/Recordings", "/sdcard/Recordings/Call"), (".m4a", ".mp3", ".aac", ".wav", ".amr", ".ogg")),
    "whatsapp_media": (("/sdcard/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Images",
                        "/sdcard/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Documents"), ()),
}
