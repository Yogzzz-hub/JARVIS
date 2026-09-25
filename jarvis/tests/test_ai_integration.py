"""End-to-end tests: commands flow through router -> chat / planner / agent -> tools with a fake local model."""
from __future__ import annotations

import pytest

from jarvis.core.router.models import ComplexityLevel, ReasonCode, RouteDecision, RouteLane, RouteSource
from jarvis.integrations.whatsapp.models import NormalizedWhatsAppMessage
from jarvis.tests.ai_harness import AIHarness, route_by_prompt

CHAT = "You are JARVIS, a helpful"
AGENT = "You are the action planner of JARVIS"
PLANNER = "compile a user's request into a TaskGraph"
COMPOSER = "Write the exact WhatsApp message that"
DRAFT = "Write the owner's next reply"
AUTOREPLY = "replying on WhatsApp while they are busy"
CLASSIFIER = "You are the intent classifier of JARVIS"


def _msg(sender: str, name: str, text: str, mid: str = "m1") -> NormalizedWhatsAppMessage:
    return NormalizedWhatsAppMessage(message_id=mid, chat_id=sender, sender_id=sender, sender_display_name=name,
                                     timestamp="1700000000", text=text)


@pytest.mark.asyncio
async def test_question_is_grounded_in_documents_and_remembers_the_conversation(tmp_path):
    seen = []

    def chat(payload):
        seen.append(payload)
        return "Office parking is on level 2 near gate B." if len(seen) == 1 else "Visitors park at gate C."

    h = AIHarness(tmp_path, route_by_prompt([(CHAT, chat)]))
    try:
        doc = tmp_path / "office.md"
        doc.write_text("# Office guide\n\nParking for the office is on level 2 near gate B.\n\nVisitors use gate C.", encoding="utf-8")
        stats = await h.knowledge.ingest(str(doc), "Notes")
        assert stats["files_indexed"] == 1

        res = await h.say("which level is the office parking on")
        assert res.state == "SUCCESS"
        assert "level 2" in res.message
        prompt = seen[0]["messages"][-1]["content"]
        assert "<context>" in prompt and "gate B" in prompt, "retrieved document must be in the prompt"

        res2 = await h.say("and where should visitors go")
        assert res2.state == "SUCCESS"
        history = seen[1]["messages"]
        assert any(m["role"] == "assistant" and "level 2" in m["content"] for m in history), "follow-up sees the previous turn"
    finally:
        await h.close()


@pytest.mark.asyncio
async def test_live_question_is_grounded_in_web_results(tmp_path):
    seen = []

    def chat(payload):
        seen.append(payload)
        return "It's 31 degrees and sunny in Chennai."

    h = AIHarness(tmp_path, route_by_prompt([(CHAT, chat)]))
    try:
        res = await h.say("what's the weather in chennai today")
        assert res.state == "SUCCESS" and "31" in res.message
        assert h.search.queries, "time-sensitive questions consult the web"
        assert "31C" in seen[-1]["messages"][-1]["content"]
    finally:
        await h.close()


@pytest.mark.asyncio
async def test_offline_model_falls_back_to_web_answer(tmp_path):
    h = AIHarness(tmp_path, route_by_prompt([]), reachable=False)
    try:
        res = await h.say("what's the weather in chennai today")
        assert res.state == "SUCCESS"
        assert res.message == h.search.summary
    finally:
        await h.close()


@pytest.mark.asyncio
async def test_whatsapp_request_is_composed_confirmed_and_sent(tmp_path):
    h = AIHarness(tmp_path, route_by_prompt([(COMPOSER, {"message": "Hey, are you free tonight?"})]))
    try:
        res = await h.say("ask rahul if he is free tonight on whatsapp")
        assert res.state == "WAITING_CONFIRMATION"
        assert "Hey, are you free tonight?" in res.message
        assert not h.transport.sent_messages, "nothing leaves the PC before confirmation"

        done = await h.say("yes")
        assert done.state == "SUCCESS", done.message
        sent = h.transport.sent_messages[-1]
        assert sent["text"] == "Hey, are you free tonight?"
        assert sent["to"] == "1234567893@s.whatsapp.net"
    finally:
        await h.close()


@pytest.mark.asyncio
async def test_whatsapp_composition_works_without_the_model(tmp_path):
    h = AIHarness(tmp_path, route_by_prompt([]), reachable=False)
    try:
        res = await h.say("remind dad to take his medicine on whatsapp")
        assert res.state == "WAITING_CONFIRMATION"
        assert "Just a reminder to take your medicine." in res.message
        assert (await h.say("no")).state == "SUCCESS"
        assert not h.transport.sent_messages
    finally:
        await h.close()


