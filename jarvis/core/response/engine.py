from typing import Protocol

class ResponseSink(Protocol):
    async def deliver(self, text: str) -> None: ...

class ResponseEngine:
    def render(self, result, verification):
        if not result.success or not verification or not verification.verified:
            return result.error or (verification.error if verification else "Verification unavailable")
        data = result.data
        match result.tool_name:
            case "open_app": return f"{data['name'].capitalize()} is open."
            case "volume_set": return f"Volume set to {data['percent']:.0f}%."
            case "volume_get": return f"Volume is {data['percent']:.0f}%."
            case "take_screenshot": return "Screenshot saved."
            case "get_time": return data["iso"]
            case "list_directory": return f"{len(data['entries'])} entries" + (" (limited)." if data["truncated"] else ".")
            case "system_info": return f"{data['os']}; Python {data['python']}; {data['ram_total_mb'] / 1024:.1f} GB RAM."
        return "Completed and verified."
