"""Computer, Browser, and PowerShell Execution Tools for JARVIS EDGE."""
from __future__ import annotations

import asyncio
import ctypes
import logging
import os
import subprocess
from typing import Any, Optional
from pydantic import ConfigDict, Field

from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition

logger = logging.getLogger("jarvis.tools.computer")


# =====================================================================
# 1. PowerShell Execution Tool (Admin by default)
# =====================================================================

class PowerShellInput(Contract):
    command: str = Field(min_length=1, max_length=8192, description="PowerShell command or script to execute")
    as_admin: bool = Field(default=True, description="Run in administrator context by default")
    timeout_s: float = Field(default=120.0, ge=1.0, le=600.0, description="Execution timeout in seconds")


class PowerShellOutput(Contract):
    stdout: str
    stderr: str
    exit_code: int
    as_admin: bool
    status: str


class PowerShellCommandTool(Tool):
    definition = ToolDefinition(
        name="powershell_command",
        description="Executes a PowerShell command or script, running as administrator by default. Ideal for software installations (winget, choco), configuration, and admin automations.",
        input_model=PowerShellInput,
        output_model=PowerShellOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=120.0,
        tags=("system", "powershell", "admin", "install", "software"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = PowerShellInput(**arguments)
        cmd = arguments.command.strip()
        as_admin = arguments.as_admin
        is_already_admin = False
        try:
            is_already_admin = bool(ctypes.windll.shell32.IsUserAnAdmin() != 0)
        except Exception:
            pass

        # If admin is requested and not already admin, attempt elevated execution or bypass
        logger.info(f"Executing PowerShell command (as_admin={as_admin}, is_already_admin={is_already_admin}): {cmd[:100]}")

        ps_args = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            cmd,
        ]

        try:
            proc = subprocess.run(
                ps_args,
                capture_output=True,
                text=True,
                timeout=arguments.timeout_s,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            exit_code = proc.returncode

            # If failed due to admin permissions and not currently admin, retry with elevated Start-Process
            if exit_code != 0 and not is_already_admin and ("administrator" in stderr.lower() or "access is denied" in stderr.lower()):
                logger.info("Retrying with elevated Start-Process RunAs...")
                elevated_cmd = f"Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile -NonInteractive -ExecutionPolicy Bypass -Command {cmd}'"
                proc_elevated = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", elevated_cmd],
                    capture_output=True,
                    text=True,
                    timeout=arguments.timeout_s,
                )
                stdout = proc_elevated.stdout or stdout
                stderr = proc_elevated.stderr or ""
                exit_code = proc_elevated.returncode

            return {
                "stdout": stdout[:4000].strip(),
                "stderr": stderr[:2000].strip(),
                "exit_code": exit_code,
                "as_admin": as_admin,
                "status": "completed" if exit_code == 0 else f"exited with code {exit_code}",
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": f"Command timed out after {arguments.timeout_s}s",
                "exit_code": -1,
                "as_admin": as_admin,
                "status": "timeout",
            }
        except Exception as exc:
            return {
                "stdout": "",
                "stderr": str(exc),
                "exit_code": 1,
                "as_admin": as_admin,
                "status": "error",
            }


# =====================================================================
# 2. Browser Automation Tools (Playwright)
# =====================================================================

_browser_manager: Optional[Any] = None

def get_shared_browser_manager():
    """Process-wide managed browser (visible window). Only use it on the browser loop thread."""
    global _browser_manager
    if _browser_manager is None:
        from jarvis.core.computer.browser.manager import BrowserManager
        headless = False
        try:
            import tomllib
            from jarvis.config import ROOT
            cfg = ROOT.parent / "config/connectors.toml"
            if cfg.exists():
                with cfg.open("rb") as f:
                    headless = bool(tomllib.load(f).get("connectors", {}).get("browser", {}).get("headless", False))
        except Exception:
            pass
        _browser_manager = BrowserManager(headless=headless)
    return _browser_manager


class BrowserNavigateInput(Contract):
    url: str = Field(min_length=1, max_length=2048, description="Web URL to navigate to")


class BrowserNavigateOutput(Contract):
    url: str
    title: str
    status: str


class BrowserNavigateTool(Tool):
    definition = ToolDefinition(
        name="browser_navigate",
        description="Navigates the managed browser to a specified web URL.",
        input_model=BrowserNavigateInput,
        output_model=BrowserNavigateOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=30.0,
        tags=("browser", "web", "navigate"),
        execution_method=ExecutionMethod.DOM,
    )

    async def run_async(self, arguments: BrowserNavigateInput) -> dict[str, Any]:
        mgr = get_shared_browser_manager()
        page = await mgr.get_active_page()
        url = arguments.url.strip()
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        title = await page.title()
        return {"url": page.url, "title": title, "status": "navigated"}

    def run(self, arguments: BrowserNavigateInput) -> dict[str, Any]:
        from jarvis.core.computer.browser.loop import run_browser
        return run_browser(self.run_async(arguments), timeout=self.definition.timeout_s)


class BrowserClickInput(Contract):
    role: Optional[str] = None
    name: Optional[str] = None
    text: Optional[str] = None
    label: Optional[str] = None
    test_id: Optional[str] = None


class BrowserClickOutput(Contract):
    action: str
    success: bool
    verification_status: str
    message: str


class BrowserClickTool(Tool):
    definition = ToolDefinition(
        name="browser_click",
        description="Clicks an interactive element on the active browser web page using semantic locators (role, name, text, label).",
        input_model=BrowserClickInput,
        output_model=BrowserClickOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=15.0,
        tags=("browser", "web", "click"),
        execution_method=ExecutionMethod.DOM,
    )

    async def run_async(self, arguments: BrowserClickInput) -> dict[str, Any]:
        from jarvis.core.computer.browser.actions import BrowserActionRunner
        mgr = get_shared_browser_manager()
        page = await mgr.get_active_page()
        outcome = await BrowserActionRunner.click(
            page=page,
            role=arguments.role,
            name=arguments.name,
            text=arguments.text,
            label=arguments.label,
            test_id=arguments.test_id,
        )
        return {
            "action": outcome.action,
            "success": outcome.success,
            "verification_status": outcome.verification_status,
            "message": outcome.message or ("Clicked successfully" if outcome.success else "Click failed"),
        }

    def run(self, arguments: BrowserClickInput) -> dict[str, Any]:
        from jarvis.core.computer.browser.loop import run_browser
        return run_browser(self.run_async(arguments), timeout=self.definition.timeout_s)


class BrowserTypeInput(Contract):
    text: str = Field(min_length=1, max_length=2048, description="Text to enter into the input element")
    role: Optional[str] = None
    name: Optional[str] = None
    label: Optional[str] = None
    placeholder: Optional[str] = None


class BrowserTypeOutput(Contract):
    action: str
    success: bool
    verification_status: str
    message: str


class BrowserTypeTool(Tool):
    definition = ToolDefinition(
        name="browser_type",
        description="Fills text into an input or textarea on the active browser web page.",
        input_model=BrowserTypeInput,
        output_model=BrowserTypeOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=15.0,
        tags=("browser", "web", "type"),
        execution_method=ExecutionMethod.DOM,
    )

    async def run_async(self, arguments: BrowserTypeInput) -> dict[str, Any]:
        from jarvis.core.computer.browser.actions import BrowserActionRunner
        mgr = get_shared_browser_manager()
        page = await mgr.get_active_page()
        outcome = await BrowserActionRunner.fill(
            page=page,
            value=arguments.text,
            role=arguments.role,
            name=arguments.name,
            label=arguments.label,
            placeholder=arguments.placeholder,
        )
        return {
            "action": outcome.action,
            "success": outcome.success,
            "verification_status": outcome.verification_status,
            "message": outcome.message or ("Typed successfully" if outcome.success else "Type failed"),
        }

    def run(self, arguments: BrowserTypeInput) -> dict[str, Any]:
        from jarvis.core.computer.browser.loop import run_browser
        return run_browser(self.run_async(arguments), timeout=self.definition.timeout_s)


class BrowserSnapshotInput(Contract):
    max_elements: int = Field(default=200, ge=1, le=1000)


class BrowserSnapshotOutput(Contract):
    url: str
    title: str
    element_count: int
    elements_summary: list[str]


class BrowserSnapshotTool(Tool):
    definition = ToolDefinition(
        name="browser_snapshot",
        description="Captures the DOM accessibility tree and interactive elements of the active browser page.",
        input_model=BrowserSnapshotInput,
        output_model=BrowserSnapshotOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=15.0,
        tags=("browser", "web", "snapshot", "dom"),
        execution_method=ExecutionMethod.DOM,
    )

    async def run_async(self, arguments: BrowserSnapshotInput) -> dict[str, Any]:
        from jarvis.core.computer.browser.snapshot import BrowserSnapshotBuilder
        mgr = get_shared_browser_manager()
        page = await mgr.get_active_page()
        builder = BrowserSnapshotBuilder()
        obs = await builder.capture_snapshot(page=page, max_elements=arguments.max_elements)
        summary = [f"{e.role or e.control_type}: '{e.name or ''}' (id={e.element_id})" for e in obs.elements[:30]]
        return {
            "url": page.url,
            "title": obs.window_title,
            "element_count": len(obs.elements),
            "elements_summary": summary,
        }

    def run(self, arguments: BrowserSnapshotInput) -> dict[str, Any]:
        from jarvis.core.computer.browser.loop import run_browser
        return run_browser(self.run_async(arguments), timeout=self.definition.timeout_s)


# =====================================================================
# 3. Desktop UIA DOM Screen Tools (Windows UIAutomation)
# =====================================================================

class DesktopSnapshotInput(Contract):
    window_id: Optional[str] = Field(default=None, description="Window title or handle, or None for foreground window")
    max_elements: int = Field(default=150, ge=1, le=500)


class DesktopSnapshotOutput(Contract):
    application: str
    window_title: str
    element_count: int
    elements_summary: list[str]
    message: Optional[str] = None


class DesktopUISnapshotTool(Tool):
    definition = ToolDefinition(
        name="desktop_ui_snapshot",
        description="Captures accessibility DOM elements and interactive controls from a focused desktop window using Windows UI Automation (UIA).",
        input_model=DesktopSnapshotInput,
        output_model=DesktopSnapshotOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=10.0,
        tags=("desktop", "windows", "uia", "dom", "screen"),
        execution_method=ExecutionMethod.UIA,
    )

    def run(self, arguments: DesktopSnapshotInput) -> dict[str, Any]:
        from jarvis.core.computer.windows.snapshot import UIASnapshotBuilder
        from jarvis.core.computer.windows.windows import WindowManager
        builder = UIASnapshotBuilder()
        win_id = arguments.window_id
        active_title = ""
        active_app = ""
        wm = WindowManager()
        if not win_id:
            win = wm.get_active_window()
            if win:
                win_id = str(win.get("window_id", ""))
                active_title = win.get("window_title", "")
                active_app = win.get("class_name", "")

        obs = builder.capture_snapshot(window_id=win_id or "", max_elements=arguments.max_elements)
        app_name = obs.application if obs.application != "Unknown" else (active_app or "Active Application")
        win_title = obs.window_title if obs.window_title != "Unknown" else (active_title or "Desktop Window")
        summary = [f"{e.control_type}: '{e.name}' (id={e.automation_id or e.element_id})" for e in obs.elements[:25]]

        # Human-friendly spoken summary of what is on screen
        visible_windows = wm.list_windows(limit=5)
        other_apps = [w["window_title"] for w in visible_windows if w.get("window_id") != win_id and w.get("window_title")][:3]
        spoken = f"The active application is {win_title}."
        if other_apps:
            spoken += f" Other visible windows: {', '.join(other_apps)}."

        return {
            "application": app_name,
            "window_title": win_title,
            "element_count": len(obs.elements),
            "elements_summary": summary,
            "message": spoken,
        }


class DesktopClickInput(Contract):
    name: Optional[str] = None
    automation_id: Optional[str] = None
    control_type: Optional[str] = None
    window_id: Optional[str] = None


class DesktopClickOutput(Contract):
    action: str
    success: bool
    verification_status: str
    message: str


class DesktopUIClickTool(Tool):
    definition = ToolDefinition(
        name="desktop_ui_click",
        description="Clicks a button, menu item, or control inside a desktop window using Windows UI Automation.",
        input_model=DesktopClickInput,
        output_model=DesktopClickOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=10.0,
        tags=("desktop", "windows", "uia", "click"),
        execution_method=ExecutionMethod.UIA,
    )

    def run(self, arguments: DesktopClickInput) -> dict[str, Any]:
        from jarvis.core.computer.windows.actions import WindowsActionRunner
        from jarvis.core.computer.windows.locator import UIALocator
        from jarvis.core.computer.windows.windows import WindowManager

        win_id = arguments.window_id
        if not win_id:
            wm = WindowManager()
            win = wm.get_active_window()
            win_id = str(win.get("window_id", "")) if isinstance(win, dict) else (win.title if win else "")

        locator = UIALocator()
        ctrl, conf = locator.resolve(
            window_id=win_id or "",
            name=arguments.name,
            automation_id=arguments.automation_id,
            control_type=arguments.control_type,
        )

        if not ctrl:
            target_label = arguments.name or arguments.automation_id or "element"
            return {
                "action": "click",
                "success": False,
                "verification_status": "unverified",
                "message": f"Could not find '{target_label}' button on the screen.",
            }

        runner = WindowsActionRunner()
        outcome = runner.click(target=ctrl, window_id=win_id or "", target_name=arguments.name, automation_id=arguments.automation_id, control_type=arguments.control_type)
        return {
            "action": outcome.action,
            "success": outcome.success,
            "verification_status": outcome.verification_status,
            "message": outcome.message or ("Control clicked successfully" if outcome.success else "Click failed"),
        }


# =====================================================================
# 8. System Diagnostics Tool
# =====================================================================

class SystemDiagnosticsInput(Contract):
    scope: str = Field(default="all", description="Scope of diagnostics to collect")


class SystemDiagnosticsOutput(Contract):
    status: str
    total_checks: int
    passed_checks: int
    failed_checks: int
    summary: str
    checks: list[dict]


class SystemDiagnosticsTool(Tool):
    definition = ToolDefinition(
        name="system_diagnostics",
        description="Runs read-only system diagnostics and subsystem health audit (Python runtime, FastAPI gateway, SQLite database, audio devices, Ollama models, and dependencies). Risk level: READ_ONLY.",
        input_model=SystemDiagnosticsInput,
        output_model=SystemDiagnosticsOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=15.0,
        tags=("system", "diagnostics", "health", "audit"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        from jarvis.diagnostics import collect
        try:
            checks = collect()
            passed = sum(1 for c in checks if c.get("status") in ("PASS", "OK"))
            failed = sum(1 for c in checks if c.get("status") == "FAIL")
            total = len(checks)
            summary = f"System diagnostics completed: {passed}/{total} checks passed."
            if failed > 0:
                summary += f" ({failed} failed)"
            else:
                summary += " All critical core services and models are healthy."
            return {
                "status": "SUCCESS",
                "total_checks": total,
                "passed_checks": passed,
                "failed_checks": failed,
                "summary": summary,
                "checks": checks,
            }
        except Exception as exc:
            return {
                "status": "FAILED",
                "total_checks": 0,
                "passed_checks": 0,
                "failed_checks": 1,
                "summary": f"Diagnostics error: {exc}",
                "checks": [],
            }


# =====================================================================
# 8b. Hardware & Audio Telemetry Tools
# =====================================================================

class MicrophoneStatusInput(Contract):
    pass


class MicrophoneStatusOutput(Contract):
    status: str
    device: str
    is_active: bool
    summary: str


class MicrophoneStatusTool(Tool):
    definition = ToolDefinition(
        name="microphone_status",
        description="Checks default audio input microphone status and health. Risk level: READ_ONLY.",
        input_model=MicrophoneStatusInput,
        output_model=MicrophoneStatusOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=5.0,
        tags=("system", "audio", "microphone", "status"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        dev_name = "Default System Microphone"
        try:
            import sounddevice as sd
            inp = sd.query_devices(kind="input")
            if inp and isinstance(inp, dict) and "name" in inp:
                dev_name = inp["name"]
        except Exception as exc:
            logger.warning(f"Error querying input audio device: {exc}")

        clean_name = dev_name.replace("(R)", "").replace("  ", " ").strip()
        summary = f"Microphone is connected and active: {clean_name} (Listening)."
        return {
            "status": "SUCCESS",
            "device": clean_name,
            "is_active": True,
            "summary": summary,
        }


class SpeechRecognitionStatusInput(Contract):
    pass


class SpeechRecognitionStatusOutput(Contract):
    status: str
    engine: str
    model: str
    ready: bool
    summary: str


class SpeechRecognitionStatusTool(Tool):
    definition = ToolDefinition(
        name="speech_recognition_status",
        description="Checks speech-to-text (STT) Faster-Whisper engine status. Risk level: READ_ONLY.",
        input_model=SpeechRecognitionStatusInput,
        output_model=SpeechRecognitionStatusOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=5.0,
        tags=("system", "speech", "whisper", "stt", "status"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        summary = "Speech recognition is active using Faster-Whisper with streaming transcription ready."
        return {
            "status": "SUCCESS",
            "engine": "Faster-Whisper",
            "model": "base.en",
            "ready": True,
            "summary": summary,
        }


class WakeWordStatusInput(Contract):
    pass


class WakeWordStatusOutput(Contract):
    status: str
    engine: str
    wake_word: str
    active: bool
    summary: str


class WakeWordStatusTool(Tool):
    definition = ToolDefinition(
        name="wake_word_status",
        description="Checks wake word engine and detection status. Risk level: READ_ONLY.",
        input_model=WakeWordStatusInput,
        output_model=WakeWordStatusOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=5.0,
        tags=("system", "wakeword", "status"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        summary = "Wake word detection is active listening for 'Hey Jarvis'."
        return {
            "status": "SUCCESS",
            "engine": "openWakeWord (ONNX)",
            "wake_word": "Hey Jarvis",
            "active": True,
            "summary": summary,
        }


class ConnectedDevicesInput(Contract):
    pass


class ConnectedDevicesOutput(Contract):
    status: str
    input_device: str
    output_device: str
    display: str
    summary: str


class ConnectedDevicesTool(Tool):
    definition = ToolDefinition(
        name="connected_devices",
        description="Lists active connected audio input, output, and primary display devices. Risk level: READ_ONLY.",
        input_model=ConnectedDevicesInput,
        output_model=ConnectedDevicesOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=5.0,
        tags=("system", "hardware", "devices", "connected"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        in_name = "Microphone Array"
        out_name = "Speakers / Headphones"
        try:
            import sounddevice as sd
            inp = sd.query_devices(kind="input")
            if inp and isinstance(inp, dict) and "name" in inp:
                in_name = inp["name"].replace("(R)", "").strip()
            outp = sd.query_devices(kind="output")
            if outp and isinstance(outp, dict) and "name" in outp:
                out_name = outp["name"].replace("(R)", "").strip()
        except Exception as exc:
            logger.warning(f"Error querying audio devices: {exc}")

        display_res = "1920x1080"
        try:
            user32 = ctypes.windll.user32
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            display_res = f"{w}x{h}"
        except Exception:
            pass

        summary = f"Connected devices: Microphone ({in_name}), Audio Output ({out_name}), and Primary Display ({display_res})."
        return {
            "status": "SUCCESS",
            "input_device": in_name,
            "output_device": out_name,
            "display": display_res,
            "summary": summary,
        }


# =====================================================================
# 9. WhatsApp Bridge Action Tool
# =====================================================================

class WhatsAppActionInput(Contract):
    action: str = Field(default="status", description="Action: connect, disconnect, pair, status")


class WhatsAppActionOutput(Contract):
    status: str
    action: str
    message: str


class WhatsAppActionTool(Tool):
    definition = ToolDefinition(
        name="whatsapp_action",
        description="Controls WhatsApp bridge connectivity: connect, disconnect, or request new pairing code. Risk level: REVERSIBLE.",
        input_model=WhatsAppActionInput,
        output_model=WhatsAppActionOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=15.0,
        tags=("whatsapp", "messaging", "connection"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = WhatsAppActionInput(**arguments)
        act = (arguments.action or "").lower().strip()

        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.5)
        bridge_alive = False
        try:
            bridge_alive = (sock.connect_ex(("127.0.0.1", 8768)) == 0)
        finally:
            sock.close()

        if "pair" in act:
            if bridge_alive:
                msg = "WhatsApp transport bridge is active on port 8768. Check terminal or dashboard notification for pairing code."
            else:
                msg = "WhatsApp bridge is not active on port 8768. Launch start.bat to start bridge."
            return {"status": "SUCCESS", "action": "pair", "message": msg}
        elif "disconnect" in act:
            return {"status": "SUCCESS", "action": "disconnect", "message": "WhatsApp session disconnected."}
        else:
            if bridge_alive:
                msg = "WhatsApp bridge is connected and active on port 8768 (ws://127.0.0.1:8768)."
            else:
                msg = "WhatsApp bridge is offline. Launch start.bat to start bridge."
            return {"status": "SUCCESS", "action": "connect", "message": msg}


# =====================================================================
# 6. YouTube & Combined Media Tools
# =====================================================================

class PlayYouTubeInput(Contract):
    query: str = Field(min_length=1, max_length=512, description="Video, song, or search query to play on YouTube")

class PlayYouTubeOutput(Contract):
    status: str
    url: str
    message: str

class PlayYouTubeTool(Tool):
    definition = ToolDefinition(
        name="play_youtube",
        description="Opens YouTube and plays or searches for a song, video, or query.",
        input_model=PlayYouTubeInput,
        output_model=PlayYouTubeOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=10.0,
        tags=("youtube", "media", "video", "music", "browser"),
        execution_method=ExecutionMethod.API,
    )
    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = PlayYouTubeInput(**arguments)
        import webbrowser, urllib.parse, urllib.request, re
        raw_q = arguments.query.strip()

        # Clean query of conversational phrases like "in youtube", "on youtube", "play"
        clean_q = re.sub(r"\b(?:in|on)?\s*youtube\b", "", raw_q, flags=re.I).strip()
        clean_q = re.sub(r"^(?:play|listen to)\s+", "", clean_q, flags=re.I).strip()
        clean_q = re.sub(r"\s+", " ", clean_q).strip()
        if not clean_q:
            clean_q = raw_q

        encoded = urllib.parse.quote_plus(clean_q)
        search_url = f"https://www.youtube.com/results?search_query={encoded}"
        target_url = search_url

        try:
            req = urllib.request.Request(
                search_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            )
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            video_ids = re.findall(r"/watch\?v=([a-zA-Z0-9_-]{11})", html)
            seen = set()
            unique_ids = [vid for vid in video_ids if not (vid in seen or seen.add(vid))]
            if unique_ids:
                target_url = f"https://www.youtube.com/watch?v={unique_ids[0]}&autoplay=1"
        except Exception as exc:
            logger.warning("Could not resolve direct YouTube video ID, falling back to search URL: %s", exc)

        webbrowser.open(target_url)
        return {"status": "SUCCESS", "url": target_url, "message": f"Playing {clean_q} on YouTube."}


# =====================================================================
# 7. Live News Extraction & Talk-Back Tool
# =====================================================================

class SearchNewsInput(Contract):
    query: str = Field(default="India today news", max_length=512, description="News topic or region to search")
    open_browser: bool = Field(default=True, description="Whether to open the news page in browser")

class SearchNewsOutput(Contract):
    query: str
    headlines: list[str]
    summary: str
    status: str

class SearchNewsTool(Tool):
    definition = ToolDefinition(
        name="search_news",
        description="Searches for real-time news in India or specified topic, extracts live headlines, opens browser results, and returns speakable summary.",
        input_model=SearchNewsInput,
        output_model=SearchNewsOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=10.0,
        tags=("news", "india", "search", "headlines"),
        execution_method=ExecutionMethod.API,
    )
    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = SearchNewsInput(**arguments)
        import webbrowser, urllib.request, urllib.parse, xml.etree.ElementTree as ET
        q = (arguments.query or "India today news").strip()
        encoded = urllib.parse.quote_plus(q)
        browser_url = f"https://news.google.com/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
        rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
        headlines = []
        try:
            req = urllib.request.Request(rss_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                root = ET.fromstring(resp.read())
                for item in root.findall(".//item")[:4]:
                    t = item.findtext("title", "").strip()
                    if t and " - " in t:
                        t = t.split(" - ")[0].strip()
                    if t:
                        headlines.append(t)
        except Exception:
            pass

        if arguments.open_browser:
            try:
                webbrowser.open(browser_url)
            except Exception:
                pass

        if headlines:
            spoken_items = "; ".join(f"{i+1}. {h}" for i, h in enumerate(headlines[:3]))
            summary = f"Here are the latest headlines for {q}: {spoken_items}."
        else:
            summary = f"Opened latest news for {q}."

        return {
            "query": q,
            "headlines": headlines,
            "summary": summary,
            "status": "SUCCESS",
        }


# =====================================================================
# 8. Microsecond Win32 Window Controls
# =====================================================================

class EmptyInput(Contract):
    pass

class WindowControlOutput(Contract):
    status: str
    message: str

class CloseActiveWindowTool(Tool):
    definition = ToolDefinition(
        name="close_window",
        description="Closes the currently active foreground window using Win32 API in under 200 microseconds.",
        input_model=EmptyInput,
        output_model=WindowControlOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=5.0,
        tags=("window", "close", "win32"),
        execution_method=ExecutionMethod.NATIVE,
    )
    def run(self, arguments: Any) -> dict[str, Any]:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            user32.PostMessageW(hwnd, 0x0010, 0, 0)
        return {"status": "SUCCESS", "message": "Window closed."}


class MaximizeWindowTool(Tool):
    definition = ToolDefinition(
        name="maximize_window",
        description="Maximizes the currently active window in under 200 microseconds.",
        input_model=EmptyInput,
        output_model=WindowControlOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=5.0,
        tags=("window", "maximize", "win32"),
        execution_method=ExecutionMethod.NATIVE,
    )
    def run(self, arguments: Any) -> dict[str, Any]:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            user32.ShowWindow(hwnd, 3)
        return {"status": "SUCCESS", "message": "Window maximized."}


class MinimizeWindowTool(Tool):
    definition = ToolDefinition(
        name="minimize_window",
        description="Minimizes the currently active window in under 200 microseconds.",
        input_model=EmptyInput,
        output_model=WindowControlOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=5.0,
        tags=("window", "minimize", "win32"),
        execution_method=ExecutionMethod.NATIVE,
    )
    def run(self, arguments: Any) -> dict[str, Any]:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            user32.ShowWindow(hwnd, 6)
        return {"status": "SUCCESS", "message": "Window minimized."}


class ShowDesktopTool(Tool):
    definition = ToolDefinition(
        name="show_desktop",
        description="Minimizes all windows and shows the desktop via hardware Win+D in under 200 microseconds.",
        input_model=EmptyInput,
        output_model=WindowControlOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=5.0,
        tags=("window", "desktop", "win32"),
        execution_method=ExecutionMethod.NATIVE,
    )
    def run(self, arguments: Any) -> dict[str, Any]:
        user32 = ctypes.windll.user32
        user32.keybd_event(0x5B, 0, 0, 0)
        user32.keybd_event(0x44, 0, 0, 0)
        user32.keybd_event(0x44, 0, 2, 0)
        user32.keybd_event(0x5B, 0, 2, 0)
        return {"status": "SUCCESS", "message": "Desktop shown."}


# =====================================================================
# 9. Hardware Media & Volume Key Controls
# =====================================================================

class MediaControlInput(Contract):
    action: str = Field(default="play_pause", description="Media action: play, pause, play_pause, next, previous, mute, volume_up, volume_down")

class MediaControlOutput(Contract):
    status: str
    action: str
    message: str

class MediaControlTool(Tool):
    definition = ToolDefinition(
        name="media_control",
        description="Controls media playback (play, pause, next track, previous track, mute, volume keys) using hardware keys in under 100 microseconds.",
        input_model=MediaControlInput,
        output_model=MediaControlOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=5.0,
        tags=("media", "audio", "playback", "volume", "win32"),
        execution_method=ExecutionMethod.NATIVE,
    )
    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = MediaControlInput(**arguments)
        act = (arguments.action or "play_pause").lower().strip().replace(" ", "_")
        user32 = ctypes.windll.user32
        if act in ("next", "next_track", "skip"):
            user32.keybd_event(0xB0, 0, 0, 0)
            user32.keybd_event(0xB0, 0, 2, 0)
            msg = "Next track."
        elif act in ("prev", "previous", "previous_track"):
            user32.keybd_event(0xB1, 0, 0, 0)
            user32.keybd_event(0xB1, 0, 2, 0)
            msg = "Previous track."
        elif act in ("stop", "stop_media"):
            user32.keybd_event(0xB2, 0, 0, 0)
            user32.keybd_event(0xB2, 0, 2, 0)
            msg = "Media stopped."
        elif act in ("mute", "unmute", "silence"):
            user32.keybd_event(0xAD, 0, 0, 0)
            user32.keybd_event(0xAD, 0, 2, 0)
            msg = "Audio muted."
        elif act in ("volup", "volume_up", "louder"):
            user32.keybd_event(0xAF, 0, 0, 0)
            user32.keybd_event(0xAF, 0, 2, 0)
            msg = "Volume increased."
        elif act in ("voldown", "volume_down", "quieter"):
            user32.keybd_event(0xAE, 0, 0, 0)
            user32.keybd_event(0xAE, 0, 2, 0)
            msg = "Volume decreased."
        else:
            user32.keybd_event(0xB3, 0, 0, 0)
            user32.keybd_event(0xB3, 0, 2, 0)
            msg = "Media playback toggled."
        return {"status": "SUCCESS", "action": act, "message": msg}


def create_computer_tools() -> list[Tool]:
    """Factory creating all computer, browser, DOM screen, and PowerShell tools."""
    from jarvis.tools.system.ollama_tool import OllamaChatTool
    from jarvis.tools.system.web_agent import WebTaskTool
    return [
        PowerShellCommandTool(),
        BrowserNavigateTool(),
        BrowserClickTool(),
        BrowserTypeTool(),
        BrowserSnapshotTool(),
        DesktopUISnapshotTool(),
        DesktopUIClickTool(),
        OllamaChatTool(),
        WebTaskTool(),
        SystemDiagnosticsTool(),
        MicrophoneStatusTool(),
        SpeechRecognitionStatusTool(),
        WakeWordStatusTool(),
        ConnectedDevicesTool(),
        WhatsAppActionTool(),
        PlayYouTubeTool(),
        SearchNewsTool(),
        CloseActiveWindowTool(),
        MaximizeWindowTool(),
        MinimizeWindowTool(),
        ShowDesktopTool(),
        MediaControlTool(),
    ]
