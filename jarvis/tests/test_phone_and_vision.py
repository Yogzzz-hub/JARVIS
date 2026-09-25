"""Laptop -> phone control (notifications, tap by label, toggles) and screen understanding."""
from __future__ import annotations

import pytest

from jarvis.connectors.android.scrcpy import find_ui_node, parse_notifications

DUMPSYS = """
  NotificationRecord(0x0a1b2c3d: pkg=com.whatsapp user=UserHandle{0} id=1 tag=null importance=4 key=0|com.whatsapp|1|null|10123: Notification(channel=individual_chat_defaults_3 ...))
      extras={
        android.title=String (Rahul)
        android.text=String (Are you coming for lunch?)
      }
  NotificationRecord(0x0a1b2c3e: pkg=com.google.android.gm user=UserHandle{0} id=2 tag=null importance=3)
      extras={
        android.title=String (Amazon)
        android.text=String (Your order has shipped)
        android.bigText=String (Your order #402 has shipped and arrives Friday)
      }
  NotificationRecord(0x0a1b2c3f: pkg=com.android.systemui user=UserHandle{0} id=3)
        android.title=String (USB debugging connected)
"""

UI_XML = """<?xml version='1.0' encoding='UTF-8'?><hierarchy rotation="0">
<node index="0" text="" content-desc="" bounds="[0,0][1080,2400]">
<node index="1" text="Network &amp; internet" content-desc="" bounds="[0,300][1080,420]" />
<node index="2" text="Settings" content-desc="" bounds="[40,120][400,200]" />
<node index="3" text="" content-desc="Send" bounds="[960,2200][1060,2300]" />
<node index="4" text="Allow" content-desc="" bounds="[600,1500][900,1600]" />
</node></hierarchy>"""


def test_phone_notifications_are_parsed():
    items = parse_notifications(DUMPSYS)
    assert items[0] == {"app": "com.whatsapp", "title": "Rahul", "text": "Are you coming for lunch?"}
    assert items[1]["text"] == "Your order #402 has shipped and arrives Friday"
    assert all(i["app"] != "com.android.systemui" for i in items)


@pytest.mark.parametrize("label,center", [
    ("settings", (220, 160)),
    ("send", (1010, 2250)),
    ("allow", (750, 1550)),
    ("network and internet", (540, 360)),
])
def test_tap_target_is_found_by_label(label, center):
    x, y, _shown = find_ui_node(UI_XML, label)
    assert (x, y) == center


def test_unknown_label_is_not_tapped():
    assert find_ui_node(UI_XML, "delete everything") is None


@pytest.mark.asyncio
async def test_describe_screen_sends_the_image_to_the_vision_model():
    from jarvis.tests.fake_ollama import FakeOllama
    from jarvis.tools.system.vision_tools import DescribeScreenTool

    fake = FakeOllama(models=["llama3.2:latest", "qwen2.5vl:3b"],
                      responder=lambda p: "The dialog says: Error 0x80070005 - Access is denied.")
    client = fake.client(vision_model="qwen2.5vl:3b")
    tool = DescribeScreenTool(client=client, capture=lambda device: "aW1hZ2U=")
    try:
        res = await tool.run({"question": "what is this error?", "device": "pc"})
    finally:
        await client.aclose()
    assert res["success"] and "0x80070005" in res["message"]
    sent = fake.chat_payloads()[-1]
    assert sent["model"] == "qwen2.5vl:3b" and sent["messages"][0]["images"] == ["aW1hZ2U="]


@pytest.mark.asyncio
async def test_describe_screen_without_vision_model_says_how_to_fix():
    from jarvis.tests.fake_ollama import FakeOllama
    from jarvis.tools.system.vision_tools import DescribeScreenTool

    fake = FakeOllama(models=["nomic-embed-text:latest"], responder=lambda p: "x")
    client = fake.client()
    try:
        res = await DescribeScreenTool(client=client, capture=lambda d: "aW1n").run({})
    finally:
        await client.aclose()
    assert not res["success"] and "ollama pull" in res["message"]


