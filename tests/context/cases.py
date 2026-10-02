"""Context suite: multi-turn conversations, judged turn by turn on the full CommandService.

Written and frozen before the context fixes of this round. Each turn is (text, expect):
- "tool"                      the turn runs this tool (or asks to confirm it)
- ("tool", {arg: value})      ... with these arguments (case-insensitive substring match)
- "CLARIFY"                   no tool runs and JARVIS asks
- "ANY"                       not scored (setup turn whose tool may vary)
A pipe in the tool name allows alternatives.
"""
from __future__ import annotations

CONVERSATIONS: list[list[tuple[str, object]]] = [
    # reference to the last app
    [("open notepad", ("open_app", {"name": "notepad"})), ("close it", ("close_app", {"name": "notepad"}))],
    [("open paint", ("open_app", {"name": "paint"})), ("minimize it", ("minimize_window|window_op", {})),
     ("bring it back", ("restore_window|window_op|maximize_window|switch_window", {}))],
    [("launch spotify", ("open_app", {"name": "spotify"})), ("actually close that", ("close_app", {"name": "spotify"}))],
    [("open vlc", ("open_app", {"name": "vlc"})), ("restart it", ("system_op|restart_app", {}))],
    # app in a browser
    [("open calculator on chrome", ("open_website", {"url": "calculator", "browser": "chrome"}))],
    [("on calculator on chrome", ("open_website", {"url": "calculator", "browser": "chrome"}))],
    [("open google maps in edge", ("open_website", {"url": "maps", "browser": "edge"}))],
    [("open translate in firefox", ("open_website", {"url": "translate", "browser": "firefox"}))],
    # several apps, ordinal and additive references
    [("open chrome", ("open_app", {"name": "chrome"})), ("open calculator too", ("open_app", {"name": "calculator"})),
     ("close the first one", ("close_app", {"name": "chrome"}))],
    [("open notepad", ("open_app", {"name": "notepad"})), ("and paint as well", ("open_app", {"name": "paint"})),
     ("close both", "close_app")],
    [("open word", ("open_app", {"name": "word"})), ("open excel also", ("open_app", {"name": "excel"})),
     ("close the last one", ("close_app", {"name": "excel"}))],
    # repeat the last action with a new target
    [("open notepad", ("open_app", {"name": "notepad"})), ("do the same for calculator", ("open_app", {"name": "calculator"}))],
    [("close notepad", ("close_app", {"name": "notepad"})), ("same with paint", ("close_app", {"name": "paint"}))],
    [("open notepad", ("open_app", {"name": "notepad"})), ("now calculator", ("open_app", {"name": "calculator"}))],
    [("search for python tutorials", ("search_web", {"query": "python tutorials"})),
     ("now search for java tutorials", ("search_web", {"query": "java tutorials"}))],
    [("what's the weather in chennai", "search_web|quick_answer|CHAT"),
     ("and in pune?", ("search_web|quick_answer", {"query": "pune"}))],
    [("send ravi i'm late", ("send_whatsapp_message", {"recipient": "ravi"})),
     ("also to meena", ("send_whatsapp_message", {"recipient": "meena", "message": "late"}))],
    # modify a number of the last action
    [("set volume to 30", ("volume_set", {"percent": "30"})), ("make it 60", ("volume_set", {"percent": "60"})),
     ("actually 40", ("volume_set", {"percent": "40"}))],
    [("set brightness to 50", ("brightness_set", {})), ("make it 80", ("brightness_set", {"value": "80"}))],
    [("set volume to 20", ("volume_set", {"percent": "20"})), ("a little higher", "volume_up|volume_set")],
    [("remind me to call ravi at 5 pm", "set_reminder"), ("make it 6", ("set_reminder", {"time": "6"}))],
    # corrections after an action
    [("open calculator", ("open_app", {"name": "calculator"})), ("no, notepad", ("open_app", {"name": "notepad"}))],
    [("open paint", ("open_app", {"name": "paint"})), ("sorry i meant word", ("open_app", {"name": "word"}))],
    [("set volume to 70", ("volume_set", {"percent": "70"})), ("no i said 17", ("volume_set", {"percent": "17"}))],
    # pronouns inside a new command
    [("open youtube", "open_website|open_app"), ("play lofi on it", ("play_youtube", {"query": "lofi"}))],
    [("find report.pdf", ("find_file", {})), ("open it", ("open_file|find_file", {}))],
    # questions about what just happened
    [("open spotify", ("open_app", {"name": "spotify"})), ("what did you just open", "recent_actions|CHAT")],
    [("set volume to 45", ("volume_set", {"percent": "45"})), ("what did you set it to", "recent_actions|CHAT|volume_get|volume_status")],
    # context must not leak into an unrelated, complete command
    [("open notepad", ("open_app", {"name": "notepad"})), ("what time is it", "get_time")],
    [("set volume to 30", ("volume_set", {"percent": "30"})), ("set brightness to 60", ("brightness_set", {}))],
    [("open chrome", ("open_app", {"name": "chrome"})), ("search for cricket score", ("search_web", {"query": "cricket score"}))],
    # unclear references must ask, never guess a consequential action
    [("delete it", "CLARIFY")],
    [("send it to him", "CLARIFY")],
    [("open notepad", ("open_app", {"name": "notepad"})), ("delete it", "CLARIFY|delete_file")],
]
