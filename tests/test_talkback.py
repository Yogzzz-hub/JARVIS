import asyncio
import pytest

from jarvis.core.metrics.clock import Clock
from jarvis.core.pulse.engine import PulseEngine
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.commands.service import CommandService
from jarvis.core.events.bus import EventBus
from jarvis.core.executor.engine import ExecutionEngine
from jarvis.core.response.engine import ResponseEngine
from jarvis.core.tasks.manager import State, TaskManager
from jarvis.core.verifier.service import Verifier
from jarvis.tools.base import Contract, RiskLevel, Tool, ToolDefinition
from jarvis.tools.registry import ToolRegistry
from pydantic import Field


class MockRecordingAudio:
    def __init__(self):
        self.played = []
    def play(self, response):
        self.played.append(response)
        return True


class MockTTS:
    def __init__(self):
        self.sample_rate = 22050
    def synthesize(self, text):
        return b"\x00" * 2205, "mock_tts"


class DummyWriter:
    error = None
    dropped = 0
    def enqueue(self, *args, **kwargs): pass
    async def start(self): pass
    async def close(self): pass


class DummyMetrics:
    dropped = 0
    def record(self, *args, **kwargs): pass


@pytest.mark.asyncio
async def test_pulse_waiting_confirmation_talkback_and_state():
    """Verify that PulseEngine handles WAITING_CONFIRMATION state correctly."""
    events = []
    class MockBus:
        def emit(self, event, request_id, **data):
            events.append((event, request_id, data))

    audio = MockRecordingAudio()
    tts = MockTTS()
    bus = MockBus()
    pulse = PulseEngine(audio_output=audio, tts_manager=tts, event_bus=bus)

    # When an action requires confirmation:
    pulse.on_verified(
        request_id="req_conf_1",
        is_verified=False,
        result_message="Please confirm: Send WhatsApp message to 'Yoga': 'hi msg'. Shall I proceed?",
        is_voice=True,
        is_waiting_confirmation=True,
    )

    # 1. UI state must be WAITING_CONFIRMATION, never ERROR
    ui_states = [d.get("state") for ev, req, d in events if ev == "ui.state"]
    assert "WAITING_CONFIRMATION" in ui_states
    assert "ERROR" not in ui_states

    # 2. Spoken response must be queued for the confirmation question
    await asyncio.sleep(0.05)
    spoken_texts = [r.text for r in audio.played]
    assert any("Please confirm" in t for t in spoken_texts)


@pytest.mark.asyncio
async def test_confirm_ticket_dispatches_immediate_talkback():
    """Verify that confirming a pending send action immediately talks back before execution."""
    class DummyMsgInput(Contract):
        recipient: str = Field(default="")
        message: str = Field(default="")

    class DummyMsgOutput(Contract):
        status: str = "SENT"
        message: str = ""

    class SlowMockWhatsAppTool(Tool):
        definition = ToolDefinition(
            name="send_whatsapp_message",
            description="Mock whatsapp tool",
            input_model=DummyMsgInput,
            output_model=DummyMsgOutput,
            read_only=False,
            risk=RiskLevel.EXTERNAL_EFFECT,
        )
        def __init__(self):
            self.executed = False
        def run(self, arguments):
            self.executed = True
            return {"status": "SENT", "message": "Message delivered to Yoga on WhatsApp."}

    tool = SlowMockWhatsAppTool()
    registry = ToolRegistry()
    registry.register(tool)
    registry.finalize()

    bus = EventBus()
    writer = DummyWriter()
    tasks = TaskManager(bus, writer)
    executor = ExecutionEngine()
    verifier = Verifier()
    response = ResponseEngine()
    audio = MockRecordingAudio()
    tts = MockTTS()
    pulse = PulseEngine(audio_output=audio, tts_manager=tts, event_bus=bus)

    service = CommandService(
        registry=registry,
        executor=executor,
        verifier=verifier,
        response=response,
        tasks=tasks,
        bus=bus,
        writer=writer,
        metrics=DummyMetrics(),
        pulse=pulse,
    )

    # Issue and approve ticket in confirmation manager
    ticket = executor.confirmation_manager.issue_ticket(
        request_id="req_test_1",
        graph_id="",
        node_id="",
        tool_name="send_whatsapp_message",
        args={"recipient": "Yoga", "message": "hi msg"},
        risk=RiskLevel.EXTERNAL_EFFECT,
    )
    executor.confirmation_manager.approve_ticket(ticket.ticket_id)

    # Simulate pending execution set from previous confirmation request
    service._pending_execution = {
        "type": "single",
        "task": tasks.create(CommandRequest(text="send hi msg to yoga", source="websocket"), Clock()),
        "ticket_id": ticket.ticket_id,
        "tool": tool,
        "arguments": DummyMsgInput(recipient="Yoga", message="hi msg"),
        "is_voice": True,
        "predicted_ms": 1500.0,
    }

    # User confirms by saying or typing "yes"
    confirm_req = CommandRequest(text="yes", source="websocket")
    res = await service.handle(confirm_req)

    # Check that immediate talkback was dispatched
    spoken_texts = [r.text for r in audio.played]
    assert any("Confirmed. Sending your message to Yoga now." in t for t in spoken_texts), f"Spoken texts: {spoken_texts}"
    assert res.state == "SUCCESS"
    assert "WhatsApp message processed" in res.message or "Message delivered" in res.message


