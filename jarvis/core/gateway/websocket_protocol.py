"""Bound Uvicorn's Sans-I/O receive mailbox, including coalesced frame bursts.

Uvicorn pauses transport reads but its upstream queue has no maxsize. A single
TCP read may contain many frames. On overload close the connection explicitly;
never silently discard commands while leaving the client connected.
"""
import asyncio
from uvicorn.protocols.websockets.websockets_sansio_impl import WebSocketsSansIOProtocol

class IncomingQueue(asyncio.Queue):
    def __init__(self, size, overload):
        super().__init__(size)
        self.overload = overload
        self.overloaded = False

    def put_nowait(self, item):
        if self.overloaded and item["type"] != "websocket.disconnect":
            return
        if self.full():
            if item["type"] == "websocket.disconnect":
                self.get_nowait()
                self.task_done()
            else:
                self.overloaded = True
                self.overload()
                return
        super().put_nowait(item)

class BoundedSansIOProtocol(WebSocketsSansIOProtocol):
    def __init__(self, config, server_state, app_state, _loop=None):
        super().__init__(config, server_state, app_state, _loop)
        self.queue = IncomingQueue(config.ws_max_queue or 16, self._overload)

    def _overload(self):
        self.logger.warning("WebSocket receive capacity exceeded; closing connection")
        self.transport.close()
