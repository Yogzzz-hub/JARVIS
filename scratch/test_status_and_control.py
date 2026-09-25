import asyncio
from jarvis.core.router.router import SmartRouter
from jarvis.core.router.models import RouteLane
from jarvis.core.commands.contracts import CommandRequest
from jarvis.tools.system.computer_tools import (
    MicrophoneStatusTool,
    SpeechRecognitionStatusTool,
    WakeWordStatusTool,
    ConnectedDevicesTool,
)
from jarvis.core.response.formatter import ResponseFormatter
from jarvis.tools.base import ToolResult

async def main():
    print("--- TESTING TOOLS DIRECTLY ---")
    mic_tool = MicrophoneStatusTool()
    res_mic = mic_tool.run({})
    print("MIC TOOL:", res_mic)
    print("MIC FORMATTED:", ResponseFormatter.format_verified_tool("microphone_status", res_mic))

    stt_tool = SpeechRecognitionStatusTool()
    res_stt = stt_tool.run({})
    print("STT TOOL:", res_stt)
    print("STT FORMATTED:", ResponseFormatter.format_verified_tool("speech_recognition_status", res_stt))

    wake_tool = WakeWordStatusTool()
    res_wake = wake_tool.run({})
    print("WAKE TOOL:", res_wake)
    print("WAKE FORMATTED:", ResponseFormatter.format_verified_tool("wake_word_status", res_wake))

    dev_tool = ConnectedDevicesTool()
    res_dev = dev_tool.run({})
    print("DEV TOOL:", res_dev)
    print("DEV FORMATTED:", ResponseFormatter.format_verified_tool("connected_devices", res_dev))

    print("\n--- TESTING ROUTER MATCHING ---")
    router = SmartRouter()
    test_queries = [
        "Show microphone status",
        "Show speech recognition status",
        "Show wake word status",
        "Stop speaking",
        "Show connected devices",
        "microphone status",
        "speech recognition status",
        "wake word status",
        "stop talking",
        "be quiet",
        "silence",
        "connected devices",
        "list connected devices",
    ]

    for q in test_queries:
        req = CommandRequest(text=q, request_id="test-req-1", source="voice")
        decision = await router.route(req)
        print(f"Query: '{q}' -> Lane: {decision.lane}, Intent: {decision.intent}, Confidence: {decision.confidence}")

if __name__ == "__main__":
    asyncio.run(main())
