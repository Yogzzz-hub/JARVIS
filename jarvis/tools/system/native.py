from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import platform
import shutil
import subprocess
import uuid
import psutil
from pydantic import ConfigDict, Field
from jarvis.config import ROOT
from jarvis.tools.base import Contract, RiskLevel, Tool, ToolDefinition

class Empty(Contract):
    pass


class AppInput(Contract):
    name: str = Field(min_length=1, max_length=256)
class AppOutput(Contract):
    name: str
    target: str
    pid: int | None
    process_names: tuple[str, ...]
    associated: bool = False
class DirectoryInput(Contract):
    path: str = Field(min_length=1, max_length=4096)
    limit: int = Field(default=100, ge=1, le=1000)
class DirectoryOutput(Contract):
    path: str
    entries: list[str]
    truncated: bool
class TimeOutput(Contract):
    iso: str
    date: str = ""
    time: str = ""
    formatted: str = ""
class InfoOutput(Contract):
    os: str
    python: str
    cpu: str
    ram_total_mb: float
    ram_used_mb: float
    gpu_name: str | None
    gpu_vram_mb: float | None
class VolumeInput(Contract):
    percent: int = Field(ge=0, le=100)
class VolumeOutput(Contract):
    percent: float = Field(ge=0, le=100)
class BrightnessInput(Contract):
    percent: int = Field(ge=0, le=100)
class BrightnessOutput(Contract):
    percent: float = Field(ge=0, le=100)
class TopProcessItem(Contract):
    name: str
    memory_mb: float
    formatted: str
class TopProcessesOutput(Contract):
    processes: list[TopProcessItem]
    total_ram_gb: float
    used_ram_gb: float
    free_ram_gb: float
class ScreenshotInput(Contract):
    path: str | None = None
class ScreenshotOutput(Contract):
    path: str
    bytes: int = Field(gt=0)
class VoiceInput(Contract):
    gender: str = Field(min_length=1, max_length=64)
class VoiceOutput(Contract):
    gender: str
    status: str
class DashboardOutput(Contract):
    status: str
    message: str
class CloseAppOutput(Contract):
    name: str
    closed: bool
    count: int = 0

