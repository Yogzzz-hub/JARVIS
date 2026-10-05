import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from jarvis.integrations.whatsapp.models import NormalizedWhatsAppMessage
from jarvis.integrations.whatsapp.service import WhatsAppIntegrationService


def test_read_only_inbound_uses_storage_path_without_command_or_event_bus():
    incoming = NormalizedWhatsAppMessage(message_id="live-1", chat_id="123@lid",
        sender_id="123@lid", sender_display_name="Test", text="restart computer", timestamp="2026-10-01T00:00:00Z")
    gateway = SimpleNamespace(handle_incoming=AsyncMock())
    service = SimpleNamespace(read_only=True, gateway=gateway,
                              _remember_chat=lambda _: None)
    asyncio.run(WhatsAppIntegrationService._on_incoming_message(service, incoming))
    stored = gateway.handle_incoming.call_args.args[0]
    assert stored.history is True
    assert stored.message_id == incoming.message_id
    assert incoming.history is False


def test_live_health_requires_evidence_from_current_generation(tmp_path):
    from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
    inbox = WhatsAppInbox(tmp_path / "inbox.db")
    inbox.set_connector_state("CONNECTED")
    with inbox._get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO whatsapp_meta VALUES ('sync_generation', 'current')")
        conn.commit()
    inbox.set_bridge_runtime({}, {"generation": "old", "event_health": {"live_direct_messages": 1}})
    assert inbox.diagnostics()["overall_state"] == "DEGRADED_LIVE"
    inbox.record_live_acceptance(generation="current", phone_received=False, message_received=False)
    assert inbox.diagnostics()["overall_state"] == "DEGRADED_LIVE"
    inbox.record_live_acceptance(generation="old", phone_received=True, message_received=False)
    assert inbox.diagnostics()["overall_state"] == "DEGRADED_LIVE"
    inbox.record_live_acceptance(generation="current", phone_received=True, message_received=False)
    assert inbox.diagnostics()["overall_state"] == "EVENT_STREAM_FAILED"
    inbox.set_bridge_runtime({}, {"generation": "current", "event_health": {"live_direct_messages": 1}})
    assert not inbox.diagnostics()["event_stream_verified"]
    inbox.record_live_acceptance(generation="current", phone_received=True, message_received=True, message_id="missing")
    assert not inbox.diagnostics()["event_stream_verified"]
    inbox.add_message(NormalizedWhatsAppMessage(message_id="probe-1", chat_id="123@lid",
        sender_id="123@lid", sender_display_name="Test", text="probe", timestamp="2026-10-01T00:00:00Z"))
    inbox.record_python_event()
    health = inbox.diagnostics()
    assert health["local_history_available"] and not health["history_complete"]
    assert health["last_python_event_at"] and health["last_sqlite_insert_at"]
    inbox.record_live_acceptance(generation="current", phone_received=True, message_received=True,
                                 message_id="probe-1", observed_after=1800000000.0)
    assert not inbox.diagnostics()["event_stream_verified"]  # old stored message is not a new probe
    inbox.record_live_acceptance(generation="current", phone_received=True, message_received=True,
                                 message_id="probe-1", observed_after=1790000000.0)
    assert inbox.diagnostics()["overall_state"] == "LIVE_ONLY"
    inbox.set_connector_state("DISCONNECTED")
    assert not inbox.diagnostics()["event_stream_verified"]
