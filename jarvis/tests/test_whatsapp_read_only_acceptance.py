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


def test_live_incoming_event_requires_new_durable_direct_message(tmp_path):
    from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
    inbox = WhatsAppInbox(tmp_path / "inbox.db")
    events = []
    async def handle(message):
        if inbox.contains_message(message.message_id, message.chat_id):
            return {"status": "DUPLICATE_IGNORED"}
        inbox.add_message(message)
        return {"status": "STORED"}
    gateway = SimpleNamespace(handle_incoming=handle, inbox=inbox, is_owner=lambda _: False)
    bus = SimpleNamespace(emit=lambda *args, **kwargs: events.append((args, kwargs)))
    service = SimpleNamespace(read_only=False, gateway=gateway, event_bus=bus,
                              _remember_chat=lambda _: None)
    direct = NormalizedWhatsAppMessage(message_id="live-1", chat_id="123@lid", sender_id="123@lid",
                                       text="restart computer", timestamp="2026-10-01T00:00:00Z")
    asyncio.run(WhatsAppIntegrationService._on_incoming_message(service, direct))
    assert inbox.contains_message("live-1", "123@lid")
    assert len(events) == 1
    assert events[0][0][0] == "whatsapp.message_received"
    assert "text" not in events[0][1]
    asyncio.run(WhatsAppIntegrationService._on_incoming_message(service, direct))
    assert len(events) == 1
    group = direct.model_copy(update={"message_id": "group-1", "chat_id": "123@g.us", "is_group": True})
    asyncio.run(WhatsAppIntegrationService._on_incoming_message(service, group))
    assert len(events) == 1
    history = direct.model_copy(update={"message_id": "history-1", "history": True})
    asyncio.run(WhatsAppIntegrationService._on_incoming_message(service, history))
    assert len(events) == 1


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
