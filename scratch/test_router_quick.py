import asyncio
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.router.router import SmartRouter

async def main():
    r = SmartRouter()
    test_cases = [
        "open chrome",
        "don't open chrome",
        "can chrome open pdf files?",
        "stop",
        "volume thirty",
        "open studio",
        "open chrome and calculator",
        "find tomorrow ML material and put everything into one folder",
    ]
    for text in test_cases:
        res = await r.route(CommandRequest(text=text))
        print(f"INPUT: {text!r:65} -> LANE={res.lane:8} INTENT={str(res.intent):15} REASON={res.reason_code} MS={res.routing_ms:.3f}ms")

if __name__ == "__main__":
    asyncio.run(main())
