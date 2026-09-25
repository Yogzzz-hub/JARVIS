import asyncio
from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from jarvis.core.commands.contracts import CommandRequest, CommandResult, WSInput
from jarvis.core.metrics.clock import Clock, now_ns
from jarvis.core.runtime import Runtime
from jarvis.tools.base import Contract

class Health(Contract):
    status: str
    tool_count: int
    database_status: str
    dropped_events: int
    dropped_persistence: int
    dropped_metrics: int
    dropped_logs: int

class TaskSnapshot(Contract):
    request_id: str
    source: str
    raw_text: str
    state: str
    created_at: str
    timestamps: dict[str, int]
    result: dict[str, Any] | None

class BoundaryClock:
    def __init__(self, app):
        self.app = app
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            scope.setdefault("state", {})["received_ns"] = now_ns()
        await self.app(scope, receive, send)

def create_app(runtime=None):
    runtime = runtime or Runtime()
    @asynccontextmanager
    async def lifespan(app):
        await runtime.start()
        app.state.runtime = runtime
        try:
            yield
        finally:
            await runtime.close()

    app = FastAPI(title="JARVIS EDGE", lifespan=lifespan)
    app.add_middleware(BoundaryClock)

    @app.middleware("http")
    async def reject_browser_commands(request: Request, call_next):
        # Match the WebSocket boundary: browser pages cannot authorize actions.
        if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get("origin"):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=403, content={"detail": "Browser-origin commands are not supported"})
        return await call_next(request)

    @app.get("/health", response_model=Health)
    async def health():
        return Health(status="ready" if runtime.ready else "stopping", tool_count=len(runtime.registry.list()),
                      database_status=runtime.writer.error or "ready", dropped_events=runtime.bus.dropped,
                      dropped_persistence=runtime.writer.dropped, dropped_metrics=runtime.metrics.dropped,
                      dropped_logs=runtime.logs.handler.dropped)

    @app.get("/tools", response_model=list[dict[str, Any]])
    async def tools():
        return runtime.registry.export_schema()

    @app.get("/voice/status")
    async def voice_status():
        return runtime.voice_status()

    @app.post("/command", response_model=CommandResult)
    async def command(body: CommandRequest, request: Request):
        try:
            return await runtime.service.handle(body, Clock(received_ns=request.state.received_ns, parsed_ns=now_ns()))
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        except RuntimeError as exc:
            if "capacity" in str(exc) or "shutting down" in str(exc):
                raise HTTPException(503, str(exc)) from exc
            raise

    @app.get("/tasks/{request_id}", response_model=TaskSnapshot)
    async def task(request_id: str):
        found = runtime.tasks.get(request_id)
        if found is None:
            raise HTTPException(404, "Task not found")
        return found.snapshot()

    @app.websocket("/ws")
    async def ws(socket: WebSocket):
        # Reject browser-origin traffic until an authenticated browser client exists.
        if socket.headers.get("origin"):
            await socket.close(code=1008)
            return
        await socket.accept()
        outgoing = asyncio.Queue(128)
        commands = asyncio.Queue(2)

        async def forward_event(event):
            if event.name == "response.ready":
                if event.data.get("source") != "websocket":
                    await outgoing.put({"version": 1, "type": "task_result", **event.data["result"]})
            elif event.name.startswith(("voice.", "audio.", "tts.", "whatsapp.", "integration.", "confirmation.")):
                message = {"version": 1, "type": "event", "event": event.name,
                           "request_id": event.request_id, "payload": event.data}
                if event.name == "audio.level" and outgoing.full():
                    return
                await outgoing.put(message)

        subscription = runtime.bus.subscribe(forward_event)
        if runtime.config.features.voice and not (runtime.voice and runtime.voice.is_running):
            await outgoing.put({"version": 1, "type": "event", "event": "voice.error",
                                "payload": {"error": runtime.voice_error or "Microphone unavailable"}})
        if hasattr(runtime, "whatsapp_service") and runtime.whatsapp_service:
            ws_state = getattr(runtime.whatsapp_service.transport.status, "state", "DISCONNECTED")
            await outgoing.put({"version": 1, "type": "event", "event": "whatsapp.status",
                                "payload": {"state": ws_state}})

        async def send():
            while True:
                await socket.send_json(await outgoing.get())

        async def execute():
            while True:
                message, clock = await commands.get()
                try:
                    await outgoing.put({"version": 1, "type": "task_state", "request_id": message.request_id, "state": "UNDERSTANDING"})
                    result = await runtime.service.handle(CommandRequest(text=message.text, request_id=message.request_id, source="websocket"), clock)
                    await outgoing.put({"version": 1, "type": "task_result", **result.model_dump(mode="json")})
                    if asyncio.current_task().cancelling():
                        return
                except (ValueError, RuntimeError) as exc:
                    await outgoing.put({"version": 1, "type": "error", "request_id": message.request_id, "error": str(exc)})
                finally:
                    commands.task_done()

        sender, executor = asyncio.create_task(send()), asyncio.create_task(execute())
        try:
            while True:
                frame = await socket.receive()
                if frame["type"] == "websocket.disconnect":
                    break
                stamp = now_ns()
                request_id = None
                try:
                    if frame.get("bytes") is not None:
                        raise ValueError("Binary frames are reserved for a later protocol version")
                    message = WSInput.model_validate_json(frame["text"])
                    request_id = message.request_id
                    if message.type == "ping":
                        await outgoing.put({"version": 1, "type": "pong", "request_id": request_id})
                    elif message.type == "stop_speaking":
                        runtime.service.response.stop_speaking()
                    elif message.type in ("ptt_start", "ptt_stop"):
                        if not runtime.voice or not runtime.voice.is_running:
                            raise ValueError(runtime.voice_error or "Voice input is unavailable")
                        if message.type == "ptt_start":
                            runtime.voice.request_ptt()
                        else:
                            runtime.voice.release_ptt()
                    elif not message.text:
                        raise ValueError("command requires text")
                    else:
                        commands.put_nowait((message, Clock(received_ns=stamp, parsed_ns=now_ns())))
                except (ValidationError, ValueError, RuntimeError, asyncio.QueueFull) as exc:
                    await outgoing.put({"version": 1, "type": "error", "request_id": request_id,
                                        "error": "Command queue full" if isinstance(exc, asyncio.QueueFull) else str(exc)})
        except WebSocketDisconnect:
            return
        finally:
            await runtime.bus.unsubscribe(subscription)
            sender.cancel()
            executor.cancel()
            await asyncio.gather(sender, executor, return_exceptions=True)
    return app
