from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from jarvis.connectors.base import BaseConnector, Capability, ConnectorInfo, ConnectorStatus

logger = logging.getLogger("jarvis.connectors.android")

COMMON_PACKAGE_MAP = {
    "spotify": "com.spotify.music",
    "whatsapp": "com.whatsapp",
    "chrome": "com.android.chrome",
    "youtube": "com.google.android.youtube",
    "maps": "com.google.android.apps.maps",
    "settings": "com.android.settings",
    "camera": "com.android.camera",
    "messages": "com.google.android.apps.messaging",
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

        if action == "open_app":
            app_raw = arguments.get("app", arguments.get("name", arguments.get("app_name", ""))).strip().casefold()
            pkg = COMMON_PACKAGE_MAP.get(app_raw, app_raw)

            if not pkg or not all(c.isalnum() or c in "._" for c in pkg):
                raise ValueError(f"Invalid Android package name: {pkg}")
            code, _, err = self._run_adb(["shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"])
            if code != 0:
                raise RuntimeError(f"Failed to launch app '{pkg}' on Android: {err}")
            return {"status": "SUCCESS", "message": f"App '{app_raw}' ({pkg}) opened on phone."}

        if action_name == "android.capture_state":
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

        raise NotImplementedError(f"Action '{action_name}' not implemented")

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
