import importlib.util
import uvicorn
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
    uvicorn.run(create_app(Runtime(config)), **options)

if __name__ == "__main__":
    main()
