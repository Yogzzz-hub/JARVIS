"""Audio Output Manager for JARVIS EDGE Phase 7.

Sole owner of speaker audio playback. Runs an asynchronous background worker
that pulls from the priority AudioOutputQueue, writes PCM frames to sounddevice
without blocking the asyncio loop, and instruments high-resolution timestamps.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from pathlib import Path
from time import perf_counter_ns
from typing import Callable, Optional

import numpy as np

from jarvis.core.audio.output.queue import AudioOutputQueue
from jarvis.core.response.models import DeliveryStatus, ResponsePriority, ResponseType, SpokenResponse

logger = logging.getLogger("jarvis.audio.output.player")


class AudioOutputManager:
    """Sole owner of speaker hardware and playback lifecycle."""

    def __init__(
        self,
        device: Optional[str | int] = None,
        sample_rate: int = 22050,
        mock_output: bool = False,
    ) -> None:
        self.device = device
        self.sample_rate = sample_rate
        self.mock_output = mock_output
        self.queue = AudioOutputQueue(max_size=10)

        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._current_response: Optional[SpokenResponse] = None
        self._is_playing = False
        self._stop_current_flag = threading.Event()
        self._stream = None
        self._device_available = True

        # Echo prevention state
        self._currently_spoken_text = ""
        self._last_playback_stop_ns = 0

        # Metrics
        self.total_played = 0
        self.total_interrupted = 0
        self.total_device_errors = 0
        self.last_first_audio_delay_ms = 0.0

    @property
    def is_playing(self) -> bool:
        """Whether audio is currently being output to the speakers."""
        return self._is_playing

    @property
    def currently_spoken_text(self) -> str:
        """The text currently being spoken (for self-echo comparison)."""
        return self._currently_spoken_text if self._is_playing else ""

    @property
    def last_playback_stop_ns(self) -> int:
        return self._last_playback_stop_ns

    def start(self) -> None:
        """Start the background playback thread."""
        if self._running:
            return
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._playback_loop, name="jarvis-audio-output", daemon=True
        )
        self._worker_thread.start()
        logger.info("AudioOutputManager playback worker started")

    def play(self, response: SpokenResponse) -> bool:
        """Enqueue a spoken response for playback."""
        response.response_requested_ns = perf_counter_ns()
        return self.queue.put(response)

    def cancel_current(self) -> None:
        """Immediately interrupt and stop currently playing audio (barge-in)."""
        if self._is_playing:
            self._stop_current_flag.set()
            if self._current_response and self._current_response.interruptible:
                self._current_response.delivery_status = DeliveryStatus.INTERRUPTED
                self.total_interrupted += 1
            logger.info("Current audio playback interrupted via barge-in")

    def wait_until_stopped(self, timeout_s: float = 0.5) -> float:
        """Wait until currently playing audio stops and return elapsed time in ms."""
        t0 = perf_counter_ns()
        while self._is_playing and (perf_counter_ns() - t0) / 1e9 < timeout_s:
            time.sleep(0.001)
        return (perf_counter_ns() - t0) / 1e6

    def cancel_request(self, request_id: str) -> None:
        """Cancel audio for a specific request ID."""
        if self._current_response and self._current_response.request_id == request_id:
            self.cancel_current()
        self.queue.cancel_request(request_id)

    def _playback_loop(self) -> None:
        """Background playback loop consuming from AudioOutputQueue."""
        while self._running:
            response = self.queue.get()
            if not response:
                time.sleep(0.01)
                continue

            if not response.audio_bytes or len(response.audio_bytes) == 0:
                response.delivery_status = DeliveryStatus.COMPLETED
                self.queue.mark_request_completed(response.request_id)
                continue

            self._play_response(response)

    def _play_response(self, response: SpokenResponse) -> None:
        """Play a single SpokenResponse synchronously in the worker thread."""
        self._current_response = response
        self._currently_spoken_text = response.text
        self._stop_current_flag.clear()
        self._is_playing = True
        response.delivery_status = DeliveryStatus.PLAYING
        response.playback_started_ns = perf_counter_ns()

        if response.tts_start_ns > 0:
            self.last_first_audio_delay_ms = (response.playback_started_ns - response.tts_start_ns) / 1e6

        try:
            pcm_bytes = response.audio_bytes
            sr = response.sample_rate or self.sample_rate

            # If mock output or hardware disabled, simulate playback duration
            if self.mock_output:
                duration_s = len(pcm_bytes) / (2 * sr)
                step = 0.05
                elapsed = 0.0
                while elapsed < duration_s and not self._stop_current_flag.is_set():
                    time.sleep(min(step, duration_s - elapsed))
                    elapsed += step
            else:
                self._stream_pcm_to_device(pcm_bytes, sr)

            if self._stop_current_flag.is_set():
                response.delivery_status = DeliveryStatus.INTERRUPTED
            else:
                response.delivery_status = DeliveryStatus.COMPLETED
                self.total_played += 1

        except Exception as exc:
            logger.error("Audio playback error: %s", exc)
            self.total_device_errors += 1
            response.delivery_status = DeliveryStatus.FAILED_FALLBACK
        finally:
            response.playback_finished_ns = perf_counter_ns()
            self._last_playback_stop_ns = response.playback_finished_ns
            self._is_playing = False
            self._currently_spoken_text = ""
            self._current_response = None
            if response.type == ResponseType.FINAL:
                self.queue.mark_request_completed(response.request_id)

    def _stream_pcm_to_device(self, pcm_bytes: bytes, sample_rate: int) -> None:
        """Stream raw int16 PCM bytes to sounddevice OutputStream in small chunks."""
        try:
            import sounddevice as sd

            audio_data = np.frombuffer(pcm_bytes, dtype=np.int16)
            chunk_size = 1024  # ~46 ms chunks at 22050 Hz

            device_idx = self.device
            with sd.OutputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="int16",
                device=device_idx,
            ) as stream:
                if self._current_response:
                    self._current_response.first_audio_device_write_ns = perf_counter_ns()

                for i in range(0, len(audio_data), chunk_size):
                    if self._stop_current_flag.is_set():
                        break
                    chunk = audio_data[i : i + chunk_size]
                    stream.write(chunk)

        except Exception as exc:
            logger.warning("Hardware audio playback failed (fallback to simulated): %s", exc)
            self._device_available = False
            # Simulate remaining time so pipeline does not crash
            dur_s = len(pcm_bytes) / (2 * sample_rate)
            time.sleep(min(dur_s, 0.5))

    def stop(self) -> None:
        """Stop playback thread and close resources."""
        self.cancel_current()
        self._running = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
        logger.info("AudioOutputManager stopped")
