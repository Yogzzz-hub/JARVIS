import asyncio
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
pytest.importorskip('PySide6')
from jarvis.ui.bridge import BridgeWorker
from jarvis.ui.state import JarvisUIState


@pytest.mark.asyncio
async def test_ping_latency_waits_for_matching_pong():
    import json
    worker = BridgeWorker(); worker._running = True
    readings = []; worker.pingUpdated.connect(readings.append)
    class Socket:
        async def send(self, raw):
            request_id = json.loads(raw)['request_id']
            await asyncio.sleep(.025)
            worker._pongs[request_id].set_result(__import__('time').monotonic())
            worker._running = False
    await worker._ping_loop(Socket())
    assert readings and readings[0] >= 20
    assert worker.health.last_pong and not worker._pongs


def test_connection_changes_preserve_visible_conversation():
    state = JarvisUIState()
    state.add_turn('user', 'Fixture request')
    state.add_turn('assistant', 'Fixture final', state='SUCCESS')
    before = list(state.conversation)
    state.set_connection('RECONNECTING')
    state.set_connection('ONLINE')
    assert state.conversation == before


@pytest.mark.asyncio
async def test_socket_reconnects_automatically_after_one_second_drop_without_offline():
    import websockets
    from unittest.mock import AsyncMock
    connections = []
    worker = BridgeWorker()
    worker._check_health = AsyncMock(return_value=True)
    worker._running = True
    states = []; worker.connectionChanged.connect(states.append)
    async def handler(socket):
        connections.append(socket)
        if len(connections) == 1:
            await asyncio.sleep(1)
            await socket.close()
        else:
            worker._running = False
            await socket.close()
    async with websockets.serve(handler, '127.0.0.1', 0) as server:
        worker.ws_url = 'ws://127.0.0.1:'+str(server.sockets[0].getsockname()[1])
        await asyncio.wait_for(worker._run(), 5)
    assert len(connections) == 2 and states.count('ONLINE') == 2
    assert 'RECONNECTING' in states and 'OFFLINE' not in states
