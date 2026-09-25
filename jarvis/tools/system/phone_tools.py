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


class PhoneNotificationsInput(Contract):
    limit: int = Field(default=10, ge=1, le=30, description="How many notifications to read")


class PhoneNotificationsTool(Tool):
    definition = ToolDefinition(
        name="android_notifications",
        description="Reads the notifications currently showing on the connected Android phone (app, title, text).",
        input_model=PhoneNotificationsInput,
        output_model=PhoneResult,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=20.0,
        tags=("android", "phone", "notifications", "read"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = PhoneNotificationsInput(**arguments)
        res = _android().execute("notifications", limit=arguments.limit)
        items = res.get("notifications", [])
        if not items:
            return {"success": True, "message": "There are no notifications on your phone.", "data": {"notifications": []}}
        parts = []
        for it in items[:6]:
            app = it["app"].split(".")[-1].replace("android", "").strip() or it["app"]
            body = f"{it['title']}: {it['text']}" if it.get("title") and it.get("text") else (it.get("title") or it.get("text"))
            parts.append(f"{app.title()} - {body}")
        more = f" and {len(items) - 6} more" if len(items) > 6 else ""
        return {"success": True, "message": f"{len(items)} notification{'s' if len(items) != 1 else ''} on your phone: " + "; ".join(parts) + more + ".",
                "data": {"notifications": items}}


class PhoneTapTextInput(Contract):
    text: str = Field(min_length=1, max_length=120, description="Label of the button / item to tap on the phone screen, e.g. 'Settings', 'Send', 'Allow'")


class PhoneTapTextTool(Tool):
    definition = ToolDefinition(
        name="android_tap_text",
        description="Taps the button or item with the given label on the phone's current screen (reads the screen, finds the label, taps it).",
        input_model=PhoneTapTextInput,
        output_model=PhoneResult,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=25.0,
        tags=("android", "phone", "tap", "click", "press", "button"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = PhoneTapTextInput(**arguments)
        res = _android().execute("tap_text", text=arguments.text)
        return {"success": bool(res.get("success")), "message": res.get("message", ""), "data": {k: v for k, v in res.items() if k in ("x", "y")}}


PhoneSetting = Literal["wifi", "bluetooth", "mobile_data", "airplane_mode", "do_not_disturb", "auto_rotate"]


class PhoneToggleInput(Contract):
    setting: PhoneSetting = Field(description="wifi, bluetooth, mobile_data, airplane_mode, do_not_disturb or auto_rotate")
    on: bool = Field(default=True, description="true = turn on, false = turn off")


class PhoneToggleTool(Tool):
    definition = ToolDefinition(
        name="android_toggle",
        description="Turns a phone setting on or off: Wi-Fi, Bluetooth, mobile data, airplane mode, do not disturb, auto-rotate.",
        input_model=PhoneToggleInput,
        output_model=PhoneResult,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=20.0,
        tags=("android", "phone", "wifi", "bluetooth", "settings", "toggle"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = PhoneToggleInput(**arguments)
        res = _android().execute("toggle", setting=arguments.setting, on=arguments.on)
        return {"success": True, "message": res.get("message", "Done on the phone."), "data": {}}


def create_phone_tools() -> list[Tool]:
    return [PhoneKeyTool(), PhoneInputTool(), PhoneOpenUrlTool(), PhoneDialTool(), PhoneScreenshotTool(),
            PhoneNotificationsTool(), PhoneTapTextTool(), PhoneToggleTool()]
