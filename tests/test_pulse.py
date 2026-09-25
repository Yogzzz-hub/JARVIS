import asyncio
import pytest

from jarvis.core.pulse.earcons import EarconManager, EarconType
from jarvis.core.pulse.telemetry import DurationPredictor
from jarvis.core.pulse.event_to_speech import EventToSpeechMapper
from jarvis.core.pulse.scheduler import InteractionScheduler, InteractionState
from jarvis.core.pulse.engine import PulseEngine


# =====================================================================
# 1. In-Memory Earcons Tests
# =====================================================================

def test_earcon_generation():
    manager = EarconManager(sample_rate=22050)
    for earcon in EarconType:
        pcm = manager.get_earcon(earcon)
        assert len(pcm) > 0
        # 16-bit mono = 2 bytes per sample
        n_samples = len(pcm) // 2
        duration_ms = (n_samples / 22050.0) * 1000.0
        # All earcons must be short cues (< 150ms)
        assert 15.0 <= duration_ms <= 120.0, f"Earcon {earcon} duration unexpected: {duration_ms}ms"


# =====================================================================
# 2. Duration Predictor (EWMA) Tests
# =====================================================================

def test_duration_predictor_ewma():
    predictor = DurationPredictor(alpha=0.25)
    # 1. Default prediction for open_app
    d0 = predictor.predict_duration("open_app")
    assert d0 == pytest.approx(380.0)

    # 2. Record a fast observation (e.g. 100ms)
    predictor.record_observation("open_app", 100.0)
    d1 = predictor.predict_duration("open_app")
    # Expected: 0.25 * 100 + 0.75 * 380 = 25 + 285 = 310
    assert d1 == pytest.approx(310.0)

    # 3. Entity specific prediction
    predictor.record_observation("open_app", 50.0, entity="calculator")
    d_calc = predictor.predict_duration("open_app", entity="calculator")
    assert d_calc < d1


# =====================================================================
# 3. Event-to-Speech Translation Tests
# =====================================================================

def test_event_to_speech_mapping():
    assert EventToSpeechMapper.format_event("APP_LAUNCH_STARTED", {"name": "Chrome"}) == "Opening Chrome."
    assert EventToSpeechMapper.format_event("FILE_SEARCH_STARTED") == "I'm looking for it."
    assert EventToSpeechMapper.format_event("DOWNLOAD_STARTED") == "Downloading it."
    assert EventToSpeechMapper.format_event("INSTALL_WAITING_FOR_USER") == "Windows needs your approval to continue."
    assert EventToSpeechMapper.format_event("TASK_VERIFIED") == "Done."
    assert EventToSpeechMapper.format_event("TASK_UNCERTAIN") == "I couldn't verify that it completed."
    assert EventToSpeechMapper.format_event("UNKNOWN_EVENT") is None

    # Contextual Micro-ACKs
    assert EventToSpeechMapper.get_contextual_ack("open_app") == "Opening it."
    assert EventToSpeechMapper.get_contextual_ack("find_file") == "Looking."
    assert EventToSpeechMapper.get_contextual_ack("unregistered_tool") == "On it."


# =====================================================================
# 4. Adaptive Feedback Budgeting Tests
# =====================================================================

def test_interaction_scheduler_budgeting():
    scheduler = InteractionScheduler(fast_threshold_ms=250.0, medium_threshold_ms=1200.0)

    # Fast action (< 250ms) -> Earcon only, no verbal ACK, no race timer
    earcon, ack_text, use_race = scheduler.plan_feedback("req_1", "get_time", 15.0, is_voice=True)
    assert earcon == EarconType.COMMAND_ACCEPTED
    assert ack_text is None
    assert use_race is False

    # Medium action (250ms - 1.2s) -> Short micro-ACK with race timer
    earcon, ack_text, use_race = scheduler.plan_feedback("req_2", "open_app", 400.0, is_voice=True)
    assert earcon == EarconType.COMMAND_ACCEPTED
    assert ack_text == "Opening it."
    assert use_race is True

    # Long action (1.2s+) -> Contextual ACK immediately without waiting for race timer
    earcon, ack_text, use_race = scheduler.plan_feedback("req_3", "planner", 3000.0, is_voice=True)
    assert ack_text == "I'll plan and handle that."
    assert use_race is False


# =====================================================================
# 5. Race-to-Completion Tests
# =====================================================================

@pytest.mark.asyncio
async def test_race_to_completion_fast_action_wins():
    scheduler = InteractionScheduler(race_timer_ms=100.0)
    spoken_acks = []

    def on_speak(req_id, text):
        spoken_acks.append((req_id, text))

    # Start race timer for 100ms
    scheduler.start_race_timer("req_fast", "Opening it.", on_speak)
    assert scheduler.get_state("req_fast") == InteractionState.ACK_PENDING

    # Action finishes in 20ms (< 100ms)
    await asyncio.sleep(0.02)
    cancelled = scheduler.cancel_race_timer("req_fast")
    assert cancelled is True
    assert scheduler.get_state("req_fast") == InteractionState.ACK_CANCELLED

    # Wait past the original timer deadline
    await asyncio.sleep(0.12)
    # Verbal ACK was cancelled, so on_speak was NEVER called!
    assert len(spoken_acks) == 0


