from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import platform
import shutil
import subprocess
import uuid
import psutil
from pydantic import Field
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
class DirectoryInput(Contract):
    path: str = Field(min_length=1, max_length=4096)
    limit: int = Field(default=100, ge=1, le=1000)
class DirectoryOutput(Contract):
    path: str
    entries: list[str]
    truncated: bool
class TimeOutput(Contract):
    iso: str
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
class ScreenshotInput(Contract):
    path: str | None = None
class ScreenshotOutput(Contract):
    path: str
    bytes: int = Field(gt=0)

def launch(target):
    if target.associated:
        os.startfile(target.path)
        return None
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

class SystemTool(Tool):
    def __init__(self, name, input_model, output_model, function, read_only=True):
        self.definition = ToolDefinition(name=name, description=name.replace("_", " "),
            input_model=input_model, output_model=output_model, read_only=read_only,
            risk=RiskLevel.READ_ONLY if read_only else RiskLevel.REVERSIBLE, tags=("system",))
        self.function = function

    def run(self, arguments):
        return self.function(arguments)

def create_tools(resolver, hardware, launcher=launch, search_engine=None, working_memory=None):
    from jarvis.tools.system.file_tools import create_file_tools

    def open_app(args):
        target = resolver.resolve(args.name)
        pid = launcher(target)
        return dict(name=args.name, target=target.path, pid=pid, process_names=target.process_names)

    def list_directory(args):
        path = Path(args.path).expanduser().resolve(strict=True)
        entries = []
        with os.scandir(path) as iterator:
            for entry in iterator:
                if len(entries) == args.limit:
                    return dict(path=str(path), entries=entries, truncated=True)
                entries.append(entry.name)
        return dict(path=str(path), entries=entries, truncated=False)

    def screenshot(args):
        import mss
        import mss.tools
        path = Path(args.path).expanduser().resolve() if args.path else ROOT / "screenshots" / f"{uuid.uuid4().hex}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        with mss.mss() as capture:
            frame = capture.grab(capture.monitors[0])
            png = mss.tools.to_png(frame.rgb, frame.size)
        with path.open("xb") as file:  # never silently overwrite user content
            file.write(png)
        return dict(path=str(path), bytes=len(png))

    base_tools = [
        SystemTool("open_app", AppInput, AppOutput, open_app, False),
        SystemTool("list_directory", DirectoryInput, DirectoryOutput, list_directory),
        SystemTool("get_time", Empty, TimeOutput, lambda _: {"iso": datetime.now(timezone.utc).astimezone().isoformat()}),
        SystemTool("system_info", Empty, InfoOutput, lambda _: {**hardware, "ram_used_mb": psutil.virtual_memory().used / 2**20}),
        SystemTool("volume_get", Empty, VolumeOutput, lambda _: {"percent": volume()}),
        SystemTool("volume_set", VolumeInput, VolumeOutput, lambda a: {"percent": volume(a.percent)}, False),
        SystemTool("take_screenshot", ScreenshotInput, ScreenshotOutput, screenshot, False),
    ]
    file_tools = create_file_tools(search_engine=search_engine, working_memory=working_memory)
    return base_tools + file_tools