@pytest.mark.asyncio
@pytest.mark.parametrize("text,intent,slots", [
    ("read my phone notifications", "android_notifications", {}),
    ("turn off bluetooth on my phone", "android_toggle", {"setting": "bluetooth", "on": False}),
    ("enable airplane mode on my phone", "android_toggle", {"setting": "airplane_mode", "on": True}),
    ("tap settings on my phone", "android_tap_text", {"text": "settings"}),
    ("what is on my phone screen", "describe_screen", {"device": "phone"}),
    ("what is this error on my screen", "describe_screen", {"device": "pc"}),
    ("look at my screen and tell me what is wrong", "describe_screen", {"device": "pc"}),
    ("send a notification to my phone saying meeting at 5", "notification_send", {"message": "meeting at 5"}),
])
async def test_phone_and_screen_requests_route(text, intent, slots):
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter
    from jarvis.memory.working_memory import WorkingMemory

    dec = await SmartRouter(llm_provider=DisabledProvider(), working_memory=WorkingMemory()).route(text)
    assert dec.intent == intent, (text, dec)
    for k, v in slots.items():
        assert dec.slots.get(k) == v


class FakeAdbConnector:
    """The real connector's pull/push logic with a scripted `adb`."""

    def __init__(self, tmp_path, listing):
        from jarvis.connectors.android.scrcpy import AndroidScrcpyConnector as ScrcpyConnector

        self.conn = ScrcpyConnector.__new__(ScrcpyConnector)
        self.conn.adb_bin = "adb"
        self.conn.device_id = None
        self.calls = []
        self.listing = listing

        def run_adb(args, timeout=5.0):
            self.calls.append(args)
            if args[:2] == ["shell", "ls"]:
                return 0, "\n".join(self.listing.get(args[-1], [])), ""
            if args[:2] == ["shell", "find"]:
                return 0, "/sdcard/Download/My Resume.pdf\n/sdcard/Android/data/x/resume.pdf", ""
            if args[0] == "pull":
                from pathlib import Path
                Path(args[2]).write_bytes(b"x")
                return 0, "1 file pulled", ""
            return 0, "", ""

        self.conn._run_adb = run_adb


def test_pull_newest_screenshots_and_named_files(tmp_path):
    fake = FakeAdbConnector(tmp_path, {"/sdcard/Pictures/Screenshots": ["Screenshot_3.png", "Screenshot_2.png", "notes.txt", "Screenshot_1.png"]})
    res = fake.conn.execute_authorized_action("a", "pull", {"kind": "screenshot", "count": 2, "destination": str(tmp_path)})
    assert res["success"] and [p.split("/")[-1].split("\\")[-1] for p in res["files"]] == ["Screenshot_3.png", "Screenshot_2.png"]

    res = fake.conn.execute_authorized_action("a", "pull", {"name": "resume", "destination": str(tmp_path)})
    assert res["files"] and res["files"][0].endswith("My Resume.pdf"), "app-private folders are skipped"

    with pytest.raises(ValueError):
        fake.conn.execute_authorized_action("a", "pull", {"name": "x; rm -rf /", "destination": str(tmp_path)})


def test_push_copies_to_phone_downloads(tmp_path):
    fake = FakeAdbConnector(tmp_path, {})
    f = tmp_path / "report.pdf"
    f.write_bytes(b"pdf")
    res = fake.conn.execute_authorized_action("a", "push", {"path": str(f)})
    assert res["success"] and ["push", str(f), "/sdcard/Download/report.pdf"] in fake.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("text,intent,slots", [
    ("get the latest photo from my phone", "android_pull_file", {"kind": "photo", "count": 1}),
    ("copy my last 3 screenshots from my phone to my laptop", "android_pull_file", {"kind": "screenshot", "count": 3}),
    ("copy resume.pdf from my phone", "android_pull_file", {"name": "resume.pdf"}),
    ("copy report.pdf to my phone", "android_push_file", {"path": "report.pdf"}),
    ("send this file to my phone", "localsend_file", {}),
])
async def test_phone_transfer_routing(text, intent, slots):
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter
    from jarvis.memory.working_memory import WorkingMemory

    dec = await SmartRouter(llm_provider=DisabledProvider(), working_memory=WorkingMemory()).route(text)
    assert dec.intent == intent, (text, dec)
    for k, v in slots.items():
        assert dec.slots.get(k) == v