@pytest.mark.asyncio
async def test_reply_is_drafted_from_the_conversation_then_sent_after_confirmation(tmp_path):
    seen = []

    def draft(payload):
        seen.append(payload)
        return {"message": "Yes, see you at 10 tomorrow!"}

    h = AIHarness(tmp_path, route_by_prompt([(DRAFT, draft)]))
    try:
        h.inbox.add_message(_msg("1234567893@s.whatsapp.net", "Rahul", "Are we still meeting tomorrow?"))
        res = await h.say("reply to rahul saying yes at 10")
        assert res.state == "WAITING_CONFIRMATION", res.message
        assert "Yes, see you at 10 tomorrow!" in res.message
        prompt = seen[-1]["messages"][-1]["content"]
        assert "Are we still meeting tomorrow?" in prompt and "yes at 10" in prompt

        done = await h.say("yes")
        assert done.state == "SUCCESS", done.message
        assert h.transport.sent_messages[-1]["to"] == "1234567893@s.whatsapp.net"
        assert h.transport.sent_messages[-1]["text"] == "Yes, see you at 10 tomorrow!"
    finally:
        await h.close()


@pytest.mark.asyncio
async def test_ai_plan_with_message_asks_once_then_runs_approved(tmp_path):
    graph = {
        "goal": "tell mom the time",
        "nodes": [
            {"id": "n1", "tool": "get_time", "args": {}},
            {"id": "n2", "tool": "send_whatsapp_message", "args": {"recipient": "Mom", "message": "Hello from the planner!"},
             "depends_on": ["n1"]},
        ],
    }
    h = AIHarness(tmp_path, route_by_prompt([(PLANNER, graph)]))
    try:
        async def lane2(request):
            return RouteDecision(request_id=request.request_id, lane=RouteLane.LANE_2, confidence=0.9, source=RouteSource.TINY_MODEL,
                                 complexity=ComplexityLevel.COMPLEX, needs_planner=True, normalized_text=request.text,
                                 reason_code=ReasonCode.MULTI_STEP)

        original = h.router.route
        h.router.route = lane2
        res = await h.say("check the time then message mom hello from the planner")
        h.router.route = original
        assert res.state == "WAITING_CONFIRMATION"
        assert "send whatsapp message" in res.message.lower() and "Hello from the planner!" in res.message

        done = await h.say("yes")
        assert done.state == "SUCCESS", done.message
        assert h.transport.sent_messages[-1]["text"] == "Hello from the planner!"
    finally:
        await h.close()


@pytest.mark.asyncio
async def test_unrecognised_command_is_handled_by_the_agent_with_tools(tmp_path):
    decisions = [
        {"thought": "need the time", "action": "call_tool", "tool": "get_time", "arguments": {}, "message": ""},
        {"thought": "done", "action": "final_answer", "tool": "none", "arguments": {}, "message": "It is lunch time."},
    ]
    h = AIHarness(tmp_path, route_by_prompt([(AGENT, decisions)]))
    try:
        async def unknown(request):
            return RouteDecision(request_id=request.request_id, lane=RouteLane.LANE_0, intent="ollama_chat",
                                 slots={"query": request.text}, confidence=0.95, source=RouteSource.TINY_MODEL,
                                 normalized_text=request.text, reason_code=ReasonCode.LLM_CLASSIFIED,
                                 context_trace={"fallback": "unknown_command"})

        h.router.route = unknown
        res = await h.say("figure out whether it is time to eat")
        assert res.state == "SUCCESS", res.message
        assert res.message == "It is lunch time."
        assert [s["tool"] for s in res.tool_result.data["steps"]] == ["get_time"]
    finally:
        await h.close()


