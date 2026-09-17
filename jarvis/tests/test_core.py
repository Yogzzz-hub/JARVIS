import asyncio
import json
import logging
from pathlib import Path
import sqlite3
import time
from unittest.mock import Mock
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from jarvis.config import Config, load
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.commands.resolver import resolve
from jarvis.core.events.bus import EventBus
from jarvis.core.gateway.app import create_app
from jarvis.core.logging_setup import LogQueue
from jarvis.core.metrics.clock import Clock, now_ns
from jarvis.core.persistence.writer import PersistenceWriter
from jarvis.core.runtime import Runtime
from jarvis.core.tasks.manager import State, TRANSITIONS, TaskManager
from jarvis.core.verifier.service import Verifier
from jarvis.tools.base import ToolResult, VerificationResult, ToolDefinition, RiskLevel, Tool
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.system.app_resolver import AppResolver, LaunchTarget
from jarvis.tools.system.native import Empty, TimeOutput, SystemTool, create_tools

def time_tool(function=None):
    return SystemTool("get_time", Empty, TimeOutput, function or (lambda _: {"iso": "2026-09-17T00:00:00+00:00"}))

@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setattr("jarvis.core.runtime.hardware_info", lambda: {})
    return Runtime(Config(), root=tmp_path, tools_factory=lambda *_: [time_tool()])

def test_config(tmp_path):
    config = load()
    assert config.server.host == "127.0.0.1" and config.server.workers == 1
    with pytest.raises(ValidationError):
        config.server.port = 99
    for data in ({"server": {"host": "0.0.0.0"}}, {"features": {"voice": True}},
                 {"performance": {"event_queue_size": 0}}, {"surprise": True}):
        with pytest.raises(ValidationError):
            Config.model_validate(data)

def test_contracts():
    with pytest.raises(ValidationError):
        CommandRequest(text="time", unknown=1)
    with pytest.raises(ValidationError):
        CommandRequest(text=42)
    with pytest.raises(ValidationError):
        ToolResult(success=True, error="bad", tool_name="x")
    with pytest.raises(ValidationError):
        ToolResult(success=False, tool_name="x")
    with pytest.raises(ValidationError):
        VerificationResult(verified=True, confidence=1.1, evidence={"a": 1})
    with pytest.raises(ValidationError):
        VerificationResult(verified=True, confidence=1.0)
    with pytest.raises(ValidationError):
        ToolDefinition(name="x", description="x", input_model=Empty, output_model=TimeOutput,
                       read_only=True, risk=RiskLevel.DESTRUCTIVE)

def test_registry(monkeypatch):
    registry = ToolRegistry()
    registry.discover([time_tool()])
    with pytest.raises(ValueError):
        registry.register(time_tool())
    with pytest.raises(ValueError):
        registry.register(Tool())
    registry.finalize()
    schema = registry.export_schema()
    monkeypatch.setattr(Empty, "model_json_schema", Mock(side_effect=AssertionError("regenerated")))
    assert registry.export_schema() is schema
    assert registry.contains("get_time")
    assert registry.search_by_tag("system")[0] is registry.get("get_time")
    with pytest.raises(RuntimeError):
        registry.register(time_tool())

@pytest.mark.parametrize("text,name,args", [("open notepad", "open_app", {"name": "notepad"}),
    ("volume 30", "volume_set", {"percent": 30}), ("time", "get_time", {}),
    ('list "C:/Some Folder"', "list_directory", {"path": "C:/Some Folder"})])
def test_grammar(text, name, args):
    assert resolve(text) == (name, args)

@pytest.mark.parametrize("text", ["volume 101", "volume -1", "volume 1.5", "open", "powershell delete", "volume ²"])
def test_invalid_grammar(text):
    with pytest.raises(ValueError):
        resolve(text)

def test_app_cache(monkeypatch, tmp_path):
    executable = tmp_path / "example.exe"
    executable.touch()
    resolver = AppResolver((("My App", str(executable)),))
    resolver.build()
    monkeypatch.setattr("shutil.which", Mock(side_effect=AssertionError("hot path disk lookup")))
    first = resolver.resolve(" MY  APP ")
    assert resolver.resolve("my app") is first
    assert resolver.build_count == 1
    if "calculator" in resolver.cache:
        assert resolver.resolve("calc") is resolver.resolve("calculator")
    with pytest.raises(ValueError):
        resolver.resolve("not indexed")

def test_state_transitions():
    manager = TaskManager(Mock(), Mock())
    for initial in State:
        for final in State:
            task = manager.create(CommandRequest(text="time"), Clock())
            task.state = initial
            if final in TRANSITIONS[initial]:
                manager.transition(task, final)
                assert task.state == final
            else:
                with pytest.raises(RuntimeError):
                    manager.transition(task, final)