@pytest.mark.asyncio
async def test_race_to_completion_slow_action_speaks_ack():
    scheduler = InteractionScheduler(race_timer_ms=50.0)
    spoken_acks = []

    def on_speak(req_id, text):
        spoken_acks.append((req_id, text))

    scheduler.start_race_timer("req_slow", "Opening it.", on_speak)

    # Action takes 100ms (> 50ms)
    await asyncio.sleep(0.08)

    # Timer expired and fired ACK!
    assert len(spoken_acks) == 1
    assert spoken_acks[0] == ("req_slow", "Opening it.")
    assert scheduler.get_state("req_slow") == InteractionState.ACK_SPOKEN


# =====================================================================
# 6. PulseEngine Concurrency & Resilience Tests
# =====================================================================

class MockAudioOutput:
    def __init__(self):
        self.played = []
    def play(self, response):
        self.played.append(response)
        return True

class MockEventBus:
    def __init__(self):
        self.emitted = []
    def emit(self, event, request_id, **kwargs):
        self.emitted.append((event, request_id, kwargs))

class MockTTSFailing:
    def __init__(self):
        self.sample_rate = 22050
    def synthesize(self, text):
        raise RuntimeError("Simulated TTS audio driver failure")


@pytest.mark.asyncio
async def test_pulse_engine_decoupled_resilience():
    mock_audio = MockAudioOutput()
    mock_bus = MockEventBus()
    failing_tts = MockTTSFailing()

    engine = PulseEngine(
        audio_output=mock_audio,
        tts_manager=failing_tts,
        event_bus=mock_bus,
        race_timer_ms=50.0,
    )

    # Start interaction
    engine.start_interaction("req_10", "open_app", 350.0, source="voice")
    # Action executes
    engine.on_execution_started("req_10")
    engine.on_execution_finished("req_10", 30.0, "open_app")
    # Verified called with failing TTS
    engine.on_verified("req_10", is_verified=True, result_message="Chrome is open", is_voice=True)

    # Allow async tasks to run
    await asyncio.sleep(0.05)

    # Verify UI states were emitted properly despite TTS failure
    emitted_states = [kwargs.get("state") for ev, req, kwargs in mock_bus.emitted if ev == "ui.state"]
    assert "UNDERSTOOD" in emitted_states
    assert "EXECUTING" in emitted_states
    assert "VERIFYING" in emitted_states
    assert "DONE" in emitted_states


@pytest.mark.asyncio
async def test_immediate_voice_talkback_and_completion_feedback():
    """Validates that voice commands immediately talk back telling the process,
    and then confirm completion without being silenced by fast-latency guards."""
    class RecordingAudioOutput:
        def __init__(self):
            self.played = []
        def play(self, response):
            self.played.append(response)
            return True

    class InstantMockTTS:
        def __init__(self):
            self.sample_rate = 22050
        def synthesize(self, text):
            return b"\x00" * 4410, "mock_tts"

    mock_audio = RecordingAudioOutput()
    mock_bus = MockEventBus()
    tts = InstantMockTTS()

    engine = PulseEngine(
        audio_output=mock_audio,
        tts_manager=tts,
        event_bus=mock_bus,
        race_timer_ms=250.0,
    )

    # 1. Voice command: Open Chrome
    engine.start_interaction("req_v1", "open_app", 50.0, source="voice", slots={"name": "chrome"})

    # Check that immediate process announcement was spoken
    spoken_texts = [resp.text for resp in mock_audio.played]
    assert "Opening Chrome." in spoken_texts, f"Expected 'Opening Chrome.' in {spoken_texts}"

    # Action completes in 20ms (< 250ms fast threshold)
    engine.on_execution_started("req_v1")
    engine.on_execution_finished("req_v1", 20.0, "open_app", "chrome")
    engine.on_verified("req_v1", is_verified=True, result_message="Chrome is open.", is_voice=True, is_fast_silent=True)

    await asyncio.sleep(0.05)
    spoken_texts = [resp.text for resp in mock_audio.played]
    assert "Chrome is open." in spoken_texts, f"Expected 'Chrome is open.' in {spoken_texts}"

    # 2. Voice command: Send WhatsApp to Mom
    engine.start_interaction("req_v2", "send_whatsapp_message", 50.0, source="voice", slots={"recipient": "Mom"})
    spoken_texts = [resp.text for resp in mock_audio.played]
    assert "Sending message to Mom." in spoken_texts, f"Expected 'Sending message to Mom.' in {spoken_texts}"

    engine.on_execution_started("req_v2")
    engine.on_execution_finished("req_v2", 30.0, "send_whatsapp_message", "Mom")
    engine.on_verified("req_v2", is_verified=True, result_message="Done, message sent to Mom.", is_voice=True, is_fast_silent=True)

    await asyncio.sleep(0.05)
    spoken_texts = [resp.text for resp in mock_audio.played]
    assert "Done, message sent to Mom." in spoken_texts, f"Expected 'Done, message sent to Mom.' in {spoken_texts}"

