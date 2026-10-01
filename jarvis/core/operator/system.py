"""system.* primitives: what the PC and JARVIS itself are doing right now - read-only except unloading a local model.

Every answer is measured (psutil, Ollama's own /api/ps, the tool registry, the task-scope history), never guessed,
and never looked up on the web. Switching the Windows default audio device has no supported public API, so that
request opens Sound settings and says so instead of pretending.
"""
from __future__ import annotations

import logging
import os
import platform
import time
from typing import Optional

from jarvis.core.operator.refs import OperatorOutcome

logger = logging.getLogger("jarvis.operator.system")


def _gb(n: float) -> str:
    return f"{n / 1024 ** 3:.1f} GB"


class SystemOperator:
    def __init__(self, llm=None, registry=None):
        self._llm = llm
        self.registry = registry

    @property
    def llm(self):
        if self._llm is None:
            from jarvis.core.llm.client import get_llm
            self._llm = get_llm()
        return self._llm

    # -- status ----------------------------------------------------------------------------------------------
    def status(self, what: str = "all") -> OperatorOutcome:
        import psutil
        what = (what or "all").lower()
        parts, ev = [], {}
        if what in ("all", "cpu", "load"):
            cpu = psutil.cpu_percent(interval=0.3)
            ev["cpu"] = cpu
            parts.append(f"CPU {cpu:.0f}%")
        if what in ("all", "ram", "memory"):
            vm = psutil.virtual_memory()
            ev["ram"] = vm.percent
            parts.append(f"RAM {vm.percent:.0f}% ({_gb(vm.used)} of {_gb(vm.total)})")
        if what in ("all", "disk", "storage"):
            root = os.environ.get("SystemDrive", "C:") + "\\" if os.name == "nt" else "/"
            du = psutil.disk_usage(root)
            ev["disk"] = du.percent
            parts.append(f"disk {root} {du.percent:.0f}% used, {_gb(du.free)} free")
        if what in ("all", "uptime", "boot"):
            up = time.time() - psutil.boot_time()
            ev["uptime_s"] = int(up)
            parts.append(f"up {int(up // 3600)} h {int(up % 3600 // 60)} min")
        if what in ("all", "network", "internet", "wifi"):
            stats = {n: s for n, s in psutil.net_if_stats().items() if s.isup and not n.lower().startswith(("lo", "loopback"))}
            ev["interfaces"] = sorted(stats)
            parts.append(f"network up on {', '.join(sorted(stats)[:3])}" if stats else "no network interface is up")
        if what in ("all", "gpu"):
            gpu = self._gpu()
            if gpu:
                ev["gpu"] = gpu
                parts.append(gpu)
            elif what == "gpu":
                parts.append("I can't read GPU usage on this PC (no NVIDIA tools found)")
        if what in ("all", "battery"):
            b = getattr(psutil, "sensors_battery", lambda: None)()
            if b is not None:
                ev["battery"] = b.percent
                parts.append(f"battery {b.percent:.0f}%{' charging' if b.power_plugged else ''}")
        if not parts:
            return OperatorOutcome(False, f"I can report cpu, ram, disk, gpu, network, uptime or battery - not '{what}'.",
                                   needs="clarify")
        return OperatorOutcome(True, "; ".join(parts) + ".", evidence=ev)

    @staticmethod
    def _gpu() -> str:
        import shutil
        import subprocess
        exe = shutil.which("nvidia-smi")
        if not exe:
            return ""
        try:
            out = subprocess.run([exe, "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                                  "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=4).stdout
            name, util, used, total = [x.strip() for x in out.splitlines()[0].split(",")]
            return f"{name} {util}% busy, {used}/{total} MiB VRAM"
        except Exception:
            return ""

    # -- local models ------------------------------------------------------------------------------------------
    def models(self, op: str = "list", model: str = "") -> OperatorOutcome:
        llm = self.llm
        try:
            client = llm._client_sync()
            if op in ("loaded", "running", "ps"):
                data = client.get("/api/ps", timeout=5).json()
                names = [m.get("name", "") for m in data.get("models", [])]
                return OperatorOutcome(True, ("Loaded now: " + ", ".join(names)) if names else "No model is loaded right now.",
                                       evidence={"loaded": names})
            if op == "unload":
                data = client.get("/api/ps", timeout=5).json()
                loaded = [m.get("name", "") for m in data.get("models", [])]
                targets = [m for m in loaded if not model or model.lower() in m.lower()]
                if not targets:
                    return OperatorOutcome(True, f"{model or 'No model'} isn't loaded.")
                for m in targets:
                    client.post("/api/generate", json={"model": m, "keep_alive": 0}, timeout=10)
                still = [m.get("name", "") for m in client.get("/api/ps", timeout=5).json().get("models", [])]
                gone = [m for m in targets if m not in still]
                return OperatorOutcome(bool(gone), f"Unloaded {', '.join(gone)}." if gone else "They are still loaded.",
                                       evidence={"verified": bool(gone), "unloaded": gone})
            if op == "warm":
                role_model = llm.settings.model_for(model or "chat") or model
                if not role_model:
                    return OperatorOutcome(False, "Which model should I warm up?", needs="clarify")
                client.post("/api/generate", json={"model": role_model, "keep_alive": llm.settings.keep_alive}, timeout=60)
                return OperatorOutcome(True, f"{role_model} is loaded and ready.")
            names = llm.list_models_sync(refresh=True)
            roles = {r: llm.settings.model_for(r) for r in ("fast", "planner", "chat", "vision", "embed")}
            used = "; ".join(f"{r}: {m}" for r, m in roles.items() if m)
            return OperatorOutcome(True, f"{len(names)} local models: {', '.join(names[:12])}. In use - {used}.",
                                   evidence={"models": names, "roles": roles})
        except Exception as e:
            return OperatorOutcome(False, f"Ollama isn't answering ({e}).")

    # -- audio devices -----------------------------------------------------------------------------------------
    def audio(self, op: str = "list", device: str = "") -> OperatorOutcome:
        names = self._audio_devices()
        if op == "list":
            if names is None:
                return OperatorOutcome(False, "I can't list audio devices on this system.")
            return OperatorOutcome(True, "Audio devices: " + (", ".join(names) or "none found") + ".",
                                   evidence={"devices": names})
        match = [n for n in (names or []) if device and device.lower() in n.lower()]
        if names is not None and device and not match:
            return OperatorOutcome(False, f"I don't see '{device}' - is it connected and paired?")
        if os.name == "nt":
            os.startfile("ms-settings:sound")  # type: ignore[attr-defined]
        return OperatorOutcome(False, f"Windows has no supported way for me to switch the output device, so I opened "
                                      f"Sound settings - pick {match[0] if match else device or 'it'} there.",
                               needs="user", evidence={"devices": names or []})

    @staticmethod
    def _audio_devices() -> Optional[list[str]]:
        if os.name != "nt":
            return None
        try:
            import win32com.client  # type: ignore
            wmi = win32com.client.GetObject("winmgmts:")
            return sorted({d.Name for d in wmi.InstancesOf("Win32_SoundDevice")})
        except Exception:
            return None

    # -- apps and processes ------------------------------------------------------------------------------------
    @staticmethod
    def _procs(name: str) -> list:
        """Processes whose executable matches the app name ('android studio' -> studio64.exe via its words)."""
        import psutil
        words = [w for w in (name or "").lower().replace(".exe", "").split() if len(w) >= 3]
        out = []
        for p in psutil.process_iter(["name", "create_time", "memory_info"]):
            n = (p.info.get("name") or "").lower()
            if words and any(w in n for w in words):
                out.append(p)
        return out

    def running(self, app: str, tracker=None) -> OperatorOutcome:
        win = None
        if tracker is not None:
            found = tracker.resolve(query=app)
            win = found.resource if found.ok else None
        procs = self._procs(app)
        if not procs and win is None:
            return OperatorOutcome(True, f"No, {app} isn't running.", evidence={"running": False})
        started = min((p.info.get("create_time") or time.time()) for p in procs) if procs else None
        mins = int((time.time() - started) // 60) if started else None
        mem = sum(getattr(p.info.get("memory_info"), "rss", 0) for p in procs)
        since = f" for {mins // 60} h {mins % 60} min" if mins and mins >= 60 else f" for {mins} min" if mins is not None else ""
        return OperatorOutcome(True, f"Yes, {app} is running{since}" + (f", using {_gb(mem)} of memory" if mem else "") + ".",
                               evidence={"running": True, "processes": len(procs), "window": bool(win)})

    def restart_app(self, app: str, tracker=None, launch=None) -> OperatorOutcome:
        """Close the app's window the normal way (it can still ask to save), wait until it is gone, open it again,
        and confirm a new window appeared. Never force-kills."""
        if tracker is None or launch is None:
            return OperatorOutcome(False, "I can't restart apps from here.")
        found = tracker.resolve(query=app)
        if not found.ok:
            if launch(app):
                return OperatorOutcome(True, f"{app} wasn't open, so I just started it.", evidence={"verified": None})
            return OperatorOutcome(False, f"{app} isn't open and I couldn't start it.")
        closed = tracker.close(found.resource)
        if not closed.ok:
            return OperatorOutcome(False, f"{app} is asking something before it closes - answer it and say 'open {app}'.",
                                   needs="user")
        if not launch(app):
            return OperatorOutcome(False, f"I closed {app} but couldn't start it again.")
        d = tracker.desktop
        back = d.wait_until(lambda: tracker.resolve(query=app).ok, timeout=10.0, interval=0.3)
        return OperatorOutcome(back, f"Restarted {app}." if back else f"I reopened {app}; its window hasn't appeared yet.",
                               evidence={"verified": back})

    # -- theme ---------------------------------------------------------------------------------------------------
    _THEME_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"

    def theme(self, mode: str) -> OperatorOutcome:
        """Windows light/dark mode for apps and the system (HKCU only, no admin), read back to verify."""
        mode = (mode or "").lower()
        if mode not in ("dark", "light", "toggle"):
            return OperatorOutcome(False, "Dark or light?", needs="clarify")
        if os.name != "nt":
            return OperatorOutcome(False, "Changing the theme only works on Windows.")
        import winreg  # type: ignore
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._THEME_KEY, 0, winreg.KEY_READ | winreg.KEY_WRITE) as k:
            if mode == "toggle":
                cur, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
                mode = "dark" if cur else "light"
            val = 0 if mode == "dark" else 1
            for name in ("AppsUseLightTheme", "SystemUsesLightTheme"):
                winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, val)
            got, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
        ok = got == val
        return OperatorOutcome(ok, f"Switched to {mode} mode." if ok else "Windows didn't take the theme change.",
                               evidence={"verified": ok, "mode": mode})

    # -- capability audit --------------------------------------------------------------------------------------
    def audit(self) -> OperatorOutcome:
        from jarvis.core.tasks.scope import get_scope_manager
        tools = []
        if self.registry is not None:
            try:
                tools = [t.definition for t in self.registry.list()]
            except Exception:
                tools = []
        risky = sorted(d.name for d in tools if str(d.risk) != "READ_ONLY")
        sm = get_scope_manager()
        active = sm.active()
        recent = sm.recent(5)
        lines = [f"{len(tools)} tools registered ({len(risky)} can change something)." if tools else
                 "I couldn't read the tool registry.",
                 f"{len(active)} task grant{'s' if len(active) != 1 else ''} active right now" +
                 (": " + "; ".join(f"{g.task_id[:8]} -> {', '.join(sorted(g.tools)) or 'nothing'}" for g in active)
                  if active else "."),
                 "Recent grants (revoked): " + ("; ".join(f"{', '.join(sorted(set(g.used))) or 'nothing used'}"
                                                         f"{' (denied ' + ', '.join(g.denied) + ')' if g.denied else ''}"
                                                         for g in recent) or "none") + ".",
                 f"Model runtime: Ollama only, on {platform.node() or 'this PC'}."]
        return OperatorOutcome(True, " ".join(lines), evidence={"tools": len(tools), "active_grants": len(active)})