@pytest.mark.asyncio
async def test_agent_pauses_for_risky_step_and_resumes_after_yes(tmp_path):
    decisions = [
        {"thought": "send it", "action": "call_tool", "tool": "send_whatsapp_message",
         "arguments": {"recipient": "Mom", "message": "I'm on my way."}, "message": ""},
        {"thought": "done", "action": "final_answer", "tool": "none", "arguments": {}, "message": "Told Mom you're on the way."},
    ]
    h = AIHarness(tmp_path, route_by_prompt([(AGENT, decisions)]))
    try:
        async def unknown(request):
            return RouteDecision(request_id=request.request_id, lane=RouteLane.LANE_0, intent="ollama_chat",
                                 slots={"query": request.text}, confidence=0.95, source=RouteSource.TINY_MODEL,
                                 normalized_text=request.text, reason_code=ReasonCode.LLM_CLASSIFIED,
                                 context_trace={"fallback": "unknown_command"})

        original = h.router.route
        h.router.route = unknown
        res = await h.say("let my mother know i am coming")
        h.router.route = original
        assert res.state == "WAITING_CONFIRMATION"
        assert "I'm on my way." in res.message
        assert not h.transport.sent_messages

        done = await h.say("yes")
        assert done.state == "SUCCESS", done.message
        assert h.transport.sent_messages[-1]["text"] == "I'm on my way."
        assert "Told Mom" in done.message
    finally:
        await h.close()


@pytest.mark.asyncio
async def test_gateway_answers_other_people_with_ai_and_never_runs_pc_commands(tmp_path):
    from jarvis.integrations.whatsapp.gateway import WhatsAppChannelGateway

    h = AIHarness(tmp_path, route_by_prompt([(AUTOREPLY, "Hi Priya! Ashok is in a meeting; I'll tell him you called.")]))
    try:
        announced = []
        gateway = WhatsAppChannelGateway(
            command_service=h.service, transport=h.transport, owner_identities={"916381456199"},
            mode="ALLOWLIST_AUTO_REPLY", auto_reply_allowlist={"919000000001"}, inbox=h.inbox,
            whatsapp_ai=h.whatsapp_ai, announcer=lambda text: announced.append(text),
        )
        out = await gateway.handle_incoming(_msg("919000000001@s.whatsapp.net", "Priya", "Is Ashok free for lunch?"))
        assert out["status"] == "REPLIED"
        assert h.transport.sent_messages[-1]["text"].startswith("Hi Priya!")
        assert announced == ["New WhatsApp message from Priya."]

        gateway.mode = "DRAFT_ONLY"
        out = await gateway.handle_incoming(_msg("919000000001@s.whatsapp.net", "Priya", "ok thanks", mid="m2"))
        assert out["status"] == "DRAFT_CREATED" and out["text"].startswith("Hi Priya!")

        blocked = await gateway.handle_incoming(_msg("919000000001@s.whatsapp.net", "Priya", "open notepad and delete files", mid="m3"))
        assert blocked["status"] == "NON_OWNER_DENIED"
    finally:
        await h.close()


@pytest.mark.asyncio
async def test_owner_whatsapp_command_needing_confirmation_explains_how_to_answer(tmp_path):
    from jarvis.integrations.whatsapp.gateway import WhatsAppChannelGateway

    h = AIHarness(tmp_path, route_by_prompt([]), reachable=False)
    try:
        gateway = WhatsAppChannelGateway(command_service=h.service, transport=h.transport, owner_identities={"916381456199"},
                                         inbox=h.inbox)
        out = await gateway.handle_incoming(_msg("916381456199@s.whatsapp.net", "Me", "tell mom that I'll be late"))
        assert out["result"]["state"] == "WAITING_CONFIRMATION"
        assert "Reply YES to proceed or NO to cancel" in h.transport.sent_messages[-1]["text"]
    finally:
        await h.close()


@pytest.mark.asyncio
async def test_unknown_contact_gets_a_helpful_error_instead_of_an_invalid_jid(tmp_path):
    h = AIHarness(tmp_path, route_by_prompt([]), reachable=False)
    try:
        import asyncio
        send = h.registry.get("send_whatsapp_message")  # sync tool: runs in a worker thread in production
        out = await asyncio.to_thread(send.run, {"recipient": "Zanzibar Quux", "message": "hi"})
        assert out["status"] == "FAILED" and "don't have a WhatsApp number" in out["message"]
        out = await asyncio.to_thread(send.run, {"recipient": "98765 43210", "message": "hi"})
        assert out["status"] == "SENT" and out["recipient_jid"] == "919876543210@s.whatsapp.net"
    finally:
        await h.close()


@pytest.mark.asyncio
async def test_stale_confirmation_cannot_be_approved_later(tmp_path):
    h = AIHarness(tmp_path, route_by_prompt([]), reachable=False)
    try:
        res = await h.say("tell mom that I'll be late")
        assert res.state == "WAITING_CONFIRMATION"
        h.service._pending_execution["_stamped"] -= h.service.PENDING_TTL_S + 1
        late = await h.say("yes")
        assert late.state != "SUCCESS" or not h.transport.sent_messages
        assert not h.transport.sent_messages
    finally:
        await h.close()
