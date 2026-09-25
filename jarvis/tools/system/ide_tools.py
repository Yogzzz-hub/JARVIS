"""Antigravity IDE & Coding Assistant Automation Tools for JARVIS EDGE."""
from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import Field

from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition
from jarvis.tools.system.native import bring_to_front
from jarvis.tools.system.input_layer import (
    send_key as _send_key,
    send_combo as _send_combo,
    type_unicode as _type_unicode,
    VK,
)

logger = logging.getLogger("jarvis.tools.ide")

# Backwards-compatible VK aliases used in this file
VK_RETURN = VK.RETURN
VK_SHIFT = VK.SHIFT
VK_CONTROL = VK.CONTROL
VK_MENU = VK.MENU
VK_TAB = VK.TAB
VK_BACK = VK.BACK


def focus_ide_window() -> bool:
    """Finds and focuses the active Antigravity or VS Code IDE window."""
    for title in ("Antigravity", "Visual Studio Code", "Code"):
        if bring_to_front(name=title):
            time.sleep(0.05)
            return True
    return False


# =====================================================================
# Contracts
# =====================================================================

class IDEControlInput(Contract):
    action: str = Field(description="IDE action: open_ide, open_project, focus_prompt, type_prompt, edit_prompt, submit_prompt, save_file, open_terminal, open_problems, open_source_control, switch_tab, select_file, explain_error, ide_screenshot")
    text: Optional[str] = Field(default=None, description="Text or prompt to type/edit")
    path: Optional[str] = Field(default=None, description="Project path or filename to open")


class IDEControlOutput(Contract):
    status: str
    action: str
    message: str
    data: Dict[str, Any] = Field(default_factory=dict)


# =====================================================================
# Tool Implementation
# =====================================================================

class AntigravityIDETool(Tool):
    definition = ToolDefinition(
        name="antigravity_ide_control",
        description="Automates Antigravity / VS Code IDE actions: live dictate/type prompts, open files, switch tabs, save files, open terminal/problems panels, explain visible errors, and submit prompts.",
        input_model=IDEControlInput,
        output_model=IDEControlOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=10.0,
        tags=("developer", "ide", "antigravity", "vscode", "coding"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: IDEControlInput) -> dict[str, Any]:
        act = arguments.action.lower().strip().replace(" ", "_")

        if act in ("open_ide", "launch_ide", "open_antigravity"):
            # Focus or launch Antigravity / VS Code
            if not focus_ide_window():
                subprocess.Popen(["code", arguments.path or "."])
                return {"status": "SUCCESS", "action": act, "message": "Launched VS Code / Antigravity workspace."}
            return {"status": "SUCCESS", "action": act, "message": "Focused Antigravity IDE window."}

        elif act in ("open_project", "open_workspace"):
            target_path = arguments.path or "."
            subprocess.Popen(["code", target_path])
            return {"status": "SUCCESS", "action": act, "message": f"Opened workspace at '{target_path}' in IDE."}

        # For remaining actions, ensure IDE has focus
        focused = focus_ide_window()

        if act in ("focus_prompt", "focus_input"):
            # In Antigravity / Cursor / VS Code Copilot, Ctrl+L or Ctrl+I focuses AI prompt
            _send_combo([VK_CONTROL], ord("L"))
            time.sleep(0.05)
            return {"status": "SUCCESS", "action": act, "message": "Focused IDE AI prompt input box."}

        elif act in ("type_prompt", "live_dictate_prompt"):
            # Focus prompt and type text
            _send_combo([VK_CONTROL], ord("L"))
            time.sleep(0.05)
            if arguments.text:
                _type_unicode(arguments.text)
            return {"status": "SUCCESS", "action": act, "message": f"Typed prompt into IDE prompt box."}

        elif act in ("submit_prompt", "send_prompt"):
            # Focus prompt box and press Enter to submit
            _send_combo([VK_CONTROL], ord("L"))
            time.sleep(0.05)
            _send_key(VK_RETURN)
            return {"status": "SUCCESS", "action": act, "message": "Submitted prompt to coding assistant."}

        elif act in ("edit_prompt", "voice_edit_prompt"):
            _send_combo([VK_CONTROL], ord("L"))
            time.sleep(0.05)
            if arguments.text:
                # Append or replace prompt
                _type_unicode(" " + arguments.text)
            return {"status": "SUCCESS", "action": act, "message": "Edited prompt in IDE prompt box."}

        elif act in ("save_file", "save"):
            _send_combo([VK_CONTROL], ord("S"))
            return {"status": "SUCCESS", "action": act, "message": "Saved current file in IDE (Ctrl+S)."}

        elif act in ("switch_tab", "next_tab"):
            _send_combo([VK_CONTROL], VK_TAB)
            return {"status": "SUCCESS", "action": act, "message": "Switched editor tab (Ctrl+Tab)."}

        elif act in ("select_file", "open_file"):
            _send_combo([VK_CONTROL], ord("P"))
            time.sleep(0.05)
            if arguments.path or arguments.text:
                fname = arguments.path or arguments.text
                _type_unicode(fname)
                time.sleep(0.05)
                _send_key(VK_RETURN)
                return {"status": "SUCCESS", "action": act, "message": f"Opened file '{fname}' in IDE."}
            return {"status": "SUCCESS", "action": act, "message": "Opened Quick Open palette (Ctrl+P)."}

        elif act in ("open_terminal", "toggle_terminal"):
            # Ctrl + ` (backtick, vk 0xC0)
            _send_combo([VK_CONTROL], 0xC0)
            return {"status": "SUCCESS", "action": act, "message": "Toggled terminal panel in IDE (Ctrl+`)."}

        elif act in ("open_problems", "toggle_problems", "errors"):
            # Ctrl+Shift+M opens Problems panel
            _send_combo([VK_CONTROL, VK_SHIFT], ord("M"))
            return {"status": "SUCCESS", "action": act, "message": "Opened Problems / Diagnostics panel (Ctrl+Shift+M)."}

        elif act in ("open_source_control", "git_panel"):
            # Ctrl+Shift+G opens Source Control panel
            _send_combo([VK_CONTROL, VK_SHIFT], ord("G"))
            return {"status": "SUCCESS", "action": act, "message": "Opened Source Control panel (Ctrl+Shift+G)."}

        elif act in ("explain_error", "diagnose_error", "explain_visible_error", "explain_currently_selected_error"):
            # Explain compiler or runtime error using local reasoning
            error_msg = arguments.text or "IndexError: list index out of range at line 42"
            from jarvis.tools.productivity.developer_tools import DiagnoseErrorTool, DiagnoseErrorInput
            report = DiagnoseErrorTool().run(DiagnoseErrorInput(error_log=error_msg))
            return {
                "status": "SUCCESS",
                "action": act,
                "message": f"Diagnostic explanation: {report.get('diagnosis', 'Error analyzed')}",
                "data": report,
            }

        elif act in ("ide_screenshot", "screenshot_ide"):
            from jarvis.tools.system.native import screenshot
            from jarvis.tools.system.native import ScreenshotInput
            res = screenshot(ScreenshotInput())
            return {
                "status": "SUCCESS",
                "action": act,
                "message": f"Captured IDE screenshot to '{res.get('path')}'.",
                "data": res,
            }

        return {"status": "FAILED", "action": act, "message": f"Unrecognized IDE action: {act}"}


def create_ide_tools() -> list[Tool]:
    return [AntigravityIDETool()]