async def test_event_isolation_and_bounds():
    bus = EventBus(1)
    blocked, delivered = asyncio.Event(), asyncio.Event()
    async def slow(event):
        await blocked.wait()
    async def fast(event):
        delivered.set()
    bus.subscribe(slow)
    bus.subscribe(fast)
    bus.emit("test", "1")
    await asyncio.wait_for(delivered.wait(), 0.5)
    for _ in range(20):
        bus.emit("test", "1")
    assert bus.dropped > 0
    assert all(q.qsize() <= 1 for q, _ in bus.subscribers)
    blocked.set()
    await bus.close()

async def test_subscriber_failure():
    bus = EventBus(2)
    async def failure(event):
        raise ValueError("diagnostic failure")
    bus.subscribe(failure)
    bus.emit("test", "r")
    await bus.close()
    assert bus.errors == 1

async def test_persistence_migration_batch_shutdown(tmp_path):
    path = tmp_path / "test.db"
    writer = PersistenceWriter(path, 1024)
    await writer.start()
    assert writer.pragmas["journal_mode"] == "wal" and writer.pragmas["synchronous"] == 1
    assert writer.pragmas["user_version"] >= 1 and writer.pragmas["busy_timeout"] == 3000
    for i in range(500):
        assert writer.enqueue("requests", str(i), {"text": "time"})
    await writer.close()
    assert writer.written == 500 and writer.max_batch > 1
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM requests").fetchone()[0] == 500
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    reopened = PersistenceWriter(path)
    await reopened.start()
    await reopened.close()

def test_persistence_bounded(tmp_path):
    writer = PersistenceWriter(tmp_path / "test.db", 1)
    assert writer.enqueue("requests", "1", {})
    assert not writer.enqueue("requests", "2", {})
    assert writer.dropped == 1
    with pytest.raises(ValueError):
        writer.enqueue("untrusted", "3", {})

async def test_log_queue(tmp_path):
    path = tmp_path / "log.jsonl"
    logs = LogQueue(path, 1024)
    logging.getLogger("jarvis.test").info("hello", extra={"request_id": "abc", "event": "test"})
    await logs.close()
    record = json.loads(path.read_text())
    assert record["request_id"] == "abc" and record["event"] == "test"
    assert set(record) == {"timestamp", "level", "request_id", "component", "event", "duration_ms", "message"}

def test_gateway_and_websocket(runtime):
    with TestClient(create_app(runtime)) as client:
        assert client.get("/health").json()["status"] == "ready"
        assert client.get("/tools").json()[0]["name"] == "get_time"
        response = client.post("/command", json={"text": "time"}).json()
        assert response["state"] == "SUCCESS"
        assert response["verification"]["verified"]
        assert response["metrics"]["first_action_ms"] >= 0
        snapshot = client.get("/tasks/" + response["request_id"]).json()
        assert snapshot["state"] == "RESPONDING" and snapshot["result"]["state"] == "SUCCESS"
        assert client.get("/tasks/missing").status_code == 404
        assert client.post("/command", json={"text": "time", "unknown": 1}).status_code == 422
        assert client.post("/command", json={"text": "unknown"}).json()["state"] == "FAILED"
        assert client.post("/command", json={"text": "time", "request_id": response["request_id"]}).status_code == 409
        with client.websocket_connect("/ws") as ws:
            for i in range(3):
                ws.send_json({"version": 1, "type": "ping", "request_id": str(i)})
                assert ws.receive_json()["type"] == "pong"
            ws.send_bytes(b"reserved")
            assert ws.receive_json()["type"] == "error"
            ws.send_json({"version": 1, "type": "command", "text": "time", "request_id": "ws-test"})
            assert ws.receive_json()["type"] == "task_state"
            result = ws.receive_json()
            assert result["type"] == "task_result" and result["state"] == "SUCCESS"
    assert not runtime.writer.thread.is_alive()
    assert runtime.writer.queue.unfinished_tasks == 0

async def test_mocked_launch_and_verification(tmp_path, monkeypatch):
    monkeypatch.setattr("jarvis.core.runtime.hardware_info", lambda: {})
    launches = []
    runtime = Runtime(Config(), root=tmp_path,
        tools_factory=lambda resolver, hardware: create_tools(resolver, hardware, lambda target: launches.append(target) or 123))
    await runtime.start()
    runtime.resolver.cache["test"] = LaunchTarget("test.exe", ("test.exe",))
    runtime.verifier.probe = lambda data: {"pid": 123}
    blocker = asyncio.Event()
    async def slow(event):
        await blocker.wait()
    runtime.bus.subscribe(slow)
    # Deliberately prevent persistence/log writes from being an execution dependency.
    original_enqueue = runtime.writer.enqueue
    runtime.writer.enqueue = lambda *args: False
    result = await runtime.service.handle(CommandRequest(text="open test"))
    assert result.state == "SUCCESS" and len(launches) == 1
    task = runtime.tasks.get(result.request_id)
    assert task.clock.tool_started_ns < task.clock.tool_returned_ns <= task.clock.verification_started_ns
    runtime.verifier = runtime.service.verifier = Verifier(1, 10, lambda _: None)
    failed = await runtime.service.handle(CommandRequest(text="open test"))
    assert failed.state == "FAILED" and not failed.tool_result.success
    runtime.writer.enqueue = original_enqueue
    blocker.set()
    await runtime.close()