def _attach_interactive_desktop():
    """Attach current thread to the user's visible desktop so launched apps appear on screen."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)  # GENERIC_ALL
        if hdesk:
            user32.SetThreadDesktop(hdesk)
            return True
    except Exception:
        pass
    return False


def bring_to_front(process_names: tuple[str, ...] | list[str] = (), name: str = "") -> bool:
    """Find visible or minimized real top-level window belonging to process_names/name and bring it to foreground."""
    if os.name != "nt":
        return False
    try:
        import win32gui, win32con, win32process, win32api, ctypes
        user32 = ctypes.windll.user32
        hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if hdesk:
            user32.SetThreadDesktop(hdesk)

        names = {p.casefold() for p in process_names} if process_names else set()
        if name:
            names.add(name.casefold())
            names.add(f"{name.casefold()}.exe")

        matching_hwnds = []

        def enum_cb(h, _):
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
            if not pid.value:
                return True
            try:
                p = psutil.Process(pid.value)
                pname = p.name().casefold()
            except Exception:
                return True

            if pname not in names and not any(n in pname for n in names):
                return True

            is_iconic = bool(user32.IsIconic(h))
            # Exclude tiny/zero-sized internal hooks and widgets (unless minimized window)
            rect = (ctypes.c_long * 4)()
            user32.GetWindowRect(h, ctypes.byref(rect))
            w = rect[2] - rect[0]
            h_sz = rect[3] - rect[1]
            if (w < 100 or h_sz < 100) and not is_iconic:
                return True

            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(h, cls, 256)
            cname = cls.value

            if cname in (
                "MSCTFIME UI", "IME", "crashpad_SessionEndWatcher",
                "Microsoft.UI.Content.PopupWindowSiteBridge",
                "Base_PowerMessageWindow", "Chrome_StatusTrayWindow",
            ):
                return True

            length = user32.GetWindowTextLengthW(h)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(h, buf, length + 1)
            wtitle = buf.value.strip()

            if pname == "explorer.exe" and cname != "CabinetWClass":
                return True

            if not wtitle and not is_iconic and cname not in ("Notepad", "ApplicationFrameWindow", "Chrome_WidgetWin_1", "CabinetWClass"):
                return True

            area = (w * h_sz) if not is_iconic else 1000000
            matching_hwnds.append((area, h))
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
        user32.EnumDesktopWindows.argtypes = [ctypes.c_size_t, WNDENUMPROC, ctypes.c_size_t]
        user32.EnumDesktopWindows.restype = ctypes.c_bool
        user32.EnumDesktopWindows(hdesk or 0, WNDENUMPROC(enum_cb), 0)

        if not matching_hwnds:
            return False

        # Sort largest window area first (main application window)
        matching_hwnds.sort(key=lambda x: x[0], reverse=True)

        for _, h in matching_hwnds:
            try:
                user32.ShowWindow(h, 9)  # SW_RESTORE
                user32.SwitchToThisWindow(h, True)
                cur_thread = win32api.GetCurrentThreadId()
                fg_hwnd = user32.GetForegroundWindow()
                fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0
                attached = False
                if fg_thread and fg_thread != cur_thread:
                    try:
                        attached = bool(user32.AttachThreadInput(cur_thread, fg_thread, True))
                    except Exception:
                        pass
                try:
                    user32.keybd_event(0x12, 0, 0, 0)  # Alt key down
                    user32.keybd_event(0x12, 0, 2, 0)  # Alt key up
                except Exception:
                    pass
                try:
                    user32.AllowSetForegroundWindow(-1)
                except Exception:
                    pass
                user32.BringWindowToTop(h)
                user32.SetForegroundWindow(h)
                if attached:
                    try:
                        user32.AttachThreadInput(cur_thread, fg_thread, False)
                    except Exception:
                        pass
                return True
            except Exception as exc:
                logging.getLogger("jarvis.launch").debug("bring_to_front window error: %s", exc)
        return False
    except Exception as exc:
        logging.getLogger("jarvis.launch").debug("bring_to_front error: %s", exc)
    return False


def _launch_via_explorer(path: str, args: str = "") -> bool:
    """Launch process through the interactive shell (Explorer.exe) on the user's Default desktop."""
    try:
        import win32com.client
        shell = win32com.client.Dispatch("Shell.Application")
        disp = shell.Windows().FindWindowSW(0, 0, 8, 0, 1)  # SWC_DESKTOP, SWFO_NEEDDISPATCH
        doc = getattr(disp, "Document", None)
        app = getattr(doc, "Application", None) if doc else None
        if app:
            app.ShellExecute(path, args, "", "open", 1)
            return True
    except Exception as exc:
        logging.getLogger("jarvis.launch").debug("Explorer ShellExecute: %s", exc)
    return False


