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
        event_callback: Callable | None = None,
    ) -> None:
        self.device = device
        self.sample_rate = sample_rate
        self.mock_output = mock_output
        self.event_callback = event_callback
        self.last_error = ""
        self.last_stream_flush_ms = None
        self._cancel_ns = 0
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

        # Cached device parameters
        self._cached_native_rate: Optional[int] = None
        self._cached_active_device = self.device
        self._resample_factors: dict[tuple[int, int], tuple[int, int]] = {}

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
            self._cancel_ns = perf_counter_ns()
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

    def cancel_all(self) -> None:
        """Immediately interrupt current playback and purge the entire queue."""
        self.cancel_current()
        with self.queue._lock:
            for prio, count, resp in self.queue._heap:
                resp.delivery_status = DeliveryStatus.DROPPED_STALE
            self.queue._heap.clear()
            self.queue._active_requests.clear()
        logger.info("All audio playback stopped and queue cleared")

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
        self._is_playing = False

        try:
            pcm_bytes = response.audio_bytes
            sr = response.sample_rate or self.sample_rate

            # If mock output or hardware disabled, simulate playback duration
            if self.mock_output:
                self._is_playing = True
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
            self.last_error = str(exc)
            logger.error("Audio playback error: %s", exc)
            self.total_device_errors += 1
            response.delivery_status = DeliveryStatus.FAILED_FALLBACK
            self._emit("tts.error", response, error=str(exc))
        finally:
            response.playback_finished_ns = perf_counter_ns()
            self._last_playback_stop_ns = response.playback_finished_ns
            self._is_playing = False
            self._currently_spoken_text = ""
            self._current_response = None
            self._emit("tts.stopped", response, status=response.delivery_status.value,
                       first_audio_ms=self.last_first_audio_delay_ms,
                       stream_flush_ms=self.last_stream_flush_ms)
            if response.type == ResponseType.FINAL:
                if not getattr(response, "is_chunk", False) or getattr(response, "is_last_chunk", True):
                    self.queue.mark_request_completed(response.request_id)

    def _stream_pcm_to_device(self, pcm_bytes: bytes, sample_rate: int) -> None:
        """Stream raw int16 PCM bytes to sounddevice OutputStream in small chunks."""
        import math
        import sounddevice as sd
        from scipy.signal import resample_poly

        audio_data = np.frombuffer(pcm_bytes, dtype=np.int16)
        active_rate = sample_rate
        active_device = self._cached_active_device

        # Cache native rate once
        if self._cached_native_rate is None:
            try:
                dev_info = sd.query_devices(active_device, "output")
                self._cached_native_rate = int(dev_info.get("default_samplerate", 48000))
            except Exception:
                self._cached_native_rate = 48000

        def _try_open_stream(dev, rate):
            return sd.OutputStream(
                samplerate=rate,
                channels=1,
                dtype="int16",
                device=dev,
            )

        stream = None
        # 1. Try specified device at requested sample_rate
        try:
            stream = _try_open_stream(active_device, active_rate)
        except Exception:
            # Resample to cached native rate
            native_rate = self._cached_native_rate or 48000
            try:
                stream = _try_open_stream(active_device, native_rate)
                cache_key = (active_rate, native_rate)
                if cache_key not in self._resample_factors:
                    gcd = math.gcd(active_rate, native_rate)
                    self._resample_factors[cache_key] = (native_rate // gcd, active_rate // gcd)
                up, down = self._resample_factors[cache_key]
                resampled = resample_poly(audio_data.astype(np.float32), up, down)
                audio_data = np.clip(resampled, -32768, 32767).astype(np.int16)
                active_rate = native_rate
            except Exception:
                # Fallback to default output device
                active_device = None
                self._cached_active_device = None
                try:
                    stream = _try_open_stream(None, 48000)
                    cache_key = (sample_rate, 48000)
                    if cache_key not in self._resample_factors:
                        gcd = math.gcd(sample_rate, 48000)
                        self._resample_factors[cache_key] = (48000 // gcd, sample_rate // gcd)
                    up, down = self._resample_factors[cache_key]
                    resampled = resample_poly(audio_data.astype(np.float32), up, down)
                    audio_data = np.clip(resampled, -32768, 32767).astype(np.int16)
                    active_rate = 48000
                except Exception:
                    pass

        if stream is None:
            raise RuntimeError(f"Could not open audio output stream on {self.device}")

        chunk_size = max(1, int(active_rate * 0.08))
        with stream:
            self._stream = stream
            try:
                for i in range(0, len(audio_data), chunk_size):
                    if self._stop_current_flag.is_set():
                        stream.abort()
                        self.last_stream_flush_ms = (perf_counter_ns() - self._cancel_ns) / 1e6
                        break
                    stream.write(audio_data[i : i + chunk_size])
                    if not self._is_playing:
                        self._is_playing = True
                        response = self._current_response
                        response.delivery_status = DeliveryStatus.PLAYING
                        response.playback_started_ns = perf_counter_ns()
                        response.first_audio_device_write_ns = response.playback_started_ns
                        if response.tts_start_ns:
                            self.last_first_audio_delay_ms = (response.playback_started_ns - response.tts_start_ns) / 1e6
                        self._emit("tts.started", response)
            finally:
                self._stream = None

    def _emit(self, name, response, **data):
        if self.event_callback:
            self.event_callback(name, response.request_id, {"text": response.text, **data})

    def stop(self) -> None:
        """Stop playback thread and close resources."""
        self.cancel_current()
        self._running = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
        logger.info("AudioOutputManager stopped")
