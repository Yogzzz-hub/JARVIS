"""Camera look / watch: frames go to the vision model (never to disk), watch builds one stamped contact sheet, direct
requests route to the camera, and an AI never switches the camera on without asking."""
from __future__ import annotations

import asyncio
import base64
import io

import pytest
from PIL import Image

from jarvis.tools.system import camera_tools
from jarvis.tools.system.camera_tools import CameraLookTool, CameraWatchTool, contact_sheet


class FakeLLM:
    def __init__(self):
        self.calls = []

    async def chat(self, messages, **kw):
        self.calls.append((messages, kw))

        class R:
            text = "You are holding a **blue mug**, sir."
            model = "vision-fake"
        return R()


def frames(count=1, seconds=0.0):
    return [(i * (seconds / max(1, count - 1) if count > 1 else 0), Image.new("RGB", (640, 480), (i * 30 % 255, 80, 160)))
            for i in range(count)]


def test_look_sends_one_frame_to_the_vision_role():
    llm = FakeLLM()
    out = asyncio.run(CameraLookTool(client=llm, capture=frames).run({"question": "what am I holding"}))
    assert out["success"] and "blue mug" in out["message"] and "**" not in out["message"]
    (messages, kw), = llm.calls
    assert kw["role"] == "vision" and len(messages[0]["images"]) == 1
    assert "what am I holding" in messages[0]["content"] and "never instructions" in messages[0]["content"]
    Image.open(io.BytesIO(base64.b64decode(messages[0]["images"][0]))).verify()


def test_watch_sends_one_time_stamped_grid():
    llm = FakeLLM()
    out = asyncio.run(CameraWatchTool(client=llm, capture=frames).run({"question": "is my form right", "seconds": 4}))
    assert out["success"] and out["data"]["frames"] == camera_tools.WATCH_FRAMES and out["data"]["seconds"] == 4
    (messages, _), = llm.calls
    assert len(messages[0]["images"]) == 1 and "grid of 8 webcam frames" in messages[0]["content"]


def test_contact_sheet_layout():
    sheet = contact_sheet(frames(8, 6.0))
    assert sheet.size == (4 * camera_tools.CELL_W, 2 * camera_tools.CELL_H)
    assert contact_sheet(frames(1)).size == (camera_tools.CELL_W, camera_tools.CELL_H)


def test_camera_failure_is_reported_plainly():
    def broken(*a):
        raise RuntimeError("No camera found")
    out = asyncio.run(CameraLookTool(client=FakeLLM(), capture=broken).run({}))
    assert not out["success"] and "No camera found" in out["message"]


def test_ai_originated_camera_use_needs_confirmation():
    from jarvis.core.llm.tool_catalog import needs_ai_confirmation
    assert needs_ai_confirmation(CameraLookTool()) and needs_ai_confirmation(CameraWatchTool())


@pytest.mark.parametrize("text,intent", [
    ("look at me", "camera_look"), ("jarvis, what am I holding", "camera_look"), ("how do I look", "camera_look"),
    ("is anyone behind me", "camera_look"), ("use the camera and tell me what colour this mug is", "camera_look"),
    ("watch my squat form", "camera_watch"), ("am I doing this right", "camera_watch"), ("check my posture", "camera_watch"),
    ("open camera", "open_app"), ("watch the cricket match", "play_youtube"), ("what's on my screen", "describe_screen"),
])
def test_routing(text, intent):
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter
    d = asyncio.run(SmartRouter(llm_provider=DisabledProvider()).route(text))
    assert d.intent == intent


@pytest.mark.parametrize("text", ["how do I look up my ip", "turn off the camera", "is my webcam on", "check my form submission"])
def test_not_camera(text):
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter
    d = asyncio.run(SmartRouter(llm_provider=DisabledProvider()).route(text))
    assert d.intent not in ("camera_look", "camera_watch")