def launch(target):
    log = logging.getLogger("jarvis.launch")

    if os.name == "nt":
        # Always attach to the interactive desktop first so the app is visible
        _attach_interactive_desktop()

        # Check if already running and has a window on Default desktop: restore & focus!
        if bring_to_front(target.process_names):
            log.info("App already running, brought to front: %s", target.process_names)
            return None

        import ctypes
        import time
        shell32 = ctypes.windll.shell32
        path = target.path

        # 1. Primary method: Explorer.exe folder window or shell folder protocol
        if "explorer.exe" in path.lower() or path.lower().startswith("shell:"):
            folder = path if path.lower().startswith("shell:") else "shell:MyComputerFolder"
            res = shell32.ShellExecuteW(None, "open", folder, None, None, 1)
            if res <= 32:
                try:
                    subprocess.Popen(["explorer.exe", folder], startupinfo=si)
                except Exception:
                    pass
            time.sleep(0.5)
            bring_to_front(target.process_names)
            return None

        # 2. Launch other apps via Explorer shell on the user's Default interactive desktop
        launch_args = ""
        if any(b in path.lower() for b in ("chrome.exe", "msedge.exe", "brave.exe", "firefox.exe")):
            launch_args = "--new-window"
        if _launch_via_explorer(path, launch_args):
            log.info("Launched via Explorer OK for %s (args=%s)", path, launch_args)
            time.sleep(0.4)
            bring_to_front(target.process_names)
            return None

        # Setup STARTUPINFO with interactive Default desktop
        si = subprocess.STARTUPINFO()
        si.lpDesktop = r"WinSta0\Default"

        # --- URLs, ms-protocol URIs, .lnk shortcuts: ShellExecuteW ---
        is_protocol = ":" in path and not (len(path) >= 2 and path[1] == ":" and (path[2:3] in ("\\", "/", "")))
        is_shell_target = (
            is_protocol  # ms-settings:, ms-photos:, bingweather:, http://, https://, etc.
            or path.lower().endswith(".lnk")
        )
        if is_shell_target:
            result = shell32.ShellExecuteW(None, "open", path, None, None, 1)
            if result > 32:
                log.info("ShellExecuteW OK for %s (result=%d)", path, result)
                time.sleep(0.3)
                bring_to_front(target.process_names)
                return None
            log.warning("ShellExecuteW failed for %s (result=%d)", path, result)

        # --- Browsers: Popen with --new-window and explicit Default desktop ---
        target_path_lower = path.lower()
        if any(b in target_path_lower for b in ("chrome.exe", "msedge.exe", "brave.exe", "firefox.exe")):
            try:
                child = subprocess.Popen(
                    [path, "--new-window"],
                    shell=False,
                    startupinfo=si,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
                log.info("Popen OK for browser %s (pid=%d)", path, child.pid)
                time.sleep(0.5)
                bring_to_front(target.process_names)
                return child.pid
            except Exception as exc:
                log.warning("Popen failed for browser %s: %s", path, exc)

        # --- Standard Windows executables (notepad, calc, mspaint, etc.) ---
        try:
            child = subprocess.Popen(
                [path],
                shell=False,
                startupinfo=si,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            log.info("Popen OK for %s (pid=%d)", path, child.pid)
            time.sleep(0.3)
            bring_to_front(target.process_names)
            return child.pid
        except Exception as exc:
            log.warning("Popen failed for %s: %s, trying ShellExecuteW", path, exc)

        result = shell32.ShellExecuteW(None, "open", path, None, None, 1)
        if result > 32:
            log.info("ShellExecuteW OK for %s (result=%d)", path, result)
            time.sleep(0.3)
            bring_to_front(target.process_names)
            return None

        # Last resort: os.startfile
        os.startfile(path)
        time.sleep(0.3)
        bring_to_front(target.process_names)
        return None

    # --- Non-Windows ---
    elif target.associated:
        try:
            import webbrowser
            webbrowser.open(target.path)
            return None
        except Exception:
            pass
    child = subprocess.Popen([target.path], shell=False)
    return child.pid

def volume(percent=None):
    import comtypes
    comtypes.CoInitialize()
    try:
        from pycaw.pycaw import AudioUtilities
        endpoint = AudioUtilities.GetSpeakers().EndpointVolume
        if percent is not None:
            endpoint.SetMasterVolumeLevelScalar(percent / 100, None)
        return float(endpoint.GetMasterVolumeLevelScalar() * 100)
    except (comtypes.COMError, AttributeError) as exc:
        raise OSError(f"Windows audio endpoint unavailable: {exc}") from exc
    finally:
        comtypes.CoUninitialize()

def brightness_control(percent=None) -> float:
    """Set or get display brightness using WMI on Windows."""
    try:
        if percent is not None:
            pct = max(0, min(100, int(percent)))
            cmd = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {pct})"
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                capture_output=True,
                check=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return float(pct)
        else:
            cmd = "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness"
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                capture_output=True,
                text=True,
                check=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            val = res.stdout.strip()
            return float(val) if val else 50.0
    except Exception as exc:
        logging.getLogger("jarvis.system").warning("WMI brightness operation failed: %s", exc)
        return float(percent if percent is not None else 50.0)

def get_top_memory_processes(limit: int = 5) -> dict:
    """Query currently running processes and aggregate RSS memory consumption."""
    agg: dict[str, float] = {}
    for p in psutil.process_iter(["name", "memory_info"]):
        try:
            info = p.info
            if info and info.get("name") and info.get("memory_info"):
                name = info["name"]
                mem_mb = info["memory_info"].rss / (1024 * 1024)
                clean_name = name[:-4] if name.lower().endswith(".exe") else name
                agg[clean_name] = agg.get(clean_name, 0.0) + mem_mb
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    sorted_procs = sorted(agg.items(), key=lambda x: x[1], reverse=True)[:limit]
    items = []
    for name, mb in sorted_procs:
        fmt = f"{mb / 1024:.1f} GB" if mb >= 1024 else f"{int(mb)} MB"
        items.append({"name": name, "memory_mb": round(mb, 1), "formatted": fmt})

    vm = psutil.virtual_memory()
    return {
        "processes": items,
        "total_ram_gb": round(vm.total / (1024**3), 1),
        "used_ram_gb": round(vm.used / (1024**3), 1),
        "free_ram_gb": round(vm.available / (1024**3), 1),
    }

def hardware_info():
    result = dict(os=platform.platform(), python=platform.python_version(),
                  cpu=platform.processor() or platform.machine(),
                  ram_total_mb=psutil.virtual_memory().total / 2**20,
                  gpu_name=None, gpu_vram_mb=None)
    executable = shutil.which("nvidia-smi")
    if executable:
        try:
            output = subprocess.run([executable, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                                    capture_output=True, text=True, timeout=3, check=True,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            name, ram = output.stdout.splitlines()[0].rsplit(",", 1)
            result.update(gpu_name=name.strip(), gpu_vram_mb=float(ram))
        except (OSError, subprocess.SubprocessError, ValueError, IndexError) as exc:
            logging.getLogger("jarvis.system").warning("GPU metadata unavailable: %s", exc)
    return result

SYSTEM_TOOL_DESCRIPTIONS = {
    "open_app": "Launch a Windows application, Start-menu app, folder shortcut or web service by name (e.g. chrome, notepad, calculator, spotify, youtube).",
    "close_app": "Close / terminate a running desktop application by name.",
    "list_directory": "List the files inside a folder and reveal it in File Explorer (path may be Desktop, Downloads, Documents or an absolute path).",
    "get_time": "Return the current local time and date.",
    "system_info": "Report OS, CPU, RAM usage and GPU of this PC.",
    "volume_get": "Read the current master speaker volume percentage.",
    "volume_set": "Set the master speaker volume to an exact percentage (0-100).",
    "brightness_get": "Read the current screen brightness percentage.",
    "brightness_set": "Set the screen brightness to an exact percentage (0-100).",
    "top_memory_processes": "List the programs using the most RAM right now.",
    "take_screenshot": "Capture the whole screen to a PNG file (optional path).",
    "set_voice": "Change JARVIS's speaking voice (male or female).",
    "show_dashboard": "Open or bring the JARVIS dashboard window to the front.",
    "wake_greeting": "Greet the user and show the JARVIS dashboard.",
}


class SystemTool(Tool):
    def __init__(self, name, input_model, output_model, function, read_only=True):
        self.definition = ToolDefinition(name=name, description=SYSTEM_TOOL_DESCRIPTIONS.get(name, name.replace("_", " ")),
            input_model=input_model, output_model=output_model, read_only=read_only,
            risk=RiskLevel.READ_ONLY if read_only else RiskLevel.REVERSIBLE, tags=("system",))
        self.function = function

    def run(self, arguments):
        return self.function(arguments)

def create_tools(resolver, hardware, launcher=launch, search_engine=None, working_memory=None, response_provider=None):
    from jarvis.tools.system.file_tools import create_file_tools

    def open_app(args):
        target = resolver.resolve(args.name)
        pid = launcher(target)
        return dict(name=args.name, target=target.path, pid=pid, process_names=target.process_names, associated=getattr(target, "associated", False))

    def list_directory(args):
        path = Path(args.path).expanduser().resolve(strict=True)
        # Visually reveal folder in File Explorer on screen for the user
        try:
            import ctypes
            shell32 = ctypes.windll.shell32
            shell32.ShellExecuteW(None, "open", str(path), None, None, 1)
        except Exception:
            try:
                subprocess.Popen(["explorer.exe", str(path)])
            except Exception:
                pass
        entries = []
        with os.scandir(path) as iterator:
            for entry in iterator:
                if len(entries) == args.limit:
                    return dict(path=str(path), entries=entries, truncated=True)
                entries.append(entry.name)
        return dict(path=str(path), entries=entries, truncated=False)

    def screenshot(args):
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
        except Exception:
            pass

        path = Path(args.path).expanduser().resolve() if args.path else ROOT / "screenshots" / f"{uuid.uuid4().hex}.png"
        path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Primary: PIL ImageGrab (handles multi-monitor and layered surfaces cleanly)
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab(all_screens=True)
            img.save(str(path), format="PNG")
            return dict(path=str(path), bytes=path.stat().st_size)
        except Exception as exc:
            logging.getLogger("jarvis.system").warning("ImageGrab failed: %s, trying mss fallback", exc)

        # 2. Fallback: mss
        import mss
        import mss.tools
        with mss.mss() as capture:
            frame = capture.grab(capture.monitors[0])
            png = mss.tools.to_png(frame.rgb, frame.size)
        with path.open("wb") as file:
            file.write(png)
        return dict(path=str(path), bytes=len(png))

    def set_voice_fn(args):
        g = args.gender.lower().strip()
        target_gender = "female" if ("fem" in g or "woman" in g) else "male"
        actual_gender = target_gender
        if response_provider:
            try:
                resp = response_provider()
                if resp:
                    tts = getattr(resp, "tts", None) or resp
                    if hasattr(tts, "set_voice"):
                        actual_gender = tts.set_voice(target_gender)
            except Exception as exc:
                logging.getLogger("jarvis.system").warning("set_voice execution error: %s", exc)
        return dict(gender=actual_gender, status="updated")

    def show_dashboard_fn(args):
        if response_provider:
            try:
                resp = response_provider()
                if resp and hasattr(resp, "event_bus") and resp.event_bus:
                    resp.event_bus.emit("voice.wake_detected", "dashboard", source="command")
            except Exception as exc:
                logging.getLogger("jarvis.system").warning("show_dashboard execution error: %s", exc)

        # 1. Bring existing window to front via Win32 on interactive Default desktop
        brought_to_front = False
        try:
            import win32gui, win32con, ctypes
            user32 = ctypes.windll.user32
            # Attach current thread to Default desktop so EnumWindows queries the real interactive screen
            hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)

            def enum_cb(h, found):
                t = win32gui.GetWindowText(h)
                if "JARVIS EDGE" in t:
                    found.append(h)
            found_hwnds = []
            win32gui.EnumWindows(enum_cb, found_hwnds)
            for h in found_hwnds:
                win32gui.ShowWindow(h, win32con.SW_RESTORE)
                try:
                    import win32process, win32api
                    fg_hwnd = win32gui.GetForegroundWindow()
                    fg_thread, _ = win32process.GetWindowThreadProcessId(fg_hwnd) if fg_hwnd else (0, 0)
                    cur_thread = win32api.GetCurrentThreadId()
                    attached = False
                    if fg_thread and fg_thread != cur_thread:
                        try:
                            attached = bool(user32.AttachThreadInput(cur_thread, fg_thread, True))
                        except Exception:
                            pass
                    try:
                        user32.keybd_event(0x12, 0, 0, 0)
                        user32.keybd_event(0x12, 0, 2, 0)
                    except Exception:
                        pass
                    win32gui.SetWindowPos(h, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
                    win32gui.SetWindowPos(h, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
                    win32gui.BringWindowToTop(h)
                    win32gui.SetForegroundWindow(h)
                    if attached:
                        try:
                            user32.AttachThreadInput(cur_thread, fg_thread, False)
                        except Exception:
                            pass
                except Exception:
                    win32gui.BringWindowToTop(h)
                    win32gui.SetForegroundWindow(h)
                brought_to_front = True
                break
        except Exception as exc:
            logging.getLogger("jarvis.system").warning("Win32 bring to front error: %s", exc)

        # 2. If not brought to front, verify process and launch jarvis.ui
        if not brought_to_front:
            try:
                from pathlib import Path
                import tempfile
                lock_file = Path(tempfile.gettempdir()) / "jarvis-edge-ui.lock"

                ui_running = False
                for p in psutil.process_iter(["cmdline"]):
                    try:
                        cmd = p.info.get("cmdline") or []
                        if any("jarvis.ui" in str(arg) for arg in cmd):
                            ui_running = True
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                if not ui_running:
                    lock_file.unlink(missing_ok=True)
                    import sys, subprocess
                    python_exe = sys.executable
                    subprocess.Popen(
                        [python_exe, "-m", "jarvis.ui"],
                        cwd=str(ROOT.parent),
                        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                        shell=False,
                    )
            except Exception as exc:
                logging.getLogger("jarvis.system").warning("show_dashboard UI launch error: %s", exc)

        return dict(status="success", message="Dashboard opened")

    def close_app(args):
        try:
            target = resolver.resolve(args.name)
            proc_names = [p.lower() for p in target.process_names]
        except Exception:
            name_clean = args.name.lower().strip()
            if not name_clean.endswith(".exe"):
                name_clean += ".exe"
            proc_names = [name_clean]

        killed = 0
        for proc in psutil.process_iter(["name"]):
            try:
                pname = proc.info.get("name")
                if pname and pname.lower() in proc_names:
                    proc.terminate()
                    killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return dict(name=args.name, closed=True, count=killed)

    def _get_time(_):
        now = datetime.now(timezone.utc).astimezone()
        date_str = now.strftime("%A, %B %d, %Y")
        time_str = now.strftime("%I:%M %p").lstrip("0")
        return {
            "iso": now.isoformat(),
            "date": date_str,
            "time": time_str,
            "formatted": f"{time_str}, {date_str}",
        }

    base_tools = [
        SystemTool("open_app", AppInput, AppOutput, open_app, False),
        SystemTool("close_app", AppInput, CloseAppOutput, close_app, False),
        SystemTool("list_directory", DirectoryInput, DirectoryOutput, list_directory),
        SystemTool("get_time", Empty, TimeOutput, _get_time),
        SystemTool("system_info", Empty, InfoOutput, lambda _: {**hardware, "ram_used_mb": psutil.virtual_memory().used / 2**20}),
        SystemTool("volume_get", Empty, VolumeOutput, lambda _: {"percent": volume()}),
        SystemTool("volume_set", VolumeInput, VolumeOutput, lambda a: {"percent": volume(a.percent)}, False),
        SystemTool("brightness_get", Empty, BrightnessOutput, lambda _: {"percent": brightness_control()}),
        SystemTool("brightness_set", BrightnessInput, BrightnessOutput, lambda a: {"percent": brightness_control(a.percent)}, False),
        SystemTool("top_memory_processes", Empty, TopProcessesOutput, lambda _: get_top_memory_processes()),
        SystemTool("take_screenshot", ScreenshotInput, ScreenshotOutput, screenshot, False),
        SystemTool("set_voice", VoiceInput, VoiceOutput, set_voice_fn, False),
        SystemTool("show_dashboard", Empty, DashboardOutput, show_dashboard_fn, False),
        SystemTool("wake_greeting", Empty, DashboardOutput, show_dashboard_fn, False),
    ]
    file_tools = create_file_tools(search_engine=search_engine, working_memory=working_memory)
    from jarvis.tools.productivity import create_productivity_tools
    prod_tools = create_productivity_tools()
    from jarvis.tools.system.computer_tools import create_computer_tools
    computer_tools = create_computer_tools()
    from jarvis.tools.system.whatsapp_tools import (
        DraftWhatsAppReplyTool,
        ReplyWhatsAppAllTool,
        SendWhatsAppBulkTool,
        SendWhatsAppMessageTool,
        ReadWhatsAppMessagesTool,
        SummarizeWhatsAppMessagesTool,
    )
    from jarvis.tools.system.web_search import WebSearchTool
    whatsapp_tools = [
        SendWhatsAppMessageTool(),
        ReadWhatsAppMessagesTool(),
        SummarizeWhatsAppMessagesTool(),
        DraftWhatsAppReplyTool(),
        ReplyWhatsAppAllTool(),
        SendWhatsAppBulkTool(),
    ]
    from jarvis.integrations.whatsapp.personal_reply.commands import WhatsAppAutoReplyTool
    whatsapp_tools.append(WhatsAppAutoReplyTool())
    web_tools = [WebSearchTool()]
    from jarvis.tools.system.connector_tools import create_connector_tools
    conn_tools = create_connector_tools(working_memory=working_memory)
    from jarvis.tools.system.app_tools import create_app_discovery_tools
    app_discovery_tools = create_app_discovery_tools(catalog=resolver if hasattr(resolver, "is_installed") else None)
    from jarvis.tools.system.window_management_tools import create_window_management_tools
    window_mgmt_tools = create_window_management_tools()
    from jarvis.tools.system.ide_tools import create_ide_tools
    ide_tools = create_ide_tools()
    from jarvis.tools.system.keyboard_tools import create_keyboard_tools
    keyboard_tools = create_keyboard_tools()
    from jarvis.tools.system.assistant_tools import create_assistant_tools
    from jarvis.tools.system.phone_tools import create_phone_tools
    from jarvis.tools.system.vision_tools import create_vision_tools
    from jarvis.tools.system.computer_use import create_computer_use_tools
    from jarvis.tools.system.everyday_tools import create_everyday_tools
    from jarvis.tools.system.quick_actions import create_quick_action_tools
    extra_tools = (create_assistant_tools() + create_phone_tools() + create_vision_tools() + create_computer_use_tools()
                   + create_everyday_tools() + create_quick_action_tools())
    return base_tools + file_tools + prod_tools + computer_tools + whatsapp_tools + web_tools + conn_tools + app_discovery_tools + window_mgmt_tools + ide_tools + keyboard_tools + extra_tools

