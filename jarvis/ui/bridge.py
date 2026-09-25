"""Asynchronous WebSocket and HTTP client bridge connecting UI to JARVIS backend."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable
from urllib.parse import urljoin
import urllib.request
import urllib.error
import websockets
from websockets.exceptions import ConnectionClosed

from PySide6.QtCore import QObject, QThread, Signal, Slot

from jarvis.ui.events import AssistantState, ConnectionState, UIEvent, UIEventType, redact_sensitive_text

logger = logging.getLogger("jarvis.ui.bridge")

RECONNECT_DELAYS = [0.5, 1.0, 2.0, 5.0, 10.0]


class BridgeWorker(QObject):
    """Worker running in a background QThread managing the WebSocket connection."""

    connectionChanged = Signal(str)
    eventReceived = Signal(object)  # UIEvent
    responseReceived = Signal(dict)
    pingUpdated = Signal(int)

    def __init__(self, ws_url: str = "ws://127.0.0.1:8765/ws", http_url: str = "http://127.0.0.1:8765") -> None:
        super().__init__()
        self.ws_url = ws_url
        self.http_url = http_url
        self._running = False
        self._ws: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._send_queue: asyncio.Queue[dict[str, Any]] | None = None

    @Slot()
    def start(self) -> None:
        """Start async loop in background worker thread."""
        self._running = True
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._run())

    @Slot()
    def stop(self) -> None:
        self._running = False
        if self._loop and self._loop.is_running():
            if self._ws:
                asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop)

    def send_control(self, kind):
        if self._loop and self._send_queue is not None and self._ws:
            self._loop.call_soon_threadsafe(self._send_queue.put_nowait,
                {"version": 1, "type": kind, "request_id": f"ui_{time.time_ns()}"})
        else:
            self.eventReceived.emit(UIEvent(UIEventType.VOICE_ERROR, payload={"error": "Backend disconnected"}))

    def send_command(self, text: str, request_id: str | None = None) -> None:
        """Enqueue command from main thread."""
        req_id = request_id or f"ui_{int(time.time() * 1000)}"
        msg = {
            "version": 1,
            "type": "command",
            "request_id": req_id,
            "text": text,
        }
        if self._loop and self._send_queue and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._send_queue.put_nowait, msg)
        else:
            # Fallback direct HTTP POST
            self._send_http_command(text, req_id)

    def _send_http_command(self, text: str, req_id: str) -> None:
        def _post() -> None:
            try:
                url = f"{self.http_url}/command"
                payload = json.dumps({"text": text, "request_id": req_id, "source": "websocket"}).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=10.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    self.responseReceived.emit(data)
            except Exception as exc:
                logger.warning("HTTP command post failed: %s", exc)
                self.responseReceived.emit({
                    "request_id": req_id,
                    "state": "FAILED",
                    "message": f"Connection error: {exc}",
                })
        import threading
        threading.Thread(target=_post, daemon=True).start()

    async def _run(self) -> None:
        self._send_queue = asyncio.Queue()
        retry_idx = 0

        while self._running:
            self.connectionChanged.emit(ConnectionState.RECONNECTING.value if retry_idx > 0 else ConnectionState.OFFLINE.value)
            try:
                # Test HTTP health first
                health_ok = await self._check_health()
                if not health_ok:
                    raise ConnectionError("JARVIS backend health endpoint unreachable")

                # Connect WebSocket
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=10,
                    ping_timeout=5,
                    close_timeout=2,
                ) as ws:
                    self._ws = ws
                    retry_idx = 0
                    self.connectionChanged.emit(ConnectionState.ONLINE.value)
                    self.eventReceived.emit(UIEvent(event_type=UIEventType.JARVIS_READY))

                    receiver_task = asyncio.create_task(self._receive_loop(ws))
                    sender_task = asyncio.create_task(self._send_loop(ws))
                    ping_task = asyncio.create_task(self._ping_loop(ws))

                    done, pending = await asyncio.wait(
                        [receiver_task, sender_task, ping_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for t in pending:
                        t.cancel()

            except Exception as exc:
                logger.debug("Backend connection error: %s", exc)
                self.connectionChanged.emit(ConnectionState.OFFLINE.value)
                self.eventReceived.emit(UIEvent(event_type=UIEventType.JARVIS_OFFLINE))

            if not self._running:
                break

            delay = RECONNECT_DELAYS[min(retry_idx, len(RECONNECT_DELAYS) - 1)]
            retry_idx += 1
            await asyncio.sleep(delay)

    async def _check_health(self) -> bool:
        loop = asyncio.get_running_loop()
        def _get() -> bool:
            try:
                url = f"{self.http_url}/health"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    return resp.status == 200
            except Exception:
                return False
        return await loop.run_in_executor(None, _get)

    async def _send_loop(self, ws: Any) -> None:
        assert self._send_queue is not None
        while self._running:
            msg = await self._send_queue.get()
            try:
                await ws.send(json.dumps(msg))
            finally:
                self._send_queue.task_done()

    async def _receive_loop(self, ws: Any) -> None:
        while self._running:
            try:
                raw = await ws.recv()
                data = json.loads(raw)
                msg_type = data.get("type")
                if msg_type == "event":
                    mapping = {
                        "audio.level": UIEventType.AUDIO_LEVEL,
                        "voice.listening": UIEventType.LISTENING_STARTED,
                        "voice.speech_ended": UIEventType.LISTENING_STOPPED,
                        "voice.partial": UIEventType.TRANSCRIPT_PARTIAL,
                        "voice.final": UIEventType.TRANSCRIPT_FINAL,
                        "voice.wake_detected": UIEventType.WAKE_DETECTED,
                        "voice.error": UIEventType.VOICE_ERROR,
                        "voice.idle": UIEventType.VOICE_IDLE,
                        "request.received": UIEventType.TASK_STARTED,
                        "tts.started": UIEventType.TTS_STARTED,
                        "tts.stopped": UIEventType.TTS_STOPPED,
                        "tts.error": UIEventType.VOICE_ERROR,
                        "whatsapp.status": UIEventType.INTEGRATION_STATE,
                        "confirmation.required": UIEventType.CONFIRMATION_REQUIRED,
                    }
                    event_type = mapping.get(data.get("event"))
                    if event_type:
                        self.eventReceived.emit(UIEvent(event_type, data.get("request_id", ""), data.get("payload", {})))
                elif msg_type == "task_state":
                    self.eventReceived.emit(UIEvent(
                        event_type=UIEventType.TASK_STARTED,
                        request_id=data.get("request_id", ""),
                        payload=data,
                    ))
                elif msg_type == "task_result":
                    self.responseReceived.emit(data)
                    state = data.get("state", "SUCCESS")
                    if state == "SUCCESS":
                        ev_type = UIEventType.TASK_COMPLETED
                    elif state == "WAITING_CONFIRMATION":
                        ev_type = UIEventType.CONFIRMATION_REQUIRED
                    else:
                        ev_type = UIEventType.TASK_FAILED
                    self.eventReceived.emit(UIEvent(
                        event_type=ev_type,
                        request_id=data.get("request_id", ""),
                        payload=data,
                    ))
                elif msg_type == "pong":
                    pass
                elif msg_type == "error":
                    self.eventReceived.emit(UIEvent(
                        event_type=UIEventType.TASK_FAILED,
                        request_id=data.get("request_id", ""),
                        payload={"error": data.get("error", "Unknown error")},
                    ))
            except ConnectionClosed:
                break
            except Exception as exc:
                logger.warning("Error receiving WS message: %s", exc)

    async def _ping_loop(self, ws: Any) -> None:
        while self._running:
            await asyncio.sleep(5)
            t0 = time.perf_counter()
            try:
                await ws.send(json.dumps({"version": 1, "type": "ping", "request_id": "ping"}))
                t1 = time.perf_counter()
                ping_ms = max(1, int((t1 - t0) * 1000))
                self.pingUpdated.emit(ping_ms)
            except Exception:
                break


class JarvisUIBridge(QObject):
    """Facade for QML/Controller connecting UI with BridgeWorker."""

    connectionChanged = Signal(str)
    eventReceived = Signal(object)
    responseReceived = Signal(dict)
    pingUpdated = Signal(int)

    def __init__(self, ws_url: str = "ws://127.0.0.1:8765/ws", http_url: str = "http://127.0.0.1:8765", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.thread = QThread()
        self.worker = BridgeWorker(ws_url, http_url)
        self.worker.moveToThread(self.thread)

        # Connect signals
        self.thread.started.connect(self.worker.start)
        self.worker.connectionChanged.connect(self.connectionChanged)
        self.worker.eventReceived.connect(self.eventReceived)
        self.worker.responseReceived.connect(self.responseReceived)
        self.worker.pingUpdated.connect(self.pingUpdated)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.worker.stop()
        self.thread.quit()
        self.thread.wait(2000)

    def send_command(self, text: str, request_id: str | None = None) -> None:
        self.worker.send_command(text, request_id)

    def send_control(self, kind):
        self.worker.send_control(kind)
