"""Filler speech for long agent runs.

A multi-step task can think for several seconds before its first tool fires, and silence that long reads as a
crash. So when the agent (local or Claude) starts using a tool after a lull, JARVIS says one short line naming the
work - then stays quiet until it has the answer. One line per run, never progress chatter.

The phrasing follows the character's grammar rather than generic assistant-speak: working lines are subjectless
participles ("Cross-referencing.", "Checking your mail."), never "let me" or "I'm now"; acknowledgement is
deferential, not eager; no exclamation marks; "sir" goes at the end, and only sometimes.
"""
from __future__ import annotations

import random
import re
import time
from contextvars import ContextVar
from typing import Callable, Optional

WORKING = ["Working on it, sir.", "Compiling.", "Retrieving.", "Cross-referencing.", "Running the query now.",
           "Searching.", "Under way."]
ACKNOWLEDGE = ["As you wish, sir.", "Very good, sir.", "Certainly.", "Understood.", "Consider it done."]
ATTENTION = ["Yes, sir?", "Sir?", "At your service, sir.", "Standing by."]


class Picker:
    """Random line that never repeats the previous one - repetition is what makes canned lines sound canned."""

    def __init__(self, pool: list[str], rng: random.Random | None = None) -> None:
        self.pool, self.last, self.rng = list(pool), -1, rng or random.Random()

    def __call__(self) -> str:
        if len(self.pool) < 2:
            return self.pool[0] if self.pool else ""
        i = self.last
        while i == self.last:
            i = self.rng.randrange(len(self.pool))
        self.last = i
        return self.pool[i]


working, acknowledge, attention = Picker(WORKING), Picker(ACKNOWLEDGE), Picker(ATTENTION)

# Tool name -> line. Order matters: specific before general; short words are word-bounded so they do not hide inside
# longer ones. An MCP name (mcp__server__tool) is split so the server and the tool are matched separately.
_RULES: list[tuple[Optional[re.Pattern], Optional[re.Pattern], list[str]]] = [
    (None, re.compile(r"whatsapp"), ["Checking WhatsApp.", "Going through your chats."]),
    (re.compile(r"gmail|\bmail\b"), re.compile(r"gmail|\bmail\b|email|inbox"), ["Checking your mail.", "Reading the inbox."]),
    (None, re.compile(r"calendar|\bdiary\b|\bmeeting|\bevents?\b"), ["Checking your calendar.", "Consulting the diary."]),
    (re.compile(r"playwright|puppeteer|chrome|browser"), re.compile(r"\bbrowser|browse|navigate|open_url|web_agent|\btab"),
     ["Opening the browser.", "Navigating."]),
    (re.compile(r"android|\badb\b|phone"), re.compile(r"phone|android|\bdevice|\bapk\b|\badb\b"),
     ["Reaching the device.", "Connecting to your phone."]),
    (None, re.compile(r"screenshot|screen|vision|camera|look|watch"), ["Having a look.", "Examining the screen."]),
    (re.compile(r"\bexa\b|serper|perplexity|tavily|brave"), re.compile(r"search_web|web_?search|web_?fetch|\bfetch\b|research|news|weather"),
     ["Searching.", "Consulting the record."]),
    (None, re.compile(r"\bfiles?\b|find_file|folder|director|document|pdf|knowledge|notes?\b|rag"),
     ["Searching your files.", "Retrieving."]),
    (re.compile(r"spotify|sonos"), re.compile(r"\bplay|music|playlist|\btrack|media"), ["Queuing it up.", "Putting it on."]),
    (re.compile(r"github|linear|jira|sentry"), re.compile(r"\brepo|repository|\bissues?\b|pull_request|\bgit\b|commit"),
     ["Checking the repository.", "Consulting the tracker."]),
    (None, re.compile(r"powershell|\bbash\b|command|terminal|install"), ["Running it now.", "Under way."]),
]
_PICKERS = [(server, tool, Picker(lines)) for server, tool, lines in _RULES]


def _split(name: str) -> tuple[str, str]:
    m = re.match(r"^mcp__(.+?)__(.+)$", name or "")
    if m:
        return m.group(1).lower(), m.group(2).lower()
    return "", (name or "").lower()


def for_tool(name: str) -> str:
    """A line suited to the tool that just fired; a neutral one when unsure (better than a confident wrong one)."""
    server, tool = _split(name)
    if server == "jarvis":                     # JARVIS's own tools exposed to Claude: judge by the tool half
        server = ""
    for server_rx, tool_rx, pick in _PICKERS:
        if (server_rx is not None and server and server_rx.search(server)) or (tool_rx is not None and tool_rx.search(tool)):
            return pick()
    return working()


# ---------------------------------------------------------------------------------------------- per-run announcer
current_announcer: ContextVar[Optional["Announcer"]] = ContextVar("jarvis_tool_announcer", default=None)


class Announcer:
    """Says at most one tool line per run, and only after the run has been silent for ``lull_s`` seconds."""

    def __init__(self, speak: Callable[[str], None], lull_s: float = 2.5, clock: Callable[[], float] = time.monotonic):
        self.speak, self.lull_s, self.clock = speak, lull_s, clock
        self.started = clock()
        self.spoken: str | None = None

    def tool_started(self, name: str) -> str | None:
        if self.spoken is not None or self.clock() - self.started < self.lull_s:
            return None
        self.spoken = for_tool(name)
        try:
            self.speak(self.spoken)
        except Exception:
            pass
        return self.spoken


def announce_tool(name: str) -> str | None:
    announcer = current_announcer.get()
    return announcer.tool_started(name) if announcer is not None else None
