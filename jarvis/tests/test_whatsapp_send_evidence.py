import pytest

from jarvis.integrations.whatsapp.contact_resolver import ContactEntry, ContactResolver
from jarvis.tools.system.whatsapp_tools import SendWhatsAppMessageTool


@pytest.mark.parametrize("response", [{"success": True}, {"status": "SENT"},
    {"success": False, "status": "UNCERTAIN", "error": "Request timed out"}])
def test_missing_receipt_or_timeout_never_fabricates_success(response):
    class Transport:
        calls = 0
        async def send_text(self, to, text):
            self.calls += 1
            return response
    transport = Transport()
    tool = SendWhatsAppMessageTool(transport=transport,
        contact_resolver=ContactResolver([ContactEntry("123@lid", "Barath")]))
    result = tool.run({"recipient": "Barath", "message": "test"})
    assert result["status"] == "UNCERTAIN"
    assert result["message_id"] is None
    assert result["action_ledger_status"] == "UNCERTAIN"
    assert transport.calls == 1


@pytest.mark.asyncio
async def test_uncertain_send_postcondition_blocks_retry():
    from jarvis.security.postconditions import verify_postconditions
    result = await verify_postconditions("send_whatsapp_message", {}, {"status": "UNCERTAIN"})
    assert result.status.value == "UNCERTAIN"
    assert not result.verified and not result.retry_safe


def test_unsupported_transport_does_not_invent_receipt():
    tool = SendWhatsAppMessageTool(transport=object(),
        contact_resolver=ContactResolver([ContactEntry("123@lid", "Barath")]))
    result = tool.run({"recipient": "Barath", "message": "test"})
    assert result["status"] == "FAILED"
    assert result["message_id"] is None


@pytest.mark.asyncio
async def test_existing_transport_emits_correlated_send_text_schema():
    import json
    from jarvis.integrations.whatsapp.service import BaileysWebSocketTransport
    transport = BaileysWebSocketTransport()
    requests = []
    class Socket:
        async def send(self, raw):
            request = json.loads(raw)
            requests.append(request)
            await transport._handle_event({"id": request["id"], "success": True,
                "result": {"status": "SENT", "message_id": "actual-receipt"}})
    transport._ws = Socket()
    transport.is_connected = True
    result = await transport.send_text("123@lid", "test")
    assert requests[0]["action"] == "send_text"
    assert requests[0]["payload"] == {"to": "123@lid", "text": "test", "quoted": None}
    assert result["result"]["message_id"] == "actual-receipt"
    assert not transport._pending_requests


@pytest.mark.asyncio
async def test_submitted_send_timeout_is_uncertain_and_cleans_pending():
    from jarvis.integrations.whatsapp.service import BaileysWebSocketTransport
    transport = BaileysWebSocketTransport()
    class Socket:
        calls = 0
        async def send(self, raw):
            self.calls += 1
    transport._ws = Socket()
    transport.is_connected = True
    result = await transport._call("send_text", {"to": "123@lid", "text": "test"}, timeout=0.01)
    assert result["status"] == "UNCERTAIN"
    assert transport._ws.calls == 1
    assert not transport._pending_requests


@pytest.mark.asyncio
@pytest.mark.parametrize("followup", ["yes", "don't send it"])
async def test_commandservice_contact_policy_and_confirmation(tmp_path, followup):
    import sqlite3
    from jarvis.tests.ai_harness import AIHarness, route_by_prompt
    from jarvis.security.ledger.ledger import ActionLedger
    h = AIHarness(tmp_path, route_by_prompt([]), reachable=False)
    h.executor.ledger = ActionLedger(tmp_path / "actions.db")
    h.registry.get("send_whatsapp_message").resolver = ContactResolver([ContactEntry("123@lid", "Barath")])
    try:
        preview = await h.say("message Barath saying JARVIS send test")
        assert preview.state == "WAITING_CONFIRMATION", preview.message
        assert not h.transport.sent_messages
        result = await h.say(followup)
        assert result.state == "SUCCESS", result.message
        assert len(h.transport.sent_messages) == (1 if followup == "yes" else 0)
        if followup == "yes":
            assert h.transport.sent_messages[0]["to"] == "123@lid"
            with sqlite3.connect(tmp_path / "actions.db") as conn:
                assert conn.execute("SELECT status FROM action_ledger WHERE tool='send_whatsapp_message'").fetchall() == [("VERIFIED",)]
    finally:
        await h.close()


@pytest.mark.asyncio
async def test_commandservice_uncertain_send_records_uncertain(tmp_path):
    import sqlite3
    from jarvis.tests.ai_harness import AIHarness, route_by_prompt
    h = AIHarness(tmp_path, route_by_prompt([]), reachable=False)
    h.registry.get("send_whatsapp_message").resolver = ContactResolver([ContactEntry("123@lid", "Barath")])
    calls = []
    async def uncertain(to, text):
        calls.append((to, text))
        return {"status": "UNCERTAIN", "success": False}
    h.transport.send_text = uncertain
    try:
        assert (await h.say("message Barath saying test")).state == "WAITING_CONFIRMATION"
        result = await h.say("yes")
        assert result.state == "UNCERTAIN", result.message
        assert len(calls) == 1
        with sqlite3.connect(tmp_path / "actions.db") as conn:
            assert conn.execute("SELECT status FROM action_ledger WHERE tool='send_whatsapp_message'").fetchall() == [("UNCERTAIN",)]
    finally:
        await h.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["what does WhatsApp do?", "show Arun's messages"])
async def test_question_and_read_request_never_send(tmp_path, monkeypatch, text):
    from jarvis.tests.ai_harness import AIHarness, route_by_prompt
    from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
    h = AIHarness(tmp_path, route_by_prompt([], default="WhatsApp is a messaging app."))
    monkeypatch.setattr(WhatsAppInbox, "_instance", h.inbox)
    try:
        result = await h.say(text)
        assert not h.transport.sent_messages
        assert result.state != "WAITING_CONFIRMATION", result.message
        if text.startswith("show"):
            assert result.tool_result.tool_name == "read_whatsapp_messages"
    finally:
        await h.close()


@pytest.mark.asyncio
async def test_readonly_mode_blocks_even_the_old_one_send_exception(monkeypatch):
    import json
    from jarvis.integrations.whatsapp.service import BaileysWebSocketTransport
    monkeypatch.setenv("JARVIS_WHATSAPP_TEST_RECIPIENT", "123@lid")
    transport = BaileysWebSocketTransport(read_only=True)
    calls = []
    class Socket:
        async def send(self, raw):
            request = json.loads(raw)
            calls.append(request)
            await transport._handle_event({"id": request["id"], "success": True,
                "result": {"status": "SENT", "message_id": "receipt"}})
    transport._ws = Socket()
    transport.is_connected = True
    assert not (await transport.send_text("other@lid", "JARVIS send test"))["success"]
    assert not (await transport.send_text("123@lid", "something else"))["success"]
    assert not (await transport.send_text("123@lid", "JARVIS send test"))["success"]
    assert not (await transport.send_text("123@lid", "JARVIS send test"))["success"]
    assert not calls


def test_explicit_ticket_confirmation_never_routes_to_desktop_dialog():
    from jarvis.core.router.control import match_control
    decision = match_control("confirm tkt_ab123", "test")
    assert decision.intent == "confirm_ticket"
    assert decision.slots["ticket_id"] == "tkt_ab123"
