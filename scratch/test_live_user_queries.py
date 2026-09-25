import asyncio
import json
import websockets

async def test_queries():
    uri = "ws://127.0.0.1:8765/ws"
    async with websockets.connect(uri) as ws:
        queries = [
            "Show microphone status",
            "Show speech recognition status",
            "Show wake word status",
            "Stop speaking",
            "Show connected devices",
        ]

        print("=== LIVE JARVIS TEST RESULTS ===", flush=True)
        for q in queries:
            req_id = f"test-{abs(hash(q)) % 100000}"
            payload = {
                "version": 1,
                "type": "command",
                "text": q,
                "request_id": req_id,
            }
            await ws.send(json.dumps(payload))

            response_text = None
            start_time = asyncio.get_event_loop().time()

            while (asyncio.get_event_loop().time() - start_time) < 3.0:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.5)
                    data = json.loads(msg)
                    ev_type = data.get("type")
                    if ev_type == "task_result" and data.get("request_id") == req_id:
                        response_text = data.get("message")
                        break
                    elif ev_type == "error" and data.get("request_id") == req_id:
                        response_text = f"ERROR: {data.get('error')}"
                        break
                except asyncio.TimeoutError:
                    break

            print(f"\nYOU:    {q}", flush=True)
            print(f"JARVIS: {response_text}", flush=True)

if __name__ == "__main__":
    asyncio.run(test_queries())
