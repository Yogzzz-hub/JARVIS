"""Conversation carry-over: turn a short follow-up into the full command it stands for.

People rarely repeat themselves. After "set volume to 30" they say "make it 60"; after "open notepad", "do the same
for calculator", "close it" or "no, paint"; after opening two apps, "close the first one"; after "send ravi I'm late",
"also to meena". This module keeps what the last few *executed* commands were and rewrites such a follow-up into a
complete sentence ("set volume to 60", "open calculator", "close notepad", "send meena I'm late").

The rewrite is plain text and goes back through the normal router, so every guard, policy and confirmation still
applies: a carried-over "send" asks for confirmation exactly like a typed one. It works on construction shapes
(new target, new number, pronoun, ordinal), never on particular sentences. It never resolves a pronoun for
destructive or sharing verbs (delete, uninstall, send, share ...); those keep asking. With no recent command, or
when the follow-up is not one of these shapes, it does nothing.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

TTL_S = 15 * 60          # a follow-up refers to something done in the last quarter hour
_NUM = r"\d+(?:\.\d+)?"

# Arguments that name what a command acted on, most specific first.
_TARGET_KEYS = ("name", "app", "target", "recipient", "contact", "to", "city", "location", "path", "file", "query", "title", "url")
# Verbs that act on an app or window and may take "it" / "the first one" for the app just used.
_APP_VERBS = (r"close|quit|exit|kill|shut|restart|reopen|relaunch|minimi[sz]e|maximi[sz]e|hide|show|focus|switch\s+to|"
              r"go\s+to|open|launch|start|bring\s+back|bring\s+up|restore|snap|move|resize|full\s*screen|pin")
# Verbs whose object is never guessed from context.
_NEVER = re.compile(r"\b(?:delete|remove|erase|wipe|trash|uninstall|send|share|forward|post|upload|email|mail|message|text|"
                    r"whatsapp|pay|buy|order|format|rename|move\s+(?:it|that|this)\s+to|install|reply)\b")
# Words that start a full command of their own ("and open chrome" is a new command, not a new target).
_VERB_START = re.compile(
    r"^(?:open|close|launch|start|run|play|pause|stop|set|turn|switch|search|find|look|show|tell|send|message|text|call|"
    r"remind|create|make|delete|remove|install|uninstall|update|take|lock|restart|shut|mute|unmute|increase|decrease|"
    r"raise|lower|go|navigate|visit|type|write|read|copy|paste|move|rename|minimi[sz]e|maximi[sz]e|what|who|where|when|"
    r"why|how|is|are|do|does|can|could|will|would|please|check|get|put|add|save|download|upload|share)\b")
# A new target is a name or a place, never a function word, a negation or an answer.
_NOT_A_TARGET = re.compile(r"^(?:don'?t|do\s+not|not|never|stop|cancel|wait|leave|forget|nothing|nevermind|thanks?|thank|ok|okay|"
                           r"yes|yeah|yep|no|nope|please|that'?s|it'?s|its|i|you|we|he|she|they|my\s+bad|then|so|what|why|how|"
                           r"again|more|less|later|now|too|also|instead|anyway|whatever|fine|good|great|cool|done)\b")
_ADJUSTABLE = ("volume", "brightness", "zoom", "speed", "font size", "temperature")
_UP = r"(?:louder|higher|brighter|up|more|bigger|faster|increase\s+it)"
_DOWN = r"(?:quieter|softer|lower|dimmer|darker|down|less|smaller|slower|decrease\s+it)"
_ORD = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2, "fourth": 3, "4th": 3,
        "last": -1, "latest": -1, "previous": -2}
_LIST_TOOLS = ("search_web", "find_file", "search_files", "list_directory", "read_whatsapp_messages", "gmail_list_recent",
               "list_reminders", "search_news", "knowledge_search")
_APP_TOOLS = ("open_app", "close_app", "focus_app", "switch_window", "minimize_window", "maximize_window", "window_op",
              "system_op")


@dataclass
class Turn:
    text: str
    tool: str
    slots: dict[str, Any]
    at: float = field(default_factory=time.monotonic)
    wall: float = field(default_factory=time.time)

    def target(self) -> tuple[str, str] | None:
        for key in _TARGET_KEYS:
            v = self.slots.get(key)
            if isinstance(v, str) and v.strip():
                return key, v.strip()
        return None


class CarryOver:
    def __init__(self) -> None:
        self.turns: list[Turn] = []
        self.apps: list[str] = []          # apps opened in this conversation, oldest first, closed ones removed

    # ---------------------------------------------------------------- recording
    def record(self, text: str, tool: str, slots: dict[str, Any] | None, app: str = "") -> None:
        if not text or not tool or tool in ("clarify", "recent_actions", "command_history"):
            return
        self.turns.append(Turn(" ".join(text.split()), tool, dict(slots or {})))
        del self.turns[:-8]
        name = (app or (slots or {}).get("name") or "").strip()
        if tool == "open_app" and name:
            self.apps = [a for a in self.apps if a.lower() != name.lower()] + [name]
            del self.apps[:-6]
        elif tool == "close_app" and name:
            self.apps = [a for a in self.apps if a.lower() != name.lower()]

    def last(self) -> Turn | None:
        if self.turns and time.monotonic() - self.turns[-1].at <= TTL_S:
            return self.turns[-1]
        return None

    # ---------------------------------------------------------------- rewriting
    def rewrite(self, text: str) -> str | None:
        """The complete command a follow-up stands for, or None when it is not a follow-up this can resolve."""
        t = " ".join((text or "").lower().split()).strip(" .!?")
        t = re.sub(r"^(?:hey\s+|ok\s+|okay\s+)?jarvis\s*,?\s+", "", t)
        if not t or len(t.split()) > 9:
            return None
        last = self.last()
        for step in (self._additive, self._ordinal, self._pronoun, self._number, self._relative, self._new_target):
            out = step(t, last)
            if out:
                return out
        return None

    @staticmethod
    def _additive(t: str, last: Turn | None) -> str | None:
        """'open calculator too' -> 'open calculator' (a complete command with an additive word)."""
        m = re.match(r"^(?:and\s+|also\s+|then\s+)?(?P<cmd>.+?)\s*,?\s+(?:too|also|as\s+well)$", t)
        if m and _VERB_START.match(m.group("cmd")) and not _NEVER.search(m.group("cmd")) and len(m.group("cmd").split()) >= 2:
            return m.group("cmd")
        return None

    def _ordinal(self, t: str, last: Turn | None) -> str | None:
        """'close the first one' / 'close both' over the apps opened in this conversation."""
        if not self.apps or (last is not None and last.tool in _LIST_TOOLS):
            return None
        m = re.match(rf"^(?:now\s+|and\s+|then\s+)?(?P<v>{_APP_VERBS})\s+(?:the\s+)?(?:(?P<o>first|1st|second|2nd|third|3rd|fourth|4th|"
                     rf"last|latest|previous)(?:\s+(?:one|app|window|program))?|(?P<all>both(?:\s+of\s+them)?|all\s+of\s+them|"
                     rf"them\s+all|them|both\s+apps|all\s+(?:those|these|the)\s+apps))$", t)
        if not m:
            return None
        verb = m.group("v")
        if verb in ("open", "launch", "start"):
            return None   # "open the second one" is about a list of results, not the apps already open
        if m.group("all"):
            if len(self.apps) < 2:
                return None
            return " and ".join(f"{verb} {a}" for a in self.apps)
        idx = _ORD[m.group("o")]
        if idx >= len(self.apps) or -idx > len(self.apps):
            return None
        return f"{verb} {self.apps[idx]}"

    def _pronoun(self, t: str, last: Turn | None) -> str | None:
        """'close it' after opening notepad -> 'close notepad'; 'play lofi on it' after youtube -> '... on youtube'."""
        if last is None or _NEVER.search(t):
            return None
        tgt = last.target()
        if tgt is None:
            return None
        key, value = tgt
        is_app = last.tool in _APP_TOOLS or key in ("name", "app")
        if last.tool == "close_app":
            is_app = False   # "open it again" after closing is fine, but "close it" twice is not a reference
            if re.match(r"^(?:open|launch|start|reopen|restart)\s+(?:it|that)(?:\s+again|\s+back)?$", t):
                return f"open {value}"
            return None
        if is_app:
            m = re.match(rf"^(?:now\s+|and\s+|then\s+|please\s+)?(?P<v>{_APP_VERBS})\s+(?:it|that|this)(?:\s+(?:app|window|program))?"
                         rf"(?P<rest>\s+(?:back|up|again|to\s+the\s+(?:left|right)|down))?$", t)
            if m:
                verb, rest = m.group("v"), (m.group("rest") or "").strip()
                if verb.startswith("bring") and rest == "back" or verb == "bring back":
                    return f"switch to {value}"
                if verb in ("open", "launch", "start") and last.tool == "open_app" and not rest:
                    return None      # already open
                return f"{verb} {value}" + (f" {rest}" if rest and rest not in ("again",) else "")
            m = re.match(r"^bring\s+(?:it|that)\s+back$", t)
            if m:
                return f"switch to {value}"
        site = value if last.tool in ("open_website", "open_app", "android_open_app") else ""
        if site:
            m = re.match(r"^(?P<cmd>(?:play|search(?:\s+for)?|look\s+up|find|watch|stream|show(?:\s+me)?)\s+.+?)\s+(?:on|in)\s+(?:it|that|there)$", t)
            if m:
                name = last.slots.get("title") or value
                name = re.sub(r"^https?://(?:www\.)?|\.(?:com|in|org)\b.*$", "", str(name))
                return f"{m.group('cmd')} on {name}"
        if last.tool in ("find_file", "search_files") and re.search(r"\.\w{1,5}$", value):
            if re.match(r"^(?:open|show|launch|run)\s+(?:it|that|this)(?:\s+file)?$", t):
                return f"open {value}"
        return None

    @staticmethod
    def _number(t: str, last: Turn | None) -> str | None:
        """'make it 60' / 'actually 40' / 'no I said 17' -> the last command with the new number."""
        if last is None:
            return None
        m = re.match(rf"^(?:no\s*,?\s+|nope\s*,?\s+|actually\s*,?\s+|sorry\s*,?\s+|wait\s*,?\s+|oops\s*,?\s+)*"
                     rf"(?:(?:make|change|set|put|turn)\s+(?:it|that)\s+(?:to\s+|at\s+|up\s+to\s+|down\s+to\s+)?|i\s+(?:said|meant)\s+|"
                     rf"(?:make\s+)?that\s+|(?:to|at)\s+)?(?P<n>{_NUM})\s*(?P<u>%|percent|per\s+cent|pm|am|o'?clock|"
                     rf"minutes?|mins?|hours?|seconds?)?(?:\s+instead|\s+please)?$", t)
        if not m:
            return None
        n = m.group("n")
        if re.search(r"send|dial|call|delete|remove|uninstall|install|pay|share|forward|email|reply|post|power|message|"
                     r"transfer|push|upload", last.tool):
            return None   # a new number for a call or a send is a new request, said in full
        explicit = re.match(r"^(?:no|nope|actually|sorry|wait|oops|make|change|set|put|turn|i\s+said|i\s+meant|that|to|at)\b", t)
        if not explicit and not any(q in last.text for q in _ADJUSTABLE):
            return None   # a bare "5" only adjusts a volume / brightness just set
        numbers = list(re.finditer(rf"(?<![\w.]){_NUM}(?![\w.])", last.text))
        if not numbers:
            return None
        hit = None
        for v in last.slots.values():
            if isinstance(v, (int, float)) or (isinstance(v, str) and re.fullmatch(_NUM, v.strip())):
                hit = next((x for x in numbers if float(x.group()) == float(v)), None)
                if hit:
                    break
        if hit is None:
            if len(numbers) != 1:
                return None   # "remind me at 5 for 10 minutes" + "make it 6": which number? ask instead
            hit = numbers[0]
        return last.text[:hit.start()] + n + last.text[hit.end():]

    @staticmethod
    def _relative(t: str, last: Turn | None) -> str | None:
        """'a little higher' / 'make it louder' after a volume or brightness change."""
        if last is None:
            return None
        noun = next((q for q in _ADJUSTABLE if q in last.text), None)
        if noun is None:
            return None
        m = re.match(rf"^(?:(?:make|turn|put)\s+(?:it|that)\s+)?(?:a\s+(?:little|bit|tad)\s+(?:bit\s+)?|slightly\s+|bit\s+|much\s+|way\s+)?"
                     rf"(?:(?P<up>{_UP})|(?P<down>{_DOWN}))(?:\s+(?:please|still|again))?$", t)
        if not m:
            return None
        return f"{'increase' if m.group('up') else 'decrease'} the {noun}"

    def _new_target(self, t: str, last: Turn | None) -> str | None:
        """'do the same for calculator', 'now calculator', 'and in pune?', 'also to meena', 'no, notepad'."""
        if last is None:
            return None
        m = (re.match(r"^(?:(?:and\s+|now\s+|then\s+)?(?:do|try)\s+)?(?:the\s+)?same\s+(?:thing\s+)?(?:for|with|to|on)\s+(?P<x>.+)$", t)
             or re.match(r"^(?:no\s*,?\s+|nope\s*,?\s+|sorry\s*,?\s+|oops\s*,?\s+|actually\s*,?\s+)+(?:i\s+(?:meant|said)\s+|not\s+that\s*,?\s+)?(?P<x>.+)$", t)
             or re.match(r"^(?:i\s+meant|i\s+said)\s+(?P<x>.+)$", t)
             or re.match(r"^(?:and|now|then|also|plus)\s+(?:also\s+)?(?P<x>.+?)(?:\s+(?:too|also|as\s+well))?$", t)
             or re.match(r"^(?:what|how)\s+about\s+(?P<x>.+)$", t))
        if not m:
            return None
        x = m.group("x").strip(" ,?")
        if not x or _NOT_A_TARGET.match(x) or _VERB_START.match(x) or _NEVER.search(x) and not _NEVER.search(last.text) \
                or re.search(r"\b(?:it|that|this|them|one)\b", x) or len(x.split()) > 4:
            return None
        prep = re.match(r"^(?P<p>in|at|to|for|from|with|on)\s+(?P<v>.+)$", x)
        if prep:
            p, v = prep.group("p"), prep.group("v")
            # "weather in chennai" + "and in pune": replace what followed the same preposition
            pm = list(re.finditer(rf"\b{p}\s+(?P<w>[\w.'-]+(?:\s+(?!(?:at|on|in|to|for|from|with|and|by|about)\b)[\w.'-]+){{0,3}})", last.text))
            if pm:
                w = pm[-1]
                return last.text[:w.start("w")] + v + last.text[w.end("w"):]
            x = v
        tgt = last.target()
        if tgt is None or last.tool == "chat":
            return None   # a question is only re-asked with a new place / person after the same preposition
        key, value = tgt
        if key == "query" and len(value) > 0.8 * len(last.text):
            return None
        pos = last.text.lower().find(value.lower())
        if pos < 0:
            return None
        return last.text[:pos] + x + last.text[pos + len(value):]


def carryover_of(memory: Any) -> CarryOver | None:
    """The carry-over attached to a working memory (created on first use)."""
    if memory is None:
        return None
    co = getattr(memory, "_carryover", None)
    if co is None:
        try:
            co = CarryOver()
            setattr(memory, "_carryover", co)
        except Exception:
            return None
    return co
