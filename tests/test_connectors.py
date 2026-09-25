import pytest
from jarvis.connectors.base import BaseConnector, Capability, ConnectorInfo, ConnectorStatus
from jarvis.connectors.calendar_contacts import CalendarContactsConnector
from jarvis.connectors.email_connector import EmailConnector
from jarvis.connectors.android import AndroidCompanionConnector
from jarvis.connectors.home_assistant import HomeAssistantConnector
from jarvis.connectors.sync_backup import SyncBackupConnector
from jarvis.connectors.node_red import NodeRedConnector


def test_calendar_contacts_connector_unconfigured():
    conn = CalendarContactsConnector(caldav_url=None, username=None)
    health = conn.health()
    assert health["status"] == ConnectorStatus.NOT_CONFIGURED.value
    assert health["caldav_configured"] is False

    caps = conn.discover_capabilities()
    assert len(caps) >= 2


def test_calendar_contacts_connector_lifecycle():
    conn = CalendarContactsConnector(caldav_url="http://127.0.0.1:5232", username="user1", password="pw")
    assert conn.status == ConnectorStatus.CONFIGURED

    # Prepare action
    prep = conn.prepare_action("create_event", {"title": "Study NLP", "start_time": "2026-09-20T10:00:00"})
    assert prep["prepared"] is True

    # Missing field raises ValueError
    with pytest.raises(ValueError, match="Missing required arguments"):
        conn.prepare_action("create_event", {"title": "No start time"})

    # Execute authorized action
    res = conn.execute_authorized_action("act_cal_1", "create_event", {"title": "Study NLP", "start_time": "2026-09-20T10:00:00"})
    assert res["status"] == "created"

    # Verify action outcome
    assert conn.verify("act_cal_1", "create_event", {}) is True

    # Read events
    events = conn.read("calendar/events")
    assert len(events) == 1
    assert events[0]["title"] == "Study NLP"

    conn.disconnect()
    assert conn.status == ConnectorStatus.DISCONNECTED


def test_email_connector_preview_and_send():
    conn = EmailConnector(imap_host="imap.example.com", username="test@example.com")
    assert conn.status == ConnectorStatus.CONFIGURED

    # Draft reply
    prep_draft = conn.prepare_action("draft_reply", {"to": "colleague@example.com", "subject": "Re: Notes"})
    assert prep_draft["prepared"] is True

    exec_draft = conn.execute_authorized_action("act_draft_1", "draft_reply", {"to": "colleague@example.com", "subject": "Re: Notes"})
    assert exec_draft["status"] == "draft_created"
    assert conn.verify("act_draft_1", "draft_reply", {}) is True

    # Send email requires review preview
    prep_send = conn.prepare_action("send_email", {"to": "colleague@example.com", "subject": "Done", "body": "Finished the report"})
    assert prep_send["recipient"] == "colleague@example.com"
    assert "SEND EMAIL" in prep_send["preview"]

    exec_send = conn.execute_authorized_action("act_send_1", "send_email", {"to": "colleague@example.com", "subject": "Done", "body": "Finished"})
    assert exec_send["status"] == "submitted"
    assert conn.verify("act_send_1", "send_email", {}) is True

    conn.disconnect()


def test_android_companion_connector():
    conn = AndroidCompanionConnector(device_id="device_pixel_9")
    caps = conn.discover_capabilities()
    assert any(c.name == "share_link" for c in caps)

    prep = conn.prepare_action("share_link", {"url": "https://python.org"})
    assert prep["prepared"] is True

    res = conn.execute_authorized_action("act_and_1", "share_link", {"url": "https://python.org"})
    assert res["status"] == "submitted"
    assert conn.verify("act_and_1", "share_link", {}) is True


def test_home_assistant_allowlist_and_control():
    conn = HomeAssistantConnector(hass_url="http://192.168.1.50:8123", access_token="tok123")
    assert conn.status == ConnectorStatus.CONFIGURED

    # Allowed domain: light
    prep = conn.prepare_action("set_entity_state", {"entity_id": "light.desk_lamp", "state": "on"})
    assert prep["prepared"] is True

    res = conn.execute_authorized_action("act_ha_1", "set_entity_state", {"entity_id": "light.desk_lamp", "state": "on"})
    assert res["new_state"] == "on"
    assert conn.verify("act_ha_1", "set_entity_state", {"entity_id": "light.desk_lamp", "new_state": "on"}) is True

    # Forbidden domain outside allowlist (e.g. lock or camera)
    with pytest.raises(ValueError, match="not in permitted allowlist"):
        conn.prepare_action("set_entity_state", {"entity_id": "lock.front_door", "state": "unlocked"})


def test_sync_backup_connector_prohibits_live_wal_sync():
    conn = SyncBackupConnector()
    assert conn.status == ConnectorStatus.CONFIGURED

    # Attempting direct backup of live active SQLite WAL file must fail
    with pytest.raises(ValueError, match="Direct backup of active live SQLite database"):
        conn.prepare_action("create_versioned_backup", {"source_dir": "c:/path/to/jarvis.db-wal"})


def test_node_red_named_workflows_only():
    conn = NodeRedConnector()
    # Approved workflow triggers successfully
    prep = conn.prepare_action("trigger_named_workflow", {"workflow_name": "notify_study_complete"})
    assert prep["prepared"] is True
    res = conn.execute_authorized_action("act_nr_1", "trigger_named_workflow", {"workflow_name": "notify_study_complete"})
    assert res["status"] in ("dispatched", "SUCCESS")
    assert conn.verify("act_nr_1", "trigger_named_workflow", {}) is True

    # Unapproved or arbitrary flow execution is rejected
    with pytest.raises(ValueError, match="is not an approved named workflow"):
        conn.prepare_action("trigger_named_workflow", {"workflow_name": "arbitrary_bash_node"})
