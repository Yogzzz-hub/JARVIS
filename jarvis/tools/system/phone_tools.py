"""Android phone control tools (ADB): keys, typing/tapping, URLs, dialer, screenshots.

All actions go through the Android connector, which never runs arbitrary shell commands:
every ADB invocation is a fixed, validated template.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Literal, Optional

from pydantic import Field

from jarvis.config import ROOT
from jarvis.connectors.manager import get_connector_manager
from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition

logger = logging.getLogger("jarvis.tools.phone")

PhoneKey = Literal[
    "home", "back", "volume_up", "volume_down", "volume_mute", "power", "sleep", "wakeup", "camera",
    "media_play_pause", "media_next", "media_previous", "app_switch", "enter", "notifications",
    "brightness_up", "brightness_down",
]


class PhoneResult(Contract):
    success: bool
    message: str
    data: dict = Field(default_factory=dict)


def _android():
    connector = get_connector_manager().get_connector("android")
    if connector is None:
        raise RuntimeError("The Android connector is disabled. Enable [connectors.android] in config/connectors.toml.")
    if not getattr(connector, "adb_bin", None):
        raise RuntimeError("ADB was not found. Install Android platform-tools and connect your phone with USB debugging.")
    return connector


def _run(operation: str, **kwargs: Any) -> dict[str, Any]:
    res = _android().execute(operation, **kwargs)
    return {"success": bool(res.get("success", True)), "message": res.get("message", "Done on the phone."), "data": {k: v for k, v in res.items() if k not in ("message",)}}


class PhoneKeyInput(Contract):
    key: PhoneKey = Field(description="Phone key to press: volume_up, volume_down, volume_mute, sleep (lock), wakeup, media_play_pause, media_next, media_previous, home, back, app_switch, camera, power")
    times: int = Field(default=1, ge=1, le=10, description="How many times to press it")


class PhoneKeyTool(Tool):
    definition = ToolDefinition(
        name="android_key",
        description="Presses a key on the connected Android phone: volume up/down/mute, lock (sleep) or wake the screen, play/pause/next/previous media, home, back, recent apps, camera.",
        input_model=PhoneKeyInput,
        output_model=PhoneResult,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=15.0,
        tags=("android", "phone", "mobile", "key", "volume", "media", "lock"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = PhoneKeyInput(**arguments)
        result = {}
        for _ in range(arguments.times):
            result = _run("key", key=arguments.key)
        spoken = {"sleep": "Your phone is locked.", "wakeup": "Your phone screen is on.", "volume_up": "Phone volume up.",
                  "volume_down": "Phone volume down.", "volume_mute": "Phone muted.", "media_play_pause": "Toggled playback on your phone.",
                  "media_next": "Skipped to the next track on your phone.", "media_previous": "Went back a track on your phone."}
        result["message"] = spoken.get(arguments.key, result.get("message", "Done."))
        return result


class PhoneInputInput(Contract):
    action: Literal["text", "tap", "swipe"] = Field(description="text = type text, tap = tap at x,y, swipe = swipe up/down/left/right")
    text: str = Field(default="", max_length=500, description="Text to type (for action=text)")
    x: Optional[int] = Field(default=None, ge=0, le=5000, description="Tap X coordinate")
    y: Optional[int] = Field(default=None, ge=0, le=5000, description="Tap Y coordinate")
    direction: Literal["up", "down", "left", "right"] = "up"


class PhoneInputTool(Tool):
    definition = ToolDefinition(
        name="android_input",
        description="Types text into the focused field on the phone, taps a screen position, or swipes up/down/left/right.",
        input_model=PhoneInputInput,
        output_model=PhoneResult,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=15.0,
        tags=("android", "phone", "type", "tap", "swipe"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = PhoneInputInput(**arguments)
        if arguments.action == "tap" and (arguments.x is None or arguments.y is None):
            raise ValueError("Tap needs x and y coordinates")
        result = _run("input", action=arguments.action, text=arguments.text, x=arguments.x, y=arguments.y, direction=arguments.direction)
        if arguments.action == "text":
            result["message"] = "Typed it on your phone."
        elif arguments.action == "swipe":
            result["message"] = f"Swiped {arguments.direction} on your phone."
        return result


class PhoneUrlInput(Contract):
    url: str = Field(min_length=3, max_length=2048, description="Web address to open on the phone")


class PhoneOpenUrlTool(Tool):
    definition = ToolDefinition(
        name="android_open_url",
        description="Opens a web page on the connected Android phone's browser.",
        input_model=PhoneUrlInput,
        output_model=PhoneResult,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=15.0,
        tags=("android", "phone", "browser", "url"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = PhoneUrlInput(**arguments)
        return _run("open_url", url=arguments.url)


class PhoneDialInput(Contract):
    number: str = Field(min_length=1, max_length=64, description="Phone number or contact name to dial")


class PhoneDialTool(Tool):
    definition = ToolDefinition(
        name="android_dial",
        description="Opens the phone's dialer with a number or a saved contact's number ready to call (you tap call).",
        input_model=PhoneDialInput,
        output_model=PhoneResult,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=15.0,
        tags=("android", "phone", "call", "dial"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = PhoneDialInput(**arguments)
        target = arguments.number.strip()
        digits = re.sub(r"[^\d+]", "", target)
        name = ""
        if len(re.sub(r"\D", "", digits)) < 6:
            from jarvis.integrations.whatsapp.contact_resolver import ContactResolver
            contact, ambiguous, prompt = ContactResolver().resolve(target)
            if ambiguous:
                raise ValueError(prompt or f"Several contacts match {target}.")
            if not contact:
                raise ValueError(f"I don't have a phone number for {target}.")
            name = contact.display_name
            digits = re.sub(r"[^\d+]", "", contact.phone_number or "+" + contact.jid.split("@")[0])
        result = _run("dial", number=digits)
        if name:
            result["message"] = f"Dialer opened for {name} on your phone. Tap call to connect."
        return result


class PhoneScreenshotInput(Contract):
    pass


class PhoneScreenshotTool(Tool):
    definition = ToolDefinition(
        name="android_screenshot",
        description="Takes a screenshot of the connected Android phone's screen and saves it on the PC.",
        input_model=PhoneScreenshotInput,
        output_model=PhoneResult,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=20.0,
        tags=("android", "phone", "screenshot", "capture"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        dest = ROOT / "screenshots" / f"phone_{time.strftime('%Y%m%d_%H%M%S')}.png"
        res = _android().execute("capture_state", destination=str(dest))
        return {"success": True, "message": "Saved a screenshot of your phone.", "data": {"path": res.get("path", str(dest)), "bytes": res.get("bytes", 0)}}


def create_phone_tools() -> list[Tool]:
    return [PhoneKeyTool(), PhoneInputTool(), PhoneOpenUrlTool(), PhoneDialTool(), PhoneScreenshotTool()]
