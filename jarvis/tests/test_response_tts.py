"""Comprehensive Unit Tests for JARVIS EDGE Phase 7.

Tests:
1. SpokenResponse & Response models
2. ResponseFormatter (filenames, extensions, paths, numbers, lists, errors, uncertain, partial)
3. AckCache (RAM loading, O(1) lookup, no-repeat rotation, weighted selection)
4. AudioOutputQueue (priorities, stale response drop, obsolete ACK drop, duplicate final prevention)
5. AudioOutputManager (dedicated playback worker, timestamps, mock playback)
6. BargeInController (playback stop latency, control words, echo signature, self-trigger guard)
7. TTSEngine & TTSManager (Piper, SAPI fallback, text-only fallback, generic caching)
8. ResponseScheduler & ResponseEngine (instant query bypass, merge window cancellation, spoken confirmation, follow-up window)
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from jarvis.core.audio.output.barge_in import BargeInController
from jarvis.core.audio.output.player import AudioOutputManager
from jarvis.core.audio.output.queue import AudioOutputQueue
from jarvis.core.response.ack_cache import AckCache
from jarvis.core.response.engine import ResponseEngine
from jarvis.core.response.formatter import ResponseFormatter
from jarvis.core.response.models import (
    ConfirmationIntent,
    DeliveryStatus,
    ResponseLifecycle,
    ResponsePriority,
    ResponseType,
    SpokenConfirmationParser,
    SpokenResponse,
)
from jarvis.core.response.progress import ProgressTracker
from jarvis.core.tts.base import TTSChunk, TTSEngine
from jarvis.core.tts.manager import TTSManager
from jarvis.core.tts.piper_engine import PiperEngine, normalize_tts_text
from jarvis.core.tts.sapi_engine import SAPIEngine
from jarvis.tools.base import ToolResult, VerificationResult


# =====================================================================
# 1. Models & Confirmation Grammar Tests
# =====================================================================

def test_spoken_response_construction():
    resp = SpokenResponse(
        text="Chrome is open.",
        type=ResponseType.FINAL,
        request_id="req_test_01",
        priority=ResponsePriority.FINAL,
    )
    assert resp.text == "Chrome is open."
    assert resp.type == ResponseType.FINAL
    assert resp.request_id == "req_test_01"
    assert resp.priority == ResponsePriority.FINAL
    assert resp.delivery_status == DeliveryStatus.PENDING
    assert resp.created_ns > 0


def test_spoken_confirmation_grammar():
    # Affirmatives
    for phrase in ["yes", "yeah", "yep", "confirm", "go ahead", "do it", "sure", "proceed"]:
        assert SpokenConfirmationParser.parse(phrase) == ConfirmationIntent.AFFIRMATIVE, f"Failed for {phrase}"

    # Negatives
    for phrase in ["no", "nope", "cancel", "stop", "don't", "abort", "reject"]:
        assert SpokenConfirmationParser.parse(phrase) == ConfirmationIntent.NEGATIVE, f"Failed for {phrase}"

    # Ambiguous
    for phrase in ["maybe", "what", "tell me more", "why", ""]:
        assert SpokenConfirmationParser.parse(phrase) == ConfirmationIntent.AMBIGUOUS, f"Failed for {phrase}"


# =====================================================================
# 2. Response Formatter Tests
# =====================================================================

def test_format_filename():
    assert ResponseFormatter.format_filename("UNIT_4_DL_FINAL_2.pdf") == "Unit 4 DL Final 2 PDF"
    assert ResponseFormatter.format_filename("budget_2026.xlsx") == "Budget 2026 Excel file"
    assert ResponseFormatter.format_filename("presentation.pptx") == "Presentation PowerPoint file"
    assert ResponseFormatter.format_filename("notes.txt") == "Notes text file"


def test_format_path():
    assert ResponseFormatter.format_path("C:\\Users\\ashok\\Downloads") == "your Downloads folder"
    assert ResponseFormatter.format_path("C:\\Users\\ashok\\Desktop") == "your Desktop"
    assert ResponseFormatter.format_path("C:\\Users\\ashok\\Documents\\Exam_Notes") == "Exam Notes"


def test_format_number_and_time():
    assert ResponseFormatter.format_number("Volume set to 30%") == "Volume set to 30 percent"
    assert ResponseFormatter.format_number("Current time is 20:35") == "Current time is 8:35 PM"
    assert ResponseFormatter.format_number("Meeting at 09:00") == "Meeting at 9 AM"


def test_format_list():
    assert ResponseFormatter.format_list(["file1.pdf"]) == "File1 PDF"
    assert ResponseFormatter.format_list(["file1.pdf", "file2.pdf"]) == "File1 PDF and File2 PDF"
    assert ResponseFormatter.format_list(["A", "B", "C"]) == "A, B, and C"
    # Max 3 items bounded
    items = ["unit1.pdf", "unit2.pdf", "unit3.pdf", "unit4.pdf", "unit5.pdf"]
    formatted = ResponseFormatter.format_list(items, max_items=3)
    assert "plus 2 more" in formatted
    assert "Unit1 PDF" in formatted


def test_format_verified_tools():
    # open_app
    msg = ResponseFormatter.format_verified_tool("open_app", {"name": "chrome"})
    assert msg == "Chrome is open."

    # volume_set
    msg = ResponseFormatter.format_verified_tool("volume_set", {"percent": 30.0})
    assert msg == "Volume set to 30 percent."

    # get_time
    msg = ResponseFormatter.format_verified_tool("get_time", {"iso": "2026-09-17T20:35:00"})
    assert msg == "8:35 PM"

    # search_files count
    msg = ResponseFormatter.format_verified_tool("find_file", {"count": 3, "matches": ["a", "b", "c"]})
    assert msg == "I found 3 matching files."

    # search_files empty
    msg = ResponseFormatter.format_verified_tool("find_file", {"count": 0, "matches": []})
    assert msg == "I couldn't find any matching files."


def test_format_uncertain_and_partial():
    class MockGraph:
        status = "uncertain"
        node_results = []
        user_message_data = ""

    assert ResponseFormatter.format_graph_result(MockGraph()) == "I performed the action, but I couldn't verify whether it completed."

    class MockPartialGraph:
        status = "partial"
        node_results = {"n1": MagicMock(success=True), "n2": MagicMock(success=False)}
        user_message_data = ""

    msg = ResponseFormatter.format_graph_result(MockPartialGraph())
    assert "I completed 1 of 2 steps" in msg


def test_sanitize_error():
    assert ResponseFormatter.sanitize_error("FileNotFoundError: [Errno 2] No such file or directory: 'x'") == "The requested file or program was not found."
    assert ResponseFormatter.sanitize_error("PermissionError: [WinError 5] Access is denied") == "Access was denied by the system."
    assert ResponseFormatter.sanitize_error("PolicyDenial: action is blocked") == "This action is blocked by security policy."


# =====================================================================
# 3. AckCache Tests
# =====================================================================

def test_ack_cache_loading_and_lookup(tmp_path):
    ack_dir = tmp_path / "acks"
    ack_dir.mkdir()
    # Create fake wav
    fake_wav = ack_dir / "got_it.wav"
    import wave
    with wave.open(str(fake_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        wf.writeframes(b"\x00\x00" * 1000)

    cache = AckCache(asset_dir=ack_dir)
    loaded = cache.load_cache()
    assert loaded == 1
    assert cache.is_cached("Got it.")
    assert cache.cached_count == 1

    phrase_bytes = cache.get_phrase_bytes("Got it.")
    assert phrase_bytes is not None
    assert len(phrase_bytes[0]) == 2000


def test_ack_cache_no_immediate_repeat():
    cache = AckCache()
    # Populate fake ram cache
    for p in ["Understood.", "Got it.", "Okay."]:
        cache._ram_cache[p] = b"fake_pcm"
        cache._durations[p] = 300.0

    seen = []
    for _ in range(10):
        phrase, _, _ = cache.get_ack(candidate_phrases=["Understood.", "Got it.", "Okay."])
        if len(seen) >= 1:
            # Cannot repeat immediate previous if alternatives exist
            assert phrase != seen[-1] or len(seen) < 2
        seen.append(phrase)


# =====================================================================
# 4. Audio Output Queue & Priorities Tests
# =====================================================================

def test_audio_queue_priorities():
    queue = AudioOutputQueue(max_size=10)
    queue.register_active_request("req_ack")
    queue.register_active_request("req_final")
    queue.register_active_request("req_cancel")

    resp_ack = SpokenResponse(text="Got it.", type=ResponseType.ACK, request_id="req_ack", priority=ResponsePriority.ACK)
    resp_final = SpokenResponse(text="Done.", type=ResponseType.FINAL, request_id="req_final", priority=ResponsePriority.FINAL)
    resp_cancel = SpokenResponse(text="Stopped.", type=ResponseType.CANCELLED, request_id="req_cancel", priority=ResponsePriority.EMERGENCY)

    # Put ACK first, then FINAL, then EMERGENCY
    queue.put(resp_ack)
    queue.put(resp_final)
    queue.put(resp_cancel)

    # EMERGENCY should be popped first
    p1 = queue.get()
    assert p1.priority == ResponsePriority.EMERGENCY
    assert p1.text == "Stopped."

    # FINAL should be popped second
    p2 = queue.get()
    assert p2.priority == ResponsePriority.FINAL
    assert p2.text == "Done."

    # ACK should be popped last
    p3 = queue.get()
    assert p3.priority == ResponsePriority.ACK
    assert p3.text == "Got it."


def test_audio_queue_obsolete_ack_drop():
    queue = AudioOutputQueue(max_size=10)
    queue.register_active_request("req_01")

    resp_ack = SpokenResponse(text="Got it.", type=ResponseType.ACK, request_id="req_01", priority=ResponsePriority.ACK)
    assert queue.put(resp_ack) is True

    # Now FINAL arrives for the same request
    resp_final = SpokenResponse(text="Done.", type=ResponseType.FINAL, request_id="req_01", priority=ResponsePriority.FINAL)
    assert queue.put(resp_final) is True

    # The pending ACK must be purged, only FINAL should be popped
    popped = queue.get()
    assert popped.type == ResponseType.FINAL
    assert popped.text == "Done."
    assert queue.get() is None
    assert queue.total_dropped_obsolete_ack == 1


def test_audio_queue_duplicate_final_prevention():
    queue = AudioOutputQueue(max_size=10)
    queue.register_active_request("req_dup")

    resp1 = SpokenResponse(text="Chrome is open.", type=ResponseType.FINAL, request_id="req_dup", priority=ResponsePriority.FINAL)
    resp2 = SpokenResponse(text="Chrome is open.", type=ResponseType.FINAL, request_id="req_dup", priority=ResponsePriority.FINAL)

    assert queue.put(resp1) is True
    # Duplicate FINAL for same request rejected
    assert queue.put(resp2) is False
    assert queue.total_duplicates_prevented == 1


def test_audio_queue_stale_response_drop():
    queue = AudioOutputQueue(max_size=10)
    queue.register_active_request("req_old")

    resp = SpokenResponse(text="Progress...", type=ResponseType.PROGRESS, request_id="req_old", priority=ResponsePriority.PROGRESS)
    queue.put(resp)

    # Cancel request
    dropped = queue.cancel_request("req_old")
    assert dropped == 1
    assert queue.get() is None


# =====================================================================
# 5. AudioOutputManager & Mock Playback Tests
# =====================================================================

def test_audio_output_manager_lifecycle():
    manager = AudioOutputManager(mock_output=True)
    manager.start()
    assert manager._running is True

    resp = SpokenResponse(
        text="Test mock audio",
        type=ResponseType.FINAL,
        request_id="req_mock",
        audio_bytes=b"\x00\x00" * 500,  # short pcm
    )
    manager.queue.register_active_request("req_mock")
    assert manager.play(resp) is True

    time.sleep(0.1)
    manager.stop()
    assert manager._running is False


# =====================================================================
# 6. BargeInController Tests
# =====================================================================

def test_barge_in_interruption():
    manager = AudioOutputManager(mock_output=True)
    barge = BargeInController(output_manager=manager)

    # Simulate speaking
    manager._is_playing = True
    manager._currently_spoken_text = "Jarvis is processing your long multi step request."
    resp = SpokenResponse(text="Long text", type=ResponseType.FINAL, request_id="req_bi", interruptible=True)
    manager._current_response = resp

    # User speaks
    interrupted = barge.on_user_speech_started()
    assert interrupted is True
    assert resp.delivery_status == DeliveryStatus.INTERRUPTED
    assert barge.last_barge_in_stop_latency_ms < 150.0


def test_barge_in_control_words():
    manager = AudioOutputManager(mock_output=True)
    cancelled_task = False

    def _cancel_task():
        nonlocal cancelled_task
        cancelled_task = True

    barge = BargeInController(output_manager=manager, task_cancellation_fn=_cancel_task)

    # "stop talking" -> audio only
    is_ctrl, action = barge.handle_barge_in_words("stop talking")
    assert is_ctrl is True
    assert action == "audio_only"
    assert cancelled_task is False

    # "cancel" -> task cancel
    is_ctrl, action = barge.handle_barge_in_words("cancel")
    assert is_ctrl is True
    assert action == "task_cancel"
    assert cancelled_task is True


def test_self_echo_protection():
    manager = AudioOutputManager(mock_output=True)
    barge = BargeInController(output_manager=manager)

    manager._is_playing = True
    manager._currently_spoken_text = "Chrome is open on your desktop."

    # Exact echo from microphone
    assert barge.check_self_echo("Chrome is open on your desktop") is True

    # Different user command
    assert barge.check_self_echo("open calculator") is False


# =====================================================================
# 7. TTSEngine, Piper & SAPI Fallback Tests
# =====================================================================

def test_normalize_tts_text():
    assert "Fast A P I" in normalize_tts_text("Building with FastAPI")
    assert "Cooda" in normalize_tts_text("Powered by CUDA")
    assert "N L P" in normalize_tts_text("NLP exam notes")


def test_sapi_engine_fallback():
    sapi = SAPIEngine()
    sapi.load()
    if sapi.is_loaded:
        pcm = sapi.synthesize("Test fallback")
        assert isinstance(pcm, bytes)
        assert len(pcm) > 0


def test_tts_manager_fallback_chain():
    fake_piper = MagicMock(spec=PiperEngine)
    fake_piper.synthesize.side_effect = RuntimeError("Piper crashed")
    fake_piper.load.return_value = None

    fake_sapi = MagicMock(spec=SAPIEngine)
    fake_sapi.synthesize.return_value = b"fake_sapi_pcm"
    fake_sapi.load.return_value = None

    manager = TTSManager(piper_engine=fake_piper, sapi_engine=fake_sapi, keep_warm=False)

    pcm, backend = manager.synthesize("Test fallback chain")
    assert backend == "sapi"
    assert pcm == b"fake_sapi_pcm"
    assert manager.piper_failures == 1
    assert manager.sapi_fallbacks == 1


def test_tts_manager_generic_phrase_caching():
    fake_piper = MagicMock(spec=PiperEngine)
    fake_piper.synthesize.return_value = b"done_pcm"
    manager = TTSManager(piper_engine=fake_piper, keep_warm=False)

    # First call: synthesizes
    pcm1, b1 = manager.synthesize("Done.")
    assert b1 == "piper"

    # Second call: served from cache
    pcm2, b2 = manager.synthesize("Done.")
    assert b2 == "cache"
    assert pcm1 == pcm2


# =====================================================================
# 8. ResponseEngine & Scheduler Tests
# =====================================================================

@pytest.mark.asyncio
async def test_instant_query_skips_ack():
    engine = ResponseEngine(ack_enabled=True)
    # get_time is in INSTANT_INTENTS
    await engine.schedule_ack_or_skip("req_time", "get_time", is_complex=False, is_voice=True)

    # Should not schedule ACK
    assert "req_time" not in engine._pending_ack_tasks
    assert engine.total_final_only == 1


@pytest.mark.asyncio
async def test_fast_action_cancels_ack():
    engine = ResponseEngine(ack_enabled=True, ack_merge_ms=100.0)
    await engine.schedule_ack_or_skip("req_fast", "open_app", is_complex=False, is_voice=True)
    assert "req_fast" in engine._pending_ack_tasks

    # Fast action completes immediately
    cancelled = engine.cancel_pending_ack("req_fast")
    assert cancelled is True
    assert engine.total_acks_cancelled_merge == 1


@pytest.mark.asyncio
async def test_confirmation_prompt_and_followup_window():
    engine = ResponseEngine()
    resp = engine.handle_confirmation_prompt("req_conf", "Delete old_report.pdf from Downloads?", is_voice=False)

    assert resp.type == ResponseType.CONFIRMATION
    assert engine.active_followup_window is True
    assert engine.followup_target_request_id == "req_conf"

    engine.close_followup_window()
    assert engine.active_followup_window is False