@pytest.mark.asyncio
async def test_whatsapp_unread_and_shorthand_routing():
    from jarvis.core.router.router import SmartRouter
    from jarvis.core.router.models import RouteLane
    router = SmartRouter()

    # Queries from user interaction
    r1 = await router.route(CommandRequest(text="what are the unread msg in whatsapp"))
    assert r1.lane == RouteLane.LANE_0
    assert r1.intent == "read_whatsapp_messages"
    assert r1.slots.get("filter") == "unread"

    r2 = await router.route(CommandRequest(text="can u read the msg to whatsapp ri8?"))
    assert r2.lane == RouteLane.LANE_0
    assert r2.intent == "read_whatsapp_messages"

    r3 = await router.route(CommandRequest(text="what are the unread messages in whatsapp"))
    assert r3.lane == RouteLane.LANE_0
    assert r3.intent == "read_whatsapp_messages"
    assert r3.slots.get("filter") == "unread"


@pytest.mark.asyncio
async def test_talkback_in_every_situation_without_latency():
    """Validates that JARVIS dispatches immediate talkback across diverse situations and modalities."""
    from jarvis.core.router.router import SmartRouter
    from jarvis.core.response.ack_cache import AckCache

    audio = MockRecordingAudio()
    tts = MockTTS()
    ack_cache = AckCache()
    bus = EventBus()
    pulse = PulseEngine(audio_output=audio, ack_cache=ack_cache, tts_manager=tts, event_bus=bus)

    # 1. Test situational contextual ACKs across actions
    test_cases = [
        ("open_app", {"name": "chrome"}, "Opening Chrome."),
        ("close_app", {"name": "notepad"}, "Closing Notepad."),
        ("switch_app", {"name": "vscode"}, "Switching to Vscode."),
        ("read_whatsapp_messages", {}, "Checking your WhatsApp messages."),
        ("send_whatsapp_message", {"recipient": "Alice"}, "Sending message to Alice."),
        ("send_email", {"recipient": "bob@example.com"}, "Sending email to bob@example.com."),
        ("volume_set", {"percent": 75}, "Setting volume to 75 percent."),
        ("volume_mute", {}, "Muting audio."),
        ("web_search", {"query": "quantum"}, "Searching for quantum."),
        ("browse_url", {}, "Opening website."),
        ("take_screenshot", {}, "Taking a screenshot."),
        ("quick_notes", {}, "Taking note."),
        ("meeting_notes", {}, "Recording meeting notes."),
        ("git_status", {}, "Checking Git status."),
        ("git_commit", {}, "Committing changes."),
        ("run_project_tests", {}, "Running tests."),
        ("ollama_chat", {}, "Looking into that."),
        ("planner", {}, "I'll plan and handle that."),
    ]

    for intent, slots, expected_text in test_cases:
        audio.played.clear()
        # Test with source="websocket" (dashboard UI input)
        pulse.start_interaction(f"req_{intent}", intent, 500.0, source="websocket", slots=slots)
        spoken_texts = [r.text for r in audio.played]
        assert expected_text in spoken_texts, f"Expected {expected_text!r} for {intent}, got {spoken_texts}"
        assert any("earcon:COMMAND_ACCEPTED" in t for t in spoken_texts), f"Expected earcon for {intent}"

    # 2. Test control actions (cancel & stop)
    audio.played.clear()
    from jarvis.core.pulse.earcons import EarconType
    pulse.play_earcon(EarconType.FAILED_UNCERTAIN, "req_cancel")
    pulse._dispatch_micro_ack("req_cancel", "Cancelled.")
    spoken_texts = [r.text for r in audio.played]
    assert "Cancelled." in spoken_texts
    assert any("earcon:FAILED_UNCERTAIN" in t for t in spoken_texts)


