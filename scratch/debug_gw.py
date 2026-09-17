import sys
from pathlib import Path
from fastapi.testclient import TestClient
from jarvis.config import Config
from jarvis.core.gateway.app import create_app
from jarvis.core.runtime import Runtime
from jarvis.tools.system.native import Empty, TimeOutput, SystemTool

def time_tool(function=None):
    return SystemTool("get_time", Empty, TimeOutput, function or (lambda _: {"iso": "2026-09-17T00:00:00+00:00"}))

tmp_path = Path("scratch/tmp_test")
tmp_path.mkdir(parents=True, exist_ok=True)
runtime = Runtime(Config(), root=tmp_path, tools_factory=lambda *_: [time_tool()])

with TestClient(create_app(runtime)) as client:
    print("Step 1: health", flush=True)
    print(client.get("/health").json(), flush=True)
    print("Step 2: tools", flush=True)
    print(client.get("/tools").json()[0]["name"], flush=True)
    print("Step 3: post command", flush=True)
    response = client.post("/command", json={"text": "time"}).json()
    print("Step 3 response:", response, flush=True)
    print("Step 4: websocket connect", flush=True)
    with client.websocket_connect("/ws") as ws:
        print("ws connected", flush=True)
        ws.send_json({"version": 1, "type": "ping", "request_id": "0"})
        print("ping sent", flush=True)
        pong = ws.receive_json()
        print("pong received:", pong, flush=True)
    print("Done ws", flush=True)
print("All Done!", flush=True)
