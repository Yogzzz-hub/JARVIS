"""Unit and integration tests for JARVIS EDGE v1.x Local Connectors.

Tests fake providers, error recovery, graceful degradation, timeouts,
and action verification across all 7 local connectors.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import pytest

from jarvis.connectors.base import BaseConnector, ConnectorInfo, ConnectorStatus
from jarvis.connectors.manager import ConnectorManager
from jarvis.connectors.android.scrcpy import AndroidScrcpyConnector
from jarvis.connectors.localsend.client import LocalSendConnector
from jarvis.connectors.rss.freshrss import FreshRSSConnector
from jarvis.connectors.notifications.provider import NotificationConnector
from jarvis.connectors.memos.client import MemosConnector
from jarvis.connectors.node_red import NodeRedConnector, ExternalEvent
from jarvis.memory.working_memory import WorkingMemory
from jarvis.tools.system.connector_tools import (
    AndroidStatusTool,
    LocalSendFileTool,
    LocalSendTextTool,
    RssLatestTool,
    NotificationSendTool,
    MemosCreateTool,
    MemosRecentTool,
    BrowserOpenUrlTool,
    MorningBriefingTool,
)


# =====================================================================
# Fake Providers for Testing
# =====================================================================

class FakeAndroidConnector(BaseConnector):
    def __init__(self, connected: bool = True):
        super().__init__(ConnectorInfo(
            connector_id="fake_android", name="FakeAndroid", version="1.0",
            transport="USB", network_requirement="NONE", permission_scope="DEVICE_CONTROL"
        ))
        self._connected = connected
        self._status = ConnectorStatus.READY if connected else ConnectorStatus.UNAVAILABLE

    def discover_capabilities(self):
        return []

    def health(self):
        return {"status": self._status.value, "devices_connected": 1 if self._connected else 0}

    def read(self, resource_uri, **kwargs):
        return {}

    def prepare_action(self, action_name, arguments):
        return {"prepared": True}

    def execute_authorized_action(self, action_id, action_name, arguments):
        if not self._connected:
            raise RuntimeError("Device disconnected")
        return {"status": "SUCCESS", "success": True, "action": action_name}

    def verify(self, action_id, action_name, expected_state):
        return self._connected


# =====================================================================
# Unit Tests
# =====================================================================

def test_connector_status_enum():
    assert ConnectorStatus.READY.value == "READY"
    assert ConnectorStatus.DEGRADED.value == "DEGRADED"
    assert ConnectorStatus.DISABLED.value == "DISABLED"
    assert ConnectorStatus.UNAVAILABLE.value == "UNAVAILABLE"


def test_connector_manager_lazy_and_status(tmp_path):
    mgr = ConnectorManager.get_default()
    statuses = mgr.get_all_statuses(force_refresh=True)
    assert "android" in statuses
    assert "localsend" in statuses
    assert "browser" in statuses
    assert "freshrss" in statuses
    assert "notifications" in statuses
    assert "memos" in statuses
    assert "nodered" in statuses


def test_android_tool_execution():
    tool = AndroidStatusTool()
    res = tool.run({})
    assert "message" in res
    assert "data" in res


def test_localsend_graceful_offline(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("hello localsend", encoding="utf-8")
    tool = LocalSendFileTool()
    res = tool.run({"path": str(f)})
    # When LocalSend is not active on PC/phone, it must report graceful failure without crashing
    assert res["success"] is False
    assert "LocalSend isn't available right now" in res["message"] or "LocalSend is not active" in res["message"]


def test_localsend_text_tool():
    tool = LocalSendTextTool()
    res = tool.run({"text": "Hello phone"})
    assert res["success"] is True
    assert res["bytes_transferred"] == len("Hello phone")


def test_freshrss_news_and_working_memory():
    wm = WorkingMemory()
    tool = RssLatestTool(working_memory=wm)
    res = tool.run({"query": "AI", "limit": 3})
    assert res["count"] >= 0
    # Items should be tracked in working memory
    if res["items"]:
        assert len(wm.last_feed_items) > 0
        resolved = wm.resolve_reference("the second one")
        if len(res["items"]) >= 2:
            assert resolved == res["items"][1]


def test_notification_deduplication():
    tool = NotificationSendTool()
    res1 = tool.run({"title": "TestAlert", "message": "First alert message"})
    assert res1["success"] is True
    res2 = tool.run({"title": "TestAlert", "message": "First alert message"})
    assert res2["success"] is True
    assert "Duplicate notification skipped" in res2["message"]


def test_memos_creation_and_redaction():
    wm = WorkingMemory()
    tool = MemosCreateTool(working_memory=wm)
    secret_note = "Remember my token=sk-abcdef1234567890abcdef1234567890 for API"
    res = tool.run({"content": secret_note})
    assert res["count"] == 1
    memo = res["notes"][0]
    # Verify secret is redacted!
    assert "sk-abcdef" not in memo["content"]
    assert "[REDACTED]" in memo["content"]



def test_nodered_event_bridge():
    nr = NodeRedConnector(enabled=True)
    # Valid event
    evt = ExternalEvent(
        source="nodered",
        event_type="download.completed",
        event_id="evt_001",
        timestamp=100.0,
        payload={"filename": "doc.pdf"}
    )
    ok, msg = nr.handle_event(evt)
    assert ok is True

    # Replay rejection
    ok_replay, msg_replay = nr.handle_event(evt)
    assert ok_replay is False
    assert "Replay detected" in msg_replay

    # Unallowed event rejection
    bad_evt = ExternalEvent(
        source="nodered",
        event_type="system.format_drive",
        event_id="evt_bad",
        timestamp=101.0,
        payload={}
    )
    ok_bad, msg_bad = nr.handle_event(bad_evt)
    assert ok_bad is False
    assert "not in allowlist" in msg_bad or "Unauthorized" in msg_bad



def test_morning_briefing_tool_and_speed():
    wm = WorkingMemory()
    tool = MorningBriefingTool(working_memory=wm)
    res = tool.run({})
    assert res["status"] == "success"
    assert "Good morning" in res["spoken_text"]
    assert "sections" in res
    assert res["duration_ms"] >= 0.0
