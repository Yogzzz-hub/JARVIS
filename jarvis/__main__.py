import importlib.util
import os
import socket
import uvicorn

# Default to manual test diagnostic mode for acceptance testing
os.environ.setdefault("JARVIS_TEST_MODE", "manual")

from jarvis.config import load
from jarvis.core.gateway.app import create_app
from jarvis.core.runtime import Runtime

def server_options(config):
    server = config.server
    http = server.http_backend
    if http == "httptools" and importlib.util.find_spec("httptools") is None:
        http = "h11"
    return dict(host=server.host, port=server.port, workers=1, loop="asyncio", http=http,
                ws=server.ws_backend, ws_per_message_deflate=False, access_log=server.access_log,
                ws_max_size=16384, ws_max_queue=16, timeout_graceful_shutdown=10)

def main():
    config = load()
    options = server_options(config)
    if options["ws"] == "websockets-sansio":
        from jarvis.core.gateway.websocket_protocol import BoundedSansIOProtocol
        options["ws"] = BoundedSansIOProtocol
    # Reserve the port before creating runtime workers or audio resources.
    # An exclusive socket also closes the simultaneous-launch race on Windows.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            listener.bind((options["host"], options["port"]))
        except OSError as exc:
            print(f"JARVIS cannot start: port {options['port']} is unavailable. "
                  f"Another instance may already be running. ({exc})", flush=True)
            return 1
        listener.listen(128)
        uvicorn.Server(uvicorn.Config(create_app(Runtime(config)), **options)).run(sockets=[listener])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