async def test_cancellation_and_output_validation(runtime):
    await runtime.start()
    entered = asyncio.Event()
    async def delayed(*args):
        entered.set()
        await args[-1].wait()
        raise asyncio.CancelledError
    runtime.verifier.verify = delayed
    request = CommandRequest(text="time")
    running = asyncio.create_task(runtime.service.handle(request))
    await entered.wait()
    assert runtime.tasks.cancel(request.request_id)
    assert (await running).state == "CANCELLED"
    runtime.registry.get("get_time").function = lambda _: {"unknown": 4}
    assert (await runtime.service.handle(CommandRequest(text="time"))).state == "FAILED"
    await runtime.close()

def test_server_configuration(monkeypatch):
    from jarvis.__main__ import server_options
    options = server_options(Config())
    assert options["workers"] == 1 and options["loop"] == "asyncio"
    assert options["ws"] == "websockets-sansio" and options["ws_per_message_deflate"] is False
    monkeypatch.setattr("importlib.util.find_spec", lambda _: None)
    assert server_options(Config())["http"] == "h11"

def test_transport_mailbox_bound():
    from jarvis.core.gateway.websocket_protocol import IncomingQueue
    overload = Mock()
    queue = IncomingQueue(2, overload)
    for _ in range(100):
        queue.put_nowait({"type": "websocket.receive", "text": "x"})
    assert queue.qsize() == 2
    overload.assert_called_once()
    queue.put_nowait({"type": "websocket.disconnect"})
    assert queue.qsize() == 2

async def test_queue_saturation_does_not_delay_launch(runtime):
    await runtime.start()
    runtime.writer.closed = True
    result = await runtime.service.handle(CommandRequest(text="time"))
    assert result.state == "SUCCESS"
    assert runtime.writer.dropped > 0
    await runtime.close()

async def test_task_history_is_bounded():
    manager = TaskManager(Mock(), Mock(), capacity=2)
    first = manager.create(CommandRequest(text="time"), Clock())
    manager.create(CommandRequest(text="time"), Clock())
    with pytest.raises(RuntimeError):
        manager.create(CommandRequest(text="time"), Clock())
    first.result = True
    manager.create(CommandRequest(text="time"), Clock())
    assert len(manager.tasks) == 2 and manager.get(first.request_id) is None

async def test_real_h11_fallback(runtime, monkeypatch):
    import socket
    import uvicorn
    import httpx
    from jarvis.__main__ import server_options
    monkeypatch.setattr("importlib.util.find_spec", lambda _: None)
    options = server_options(Config())
    assert options["http"] == "h11"
    server = uvicorn.Server(uvicorn.Config(create_app(runtime), **options))
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    serving = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        async with asyncio.timeout(5):
            while not server.started:
                await asyncio.sleep(.01)
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:{port}/health")
            assert response.status_code == 200 and response.json()["status"] == "ready"
        assert "Proactor" in runtime.startup["event_loop"]
    finally:
        server.should_exit = True
        await serving
        sock.close()

def test_directory_tool(tmp_path):
    from jarvis.tools.system.native import DirectoryInput
    for name in ("a.txt", "b.txt", "c.txt"):
        (tmp_path / name).write_text("example")
    tools = {tool.definition.name: tool for tool in create_tools(AppResolver(), {})}
    output = tools["list_directory"].run(DirectoryInput(path=str(tmp_path), limit=2))
    assert len(output["entries"]) == 2 and output["truncated"]
    with pytest.raises(FileNotFoundError):
        tools["list_directory"].run(DirectoryInput(path=str(tmp_path / "missing")))

async def test_volume_verification(monkeypatch):
    from jarvis.tools.system.native import VolumeInput
    monkeypatch.setattr("jarvis.tools.system.native.volume", lambda: 30.0)
    result = ToolResult(success=True, data={"percent": 30.0}, tool_name="volume_set")
    verifier = Verifier()
    assert (await verifier.verify("volume_set", result, VolumeInput(percent=30), asyncio.Event())).verified
    assert not (await verifier.verify("volume_set", result, VolumeInput(percent=90), asyncio.Event())).verified

async def test_screenshot_verification(tmp_path):
    path = tmp_path / "test.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"test payload")
    result = ToolResult(success=True, data={"path": str(path), "bytes": path.stat().st_size}, tool_name="take_screenshot")
    assert (await Verifier().verify("take_screenshot", result, None, asyncio.Event())).verified
    path.write_bytes(b"bad")
    assert not (await Verifier().verify("take_screenshot", result, None, asyncio.Event())).verified

async def test_confirmation_required_is_not_executed(runtime):
    await runtime.start()
    tool = runtime.registry.get("get_time")
    tool.definition = tool.definition.model_copy(update={"requires_confirmation": True})
    tool.function = Mock(side_effect=AssertionError("must not invoke"))
    result = await runtime.service.handle(CommandRequest(text="time"))
    assert result.state == "FAILED" and result.metrics["first_action_ms"] is None
    tool.function.assert_not_called()
    await runtime.close()
