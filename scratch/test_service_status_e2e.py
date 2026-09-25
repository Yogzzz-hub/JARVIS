import asyncio
import json
from jarvis.core.runtime import Runtime
from jarvis.core.commands.contracts import CommandRequest

async def main():
    runtime = Runtime()
    await runtime.start()
    service = runtime.service

    queries = [
        "Show microphone status",
        "Show speech recognition status",
        "Show wake word status",
        "Stop speaking",
        "Show connected devices",
        "be quiet",
    ]

    for q in queries:
        req = CommandRequest(text=q, request_id=f"test-req-{q[:4]}", source="voice")
        res = await service.handle(req)
        print(f"\n==========================================")
        print(f"QUERY: '{q}'")
        print(f"STATUS: {res.state.value if hasattr(res.state, 'value') else res.state}")
        print(f"MESSAGE: {res.message}")
        print(f"==========================================")

if __name__ == "__main__":
    asyncio.run(main())
