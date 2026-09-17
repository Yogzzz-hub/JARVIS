def resolve(text: str) -> tuple[str, dict]:
    text = text.strip()
    lowered = text.casefold()
    exact = {"time": "get_time", "system info": "system_info", "screenshot": "take_screenshot", "volume": "volume_get"}
    if lowered in exact:
        return exact[lowered], {}
    verb, separator, rest = text.partition(" ")
    rest = rest.strip()
    if separator and rest:
        match verb.casefold():
            case "open": return "open_app", {"name": rest}
            case "list": return "list_directory", {"path": rest.strip('"')}
            case "volume":
                if rest.isascii() and rest.isdecimal() and 0 <= int(rest) <= 100:
                    return "volume_set", {"percent": int(rest)}
                raise ValueError("Volume must be an integer from 0 to 100")
    raise ValueError("Supported: open <app>, volume <0-100>, list <path>, screenshot, time, system info")
